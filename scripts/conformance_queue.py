#!/usr/bin/env python3
"""The conformance queue: Westlake's work ranked by measured impact (ADR-0001).

Every open row across the corpus's gap maps, ranked by

    apps whose map has the row open  x  what the conformance run measured  /  effort

where a row the probes found broken weighs 1, a row no probe has measured 0.5 (it may or may not be
broken), and a row measured conformant or truthfully absent drops out. Effort weighs XS 1, S 2,
verify 3, M 4, L 8, OH 16. Rows that describe the provider rather than the app (a map's
provider_rows) are counted once, apart.

It also reports ADR-0001's measures: open rows per app, and the share of the corpus's app-specific
open rows (app x row) that carry a measured verdict.

Usage: conformance_queue.py <map-root> [<map-root> ...] [--top N] [--out queue.md]
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path

OPEN = {"missing", "stub", "hollow", "null", "strict", "unresolved", "inert", "denied", "partial", "unverified",
        "hollow-candidate", "probe-only", "refused", "environment-sensitive"}
EFFORT = {"XS": 1, "S": 2, "verify": 3, "M": 4, "L": 8, "OH": 16}
WEIGHT = {"broken": 1.0, None: 0.5}


def load_maps(roots: list[Path]) -> dict[str, dict]:
    maps = {}
    for root in roots:
        for path in sorted(root.glob("*/gap-map.json")):
            maps.setdefault(path.parent.name, json.loads(path.read_text()))
    return maps


def queue(maps: dict[str, dict]) -> tuple[list[dict], dict]:
    apps_with: dict[str, set[str]] = defaultdict(set)
    sample: dict[str, dict] = {}
    measured_instances = open_instances = 0
    per_app_open = []
    for app, gap in maps.items():
        open_here = 0
        for row in gap["rows"]:
            measured = row.get("measured")
            if measured in {"conformant", "absent"}:
                measured_instances += 1
                open_instances += 1
                continue
            if row.get("verdict") not in OPEN or row.get("effort") == "none":
                continue
            open_here += 1
            open_instances += 1
            if measured == "broken":
                measured_instances += 1
            apps_with[row["id"]].add(app)
            if row["id"] not in sample or (measured == "broken" and sample[row["id"]].get("measured") != "broken"):
                sample[row["id"]] = row
        per_app_open.append(open_here)
    ranked = []
    for row_id, apps in apps_with.items():
        row = sample[row_id]
        weight = WEIGHT.get(row.get("measured"), 0.5)
        effort = EFFORT.get(row.get("effort"), 4)
        ranked.append({"row": row_id, "apps": len(apps), "measured": row.get("measured") or "unmeasured",
                       "effort": row.get("effort"), "category": row.get("category"),
                       "score": round(len(apps) * weight / effort, 1),
                       "finding": (row.get("provider") or "")[:160] if row.get("measured") == "broken" else ""})
    ranked.sort(key=lambda r: (-r["score"], -r["apps"], r["row"]))
    provider = Counter(row["id"] for gap in maps.values() for row in gap.get("provider_rows", [])
                       if row.get("verdict") in OPEN)
    summary = {"maps": len(maps),
               "median_open_rows_per_app": statistics.median(per_app_open) if per_app_open else 0,
               "open_row_instances": open_instances, "measured_instances": measured_instances,
               "measured_share": round(measured_instances / open_instances, 3) if open_instances else 0.0,
               "provider_rows": len(provider)}
    return ranked, summary


def markdown(ranked: list[dict], summary: dict, top: int) -> str:
    out = ["# Conformance queue", "",
           f"{summary['maps']} gap maps. Median open rows per app: {summary['median_open_rows_per_app']}. "
           f"Measured: {summary['measured_instances']} of {summary['open_row_instances']} app-specific open rows "
           f"({summary['measured_share']:.0%}). Provider rows, counted apart: {summary['provider_rows']}.", "",
           "| rank | row | apps | measured | effort | score | the probe's finding |", "|---|---|---|---|---|---|---|"]
    for i, r in enumerate(ranked[:top], 1):
        out.append(f"| {i} | `{r['row']}` | {r['apps']} | {r['measured']} | {r['effort']} | {r['score']} | "
                   f"{r['finding'].replace('|', '/')} |")
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("roots", nargs="+", type=Path)
    parser.add_argument("--top", type=int, default=30)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    ranked, summary = queue(load_maps(args.roots))
    text = markdown(ranked, summary, args.top)
    if args.out:
        args.out.write_text(text)
    if args.json:
        args.json.write_text(json.dumps({"summary": summary, "queue": ranked}, indent=1) + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
