# r87: the NDK's input calls, GLES 3, and services answered in process (2026-10-06)

r87 reran the whole corpus (329 apps) on the provider that the tests after r86 had cleared:
- **Builds 91 to 95:**
  - a direct launch resumes in its launch transaction only, so each activity reports its resume
    once;
  - `device_identifiers` answered in process, refusing `getSerial` with SecurityException as
    Android refuses an ordinary app;
  - LauncherApps answered in process, and the user service's profile group (`getProfileIds` and
    the calls around it) for the app's only user;
  - build 93 marked an opaque SurfaceView's own OH window opaque. That changed nothing on the board,
    and build 95 reverts it.
- **The shim:**
  - the NDK's input calls (`AInputQueue_*`, `AInputEvent_*`, `AKeyEvent_*`, `AMotionEvent_*`), as a
    queue that never reaches an app;
  - an Android library's `dlopen` of `libGLESv2.so` answered with OH's `libGLESv3.so`, ahead of the
    shim's `.z.so` probe.
- **The launcher:** the Android namespace inherits the parent's GL stack, and a launch activity named
  relative to its package is expanded.
- **The host application** requests the microphone, reinstalled over itself with its uid kept.
- Host-compiled code for the same eleven apps as r86, against build 95's boot image, and the input
  cache.

This record covers what r87 found against r86, what still stops the apps short of drawing, the
tests made after it, and the harness changes since the r86 record.

Files, made with today's harness:
- `r87-lifecycle.json`: r87 classified
  (`python -m harness.westlake_gap.lifecycle <logs> --json r87-lifecycle.json`).
- `r87-score.json`: its first blockers scored against gap maps made with today's harness, against
  r87's own provider (`scripts/score_first_blockers.py`).

## Regression check against r86

- **Coverage:** all 329 apps ran.
- **Drawing:** 316 (r86: 311).
- **Up:** 5 apps, all to drawing. The change behind each:

  | app | what moved it |
  |---|---|
  | aaaaxy | the NDK's input calls let its `libgojni.so` load; GLES 3 through `libGLESv2.so` let its Ebiten find `glGenVertexArrays` |
  | Emacs | its launch activity, which its manifest names relative to its package, expanded by the launcher |
  | MuseKit | the host's microphone permission: it draws its tuner and listens |
  | wormhole2 | `device_identifiers` answered: its device-info plugin gets SecurityException from `getSerial` and catches it |
  | Zoom | none: its r86 stop at bound is intermittent (`libzData.so`'s load against the board's libc++) |

- **Back:** none. No app that drew in r86 stopped drawing.
- **A false crash:** r86 and r87 both show TikTok drawing. r87's record first gave it a SIGSEGV in
  libhwui. That dump was PPSSPP's: PPSSPP's process had the same pid 2 h 22 min earlier. The
  lifecycle now leaves out a dump older than the process (below).

## Start-up

- **First frame:** 254 of the 316 apps that draw report a drawn first frame.
  - Median 1.76 s from process start (r86: 1.79 s). 155 drew within 2 s (158), 243 within 5 s
    (243).
  - Six took over 10 s: Waze (56.6 s), TikTok (25.5 s), Moovit (11.4 s), Transit (11.3 s), msstart
    (11.1 s) and Instagram (10.2 s). Moovit and Transit took 9.7 s and 9.9 s in r86.
- **Against r86, apps that drew in both:**
  - 242 apps with a first frame in both: median 1.78 s, then 1.75 s;
  - 301 apps that logged a resume in both: median 0.93 s in each round.

The host-compiled apps start as in r86. Zoom, which stopped at bound in r86, resumed in 4.5 s and
drew in 5.3 s.

## What stopped the 13 apps short of drawing

| app | stop | cause |
|---|---|---|
| cclauncher | idle, host screen | LauncherApps answers it now (r86: a null `ILauncherApps`): it reads the user's profiles and launcher activities, and its first frame is drawn. Its window is transparent with `windowShowWallpaper`, and nothing of it shows over the host screen (`wm:show-wallpaper`) |
| clauncher | idle, host screen | its profile group answers now (r86: the user service refused `getProfileIds`). It draws its clock and hints in white in a transparent `windowShowWallpaper` window, which over the host's light page read as the host screen (`wm:show-wallpaper`) |
| Reddit | resumed, no frame | its splash waits on its own servers, which the board's network does not reliably reach, as in r86 |
| Fossify Messages | finished itself | no SMS role on a board without telephony: a device's answer |
| opflashcontrol | slider out of range | a flashlight app on a board with no camera exposed to Android: a device's answer |
| Shortcut | finished itself | it hands its intent to an app that is not installed |
| facebooknotifica | InflateException | its preference XML names a class its bundled androidx lacks; Android fails the same way |
| NYTimes, Flipboard | Google Play services | out of scope |
| insigno | Mali's backend thread aborts | at bind, as Flutter's Vulkan backend imports a native buffer; open |
| OsmAnd | an abort on a Qt pool thread | its first start copies its bundled data while the map engine starts; open |
| PPSSPP | SIGSEGV in libhwui | its calls to its own exported functions bind to libhwui's copies (`load:interposed-by-runtime`); its gap map names the routing that avoids it, and the corpus run does not apply it |
| supertuxkart | SIGSEGV on SDL's thread in musl | `libmain.so`'s `png_set_longjmp_fn` binds to the runtime's libpng (`load:interposed-by-runtime`); routed, it draws its menu since GLES 3 through `libGLESv2.so` |

