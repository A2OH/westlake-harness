"""Classify findings by the API level that introduced the member they name.

A gap list against one runtime mixes three very different things: contracts the app can
really reach on a device it demonstrably runs on, contracts introduced after that device's
API level (which the app must already tolerate the absence of), and names that were never
Android at all — JavaSE classes pulled in by libraries with a desktop code path, build-time
lint APIs, compile-time annotations.

Only the first kind is a gap worth building. Deciding which is which needs the platform
jars, so this module reads them directly: a minimal ``.class`` parser over ``android.jar``
is faster and more dependable than shelling out per class.
"""

from __future__ import annotations

import struct
import zipfile
from pathlib import Path
from typing import Any, Iterable

# Constant-pool tag -> fixed payload width. Utf8 (1) is variable and handled separately.
_CONSTANT_WIDTH = {3: 4, 4: 4, 5: 8, 6: 8, 7: 2, 8: 2, 9: 4, 10: 4, 11: 4, 12: 4,
                   15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2}
_WIDE_TAGS = {5, 6}  # long and double occupy two constant-pool slots


def _parse_class(data: bytes) -> tuple[set[str], set[str]] | None:
    """Return ``(method names, field names)`` declared by one class file."""
    try:
        if len(data) < 10 or data[:4] != b"\xca\xfe\xba\xbe":
            return None
        pool_count = struct.unpack_from(">H", data, 8)[0]
        strings: dict[int, str] = {}
        offset, index = 10, 1
        while index < pool_count:
            tag = data[offset]
            offset += 1
            if tag == 1:
                length = struct.unpack_from(">H", data, offset)[0]
                offset += 2
                strings[index] = data[offset:offset + length].decode("utf-8", "replace")
                offset += length
            else:
                width = _CONSTANT_WIDTH.get(tag)
                if width is None:
                    return None
                offset += width
            index += 2 if tag in _WIDE_TAGS else 1

        offset += 6  # access_flags, this_class, super_class
        interfaces = struct.unpack_from(">H", data, offset)[0]
        offset += 2 + interfaces * 2

        def members() -> set[str]:
            nonlocal offset
            count = struct.unpack_from(">H", data, offset)[0]
            offset += 2
            names: set[str] = set()
            for _ in range(count):
                _, name_index, _ = struct.unpack_from(">HHH", data, offset)
                offset += 6
                names.add(strings.get(name_index, ""))
                attributes = struct.unpack_from(">H", data, offset)[0]
                offset += 2
                for _ in range(attributes):
                    length = struct.unpack_from(">I", data, offset + 2)[0]
                    offset += 6 + length
            return names

        fields = members()
        methods = members()
        return methods, fields
    except (struct.error, IndexError, UnicodeDecodeError):
        return None


def load_platform_index(jar: Path) -> dict[str, dict[str, set[str]]]:
    """Index one ``android.jar``: class name (``android/net/wifi/WifiInfo``) -> members."""
    index: dict[str, dict[str, set[str]]] = {}
    with zipfile.ZipFile(jar) as archive:
        for entry in archive.namelist():
            if not entry.endswith(".class"):
                continue
            parsed = _parse_class(archive.read(entry))
            if parsed is None:
                continue
            methods, fields = parsed
            index[entry[:-6]] = {"methods": methods, "fields": fields}
    return index


