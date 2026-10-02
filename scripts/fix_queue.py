#!/usr/bin/env python3
"""The fix queue: which open gaps, closed, would unblock the most apps.

For every open row (not supplied) across the maps, the apps that carry it, split by their current
outcome: a row that many blocked apps carry and few drawing apps do is a likely blocker, and its
count is the payoff of closing it. The ledger's open blockers that no row names come after: those are
the gaps the harness cannot see yet, and each one is a candidate for a new check.

Usage: fix_queue.py <map-root> <benchmark-dir> [top-n]
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

OPEN = {"missing", "stub", "hollow", "null", "strict", "unresolved", "absent", "partial", "unverified",
        "hollow-candidate", "refused", "environment-sensitive"}
# Row families that sit in most maps and say little about a first screen on their own.
BACKGROUND = ("java:", "svc:", "pm:providers", "pm:component-metadata", "wm:", "load:in-apk",
              "load:runtime-silent-success", "policy:", "dep:")


def main() -> int:
    maps, bench = Path(sys.argv[1]), Path(sys.argv[2])
    top = int(sys.argv[3]) if len(sys.argv) > 3 else 25
    outcomes = json.loads((bench / "loop-outcomes.json").read_text())["apps"]
    carried: dict[str, dict[str, list[str]]] = defaultdict(lambda: {"blocked": [], "drew": []})
    items: dict[str, str] = {}
    for app, outcome in sorted(outcomes.items()):
        path = maps / app / "gap-map.json"
        if outcome["after"] not in ("blocked", "draws") or not path.exists():
            continue
        state = "blocked" if outcome["after"] == "blocked" else "drew"
        for row in json.loads(path.read_text())["rows"]:
            if row["verdict"] in OPEN and not row["id"].startswith(BACKGROUND):
                carried[row["id"]][state].append(app)
                items.setdefault(row["id"], row["item"])
    # A row most apps carry says little; one carried mostly by blocked apps is a lead. Rank by how
    # far the blocked share among its carriers is above the corpus's base rate, then by payoff.
    states = [o["after"] for o in outcomes.values() if o["after"] in ("blocked", "draws")]
    base = states.count("blocked") / max(1, len(states))

    def share(apps: dict[str, list[str]]) -> float:
        return len(apps["blocked"]) / max(1, len(apps["blocked"]) + len(apps["drew"]))

    leads = [(rid, apps) for rid, apps in carried.items()
             if len(apps["blocked"]) >= 2 and share(apps) >= min(0.5, 2 * base)]
    leads.sort(key=lambda kv: (-share(kv[1]), -len(kv[1]["blocked"]), kv[0]))
    print(f"base rate: {base:.2f} of apps blocked. Rows carried mostly by blocked apps:")
    print(f"{'open row':52} {'blocked':>7} {'drew':>5} {'share':>5}  blocked apps")
    for rid, apps in leads[:top]:
        print(f"{rid[:52]:52} {len(apps['blocked']):7d} {len(apps['drew']):5d} {share(apps):5.2f}  "
              f"{', '.join(apps['blocked'][:6])}")

    ledger = json.loads((bench / "blockers-ledger.json").read_text())["blockers"]
    unseen = [b for b in ledger if not b.get("fixed_in") and not b.get("row")
              and outcomes.get(b["app"], {}).get("after") == "blocked"]
    print(f"\nopen ledger blockers no row names ({len(unseen)}): the harness's blind spots")
    for b in unseen:
        print(f"  {b['app']:18} {b['symptom'][:100]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
