"""Static DEX/ELF inventory and resolution for the Westlake APK gap harness.

The scanner deliberately makes a smaller claim than a compatibility test: it proves that a
referenced name/member is absent from an exact boot-classpath snapshot. It cannot prove semantic
compatibility, runtime reachability, or dynamic RegisterNatives bindings without runtime evidence.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import struct
import gc
import subprocess
import tempfile
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Iterator

from androguard.core.apk import APK
from androguard.core.dex import DEX, HiddenApiClassDataItem
from loguru import logger

from .contracts import ANDROID_JCA_PROVIDERS
from .native import (
    abi_from_archive_name,
    abi_from_machine,
    library_filename,
    recover_jni_registration_entries,
)
from .nativeprov import attribute_unresolved_imports, resolve_native_imports


SCHEMA_VERSION = "westlake-apk-gap/v0.2"
PLATFORM_PREFIXES = (
    "Landroid/",
    "Lcom/android/",
    "Ldalvik/",
    "Ljava/",
    "Ljavax/",
    "Llibcore/",
    "Lorg/apache/harmony/",
    "Lorg/json/",
    "Lorg/w3c/",
    "Lorg/xml/",
)
DEX_NAME_RE = re.compile(r"(?:^|/)classes(?:[2-9]|[1-9][0-9]+)?\.dex$")
DESCRIPTOR_RE = re.compile(r"\[*L[^;]+;")
CONST_OPS = {
    "const/4",
    "const/16",
    "const",
    "const/high16",
    "const-wide/16",
    "const-wide/32",
    "const-wide",
    "const-wide/high16",
    "const-string",
    "const-string/jumbo",
    "const-class",
}


def quiet_androguard() -> None:
    """Remove Androguard's per-item debug logging from CLI output."""
    logger.remove()
    # Android 15+ has emitted hidden-API domain values newer than Androguard 4.1.3's enum. The
    # flags do not participate in this scanner's class/member inventory, but rejecting an unknown
    # value prevents the whole DEX from loading. Preserve unknown numeric values as enum instances.
    for enum_type in (
        HiddenApiClassDataItem.DomapiApiFlag,
        HiddenApiClassDataItem.RestrictionApiFlag,
    ):
        if getattr(enum_type, "_westlake_forward_compatible", False):
            continue

        @classmethod
        def _missing_(cls: Any, value: int) -> Any:
            member = int.__new__(cls, value)
            member._name_ = f"UNKNOWN_{value}"
            member._value_ = value
            return member

        enum_type._missing_ = _missing_  # type: ignore[method-assign]
        enum_type._westlake_forward_compatible = True  # type: ignore[attr-defined]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact_descriptor(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        value = "".join(str(part) for part in value)
    return re.sub(r"\s+", "", str(value))


def component_type(descriptor: str) -> str:
    return descriptor.lstrip("[")


def is_platform_type(descriptor: str) -> bool:
    return component_type(descriptor).startswith(PLATFORM_PREFIXES)


def descriptor_types(descriptor: str) -> set[str]:
    return {component_type(match.group(0)) for match in DESCRIPTOR_RE.finditer(descriptor)}


def class_name_to_descriptor(name: str) -> str | None:
    name = name.strip()
    if not name:
        return None
    if name.startswith("["):
        return component_type(name.replace(".", "/"))
    if name.startswith("L") and name.endswith(";"):
        return name.replace(".", "/")
    if "/" in name or "." in name:
        return "L" + name.replace(".", "/").strip("L;") + ";"
    return None


def method_key(name: str, descriptor: str) -> str:
    return f"{name}{compact_descriptor(descriptor)}"


def field_key(name: str, descriptor: str) -> str:
    return f"{name}:{compact_descriptor(descriptor)}"


def method_tuple(item: Any) -> tuple[str, str, str]:
    return (
        str(item.get_class_name()),
        str(item.get_name()),
        compact_descriptor(item.get_descriptor()),
    )


def field_tuple(item: Any) -> tuple[str, str, str]:
    return (
        str(item.get_class_name()),
        str(item.get_name()),
        compact_descriptor(item.get_descriptor()),
    )


def dex_blobs(path: Path) -> Iterator[tuple[str, bytes]]:
    """Yield DEX entries without extracting untrusted ZIP paths."""
    if path.suffix.lower() == ".dex":
        yield path.name, path.read_bytes()
        return
    try:
        with zipfile.ZipFile(path) as archive:
            if path.suffix.lower() in {".xapk", ".apkm"}:
                for apk_name in _ordered_inner_apks(archive):
                    info = archive.getinfo(apk_name)
                    if info.file_size > 1024 * 1024 * 1024:
                        raise ValueError(f"refusing oversized inner APK {apk_name}: {info.file_size} bytes")
                    with zipfile.ZipFile(io.BytesIO(archive.read(apk_name))) as inner:
                        for name in sorted(
                            (name for name in inner.namelist() if DEX_NAME_RE.search(name)),
                            key=lambda name: (len(name), name),
                        ):
                            dex_info = inner.getinfo(name)
                            if dex_info.file_size > 256 * 1024 * 1024:
                                raise ValueError(f"refusing oversized DEX entry {apk_name}!{name}")
                            yield f"{apk_name}!{name}", inner.read(name)
                return
            names = sorted(
                (name for name in archive.namelist() if DEX_NAME_RE.search(name)),
                key=lambda name: (len(name), name),
            )
            for name in names:
                info = archive.getinfo(name)
                if info.file_size > 256 * 1024 * 1024:
                    raise ValueError(f"refusing oversized DEX entry {name}: {info.file_size} bytes")
                yield name, archive.read(name)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"{path} is neither a DEX nor a valid APK/JAR/ZIP") from exc


def _ordered_inner_apks(archive: zipfile.ZipFile) -> list[str]:
    names = [name for name in archive.namelist() if name.lower().endswith(".apk")]
    try:
        manifest = json.loads(archive.read("manifest.json"))
        ordered = [item["file"] for item in manifest.get("split_apks", []) if item.get("file") in names]
        return ordered + sorted(set(names) - set(ordered))
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return sorted(names, key=lambda name: ("config." in name or "split" in name, name))


NATIVE_CALL_DEPTH = 3


def _index_native_calls(artifacts: Iterable[Path], classes: dict[str, dict[str, Any]]) -> None:
    """Record, per framework method, the native methods it reaches within the framework.

    An app rarely calls a framework native itself: it calls a public wrapper and the wrapper calls
    the native, sometimes through another: AudioTrack.getBufferSizeInFrames calls its native
    directly, AudioManager.getPlaybackOffloadSupport reaches AudioSystem.native_get_offload_support
    through AudioSystem.getOffloadSupport. In a class whose natives are only partly registered, the
    wrapper is the only static trace of the gap. Calls are followed NATIVE_CALL_DEPTH deep, as
    declared (no virtual dispatch), through android.*, com.android.* and libcore methods. A second pass,
    because a native's owner may be defined in a later artifact.
    """
    natives = {(owner, key) for owner, record in classes.items() for key in record["native_methods"]}
    if not natives:
        return
    # libcore too: its natives are not all registered either (sun.nio.ch.Net's, reached from the
    # public NIO channel classes).
    framework = ("Landroid/", "Lcom/android/", "Ljava/", "Ljavax/", "Lsun/", "Llibcore/", "Ljdk/", "Ldalvik/")
    callees: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for path in artifacts:
        for _, blob in dex_blobs(path.resolve()):
            dex = DEX(blob)
            for class_def in dex.get_classes():
                owner = str(class_def.get_name())
                record = classes.get(owner)
                if record is None or record["artifact"] != path.resolve().name or not owner.startswith(framework):
                    continue
                for method in class_def.get_methods():
                    targets: set[tuple[str, str]] = set()
                    try:
                        instructions = list(method.get_instructions())
                    except Exception:
                        continue
                    for instruction in instructions:
                        if not instruction.get_name().startswith("invoke-"):
                            continue
                        try:
                            target_owner, target, proto = dex.get_cm_method(int(instruction.get_ref_kind()))
                        except Exception:
                            continue
                        if str(target_owner).startswith(framework):
                            targets.add((str(target_owner), method_key(str(target), compact_descriptor(proto))))
                    if targets:
                        callees[(owner, method_key(method.get_name(), method.get_descriptor()))] = targets
    for (owner, key), direct in callees.items():
        reached: set[tuple[str, str]] = set()
        frontier, seen = direct, {(owner, key)}
        for _ in range(NATIVE_CALL_DEPTH):
            following: set[tuple[str, str]] = set()
            for callee in frontier - seen:
                seen.add(callee)
                if callee in natives:
                    reached.add(callee)
                else:
                    following |= callees.get(callee, set())
            frontier = following
        if reached:
            classes[owner].setdefault("native_calls", {})[key] = sorted(f"{o}->{k}" for o, k in reached)


def class_record(class_def: Any, artifact: str) -> dict[str, Any]:
    methods: list[str] = []
    fields: list[str] = []
    hollow_methods: list[str] = []
    native_methods: list[str] = []
    for method in class_def.get_methods():
        key = method_key(method.get_name(), method.get_descriptor())
        methods.append(key)
        flags = set(str(method.get_access_flags_string()).split())
        if "native" in flags:
            native_methods.append(key)
        elif _is_hollow_method(method):
            hollow_methods.append(key)
    for fld in class_def.get_fields():
        fields.append(field_key(fld.get_name(), fld.get_descriptor()))
    interfaces = [str(item) for item in class_def.get_interfaces()]
    return {
        "artifact": artifact,
        "super": str(class_def.get_superclassname() or ""),
        "interfaces": sorted(interfaces),
        "methods": sorted(set(methods)),
        "fields": sorted(set(fields)),
        "hollow_methods": sorted(set(hollow_methods)),
        "native_methods": sorted(set(native_methods)),
        "hollow_class_candidate": _is_hollow_class(class_def),
    }


def _is_hollow_method(method: Any) -> bool:
    name = str(method.get_name())
    flags = set(str(method.get_access_flags_string()).split())
    if name in {"<init>", "<clinit>"} or flags & {"abstract", "native"}:
        return False
    code = method.get_code()
    if code is None:
        return False
    names = [
        instruction.get_name()
        for instruction in code.get_bc().get_instructions()
        if instruction.get_name() != "nop"
    ]
    if names == ["return-void"]:
        return True
    return len(names) == 2 and names[0] in CONST_OPS and names[1].startswith("return")


def _is_hollow_class(class_def: Any) -> bool:
    real_methods = []
    for method in class_def.get_methods():
        if str(method.get_name()) not in {"<init>", "<clinit>"}:
            real_methods.append(method)
    return not real_methods and not list(class_def.get_fields())


# Relocation tags only bionic's linker applies. OH's musl applies DT_ANDROID_RELA (APS2 packed) and
# standard DT_RELR -- its own libraries carry both -- but skips DT_ANDROID_RELR, leaving every
# pointer it relocates at its link-time value (Meta's libraries: an INIT_ARRAY entry of 0x2ae2c
# was called).
ANDROID_RELOCATION_TAGS = {0x6FFFE000: "ANDROID_RELR"}


def _android_relocation_tags(readelf_text: str) -> list[str]:
    found = {int(tag, 16) for tag in re.findall(r"^\s*0x([0-9a-fA-F]+)\s+\(", readelf_text, re.M)}
    return sorted(name for tag, name in ANDROID_RELOCATION_TAGS.items() if tag in found)


_VERSIONED_IMPORT = re.compile(r"\sUND\s+([A-Za-z_][\w.$]*)@([A-Za-z_]\w*)")


def import_versions(readelf_text: str) -> dict[str, Any]:
    """Imports that ask for a symbol version (Bionic's libc: __system_property_read_callback@LIBC_O),
    from readelf's dynamic symbol table."""
    found = {match[1]: match[2] for match in _VERSIONED_IMPORT.finditer(readelf_text)}
    return {"import_versions": found} if found else {}


_SIGNAL_NAMES = ("sigaction", "sigaction64", "sigprocmask", "sigprocmask64", "pthread_sigmask", "pthread_sigmask64")


