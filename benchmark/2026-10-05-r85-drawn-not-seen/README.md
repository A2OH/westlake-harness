# r85: drawn and not seen (2026-10-05)

r85 reran the whole corpus (329 apps) on the newest stack the tests before it had cleared:
- build 85: the task model, in-process services and answers, and the app's own Intent for its
  in-process launches (see the r84 record);
- the shim with Bionic's static mutex initializers adopted, by-name loads checked with
  `RTLD_NOLOAD`, and a trylock that needs no `dlsym`;
- the patched libart whose palette answers `NORM_PRIORITY` for the threads it attaches.

It is the regression check for everything since r84. This record covers what it found, the
harness changes it led to, and the fixes made from its evidence.

Files, made with today's harness:
- `r85-lifecycle.json`: r85 classified
  (`python -m harness.westlake_gap.lifecycle <logs> --json r85-lifecycle.json`).
- `r85-score.json`: its first blockers scored against gap maps made with today's harness, against
  r85's own provider (`scripts/score_first_blockers.py`).

## Regression check against r84

- **Coverage:** all 329 apps ran. Bim and Citymapper, lost in r84, both draw.
- **Drawing:** 299 (r84: 276).
- **Up:** 28 apps moved up, 24 of them to drawing.
  - From runtime-init: CNN, LibreTube, quitter and Translator.
  - Spotify, Instagram, Discord, Reddit, CapCut and Open Camera draw, among others.
- **Back:** 3 apps moved back, each for a cause the tests before r85 had already shown:
  - anarchre and supertuxkart: SDL now loads and aborts in the GL stack, where in r84 it showed its
    error dialog (the native EGL windows test in the r84 record);
  - OsmAnd: it aborts with the static mutex adoption and draws without it (the r84 A/B).

## Start-up

r85 staged no host-compiled code for the apps themselves: their own code ran interpreted and
through the JIT, over the speed-compiled boot image.

The first frame here is the adapter's report, read from each app's own hilog. It fires on the first
drawn frame, or 800 ms after the resume with none drawn, and until build 88 both logged the same
line. 80 of the 298 apps with both times sat 0.79-1.2 s after their resume, piled up at 0.8 s. For
those the report may be the timeout, and the time below is then a lower bound: the frame came
later, or never (linphone). From the hilogs, for the 311 apps whose activity reported a first frame:
- median 1.84 s from process start (r84: 1.86 s);
- 191 within 2 s, 293 within 5 s;
- 8 over 10 s.

Discord's first frame went from 62.9 s to 2.2 s, and FairScan's from 36.8 s to 1.7 s. With their
own code compiled on the host as well (a test after r85, below), the slowest apps reach their first
resume several times sooner: Spotify in 1.5 s instead of 14.7, CapCut in 5.3 instead of 24.1. The
eight over 10 s:

| app | first frame | r84 | note |
|---|---|---|---|
| CapCut | 33.8 s | 15.1 s | it now goes on to its home screen: its Application takes 11 s, its main activity 13 s more to resume. Build 85's own test measured 32.3 s |
| Uber | 19.9 s | 18.9 s | |
| Spotify | 17.8 s | - | draws for the first time |
| CNN | 17.3 s | - | draws for the first time |
| Citymapper | 16.5 s | - | lost in r84 |
| Instagram | 15.1 s | 14.3 s | |
| OsmAnd | 12.8 s | 5.5 s | then aborts (above) |
| StreetComplete | 11.6 s | 12.5 s | |

## What stopped the 30 apps short of drawing

r85's first blockers were scored against gap maps made with today's harness, using r85's provider:
- **Scorable:** 11 of 30. **Named:** 9, a row that is not supplied names the blocker.
- **A device's answer:** 1, Fossify Messages (below).
- **Not named:** 1, Shortcut. **Marked supplied:** none.
- The harness r85 started with scored 5: 2 named, 1 not named, and 2 marked supplied. Those two,
  Shazam and Fossify Messages, it had put down to the task-root check.
- **Native crashes** now count where a row names a library the crash's app frames are in. A row
  about one kind of call (a thread start, an allocator name) also needs that call among the crash's
  frames. This counts Waze, Fennec, TikTok, econverter and Element X. PPSSPP's crash runs in
  libhwui's copy of symbols its own library exports, which `load:interposed-by-runtime` names.
  Matched by library alone, it had read as a thread-handle crash.
- **The 19 unscorable:** crashes in the GL stack or in code no row names, app exceptions with no
  platform symbol, and windows that drew and were not seen. Their causes are below. Linphone's,
  `am:post-create`, is scorable only from build 88's logs, where an activity that never drew says so.

### Apps that closed themselves

Three apps resumed their first activity and finished it themselves, with nothing replacing it.

