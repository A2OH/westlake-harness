# Rerun of all 101 apps (framework 57)

## Harness updates

- **`load:needed-missing`**: a library an APK library lists in DT_NEEDED that neither the APK, the
  Westlake runtime nor the board provides. It flags 6 apps, all real gaps: Fennec and SuperTuxKart
  load theirs at startup and are blocked; mpv and Jami load theirs only for playback or calls;
  Element's importer is never loaded; Seal's are helper executables.
- **`scripts/score_checks.py`** scores each check as a startup-blocker detector against what the
  board shows, and lists which open ledger blockers a row names.
- **Predictor rule v2** drops bionic-libc imports and audio/media lookups, which fired mostly on
  apps that draw.

## Per-check scores

Fresh scans of all 101 apps against framework 57. There are 24 apps blocked and 77 drawing.
[check-scores.txt](check-scores.txt) has the full table.

| Check | Blocked | Drew | Precision | Recall |
|---|---|---|---|---|
| engine draws into its own SurfaceView | 7 | 1 | 0.88 | 0.29 |
| NDK name looked up at run time | 6 | 5 | 0.55 | 0.25 |
| DT_NEEDED library nobody provides | 2 | 4 | 0.33 | 0.08 |
| any null/hollow/strict service | 23 | 75 | 0.23 | 0.96 |
| any unregistered framework native | 22 | 70 | 0.24 | 0.92 |
| WebView renderer process | 8 | 31 | 0.21 | 0.33 |

Only the engine check is a precise startup signal. The broad checks list real gaps, but flag
about three drawing apps for every blocked one: the harness cannot yet tell which gaps startup
reaches. Of the 24 open ledger blockers, **10 are named by a row** in the app's current map.

## Predictor

On all 101 apps (in sample): v1 had accuracy 0.75, precision 0.47, recall 0.38. **v2 has accuracy
0.81, precision 0.69, recall 0.38.** Recall is capped by blockers no row names.

## Launch repeatability

20 apps were launched again on framework 57, 33 extra launches in all. A full board `/data`
killed the second round after 13 apps. Nineteen of the 20 gave the same result on every launch.
The one that changed is **Material Files**: when `inotify_add_watch` succeeds, its own
WatchService poller thread crashes (SIGSEGV at address 0). When SELinux denies the watch, it
draws. It crashed in 3 of 4 launches.

So a single launch is reliable for about 95% of apps. An app that fails intermittently needs
several launches before its result means anything.

## Operational finding

Every framework deploy stages about 1.5 GB under `/data/local/tmp`, and nothing removed the old
stages. 24 of them filled the board's `/data`, which killed the rerun and stopped the board
writing crash reports. `build.sh` now keeps only the current and previous stages.
