"""Resolve an APK's native imports against the libraries a process gets on the board.

An import is resolved when the APK's own libraries export it or a library in the index does: OH's
system libraries pulled from the board plus the staged Westlake runtime (including the bionic shim
preloaded for APK libraries). Weak imports are optional and never count as missing. Each missing
symbol records how many of the APK's libraries import it and, from the NDK stub libraries, which
NDK library declares it ("surface"); a symbol no NDK library declares is bionic-private.

The output has the shape `gap-map --oh-resolution` reads: {"board", "apps": {key: {...}}}.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import ndk


def index_exports(directories: list[Path]) -> tuple[set[str], list[str]]:
    exports: set[str] = set()
    libraries = []
    for directory in directories:
        for name, record in ndk.library_exports(directory).items():
            if ndk.is_variant(name):
                continue
            exports |= record["exports"]
            libraries.append(f"{directory.name}/{name}")
    return exports, sorted(libraries)


def ndk_declarations(api_dir: Path | None) -> dict[str, str]:
    if api_dir is None:
        return {}
    declared = {}
    for library, symbols in ndk.ndk_surface(api_dir).items():
        for symbol in symbols:
            declared.setdefault(symbol, library.removesuffix(".so"))
    return declared


def target_elfs(scan: dict[str, Any]) -> list[dict[str, Any]]:
    """The packaged libraries the process loads: a fat APK carries every ABI's copy of each library,
    and only the target ABI's are loaded. The others import 32-bit ARM or x86 runtime symbols
    (__aeabi_*) that no arm64 process has."""
    elfs = scan["inventory"].get("elfs", [])
    target = scan.get("apk", {}).get("target_abi") or scan["inventory"].get("native_resolution", {}).get("target_abi")
    return [elf for elf in elfs if elf.get("abi", target) == target] if target else list(elfs)


def resolve(scan: dict[str, Any], provided: set[str], declared: dict[str, str]) -> dict[str, Any]:
    elfs = target_elfs(scan)
    own: set[str] = set()
    for elf in elfs:
        own |= set(elf.get("exported_symbols", []))
    importers: dict[str, set[str]] = {}
    for elf in elfs:
        name = elf.get("soname") or elf.get("name")
        weak = set(elf.get("undefined_weak_symbols", []))
        for symbol in elf.get("undefined_symbols", []):
            if symbol not in weak:
                importers.setdefault(symbol, set()).add(name)
    missing = []
    for symbol, names in sorted(importers.items()):
        if symbol in own or symbol in provided:
            continue
        missing.append({"symbol": symbol, "importers": len(names), "importing_libraries": sorted(names),
                        "surface": declared.get(symbol, "bionic-private (not in the NDK)")})
    missing.sort(key=lambda m: (-m["importers"], m["symbol"]))
    return {"symbols": len(importers), "resolved": len(importers) - len(missing), "missing": missing}