def signal_lookups(raw: bytes, imported: set[str]) -> dict[str, Any]:
    """Signal calls a library names as a string without importing them: it looks them up with dlsym,
    usually in libc's own handle, past any interposer (ByteDance's bytesig in shadowhook and
    bytehook takes sigaction64 or sigaction that way to put its handler first)."""
    names = sorted(name for name in _SIGNAL_NAMES
                   if name not in imported and b"\x00" + name.encode() + b"\x00" in raw)
    return {"signal_lookups": names} if names else {}


_EGL_NAMES = ("eglCreateWindowSurface", "eglTerminate")


def egl_lookups(raw: bytes, imported: set[str]) -> dict[str, Any]:
    """EGL entry points a library names as a string without importing them: it dlopens libEGL.so
    and looks them up by handle, past the preloaded shim's own (SDL does this for all of EGL)."""
    names = sorted(name for name in _EGL_NAMES
                   if name not in imported and b"\x00" + name.encode() + b"\x00" in raw)
    return {"egl_lookups": names} if names else {}


_GLES3_NAMES = tuple(json.loads((Path(__file__).parent / "data" / "gles3-core-entry-points.json").read_text())["names"])
# Longest first, so a name is never cut short by a shorter one it starts with (glGetString, glGetStringi).
_GLES3_PATTERN = re.compile(rb"(" + b"|".join(re.escape(name.encode()) for name in
                                              sorted(_GLES3_NAMES, key=len, reverse=True)) + rb")(?![A-Z0-9_])")


def gles3_lookups(raw: bytes, imported: set[str]) -> dict[str, Any]:
    """GLES 3 core entry points a library names as a string without importing them: a GL loader
    that dlopens libGLESv2.so and looks each one up by handle, as Android's libGLESv2.so carries
    them. Go packs its strings without terminators, so a name followed by more letters still
    counts, but not one an upper-case letter, digit or underscore continues: glDrawBuffers inside
    glDrawBuffersEXT is not a lookup of it. Each "gl" starts a candidate, as the next packed
    string may begin right after a name."""
    if b"gl" not in raw:
        return {}
    found = {match.decode() for match in _GLES3_PATTERN.findall(raw.replace(b"gl", b"\x00gl"))}
    names = sorted(found - imported)
    return {"gles3_lookups": names} if names else {}


def vm_lookups(raw: bytes, imported: set[str], exported: set[str]) -> dict[str, Any]:
    """How a library finds the process's JavaVM without being handed one: JNI_GetCreatedJavaVMs,
    imported (the NDK's libnativehelper, API 31) or named for a dlsym (Element X's Rust library:
    dlsym(dlopen(NULL), ...))."""
    name = "JNI_GetCreatedJavaVMs"
    if name in exported:
        return {}
    if name in imported:
        return {"vm_lookup": "import"}
    return {"vm_lookup": "by-name"} if b"\x00" + name.encode() + b"\x00" in raw else {}


_ART_INTERNAL = re.compile(rb"_ZN3art[A-Za-z0-9_]{4,}")


def art_internal_names(raw: bytes) -> dict[str, Any]:
    """ART's own C++ symbols a library names: performance and crash libraries (ByteDance's jato,
    sysoptimizer, godzilla; npth) look them up in libart.so and patch the runtime through them, at
    offsets they choose by the device's SDK level. Empty for an ordinary library."""
    names = sorted({m.decode() for m in _ART_INTERNAL.findall(raw)})
    return {"art_internal_symbols": len(names), "art_internal_sample": names[:6]} if names else {}


_PACKED_RELOCATION_TAGS = {0x6000000F, 0x60000010, 0x60000011, 0x60000012}  # DT_ANDROID_REL{,SZ}, RELA{,SZ}


