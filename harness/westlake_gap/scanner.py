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
    nonnull_casts: list[dict[str, Any]] = field(default_factory=list)
    native_methods: list[dict[str, Any]] = field(default_factory=list)


def inventory_dex(path: Path) -> DexInventory:
    quiet_androguard()
    result = DexInventory()
    for dex_name, blob in dex_blobs(path):
        dex = DEX(blob)
        dex_sha256 = sha256_bytes(blob)
        result.dex_entries.append({"name": dex_name, "sha256": dex_sha256, "bytes": len(blob)})
        result.defined_classes.update(str(c.get_name()) for c in dex.get_classes())
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


def _inventory_defined_methods(
    dex: DEX,
    dex_name: str,
    dex_sha256: str,
    out: DexInventory,
) -> None:
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
            _inventory_instructions(dex, method, caller, out)


def _inventory_instructions(dex: DEX, method: Any, caller: dict[str, Any], out: DexInventory) -> None:
    string_regs: dict[int, str] = {}
    class_regs: dict[int, str] = {}
    for offset, instruction in method.get_instructions_idx():
        name = instruction.get_name()
        try:
            operands = instruction.get_operands() or []
        except Exception:
            operands = []
        registers = [int(op[1]) for op in operands if int(op[0]) == 0]

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
                out.callable_owners.add(str(owner))
                if is_platform_type(str(owner)):
                    out.method_refs[key] += 1
                    if len(out.method_sites[key]) < 8:
                        out.method_sites[key].append({**caller, "offset": offset, "opcode": name})
                _detect_string_call(key, registers, string_regs, caller, offset, out)
                _detect_service_call(key, registers, string_regs, class_regs, caller, offset, out)
                _detect_jca_call(key, registers, string_regs, caller, offset, out)
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
            "activities": len(apk.get_activities() or []),
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
    """Read one packaged ELF back out of the APK, including from a nested split archive."""
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
) -> dict[str, Any]:
    inventory = inventory_dex(path)
    resolver = RuntimeResolver(runtime)
    identity = apk_metadata(path)
    elf_records = apk_elf_inventory(path) if include_elf else []
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
            "platform_type_references": len(inventory.type_refs),
            "platform_method_references": len(inventory.method_refs),
            "platform_field_references": len(inventory.field_refs),
            "existence_probes": inventory.probes,
            "load_library_calls": inventory.load_libraries,
            "service_requests": inventory.service_requests,
            "jca_requests": inventory.jca_requests,
            "nonnull_casts": inventory.nonnull_casts,
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
                "packaged_elf_count": len(elf_records),
                "selected_packaged_elf_count": len(selected_elfs),
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
