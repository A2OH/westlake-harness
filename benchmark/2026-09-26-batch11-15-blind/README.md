# Batches 11–15: 100 new F-Droid apps, predicted blind (framework 59)

Written before any of these apps was launched. The outcomes are added afterwards; the
predictions here are not edited.

## Selection

The rule was fixed before looking at individual apps. The source is the F-Droid index
(2026-09-23). Eligible apps:

- were updated within the last 12 months;
- target SDK 30 or later;
- are at most 80 MB;
- ship arm64 native code or none;
- were not among the 101 apps already tried.

That left 2,168 apps in 113 categories. The pick is one app per category in turn; within a
category, the app with the most published versions (a proxy for a maintained app) comes first.
The first 100 downloads all verified against the index's sha256. `apps.json` has the package,
version, category, sha256 and batch of each.

## Prediction

`scripts/predict_first_screen.py` (rule v2 plus the libnativehelper lookup) runs on the static gap
maps. No Android startup traces this time: the phone was not attached. So the runtime-data rows,
which count only on a traced path, do not contribute.

- **37 of 100 predicted blocked.**
- Reasons: 54 apps flag a runtime `libandroid`/`libnativewindow`/`libnativehelper` lookup, 30 an
  engine-drawn SurfaceView, and 14 an unresolved NDK import. Several apps flag more than one.
- The batch holds many more Flutter apps than the first 101, and each of them flags both the
  engine surface and the `libandroid` lookup.
- `stopwatch` declares no launchable activity and cannot be launched through the direct-launch
  path; it is recorded as such, not dropped.

`predictions.json` gives each app's expected result and the rows that decided it.
