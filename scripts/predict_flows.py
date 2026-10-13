#!/usr/bin/env python3
"""Predict calibration flows from gap maps alone, by a fixed rule.

A plan, written before any map is read, names each flow's app, what the user does, what counts as
working, and the contracts the function needs: row ids, or id prefixes ending in "*". A flow
is predicted to fail when any of its app's rows that match is a hard gap, the verdicts the startup
backtest counts as predicting a failure (gapmap.HARD_GAPS: missing, null, inert, hollow, strict,
denied, stub, absent). Otherwise it is predicted to work, also when no row matches: the map knows no
gap on the path. Each prediction lists the rows it read, and the contracts no row describes, which
are where a miss would point.

    scripts/predict_flows.py --plan <plan.json> --maps <map root> [--maps ...] > predictions.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "harness"))
from westlake_gap.gapmap import HARD_GAPS  # noqa: E402


def matches(row_id: str, contract: str) -> bool:
    return row_id.startswith(contract[:-1]) if contract.endswith("*") else row_id == contract


def predict(flow: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    """The flow's prediction from its app's rows."""
    read: dict[str, str] = {}
    hard = False
    undescribed = []
    for contract in flow["rows"]:
        found = [r for r in rows if matches(r["id"], contract)]
        if not found:
            undescribed.append(contract)
        for row in found:
            measured = row.get("measured")
            read[row["id"]] = row["verdict"] + (f", measured {measured}" if measured else "")
            hard |= row["verdict"] in HARD_GAPS
    return {"outcome": "fails" if hard else "works", "rows": read, "no_row": undescribed}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--maps", action="append", type=Path, required=True, help="gap-map root: <root>/<app>/gap-map.json")
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    out = []
    for flow in plan["flows"]:
        gap = next((root / flow["app"] / "gap-map.json" for root in args.maps
                    if (root / flow["app"] / "gap-map.json").exists()), None)
        if gap is None:
            raise SystemExit(f"{flow['id']}: no gap map for {flow['app']}")
        gap_map = json.loads(gap.read_text())
        out.append({**{k: flow[k] for k in ("id", "app", "intent", "works_when")},
                    "westlake_commit": gap_map["provider"]["westlake"].get("commit"),
                    "prediction": predict(flow, gap_map["rows"])})
    json.dump({"rule": "fails when a matching row's verdict is in gapmap.HARD_GAPS", "flows": out}, sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
