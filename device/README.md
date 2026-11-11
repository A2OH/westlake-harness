# device/ — launch apps on the OpenHarmony board and score them

These scripts drive a device round: stage each app's original APK, launch it through Westlake on the board,
wait until it is on screen (or gone), capture the evidence `westlake_gap.lifecycle` and `.evidence` score,
and clean up so a round of a thousand apps fits on both disks. The `play/` scripts run the same round with
every app connected to **one shared Play services process**, the way GrapheneOS runs Play services as an
ordinary unprivileged app, and compare it with microG in each app.

Nothing machine-specific is in the repo: settings come from `env.sh` (copy `env.sample.sh`); each script
stops with the name of any setting it needs and lacks. `config.sh` lists them. No APK is in this repo:
apps, and Google's Play services for `play/`, come from your own corpus directory (`$WL_CORPUS/dl`).

## Files

| Script | Does |
|---|---|
| `config.sh` | settings, hdc helpers (`hdc_heal` restarts a hung local hdc server), `kill_children` |
| `launch.sh <app> <out>` | one launch through the launcher; disk guard (exit 3), link gate, reconnect retries |
| `run_apps.sh <tag> <app...>` | launch, wait, capture: stderr, screenshot, process map, hilog, crash dump, run-time native libraries |
| `screen_ok.py` | the scorer's host-screen check on one screenshot, for the early exit |
| `prep_apps.py <pkg...>` | unpack, verify signatures (one certificate across splits), pin, stage |
| `round.sh <tag> <first> <last>` | the round over `apps.csv`, five apps at a time, next batch staged ahead; resumable |
| `prefetch_board.py <pkg...>` | send staged files into the board's input cache ahead (`PUSH_AHEAD=1`) |
| `harvest_manifest.py` | describe the run-time libraries harvest for `scan --unpacked-libs` |
| `explore.py oh\|android` | Level 2: use a running app like a curious user (unvisited views, scrolls, a tap grid for WebView/Compose/game surfaces, Back), same loop on the board and on a phone |
| `android_round.sh <tag> <pkg...>` | Level 2 on the Android reference phone: install the same download, explore, keep the crash log, uninstall |
| `compare_explore.py <W tag> <A tag>` | per app: died / blank / shallow / close / both-died |
| `tells.py <tag>...` | what the runtime told about each app and how each app ended (Java exit, self-signal, uncaught, Back, crash, dump timed out, silent), with the candidate cause; `analysis/RUNTIME-TELLS.md` step T0 |
| `play/start_play.sh` | start the shared Play services process (no activity) and watch it up to 24 h |
| `play/client.sh <tag> <pkg>` | one app beside it |
| `play/shared_round.sh <tag>` | a round with every app connected to it; stops at once if it dies |
| `play/run_all.sh <tag>` | `shared_round.sh` with resume, for day-long runs; probes the board's network at the start and end (`NETPROBE=0` skips) |
| `netprobe.sh <out.json>` | the board's network for the names in `netprobe/names.txt`, through the resolver apps use: lookup, TCP connect to 443, TLS hello with SNI, beside Google's DNS-over-HTTPS answers on the host |
| `play/score_play.py <tag> [<microG tag>]` | rungs, connection status, error replies, missing services, token counts |

## Level 2

`EXPLORE=180 round.sh <tag> ...` explores each app on the board for 3 minutes after it is on screen,
before the usual evidence is taken; `android_round.sh` does the same on a phone, and `compare_explore.py`
sets the two side by side. Screens are told apart by the views on them, so the comparison is a lead to
look at with the step screenshots, not a verdict on its own. The explorer never taps views whose text
looks like paying, deleting, signing out or reporting, and never types.

## Timing

A launch waits up to `WAIT` seconds but moves on once, at least `MINWAIT` (20) seconds in, the app's log
shows it drawing **and** two screenshots in a row read as the app — or at once when its process is gone.
On a fixed 60 s wait, ~64% of each launch was the app sitting idle; with the early exit, a launch of an
app whose files the board already has takes ~45–65 s. Over the board's wireless link (~4 MB/s) a new
app's files dominate; a USB link removes most of that.

## Lessons kept in the scripts

- A hung local hdc server still lists the board but times out every shell call; restart it (`hdc_heal`).
  A large file send beside a launch's own transfers caused it, so `PUSH_AHEAD` is off by default.
- The first relayout in the log comes ~10 s before the screen shows anything; a screenshot check is needed.
- Leaving before ~20 s misses apps that crash after their first screen.
- The board keeps every child's stderr and every app stage unless removed; both once filled `/data`.
- Crash dumps: pids repeat, so only a dump newer than the launch mark is the app's own.
