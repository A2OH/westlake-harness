# Batch 8: mechanical predictions

RethinkDNS, Jami, FFUpdater, Suntimes, Linux Command Library, Scrambled Exif, Tomato, WiFiAnalyzer,
GPS Cockpit and Red Moon ([downloads.lock.json](downloads.lock.json)).

Provider: framework 49 (Westlake working tree after batch 7's fixes; native runtime opengl6,
bionic shim nw8).

## Predictions

[predictions.json](predictions.json), committed before any launch:

- **Rule: 9 of 10 draw.** Jami is flagged: run-time lookups of libaaudio and libmediandk, the
  libc ABI, and the NDK audio weld.
- **Calibrated: about 6.** Batch 7 drew 5 of 10 on first launch, down from 9: newer apps keep
  finding services nobody asked for before.

## Results

One launch per app on framework 49. **4 of 10 drew on first launch**: Linux Command Library,
Tomato, Red Moon and Suntimes. No fix this batch unblocked another, so it stays at 4.

| App | Rule | Outcome | Blocker |
|---|---|---|---|
| FFUpdater | draws | **blocked** | AppCompat rejects its theme (`main_activity__theme` → Theme.Material3.DayNight.NoActionBar) |
| Jami | blocked | **blocked** | the same AppCompat theme rejection, before its flagged native gaps are reached |
| WiFiAnalyzer | draws | **blocked** | inflating a settings view fails on a theme attribute (the same family as VLC) |
| GPS Cockpit | draws | **blocked** | a null in `onResume`, likely `LocationManager.getBestProvider`: a legitimate answer with no location providers |
| RethinkDNS | draws | **blocked** | stops after bind with no error logged (open) |
| Scrambled Exif | draws | **blocked** | its app name is null. The launch path zeroes `labelRes` on purpose, an early bring-up workaround, which is also why Catima's title shows its class name (open) |

- **Rule: 5 of 10 right** (the four that drew, and Jami).
- **The theme gap is now the top repeated blocker:** Seal, FFUpdater and Jami die in AppCompat,
  and VLC and WiFiAnalyzer die on unresolved theme attributes. The launch now uses each
  manifest's declared theme (westlake `1baca65`), which is right but not sufficient. The declared
  themes' attributes do not resolve through their parent styles on this runtime. Fixing that is
  a resource-system investigation, not another service answer.
