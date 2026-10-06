# r86: the first SDL games and Firefox (2026-10-06)

r86 reran the whole corpus (329 apps) on the provider that the tests after r85 had cleared:
- **Builds 86 to 90:**
  - the display as every window's global configuration, and the board's Vulkan claimed;
  - implicit intents for the app's own activities;
  - the launch transaction carrying the start, so `onPostCreate` runs;
  - a window and its SurfaceViews' windows as one focus group;
  - runtime permission requests answered in process;
  - credential-encrypted storage unlocked under Android 15's name;
  - the resume in the launch transaction.
- **The shim:**
  - libmozglue's versions and C++ operators;
  - libraries written at run time sharing the APK's;
  - EGL looked up by handle;
  - `pthread_create` in Bionic's order;
  - the NDK's font list and performance hint API;
  - `JNI_GetCreatedJavaVMs`;
  - `ANativeWindow_setBuffersGeometry` in Android's terms;
  - Bionic's fts;
  - `ANativeWindow_lock` on the adapter's windows.
- **The runtime libraries:**
  - libart's init array sanitizer for packed relocations;
  - natives that the runtime lacked or answered wrongly: `Process.readProcFile`, the hint manager,
    legacy Camera, `LocalSocketImpl`, `Surface.lockCanvas` and SQLite's collations.
- **The launcher:** an input cache on the board, and host-compiled code for the eleven slowest apps,
  against build 90's boot image.

This record covers what r86 found against r85, what still stops the apps short of drawing, and the
tests made after it.

Files, made with today's harness:
- `r86-lifecycle.json`: r86 classified
  (`python -m harness.westlake_gap.lifecycle <logs> --json r86-lifecycle.json`).
- `r86-score.json`: its first blockers scored against gap maps made with today's harness, against
  r86's own provider (`scripts/score_first_blockers.py`).

## Regression check against r85

- **Coverage:** all 329 apps ran.
- **Drawing:** 311 (r85: 299).
- **Up:** 15 apps moved up, 14 of them to drawing. The change behind each:

  | app | what moved it |
  |---|---|
  | anarchre, diesimu | SDL's buffer geometry in Android's terms; EGL by handle before it |
  | Fennec | libmozglue's operators and allocator, by version; the NDK's font list |
  | Element X | `JNI_GetCreatedJavaVMs` answered by the running VM |
  | linphone | the launch carries the start: its draws waited for `onPostCreate` |
  | Shazam | implicit intents for its own activities |
  | duckrun, playmaker | the board's Vulkan claimed (Godot) |
  | Draw Anywhere | the display as the global configuration |
  | econverter, werewolvesgame | written libraries share the APK's (Chaquopy) |
  | Waze | libart's sanitizer keeps a packed-relocation init array |
  | TikTok | `pthread_create` in Bionic's order |
  | usp | it no longer aborts (below), but its emulator screen does not show |
  | emacs | Bionic's fts: its library loads, and it stops at its first activity (below) |

- **Back:** 3 apps.
  - Reddit and Zoom: their stops come from the network and from an intermittent load, and occur
    without these changes too.
  - Shortcut: it reaches bound instead of view. It finishes its trampoline at once, as in r85.
  - No other app that drew in r85 stopped drawing.

## Start-up

