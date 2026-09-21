"""The entire NDK as the native provider contract, and how each piece is supplied on OpenHarmony.

Westlake's strategy for native code (`analysis/AOSP-PACKAGING-STRATEGY.md`) is to package AOSP's
NDK libraries the way it packages the framework jars, and weld only their bottoms to OpenHarmony.
Under that strategy, an app import missing from the OH board is not simply "missing". It is one of:

- **package**: AOSP source Westlake compiles; nothing new underneath;
- **libc-abi**: a bionic name to translate onto musl (two libcs cannot share a process);
- **weld**: AOSP source above a named OH subsystem (audio, sensors, camera, …): the real work;
- **gpu-driver** / **use-oh**: OpenHarmony answers; missing names are Android extensions;
- **truthful-absence**: legacy or deprecated, reported unavailable the way a device without it does.

This module measures the whole public NDK (from the NDK's stub libraries) against the libraries
on a board, classifies every missing symbol with `data/ndk-weld-model.json`, and checks whether
Westlake already has a build manifest for the AOSP source behind it: "built but not deployed" is a
very different gap from "not started".
"""

from __future__ import annotations

import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from elftools.elf.elffile import ELFFile

MODEL_PATH = Path(__file__).parent / "data" / "ndk-weld-model.json"

# Backup and experimental copies left in a deployment directory (`libart.pre-jit790.so`,
# `bridge_604.so`, `libart-607-known-good.so`) are not what the process loads. Counting their
# exports would overstate coverage, so they are reported separately.
_VARIANT = re.compile(r"\.|[-_]\d{3}[a-z]?(?=$|[-_.])|known-good|-jit\d|-\d{8}")


def is_variant(name: str) -> bool:
    stem = name[:-3] if name.endswith(".so") else name
    return bool(_VARIANT.search(stem))


def elf_exports(data: bytes) -> set[str]:
    """Defined global/weak dynamic symbols of one ELF, or an empty set for anything else."""
    if data[:4] != b"\x7fELF":
        return set()
    table = ELFFile(io.BytesIO(data)).get_section_by_name(".dynsym")
    if table is None:
        return set()
    return {s.name for s in table.iter_symbols()
            if s.name and s["st_shndx"] != "SHN_UNDEF" and s["st_info"]["bind"] in ("STB_GLOBAL", "STB_WEAK")}


def ndk_surface(api_dir: Path) -> dict[str, list[str]]:
    """Public NDK symbols per library, from the stub libraries of one API level of an NDK sysroot."""
    surface = {}
    for path in sorted(api_dir.glob("*.so")):
        exports = elf_exports(path.read_bytes())  # linker scripts (libc++.so) yield nothing
        if exports:
            surface[path.name] = sorted(exports)
    return surface


def library_exports(directory: Path) -> dict[str, dict[str, Any]]:
    """Name -> exports and sha256 for every ELF in a directory pulled from a board."""
    out = {}
    for path in sorted(directory.glob("*.so")):
        data = path.read_bytes()
        exports = elf_exports(data)
        if exports:
            out[path.name] = {"sha256": hashlib.sha256(data).hexdigest(), "exports": exports}
    return out


def load_model(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or MODEL_PATH).read_text())


def classify(library: str, symbol: str, model: dict[str, Any]) -> dict[str, Any]:
    """How a missing NDK symbol is supplied: group, weld and AOSP source."""
    entry = model["libraries"].get(library, {})
    for family in entry.get("families", []):
        if re.search(family["match"], symbol):
            rule = {**entry, **family}
            break
    else:
        rule = {**entry, "group": entry.get("missing_group") or entry.get("group", "package")}
    weld = rule.get("weld") if rule.get("group") == "weld" else None
    return {"group": rule.get("group", "package"), "weld": weld,
            "oh": model["welds"].get(weld, {}).get("oh") if weld else None,
            "source": rule.get("source"), "note": rule.get("note")}


def westlake_manifest_index(westlake_root: Path) -> dict[str, list[str]]:
    """AOSP source path -> Westlake native build manifests that compile it."""
    index: dict[str, set[str]] = defaultdict(set)

    def walk(value: Any, manifest: str) -> None:
        if isinstance(value, str) and value.endswith((".c", ".cc", ".cpp")):
            index[value].add(manifest)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item, manifest)
        elif isinstance(value, list):
            for item in value:
                walk(item, manifest)

    for manifest in sorted((westlake_root / "native").glob("*.json")):
        try:
            walk(json.loads(manifest.read_text()), manifest.name)
        except (json.JSONDecodeError, OSError):
            continue
    return {path: sorted(names) for path, names in index.items()}


