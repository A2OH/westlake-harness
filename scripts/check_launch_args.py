#!/usr/bin/env python3
"""Check every gap map's launch args against what the launcher will accept.

The launcher (manifest tools/probe_source_app.py) refuses an Android-namespace target that is not one
of the app's pinned native libraries, by file name, and then never starts the app. A map that names
a library any other way (TikTok's maps once used the SONAME libeffect.so for libeffect_plugin.so)
silently drops that app from every run. This compares each map's launch_args with the app's pinned
inputs and exits non-zero when any target would be refused.

Usage: check_launch_args.py --app-inputs <dir of prep-<app>/app-input.json> <map-root> [<map-root> ...]
"""
import argparse
import json
from pathlib import Path

LIBRARY_FLAGS = ("--android-native-target", "--android-native-net-target")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--app-inputs", required=True, type=Path,
                        help="directory holding prep-<app>/app-input.json for each app")
    parser.add_argument("roots", nargs="+", type=Path)
    args = parser.parse_args()
    checked, problems, unpinned = 0, {}, []
    for root in args.roots:
        for gap_path in sorted(root.glob("*/gap-map.json")):
            app = gap_path.parent.name
            launch = json.loads(gap_path.read_text()).get("launch_args", [])
            targets = [v for f, v in zip(launch[0::2], launch[1::2]) if f in LIBRARY_FLAGS]
            if not targets:
                continue
            app_input = args.app_inputs / ("prep-" + app) / "app-input.json"
            if not app_input.exists():
                unpinned.append(app)
                continue
            pinned = {Path(name).name for name in json.loads(app_input.read_text())["native_libraries"]}
            checked += 1
            refused = sorted({t for t in targets if t not in pinned})
            if refused:
                problems[app] = refused
    print(f"{checked} maps with library launch targets checked; {len(problems)} would be refused")
    for app, refused in sorted(problems.items()):
        print(f"  {app}: {' '.join(refused)}")
    if unpinned:
        print(f"  (no pinned inputs for {len(unpinned)}: {' '.join(unpinned[:10])})")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