Since build 88 the adapter logs a drawn first frame and its 800 ms timeout as different lines, so
r86's first frames are drawn frames. 251 of the 311 apps that draw report one. The other 57 show
only the timeout: they draw through a SurfaceView's own window (the Flutter apps) or a later
activity (CapCut's splash hands over to its home screen), and the resumed activity's own window
never draws.

- **First frame:** median 1.79 s from process start. 158 apps drew within 2 s, 243 within 5 s.
  Four took over 10 s: Waze (60.6 s, the first time it draws), TikTok (25.9 s), msstart (10.9 s)
  and Instagram (10.9 s).
- **Against r85**, by the resume, which both runs log the same way (298 apps): median 0.93 s
  (r85: 0.90 s); within 2 s 272 (267); over 10 s none (5).

The eleven apps with host-compiled code account for the tail:

| app | r85 resumed / first frame | r86 resumed / first frame |
|---|---|---|
| Spotify | 14.7 / 17.8 s | 1.7 / 2.1 s |
| Uber | 15.0 / 19.9 s | 3.4 / 4.5 s |
| CNN | 11.1 / 17.3 s | 1.9 / 2.5 s |
| Citymapper | 4.8 / 16.5 s | 1.3 / 2.9 s |
| StreetComplete | 4.4 / 11.6 s | 1.2 / 2.2 s |
| X | 4.4 / 8.1 s | 1.7 / 2.2 s |
| DuckDuckGo | 7.6 / 9.3 s | 2.2 / 4.6 s |
| Instagram | 13.4 / 15.1 s | 9.1 / 10.9 s |
| OsmAnd | 10.4 / 12.8 s | 2.8 / 3.4 s (then aborts, below) |

CapCut draws its home screen through a later activity (above). Zoom stopped at bound.

## What stopped the 18 apps short of drawing

| app | stop | cause |
|---|---|---|
| Reddit | resumed, no frame | its splash waits on requests to its own servers, which the board's network does not reliably reach (one launch got a Meta address for reddit.com from the board's DNS). Android calls the `onPostCreate` that arms that splash too |
| Zoom | bound | intermittent: a SIGSEGV as `libzData.so`'s load fails on a libc++ symbol, the board's `libc++_shared.so` found before the APK's (`load:shadowed-by-board`) |
| Fossify Messages | finished itself | no SMS role on a board without telephony: a device's answer |
| opflashcontrol | slider out of range | a flashlight app on a board with no camera exposed to Android: a device's answer |
| Shortcut | finished itself | it hands its intent to an app that is not installed |
| facebooknotifica | InflateException | its preference XML names a class its bundled androidx lacks; Android fails the same way |
| NYTimes, Flipboard | Google Play services | out of scope |
| MuseKit | "startRecording() called on an uninitialized AudioRecord" | the host application did not request the microphone permission; fixed after r86 (below) |
| emacs | ClassNotFoundException at its first activity | its manifest names the activity relative to its package (`.EmacsLauncherPreferencesActivity`), which Android's parser expands and the launcher passed on as is; fixed in the launcher after r86 (below) |
| wormhole2 | resumed, no frame | its device-info plugin calls `Build.getSerial()`, which reached a null `device_identifiers` service and threw NullPointerException. Android answers an ordinary app with SecurityException, which plugins catch; the NPE failed the plugin call and the app never built its first screen |
| aaaaxy | bound | `AInputEvent_getDeviceId` missing: NativeActivity's input queue (`ndk:weld:input`) |
| cclauncher, clauncher | idle, host screen | launchers that list nothing: cclauncher dereferenced a null `ILauncherApps` (`getUserProfiles`), and clauncher's `UserManager.getUserProfiles` met the user service's refusal of `getProfileIds`. Both show a transparent window with `windowShowWallpaper`, and no wallpaper is behind it on OH |
| insigno | Mali's backend thread aborts | at bind, before any window, Flutter's Vulkan backend imports a native buffer and a GPU job fails (`base_jd_event_term`); open |
| OsmAnd | an abort on a Qt pool thread | its first start copies its bundled data while the map engine starts: the engine read the world basemap mid-copy ("Unexpected 7788245 unread byte(s)", "Failed to open OBF"), and PROJ's `FactoryException` aborted a pool thread. Every launch is a first start here; open |
| PPSSPP | SIGSEGV in libhwui | its library exports 341 symbols libhwui also exports, and its calls bind to libhwui's copies (`load:interposed-by-runtime`); routing it to the Android namespace avoids that (tested after r86, below) |
| supertuxkart | SIGSEGV on SDL's thread in musl | its `libmain.so` binds libpng's `png_set_longjmp_fn` to the runtime's copy (`load:interposed-by-runtime`); routed, it then needs the parent's GL stack (tested after r86, below) |

usp counts as drawing, and its main content is missing. It is a ZX Spectrum emulator: its keyboard
draws, and the emulator screen, a GLSurfaceView 1200x1152 in a 1920-high window, shows the host
screen. A SurfaceView short of 90% of its window shares the activity's OH window, so its GL and
hwui draw into one window. In r85 the GL thread took it first and hwui aborted with no surface; in
r86 hwui took it first, and the GL thread's `eglCreateWindowSurface` failed (`EGL_BAD_ALLOC`).

## Scoring

r86's first blockers were scored against gap maps made with today's harness (the rows and evidence
below included), against r86's own provider:
- **Scorable:** 9 of 18. **Named:** 6, each by a row that is not supplied:
  - aaaaxy by `ndk:weld:input`;
  - PPSSPP by `load:interposed-by-runtime`;
  - wormhole2 by `svc:device_identifiers`;
  - cclauncher by `svc:launcherapps`;
  - clauncher by `svc:user-unanswered`: its stall followed the user service's refusal of
    `getProfileIds`;
  - MuseKit by `perm:host:ohos.permission.MICROPHONE`, whose symptoms include its uninitialized
    AudioRecord.
- **A device's answer:** Fossify Messages.
- **Marked supplied:** Reddit. `am:post-create` is supplied, and its stop is its network, which no
  row covers.
- **Not named:** Shortcut.
- **The 9 unscorable:**
  - app exceptions with no platform symbol: emacs's relative name, facebooknotifica, NYTimes,
    Flipboard and opflashcontrol;
  - crashes in code no row names: insigno in Mali; OsmAnd in libc++; supertuxkart in musl's
    `setjmp`, after the runtime's libpng had answered its `png_set_longjmp_fn`;
  - Zoom's stop at bound, with no blocker.