- **Shazam:** its splash resolves `VIEW shazam_activity://configuration` in its own package before
  it starts its first screen.
  - The scheme is a string resource in its manifest, which Android's parser resolves.
  - Westlake asked OH's bundle manager, which knows OH's abilities and nothing of the app's
    manifest. Nothing resolved, the splash started nothing, and it finished as it always does.
  - **The fix:** the package manager answers the app's own activities from their manifest filters,
    as PackageManagerService's resolver does (MATCH_DEFAULT_ONLY needs CATEGORY_DEFAULT). An
    implicit `startActivity` that resolves to one of them is made explicit before it becomes a
    Want (build 87). In its test Shazam draws its home screen.
  - **The row:** `am:own-implicit-intents`. The scanner reads the schemes and actions only the
    app's own activity filters declare, and which of them the app's dex names. Shazam names
    `shazam_activity`, two other schemes of its own and two of its own actions.
- **Fossify Messages:** it asks RoleManager whether the SMS role is available, shows a toast and
  finishes.
  - The role service answers as a board with no telephony: no role is available.
  - Fossify Messages closes the same way on any Android device that cannot send SMS. This is the
    device's answer, not a gap.
  - **The harness:** it had no row for the role service. R8 had moved `RoleManager.class` into a
    method of its own (API outlining), so the class reached `getSystemService` through a call,
    which the scanner did not follow. It does now.
  - The service row now carries the device's answer, read from the comment of the in-process
    handler that answers only defaults. The scorer counts this exit as a device's answer.
- **Shortcut:** it hands its intent to another app and finishes. That app is not installed. No row
  covers it (as in r84).

### A thread that read its own handle before it was stored: TikTok

TikTok drew in every test before r85 and died at runtime-init in r85, in musl's
`pthread_setname_np`.

- **The cause:** ByteDance's `libvcbasekit.so` creates its threads with the handle inside the
  object it hands them: `pthread_create(&this->thread_, ..., this)`. The thread's first act is
  `pthread_setname_np(this->thread_, name)`.
  - Bionic stores the new thread's handle before the thread runs. The thread waits on a startup
    lock that `pthread_create` releases after that store.
  - musl stores it after `clone` returns. When the thread wins the race, it reads handle 0.
- **Reading the dump:** OH's crash dump named the calling frames in `libvcbasekit.so` at offsets
  0x20000 too high. The thread's saved frame records and its `x16` (the PLT slot of
  `pthread_setname_np` in libvcbasekit's GOT) gave the real caller.
- **The fix:** the shim's `pthread_create` starts an Android caller's thread in a routine that
  waits on a futex until the handle is stored. Other callers go straight to musl's.
  - A host test with a deliberately late store: without the wait, 199 or 200 of 200 threads saw
    no handle; with it, none did.
- **The row:** `abi:thread-handle-order`. The scanner counts `pthread_create` calls whose handle
  is built as the thread argument plus a constant.
  - 46 corpus apps have one, among them TikTok, CapCut and Toutiao through `libvcbasekit.so`.
  - Such a call is a risk, not a proof: the thread may never read the field.

### CapCut after its home screen: Bionic's TLS slots

CapCut draws its home screen (it did not in r84) and then dies in ByteDance's `libmetasec_ov.so`,
in every run.

- **The site:** a store to address 0x13 at +0x15b6ec, in a copy of Bionic's `vfork` (it then calls
  `clone` with `CLONE_VM | CLONE_VFORK | SIGCHLD`). Bionic's vfork clears the thread's cached pid in
  its `pthread_internal_t`, which it reaches through TLS slot 1, `[TPIDR_EL0 + 8]`. On OH that word
  held -1, and -1 + 20 is 0x13.
- **Why OH differs:** Bionic keeps eight slots above the arm64 thread pointer. OH musl keeps its own
  reserved slots below it, then a 16-byte gap and the static TLS blocks above it. What a load from
  the thread pointer reads is the loader's layout; no library can change it.
- **The row:** `abi:bionic-tls-slots`, effort L. Seven corpus apps read Bionic's slots directly,
  besides the stack guard every Android-built function reads: the thread id slot in ByteDance's
  security and trace libraries (CapCut, TikTok, Toutiao), Uber's `libeef0.so` and libpython 3.13;
  ART's `Thread*` in ByteDance's and Meta's profilers.

### Windows that drew and were not seen

Four apps drew a first frame, kept an idle main thread, and showed the host screen at the
screenshot:

| app | why |
|---|---|
| cclauncher, clauncher | launchers: a transparent window with `windowShowWallpaper`, and no wallpaper behind it on OH. LauncherApps is null, so they list no apps and draw nothing over it |
| wormhole | its content is a SurfaceView in a translucent window; a SurfaceView's own surface is not composited (as usp) |
| linphone | it never drew. Its MainActivity cancels every draw from a pre-draw listener until `onPostCreate` marks its first screen ready, and Westlake never called `onPostCreate` (below). Its main thread asked for a frame 60 times a second for the whole run |

