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


def index_export_versions(directories: list[Path]) -> dict[str, set[str | None]]:
    """For every provided symbol, the versions it is defined under; None stands for a definition in
    a library without symbol versions, which satisfies an import of any version."""
    versions: dict[str, set[str | None]] = {}
    for directory in directories:
        for name, record in ndk.library_exports(directory).items():
            if ndk.is_variant(name):
                continue
            defined = record.get("versions") or {}
            for symbol in record["exports"]:
                versions.setdefault(symbol, set()).add(defined.get(symbol))
    return versions


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


def packaged_elfs(scan: dict[str, Any]) -> list[dict[str, Any]]:
    """target_elfs without the libraries harvested from the app's storage after a run (scan
    --unpacked-libs): the launcher stages and routes only what the APK packages."""
    return [elf for elf in target_elfs(scan) if elf.get("origin") != "unpacked"]


def resolve(scan: dict[str, Any], provided: set[str], declared: dict[str, str],
            versions: dict[str, set[str | None]] | None = None) -> dict[str, Any]:
    """With versions (index_export_versions), an import that asks for a version resolves only against
    a definition under that version or one in an unversioned library, as OH's loader binds:
    Messenger's libcore.so asked for __system_property_read_callback@LIBC_O, and the bionic shim
    defined it under LIBC only."""
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
    wanted: dict[str, set[str]] = {}
    for elf in elfs:
        for symbol, version in (elf.get("import_versions") or {}).items():
            wanted.setdefault(symbol, set()).add(version)
    missing = []
    for symbol, names in sorted(importers.items()):
        if symbol in own:
            continue
        if symbol in provided:
            defined = (versions or {}).get(symbol)
            if not defined or None in defined or not wanted.get(symbol) or wanted[symbol] <= defined:
                continue
            missing.append({"symbol": symbol, "importers": len(names), "importing_libraries": sorted(names),
                            "surface": declared.get(symbol, "bionic-private (not in the NDK)"),
                            "version_mismatch": {"wanted": sorted(wanted[symbol] - defined),
                                                 "defined": sorted(defined)}})
            continue
        missing.append({"symbol": symbol, "importers": len(names), "importing_libraries": sorted(names),
                        "surface": declared.get(symbol, "bionic-private (not in the NDK)")})
    missing.sort(key=lambda m: (-m["importers"], m["symbol"]))
    return {"symbols": len(importers), "resolved": len(importers) - len(missing), "missing": missing,
            "versioned_clash": versioned_clashes(elfs, versions)}


def versioned_clashes(elfs: list[dict[str, Any]], versions: dict[str, set[str | None]] | None) -> list[dict[str, Any]]:
    """Imports versioned against another of the app's own libraries, under a name a library without
    symbol versions on the board also defines. OH's loader takes that unversioned definition for an
    import that names its version by hash, and libc is searched before the app's libraries, so the
    import binds to the board's copy; Android's linker binds it only to the versioned one. Firefox's
    libraries import malloc and free as name@libmozglue.so: libxul freed with musl's free what
    libmozglue's mozjemalloc had allocated."""
    if not versions:
        return []
    own = {(elf.get("soname") or elf.get("name", "").rsplit("/", 1)[-1]).removesuffix(".so") for elf in elfs}
    by_import: dict[tuple[str, str], set[str]] = {}
    for elf in elfs:
        name = elf.get("soname") or elf.get("name")
        for symbol, version in (elf.get("import_versions") or {}).items():
            if version and version.removesuffix(".so") in own and None in versions.get(symbol, set()):
                by_import.setdefault((symbol, version.removesuffix(".so")), set()).add(name)
    return [{"symbol": symbol, "version": version, "importing_libraries": sorted(names)}
            for (symbol, version), names in sorted(by_import.items())]
