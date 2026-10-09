# r89: services answered, batches 21 and 22 in the corpus (2026-10-08)

r89 reran the whole corpus on the provider that the tests after r88 had cleared, and for the first
time it included the 40 apps of blind batches 21 and 22: 369 apps.
- **Build 99:** build 96, plus what the two batches' misses showed:
  - `vpn_management` answered in process, as on a device where the user has not yet consented to
    this app's VPN (socks5's miss);
  - the in-process AndroidKeyStore converts a legacy `KeyPairGeneratorSpec`, as Android's provider
    does (gitling's);
  - the package manager answers for the platform package `android` (NewPipe's and Retro Music's
    media services, which r87 and r88 showed failing).
- **The bionic shim:** `if_nametoindex` and `if_indextoname` fall back to `getifaddrs` when OH's
  policy refuses an app's domain the ioctl (yaacc's miss).
- **The runtime override:** `UnixNativeDispatcher`'s file-time setters registered (gitling's next
  stop).
- **The gap maps:** r88's, whose launch args route the libraries exposed to the runtime's exports;
  for the batches, their own.
- Host-compiled code for the same eleven apps, against build 99's boot image, and the input cache.

This record covers what r89 found against r88, what still stops the apps short of drawing, and the
harness changes since the r88 record. The tests that cleared this provider are in the records of
batches 21 and 22.

Files, made with today's harness:
- `r89-lifecycle.json`: r89 classified
  (`python -m harness.westlake_gap.lifecycle <logs> --json r89-lifecycle.json`).
- `r89-score.json`: its first blockers scored against gap maps made with today's harness, against
  r89's own provider (`scripts/score_first_blockers.py`).

## Regression check against r88

- **Coverage:** all 369 apps ran.
- **Drawing:** 356 of 369.
  - The 329 apps of r88: 317 draw, as in r88.
  - The 40 apps of batches 21 and 22: 39 draw. plusplusbattery stops on its shell (`os:shell`),
    as in batch 22.
- **Up:** Guardian and Reddit, both flaky in r88's record. Guardian drew, as in its three relaunches
  after r88 (its screenshot can fall inside the pause and resume it makes about 50 s after start).
  Reddit's splash got through to its servers this time (first frame at 13.7 s).
- **Back:**
  - **Zoom:** at bound, as in r86. A SIGSEGV on its `us.zoom.videome` thread, which Zoom's own
    handler survives only once OH's in-process dump finishes; the dump helper timed out
    (`waitpid ... timeout`) and the app died without a dump. Zoom counts as flaky in decisions.
  - **usp:** an abort in libhwui, "drawRenderNode called on a context with no surface!". usp's
    GLSurfaceView (1200x1152 at the top of a 1200x1920 window) is too small for an OH window of
    its own, so it shares the activity's, and its GL thread and libhwui race to make that
    window's EGL surface. In r87 and r88 libhwui won: usp's `eglCreateWindowSurface` was refused
    (`EGL_BAD_ALLOC`), and it drew without its emulator's screen. In r89 its GL thread won, and
    libhwui, left without a surface, aborted at its first draw. Relaunched four times on this
    provider, the GL thread won twice more (below).
- **The changes' own apps:**
  - socks5, yaacc and gitling, the batches' misses, draw (first frames at 1.37, 2.0 and 3.2 s);
  - blockads no longer throws on its VPN thread, and openhab no longer on its network interfaces;
  - NewPipe and Retro Music start their media services: their `NameNotFoundException` for the
    package `android` is gone. The service failures left in the corpus are Felicity's
    (`libaaudio.so` would not load) and Fennec's content process ("Cannot reuse process tab").

## Start-up

- **First frame:** 284 of the 356 apps that draw report a drawn first frame.
  - Median 1.79 s from process start (r88: 1.73 s). 180 drew within 2 s, 274 within 5 s.
  - Seven took over 10 s: Waze (58.9 s), TikTok (26.8 s), Reddit (13.7 s), Instagram (11.5 s),
    Nextcloud Talk (11.2 s; 8.5 s in r88), Moovit (10.8 s) and msstart (10.1 s).
- **Against r88, apps that drew in both:**
  - 244 apps with a first frame in both: median 1.73 s, then 1.79 s;
  - 292 apps that logged a resume in both: median 0.90 s, then 0.94 s.
  The medians of r86 to r88 moved by as much (1.79, 1.76, 1.73 s).

