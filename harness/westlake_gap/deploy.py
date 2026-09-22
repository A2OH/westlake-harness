"""Is what Westlake needs at run time actually deployed, and is it the build of today's source?

The gap map reads the APK against the provider's *source*. Two McDonald's blockers passed that and
still failed on the board, because the deployed runtime was not what the source described:

- `OhImeBridge` loads `liboh_ime_helper_capi.so`; the staged runtime did not contain it, so the
  soft keyboard never appeared (dlopen errno 2, logged and swallowed);
- the WebView input's `libwebview_bionic_shim.so` was captured from a device before the source
  gained the refusal of self-trapping libraries, so supplying the WebView brought Akamai's SIGILL
  back.

This check needs no device. From the Westlake tree it collects every library the runtime asks for
by name (`System.loadLibrary`, `dlopen` literals); from the build and launch reports it takes what
was staged, with hashes; from a board listing, what OpenHarmony itself provides. A name found in
none of them is **missing**. For staged Westlake binaries whose bytes are available, the log
strings of their sources are looked up in the binary: a binary that has some of them but not all
was built from an older source (**older than source**).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

DATA = Path(__file__).parent / "data" / "westlake-artifacts.json"

_LOAD_LIBRARY = re.compile(r'System\.loadLibrary\(\s*"([^"]+)"\s*\)')
_DLOPEN = re.compile(r'dlopen\(\s*"([^"]+)"')
# Tagged log strings: "[WESTLAKE-LOADER] refusing self-trapping library: %s\n" -> the constant
# prefix before the first format specifier or escape, when long enough to be distinctive.
_TAGGED = re.compile(r'"(\[[A-Z][A-Z0-9_\-. ]{2,40}\][^"%\\]*)')
_MIN_STRING = 16


def _line(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def expected_loads(westlake_root: Path) -> list[dict[str, Any]]:
    """Every library the runtime asks for by name, with where it asks."""
    loads: list[dict[str, Any]] = []
    framework = westlake_root / "framework"
    for path in sorted(framework.rglob("*.java")):
        if "/tests/" in path.as_posix():
            continue
        text = path.read_text(errors="replace")
        for match in _LOAD_LIBRARY.finditer(text):
            loads.append({"name": "lib" + match.group(1) + ".so", "how": "System.loadLibrary",
                          "site": f"{path.relative_to(westlake_root)}:{_line(text, match.start())}"})
    for pattern in ("*.c", "*.cc", "*.cpp"):
        for path in sorted(framework.rglob(pattern)):
            if "/tests/" in path.as_posix():
                continue
            text = path.read_text(errors="replace")
            for match in _DLOPEN.finditer(text):
                loads.append({"name": match.group(1), "how": "dlopen",
                              "site": f"{path.relative_to(westlake_root)}:{_line(text, match.start())}"})
    return loads


def staged_files(*reports: dict[str, Any]) -> dict[str, str]:
    """Staged path -> sha256, from a framework build report and/or an app launch report."""
    staged: dict[str, str] = {}
    for report in reports:
        for key in ("files", "source_files"):
            for name, entry in (report.get(key) or {}).items():
                staged[name] = entry.get("sha256", "")
        for key in ("webview_payload", "webview_device_input"):
            for name, entry in ((report.get(key) or {}).get("files") or {}).items():
                staged[name] = entry.get("sha256", "")
    return staged


def board_libraries(listing: Path | None) -> set[str]:
    """Full paths and basenames of the libraries on the board (one path per line)."""
    if listing is None:
        return set()
    names = set()
    for line in listing.read_text().splitlines():
        line = line.strip()
        if line:
            names.add(line)
            names.add(line.rsplit("/", 1)[-1])
    return names


def classify_loads(loads: list[dict[str, Any]], staged: dict[str, str], board: set[str]) -> list[dict[str, Any]]:
    staged_names = {name.rsplit("/", 1)[-1] for name in staged} | set(staged)
    by_name: dict[str, dict[str, Any]] = {}
    for load in loads:
        name = load["name"]
        entry = by_name.setdefault(name, {"name": name, "sites": [], "how": set()})
        entry["sites"].append(load["site"])
        entry["how"].add(load["how"])
    rows = []
    for name, entry in sorted(by_name.items()):
        base = name.rsplit("/", 1)[-1]
        if name.startswith("/data/local/tmp/asx/"):
            status = "staged" if name.removeprefix("/data/local/tmp/asx/") in staged else "missing"
        elif base in staged_names:
            status = "staged"
        elif name in board or base in board:
            status = "board"
        else:
            status = "missing" if board else "not staged (board listing not given)"
        # System.loadLibrary throws UnsatisfiedLinkError; a dlopen caller often has a fallback.
        rows.append({"name": name, "status": status, "how": sorted(entry["how"]), "sites": entry["sites"],
                     "on_failure": "throws" if "System.loadLibrary" in entry["how"] else "caller decides"})
    return rows


def artifact_sources(westlake_root: Path, data: dict[str, Any] | None = None) -> dict[str, list[str]]:
    """Westlake-built artifact -> its source files (Westlake-relative), from the tree's own records."""
    mapping: dict[str, list[str]] = {}
    index = westlake_root / "native" / "libraries.json"
    if index.exists():
        for name, entry in json.loads(index.read_text()).get("libraries", {}).items():
            mapping[name] = [s.removeprefix("westlake/") for s in entry.get("sources", []) if s.startswith("westlake/")]
    builder = westlake_root / "tools" / "build_native.py"
    if builder.exists():
        for name, source in re.findall(r"\('(lib[\w.+-]+\.so)',\s*ROOT\s*/\s*'([^']+)'", builder.read_text()):
            mapping[name] = [source]
    for name, entry in (data or json.loads(DATA.read_text()))["artifacts"].items():
        sources = list(entry.get("sources", []))
        manifest = entry.get("manifest")
        if manifest and (westlake_root / manifest).exists():
            listed = json.loads((westlake_root / manifest).read_text()).get("sources", [])
            sources += [s.removeprefix("westlake/") for s in listed if isinstance(s, str) and s.startswith("westlake/")]
        mapping[name] = sources
    return {name: sources for name, sources in mapping.items() if sources}


