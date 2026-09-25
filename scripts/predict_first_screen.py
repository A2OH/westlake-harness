#!/usr/bin/env python3
"""Predict, from gap maps alone, whether each app draws its first screen.

A fixed rule, so a prediction is reproducible and no reading of the code can tilt it. An app is
predicted blocked when its map has any of:

  native     a strong native import neither OpenHarmony nor the runtime supplies
             (ndk:* missing, not a library the APK itself fails to ship)
  framework  a hollow service whose null answer AOSP's own manager unwraps, for a method the app calls
  lookup     an NDK library the app resolves entry points from at run time that the runtime does not
             supply: libandroid, libnativewindow, libmediandk, libaaudio (Flutter's raster thread,
             Gecko)
  engine     a first screen drawn by an engine into its own SurfaceView (window:engine-surface):
             libGDX, Arc, Flutter, SDL, Unity, Godot, a NativeActivity. Added after batch 4: on the
             41 apps then known, it flagged 5, all blocked, and no app that drew.

Otherwise it is predicted to draw. Each prediction lists the rows that decided it.

The signals were chosen on the 31 apps of the loop and corpora 2 and 3, against their first-screen
outcomes (scripts' input: outcomes.json). Per signal, apps flagged that were blocked / that drew:
class-init natives of android.media classes 7/20, WebView renderer process 3/15, Camera 4/3 --
too common among apps that draw to predict anything; runtime lookups of libandroid 4/1,
libnativewindow 3/1, libmediandk 2/0; unresolved native imports 1/0. On those 31 (in sample) the
rule scores accuracy 0.81, precision 0.83, recall 0.50. The blockers it misses are one missing
Android behaviour each (a null service, a PackageManager answer, a settings value) that no row
ranks as reachable at startup.

Usage: predict_first_screen.py <map-root> <app> [<app> ...] > predictions.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Rule v2, fitted on all 101 apps of the loop at framework 57 (so in sample; the next batch is
# its test). Dropped from v1 because they fired mostly on apps that draw:
#   bionic libc imports (ndk:libc-abi)          1 blocked, 7 drew
#   audio/media run-time lookups and welds       reached only when playing media: 2 blocked, 5 drew
# Kept: the libandroid/libnativewindow lookups Flutter's and VLC's renderers make (4 blocked,
# 2 drew), the non-media NDK packages and welds, and the engine surface (7 blocked, 1 drew).
LOOKUPS = {f"sym:runtime-resolved:{lib}" for lib in ("libandroid.so", "libnativewindow.so")}
LAZY_NDK = ("ndk:libc-abi", "ndk:weld:audio", "ndk:weld:media")


def reasons(rows: list[dict]) -> list[str]:
    found = []
    for row in rows:
        rid = row["id"]
        if (rid.startswith("ndk:") and row["verdict"] == "missing" and "unshipped-library" not in rid
                and not rid.startswith(LAZY_NDK)):
            found.append(f"native:{rid}")
        if row.get("throws_in_framework"):
            found.append(f"framework:{rid}")
        if rid in LOOKUPS:
            found.append(f"lookup:{rid}")
        if rid == "window:engine-surface":
            found.append(f"engine:{rid}")
    return sorted(set(found))


def main() -> int:
    root = Path(sys.argv[1])
    out = {}
    for app in sys.argv[2:]:
        rows = json.loads((root / app / "gap-map.json").read_text())["rows"]
        why = reasons(rows)
        out[app] = {"expected": "blocked" if why else "draws", "because": why}
    json.dump(out, sys.stdout, indent=1)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