def null_array_entries(raw: bytes) -> dict[str, int] | None:
    """Null or -1 entries in the init and fini arrays that no relocation fills: bionic skips them
    (soinfo::call_array), OH's musl calls them and jumps to address 0 (TikTok's libttffmpeg.so).
    None when the library's relocations are in Android's packed format, which is not decoded here."""
    if raw[:4] != b"\x7fELF" or raw[4] != 2 or raw[5] != 1:
        return None
    u64 = lambda at: int.from_bytes(raw[at:at + 8], "little")
    phoff, count = u64(0x20), int.from_bytes(raw[0x38:0x3A], "little")
    loads, dynamic = [], None
    for index in range(count):
        header = phoff + index * 56
        kind = int.from_bytes(raw[header:header + 4], "little")
        if kind == 1:
            loads.append((u64(header + 16), u64(header + 8), u64(header + 32)))
        elif kind == 2:
            dynamic = (u64(header + 8), u64(header + 32))
    if dynamic is None:
        return {}

    def offset_of(vaddr: int) -> int | None:
        return next((offset + vaddr - start for start, offset, size in loads if start <= vaddr < start + size), None)

    tags: dict[int, int] = {}
    for position in range(dynamic[0], min(dynamic[0] + dynamic[1], len(raw) - 15), 16):
        tag = u64(position)
        if tag == 0:
            break
        tags.setdefault(tag, u64(position + 8))
    if _PACKED_RELOCATION_TAGS & set(tags):
        return None
    targets: set[int] = set()
    if 7 in tags and 8 in tags and offset_of(tags[7]) is not None:
        start, entry = offset_of(tags[7]), tags.get(9, 24) or 24
        targets = {u64(at) for at in range(start, min(start + tags[8], len(raw) - 7), entry)}
    out = {}
    for name, array, size in (("init", 25, 27), ("fini", 26, 28)):
        if array not in tags or size not in tags or offset_of(tags[array]) is None:
            continue
        start = offset_of(tags[array])
        nulls = sum(1 for i in range(tags[size] // 8)
                    if u64(start + 8 * i) in (0, 0xFFFFFFFFFFFFFFFF) and tags[array] + 8 * i not in targets)
        if nulls:
            out[name] = nulls
    return out


def packed_init_entries(raw: bytes) -> dict[str, int]:
    """Init array entries of a library whose relocations come only in Android's packed format
    (DT_ANDROID_REL or DT_ANDROID_RELA, no RELR): every slot such a table fills reads as zero in the
    file. The runtime's init array sanitizer, which drops null entries before ART opens a library,
    read all of libwaze.so's 2189 that way and dropped them. Empty when the library has none."""
    if raw[:4] != b"\x7fELF" or raw[4] != 2 or raw[5] != 1:
        return {}
    u64 = lambda at: int.from_bytes(raw[at:at + 8], "little")
    phoff, count = u64(0x20), int.from_bytes(raw[0x38:0x3A], "little")
    tags: dict[int, int] = {}
    for index in range(count):
        header = phoff + index * 56
        if int.from_bytes(raw[header:header + 4], "little") != 2:
            continue
        start, size = u64(header + 8), u64(header + 32)
        for position in range(start, min(start + size, len(raw) - 15), 16):
            tag = u64(position)
            if tag == 0:
                break
            tags.setdefault(tag, u64(position + 8))
    relr = {35, 36, 0x6FFFE000, 0x6FFFE001}
    if not _PACKED_RELOCATION_TAGS & set(tags) or relr & set(tags) or tags.get(27, 0) < 8:
        return {}
    return {"packed_init_entries": tags[27] // 8}


#: Bionic's PTHREAD_RECURSIVE_MUTEX_INITIALIZER and PTHREAD_ERRORCHECK_MUTEX_INITIALIZER: the type in
#: bits 14-15 of the first of the mutex's ten words. musl keeps its type in the low bits and reads
#: both as a normal mutex, so a recursive lock deadlocks on its own thread.
_BIONIC_MUTEX_TYPES = {0x4000: "recursive", 0x8000: "errorcheck"}
_MUTEX_LOCKS = ("pthread_mutex_lock", "pthread_mutex_trylock", "pthread_mutex_timedlock")


def _sext(value: int, bits: int) -> int:
    return value - (1 << bits) if value & (1 << (bits - 1)) else value


def x0_address_before(words: list[int], index: int, base: int, got: dict[int, int] | None = None) -> int | None:
    """The address the call at ``words[index]`` passes in x0, when the instructions just before it
    build it: adrp then add, through movs, or a GOT load (adrp then ldr). None for anything else: a
    call, branch or other write in between, or a value from memory the GOT does not explain."""
    # Walking back from the call: ``want`` is the register x0's value comes from, ``offset`` what
    # adds put on top of it. A GOT load (ldr) moves the offset so far onto the loaded pointer.
    want, offset, slot, after_load = 0, 0, None, 0
    for j in range(index - 1, max(index - 24, -1), -1):
        insn = words[j]
        if (insn & 0x7C000000) == 0x14000000 or (insn & 0xFFFFFC1F) in (0xD63F0000, 0xD65F0000, 0xD61F0000):
            return None                                   # b, bl, blr, ret, br: x0 is not built here
        if (insn & 0x1F) != want:
            continue
        if (insn & 0xFF800000) == 0x91000000:             # add xd, xn, #imm{, lsl 12}
            offset += ((insn >> 10) & 0xFFF) << (12 * ((insn >> 22) & 1))
            want = (insn >> 5) & 0x1F
        elif (insn & 0xFFE0FFE0) == 0xAA0003E0:           # mov xd, xm
            want = (insn >> 16) & 0x1F
        elif (insn & 0xFFC00000) == 0xF9400000 and slot is None and got is not None:
            slot, after_load, offset = ((insn >> 10) & 0xFFF) * 8, offset, 0   # ldr xd, [xn, #imm]
            want = (insn >> 5) & 0x1F
        elif (insn & 0x9F000000) == 0x90000000:           # adrp xd, page
            page = ((base + 4 * j) & ~0xFFF) + (_sext((((insn >> 5) & 0x7FFFF) << 2) | ((insn >> 29) & 3), 21) << 12)
            if slot is None:
                return page + offset
            target = (got or {}).get(page + offset + slot)
            return None if target is None else target + after_load
        else:
            return None
    return None


def _plt_stubs(elf: Any, names: Iterable[str]) -> tuple[set[int], dict[int, int]]:
    """The addresses of the PLT entries that call any of ``names``, and the GOT slots whose
    relocations hold a known address (RELATIVE, or GLOB_DAT of a symbol the library defines)."""
    from elftools.elf.relocation import RelocationSection

    names = set(names)
    jump_slots, got = {}, {}
    for relocations in elf.iter_sections():
        if not isinstance(relocations, RelocationSection) or not relocations.is_RELA():
            continue
        symbols = elf.get_section(relocations["sh_link"])
        for relocation in relocations.iter_relocations():
            kind, index = relocation["r_info_type"], relocation["r_info_sym"]
            if kind == 1026 and index:                    # R_AARCH64_JUMP_SLOT
                jump_slots[relocation["r_offset"]] = symbols.get_symbol(index).name
            elif kind == 1027:                            # R_AARCH64_RELATIVE
                got[relocation["r_offset"]] = relocation["r_addend"]
            elif kind == 1025 and index:                  # R_AARCH64_GLOB_DAT
                symbol = symbols.get_symbol(index)
                if symbol["st_shndx"] != "SHN_UNDEF":
                    got[relocation["r_offset"]] = symbol["st_value"] + relocation["r_addend"]
    stubs = set()
    plt = elf.get_section_by_name(".plt")
    if plt is not None:
        code, base = plt.data(), plt["sh_addr"]
        words = [int.from_bytes(code[i:i + 4], "little") for i in range(0, len(code) - 3, 4)]
        for i in range(len(words) - 1):
            adrp, load = words[i], words[i + 1]
            if (adrp & 0x9F00001F) != 0x90000010 or (load & 0xFFC003FF) != 0xF9400211:
                continue                                  # adrp x16, page; ldr x17, [x16, #slot]
            page = ((base + 4 * i) & ~0xFFF) + (_sext((((adrp >> 5) & 0x7FFFF) << 2) | ((adrp >> 29) & 3), 21) << 12)
            if jump_slots.get(page + ((load >> 10) & 0xFFF) * 8) in names:
                stubs.add(base + 4 * i)
                if i and words[i - 1] == 0xD503245F:      # bti c opens the entry
                    stubs.add(base + 4 * (i - 1))
    return stubs, got


def _writes(insn: int, register: int) -> bool:
    """Whether an instruction may write ``register`` (its destination field, bits 0-4). Stores name
    the register they read there and are not writes; anything else with that field is taken as one.
    Field 31 is sp only for add and sub (immediate); everywhere else it is xzr."""
    if (insn & 0x1F) != register:
        return False
    if register == 31:
        return (insn & 0x7F800000) in (0x11000000, 0x51000000)
    return not ((insn & 0x0A000000) == 0x08000000 and not insn & (1 << 22))   # a store: str, stp, stur


def register_base_before(words: list[int], index: int, register: int) -> tuple[int, int, int] | None:
    """How the instructions just before the call at ``words[index]`` build ``register``: as another
    register plus a constant (add xd, xn, #imm; mov xd, xm). (base register, offset, the index of the
    instruction) or None for anything else, or a call or branch in between."""
    for j in range(index - 1, max(index - 24, -1), -1):
        insn = words[j]
        if (insn & 0x7C000000) == 0x14000000 or (insn & 0xFFFFFC1F) in (0xD63F0000, 0xD65F0000, 0xD61F0000):
            return None
        if not _writes(insn, register):
            continue
        if (insn & 0xFF800000) == 0x91000000:             # add xd, xn, #imm{, lsl 12}
            return (insn >> 5) & 0x1F, ((insn >> 10) & 0xFFF) << (12 * ((insn >> 22) & 1)), j
        if (insn & 0xFFE0FFE0) == 0xAA0003E0:             # mov xd, xm
            return (insn >> 16) & 0x1F, 0, j
        return None
    return None


def thread_handles_in_argument(data: bytes) -> dict[str, int]:
    """Calls to pthread_create that store the new thread's handle inside the object they hand the
    thread: pthread_create(&obj->thread, attr, start, obj), x0 built as x3 plus a constant. Bionic
    stores the handle before the thread runs; musl stores it after clone returns, so a thread that
    reads its own handle there first can read 0 (ByteDance's vcbasekit names its threads with it).
    Such a call is a risk, not a proof: the thread may never read the field."""
    try:
        from elftools.elf.elffile import ELFFile

        elf = ELFFile(io.BytesIO(data))
        if elf["e_machine"] != "EM_AARCH64":
            return {}
        stubs, _ = _plt_stubs(elf, ("pthread_create",))
        text = elf.get_section_by_name(".text")
        if not stubs or text is None:
            return {}
        code, base = text.data(), text["sh_addr"]
        words = [w for (w,) in struct.iter_unpack("<I", code[:len(code) - len(code) % 4])]
        calls = 0
        for index, insn in enumerate(words):
            if (insn & 0xFC000000) != 0x94000000 or base + 4 * index + _sext(insn & 0x3FFFFFF, 26) * 4 not in stubs:
                continue
            handle, argument = register_base_before(words, index, 0), register_base_before(words, index, 3)
            if handle is None or argument is None or argument[1] != 0 or handle[0] != argument[0]:
                continue
            # The shared base must hold one value for both: not rewritten after the first of them.
            if not any(_writes(words[j], handle[0]) for j in range(min(handle[2], argument[2]) + 1, index)):
                calls += 1
        return {"thread_handle_in_argument": calls} if calls else {}
    except Exception:
        return {}


#: Bionic's TLS slots above the arm64 thread pointer (bionic/libc/platform/bionic/tls_defines.h), by
#: byte offset. Slot 5, the stack guard, is read by nearly all Android-built code and is not counted.
_BIONIC_TLS_SLOTS = {0: "self", 8: "thread id", 16: "app", 24: "opengl", 32: "opengl api", 48: "sanitizer",
                     56: "art thread self"}


def bionic_tls_slots(data: bytes) -> dict[str, Any]:
    """Bionic TLS slots the library's code reads directly: mrs xT, tpidr_el0, then a load from xT at
    one of the slots' fixed offsets. OH musl keeps its own slots below the thread pointer and its TLS
    blocks above it, so these words hold something else: ByteDance's security libraries inline
    Bionic's vfork, which clears pthread_internal_t's cached pid through the thread id slot (CapCut
    stored to -1 + 20), and profilers read ART's Thread* from slot 7."""
    try:
        from elftools.elf.elffile import ELFFile

        elf = ELFFile(io.BytesIO(data))
        if elf["e_machine"] != "EM_AARCH64":
            return {}
        text = elf.get_section_by_name(".text")
        if text is None:
            return {}
        code = text.data()
        words = [w for (w,) in struct.iter_unpack("<I", code[:len(code) - len(code) % 4])]
        found: Counter = Counter()
        for index, insn in enumerate(words):
            if (insn & 0xFFFFFFE0) != 0xD53BD040:                 # mrs xT, tpidr_el0
                continue
            register = insn & 0x1F
            for later in words[index + 1:index + 5]:
                if (later & 0xFFC00000) == 0xF9400000 and ((later >> 5) & 0x1F) == register:   # ldr xM, [xT, #imm]
                    offset = ((later >> 10) & 0xFFF) * 8
                    if offset in _BIONIC_TLS_SLOTS:
                        found[_BIONIC_TLS_SLOTS[offset]] += 1
                    break
                if _writes(later, register):
                    break
        return {"bionic_tls_slots": dict(sorted(found.items()))} if found else {}
    except Exception:
        return {}


def bionic_static_mutexes(data: bytes) -> dict[str, Any]:
    """Mutexes initialized with Bionic's recursive or error-checking static initializer that the
    library's code locks: one whose address is built right before a call to pthread_mutex_lock (or
    trylock, timedlock). A ten-word object in .data that only looks like one, and is never passed to
    a lock, is not counted; one locked through a pointer kept elsewhere is missed."""
    try:
        from elftools.elf.elffile import ELFFile

        elf = ELFFile(io.BytesIO(data))
        if elf["e_machine"] != "EM_AARCH64":
            return {}
        section = elf.get_section_by_name(".data")
        if section is None or section["sh_type"] == "SHT_NOBITS":
            return {}
        contents, start = section.data(), section["sh_addr"]
        candidates = {}
        for at in range((-start) % 4, len(contents) - 39, 4):
            first = int.from_bytes(contents[at:at + 4], "little")
            if first in _BIONIC_MUTEX_TYPES and not any(contents[at + 4:at + 40]):
                candidates[start + at] = _BIONIC_MUTEX_TYPES[first]
        if not candidates:
            return {}
        stubs, got = _plt_stubs(elf, _MUTEX_LOCKS)
        text = elf.get_section_by_name(".text")
        if not stubs or text is None:
            return {}
        code, base = text.data(), text["sh_addr"]
        words = [w for (w,) in struct.iter_unpack("<I", code[:len(code) - len(code) % 4])]
        locked = {}
        for index, insn in enumerate(words):
            if (insn & 0xFC000000) == 0x94000000 and base + 4 * index + _sext(insn & 0x3FFFFFF, 26) * 4 in stubs:
                address = x0_address_before(words, index, base, got)
                if address in candidates:
                    locked[address] = candidates[address]
        if not locked:
            return {}
        counts = Counter(locked.values())
        return {"bionic_static_mutexes": dict(sorted(counts.items()))}
    except Exception:
        return {}


def read_elf(
    path: Path | None = None,
    data: bytes | None = None,
    label: str = "",
    abi: str | None = None,
) -> dict[str, Any]:
    if path is None and data is None:
        raise ValueError("read_elf requires a path or bytes")
    temp_name: str | None = None
    try:
        if path is None:
            with tempfile.NamedTemporaryFile(prefix="westlake-elf-", suffix=".so", delete=False) as tmp:
                tmp.write(data or b"")
                temp_name = tmp.name
            path = Path(temp_name)
        proc = subprocess.run(
            ["readelf", "--wide", "-h", "-d", "-Ws", "-n", str(path)],
            capture_output=True,
            text=True,
            # Symbol tables may carry bytes that are not UTF-8 (OsmAnd); one must not abort the scan.
            errors="replace",
            timeout=45,
            check=False,
        )
        text = proc.stdout
        machine = _match_value(text, r"^\s*Machine:\s*(.+)$")
        soname = _match_value(text, r"\(SONAME\).*\[([^]]+)\]")
        build_id = _match_value(text, r"Build ID:\s*([0-9a-fA-F]+)")
        needed = sorted(set(re.findall(r"\(NEEDED\).*\[([^]]+)\]", text)))
        raw = data if data is not None else path.read_bytes()
        exports, undefined, undefined_weak = _dynamic_symbols(raw)
        if exports is None:
            exports, undefined, undefined_weak = _dynamic_symbols_from_text(text)
        registration_entries, registration_error = recover_jni_registration_entries(raw)
        machine_abi = abi_from_machine(machine)
        record = {
            "name": label or path.name,
            "sha256": sha256_bytes(raw),
            "bytes": len(raw),
            "machine": machine,
            "abi": abi or machine_abi,
            "archive_abi": abi,
            "machine_abi": machine_abi,
            "abi_matches_machine": not abi or not machine_abi or abi == machine_abi,
            "soname": soname,
            "build_id": build_id,
            "needed": needed,
            "android_relocation_tags": _android_relocation_tags(text),
            "null_array_entries": null_array_entries(raw),
            **packed_init_entries(raw),
            **art_internal_names(raw),
            **signal_lookups(raw, set(undefined) | set(undefined_weak)),
            **egl_lookups(raw, set(undefined) | set(undefined_weak)),
            **gles3_lookups(raw, set(undefined) | set(undefined_weak)),
            **vm_lookups(raw, set(undefined) | set(undefined_weak), set(exports or ())),
            **bionic_static_mutexes(raw),
            **thread_handles_in_argument(raw),
            **bionic_tls_slots(raw),
            **import_versions(text),
            "exported_symbols": sorted(exports),
            "undefined_symbols": sorted(undefined),
            "undefined_weak_symbols": sorted(undefined_weak),
            "runtime_symbol_candidates": runtime_symbol_candidates(
                raw, set(exports or ()) | set(undefined) | set(undefined_weak)),
            "jni_exports": sorted(name for name in exports if name.startswith("Java_")),
            "has_jni_onload": "JNI_OnLoad" in exports,
            "jni_registration_entries": registration_entries,
            "readelf_ok": proc.returncode == 0,
        }
        if registration_error:
            record["registration_scan_error"] = registration_error
        return record
    finally:
        if temp_name:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


#: A platform entry point looked up by name at runtime: AFoo_bar, ASurfaceTransaction_setBuffer.
#: Deliberately narrow. Every string in a binary is a candidate for dlsym and almost none of them
#: are, so this matches the shape the NDK gives its C entry points and leaves the rest alone.
#: Matched against whole NUL-terminated strings, not anywhere in the file: the name handed to
#: dlsym is its own string literal, while the same letters inside a mangled C++ symbol or a longer
#: identifier are not a lookup. Anchoring cuts an engine's candidates by roughly ten times, which
#: matters because this list is what the on-device probe has to resolve one by one.
_RUNTIME_SYMBOL_SHAPE = re.compile(rb"[\x00-\x1f\"' ]([A-Z][A-Za-z0-9]{2,}_[A-Za-z0-9_]{2,})\x00")


def runtime_symbol_candidates(data: bytes, declared: set[str]) -> list[str]:
    """Platform entry points this ELF can reach by name at runtime rather than by declaring them.

    A dlopen/dlsym pair leaves nothing in the symbol table: the name exists only as a string, so
    the library never says it needs the function and a missing one is not a load failure. That is
    why an engine looking up fourteen NDK SurfaceControl entry points still scanned as 288 of 289
    resolved, and why losing them cost hardware compositing with no error anywhere.

    These are candidates and nothing more. A name of the right shape may never be passed to dlsym,
    may sit behind a version check that never fires, or may be one of several the caller tries in
    turn. Names built at runtime do not appear at all. Deciding any of them means performing the
    lookup on the board; this only narrows where to look.
    """
    found = {match.decode("ascii", "ignore") for match in _RUNTIME_SYMBOL_SHAPE.findall(data)}
    # A name it already imports is covered by the ordinary undefined-symbol check, which is
    # stronger evidence: the loader refuses to load the library at all when one is missing.
    return sorted(found - declared)


def _dynamic_symbols(data: bytes) -> tuple[set[str] | None, set[str], set[str]]:
    """Read .dynsym directly.

    readelf's text output is not column-stable: an IFUNC prints its type as
    ``<OS specific>: 10``, which is three whitespace-separated tokens where every other
    symbol has one, shifting the bind and name columns. On Android arm64 the optimized libc
    string and memory routines are all IFUNCs, so a column parser silently drops `strlen`,
    `strcmp`, `memcpy` and friends from a library's exports — and then reports every caller
    of them as a missing symbol.
    """
    exports: set[str] = set()
    undefined: set[str] = set()
    undefined_weak: set[str] = set()
    try:
        from elftools.elf.elffile import ELFFile
        from elftools.elf.sections import SymbolTableSection

        elf = ELFFile(io.BytesIO(data))
        section = elf.get_section_by_name(".dynsym")
        if not isinstance(section, SymbolTableSection):
            return None, undefined, undefined_weak
        for symbol in section.iter_symbols():
            name = (symbol.name or "").split("@", 1)[0]
            if not name:
                continue
            bind = symbol["st_info"]["bind"]
            if symbol["st_shndx"] == "SHN_UNDEF":
                undefined.add(name)
                if bind == "STB_WEAK":
                    # A weak undefined symbol is allowed to stay unresolved by design.
                    undefined_weak.add(name)
            elif bind in {"STB_GLOBAL", "STB_WEAK"}:
                exports.add(name)
        return exports, undefined, undefined_weak
    except Exception:
        return None, undefined, undefined_weak


def _dynamic_symbols_from_text(text: str) -> tuple[set[str], set[str], set[str]]:
    """Fallback column parse of ``readelf -Ws`` for inputs pyelftools cannot open."""
    exports: set[str] = set()
    undefined: set[str] = set()
    undefined_weak: set[str] = set()
    for line in text.splitlines():
        parts = line.split()
        if len(parts) < 8 or not parts[0].rstrip(":").isdigit():
            continue
        if parts[3].startswith("<OS") and len(parts) >= 10:
            parts = [*parts[:3], "IFUNC", *parts[6:]]
        ndx, name = parts[6], parts[7].split("@", 1)[0]
        if not name:
            continue
        if ndx == "UND":
            undefined.add(name)
            if parts[4] == "WEAK":
                undefined_weak.add(name)
        elif parts[4] in {"GLOBAL", "WEAK"}:
            exports.add(name)
    return exports, undefined, undefined_weak


def _match_value(text: str, pattern: str) -> str | None:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else None


def build_runtime_index(
    artifacts: Iterable[Path],
    bridge_libraries: Iterable[Path] = (),
    target_abi: str | None = None,
    system_libraries: Iterable[Path] = (),
) -> dict[str, Any]:
    """Index the exact boot-classpath order. The first definition of a duplicate class wins."""
    quiet_androguard()
    classes: dict[str, dict[str, Any]] = {}
    duplicates: dict[str, list[str]] = defaultdict(list)
    artifact_records: list[dict[str, Any]] = []
    for order, path in enumerate(artifacts):
        path = path.resolve()
        record = {
            "order": order,
            "name": path.name,
            "path": str(path),
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "dex_entries": [],
        }
        for dex_name, blob in dex_blobs(path):
            record["dex_entries"].append({"name": dex_name, "sha256": sha256_bytes(blob), "bytes": len(blob)})
            dex = DEX(blob)
            for class_def in dex.get_classes():
                owner = str(class_def.get_name())
                if owner in classes:
                    duplicates[owner].append(path.name)
                    continue
                classes[owner] = class_record(class_def, path.name)
        artifact_records.append(record)
    _index_native_calls(artifacts, classes)

    elf_records = [read_elf(path=path.resolve(), label=path.name) for path in bridge_libraries]
    system_records = [read_elf(path=path.resolve(), label=path.name) for path in system_libraries]
    inferred_abis = {record["abi"] for record in elf_records if record.get("abi")}
    if target_abi is None and len(inferred_abis) == 1:
        target_abi = next(iter(inferred_abis))
    if target_abi and inferred_abis and target_abi not in inferred_abis:
        raise ValueError(
            f"target ABI {target_abi} does not match bridge ELF ABIs: {', '.join(sorted(inferred_abis))}"
        )
    lock_material = json.dumps(
        {
            "boot_classpath": [record["sha256"] for record in artifact_records],
            "bridge_libraries": [record["sha256"] for record in elf_records],
            "system_libraries": [record["sha256"] for record in system_records],
            "target_abi": target_abi,
        },
        sort_keys=True,
    ).encode()
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "runtime_lock_id": "sha256:" + sha256_bytes(lock_material),
        "target_abi": target_abi,
        "boot_classpath": artifact_records,
        "bridge_libraries": elf_records,
        "system_libraries": system_records,
        "class_count": len(classes),
        "duplicate_class_count": len(duplicates),
        "duplicates": dict(sorted(duplicates.items())),
        "classes": classes,
    }


@dataclass
class DexInventory:
    dex_entries: list[dict[str, Any]] = field(default_factory=list)
    defined_classes: set[str] = field(default_factory=set)
    type_refs: set[str] = field(default_factory=set)
    method_refs: Counter[tuple[str, str, str]] = field(default_factory=Counter)
    field_refs: Counter[tuple[str, str, str]] = field(default_factory=Counter)
    method_sites: dict[tuple[str, str, str], list[dict[str, Any]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    field_sites: dict[tuple[str, str, str], list[dict[str, Any]]] = field(
        default_factory=lambda: defaultdict(list)
    )
    callable_owners: set[str] = field(default_factory=set)
    probes: list[dict[str, Any]] = field(default_factory=list)
    load_libraries: list[dict[str, Any]] = field(default_factory=list)
    service_requests: list[dict[str, Any]] = field(default_factory=list)
    jca_requests: list[dict[str, Any]] = field(default_factory=list)
    feature_queries: list[dict[str, Any]] = field(default_factory=list)
    nonnull_casts: list[dict[str, Any]] = field(default_factory=list)
    native_methods: list[dict[str, Any]] = field(default_factory=list)
    superclasses: dict[str, str] = field(default_factory=dict)
    own_intent_names: set[str] = field(default_factory=set)
    # Android's SQLite collations the app's SQL names (COLLATE UNICODE / LOCALIZED / PHONEBOOK).
    sql_collations: set[str] = field(default_factory=set)
    # Classes defining one of AFTER_START_CALLBACKS, with which ones.
    after_start_callbacks: dict[str, set[str]] = field(default_factory=dict)


_SQL_COLLATION = re.compile(r"\bCOLLATE\s+(UNICODE|LOCALIZED|PHONEBOOK)\b", re.I)


def sql_collations(strings: Iterable[str]) -> set[str]:
    """The collations Android registers on every SQLite connection that the app's SQL names:
    Fossify Notes reads its notes "ORDER BY title COLLATE UNICODE"."""
    return {m.group(1).upper() for text in strings if "OLLATE" in text.upper()
            for m in _SQL_COLLATION.finditer(text)}


def named_filter_targets(strings: Iterable[str], targets: dict[str, list[str]]) -> set[str]:
    """Which of the app's own filter schemes and actions (activity_filter_targets) its code names:
    a scheme as a string of its own (Uri.Builder().scheme(...)) or opening a URI, an action whole.
    Such a string is how the app reaches its own activities by implicit intent."""
    schemes, actions = set(targets.get("schemes") or ()), set(targets.get("actions") or ())
    if not schemes and not actions:
        return set()
    found = set()
    for text in strings:
        if text in schemes or text in actions:
            found.add(text)
        elif ":" in text and text.split(":", 1)[0] in schemes:
            found.add(text.split(":", 1)[0])
    return found


# Callbacks Android makes after onStart on an activity's way to its first resume, from the pending
# actions its launch marked: onRestoreInstanceState (with a saved state) and onPostCreate. A provider
# that resumes in a transaction of its own finds those actions cleared and makes neither.
AFTER_START_CALLBACKS = frozenset({"onPostCreate", "onRestoreInstanceState"})
# Library activities whose overrides of them are left out: AppCompat's onPostCreate installs a decor
# that setContentView has already installed.
_LIBRARY_ACTIVITY_PREFIXES = ("Landroidx/", "Landroid/support/", "Lcom/google/android/material/")


def _renamed(descriptor: str) -> bool:
    """A class R8 renamed: every segment of its name one or two characters (AppCompatActivity is
    Lk/h; in linphone). A manifest activity keeps its name; an app's renamed base class is
    indistinguishable from a library's and is left out."""
    return all(len(part) <= 2 for part in descriptor[1:-1].split("/"))


def after_start_overrides(activities: list[str], superclasses: dict[str, str],
                          callbacks: dict[str, set[str]]) -> list[dict[str, Any]]:
    """The app's activities whose own classes override an AFTER_START_CALLBACKS callback: the most
    derived such class in each activity's chain, the activity itself or a base class that kept its
    name. Linphone's MainActivity marks its first screen ready in onPostCreate and cancels every
    draw until then."""
    found = []
    for name in activities:
        current, depth = "L" + name.replace(".", "/") + ";", 0
        while current and depth < 32:
            if current in callbacks and not current.startswith(_LIBRARY_ACTIVITY_PREFIXES) \
                    and (depth == 0 or not _renamed(current)):
                found.append({"activity": name, "class": current, "callbacks": sorted(callbacks[current])})
                break
            current, depth = superclasses.get(current), depth + 1
    return found


def _activity_chains(activities: list[str], superclasses: dict[str, str]) -> dict[str, list[str]]:
    chains = {}
    for name in activities:
        chain, current = [], "L" + name.replace(".", "/") + ";"
        while current in superclasses and len(chain) < 32:
            current = superclasses[current]
            chain.append(current)
        chains[name] = chain
    return chains


def inventory_dex(path: Path, filter_targets: dict[str, list[str]] | None = None) -> DexInventory:
    quiet_androguard()
    result = DexInventory()
    for dex_name, blob in dex_blobs(path):
        dex = DEX(blob)
        dex_sha256 = sha256_bytes(blob)
        result.dex_entries.append({"name": dex_name, "sha256": dex_sha256, "bytes": len(blob)})
        try:
            strings = [str(text) for text in dex.get_strings()]
        except Exception:
            strings = []
        if filter_targets:
            result.own_intent_names |= named_filter_targets(strings, filter_targets)
        result.sql_collations |= sql_collations(strings)
        for c in dex.get_classes():
            result.defined_classes.add(str(c.get_name()))
            # Kept for the activity hierarchy: which engine base class a launch activity extends.
            result.superclasses[str(c.get_name())] = str(c.get_superclassname() or "")
            for m in c.get_methods():
                if str(m.get_name()) in AFTER_START_CALLBACKS and str(m.get_descriptor()).startswith("(Landroid/os/Bundle;"):
                    result.after_start_callbacks.setdefault(str(c.get_name()), set()).add(str(m.get_name()))
        for type_idx in range(dex.get_header_item().type_ids_size):
            type_name = component_type(str(dex.get_cm_type(type_idx)))
            if is_platform_type(type_name):
                result.type_refs.add(type_name)
        # The ID pools are the complete statically declared contract. Instruction walking below
        # adds call counts and proving sites, but references that are not in executable code (for
        # example encoded call sites) must not silently disappear.
        for method_ref in dex.get_methods():
            owner, name, descriptor = method_tuple(method_ref)
            if is_platform_type(owner):
                result.method_refs.setdefault((owner, name, descriptor), 0)
        for fld_ref in dex.get_fields():
            owner, name, descriptor = field_tuple(fld_ref)
            if is_platform_type(owner):
                result.field_refs.setdefault((owner, name, descriptor), 0)
        _inventory_defined_methods(dex, dex_name, dex_sha256, result)
        del dex
        gc.collect()
    return result


def _class_outlines(dex: DEX) -> dict[tuple[str, str, str], str]:
    """Static methods whose whole body returns one class constant. R8 outlines a const-class of a
    platform class newer than the app's minSdk into such a method, so the caller's own code never
    names the class: Fossify Messages asks getSystemService(k7.i()) for its RoleManager."""
    found: dict[tuple[str, str, str], str] = {}
    for class_def in dex.get_classes():
        for method in class_def.get_methods():
            if compact_descriptor(method.get_descriptor()) != "()Ljava/lang/Class;" or method.get_code() is None:
                continue
            try:
                body = list(method.get_instructions())
                if [i.get_name() for i in body] == ["const-class", "return-object"]:
                    found[method_tuple(method)] = str(dex.get_cm_type(int(body[0].get_ref_kind())))
            except Exception:
                continue
    return found


def _inventory_defined_methods(
    dex: DEX,
    dex_name: str,
    dex_sha256: str,
    out: DexInventory,
) -> None:
    outlines = _class_outlines(dex)
    for class_def in dex.get_classes():
        for method in class_def.get_methods():
            flags = set(str(method.get_access_flags_string()).split())
            if "native" in flags:
                owner, name, descriptor = method_tuple(method)
                short, long = jni_symbols(owner, name, descriptor)
                out.native_methods.append(
                    {
                        "owner": owner,
                        "name": name,
                        "descriptor": descriptor,
                        "dex": dex_name,
                        "dex_sha256": dex_sha256,
                        "jni_short": short,
                        "jni_long": long,
                    }
                )
            code = method.get_code()
            if code is None:
                continue
            caller = {
                "dex": dex_name,
                "owner": str(method.get_class_name()),
                "method": str(method.get_name()),
                "descriptor": compact_descriptor(method.get_descriptor()),
            }
            _inventory_instructions(dex, method, caller, out, outlines)


def _inventory_instructions(dex: DEX, method: Any, caller: dict[str, Any], out: DexInventory,
                            outlines: dict[tuple[str, str, str], str] | None = None) -> None:
    string_regs: dict[int, str] = {}
    class_regs: dict[int, str] = {}
    # The class an outline (see _class_outlines) just returned, for the move-result right after it.
    outlined: str | None = None
    # A service request whose result is about to be null-checked: R8 compiles Kotlin's non-null
    # checks to Object.getClass() on the value (or keeps Intrinsics.checkNotNull*), so a null
    # manager throws a few instructions after the call. clauncher's HomeFragment does that to
    # getSystemService("device_policy").
    pending: dict[str, Any] | None = None
    for offset, instruction in method.get_instructions_idx():
        name = instruction.get_name()
        try:
            operands = instruction.get_operands() or []
        except Exception:
            operands = []
        registers = [int(op[1]) for op in operands if int(op[0]) == 0]
        if pending is not None:
            if pending["register"] is None:
                # The result is taken right after the call, or discarded.
                if name == "move-result-object" and registers:
                    pending["register"] = registers[0]
                else:
                    pending = None
            elif registers and registers[0] == pending["register"] \
                    and name.startswith("invoke-") and _is_null_check(dex, instruction):
                pending["request"]["null_checked"] = True
                pending = None
            if pending is not None:
                pending["left"] -= 1
                if pending["left"] <= 0:
                    pending = None
        if outlined is not None:
            if name == "move-result-object" and registers:
                class_regs[registers[0]] = outlined
                string_regs.pop(registers[0], None)
                outlined = None
                continue
            outlined = None

        if name in {"const-string", "const-string/jumbo"} and registers:
            string_regs[registers[0]] = str(instruction.get_string())
            class_regs.pop(registers[0], None)
            if string_regs[registers[0]].startswith(KOTLIN_NONNULL_CAST + "android."):
                # Kotlin's `x as T` on a platform type: the message is the only trace in the dex
                # that a null result throws here instead of being checked.
                out.nonnull_casts.append({**caller, "offset": offset,
                                          "type": string_regs[registers[0]][len(KOTLIN_NONNULL_CAST):]})
            if string_regs[registers[0]] in ANDROID_JCA_PROVIDERS:
                # Libraries keep the provider name in a constant and pass it on through fields and
                # helpers, so the name itself is evidence even where the getInstance call is not.
                out.jca_requests.append({**caller, "offset": offset, "api": "provider name",
                                         "provider": string_regs[registers[0]]})
            continue
        if name == "const-class" and registers:
            try:
                class_regs[registers[0]] = str(dex.get_cm_type(int(instruction.get_ref_kind())))
            except Exception:
                class_regs.pop(registers[0], None)
            string_regs.pop(registers[0], None)
            continue
        if name.startswith("move-object") and len(registers) >= 2:
            for regs in (string_regs, class_regs):
                if registers[1] in regs:
                    regs[registers[0]] = regs[registers[1]]
                else:
                    regs.pop(registers[0], None)
            continue

        ref_kind: int | None = None
        try:
            ref_kind = int(instruction.get_ref_kind())
        except Exception:
            # Androguard exposes get_ref_kind on the base instruction class and raises a generic
            # "not implemented" exception for opcodes without a reference operand.
            pass

        if name.startswith("invoke-") and ref_kind is not None:
            try:
                owner, target, proto = dex.get_cm_method(ref_kind)
                descriptor = compact_descriptor(proto)
                key = (str(owner), str(target), descriptor)
                if outlines and name.startswith("invoke-static") and key in outlines:
                    outlined = outlines[key]
                out.callable_owners.add(str(owner))
                if is_platform_type(str(owner)):
                    out.method_refs[key] += 1
                    if len(out.method_sites[key]) < 8:
                        out.method_sites[key].append({**caller, "offset": offset, "opcode": name})
                _detect_string_call(key, registers, string_regs, caller, offset, out)
                requested = len(out.service_requests)
                _detect_service_call(key, registers, string_regs, class_regs, caller, offset, out)
                if len(out.service_requests) > requested:
                    pending = {"request": out.service_requests[-1], "register": None, "left": 6}
                _detect_jca_call(key, registers, string_regs, caller, offset, out)
                _detect_feature_query(key, registers, string_regs, caller, offset, out)
            except (IndexError, TypeError, ValueError):
                pass
        elif (
            ref_kind is not None
            and name.startswith(("iget", "iput", "sget", "sput"))
        ):
            try:
                owner, descriptor, target = dex.get_cm_field(ref_kind)
                key = (str(owner), str(target), compact_descriptor(descriptor))
                out.callable_owners.add(str(owner))
                if is_platform_type(str(owner)):
                    out.field_refs[key] += 1
                    if len(out.field_sites[key]) < 8:
                        out.field_sites[key].append({**caller, "offset": offset, "opcode": name})
            except (IndexError, TypeError, ValueError):
                pass

        # Most non-invoke instructions with a first register overwrite it. Clearing here avoids
        # treating an old constant as a later reflective argument while preserving direct flows.
        if registers and not name.startswith(("invoke-", "return", "if-", "iput", "sput", "aput", "throw")):
            string_regs.pop(registers[0], None)
            class_regs.pop(registers[0], None)


def _detect_string_call(
    key: tuple[str, str, str],
    registers: list[int],
    string_regs: dict[int, str],
    caller: dict[str, Any],
    offset: int,
    out: DexInventory,
) -> None:
    owner, name, descriptor = key
    string_register: int | None = None
    kind: str | None = None
    if owner == "Ljava/lang/Class;" and name == "forName" and registers:
        string_register, kind = registers[0], "Class.forName"
    elif name in {"findClass", "loadClass"} and "Ljava/lang/String;" in descriptor and len(registers) >= 2:
        string_register, kind = registers[1], f"{owner}->{name}"
    elif owner == "Ljava/lang/System;" and name in {"load", "loadLibrary"} and registers:
        value = string_regs.get(registers[0])
        if value is not None:
            out.load_libraries.append({**caller, "offset": offset, "api": name, "value": value})
        return
    if string_register is None:
        return
    value = string_regs.get(string_register)
    descriptor_value = class_name_to_descriptor(value or "")
    if descriptor_value:
        out.probes.append(
            {
                **caller,
                "offset": offset,
                "api": kind,
                "class_name": value,
                "descriptor": descriptor_value,
            }
        )


# Calls that ask the platform for a service by name or by manager class. The argument register
# for each: instance getSystemService(String|Class) takes it after `this`; the static forms take it
# first (ServiceManager) or second (ContextCompat, after the Context).
# Services an app reaches without ever naming them: a static framework accessor calls
# getSystemService inside the platform, so the app's dex holds no call site at all. Wikipedia died
# in onCreate on a null AccountManager.get(context) and its map had no row for the account service.
STATIC_SERVICE_ACCESSORS = {
    ("Landroid/accounts/AccountManager;", "get"): "account",
    ("Landroid/accounts/AccountManager;", "getInstance"): "account",
    ("Landroid/view/LayoutInflater;", "from"): "layout_inflater",
    ("Landroid/view/accessibility/AccessibilityManager;", "getInstance"): "accessibility",
    ("Landroid/telephony/SubscriptionManager;", "from"): "telephony_subscription_service",
    ("Landroid/telephony/TelephonyManager;", "from"): "phone",
    ("Landroid/app/NotificationManagerCompat;", "from"): "notification",
    ("Landroidx/core/app/NotificationManagerCompat;", "from"): "notification",
    ("Landroid/net/ConnectivityManager;", "from"): "connectivity",
    ("Landroid/os/storage/StorageManager;", "from"): "storage",
    ("Landroid/media/AudioManager;", "from"): "audio",
    ("Landroid/view/inputmethod/InputMethodManager;", "getInstance"): "input_method",
}

_SERVICE_BY_NAME = {"(Ljava/lang/String;)Ljava/lang/Object;"}
_SERVICE_BY_CLASS = {"(Ljava/lang/Class;)Ljava/lang/Object;"}


def _detect_service_call(
    key: tuple[str, str, str],
    registers: list[int],
    string_regs: dict[int, str],
    class_regs: dict[int, str],
    caller: dict[str, Any],
    offset: int,
    out: DexInventory,
) -> None:
    owner, name, descriptor = key
    request: dict[str, Any] | None = None
    if name == "getSystemService" and len(registers) >= 2:
        if descriptor in _SERVICE_BY_NAME:
            request = {"api": "getSystemService(String)", "service": string_regs.get(registers[1])}
        elif descriptor in _SERVICE_BY_CLASS:
            request = {"api": "getSystemService(Class)", "manager_class": class_regs.get(registers[1])}
        elif descriptor == "(Landroid/content/Context;Ljava/lang/Class;)Ljava/lang/Object;":
            request = {"api": f"{owner}->getSystemService", "manager_class": class_regs.get(registers[1])}
    elif owner == "Landroid/os/ServiceManager;" and name in {"getService", "checkService", "getServiceOrThrow"} and registers:
        request = {"api": f"ServiceManager.{name}", "service": string_regs.get(registers[0]), "binder_direct": True}
    elif (owner, name) in STATIC_SERVICE_ACCESSORS:
        request = {"api": f"{owner.strip('L;').rsplit('/', 1)[-1]}.{name}",
                   "service": STATIC_SERVICE_ACCESSORS[(owner, name)], "via_static_accessor": True}
    if request is None:
        return
    request["dynamic"] = request.get("service") is None and request.get("manager_class") is None
    out.service_requests.append({**caller, "offset": offset, "call_owner": owner, **request})


_NULL_CHECKS = {
    ("Ljava/lang/Object;", "getClass"),
    ("Ljava/util/Objects;", "requireNonNull"),
    ("Lkotlin/jvm/internal/Intrinsics;", "checkNotNull"),
    ("Lkotlin/jvm/internal/Intrinsics;", "checkNotNullExpressionValue"),
    ("Lkotlin/jvm/internal/Intrinsics;", "checkNotNullParameter"),
}


def _is_null_check(dex: DEX, instruction: Any) -> bool:
    """An invoke that throws when its first argument is null and is there only to check it."""
    try:
        owner, target, _ = dex.get_cm_method(int(instruction.get_ref_kind()))
    except Exception:
        return False
    return (str(owner), str(target)) in _NULL_CHECKS


def _detect_feature_query(
    key: tuple[str, str, str],
    registers: list[int],
    string_regs: dict[int, str],
    caller: dict[str, Any],
    offset: int,
    out: DexInventory,
) -> None:
    """PackageManager.hasSystemFeature(name[, version]). The FEATURE_* names are compile-time
    constants, so the name is in a register at the call (None where it is computed)."""
    owner, name, descriptor = key
    if name != "hasSystemFeature" or len(registers) < 2 or not descriptor.startswith("(Ljava/lang/String;"):
        return
    out.feature_queries.append({**caller, "offset": offset, "call_owner": owner,
                                "feature": string_regs.get(registers[1])})


KOTLIN_NONNULL_CAST = "null cannot be cast to non-null type "

# JCA engine classes: getInstance(type[, provider]) picks an implementation by name at run time, so
# the class being present in the boot jars says nothing about whether the named one is installed.
JCA_ENGINES = {
    "Ljava/security/KeyStore;", "Ljava/security/KeyPairGenerator;", "Ljava/security/KeyFactory;",
    "Ljava/security/Signature;", "Ljava/security/MessageDigest;", "Ljava/security/SecureRandom;",
    "Ljava/security/AlgorithmParameters;", "Ljava/security/cert/CertificateFactory;",
    "Ljavax/crypto/Cipher;", "Ljavax/crypto/KeyGenerator;", "Ljavax/crypto/Mac;", "Ljavax/crypto/SecretKeyFactory;",
    "Ljavax/crypto/KeyAgreement;", "Ljavax/net/ssl/SSLContext;", "Ljavax/net/ssl/TrustManagerFactory;",
    "Ljavax/net/ssl/KeyManagerFactory;",
}


def _detect_jca_call(
    key: tuple[str, str, str],
    registers: list[int],
    string_regs: dict[int, str],
    caller: dict[str, Any],
    offset: int,
    out: DexInventory,
) -> None:
    owner, name, descriptor = key
    if owner not in JCA_ENGINES or name != "getInstance" or not registers or not descriptor.startswith("(Ljava/lang/String;"):
        return
    request = {"api": owner.strip("L;").rsplit("/", 1)[-1] + ".getInstance", "type": string_regs.get(registers[0])}
    if descriptor.startswith("(Ljava/lang/String;Ljava/lang/String;)") and len(registers) >= 2:
        request["provider"] = string_regs.get(registers[1])
    elif descriptor.startswith("(Ljava/lang/String;Ljava/security/Provider;)"):
        request["provider"] = "(Provider object)"
    out.jca_requests.append({**caller, "offset": offset, **request})


def _method_names_by_owner(method_refs: Iterable[tuple[str, str, str]]) -> dict[str, list[str]]:
    names: dict[str, set[str]] = defaultdict(set)
    for owner, name, _descriptor in method_refs:
        names[owner].add(name)
    return {owner: sorted(values) for owner, values in sorted(names.items())}


def jni_mangle(value: str) -> str:
    out: list[str] = []
    for char in value:
        if char.isascii() and char.isalnum():
            out.append(char)
        elif char in {"/", "."}:
            out.append("_")
        elif char == "_":
            out.append("_1")
        elif char == ";":
            out.append("_2")
        elif char == "[":
            out.append("_3")
        else:
            encoded = char.encode("utf-16-be")
            for index in range(0, len(encoded), 2):
                unit = int.from_bytes(encoded[index : index + 2], "big")
                out.append(f"_0{unit:04x}")
    return "".join(out)


def jni_symbols(owner: str, name: str, descriptor: str) -> tuple[str, str]:
    class_part = owner.removeprefix("L").removesuffix(";")
    short = f"Java_{jni_mangle(class_part)}_{jni_mangle(name)}"
    params = descriptor[descriptor.find("(") + 1 : descriptor.find(")")]
    return short, f"{short}__{jni_mangle(params)}"


class RuntimeResolver:
    def __init__(self, runtime: dict[str, Any]):
        self.runtime = runtime
        self.classes: dict[str, dict[str, Any]] = runtime["classes"]
        self.bridge_exports = {
            symbol
            for elf in runtime.get("bridge_libraries", [])
            for symbol in elf.get("exported_symbols", [])
        }

    def has_class(self, owner: str) -> bool:
        return owner in self.classes

    def resolve_method(self, owner: str, name: str, descriptor: str) -> tuple[str, dict[str, Any]] | None:
        key = method_key(name, descriptor)
        return self._resolve(owner, key, "methods", set())

    def resolve_field(self, owner: str, name: str, descriptor: str) -> tuple[str, dict[str, Any]] | None:
        key = field_key(name, descriptor)
        return self._resolve(owner, key, "fields", set())

    def _resolve(
        self, owner: str, key: str, member_kind: str, seen: set[str]
    ) -> tuple[str, dict[str, Any]] | None:
        if owner in seen:
            return None
        seen.add(owner)
        record = self.classes.get(owner)
        if not record:
            return None
        if key in record.get(member_kind, []):
            return owner, record
        if member_kind == "methods" and key.startswith("<init>"):
            return None
        parents = [record.get("super", ""), *record.get("interfaces", [])]
        for parent in parents:
            if parent:
                found = self._resolve(parent, key, member_kind, seen)
                if found:
                    return found
        return None


def _launch_targets(apk: Any) -> list[str]:
    ns = "{http://schemas.android.com/apk/res/android}"
    targets: dict[str, str] = {}
    try:
        manifest = apk.get_android_manifest_xml()
        package = apk.get_package() or ""
        for alias in manifest.iter("activity-alias"):
            name, target = alias.get(ns + "name"), alias.get(ns + "targetActivity")
            if name and target:
                full = lambda n: package + n if n.startswith(".") else n
                targets[full(name)] = full(target)
    except Exception:
        pass
    return sorted({targets.get(name, name) for name in (apk.get_main_activities() or [])})

#: Schemes an app's filters share with everyone: the web, files, content and the platform's own
#: handlers. Any other scheme an activity's filter declares names the app's own deep links.
_SHARED_SCHEMES = {"http", "https", "file", "content", "geo", "tel", "mailto", "sms", "smsto", "mms", "mmsto",
                   "market", "intent", "android-app", "data", "ftp", "rtsp", "about", "javascript", "package",
                   "ws", "wss", "magnet", "otpauth", "webcal", "voicemail", "sip"}


def activity_filter_targets(apk: Any) -> dict[str, list[str]]:
    """The schemes and actions the app's own activity filters declare that no platform handler
    shares: its deep-link schemes (Shazam's shazam_activity) and its own actions. A string resource
    in the manifest is resolved, as Android's parser resolves it."""
    ns = "{http://schemas.android.com/apk/res/android}"
    resources = None

    def value(text: str | None) -> str | None:
        nonlocal resources
        if not text or not text.startswith("@"):
            return text
        try:
            resources = resources or apk.get_android_resources()
            configs = resources.get_resolved_res_configs(int(text[1:], 16))
            return str(configs[0][1]) if configs else None
        except Exception:
            return None

    schemes, actions = set(), set()
    try:
        manifest = apk.get_android_manifest_xml()
        for activity in manifest.iter():
            if activity.tag not in ("activity", "activity-alias"):
                continue
            for element in activity.iter():
                if element.tag == "data":
                    scheme = value(element.get(ns + "scheme"))
                    if scheme and scheme.lower() not in _SHARED_SCHEMES:
                        schemes.add(scheme)
                elif element.tag == "action":
                    action = value(element.get(ns + "name"))
                    if action and not action.startswith(("android.", "com.android.", "com.google.android.")):
                        actions.add(action)
    except Exception:
        pass
    return {"schemes": sorted(schemes), "actions": sorted(actions)}


_SHOW_WALLPAPER = 0x01010292  # android:attr/windowShowWallpaper
# The framework's themes that show the wallpaper (public-final.xml's Theme.*Wallpaper*): an app theme
# that inherits one shows it unless it says otherwise.
_FRAMEWORK_WALLPAPER_THEMES = frozenset({0x0103005e, 0x0103005f, 0x01030060, 0x01030061, 0x01030062, 0x0103007d,
                                         0x0103007e, 0x0103013c, 0x0103013d, 0x01030235, 0x01030236})


def _shows_wallpaper(resources: Any, theme: int, seen: set[int]) -> bool:
    """Whether a theme sets windowShowWallpaper, or, where it does not say, the parent it inherits from."""
    if not theme or theme in seen or len(seen) > 32:
        return False
    seen.add(theme)
    if theme >> 24 == 0x01:
        return theme in _FRAMEWORK_WALLPAPER_THEMES
    try:
        configs = resources.get_res_configs(theme)
    except Exception:
        return False
    said, parents = [], []
    for _config, entry in configs:
        if not entry.is_complex():
            continue
        for attr, value in entry.item.items:
            if attr == _SHOW_WALLPAPER:
                if value.data_type == 0x12:  # TYPE_INT_BOOLEAN
                    said.append(value.data != 0)
                elif value.data_type == 0x01:  # a reference to a bool resource
                    try:
                        resolved = resources.get_resolved_res_configs(value.data)
                        said.append(bool(resolved) and str(resolved[0][1]).lower() == "true")
                    except Exception:
                        pass
        parents.append(entry.item.id_parent)
    if said:
        return any(said)
    return any(_shows_wallpaper(resources, parent, seen) for parent in parents)


def wallpaper_activities(apk: Any) -> list[str]:
    """Activities whose theme (theirs, else the application's) shows the wallpaper behind their window:
    launchers and wallpaper settings. Android draws the wallpaper under such a window."""
    ns = "{http://schemas.android.com/apk/res/android}"
    resource_id = lambda text: int(text[1:], 16) if text and re.fullmatch(r"@[0-9A-Fa-f]{8}", text) else 0
    try:
        resources = apk.get_android_resources()
        manifest = apk.get_android_manifest_xml()
        application = manifest.find("application")
        default = resource_id(application.get(ns + "theme")) if application is not None else 0
        package = apk.get_package() or ""
        found = set()
        for activity in manifest.iter("activity"):
            name = activity.get(ns + "name") or ""
            name = package + name if name.startswith(".") else name
            if name and _shows_wallpaper(resources, resource_id(activity.get(ns + "theme")) or default, set()):
                found.add(name)
        return sorted(found)
    except Exception:
        return []


def apk_metadata(path: Path) -> dict[str, Any]:
    quiet_androguard()
    base = {
        "path": str(path.resolve()),
        "filename": path.name,
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }
    if path.suffix.lower() not in {".apk", ".xapk", ".apkm"}:
        return {**base, "package": path.stem, "manifest_available": False}
    try:
        container: dict[str, Any] = {}
        if path.suffix.lower() == ".apk":
            apk = APK(str(path), skip_analysis=False)
        else:
            with zipfile.ZipFile(path) as archive:
                try:
                    xmanifest = json.loads(archive.read("manifest.json"))
                except (KeyError, json.JSONDecodeError):
                    xmanifest = {}
                inner_names = _ordered_inner_apks(archive)
                if not inner_names:
                    raise ValueError("bundle contains no APK files")
                apk = APK(archive.read(inner_names[0]), raw=True, skip_analysis=False)
                container = {
                    "container_format": path.suffix.lower().lstrip("."),
                    "split_apks": inner_names,
                    "split_count": len(inner_names),
                    "container_manifest": {
                        key: xmanifest.get(key)
                        for key in ("xapk_version", "package_name", "version_code", "version_name", "split_configs")
                        if key in xmanifest
                    },
                }
        certificates: set[str] = set()
        for getter_name in ("get_certificates_der_v3", "get_certificates_der_v2"):
            try:
                for cert in getattr(apk, getter_name)() or []:
                    certificates.add(sha256_bytes(bytes(cert)))
            except Exception:
                pass
        files = apk.get_files() or []
        native_entries = [name for name in files if name.startswith("lib/") and name.endswith(".so")]
        abis = sorted({name.split("/", 2)[1] for name in native_entries if name.count("/") >= 2})
        return {
            **base,
            **container,
            "manifest_available": True,
            "package": apk.get_package(),
            "app_name": apk.get_app_name(),
            "version_code": apk.get_androidversion_code(),
            "version_name": apk.get_androidversion_name(),
            "min_sdk": apk.get_min_sdk_version(),
            "target_sdk": apk.get_target_sdk_version(),
            # A launcher entry may be an <activity-alias>: no class has its name, and what
            # starts is its targetActivity (Organic Maps, Element, Gallery, Fennec).
            "main_activities": _launch_targets(apk),
            "activity_filter_targets": activity_filter_targets(apk),
            "wallpaper_activities": wallpaper_activities(apk),
            "activities": len(apk.get_activities() or []),
            "activity_names": sorted(apk.get_activities() or []),
            "services": len(apk.get_services() or []),
            "receivers": len(apk.get_receivers() or []),
            "providers": len(apk.get_providers() or []),
            "permissions": sorted(apk.get_permissions() or []),
            "features": sorted(apk.get_features() or []),
            "signing_certificate_sha256": sorted(certificates),
            "abis": abis,
            "native_library_entries": len(native_entries),
        }
    except Exception as exc:
        return {**base, "package": path.stem, "manifest_available": False, "manifest_error": str(exc)}


def apk_elf_inventory(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() not in {".apk", ".xapk", ".apkm"}:
        return []
    records: list[dict[str, Any]] = []
    if path.suffix.lower() == ".apk":
        with zipfile.ZipFile(path) as archive:
            _append_elf_records(archive, "", records)
    else:
        with zipfile.ZipFile(path) as outer:
            for apk_name in _ordered_inner_apks(outer):
                with zipfile.ZipFile(io.BytesIO(outer.read(apk_name))) as inner:
                    _append_elf_records(inner, f"{apk_name}!", records)
    return records


def unpacked_elf_inventory(directory: Path, packaged: Iterable[dict[str, Any]] = ()) -> list[dict[str, Any]]:
    """The libraries an app wrote under its data directory at run time, harvested from a run.

    A superpack unpacked by SoLoader (WhatsApp's files/decompressed/libs.spo/, Instagram's
    lib-compressed/), Chaquopy's extracted modules or a downloaded plugin is code the APK does not
    package as lib/<abi>/*.so, so no scan of the APK sees its imports. ``directory`` holds the files as
    <pkg>/<path> with a harvest.json listing each one's device path (inputs run4.sh). A file with the
    hash of a packaged library is that library extracted again and is left out; a file that is not
    an ELF file (an archive or a partial write under a .so name) is skipped.
    """
    manifest = json.loads((directory / "harvest.json").read_text())
    seen = {record.get("sha256") for record in packaged}
    records: list[dict[str, Any]] = []
    for entry in manifest.get("libraries", []):
        if not entry.get("elf") or entry.get("sha256") in seen:
            continue
        seen.add(entry.get("sha256"))
        path = directory / entry["file"]
        try:
            record = read_elf(path=path, label=entry["device_path"])
        except (OSError, subprocess.SubprocessError) as exc:
            record = {"name": entry["device_path"], "error": str(exc)}
        record["origin"] = "unpacked"
        record["harvest_file"] = str(path)
        records.append(record)
    return records


def is_unpacked(record: dict[str, Any]) -> bool:
    """A library the app wrote at run time: the launcher cannot name it, only what the APK packages."""
    return record.get("origin") == "unpacked"


def _append_elf_records(
    archive: zipfile.ZipFile, prefix: str, records: list[dict[str, Any]]
) -> None:
    for name in sorted(archive.namelist()):
        if not (name.startswith("lib/") and name.endswith(".so")):
            continue
        info = archive.getinfo(name)
        if info.file_size > 512 * 1024 * 1024:
            records.append(
                {
                    "name": prefix + name,
                    "archive_entry": name,
                    "split_apk": prefix.removesuffix("!") or None,
                    "abi": abi_from_archive_name(name),
                    "error": "oversized ELF entry",
                }
            )
            continue
        try:
            record = read_elf(
                data=archive.read(name),
                label=prefix + name,
                abi=abi_from_archive_name(name),
            )
            record["archive_entry"] = name
            record["split_apk"] = prefix.removesuffix("!") or None
            records.append(record)
        except (OSError, subprocess.SubprocessError) as exc:
            records.append(
                {
                    "name": prefix + name,
                    "archive_entry": name,
                    "split_apk": prefix.removesuffix("!") or None,
                    "abi": abi_from_archive_name(name),
                    "error": str(exc),
                }
            )


def _read_archive_member(path: Path, record: dict[str, Any]) -> bytes | None:
    """Read one packaged ELF back out of the APK, including from a nested split archive, or a
    harvested one from its file."""
    if record.get("harvest_file"):
        try:
            return Path(record["harvest_file"]).read_bytes()
        except OSError:
            return None
    entry = record.get("archive_entry")
    if not entry:
        return None
    try:
        with zipfile.ZipFile(path) as archive:
            inner = record.get("split_apk")
            if not inner:
                return archive.read(entry)
            with archive.open(inner) as stream:
                with zipfile.ZipFile(io.BytesIO(stream.read())) as nested:
                    return nested.read(entry)
    except (KeyError, OSError, zipfile.BadZipFile):
        return None


def _attribute_native_imports(
    path: Path, selected_elfs: list[dict[str, Any]], unresolved: list[dict[str, Any]]
) -> str:
    """Attach the JNI methods that reach each unresolved symbol, in place.

    Attribution is a direct-call lower bound: a symbol with no reaching method is *not
    proven to reach one*, never proven unreachable.
    """
    wanted: dict[str, set[str]] = defaultdict(set)
    for item in unresolved:
        for source in item["importing_libraries"]:
            wanted[source["elf"]].add(item["symbol"])
    records = {record["name"]: record for record in selected_elfs}
    attributed: dict[str, dict[str, list[str]]] = {}
    analyzed = 0
    with tempfile.TemporaryDirectory(prefix="westlake-native-reach-") as temp:
        for label, symbols in sorted(wanted.items()):
            record = records.get(label)
            if not record or not record.get("jni_registration_entries"):
                continue
            blob = _read_archive_member(path, record)
            if blob is None:
                continue
            destination = Path(temp) / f"{record.get('sha256', label)[:24]}.so"
            destination.write_bytes(blob)
            attributed[label] = attribute_unresolved_imports(destination, record, symbols)
            analyzed += 1
    for item in unresolved:
        reaching = [
            {"elf": label, "method": method}
            for label, by_symbol in sorted(attributed.items())
            for method in by_symbol.get(item["symbol"], ())
        ]
        if reaching:
            item["reaching_methods"] = reaching
        item["attribution_basis"] = "direct-bl-lower-bound"
    return f"analyzed {analyzed} of {len(wanted)} importing libraries"


def _single_elf_abi(records: Iterable[dict[str, Any]]) -> str | None:
    abis = {record["abi"] for record in records if record.get("abi")}
    return next(iter(abis)) if len(abis) == 1 else None


def _symbol_sources(records: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        for symbol in record.get("exported_symbols", []):
            sources[symbol].append(
                {
                    "elf": record["name"],
                    "elf_sha256": record.get("sha256"),
                    "build_id": record.get("build_id"),
                    "symbol": symbol,
                }
            )
    return sources


def _native_library_candidates(
    native: dict[str, Any],
    owner_calls: list[dict[str, Any]],
    dex_calls: list[dict[str, Any]],
    elf_by_filename: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Attribute a declaration to packaged libraries without pretending a call graph exists."""
    candidates: dict[str, dict[str, Any]] = {}
    for confidence, calls in (("same-owner-load", owner_calls), ("same-dex-load", dex_calls)):
        for call in calls:
            filename = library_filename(call["value"])
            for record in elf_by_filename.get(filename, []):
                name = record["name"]
                if name not in candidates:
                    candidates[name] = {**record, "attribution": []}
                if confidence not in candidates[name]["attribution"]:
                    candidates[name]["attribution"].append(confidence)
    return sorted(
        candidates.values(),
        key=lambda record: (
            "same-owner-load" not in record["attribution"],
            not record.get("has_jni_onload"),
            record["name"],
        ),
    )


def scan_apk(
    path: Path,
    runtime: dict[str, Any],
    include_elf: bool = True,
    target_abi: str | None = None,
    native_reach: bool = False,
    platform_members: dict[str, Any] | None = None,
    unpacked_libs: Path | None = None,
) -> dict[str, Any]:
    identity = apk_metadata(path)
    inventory = inventory_dex(path, identity.get("activity_filter_targets"))
    resolver = RuntimeResolver(runtime)
    elf_records = apk_elf_inventory(path) if include_elf else []
    if include_elf and unpacked_libs is not None:
        elf_records += unpacked_elf_inventory(unpacked_libs, elf_records)
    target_abi = target_abi or runtime.get("target_abi") or _single_elf_abi(runtime.get("bridge_libraries", []))
    available_abis = sorted({record["abi"] for record in elf_records if record.get("abi")})
    if target_abi:
        selected_elfs = [
            record
            for record in elf_records
            if record.get("abi") == target_abi and record.get("abi_matches_machine", True)
        ]
        selected_runtime_elfs = [
            record
            for record in runtime.get("bridge_libraries", [])
            if not record.get("abi") or record.get("abi") == target_abi
        ]
        selected_system_elfs = [
            record
            for record in runtime.get("system_libraries", [])
            if not record.get("abi") or record.get("abi") == target_abi
        ]
    else:
        selected_elfs = list(elf_records)
        selected_runtime_elfs = list(runtime.get("bridge_libraries", []))
        selected_system_elfs = list(runtime.get("system_libraries", []))
    if available_abis and target_abi and target_abi not in available_abis:
        abi_status = "target-abi-unavailable"
    elif available_abis and target_abi and not selected_elfs:
        abi_status = "target-abi-elf-mismatch"
    elif available_abis and target_abi:
        abi_status = "target-abi-available"
    elif available_abis:
        abi_status = "target-abi-unspecified"
    else:
        abi_status = "no-packaged-native-libraries"
    identity["native_abis"] = available_abis
    identity["target_abi"] = target_abi
    identity["native_abi_status"] = abi_status
    defined = inventory.defined_classes
    findings: list[dict[str, Any]] = []

    used_owners = inventory.callable_owners
    missing_classes: set[str] = set()
    for owner in sorted(inventory.type_refs):
        if owner in defined or resolver.has_class(owner):
            continue
        missing_classes.add(owner)
        findings.append(
            finding(identity["sha256"], runtime["runtime_lock_id"], "missing_class", "C1/C4", owner)
        )

    for (owner, name, descriptor), count in sorted(inventory.method_refs.items()):
        if owner in defined:
            continue
        if not resolver.has_class(owner):
            continue
        resolved = resolver.resolve_method(owner, name, descriptor)
        if resolved is None:
            record = resolver.classes[owner]
            classification = "C9-candidate" if record.get("hollow_class_candidate") or "stub" in record.get("artifact", "").lower() else "C1/C4"
            findings.append(
                finding(
                    identity["sha256"], runtime["runtime_lock_id"], "missing_method", classification,
                    owner, name, descriptor, count, inventory.method_sites[(owner, name, descriptor)],
                    artifact=record.get("artifact"),
                )
            )
        else:
            resolved_owner, record = resolved
            key = method_key(name, descriptor)
            if key in record.get("hollow_methods", []):
                findings.append(
                    finding(
                        identity["sha256"], runtime["runtime_lock_id"], "hollow_method", "C9-candidate",
                        owner, name, descriptor, count, inventory.method_sites[(owner, name, descriptor)],
                        resolved_owner=resolved_owner, artifact=record.get("artifact"),
                    )
                )

    for (owner, name, descriptor), count in sorted(inventory.field_refs.items()):
        if owner in defined or not resolver.has_class(owner):
            continue
        if resolver.resolve_field(owner, name, descriptor) is None:
            record = resolver.classes[owner]
            classification = "C9-candidate" if record.get("hollow_class_candidate") or "stub" in record.get("artifact", "").lower() else "C1/C4"
            findings.append(
                finding(
                    identity["sha256"], runtime["runtime_lock_id"], "missing_field", classification,
                    owner, name, descriptor, count, inventory.field_sites[(owner, name, descriptor)],
                    artifact=record.get("artifact"),
                )
            )

    probes_by_owner: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for probe in inventory.probes:
        probes_by_owner[probe["descriptor"]].append(probe)
    for owner, probe_evidence in sorted(probes_by_owner.items()):
        if owner in defined or resolver.has_class(owner):
            continue
        callable_use = owner in used_owners
        findings.append(
            finding(
                identity["sha256"], runtime["runtime_lock_id"], "existence_probe",
                "CU" if callable_use else "C8-candidate", owner,
                reference_count=len(probe_evidence), evidence=probe_evidence[:16],
                probe_only=not callable_use,
                layer="J" if is_platform_type(owner) else "V",
            )
        )

    apk_exports = _symbol_sources(selected_elfs)
    runtime_exports = _symbol_sources(selected_runtime_elfs)
    registration_sources: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for elf in selected_elfs:
        for entry in elf.get("jni_registration_entries", []):
            registration_sources[(entry["name"], entry["signature"])].append(
                {
                    "elf": elf["name"],
                    "elf_sha256": elf.get("sha256"),
                    "build_id": elf.get("build_id"),
                    "function_vaddr": entry.get("function_vaddr"),
                    "table_vaddr": entry.get("table_vaddr"),
                }
            )
    elf_by_filename: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for elf in selected_elfs:
        filename = PurePosixPath(elf.get("archive_entry") or elf["name"].rsplit("!", 1)[-1]).name
        elf_by_filename[filename].append(elf)
        if elf.get("soname"):
            elf_by_filename[elf["soname"]].append(elf)
    owner_loads: dict[str, list[dict[str, Any]]] = defaultdict(list)
    dex_loads: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for call in inventory.load_libraries:
        owner_loads[call["owner"]].append(call)
        dex_loads[call["dex"]].append(call)
    any_selected_onload = any(elf.get("has_jni_onload") for elf in selected_elfs)
    native_findings: list[dict[str, Any]] = []
    for native in inventory.native_methods:
        if not include_elf:
            state, classification = "elf-scan-skipped", "CU"
            item = {**native, "state": state, "classification": classification, "target_abi": target_abi}
            native_findings.append(item)
            continue
        symbol = next(
            (
                candidate
                for candidate in (native["jni_short"], native["jni_long"])
                if candidate in apk_exports
            ),
            None,
        )
        runtime_symbol = next(
            (
                candidate
                for candidate in (native["jni_short"], native["jni_long"])
                if candidate in runtime_exports
            ),
            None,
        )
        table_sources = registration_sources.get((native["name"], native["descriptor"]), [])
        candidates = _native_library_candidates(
            native,
            owner_loads.get(native["owner"], []),
            dex_loads.get(native["dex"], []),
            elf_by_filename,
        )
        candidate_onload = any(candidate.get("has_jni_onload") for candidate in candidates)
        sources: list[dict[str, Any]] = []
        provider_scope = "UNKNOWN"
        if symbol:
            state, classification = "apk-export-resolved", "C0"
            provider_scope = "APP_BUNDLED"
            sources = apk_exports[symbol]
        elif runtime_symbol:
            state, classification = "runtime-export-resolved", "C0"
            provider_scope = "PLATFORM_FRAMEWORK"
            sources = runtime_exports[runtime_symbol]
        elif abi_status in {"target-abi-unavailable", "target-abi-elf-mismatch"}:
            state, classification = abi_status, "CU"
        elif table_sources:
            state, classification = "static-registration-table-candidate", "CU"
            provider_scope = "APP_BUNDLED"
            sources = table_sources
        elif candidate_onload:
            state, classification = "library-scoped-registration-unresolved", "CU"
            provider_scope = "APP_BUNDLED"
        elif candidates:
            state, classification = "load-attributed-no-binding-evidence", "CU"
            provider_scope = "APP_BUNDLED"
        elif any_selected_onload:
            state, classification = "registration-source-unattributed", "CU"
        else:
            state, classification = "no-export-or-registration-evidence", "V-C1-candidate"
        item = {
            **native,
            "state": state,
            "classification": classification,
            "target_abi": target_abi,
            "provider_scope": provider_scope,
            "resolution_sources": sources[:16],
            "candidate_library_count": len(candidates),
            "candidate_libraries": [
                {
                    "elf": candidate["name"],
                    "elf_sha256": candidate.get("sha256"),
                    "build_id": candidate.get("build_id"),
                    "has_jni_onload": bool(candidate.get("has_jni_onload")),
                    "attribution": candidate.get("attribution", []),
                }
                for candidate in candidates[:16]
            ],
        }
        native_findings.append(item)
        if classification != "C0":
            findings.append(
                finding(
                    identity["sha256"], runtime["runtime_lock_id"], "unbound_native", classification,
                    native["owner"], native["name"], native["descriptor"],
                    jni_short=native["jni_short"], jni_long=native["jni_long"], state=state,
                    layer="V", dex=native["dex"], dex_sha256=native["dex_sha256"],
                    target_abi=target_abi, provider_scope=provider_scope,
                    resolution_sources=sources[:16],
                    candidate_library_count=len(candidates),
                    candidate_libraries=item["candidate_libraries"],
                )
            )

    system_exports = _symbol_sources(selected_system_elfs)
    system_index_available = bool(selected_system_elfs)
    native_imports = resolve_native_imports(
        selected_elfs, apk_exports, runtime_exports, system_exports, system_index_available
    )
    unresolved_imports = [item for item in native_imports if item["classification"] != "C0"]
    reach_state = "not-requested"
    if native_reach and unresolved_imports:
        reach_state = _attribute_native_imports(path, selected_elfs, unresolved_imports)
    for item in unresolved_imports:
        findings.append(
            finding(
                identity["sha256"], runtime["runtime_lock_id"], "native_import", item["classification"],
                "native-import", item["symbol"], None,
                layer="N", state=item["state"], target_abi=target_abi,
                provider_scope=item["provider_scope"],
                surface=item["surface"],
                importing_libraries=item["importing_libraries"],
                importing_library_count=item["importing_library_count"],
                reaching_methods=item.get("reaching_methods", []),
                reaching_method_count=len(item.get("reaching_methods", [])),
                attribution_basis=item.get("attribution_basis"),
            )
        )
    if not system_index_available and any(
        record.get("undefined_symbols") for record in selected_elfs
    ):
        findings.append(
            finding(
                identity["sha256"], runtime["runtime_lock_id"], "native_import_coverage", "O-BLIND",
                "native-import", "runtime-system-library-index", None,
                layer="O", state="runtime-system-index-unavailable", target_abi=target_abi,
                fault_origin="observation-system",
                unresolved_symbol_count=len(unresolved_imports),
            )
        )

    # Java framework APIs the packaged native code calls back into through JNIEnv. Needs a reference
    # android.jar to enumerate candidate members; see nativeupcall.py.
    native_upcalls: list[dict[str, Any]] = []
    if platform_members is not None:
        from .nativeupcall import library_upcalls, resolve_upcalls

        for elf in selected_elfs:
            blob = _read_archive_member(path, elf)
            if not blob:
                continue
            upcalls = resolve_upcalls(library_upcalls(blob, platform_members, runtime), resolver, platform_members)
            if not upcalls["classes"]:
                continue
            native_upcalls.append({"elf": elf["name"], "soname": elf.get("soname"), **upcalls})
            evidence = [{"elf": elf["name"], "elf_sha256": elf.get("sha256")}]
            for cls, state in upcalls["class_states"].items():
                if state in {"missing", "unknown"}:
                    findings.append(finding(
                        identity["sha256"], runtime["runtime_lock_id"], "native_upcall_class",
                        "C1/C4" if state == "missing" else "CU", f"L{cls};", layer="J",
                        evidence=evidence, reached_from=elf["name"], state=state,
                    ))
            for member in upcalls["members"]:
                if member["state"] not in {"missing", "hollow", "hollow-candidate"}:
                    continue
                hollow = member["state"].startswith("hollow")
                findings.append(finding(
                    identity["sha256"], runtime["runtime_lock_id"],
                    "native_upcall_hollow" if hollow else f"native_upcall_{member['kind']}",
                    "C9-candidate" if hollow else "C1/C4",
                    f"L{member['owner']};", member["name"], member["descriptor"], layer="J",
                    evidence=evidence, reached_from=elf["name"], state=member["state"],
                ))

    findings.sort(key=lambda x: (x["kind"], x["dependency"]["owner"], x["dependency"].get("name") or "", x["dependency"].get("signature") or ""))
    result = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "runtime_lock_id": runtime["runtime_lock_id"],
        "apk": identity,
        "inventory": {
            "dex_entries": inventory.dex_entries,
            "defined_classes": len(defined),
            # Each launch activity's superclass chain, up to the first class the APK does not
            # define: which engine base class (libGDX, SDL, Flutter, NativeActivity...) it runs on.
            "launch_activity_chains": _activity_chains(identity.get("main_activities") or [], inventory.superclasses),
            "platform_type_references": len(inventory.type_refs),
            "platform_method_references": len(inventory.method_refs),
            "platform_field_references": len(inventory.field_refs),
            "existence_probes": inventory.probes,
            "load_library_calls": inventory.load_libraries,
            "service_requests": inventory.service_requests,
            "jca_requests": inventory.jca_requests,
            "feature_queries": inventory.feature_queries,
            "nonnull_casts": inventory.nonnull_casts,
            "own_intent_names": sorted(inventory.own_intent_names),
            "sql_collations": sorted(inventory.sql_collations),
            "after_start_overrides": after_start_overrides(identity.get("activity_names") or [],
                                                           inventory.superclasses, inventory.after_start_callbacks),
            "native_upcalls": native_upcalls if platform_members is not None else None,
            "platform_method_names": _method_names_by_owner(inventory.method_refs),
            "declared_native_methods": native_findings,
            "elfs": elf_records,
            "native_imports": native_imports,
            "native_import_attribution": reach_state,
            "native_resolution": {
                "target_abi": target_abi,
                "abi_status": abi_status,
                "available_abis": available_abis,
                "abi_mismatch_elf_count": sum(
                    not record.get("abi_matches_machine", True) for record in elf_records
                ),
                "packaged_elf_count": sum(not is_unpacked(record) for record in elf_records),
                "unpacked_elf_count": sum(is_unpacked(record) for record in elf_records),
                "selected_packaged_elf_count": sum(not is_unpacked(record) for record in selected_elfs),
                "selected_runtime_elf_count": len(selected_runtime_elfs),
                "recovered_registration_entry_count": sum(
                    len(elf.get("jni_registration_entries", [])) for elf in selected_elfs
                ),
                "state_counts": dict(sorted(Counter(item["state"] for item in native_findings).items())),
            },
        },
        "summary": {},
        "findings": findings,
        "limitations": [
            "Static references over-approximate runtime reachability.",
            "Computed reflection and code downloaded after install are not visible.",
            "CU native findings may be satisfied through RegisterNatives at runtime.",
            "Static JNINativeMethod recovery is candidate evidence until runtime registration is observed.",
            "Presence does not prove semantic, lifecycle, timing, or ABI compatibility.",
        ],
    }
    refresh_scan_summary(result)
    return result


def refresh_scan_summary(scan: dict[str, Any]) -> None:
    candidates = [item for item in scan["findings"] if item.get("classification") != "CU"]
    unresolved = [item for item in scan["findings"] if item.get("classification") == "CU"]
    direct_absence = [item for item in candidates if item["kind"].startswith("missing_")]
    native_methods = scan.get("inventory", {}).get("declared_native_methods", [])
    native_states = Counter(item.get("state", "unknown") for item in native_methods)
    scan["summary"] = {
        "finding_count": len(candidates),
        "candidate_count": len(candidates),
        "unresolved_count": len(unresolved),
        "direct_absence_count": len(direct_absence),
        "findings_by_kind": dict(sorted(Counter(item["kind"] for item in candidates).items())),
        "unresolved_by_kind": dict(sorted(Counter(item["kind"] for item in unresolved).items())),
        "missing_classes": sum(item["kind"] == "missing_class" for item in candidates),
        "native_declaration_count": len(native_methods),
        "native_by_state": dict(sorted(native_states.items())),
        "native_resolved_count": sum(item.get("classification") == "C0" for item in native_methods),
        "native_unresolved_count": sum(item.get("classification") == "CU" for item in native_methods),
        "native_candidate_count": sum(
            item.get("classification") not in {"C0", "CU"} for item in native_methods
        ),
        "static_scope": "base-and-supplied-splits",
    }


def finding(
    apk_sha: str,
    runtime_id: str,
    kind: str,
    classification: str,
    owner: str,
    name: str | None = None,
    signature: str | None = None,
    reference_count: int = 0,
    evidence: list[dict[str, Any]] | None = None,
    layer: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    stable = json.dumps(
        {"apk": apk_sha, "runtime": runtime_id, "kind": kind, "owner": owner, "name": name, "signature": signature},
        sort_keys=True,
    ).encode()
    return {
        "finding_id": "sha256:" + sha256_bytes(stable),
        "apk_sha256": apk_sha,
        "runtime_lock_id": runtime_id,
        "fault_origin": "apk-dependency",
        "kind": kind,
        "classification": classification,
        "confidence": (
            "unresolved" if classification.startswith("CU")
            else "direct-static" if reference_count > 0 or evidence
            else "reference-pool"
        ),
        "dependency": {"layer": layer or ("V" if classification.startswith("V-") else "J"), "owner": owner, "name": name, "signature": signature},
        "reference_count": reference_count,
        "evidence": evidence or [],
        "status": "candidate",
        **extra,
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False)
        stream.write("\n")


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)