## Tests after r86

| test | change | what it showed | apps that moved back |
|---|---|---|---|
| the host's microphone permission (10 apps, build 90) | the host application requests `ohos.permission.MICROPHONE`, reinstalled over itself (its uid kept) and granted | MuseKit draws its tuner and listens (r86: "startRecording() called on an uninitialized AudioRecord"); the voice recorders, which record only when asked, and the controls draw | none |
| build 92 (23 apps) | a direct launch resumes in its launch transaction only; the window adapter logs a SurfaceView it leaves sharing its window; `device_identifiers` answered in process, refusing `getSerial` with SecurityException as Android refuses an ordinary app | wormhole2 draws its first screen (r86: resumed, no frame); each activity reports its resume once (build 90 reported it twice); usp's GLSurfaceView is logged sharing its window (1200x1152 in 1200x1920); all 23 draw | none |
| the launcher (9 launches, build 92) | the Android namespace inherits the parent's GL stack (EGL, the GLES libraries, the Mali driver); a launch activity named relative to its package is expanded | Emacs draws its launcher preferences (r86: ClassNotFoundException). PPSSPP and supertuxkart with their libraries routed to the Android namespace by hand: PPSSPP no longer crashes, and its screen shows faintly, its SurfaceView's OH window blending with the screen behind it; supertuxkart loads GL and starts its renderer, then calls a GL entry point that came back null. VLC and Element (routed by their gap maps), Telegram, FluffyChat and anarchre draw; OsmAnd aborts as in r86 | none |
| the NDK's input calls (8 apps) | the bionic shim defines `AInputQueue_*`, `AInputEvent_*`, `AKeyEvent_*` and `AMotionEvent_*` as a queue that never reaches an app: the runtime has no NativeActivity natives, and the `fromJava` calls are left out | aaaaxy's `libgojni.so` loads (r86: "AInputEvent_getDeviceId: symbol not found"); its Ebiten then logs "gl: glGenVertexArrays is missing", looked up in OH's NDK `libGLESv2.so`, and the activity draws nothing on screen. anarchre, diesimu, Telegram, FluffyChat, Element, X and Spotify draw | none |

PPSSPP's and supertuxkart's gap maps name the routing that avoids their stops
(`load:interposed-by-runtime`) but do not apply it: their launch arguments carry only the network
translation, so the corpus run loads both in the default namespace. The tests above routed them by
hand. Applying the routing by default would route a library in some 160 corpus apps, which needs
a corpus run of its own.

## Harness changes

The rows this round's earlier causes led to (`window:buffers-geometry`, `window:software-canvas`,
`db:sqlite-collations`, the GLSurfaceView renderers in `window:engine-surface`, and the
`window-buffers` blocker) came with the r85 record. From r86:

| change | what it reads | what it names |
|---|---|---|
| `svc:device_identifiers` | apps that call `Build.getSerial`, which asks the device_identifiers service itself (no manager and no getSystemService request names it), against a provider that answers it | wormhole2; 21 corpus apps call it |
| null platform services | the platform service interfaces an app dereferenced null, from the NullPointerException messages in its logs, caught or not | a stall, or an activity that never drew, after such a dereference is named by that service's row: wormhole2, cclauncher |
| `perm:host:<OH permission>` | Android permissions the app requests whose capability the provider carries out in the host application's process, through an OH call that checks the caller's permission (audio capture, for now), against the permissions the host requests | MuseKit: `perm:host:ohos.permission.MICROPHONE`, missing on r86's provider |
| `gl:gles3-by-handle` | GLES 3 core entry points a library names without importing them (Go's unterminated strings included), against a shim that answers an Android dlopen of `libGLESv2.so` with OH's `libGLESv3.so`, ahead of its `.z.so` probe (which returns the plain name's library first) | aaaaxy (Ebiten, 3 names); supertuxkart (216); SDL itself names `glGetStringi` |
| dlsym failures in the app's log | OH's "do_dlsym failed: Symbol not found" lines an app passes on; off screen, the first is the blocker ("dlsym found no ... in ..."), named by the row that lists the name | aaaaxy after r86 |
| symptoms in scoring | an app exception that a row lists among its symptoms is named by that row | MuseKit's "uninitialized AudioRecord", by `perm:host:ohos.permission.MICROPHONE` |
| `svc:user-unanswered` | UserManager calls the app makes that reach an `IUserManager` method the in-process user service does not name (it throws UnsupportedOperationException there), through a census of UserManager's source that follows its own methods | clauncher (`getUserProfiles` asks `getProfileIds`); eight corpus apps on r86's provider |
| service refusals | the user service's "does not implement" exceptions in the app's logs; a stall or an activity that never drew after one is named by the row that lists it among its symptoms | clauncher |
