# r88: routing by default, the time zone, and per-thread lookups (2026-10-07)

r88 reran the whole corpus (329 apps) on the provider that the tests after r87 had cleared:
- **Build 96:** build 95, plus the default time zone. The child's common init now installs the
  supplier Android's `RuntimeInit.commonInit` installs, which reads `persist.sys.timezone` and
  falls back to OH's `persist.time.timezone`. Before, every app's clock and calendar showed UTC.
- **The shim:** `getpwnam`, `getpwuid`, `getgrnam` and `getgrgid` keep a result per thread for
  Android code, as Bionic does. musl keeps one result and one line buffer for all threads.
- **The gap maps:** made with today's harness against this provider. Their launch args are the
  ones r87 ran with, plus the routing of the libraries exposed to the runtime's exports
  (`load:interposed-by-runtime`) in 129 apps. They differ in nothing else.
- **The host application:** version 4, whose page is empty and black.
- Host-compiled code for the same eleven apps, against build 96's boot image, and the input cache.

This record covers what r88 found against r87, what still stops the apps short of drawing, the
tests made after r87 that cleared these changes, and the harness changes since the r87 record.

Files, made with today's harness:
- `r88-lifecycle.json`: r88 classified
  (`python -m harness.westlake_gap.lifecycle <logs> --json r88-lifecycle.json`).
- `r88-score.json`: its first blockers scored against gap maps made with today's harness, against
  r88's own provider (`scripts/score_first_blockers.py`).

## Regression check against r87