def manifests_for(source: str | None, index: dict[str, list[str]]) -> list[str]:
    """Manifests compiling a model source: an exact file, or any file under a source directory."""
    if not source:
        return []
    hits = set()
    for path, names in index.items():
        if path.endswith("/" + source) or ("/" + source + "/") in path:
            hits.update(names)
    return sorted(hits)


def coverage(
    surface: dict[str, list[str]],
    oh: dict[str, dict[str, Any]],
    westlake: dict[str, dict[str, Any]],
    model: dict[str, Any],
    manifest_index: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    live = {name: rec for name, rec in westlake.items() if not is_variant(name)}
    variants = {name: rec for name, rec in westlake.items() if is_variant(name)}

    def providers(symbol: str, pool: dict[str, dict[str, Any]]) -> list[str]:
        return sorted(name for name, rec in pool.items() if symbol in rec["exports"])

    symbols = []
    for library, names in sorted(surface.items()):
        for symbol in names:
            item: dict[str, Any] = {"library": library, "symbol": symbol}
            if found := providers(symbol, oh):
                item.update(status="oh", providers=found)
            elif found := providers(symbol, live):
                item.update(status="westlake", providers=found)
            else:
                item["status"] = "missing"
                if found := providers(symbol, variants):
                    item["only_in_backup_copies"] = found
                how = classify(library, symbol, model)
                item.update(how)
                if manifest_index is not None:
                    item["westlake_manifests"] = manifests_for(how["source"], manifest_index)
            symbols.append(item)

    per_library = {}
    for library, names in sorted(surface.items()):
        rows = [s for s in symbols if s["library"] == library]
        per_library[library] = {"symbols": len(names), **Counter(s["status"] for s in rows),
                                "strategy": model["libraries"].get(library, {}).get("group", "unmodelled")}
    missing = [s for s in symbols if s["status"] == "missing"]
    return {
        "summary": {
            "symbols": len(symbols),
            "libraries": len(surface),
            "status": dict(Counter(s["status"] for s in symbols)),
            "missing_by_group": dict(Counter(s["group"] for s in missing)),
            "missing_by_weld": dict(Counter(s["weld"] for s in missing if s["weld"])),
            "missing_with_westlake_manifest": sum(1 for s in missing if s.get("westlake_manifests")),
            "missing_only_in_backup_copies": sum(1 for s in missing if s.get("only_in_backup_copies")),
        },
        "per_library": per_library,
        "providers": {"oh": {n: r["sha256"] for n, r in oh.items()},
                      "westlake_live": {n: r["sha256"] for n, r in live.items()},
                      "westlake_backup_copies": sorted(variants)},
        "symbols": symbols,
    }


def markdown(cov: dict[str, Any], model: dict[str, Any], title: str) -> str:
    s = cov["summary"]
    status = s["status"]
    total = s["symbols"]
    pct = lambda n: f"{100 * n / total:.1f}%" if total else "—"
    out = [f"# {title}", "",
           f"The whole public NDK: **{total} symbols in {s['libraries']} libraries**.", "",
           "| Provided by | Symbols | Share |", "|---|---|---|",
           f"| OpenHarmony | {status.get('oh', 0)} | {pct(status.get('oh', 0))} |",
           f"| Westlake (live libraries) | {status.get('westlake', 0)} | {pct(status.get('westlake', 0))} |",
           f"| Missing | {status.get('missing', 0)} | {pct(status.get('missing', 0))} |", "",
           "## How the missing symbols are supplied", "",
           "| Strategy | Symbols | Meaning |", "|---|---|---|"]
    for group, count in sorted(s["missing_by_group"].items(), key=lambda kv: -kv[1]):
        out.append(f"| {group} | {count} | {model['groups'].get(group, '')} |")
    out += ["", "| Weld | Symbols | OpenHarmony subsystem | Effort |", "|---|---|---|---|"]
    for weld, count in sorted(s["missing_by_weld"].items(), key=lambda kv: -kv[1]):
        info = model["welds"].get(weld, {})
        out.append(f"| {weld} | {count} | {info.get('oh', '')} | {info.get('effort', '')} |")
    out += ["", f"{s['missing_with_westlake_manifest']} missing symbols already have a Westlake build manifest for "
            "their AOSP source (built, not deployed on the measured board). "
            f"{s['missing_only_in_backup_copies']} exist only in backup copies of a library, which are not counted.",
            "", "## Per library", "", "| Library | Symbols | OH | Westlake | Missing | Strategy |", "|---|---|---|---|---|---|"]
    for library, row in sorted(cov["per_library"].items(), key=lambda kv: -kv[1]["symbols"]):
        out.append(f"| `{library}` | {row['symbols']} | {row.get('oh', 0)} | {row.get('westlake', 0)} | "
                   f"{row.get('missing', 0)} | {row['strategy']} |")
    return "\n".join(out) + "\n"