def _parse_class_detail(data: bytes) -> dict[str, Any] | None:
    """Return this/super/interfaces and ``(name, descriptor)`` members of one class file."""
    try:
        if len(data) < 10 or data[:4] != b"\xca\xfe\xba\xbe":
            return None
        pool_count = struct.unpack_from(">H", data, 8)[0]
        strings: dict[int, str] = {}
        classes: dict[int, int] = {}
        offset, index = 10, 1
        while index < pool_count:
            tag = data[offset]
            offset += 1
            if tag == 1:
                length = struct.unpack_from(">H", data, offset)[0]
                offset += 2
                strings[index] = data[offset:offset + length].decode("utf-8", "replace")
                offset += length
            else:
                width = _CONSTANT_WIDTH.get(tag)
                if width is None:
                    return None
                if tag == 7:
                    classes[index] = struct.unpack_from(">H", data, offset)[0]
                offset += width
            index += 2 if tag in _WIDE_TAGS else 1

        def class_name(idx: int) -> str | None:
            return strings.get(classes.get(idx, -1)) if idx else None

        this_class, super_class = struct.unpack_from(">HH", data, offset + 2)
        offset += 6
        count = struct.unpack_from(">H", data, offset)[0]
        interfaces = [class_name(struct.unpack_from(">H", data, offset + 2 + 2 * i)[0]) for i in range(count)]
        offset += 2 + count * 2

        def members() -> list[tuple[str, str, int]]:
            nonlocal offset
            total = struct.unpack_from(">H", data, offset)[0]
            offset += 2
            out = []
            for _ in range(total):
                access, name_index, descriptor_index = struct.unpack_from(">HHH", data, offset)
                offset += 6
                out.append((strings.get(name_index, ""), strings.get(descriptor_index, ""), access))
                attributes = struct.unpack_from(">H", data, offset)[0]
                offset += 2
                for _ in range(attributes):
                    length = struct.unpack_from(">I", data, offset + 2)[0]
                    offset += 6 + length
            return out

        fields = members()
        methods = members()
        return {"this": class_name(this_class), "super": class_name(super_class),
                "interfaces": [i for i in interfaces if i], "methods": methods, "fields": fields}
    except (struct.error, IndexError, UnicodeDecodeError):
        return None


def load_platform_members(jar: Path) -> dict[str, dict[str, Any]]:
    """Index one ``android.jar`` with descriptors and supertypes: ``android/os/Handler`` -> record.

    Unlike :func:`load_platform_index`, members keep their JNI signatures, which is what native
    code passes to ``GetMethodID`` and what makes a string match meaningful.
    """
    index: dict[str, dict[str, Any]] = {}
    with zipfile.ZipFile(jar) as archive:
        for entry in archive.namelist():
            if entry.endswith(".class"):
                parsed = _parse_class_detail(archive.read(entry))
                if parsed and parsed["this"]:
                    index[parsed["this"]] = parsed
    return index


def introduced_at(
    owner: str, member: str | None, kind: str, indexes: dict[int, dict[str, dict[str, set[str]]]]
) -> int | None:
    """Lowest indexed API level declaring this class or member, or ``None`` if never."""
    cls = owner.strip("L;")
    for api in sorted(indexes):
        entry = indexes[api].get(cls)
        if entry is None:
            continue
        if member is None:
            return api
        pool = entry["fields"] if kind.endswith("field") else entry["methods"]
        if member in pool:
            return api
        # A member may be declared on a supertype; the class existing is still evidence.
    return None


def annotate(
    findings: Iterable[dict[str, Any]],
    indexes: dict[int, dict[str, dict[str, set[str]]]],
    reference_api: int,
) -> dict[str, Any]:
    """Tag each absence finding with the API level that introduced it, and a verdict.

    ``reference_api`` is the API level of a device the app is known to run on. A member
    introduced after it cannot exist there, so the app already copes without it.
    """
    counts: dict[str, int] = {}
    annotated = 0
    for finding in findings:
        if not finding.get("kind", "").startswith("missing_"):
            continue
        dependency = finding["dependency"]
        kind = finding["kind"]
        member = dependency.get("name") if kind != "missing_class" else None
        api = introduced_at(dependency["owner"], member, kind, indexes)
        class_api = introduced_at(dependency["owner"], None, "missing_class", indexes)
        if api is not None and api <= reference_api:
            verdict = "required"                   # reachable on a device the app runs on
        elif api is not None:
            verdict = "newer-than-reference"       # app already tolerates its absence
        elif class_api is None:
            verdict = "absent-from-platform"      # the class was never an Android API
        else:
            # The class exists but no indexed jar declares this member: either it arrived
            # after the newest jar supplied, or it is a hidden/removed API. Not the same
            # claim as "never Android", so it gets its own verdict.
            verdict = "member-not-in-indexed-jars"
        finding["introduced_api"] = api
        finding["class_introduced_api"] = class_api
        finding["api_verdict"] = verdict
        counts[verdict] = counts.get(verdict, 0) + 1
        annotated += 1
    return {"reference_api": reference_api, "annotated": annotated, "verdicts": counts,
            "platform_jars": sorted(indexes)}