- **Coverage:** all 329 apps ran.
- **Drawing:** 317 (r87: 316).
- **Up:** 3 apps.

  | app | what moved it |
  |---|---|
  | PPSSPP | the routing: its JNI library no longer binds its own calls to libhwui's copies, and it draws its welcome screen (r87: SIGSEGV in libhwui) |
  | supertuxkart | the routing: `libmain.so` and `libSDL2.so` load in the Android namespace, and it draws its first-run controls dialog over its menu (r87: SIGSEGV in musl's `setjmp`) |
  | clauncher | the host's black page: its clock and hints, drawn in white in a transparent window, now show (over the light page they read as the host screen). The wallpaper Android would draw behind them is still missing |

- **Back:** 2 apps.
  - **Guardian:** a timing race, not a regression. Its screenshot was black, with its main thread
    in `HardwareRenderer.nPause`: Guardian pauses and re-resumes its home about 50 s after start,
    and the screenshot (at 45 s) fell inside that cycle. Its activity sequence matched r87's
    step for step. Relaunched three times on r88's provider, it drew every time.
  - **spacebeam:** a stop the black page exposed, not a regression. Its screen has been pure
    black in every round since r77, and over the light page that counted as drawing. It draws
    through a GLSurfaceView in an OH window of its own; its GL thread swaps frames, and nothing
    shows. Two relaunches on r88's provider gave the same. Open (below).
- **The changes' own apps:** all draw as in r87.
  - The two Chaquopy apps (econverter, werewolvesgame), left unrouted.
  - Material Files.
  - Zoom, Duolingo, TikTok, CapCut, and the Meta apps (Instagram, Threads, Facebook, Messenger).
  - The clocks and calendars, now on the board's time zone.
- **aaaaxy:** it draws its game on screen. Its log stops at bind (its Go runtime writes to
  hilog), and its hilog this time carried neither the adapter's first frame nor its timeout. The
  lifecycle now counts an app whose screenshot shows its content, with nothing stopping it, as
  drawing (below).

## Start-up

- **First frame:** 259 of the 317 apps that draw report a drawn first frame.
  - Median 1.73 s from process start (r87: 1.76 s). 169 drew within 2 s (155), 250 within 5 s
    (243).
  - Six took over 10 s, as in r87: Waze (57.5 s), TikTok (27.1 s), msstart (11.3 s), Instagram
    (10.8 s), Moovit (10.4 s) and Transit (10.1 s).
- **Against r87, apps that drew in both:**
  - 245 apps with a first frame in both: median 1.75 s, then 1.73 s;
  - 304 apps that logged a resume in both: median 0.93 s, then 0.90 s.
- **Host-compiled apps:** within a few tenths of a second of r87. CapCut now logs its resume
  (6.0 s).

## What stopped the 12 apps short of drawing

| app | stop | cause |
|---|---|---|
| cclauncher | idle, host screen | a transparent `windowShowWallpaper` window with nothing visible in it, as in r87 (`wm:show-wallpaper`) |
| spacebeam | drawing frames, black screen | its GLSurfaceView's own OH window shows nothing: a default SurfaceView sits behind its activity's window, and the bridge also creates a "Background for SurfaceView" layer; one of the two covers the frames. Black since r77; the map's `window:engine-surface` reads as supplied; open |
| Guardian | screenshot during its pause/resume | timing (above) |
| Reddit | resumed, no frame | its splash waits on its own servers, which the board's network does not reliably reach |
| Fossify Messages | finished itself | no SMS role on a board without telephony: a device's answer |
| opflashcontrol | slider out of range | a flashlight app on a board with no camera exposed to Android: a device's answer |
| Shortcut | finished itself | it hands its intent to an app that is not installed |
| facebooknotifica | InflateException | its preference XML names a class its bundled androidx lacks; Android fails the same way |
| NYTimes, Flipboard | Google Play services | out of scope |
| insigno | Mali's backend thread aborts | at bind, as Flutter's Vulkan backend imports a native buffer; open |
| OsmAnd | an abort on a Qt pool thread | its first start copies its bundled data while the map engine starts; open |

## Scoring

r88's first blockers were scored against gap maps made with today's harness, against r88's own
provider:
- **Scorable:** 4 of 12.
  - **Named:** cclauncher, by `wm:show-wallpaper`.
  - **A device's answer:** Fossify Messages.
  - **Marked supplied:** Reddit. `am:post-create` is supplied, and its stop is its network.
  - **Not named:** Shortcut.
- **The 8 unscorable:**
  - app exceptions with no platform symbol: facebooknotifica, NYTimes, Flipboard and opflashcontrol;
  - crashes in code no row names: insigno in Mali, OsmAnd in libc++;
  - stalls no row names: Guardian (timing) and spacebeam. A SurfaceView whose own window shows
    nothing is a gap that no row reads yet.

r87's three named stops, a round later:
- clauncher and PPSSPP draw;
- cclauncher is named by the same row.

## Tests after r87

| test | change | what it showed | apps that moved back |
|---|---|---|---|
| the routing pilot (12 apps, build 95) | the gap maps' interposition rows routed by launch args | all 12 draw, PPSSPP and supertuxkart among them; start-up as in r87 | none |
| the routing A/B (131 apps, build 95) | the same, for every corpus app with libraries exposed to the runtime's exports, against r87 unrouted | up: PPSSPP and supertuxkart. Back: the two Chaquopy apps, whose written modules then load in the Android namespace beside a second, uninitialized libpython (since then, such apps are not routed); Material Files and Zoom, on intermittent faults they meet unrouted too (Material Files' heap corruption under `getgrgid`, below; Zoom's dump-helper timeout, as in r86). Median first frame 1.90 s, against 1.92 s | the Chaquopy apps (excluded since) |
| build 96 (11 apps) | the default time zone from OH's zone setting | Fossify Clock reads 7:45:45 PM, Wed 7 Oct, matching the board's status bar (r87: 5:36 PM, Tue 6 Oct, against 01:36 on Wed 7 Oct); clauncher's clock, Etar's current-time line and Fossify Calendar's today agree; all 11 draw | none |
| per-thread lookups (Material Files 12 times, alternated; 8 other apps; build 96) | the bionic shim's `getpw*`/`getgr*` with a result per thread | Material Files: no crash in 6 launches with it, one in 6 without (musl's `free`, under `getgrgid`, from the same call site). briar, castlab, appmanager, viewer, ooniprobe, seal, vaultexplorer and emacs draw with it | none |
| Guardian and spacebeam relaunched (5 launches, r88's provider) | none | Guardian drew in 3 of 3; spacebeam showed black in 2 of 2 | not applicable |

## Harness changes

| change | what it reads | what it names |
|---|---|---|
| routing in the launch args | `load:interposed-by-runtime` carries, with a launcher that routes by name, the routing of the exposed packaged libraries and every packaged library whose DT_NEEDED graph reaches one, and counts as supplied. An app whose written libraries need packaged ones (Chaquopy, `load:written-needs-packaged`) is not routed. Built before `android_namespace_rows`, which checks what the routed libraries need there | 129 corpus apps routed; PPSSPP and supertuxkart draw with it |
| `abi:passwd-group-static-result` | libraries importing `getpwnam`, `getpwuid`, `getgrnam` or `getgrgid`, as a risk; supplied for each lookup the bionic shim keeps per thread. A crash in those lookups from a listed library is named by it | Material Files' intermittent heap corruption; 26 corpus apps import the lookups |
| musl's allocator frames | `__libc_realloc`, `__libc_malloc` and `__libc_calloc` count as allocator frames | such a fault reads as a corrupt heap |
| file names before SONAMEs | a launch target names the file of that name, and a SONAME only where no file has that name | Duolingo's routing of `libmain.so`, which `libduolingounity.so` shares a SONAME with |
| an app on screen that nothing stopped | a screenshot showing the app's content, with no blocker, reaches drawing even when the logs stop short (with an anomaly saying so) | aaaaxy in r88 |
| ledger | PPSSPP's and supertuxkart's interposition stops closed by the routing; Material Files' lookups, recorded and closed; spacebeam's black SurfaceView recorded, open | |

The black page has a cost for the screenshot classifier: an app that draws a nearly black screen
looks like the host. Two dark apps in r88 (graph89 and uturn) read as the black page with their
content over part of it, still drawing; an app drawing pure black would not be told apart from the
host.

r86's and r87's lifecycle records are unchanged under these changes.
