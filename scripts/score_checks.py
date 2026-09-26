#!/usr/bin/env python3
"""Per-check accuracy of the gap map against what the board showed.

For every app with a map and a known current outcome (loop-outcomes.json "after": the provider the
maps were made against), each check family is scored as a startup-blocker detector:

  blocked  apps it flags that are blocked on the board   (true positives)
  drew     apps it flags that draw anyway                (false alarms as a blocker signal)
  precision = blocked / (blocked + drew), recall = blocked / all blocked apps

A check with low precision can still be a correct gap list (a media class nobody touches before
the first screen); the score only says how well it predicts a first screen.

Then the ledger: of the blockers still open, how many are named by a row in that app's current map.

Usage: score_checks.py <map-root> <benchmark-dir>
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

LOOKUP_LIBS = ("libandroid.so", "libnativewindow.so", "libmediandk.so", "libaaudio.so")
CLASS_INIT = re.compile(r"(?i)^_?native_?(class_?)?init\(")


def families(rows: list[dict]) -> set[str]:
    out = set()
    for r in rows:
        rid, verdict = r["id"], r["verdict"]
        if rid.startswith("ndk:") and verdict == "missing" and "unshipped-library" not in rid:
            out.add("native: unresolved NDK/libc import")
        if rid == "load:needed-missing":
            out.add("native: DT_NEEDED library nobody provides")
        if r.get("throws_in_framework"):
            out.add("service: null unwrapped inside the framework")
        if r.get("throws_if_null"):
            out.add("service: null cast non-null by the app")
        if rid.startswith("svc:") and verdict in ("null", "hollow", "strict"):
            out.add("service: any null/hollow/strict")
        if rid in {f"sym:runtime-resolved:{lib}" for lib in LOOKUP_LIBS}:
            out.add("native: NDK name looked up at run time")
        if rid == "window:engine-surface":
            out.add("window: engine draws into its own SurfaceView")
        if rid.startswith("jni:"):
            out.add("framework natives: any unregistered")
            if any(CLASS_INIT.match(s) for s in r.get("open_symbols", [])):
                out.add("framework natives: class initializer unregistered")
        if rid.startswith("data:"):
            out.add(f"runtime data: {rid[5:]}")
        if rid == "wv:renderer-process":
            out.add("webview: renderer process")
        if rid.startswith("java:") and verdict == "missing":
            out.add("java: platform API absent")
        if rid == "pm:multiprocess":
            out.add("pm: secondary processes")
    return out


def main() -> int:
    maps, bench = Path(sys.argv[1]), Path(sys.argv[2])
    outcomes = json.loads((bench / "loop-outcomes.json").read_text())["apps"]
    flagged: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"blocked": [], "drew": []})
    blocked_total = drew_total = 0
    for app, o in sorted(outcomes.items()):
        path = maps / app / "gap-map.json"
        if not path.exists():
            continue
        state = "blocked" if o["after"] == "blocked" else "drew"
        blocked_total += state == "blocked"
        drew_total += state == "drew"
        for family in families(json.loads(path.read_text())["rows"]):
            flagged[family][state].append(app)

    print(f"{blocked_total} apps blocked, {drew_total} drawing on the provider the maps describe\n")
    print(f"{'check':52} {'blocked':>7} {'drew':>5} {'prec':>5} {'recall':>6}")
    for family, hit in sorted(flagged.items(), key=lambda kv: -len(kv[1]["blocked"])):
        b, d = len(hit["blocked"]), len(hit["drew"])
        print(f"{family:52} {b:7d} {d:5d} {b / max(1, b + d):5.2f} {b / max(1, blocked_total):6.2f}")

    ledger = json.loads((bench / "blockers-ledger.json").read_text())["blockers"]
    open_blockers = [b for b in ledger if not b.get("fixed_in") and b["app"] in outcomes]
    named = []
    for b in open_blockers:
        path = maps / b["app"] / "gap-map.json"
        ids = {r["id"] for r in json.loads(path.read_text())["rows"]} if path.exists() else set()
        if b.get("row") and b["row"] in ids:
            named.append(b)
    print(f"\nopen ledger blockers: {len(open_blockers)}, named by a row in the app's current map: {len(named)}")
    for b in open_blockers:
        mark = "row " + b["row"] if b in named else "NO ROW"
        print(f"  {b['app']:14} {mark:42} {b['symptom'][:70]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
