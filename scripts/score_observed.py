#!/usr/bin/env python3
"""How much a real-Android startup trace sharpens the gap map as a first-screen predictor.

Each app's map is re-made with `gap-map --observed` from an ART method trace of its cold start on
an Android phone; every row then says whether the app reached it (`observed.on_path`). This scores
each check family and the fixed predictor twice against the board outcomes: on all rows (static),
and on only the rows the trace put on the startup path (observed). A family that loses its false
alarms without losing its blocked apps was flagging code nobody runs at startup.

Usage: score_observed.py <map-obs-root> <benchmark-dir>
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from predict_first_screen import reasons  # noqa: E402
from score_checks import families  # noqa: E402


def on_path(rows: list[dict]) -> list[dict]:
    return [r for r in rows if r.get("observed", {}).get("on_path")]


def score(pred: dict[str, bool], truth: dict[str, bool]) -> str:
    tp = sum(pred[a] and truth[a] for a in pred)
    fp = sum(pred[a] and not truth[a] for a in pred)
    fn = sum(not pred[a] and truth[a] for a in pred)
    acc = sum(pred[a] == truth[a] for a in pred) / max(1, len(pred))
    return f"accuracy {acc:.2f}, precision {tp / max(1, tp + fp):.2f}, recall {tp / max(1, tp + fn):.2f} (tp {tp}, fp {fp}, fn {fn})"


def main() -> int:
    maps, bench = Path(sys.argv[1]), Path(sys.argv[2])
    outcomes = json.loads((bench / "loop-outcomes.json").read_text())["apps"]
    truth, static_pred, observed_pred = {}, {}, {}
    hits: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: {v: {"blocked": 0, "drew": 0} for v in ("static", "observed")})
    for app, o in sorted(outcomes.items()):
        path = maps / app / "gap-map.json"
        if not path.exists():
            continue
        rows = json.loads(path.read_text())["rows"]
        state = "blocked" if o["after"] == "blocked" else "drew"
        truth[app] = state == "blocked"
        for view, subset in (("static", rows), ("observed", on_path(rows))):
            for family in families(subset):
                hits[family][view][state] += 1
        static_pred[app] = bool(reasons([{k: v for k, v in r.items() if k != "observed"} for r in rows]))
        observed_pred[app] = bool(reasons(on_path(rows)))

    blocked = sum(truth.values())
    print(f"{len(truth)} apps with a traced map: {blocked} blocked, {len(truth) - blocked} drawing\n")
    print(f"{'check':52} {'static b/d':>11} {'prec':>5} {'observed b/d':>13} {'prec':>5}")
    for family, h in sorted(hits.items(), key=lambda kv: -kv[1]["static"]["blocked"]):
        s, ob = h["static"], h["observed"]
        print(f"{family:52} {s['blocked']:5d}/{s['drew']:<5d} {s['blocked'] / max(1, s['blocked'] + s['drew']):5.2f}"
              f" {ob['blocked']:6d}/{ob['drew']:<6d} {ob['blocked'] / max(1, ob['blocked'] + ob['drew']):5.2f}")
    print(f"\npredictor v2, static:   {score(static_pred, truth)}")
    print(f"predictor v2, observed: {score(observed_pred, truth)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
