#!/usr/bin/env python3
"""compare_explore.py <westlake-tag> <android-tag>  -- compare Level 2 explorations app by app.

Reads $WL_SC/inputs/logs/<westlake-tag>/hk-<package>.explore/explore.json (run_apps.sh EXPLORE=) and
<android-tag>/<package>.explore/explore.json (android_round.sh). For each package explored on both:

  died      Westlake's process ended during exploration and Android's did not
  closed    it ended right after Back on the app's last screen: Westlake ends the process, Android
            keeps it cached; the app closed on both. A crash while handling Back looks the same,
            and the exit itself can be unclean (two apps' GPU driver thread aborted during it), so
            read tells.py's end for the app before calling it clean
  blank     Westlake's view dumps came back empty for most steps (nothing to use)
  shallow   Westlake reached under half of the screens Android reached
  close     half or more of Android's screens (more is possible: different content or layouts)
  both-died the app also ended on Android (an app or environment problem, not Westlake's)

Prints the counts and a table, and writes <westlake-tag>-vs-<android-tag>.json beside the logs.
Screens are counted by the views on them, not by pixels, so they compare like for like only roughly:
read 'shallow' as a lead to look at, with the step screenshots, not a verdict on its own."""
import json
import os
import sys
from collections import Counter
from pathlib import Path


def load(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def verdict(w: dict, a: dict) -> str:
    if a.get("died_at") is not None and w.get("died_at") is not None:
        return "both-died"
    if w.get("died_at") is not None:
        return "closed" if w.get("died_after") == "back" else "died"
    if w["steps"] and w["empty_dumps"] > 0.6 * w["steps"]:
        return "blank"
    if w["screens"] * 2 < a["screens"]:
        return "shallow"
    return "close"


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 64
    logs = Path(os.environ["WL_SC"]) / "inputs" / "logs"
    wt, at = sys.argv[1], sys.argv[2]
    rows = []
    for d in sorted((logs / at).glob("*.explore")):
        pkg = d.name[: -len(".explore")]
        a = load(d / "explore.json")
        w = load(logs / wt / f"hk-{pkg}.explore" / "explore.json")
        if not a or not w:
            continue
        rows.append({"package": pkg, "verdict": verdict(w, a),
                     "westlake": {k: w.get(k) for k in ("screens", "taps", "died_at", "empty_dumps", "steps")},
                     "android": {k: a.get(k) for k in ("screens", "taps", "died_at", "empty_dumps", "steps")}})
    counts = Counter(r["verdict"] for r in rows)
    print(f"{len(rows)} apps explored on both:", dict(counts.most_common()))
    print(f"{'package':45} {'verdict':9} {'screens W/A':>11} {'died W/A':>15}")
    for r in sorted(rows, key=lambda r: (r["verdict"], r["package"])):
        w, a = r["westlake"], r["android"]
        print(f"{r['package'][:45]:45} {r['verdict']:9} {w['screens']:>5}/{a['screens']:<5} "
              f"{str(w['died_at']):>7}/{str(a['died_at']):<7}")
    (logs / f"{wt}-vs-{at}.json").write_text(json.dumps({"counts": counts, "apps": rows}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
