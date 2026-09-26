# 101 Android apps on OpenHarmony: the launch–fix–rescan loop

The goal was to keep one loop running until 100 APKs had been tried. Each batch went:

1. Map every app with the harness.
2. Predict, then commit the predictions before any launch.
3. Launch on the OH board and score each app from its screenshot.
4. Fix what blocks the apps in Westlake.
5. Change the harness wherever it missed.
6. Rescan.

Every app is an original arm64 APK. Batches 2 onward came from the F-Droid main repository, with
each hash checked against the index. The board ran OpenHarmony 6.1.0.31 (arm64) under SELinux
enforcing.

## Result

`scripts/loop_report.py benchmark` reads [loop-outcomes.json](loop-outcomes.json), each batch's
`predictions.json` and the [blockers ledger](blockers-ledger.json):

```
batch      apps  first  after  rule ok
loop-1       11      2      8        -
corpus-2     10      2      6        -
corpus-3     10      2      7        -
batch-4      10      7      8     6/10
batch-5      10      8      8     8/10
batch-6      10      9     10     9/10
batch-7      10      5      9     5/10
batch-8      10      4      6     5/10
batch-9      10      3      6     5/10
batch-10     10      7      9     8/10
all         101     49     77 46/ 70

ledger: 66 blockers, 25 named by a gap-map row, 41 fixed
```

- **77 of 101 draw a first screen** on the current provider (Westlake `corpus2-fixes`, framework
  57). On their first launch, 49 of 101 drew.
- **Fixes carried over to apps nobody had looked at.** Corpora 2 and 3 drew 2 of 10 each on first
  launch. Batches 4 to 6, launched after those fixes, drew 7, 8 and 9. First-launch rates dipped
  again in batches 7 to 9, when new gaps appeared (heavier apps, a theme defect); batch 10 drew 7.
- **The mechanical rule was right for 46 of 70** first launches it predicted (batches 4 to 10).
  Every hand-made blind prediction before it (Burger King, corpora 2 and 3) was optimistic.

## What was fixed in Westlake

Grouped by kind, with the apps each fix first unblocked:

| Kind | Fixes |
|---|---|
| Null system services dereferenced inside AOSP managers | notification, jobscheduler (empty lists), appwidget, deviceidle, search, domain_verification, role, wallpaper, wifi, media_router, trust, uri_grants |
| PackageManager answers | getPackageInstaller, queryIntentServices/resolveService from manifest filters, resolveContentProvider by authority |
| Activity manager in process | PendingIntents (LocalIntentSenders), bindService of own services, startActivity off the main thread posted to it |
| Launch fidelity | launcher intent (`ACTION_MAIN`/`CATEGORY_LAUNCHER`), activity theme from the manifest, activity-theme styling for apps with no or conflicting application themes |
| Unbound framework and libcore natives | EGL14/EGL15/EGLExt, audio-effect library (AudioEffect, Visualizer), `VM.getNanoTimeAdjustment` (a `@CriticalNative`), `ProcessEnvironment.environ` |
| Values Android never leaves unset | `Settings.Secure.ANDROID_ID`, private internal storage volume, `WifiDisplayStatus` |
| Native ABI | OpenSL ES translated between Android's 32-bit and OH's 64-bit `SLuint32` |

## What the harness learned

Each change came with a known-answer test and a backtest:

- **Fat APKs** are resolved for the target ABI only. **Launcher aliases** resolve to their
  target activity. **Non-UTF-8 tool output** no longer aborts a scan.
- **`throws_in_framework`**: a hollow service whose null answer an AOSP manager unwraps. The
  model knows when the provider answers empty lists.
- **Framework natives**: platform classes whose natives no deployed library registers (it caught
  EGL14 by its class initializer). These rows mark gaps, not startup blockers: most media classes
  are never reached before a first screen.
- **`window:engine-surface`**: first screens an engine draws into its own SurfaceView (libGDX,
  Arc, Flutter, SDL, a NativeActivity). It flagged 5 known apps, all blocked; its first blind
  case (Unciv) was right; it also flagged SuperTuxKart, which was blocked.
- **The blockers ledger** records every startup blocker observed, with the row that names it. A
  row that blocked one app is marked in every later map.
- **A mechanical predictor** (`scripts/predict_first_screen.py`) uses only the signals that
  separated drawing from blocked apps.
- **The screenshot decides.** The lifecycle scorer compares each screenshot with the host
  screen. Apps that drew and then left had been scored "drawing".

## What stays open

- **SurfaceView gets the activity's OH window** (PPSSPP, Mindustry, Shattered Pixel Dungeon,
  Unciv, SuperTuxKart): a window-system change, L.
- **Flutter's raster thread calls a null function** (FluffyChat, Obtainium): an NDK name resolved
  at run time, not yet identified.
- **Libraries OH does not ship**: `libmediandk` (Fennec), `libGLESv1_CM` (SuperTuxKart).
- **The launch path zeroes `labelRes`** on purpose (an early bring-up workaround), so apps read
  their own name as null (Scrambled Exif) and some titles show class names (Catima).
- **Where the application theme overrides the activity's** is worked around, not located.
- **Unexplained failures** (VLC and WiFiAnalyzer theme attributes, Breezy Weather, Nextcloud's
  splash, RethinkDNS, DuckDuckGo's time zones, Element X and StreetComplete native crashes, GPS
  Cockpit, LibreTube's cache size, Fossify Voice Recorder's window session) are in the ledger.
- **Two OS walls:** OH's app-data policy denies symlinks (Termux, Seal), and OpenCamera needs
  the camera natives.
- **One app is unstable across launches:** OsmAnd drew once, and now leaves after drawing on every
  build tried. Material Files crashed inside ART once in the final regression and drew on relaunch.
  Every app was launched once per build, so single results carry that uncertainty.