def strip_comments(text: str) -> str:
    """C/C++/Java source without comments; string and character literals are kept intact."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            j = i + 1
            while j < n and text[j] != c:
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("//", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            out.append(" ")
            i = n if j < 0 else j + 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def source_strings(westlake_root: Path, sources: list[str]) -> dict[str, list[str]]:
    """Source file -> its distinctive tagged log strings (comments excluded)."""
    by_file: dict[str, list[str]] = {}
    for source in sources:
        path = westlake_root / source
        if not path.exists():
            continue
        strings = {m.group(1).rstrip() for m in _TAGGED.finditer(strip_comments(path.read_text(errors="replace")))}
        strings = sorted(v for v in strings if len(v) >= _MIN_STRING)
        if strings:
            by_file[source] = strings
    return by_file


def freshness(westlake_root: Path, staged: dict[str, str], local_dirs: list[Path],
              mapping: dict[str, list[str]]) -> list[dict[str, Any]]:
    """For each staged Westlake binary with bytes on hand: are its sources' log strings in it?"""
    by_sha: dict[str, Path] = {}
    for directory in local_dirs:
        for path in directory.rglob("*"):
            if path.is_file() and (path.suffix in {".so", ".a"} or ".so." in path.name):
                by_sha[hashlib.sha256(path.read_bytes()).hexdigest()] = path
    rows = []
    for name, sha in sorted(staged.items()):
        base = name.rsplit("/", 1)[-1]
        sources = mapping.get(base)
        local = by_sha.get(sha)
        if not sources or local is None:
            continue
        by_file = source_strings(westlake_root, sources)
        if not by_file:
            continue
        data = local.read_bytes()
        # Judged per source file: a file with none of its strings in the binary is not compiled
        # into it (a build flag, another library); one with some but not all was compiled from
        # an older version of that file.
        compiled, stale_files, absent, total = 0, [], [], 0
        for source, strings in by_file.items():
            missing = [s for s in strings if s.encode() not in data]
            if len(missing) == len(strings):
                continue
            compiled += 1
            total += len(strings)
            if missing:
                stale_files.append(source)
                absent += [{"string": s, "source": source} for s in missing]
        if compiled == 0:
            verdict = "unverified"      # no source string at all: wrong mapping or strings stripped
        elif stale_files:
            verdict = "older than source"
        else:
            verdict = "matches source"
        rows.append({"artifact": name, "sha256": sha, "sources": sources, "files_compiled_in": compiled,
                     "strings": total, "absent": len(absent), "stale_files": stale_files,
                     "absent_examples": absent[:5], "verdict": verdict})
    return rows


def check(westlake_root: Path, reports: list[dict[str, Any]], local_dirs: list[Path],
          board_listing: Path | None = None) -> dict[str, Any]:
    staged = staged_files(*reports)
    loads = classify_loads(expected_loads(westlake_root), staged, board_libraries(board_listing))
    fresh = freshness(westlake_root, staged, local_dirs, artifact_sources(westlake_root))
    return {
        "summary": {
            "loads": len(loads),
            "missing": [row["name"] for row in loads if row["status"] == "missing"],
            "older_than_source": [row["artifact"] for row in fresh if row["verdict"] == "older than source"],
            "staged_files": len(staged),
        },
        "loads": loads,
        "freshness": fresh,
    }


def markdown(result: dict[str, Any], title: str) -> str:
    s = result["summary"]
    out = [f"# {title}", "",
           f"{s['staged_files']} files staged; the runtime asks for {s['loads']} libraries by name.", "",
           f"**Missing: {len(s['missing'])}. Older than their source: {len(s['older_than_source'])}.**", ""]
    missing = [row for row in result["loads"] if row["status"] == "missing"]
    if missing:
        out += ["## Asked for, not deployed", "", "| Library | How | If absent | Where |", "|---|---|---|---|"]
        for row in missing:
            out.append(f"| `{row['name']}` | {', '.join(row['how'])} | {row['on_failure']} | "
                       f"{', '.join('`' + x + '`' for x in row['sites'][:3])} |")
        out.append("")
    stale = [row for row in result["freshness"] if row["verdict"] != "matches source"]
    if stale:
        out += ["## Deployed binaries and their source", "",
                "A source file counts when the binary holds some of its log strings; it is stale when it holds "
                "some but not all.", "",
                "| Binary | Verdict | Stale source files | Example string absent |", "|---|---|---|---|"]
        for row in stale:
            example = row["absent_examples"][0] if row["absent_examples"] else None
            ex = f"`{example['string']}` ({example['source'].rsplit('/', 1)[-1]})" if example else ""
            files = ", ".join(f"`{f.rsplit('/', 1)[-1]}`" for f in row["stale_files"][:4])
            out.append(f"| `{row['artifact']}` | {row['verdict']} | {files} | {ex} |")
        out.append("")
    fine = [row["artifact"] for row in result["freshness"] if row["verdict"] == "matches source"]
    if fine:
        out += ["Matching their source: " + ", ".join(f"`{name}`" for name in fine) + ".", ""]
    return "\n".join(out)