usp still counts as drawing with its emulator screen missing: its GLSurfaceView shares the
activity's OH window, as in r86.

## Scoring

r87's first blockers were scored against gap maps made with today's harness, against r87's own
provider:
- **Scorable:** 6 of 13. **Named:** 3, each by a row that is not supplied:
  - cclauncher and clauncher by `wm:show-wallpaper`: each is idle with the host screen showing, and
    its launch activity shows the wallpaper;
  - PPSSPP by `load:interposed-by-runtime`.
- **A device's answer:** Fossify Messages.
- **Marked supplied:** Reddit. `am:post-create` is supplied, and its stop is its network, which no
  row covers.
- **Not named:** Shortcut.
- **The 7 unscorable:**
  - app exceptions with no platform symbol: facebooknotifica, NYTimes, Flipboard and opflashcontrol;
  - crashes in code no row names: insigno in Mali; OsmAnd in libc++; supertuxkart in musl's
    `setjmp`, after the runtime's libpng had answered its `png_set_longjmp_fn`.

r86's six named stops, a round later:
- aaaaxy, wormhole2 and MuseKit draw: the change for each row closed its gap.
- The launchers' service rows are supplied, and the next stop for both is named by
  `wm:show-wallpaper`.
- PPSSPP is named by the same row as in r86: the run still does not apply the routing.

## Tests after r87

| test | change | what it showed | apps that moved back |
|---|---|---|---|
| the host's black page (8 apps, and PPSSPP routed; build 95) | the host application's page is empty and black (version 4, reinstalled over itself, its microphone grant kept) | clauncher's clock and hints show in white over the black page (over the light page the classifier read them as the host). cclauncher still shows nothing. PPSSPP, routed, shows its welcome screen in full colour: its SurfaceView's window still blends with what lies below it, and over black its frames show as drawn. aaaaxy, MuseKit (listening), Telegram, X, FluffyChat and Element draw | none |

Over the black page the navigation bar's handle is light, and over cclauncher's transparent window it
is dark: the screen comparison now leaves the handle out (below).

## Harness changes

The rows from r86's evidence (`svc:device_identifiers`, `perm:host:<OH permission>`,
`gl:gles3-by-handle`, `svc:user-unanswered`, and reading null services, refusals and dlsym failures
from the logs) came with the r86 record. Since then:

| change | what it reads | what it names |
|---|---|---|
| `window:surfaceview-opacity` | an engine's SurfaceView in an OH window of its own. Android composes an opaque SurfaceView's layer without blending; OH's render service blends what the window shows. The row counts as supplied only when the window's self-drawing content node is marked opaque: marking the window's own node changed nothing on the board | PPSSPP, routed: its frames showed faintly over the host's first page; over the black page they show as drawn |
| `wm:show-wallpaper` | activities whose theme (their own, a parent's, or a framework `Theme.*Wallpaper*` a parent inherits) sets `windowShowWallpaper`, resolved through `resources.arsc`. Android draws the wallpaper under such a window; OH draws its wallpaper only under its own launcher | cclauncher and clauncher; 13 corpus apps have such activities, 3 of them as their launch activity |
| the host's pages | a screenshot is the host screen when it shows one of the host's pages bare: its first page, a title and a keyboard control on light grey, or since host version 4 an empty black page. Each run is read against the page that most of its screenshots show bare. Against both pages, three dark apps in r87 (spacebeam, graph89, uturn) read as the black page with something over part of it | the records made over either page classify as they were made |
| the navigation bar's handle | the comparison leaves out the screenshot's bottom rows, as it leaves out the status bar: the handle's shade follows the window under it | cclauncher over the black page is the host screen, not the host with something over it |
| crash dumps of other processes | a crash dump older than the first line of the process's own hilog is another process's: pids repeat within a run, and the run looks dumps up by pid | TikTok's false SIGSEGV in r87 |
| scoring | a stall, idle on the host screen, in an app whose launch activity shows the wallpaper, is named by `wm:show-wallpaper`, which now lists those launch activities | cclauncher and clauncher in r87 |
| ledger | aaaaxy's input and GL lookups, supertuxkart's GL lookups and the launchers' services marked fixed; the launchers' wallpaper stops named by `wm:show-wallpaper` | |

r86's record is unchanged under these changes.
