# Batch 7: mechanical predictions

Seal, Home Assistant (minimal), Trail Sense, Chrono, Noice, Retro Music, RadioDroid, Kore, openHAB
and AndStatus ([downloads.lock.json](downloads.lock.json)).

Provider: Westlake `corpus2-fixes` at `e2524b1`, framework 47 (native runtime opengl6 with the
audio-effect library, bionic shim nw8).

## Predictions

[predictions.json](predictions.json), from `scripts/predict_first_screen.py`, committed before any
launch:

- **Rule: 8 of 10 draw.** Seal is flagged for an NDK run-time lookup (`libandroid`) and a bionic
  libc import. Home Assistant is flagged for unresolved native imports (libc ABI and an NDK
  package symbol).
- **Calibrated: about 8 to 9.** Batch 6 drew 9 of 10 on first launch.

## Results

One launch per app on framework 47. **5 of 10 drew on first launch**: Home Assistant, Trail
Sense, Chrono, Noice and Kore. After fixes (framework 49), Retro Music, openHAB and RadioDroid drew too:
**8 of 10**.

| App | Rule | Outcome | Blocker |
|---|---|---|---|
| Seal | blocked | **blocked** | AppCompat rejects its theme. Two faults: the activity's own theme was missing from direct launch's ActivityInfo (fixed), and the theme's attributes still do not resolve through its parent styles. VLC shows the same resource-system gap (open) |
| Home Assistant | blocked | draws | the flagged native imports are not reached at startup |
| Retro Music | draws | **blocked**, then draws | `WallpaperManager` had no service (fixed) |
| RadioDroid | draws | **blocked**, then draws | `getWifiDisplayStatus()` null, then `IMediaRouterService` null (both fixed; it draws on framework 49) |
| openHAB | draws | **blocked**, then draws | a Kotlin non-null cast of a null `WifiManager` (fixed) |
| AndStatus | draws | **blocked** | it started its first activity from a worker thread, and direct launch built it off the main looper (fixed, as for Fennec); it now draws, then exits with no error (open) |

- **Rule: 5 of 10 right.** The calibrated forecast (8 to 9) was too optimistic this time.
- **Two blockers had rows the predictor ignores:** openHAB's `svc:wifi` (a Kotlin non-null
  cast, which misfired on apps that drew earlier) and Seal's.
- **Repeated gaps this batch closed:** starting an activity off the main thread (AndStatus,
  Fennec) and a per-activity theme or label (Seal, and Catima's class-name title).