## What stopped the 13 apps short of drawing

| app | stop | cause |
|---|---|---|
| plusplusbattery | process init: `NoShellException` | libsu starts a shell; OH's policy refuses an app's domain `/system/bin/sh`, and OH's toybox has no `sh` applet (`os:shell`) |
| cclauncher | idle, host screen | a transparent `windowShowWallpaper` window with nothing visible in it, as in r87 and r88 (`wm:show-wallpaper`) |
| spacebeam | drawing frames, black screen | its GLSurfaceView's own OH window shows nothing; open |
| usp | abort in libhwui | its GLSurfaceView shares the activity's OH window, and its GL thread made the window's EGL surface before libhwui did (above); open |
| Zoom | bound | its video thread's fault, and OH's dump helper timing out (above) |
| Fossify Messages | finished itself | no SMS role on a board without telephony: a device's answer |
| opflashcontrol | slider out of range | a flashlight app on a board with no camera exposed to Android: a device's answer |
| Shortcut | finished itself | it looks for Android's file manager (DocumentsUI), which is not installed, and finishes |
| facebooknotifica | InflateException | its preference XML names a class its bundled androidx lacks; Android fails the same way |
| NYTimes, Flipboard | Google Play services | out of scope |
| insigno | Mali's backend thread aborts | at bind, as Flutter's Vulkan backend imports a native buffer; open |
| OsmAnd | an abort on a Qt pool thread | its first-start data copy races the map engine, and PROJ's uncaught `FactoryException` aborts a pool thread, as in r86 to r88; open |

## Relaunches after r89

| launch | provider | who made the window's EGL surface | result |
|---|---|---|---|
| r89 | r89's | usp's GL thread | abort in libhwui |
| 1 | r89's, with the shim carrying AAudio | usp's GL thread | abort in libhwui |
| 2 | r89's | usp's GL thread | abort in libhwui |
| 3 | r89's | libhwui; usp's refused | drew, without the emulator's screen |
| 4 | r89's | libhwui; usp's refused | drew, without the emulator's screen |

The emulator's SurfaceView starts at its window's origin, where OH places every window, so an OH
window of its own, the size of the SurfaceView, would sit where Android composes it: the race
would go, and the emulator's screen would show.

## Scoring

r89's first blockers were scored against gap maps made with today's harness, against r89's own
provider (the batches' apps against their own maps):
- **Scorable:** 4 of 13.
  - **Named:** plusplusbattery by `os:shell`, and cclauncher by `wm:show-wallpaper`.
  - **A device's answer:** Fossify Messages.
  - **Not named:** Shortcut.
- **The 9 unscorable:**
  - app exceptions with no platform symbol: facebooknotifica, NYTimes, Flipboard and opflashcontrol;
  - crashes in code no row names: insigno in Mali, OsmAnd in libc++ (PROJ's exception), and usp's
    abort in libhwui, a graphics abort no row type covers;
  - a stall no row names: spacebeam;
  - Zoom: its log names no blocker, as its fault died with OH's dump.

r88's named stop, cclauncher, is named by the same row. Batch 22's misses, a round later:
plusplusbattery is named by `os:shell`; yaacc and gitling draw.

## Harness changes since the r88 record

They came with the records of batches 21 and 22:

| change | what it reads | what it names in r89 |
|---|---|---|
| framework service fetches | public framework methods that fetch a service's binder themselves (52 classes, 387 methods); a call to one is a service request, listed with the binder interface (`framework_fetch_throws`) | none: `vpn_management` is answered |
| scoring null binders | a NullPointerException on a null `I*` binder interface is named by the service row that lists the interface | |
| `abi:interface-index` | `NetworkInterface` calls and native imports of `if_nametoindex` / `if_indextoname`; supplied where the shim answers the index from `getifaddrs` | supplied |
| `jca:legacy-keypair-spec` | a `KeyPairGeneratorSpec`, against whether the in-process AndroidKeyStore accepts it | supplied |
| `os:shell` | an app that runs a shell through libsu (libraries recorded by a marker class, `library_markers`) | plusplusbattery |
| service failures | exceptions an app's own service throws in `onCreate`, `onStartCommand` or `onBind`, which Westlake's in-process services catch and log; a stop after one is named by a row listing the exception among its symptoms | Felicity's and Fennec's, in apps that draw |
| ledger | gitling's file times and the three broken services recorded; closed where build 99 answers them | |
