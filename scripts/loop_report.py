#!/usr/bin/env python3
"""Accuracy of the loop so far, from committed predictions, observed outcomes and the ledger.

Inputs (all under benchmark/):
  loop-outcomes.json   per app: batch, first-launch outcome, outcome after the batch's fixes
  */predictions.json   the mechanical predictions committed before each batch launched
  blockers-ledger.json every startup blocker observed, with the row that names it (if any)

Prints, per batch: apps, drew on first launch, drew after fixes, and the rule's accuracy against
the first launch; then the ledger's coverage (blockers a gap-map row named).

Usage: loop_report.py [benchmark-dir]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "benchmark")
    outcomes = json.loads((root / "loop-outcomes.json").read_text())["apps"]
    predictions: dict[str, str] = {}
    for path in sorted(root.glob("*/predictions.json")):
        for app, entry in json.loads(path.read_text()).items():
            if isinstance(entry, dict) and "expected" in entry:
                predictions[app] = entry["expected"]
    by_batch: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for app, o in outcomes.items():
        by_batch[o["batch"]].append((app, o))

    print(f"{'batch':10} {'apps':>4} {'first':>6} {'after':>6} {'rule ok':>8}")
    total = defaultdict(int)
    order = ["loop-1", "corpus-2", "corpus-3"] + sorted((b for b in by_batch if b.startswith("batch-")),
                                                        key=lambda b: int(b.split("-")[1]))
    for batch in [b for b in order if b in by_batch]:
        apps = by_batch[batch]
        first = sum(o["first"] == "draws" for _, o in apps)
        after = sum(o["after"] == "draws" for _, o in apps)
        scored = [(a, o) for a, o in apps if a in predictions]
        right = sum(predictions[a] == o["first"] for a, o in scored)
        rule = f"{right}/{len(scored)}" if scored else "-"
        print(f"{batch:10} {len(apps):4d} {first:6d} {after:6d} {rule:>8}")
        total["apps"] += len(apps); total["first"] += first; total["after"] += after
        total["right"] += right; total["scored"] += len(scored)
    print(f"{'all':10} {total['apps']:4d} {total['first']:6d} {total['after']:6d} "
          f"{total['right']}/{total['scored']:>3}")

    ledger = json.loads((root / "blockers-ledger.json").read_text())["blockers"]
    rowed = sum(1 for b in ledger if b.get("row"))
    fixed = sum(1 for b in ledger if b.get("fixed_in"))
    print(f"\nledger: {len(ledger)} blockers, {rowed} named by a gap-map row, {fixed} fixed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
