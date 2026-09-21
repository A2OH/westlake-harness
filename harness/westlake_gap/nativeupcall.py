"""Java framework APIs that packaged native code calls back into.

A `.so` reaches Java through the JNIEnv function table (`FindClass`, `GetMethodID`,
`GetStaticFieldID`, …), never through an import. So both scans miss it: the call is not in the dex,
and it is not a native import. The names still have to be in the library as strings: a class name
for `FindClass`, and a member name plus a JNI signature for `Get*ID`.

Recovery, without disassembly:

1. read every NUL-delimited string from the library's allocated, non-executable data sections;
2. keep the ones that name a platform class (`android/os/Handler`);
3. for each such class, enumerate its members (declared and inherited) from a reference
   `android.jar` and from the runtime under test, and keep a member only when **both** its name and
   its exact JNI signature occur as strings in the same library. A random identifier and a random
   signature coinciding with a real member of a class the library names is rare;
4. resolve the survivors against the runtime exactly like dex references: present, hollow, missing.

Limits: a field of primitive type (`I`, `J`, `Z`) is matched by name alone, which requires the name
to be at least three characters; strings that are built at runtime, encrypted, or tail-merged into
a longer string are invisible; a string being present does not prove the call executes.
"""

from __future__ import annotations

import io
import re
from typing import Any

from elftools.elf.constants import SH_FLAGS
from elftools.elf.elffile import ELFFile

from .scanner import is_platform_type

_SKIP_SECTIONS = {".eh_frame", ".eh_frame_hdr", ".gcc_except_table", ".init_array", ".fini_array",
                  ".got", ".got.plt", ".data.rel.ro", ".dynamic", ".note.android.ident"}
_STRING = re.compile(rb"[\x20-\x7e]{2,}")
_CLASS = re.compile(r"^[a-z][a-z0-9_]*(?:/[A-Za-z0-9_$]+)+$")
_SIGNATURE = re.compile(r"^\((?:\[*(?:[ZBCSIJFD]|L[A-Za-z0-9_/$]+;))*\)\[*(?:[ZBCSIJFDV]|L[A-Za-z0-9_/$]+;)$")
_SIG_TYPE = re.compile(r"L([A-Za-z0-9_/$]+);")

# Upstream library jars: an empty body there is upstream behaviour (``OutputStream.flush``), not a
# Westlake placeholder. Hollowness is only evidence in jars Westlake builds or stubs.
UPSTREAM_JARS = {"core-oj.jar", "core-libart.jar", "core-icu4j.jar", "bouncycastle.jar", "apache-xml.jar", "okhttp.jar"}
# framework.jar is AOSP compiled by Westlake: a constant body there is often AOSP's own
# (``AudioTrack.getMaxVolume`` returns ``GAIN_MAX``), so it is only a candidate. Westlake's adapter and
# stub jars are where placeholders are written, so an empty body there is evidence.


def _westlake_owned(artifact: str | None) -> bool:
    return bool(artifact) and (artifact.startswith(("adapter-", "oh-adapter")))
_ACC_PUBLIC, _ACC_PROTECTED, _ACC_SYNTHETIC = 0x0001, 0x0004, 0x1000


class StringTable:
    """Standalone strings of one ELF's data sections, with O(1) membership."""

    def __init__(self, data: bytes):
        blobs = []
        try:
            elf = ELFFile(io.BytesIO(data))
            for section in elf.iter_sections():
                flags = section["sh_flags"]
                if (flags & SH_FLAGS.SHF_ALLOC and not flags & SH_FLAGS.SHF_EXECINSTR
                        and section["sh_type"] == "SHT_PROGBITS" and section.name not in _SKIP_SECTIONS):
                    blobs.append(section.data())
        except Exception:
            blobs = []
        # A library stripped of section headers still has its strings; fall back to the whole image.
        blob = b"\x00".join(blobs) if blobs else data
        self.strings = {m.group(0).decode("ascii") for m in _STRING.finditer(blob)
                        if blob[m.end():m.end() + 1] in (b"\x00", b"")
                        and (m.start() == 0 or blob[m.start() - 1:m.start()] == b"\x00")}

    def __contains__(self, value: str) -> bool:
        return value in self.strings