Linphone's "first frame" was not one. The adapter reports an activity's first drawn frame, or, 800 ms
after its resume with none drawn, a timeout, and both logged the same line (see Start-up).

**onPostCreate, for every app.** Android's launch transaction creates, starts and resumes the
activity. `handleLaunchActivity` marks the executor's pending actions (restore the saved state, call
`onPostCreate`) and the start consumes them. Westlake's launch transaction stops at `onCreate`, and
the resume comes in a transaction of its own (the OH foreground step, the direct launch's, an
in-process launch's). The executor clears its pending actions when a transaction ends, so no
activity, in any app, got `onRestoreInstanceState` or `onPostCreate`.
- **The fix:** the launch transaction requests the start state (build 88). The start reports
  nothing to OH and adds no window, so the separate resume is unchanged. In its test linphone
  draws its main screen, and the controls draw as before.
- **Reddit after it:** its main activity now holds its splash (its own onPostCreate arms the splash
  state, as on Android) until requests to its own servers come back, and from the board's network
  they often do not: one launch got a Meta address for reddit.com from the board's DNS. Before
  build 88 the splash state never ran, so the activity drew at once. Its no-frame is the network,
  not the platform; it counts as flaky, like Zoom.
- **Build 90** carries the resume in the launch transaction too, for a launch with no OH ability
  behind it (the direct launch, an in-process one), as Android's does: what onCreate, onStart and
  onPostCreate post then runs after onResume. In its test 35 of 37 apps draw; the other two are
  Fossify Messages (no SMS role) and Reddit (its network).
- **The row:** `am:post-create`. The scanner lists manifest activities whose own class, or a base
  class that kept its name, overrides either callback: 85 of the 329 corpus apps do. R8 renames AppCompatActivity (linphone's is
  `k.h`), whose override only installs the decor again, so a renamed base class is left out.
- **The blocker:** with build 88 the timeout logs a line of its own. A resumed activity with only the
  timeout, and the host screen behind it, is the `no-frame` blocker, which the scorer matches to
  `am:post-create`.

Nounours's action bar is on screen, over a window that is transparent where its SurfaceView
should be. It draws that SurfaceView in software, with `SurfaceHolder.lockCanvas`, and the
runtime's `Surface.lockCanvas` handed back no buffer behind the Canvas while its
`unlockCanvasAndPost` posted nothing; the shim's `ANativeWindow_lock`, the native pair, answered
`-ENODEV`.
- **The fix:** `ANativeWindow_lock` requests and maps a buffer of the OH window behind the
  adapter's, in Android's terms, and `unlockAndPost` flushes it; `Surface.lockCanvas` is wrapped
  over that pair from the missing-natives library, the Canvas pointed at the buffer through
  libhwui's `ACanvas` API. In its test nounours's bear shows, on its rainbow ground. Its action
  bar does not: the SurfaceView's own OH window sits above the activity's, where Android puts the
  SurfaceView behind it.
- **The row:** `window:software-canvas`, from `lockCanvas` calls and `ANativeWindow_lock` imports.

The classifier now counts such a screenshot (the host screen with the app's content over part of
it) as on screen; Draw Anywhere's overlay toolbar reads the same way.

### Graphics

| app | stop | cause |
|---|---|---|
| anarchre, supertuxkart, diesimu | aborts in the GL stack | SDL `dlopen`s `libEGL.so` and takes every entry point from that handle. It reached OH's NDK libEGL, whose wrapper cannot load GLES in OH's ndk namespace, and an `eglCreateWindowSurface` that refused the adapter's window (`EGL_BAD_NATIVE_WINDOW`). The fix: such a lookup gets the shim's EGL. In its test the aborts are gone, and nothing of SDL's shows: every buffer request on its SurfaceView's window failed (13,915 in anarchre's minute). Before it creates its EGL surface, SDL calls `ANativeWindow_setBuffersGeometry(window, 0, 0, its config's visual)`, as the NDK documents; 0x0 means the window's own size, and the runtime's definition handed OH a 0x0 buffer size and Android's format number, which is CLUT1 in OH's numbering. The fix: the shim answers an app library's call in Android's terms (`window:buffers-geometry`). In its test no buffer request fails, anarchre shows its title screen and menu, and diesimu its Kivy screen: the first SDL apps to show on Westlake; with the shim before it, both fail as before. The controls draw. supertuxkart then dies loading a PNG: its `libmain.so` exports 384 libpng symbols the runtime's `libpng.so` exports too, its `png_set_longjmp_fn` bound to the runtime's, answered NULL for Bionic's `jmp_buf` size, and `setjmp(NULL)` faulted (`load:interposed-by-runtime`) |
| duckrun, playmaker | a call through a null function pointer in Godot | Godot's Java side found no Vulkan feature while its engine found a working libvulkan. The fix: the board's Vulkan is claimed (build 86); both draw in its test |
| insigno | Mali's backend thread aborts | open. At bind, on the main thread and before any window exists, Flutter's engine creates its Vulkan device and imports one native buffer. 27 ms later a GPU job comes back failed (`base_jd_event_term`) and Mali's backend thread aborts. Other Flutter apps import such buffers for their swapchains and draw |
| PPSSPP | SIGSEGV in libhwui, called from `libppsspp_jni.so` | its library exports 341 symbols libhwui also exports, and its calls bind to libhwui's copy. Routing it to the Android namespace avoids that (an r84 test); the gap map names the remedy but does not apply it, since the same row covers many apps no test has run that way. Applied in a test after r85, PPSSPP no longer crashes, and its UI shows only faintly over the host screen. supertuxkart, routed the same way, gets past libpng, and its SDL then cannot load GL: the runtime's `libGLESv1_CM.so` needs OH's `libGLES_mali.z.so`, which the Android namespace neither finds nor shares with its parent |
| usp | "drawRenderNode called on a context with no surface" | open. Its GLSurfaceView (1200x1152 of a 1920-high window) is smaller than the 90% of its window that gets an OH window of its own, so it shares the activity's: its GL thread's EGL surface took that window, and hwui's render thread, left with no EGL surface, aborted. OH windows cannot be placed here, so a smaller SurfaceView has no window of its own |

**A SurfaceView's window takes the focus.** A SurfaceView that fills its window gets an OH window of
its own, above the activity's. Once it shows, OH moves focus to it. Its session's focus callback
reached a bare Binder that no ViewRootImpl stands behind ("No field mViewAncestor"), so the
activity's window saw only the loss: in anarchre, in diesimu, and in fluffychat.
- Android's SurfaceView is a layer of its window and never takes focus. SDL pauses its native loop
  when its activity loses focus; Flutter draws on regardless, and fluffychat shows.
- **The fix:** the SurfaceView's session is created for a window object that names the ViewRootImpl
  it belongs to. A window and its SurfaceViews' windows are one focus group: the window stays
  focused while any of them holds OH focus (build 89). In its test the activity's window gets
  its focus back from its SurfaceView's window, and anarchre and diesimu still show nothing:
  focus was not why. Their SurfaceView's window got no buffers at all (Graphics, above).
- **The row:** `window:surfaceview-focus`, for apps with an engine that renders only with focus
  (SDL; Cocos2d-x resumes its GL view only with focus).
- Touch input picks the window whose view has focus, so the fix also keeps taps going to the
  activity's window.

### Permission requests

Five apps that drew asked for runtime permissions (aat, castlab, Element, msstart, ssh) and never
heard back. `Activity.requestPermissions` starts the permission controller for a result, and on
Android the activity always hears back in `onRequestPermissionsResult`. Here the request went to OH
as an implicit action it does not know.
- **The fix:** the request is answered in process with what OH has granted the host application, as
  if the user had decided and changed nothing. It arrives as the controller's result would, through
  `Activity.dispatchActivityResult` (build 89).
- **The row:** `am:permission-request`.

### Past the first screen: SQLite collations

Fossify Notes drew in r85, and every query for its notes failed on its worker threads: "no such
collation sequence: UNICODE". Android registers UNICODE on every SQLite connection, and LOCALIZED
and PHONEBOOK for the locale, over ICU. The runtime registered no UNICODE and compared LOCALIZED
and PHONEBOOK with `strcoll`, which musl implements as byte order.
- **The fix:** `SQLiteConnection.nativeOpen` and `nativeRegisterLocalizedCollators` are wrapped
  from the missing-natives library: UNICODE over ICU's root collator, LOCALIZED and PHONEBOOK over
  the locale's at primary strength. In its test Fossify Notes logs no such error and opens its
  editor.
- **The row:** `db:sqlite-collations`, from the SQL in the app's dex: Fossify Notes names
  UNICODE, and five corpus apps sort with LOCALIZED.

### The rest

| app | stop | cause |
|---|---|---|
| Fennec | SIGSEGV in musl | `free@libmozglue.so` bound to musl's unversioned `free`. The fix: the shim defines those names at libmozglue's version. In its test Fennec then reached a call through a null weak import, the NDK's system font list (API 29), which the shim now defines too, with the performance hint API (API 33) beside it (`ndk:weak-api`). With the font list it gets past its font thread and dies on its launcher thread: libxul's sized delete, imported as `_ZdlPvm@libmozglue.so`, bound to a libc++'s, which handed musl's free memory mozjemalloc had allocated. `abi:versioned-import-clash` had listed the operators among the open imports; the shim now forwards them to libmozglue too. In its test Fennec draws, for the first time on Westlake, and again in a second test |
| econverter, werewolvesgame | SIGSEGV in libpython; bound with no blocker | Chaquopy's written libraries load a second copy of the APK's `libpython`. The fix: the APK's own library names are shared with the default namespace; both draw in its test |
| Waze | an abort; the dump's frames lie past `libwaze.so`'s mappings, so they give no site | the runtime's init array sanitizer read all 2189 entries of the library's init array as zero (a packed-relocation table fills them) and dropped them. This is a static finding. The fix: the sanitizer knows `DT_ANDROID_RELA` (patched libart); in its test Waze draws its home screen |
| Draw Anywhere | "maximum -460" | its 180x180 overlay set the process-wide screen size to its own. The fix: the display is every window's global configuration (build 86). In its test the overlay toolbar shows over the host screen, as the app intends |
| OsmAnd | an abort: PROJ's `FactoryException`, uncaught on a Qt pool thread | open. Its init thread starts the native core (`initOpenGl`) before it copies `proj.db` and its color palettes from its assets (`reloadIndexesOnStart`). A map-engine task used PROJ before the copy, and Qt's thread pool rethrows what a task throws. In r84, without the mutex adoption, the init thread deadlocked inside `InitializeCore` before getting that far. Compiled code is not why: with its own code compiled on the host it aborts the same way, twice. What slows the copy here: Android 15 asks the storage manager isCeStorageUnlocked, which the in-process one answered only under its old name, so the user's storage read as locked, and OsmAnd's StrictMode logged a violation with its stack trace for every file it touched, 20,000 lines while it started (`os:ce-storage-unlocked`; the new name is answered in build 89). In its test OsmAnd's StrictMode logs nothing, and OsmAnd aborts the same way: the slowdown was not why. Open |
| opflashcontrol | a slider value out of range | a flashlight app on a board with no camera exposed to Android |
| musekit | "startRecording() called on an uninitialized AudioRecord" | the host HAP does not request the microphone permission |
| Element X | SIGSEGV in `libmatrix_sdk_ffi.so` | its first call over JNA, `init_platform`, finds the process's JavaVM with `dlsym(dlopen(NULL), "JNI_GetCreatedJavaVMs")`, checks the result and not the count, and takes the first JavaVM* it asked for. That resolved to libnativehelper's, which answers `JNI_OK` with no VM: appspawn-x creates the VM through a `JniInvocation` on `startVm()`'s stack, whose destructor clears libnativehelper's table. The JavaVM* was the caller's own stack, the JNIEnv from it pointed at the string "infoJson" in its `.rodata`, and `FindClass` (`[table+48]`) faulted. The fix: the preloaded shim defines `JNI_GetCreatedJavaVMs`, forwarding to libart's (`jni:created-vms`). In its test Element X draws its first screen in both launches; with the shim before it, it crashes as in r85 |
| aaaaxy | `AInputEvent_getDeviceId` missing | NativeActivity's input queue; named by `ndk:weld:input` |
| emacs | `fts_open` missing | its libselinux imports it, and OH's musl has no fts (`ndk:libc-abi`). The fix: the shim carries Bionic's fts. In its test the library loads, and Emacs stops at its first activity, which its manifest names relative to its package (`.EmacsLauncherPreferencesActivity`); the launcher passed the name on unexpanded, where Android's parser expands it (fixed in the launcher after r86) |
| facebooknotifica | "Error inflating class RingtonePreference" | its preference XML names a class its bundled androidx lacks; Android fails the same way |
| NYTimes, Flipboard | Google Play services modules | out of scope |
| TikTok | SIGSEGV in `pthread_setname_np` | above |

## Zoom

Zoom drew on build 83 with an earlier shim and stopped at bound in later tests. It draws in r85.

- **The bisect:** one launch per shim build on build 84, with that build's runtime overrides. Every
  shim through by-name loading draws. The first with routed libraries (an Android caller's `dlopen`
  answered in the Android namespace) stops at bound. One launch each, which proved too few (below).
- **The failure:** a SIGSEGV right after `libzData.so`'s first load failed on a libc++ symbol.
  Every run, the drawing ones included, sees such first failures, and in the runs that draw the
  loads go on.
- **Intermittent, whatever the shim:** on build 87, one of four launches drew (the routing shim
  with the patched libart) and three stopped at bound, both launches with r85's own shim among them.
  Each stop is a SIGSEGV on the main thread the moment `libzData.so`'s dlopen fails on a libc++
  symbol (the board's `libc++_shared.so` is found before the APK's), after which OH's crash handler
  times out waiting for its dump helper and the app dies. r85's one launch drew.
- **The row:** `load:shadowed-by-board` names the shadowed `libc++_shared.so` (missing).

## Tests of the fixes

Each test ran its apps with r85's settings except for the change under test, and compared them
with r85. Fixes reached the board in five builds, the shims and the runtime libraries:

- **Build 86:** the display as every window's global configuration; the board's Vulkan claimed.
- **Build 87:** implicit intents for the app's own activities.
- **Build 88:** the launch carries the start, so onPostCreate and onRestoreInstanceState run.
- **Build 89:** a window and its SurfaceViews' own windows one focus group; runtime permission
  requests answered in process; credential-encrypted storage unlocked under Android 15's name.
- **Build 90:** a launch with no OH ability behind it resumes in its launch transaction.
- **The shims:** libmozglue's versions and C++ operators; written libraries sharing the APK's;
  EGL looked up by handle; `pthread_create` in Bionic's order; the NDK's font list and
  performance hint API; `JNI_GetCreatedJavaVMs`; `ANativeWindow_setBuffersGeometry` in
  Android's terms; Bionic's fts; `ANativeWindow_lock` on the adapter's windows.
- **The runtime libraries:** libart's init array sanitizer for packed relocations; natives the
  runtime lacked or answered wrongly (`Process.readProcFile`, the hint manager, legacy Camera,
  `LocalSocketImpl`, `Surface.lockCanvas`, SQLite's collations).
- **The launcher:** an input cache on the board for files that do not change between launches.

| test | change | what it showed | apps that moved back |
|---|---|---|---|
| launch input cache (20 apps) | the launcher keeps the WebView files and runtime overrides on the board between launches and stages only what changed | outcomes identical to r85; with the same waits, a launch's median time fell from 140 s to 114 s (19 launches: 2905 s to 2324 s) | none |
| build 86 (30 apps) | the display as every window's global configuration; the board's Vulkan claimed, and listed with the features | duckrun and playmaker (Godot) draw; Draw Anywhere's overlay toolbar shows over the host screen, with no exception | none |
| shim: libmozglue's versions, written libraries (12 apps) | Firefox's versioned allocator imports bound to libmozglue's own; libraries written at run time share the APK's | econverter and werewolvesgame (Chaquopy) draw; Fennec gets past musl's free to a call through a null weak import (the font list, below) | none |
| libart: packed relocations (8 apps) | the init array sanitizer leaves alone a library relocated with DT_ANDROID_RELA | Waze draws its home screen; TikTok drew (its thread race went its way) | none |
| shim: EGL by handle (12 apps) | an Android library's dlopen of libEGL.so gets the runtime's EGL, and its lookups of eglCreateWindowSurface and eglTerminate by handle get the shim's | no SDL app aborts any more: anarchre and diesimu render into their SurfaceView's OH window (not shown); supertuxkart reaches a PNG load (interposed libpng) | none |
| shim: pthread_create in Bionic's order (18 apps, TikTok 3 times) | an Android caller's new thread waits until pthread_create has stored its handle | TikTok draws in all three runs (r85: runtime-init). CapCut and Zoom stop at bound: each took a SIGSEGV its own handler survives in other runs, and OH's crash handler timed out waiting for its dump helper ("waitpid timeout"), which no run before this shim showed. CapCut drew in all five launches of a test that alternated the shims, and Zoom stops as often without the wrapper: neither stop is the wrapper's | none attributable |
| build 87 (27 apps) | implicit intents for the app's own activities, resolved from its manifest filters; startActivity makes such an intent explicit | Shazam draws its home screen (r85: it finished itself); all 25 controls draw; Fossify Messages still closes for want of an SMS role, a device's answer | none |
| Zoom: shim and libart (4 launches on build 87) | the routing shim with the patched libart, and r85's shim with the libart before it, twice each | one launch of the first drew; the other three stopped at bound, each faulting as libzData.so's dlopen failed on a libc++ symbol, with OH's crash handler timing out. Zoom is intermittent whatever the shim | none attributable |
| host-compiled app code (10 apps, build 87) | each app's dex compiled on the host against build 87's speed boot image, with explicit null and suspend checks | the nine that drew reached their first resume 1.5-5x sooner: Spotify 14.7 s to 1.5 s, CNN 11.1 to 1.7, Uber 15.0 to 3.1, CapCut 24.1 to 5.3 (its first frame 33.8 to 8.0), DuckDuckGo 7.6 to 1.9, Citymapper 4.8 to 1.4, StreetComplete 4.4 to 1.2, X 4.4 to 1.6, Instagram 13.4 to 9.0 | none attributable (Zoom: intermittent) |
| missing natives (10 apps, build 87) | Process.readProcFile and parseProcLine, PerformanceHintManager.nativeAcquireManager answering no manager, Camera.native_release | WhatsApp, Messenger and Open Camera no longer throw UnsatisfiedLinkError on the calling thread; all three, and the controls, draw with no blocker left | none |
| OsmAnd with its code compiled on the host (2 launches, build 87) | its dex compiled against build 87's boot image | both abort as in r85: PROJ's FactoryException, uncaught on a Qt pool thread. Compiled code does not decide the race | none (no gain) |
| shim: the NDK's font list and performance hint API (Fennec twice, build 87) | ASystemFontIterator and AFont from the runtime's fonts; APerformanceHint answering a device with no hint service | Fennec gets past its font thread (r85: runtime-init) in both launches and stops at view: SIGSEGV in musl's free from libxul's sized delete (next: libmozglue's C++ operators) | none |
| LocalSocketImpl natives (5 apps, build 87) | connect, bind, read, write and peer credentials for android.net.LocalSocket, with descriptor passing | TikTok's local socket server binds and waits in accept (in the pthread_create test bindLocal had thrown UnsatisfiedLinkError on its thread); TikTok, CapCut, Element and the missing-natives test's apps draw | none |
| routing to the Android namespace (supertuxkart, PPSSPP; build 87) | the gap map's remedy for load:interposed-by-runtime, applied: the game's libraries load in the Android namespace, where the runtime's libraries are not global | PPSSPP no longer crashes in libhwui; its UI shows faintly over the host screen. supertuxkart gets past libpng and shows SDL's error dialog: the runtime's libGLESv1_CM.so needs OH's libGLES_mali.z.so, which the Android namespace does not reach (its search path has no vendor directory, and the driver is not among the libraries it shares with its parent). The harness read the dialog as drawing | none (no gain yet) |
| CapCut with and without the pthread_create wrapper (5 launches alternated, build 86) | the wrapper's shim three times, r85's shim twice | all five draw. Thread-13's fault comes every time; OH's crash handler finishes its dump each time and CapCut's own handler recovers. The pthread_create test's stop, the dump timing out, was chance: the wrapper stays | none |
| build 88 (34 apps) | the launch carries the start: onStart, onRestoreInstanceState and onPostCreate in Android's order | linphone draws (r85: its window never drew); Shazam draws (build 87). Reddit held its splash and drew nothing within the run: its splash state, which its onPostCreate now arms (as on Android), waits on requests to its own servers, and reddit.com is not reliably reachable from the board's network (one launch got a Meta address for it from the board's DNS). Fossify Messages closes itself as before | none attributable (Reddit: its network) |
| build 89 (26 apps, Reddit twice) | a window and its SurfaceViews' windows one focus group; permission requests answered; credential-encrypted storage unlocked under Android 15's name | linphone, duckrun and playmaker draw. anarchre and diesimu keep their activity's focus and still show nothing. OsmAnd's StrictMode logs nothing (r85: 20,724 lines) and it aborts as before. ssh, Element and aat, which ask for permissions, draw as before. Reddit drew in one launch of two, its second activity 37 s in | none attributable (Reddit: its network) |
| shim: JNI_GetCreatedJavaVMs from libart (13 launches, build 87) | the preloaded shim defines it for every caller, forwarding to libart's, which answers from the Runtime | Element X draws in both launches (r85: SIGSEGV in libmatrix_sdk_ffi.so); with the shim before it, it crashes as in r85; noice, Element, Telegram, WhatsApp, Discord, Instagram, Mindustry, Threads, X and Spotify draw | none |
| shim: libmozglue's C++ operators by version (2 launches, build 87; cut short) | the shim forwards libxul's operator new and delete imports, versioned against libmozglue, to libmozglue's own | Fennec draws (r85: runtime-init), for the first time; Telegram draws. The board dropped off hdc before WhatsApp, Discord and the second Fennec launch | none |
| build 90 (37 apps, Reddit three times) | a launch with no OH ability behind it resumes in its launch transaction, as Android's does | 35 draw, linphone and Shazam among them; Fossify Messages closes for want of an SMS role; Reddit holds its splash in all three launches (its network) | none attributable |
| shim: setBuffersGeometry in Android's terms, Bionic's fts (20 apps, build 90; SDL apps also with the shim before) | an app library's ANativeWindow_setBuffersGeometry keeps the window's size for 0x0 and maps Android's format numbers; fts_open and the rest from Bionic | anarchre and diesimu draw (r85: GL aborts, then no buffers): no buffer request fails; with the shim before, both fail every request. Fennec draws again. Emacs loads its library and stops at an activity named relative to its package. Organic Maps, mpv, VLC, miniter, linphone and the controls draw | none |
| software windows and SQLite collations (28 apps, build 90) | the shim's ANativeWindow_lock and unlockAndPost on the adapter's windows; Surface.lockCanvas over them; SQLiteConnection's natives registering UNICODE, LOCALIZED and PHONEBOOK over ICU | nounours's bear shows (r85: a transparent hole); Fossify Notes logs no collation error and opens its editor; droidify and ncnotes, which sort with LOCALIZED, draw; the games, players and gif views that name lockCanvas, the Flutter apps and the controls draw | none |

## Harness changes

This round's rows, each from a cause r84 or r85 found on the board:

| row | what it reads | what it names |
|---|---|---|
| `feature:android.hardware.vulkan.version` | apps that ask for the Vulkan feature, against the runtime's Vulkan loader | Godot (duckrun, playmaker): contradicted while the feature is absent and libvulkan answers |
| `abi:versioned-import-clash` | imports versioned against the app's own libraries that the board also defines unversioned | Fennec's `free@libmozglue.so` |
| `load:written-needs-packaged` | libraries the app writes at run time whose dependencies it packages | econverter and werewolvesgame (Chaquopy) |
| `am:type-defaults` | ActivityManager calls the in-process stand-in answers with a type default, against the AIDL's documented answers | none in r85 |
| `load:packed-init-array` | init arrays that only Android's packed relocations fill, against the runtime's init array sanitizer | Waze, among five |
| `egl:by-handle` | EGL entry points native code looks up by name instead of importing | the four SDL apps |
| `abi:thread-handle-order` | `pthread_create(&obj->thread, ..., obj)` | TikTok's vcbasekit, in 46 apps |
| `abi:bionic-tls-slots` | loads from Bionic's TLS slots above the thread pointer, the stack guard aside | CapCut's security library (below), in 7 apps |
| `ndk:weak-api` | weak NDK imports nothing on the board defines; the loader binds them to 0 | Fennec's font list (below) |
| `am:own-implicit-intents` | the schemes and actions only the app's own activity filters declare, named by its dex | Shazam |
| `jni:created-vms` | native code that imports `JNI_GetCreatedJavaVMs` or names it for a dlsym, against the shim defining it | Element X; also libraries in Telegram (language ID), Transit (TFLite) and VLC, used past the first screen |
| `window:surfaceview-focus` | an engine that renders only with focus, in a provider that gives its SurfaceView an OH window of its own | anarchre, diesimu |
| `am:permission-request` | `Activity.requestPermissions`, against an activity task manager that answers it | the five apps that asked |
| `os:ce-storage-unlocked` | apps that enable StrictMode's VM checks, against a storage manager that answers Android 15's isCeStorageUnlocked | OsmAnd, Felicity |
| `am:post-create` | the app's own activity code in `onPostCreate` or `onRestoreInstanceState`, against a launch transaction that carries the start | linphone |
| `window:buffers-geometry` | native code that imports `ANativeWindow_setBuffersGeometry`, against a shim that answers it in Android's terms (0x0 is the window's size; Android's format numbers) | anarchre, diesimu (SDL) |
| `window:software-canvas` | `lockCanvas` calls and `ANativeWindow_lock` imports, against a provider whose lock hands back a buffer | nounours |
| `db:sqlite-collations` | SQL in the app's dex that names `COLLATE UNICODE`, `LOCALIZED` or `PHONEBOOK`, against a provider that registers them over ICU | Fossify Notes (UNICODE); five apps sort with LOCALIZED |
| `window:engine-surface` (extended) | also an app's own GL renderer in a GLSurfaceView, which no engine library names | usp |

And in how the harness reads a run:
- **The main thread** is the one running `ActivityThread.main`. The VM starts on a worker pthread,
  and tid 1 can be any thread: cclauncher's "parked main thread" was a WorkManager pool thread.
- **Detection:** libraries loaded from Java under a computed name, and Chaquopy's, are found by what
  the scan can see.
- **Service requests** whose manager class R8 outlined into a method of its own are followed.
- **A device's answer:** an in-process service that answers only defaults, under a comment that
  states an absence, gives its row that answer. The scorer counts an exit after such a call as the
  device's answer.
- **Version clashes, name by name:** the versioned-import row had counted libmozglue's version as
  supplied once the shim defined that version at all. The shim forwards the calls it lists, and
  Fennec's sized delete still bound to a libc++'s. The row now checks each name against the
  forwarders the shim defines.
- **No frame:** an activity whose first-frame report was the adapter's timeout, with the host screen
  behind it, resumed and never drew (from build 88's logs). The scorer looks for what holds its
  draws. Start-up times leave the timeout out.
- **The screenshot** has a third state: the host screen with the app's content over part of it
  (an overlay, or a window transparent where it draws nothing). It counts as on screen.
- **Window buffers:** a window whose buffer requests OH refused (native_window's RequestBuffer
  error in the app's hilog), with the host screen showing, is the `window-buffers` blocker, which
  the scorer matches to `window:buffers-geometry`.
- **Crash frames** past their file's mappings are marked, and no longer read as a site in that
  file (5 of r85's 15 dumps). An app library's faulting frame takes its offset from the pc register
  and the dump's maps: the dump had printed CapCut's at 0x1756ec (in `.rodata`) and 0x215d6ec for
  a store at 0x15b6ec.
- **musl's allocator:** a fault in `get_meta`, mallocng's check of the chunk it is handed, reads as
  memory musl's heap never allocated, or a corrupt heap (Fennec).
- **Scoring native crashes:** rows about a library's own risk list it (`libraries`). A row about one
  kind of call also gives the frames such a crash shows (`crash_symbols`). The interposition row
  gives the runtime libraries whose copies take an app library's symbols over (`crash_libraries`).
