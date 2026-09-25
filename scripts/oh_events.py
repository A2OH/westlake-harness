#!/usr/bin/env python3
"""Structured events for every launch log in a directory.

Usage: oh_events.py <log-dir> <out-dir>
Writes <out-dir>/<app>.events.json (ordered events plus a summary) for each <app>.stderr, and
<out-dir>/summary.json with one line per app: services it got null, natives missing, the root
cause of its first failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))
from westlake_gap import ohevents  # noqa: E402


def main() -> int:
    logs, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    summary = {}
    for path in sorted(logs.glob("*.stderr")):
        result = ohevents.parse_file(path)
        (out / f"{path.stem}.events.json").write_text(json.dumps(result, indent=1) + "\n")
        summary[path.stem] = result["summary"]
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    for app, s in summary.items():
        rc = s["root_cause"] or {}
        print(f"{app:16} events={s['event_count']:3} null={len(s['services_null']):2} "
              f"missing-natives={len(s['natives_missing'])} root={rc.get('error') or rc.get('name') or '-'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