def _members(record: dict[str, Any], kind: str) -> list[tuple[str, str]]:
    """``(name, descriptor)`` pairs from either a reference-jar record or a runtime-index record."""
    values = record.get(kind, [])
    out = []
    for value in values:
        if isinstance(value, (list, tuple)):
            # Reference-jar member. SDK stubs carry package-private placeholder constructors and
            # synthetic members that do not exist in the real API; only public/protected count.
            access = value[2] if len(value) > 2 else _ACC_PUBLIC
            if access & _ACC_SYNTHETIC or not access & (_ACC_PUBLIC | _ACC_PROTECTED):
                continue
            out.append((value[0], value[1]))
        elif kind == "methods" and "(" in value:
            at = value.index("(")
            out.append((value[:at], value[at:]))
        elif kind == "fields" and ":" in value:
            name, _, desc = value.partition(":")
            out.append((name, desc))
    return out


def _hierarchy(name: str, index: dict[str, dict[str, Any]], runtime_style: bool) -> list[tuple[str, dict[str, Any]]]:
    """The class and its supertypes, stopping before java/lang/Object."""
    chain, queue, seen = [], [name], set()
    while queue:
        current = queue.pop(0)
        key = f"L{current};" if runtime_style else current
        if current in seen or current == "java/lang/Object":
            continue
        seen.add(current)
        record = index.get(key)
        if not record:
            continue
        chain.append((current, record))
        parents = [record.get("super") or "", *record.get("interfaces", [])]
        queue.extend(p[1:-1] if runtime_style and p.startswith("L") else p for p in parents if p)
    return chain


def library_upcalls(data: bytes, reference: dict[str, dict[str, Any]], runtime: dict[str, Any]) -> dict[str, Any]:
    """Platform classes and members one library names for JNI calls back into Java."""
    table = StringTable(data)
    runtime_classes = runtime.get("classes", {})
    classes = sorted(s for s in table.strings if _CLASS.match(s) and is_platform_type(f"L{s};"))
    signatures = {s for s in table.strings if _SIGNATURE.match(s)}
    boundary = sorted({t for sig in signatures for t in _SIG_TYPE.findall(sig) if is_platform_type(f"L{t};")})

    members = []
    for cls in classes:
        seen: set[tuple[str, str, str]] = set()
        for source, runtime_style in ((reference, False), (runtime_classes, True)):
            for declaring, record in _hierarchy(cls, source, runtime_style):
                for kind in ("methods", "fields"):
                    for name, desc in _members(record, kind):
                        if (kind, name, desc) in seen or name not in table or name == "<clinit>":
                            continue
                        # Constructors are not inherited: NewObject on a class needs its own.
                        if name == "<init>" and declaring != cls:
                            continue
                        if kind == "methods" and desc not in table:
                            continue
                        if kind == "fields" and len(desc) > 1 and desc not in table:
                            continue
                        if kind == "fields" and len(desc) == 1 and len(name) < 3:
                            continue
                        seen.add((kind, name, desc))
                        members.append({"owner": cls, "kind": kind[:-1], "name": name, "descriptor": desc,
                                        "declared_in": declaring,
                                        "in_reference": source is reference})
    return {"classes": classes, "members": members, "boundary_types": boundary}


def resolve_upcalls(upcalls: dict[str, Any], resolver: Any, reference: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Resolve each named class and member against the runtime: present, hollow or missing."""
    class_states = {}
    for cls in upcalls["classes"]:
        owner = f"L{cls};"
        if resolver.has_class(owner):
            class_states[cls] = "present"
        elif cls in reference:
            class_states[cls] = "missing"
        else:
            # Neither the public SDK nor the runtime knows it: a hidden API the runtime lacks, or a
            # string that only looks like a class name. Not decidable from strings alone.
            class_states[cls] = "unknown"
    resolved = []
    for member in upcalls["members"]:
        owner = f"L{member['owner']};"
        if class_states.get(member["owner"]) != "present":
            state = "class-" + class_states.get(member["owner"], "unknown")
        else:
            if member["kind"] == "method":
                hit = resolver.resolve_method(owner, member["name"], member["descriptor"])
                key = f"{member['name']}{member['descriptor']}"
            else:
                hit = resolver.resolve_field(owner, member["name"], member["descriptor"])
                key = None
            artifact = hit[1].get("artifact") if hit else None
            if hit is None:
                state = "missing"
            elif key and key in hit[1].get("hollow_methods", []) and artifact not in UPSTREAM_JARS:
                state = "hollow" if _westlake_owned(artifact) else "hollow-candidate"
            else:
                state = "present"
            member = {**member, "runtime_artifact": artifact}
        resolved.append({**member, "state": state})
    return {**upcalls, "class_states": class_states, "members": resolved}
