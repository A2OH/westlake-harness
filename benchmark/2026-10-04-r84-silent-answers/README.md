# r84: answers that were never errors (2026-10-04)

r84 reran the whole corpus (329 apps) on build 80. Build 80 is build 79 with its boot image compiled
at "speed", with explicit null and suspend checks (see the r83 record).

Most of what kept r84's apps from drawing came back as an answer, not as an error:
- a mutex that was not recursive;
- a free-space query that answered 0;
- an ActivityManager call answered with null;
- a launcher activity told it was not its task's root, so it closed itself.

Nothing failed to load, and no exception named the cause where it happened. This record covers what
the harness now sees of them and what the fixes did on the board.

Files, made with today's harness:
- `r84-lifecycle.json`: r84 classified
  (`python -m harness.westlake_gap.lifecycle <logs> --json r84-lifecycle.json`).
- `r84-score.json`: its first blockers scored against gap maps made with today's harness, against
  r84's own provider (`scripts/score_first_blockers.py`).

## Regression check against r83

- **Coverage:** 327 of 329 apps ran. Two launches were lost before the app started (bim,
  citymapper). Both were rerun with the fixes below.
- **Stages:** no app moved back a stage.
- **Up:** 14 apps moved up.
  - WhatsApp, Threads, Messenger, Files and Rethink now draw.
  - CapCut, Instagram, Discord and six more reach their view.
- **Drawing:** 276 (r83: 272).

## Start-up

From each app's own hilog, for the 295 apps whose activity drew a first frame:
- median 1.86 s from process start;
- 173 within 2 s, 278 within 5 s;
- 6 over 10 s. Four of those six are explained below:

| app | first frame | why |
|---|---|---|
| Discord | 62.9 s | its crash reporter's init deadlocked (static mutexes, below), and its main thread waited out two 30 s timeouts |
| FairScan | 36.8 s | CameraX init failed on a null DevicePolicyManager, then waited 30 s on the main thread |
| CapCut | 15.1 s | then finished itself: the task-root check |
| Instagram | 14.3 s | the same |

## What stopped the 51 apps short of drawing

r84's first blockers were scored against gap maps made with today's harness, using r84's provider:
- **Scorable:** 20 of 51. **Named:** 17, a row that is not supplied names the blocker.
- **Not named:** 3, listed in the table below.
- **Marked supplied:** none.
- Before today's changes, 11 were scorable and all 11 named.

Not named:

| app | blocker | why no row names it |
|---|---|---|
| Shortcut | its activity forwards to another app and finishes | no row covers handing off to an app that is not installed |
| Draw Anywhere | it starts its overlay service and finishes | covered from today's map on (`am:in-app-services`, below); the overlay window itself is not |
| AndStatus | its first activity waits for defaults that are never set, then finishes | its Want carried the action under OH's prefix (fixed in build 82) |

The 31 unscorable apps are app exceptions and native crashes without a platform symbol. Their root
causes are below.

## Five silent answers

### A recursive mutex that musl locked as a normal one: Discord

Discord's `CrashReportingInitThread` never left `initSentryNative`, and its main thread waited
twice for "application initialization".

- **The mechanism:**
  - Bionic's `PTHREAD_RECURSIVE_MUTEX_INITIALIZER` puts the mutex type in bits 14-15 of the
    first word: 0x4000. The error-checking initializer gives 0x8000.
  - musl reads its type from the low bits, so both lock as normal mutexes.
  - sentry-native's `sentry_init` holds its options lock and takes it again in `sentry_close`,
    and so deadlocked on its own thread.
- **The fix:** the bionic shim now exports `pthread_mutex_lock` and `pthread_mutex_trylock`.
  Before musl sees an unlocked mutex holding either word, they give it musl's type.
- **The row:** `abi:static-mutex-init`.
  - The scanner counts an initializer in `.data` only when the library's code builds its
    address right before a lock call (adrp/add, a mov, or a GOT load).
  - The bare pattern matches about 60 times in libpython and is never locked there.
  - Confirmed users: libsentry (Discord, AdAway, Blockads, Element, Element X), LinkedIn's
    libsecsdk, TikTok's libjarvis-trace.

### A native registered as "return 0": CNN

CNN's Application sized its OkHttp cache at half of `/data`'s usable space and died on
"maxSize <= 0".

- **The cause:** the runtime's openjdk stub registers `UnixFileSystem.getSpace0` with a body
  that returns 0. `File.getTotalSpace`, `getFreeSpace` and `getUsableSpace` answered 0 for every
  path. 95 of 329 corpus apps call one of them.
- **The fix:** the missing-natives library binds libcore's implementation (statvfs) over the stub.
- **The row:** `runtime:stub-natives`. It reads the stub for natives whose body only returns a
  constant, and the natives library for the ones bound over them.

### Activities told they were not their task's root

Before build 81, `getTaskForActivity` answered -1 for every activity, so `Activity.isTaskRoot()`
was false. Five apps' launcher activities checked it and finished as soon as they resumed:
Instagram, CapCut, Shazam, fmessages and RedReader.

- **The fix:** the activity client controller keeps the app's one task (build 81).
- **Seeing it:** the lifecycle classifier now names this directly. It reads the adapter's
  `activityResumed` and `finishActivity` lines in the app's hilog: the last activity the app
  resumed finished itself, and none took over.
  - Nine r84 apps did this, and their blockers had read as idle main threads.
  - The scorer looks such a blocker up in `am:task-root` and `svc:bluetooth`. Beatbridge closes
    on a device without Bluetooth.

### What a stand-in for system_server answered as nothing

In direct launch, a `java.lang.reflect.Proxy` stands in for IActivityManager. A method its handler
does not name returns a type default.

| call | default | effect | corpus apps |
|---|---|---|---|
| `startService`, `startForegroundService` | null: "no such service" | the app's own started services never ran | 243 (`am:in-app-services`) |
| `registerReceiver`, `sendBroadcast` | null, nothing delivered | no sticky intent (`registerReceiver(null, BATTERY_CHANGED)`), the app's own broadcasts lost | 295 (`am:broadcasts`) |
| `getMemoryInfo` | the struct untouched | totalMem, availMem and threshold read 0 | 96 (`am:memory-info`) |

The task manager adapter answered `getRunningTasks` and `getAppTasks` with empty lists, and
`getRecentTasks` with null. An app sees its own task there (`am:own-task`, 38 apps).

Each now has an in-process answer:
- services are created once, with `onStartCommand` per start and the stop rules AOSP applies;
- registrations are kept, and the app's broadcasts delivered to the matching ones;
- memory is reported from `/proc/meminfo` with ProcessList's levels;
- task queries report the app's task.

### The rest of the root causes

| app | root cause | fix |
|---|---|---|
| clauncher, otgmaster, Internet Radio, onloc, linphone | a null DevicePolicyManager, UsbManager, NsdManager or UsageStatsManager used unchecked | answered in process (build 82) |
| FairScan, Open Camera, opflashcontrol | camera claimed with no camera service; legacy Camera natives missing | no camera claimed; the natives answer for a device without one |
| aat, Spotify | window metrics 0x0 before the first layout | bounds in the bind-time configuration (build 82) |
| ScrambledExif | application label read from labelRes, zeroed at launch | Android resource ids kept |
| LibreTube | cache quota 0 | StorageStatsService's 64 MiB default |
| quitter | a provider whose authority a disabled one already held | authorities claimed in manifest order |
| Fossify Voice Recorder, Nounours | MediaPlayer stopped before prepare threw | MEDIA_ERROR(-38), as AOSP's JNI posts it |
| Fennec (and FairScan, which drew anyway) | libmediandk.so missing | the NDK media library (build 83) |
| duckrun, playmaker | libcamera2ndk.so missing | the NDK camera library (build 83) |
| diesimu, supertuxkart, infraarcana, anarchre | libGLESv1_CM.so missing for SDL | GLES 1 over the board's Mali driver (build 83) |
| econverter, werewolvesgame, Translator | a library loaded twice (by path, then by name) | app libraries opened by name |
| Instagram (after the task-root fix) | ModalActivity's onCreate ran inside its caller's `startActivity` | the app's own activities start after the caller's message (build 84) |
| Element X | a pointer read from string data in `libmatrix_sdk_ffi.so` | open |
| Waze | an abort in its own stripped `libwaze.so` right after its common init | open |
| usp | its SurfaceView shares the window's native window, and hwui aborts with no surface | open: SurfaceView needs its own OH surface |
| NYTimes, Flipboard | Google Play services modules and the WebView provider | out of scope |

## Classifier fixes

- **Exception names:** the blocker patterns took an exception name as one or more characters
  before "Exception". `java.lang.Exception` never matched, and Fennec scored with no blocker.
- **Root causes:** they are now recorded whether or not the log reached drawing. onloc drew, then
  threw, and its screenshot is the host screen.

## Tests of the fixes

Each test ran its apps with r84's settings except for the change under test, and compared them
with r84. Fixes reached the board in five builds, the shims and one runtime patch:

- **Build 81:** the task model.
- **Build 82:** in-process services, features, Want actions, window bounds, provider authorities,
  label ids and the cache quota.
- **Build 83:** the NDK camera, media and GLES 1 libraries.
- **Build 84:** asynchronous starts of the app's own activities; in-process started services,
  broadcasts, memory info and task queries; Bluetooth present and off.
- **Build 85:** the app's own Intent handed to its in-process launch.
- **The shims:** signal and loader fixes, then the static-mutex adoption.
- **The runtime:** the thread-priority answer of ART's palette (a patched libart).

| test | change | apps that moved up | apps that moved back |
|---|---|---|---|
| shim: signals, symbol versions | bytesig's libc handle, LIBC_O/LIBC_Q versions | TikTok (runtime-init to drawing) | none |
| routing | PPSSPP's library in the Android namespace | PPSSPP no longer crashes in libhwui's VMA; draws, its surface not composited | none |
| build 81 | the task model | Instagram stops finishing itself (then the in-place launch, below) | none |
| build 82 (42 apps) | services, features, Want actions, bounds | AndStatus, Internet Radio, LibreTube, onloc draw; aat, clauncher, linphone reach their view; FairScan's first frame 36.8 s to 1.5 s | none |
| build 83 (15 apps) | NDK camera, media, GLES 1 | Spotify draws; duckrun, playmaker, linphone reach their view | none |
| MediaPlayer states | MEDIA_ERROR(-38) instead of throwing | Fossify Voice Recorder draws; Nounours reaches its view (its content is a SurfaceView) | none |
| shim: native EGL windows, AConfiguration | Flutter's Skia renderer, SDL | Cards with Cats, Mobile v2, Mouse Pounce draw | anarchre, supertuxkart: in r84 they "drew" SDL's error dialog; now SDL loads and aborts in the Mali driver |
| shim: loading by name | routed libraries answered in the Android namespace | Translator draws | none (the by-name check never succeeded on the board, below) |
| build 83 (20 apps) | authorities, usb, labels, task ids, bounds | otgmaster, quitter, RedReader, ScrambledExif, Spotify, wormhole draw; Open Camera reaches its view | none |
| ByteDance and Meta | build 83 with the shim fixes | CapCut draws its home screen; TikTok draws | none |
| shim: static mutexes (20 apps) | 0x4000/0x8000 adopted before musl locks | Discord's first frame 62.9 s to 1.98 s | OsmAnd, Zoom (below) |
| File space natives (12 apps) | getSpace0 from statvfs | CNN draws | none |
| build 84 (31 apps) | own activities started after the caller's message; services, broadcasts, memory info, task queries in process; Bluetooth present and off | aat, AndStatus, Beatbridge, CNN, Discord, TikTok draw | K-9 (below); CapCut, Instagram, Draw Anywhere stopped later than before (below) |
| shim: by-name check, AHardwareBuffer socket calls | RTLD_NOLOAD instead of dlinfo | TikTok draws; Fennec's libxul loads (then a SIGSEGV in musl) | OsmAnd (the mutex adoption) |
| A/B: OsmAnd and Zoom with and without the mutex adoption | | | OsmAnd draws without it and aborts with it; Zoom stops at bound with both |
| build 85 and the priority answer (19 apps) | the app's own Intent for its launch; NORM_PRIORITY for attached threads | aat, AndStatus, Beatbridge, CapCut, CNN, Discord, Instagram and TikTok draw; K-9 draws again | none; Draw Anywhere still stops at its overlay windows |

### What running more of the app turned up

Started services that now run, broadcasts that now arrive and recursive locks that now recurse each
let an app go further, and some then failed further on:

- **K-9:** its `DatabaseUpgradeService` now runs. When it finished, `UpgradeDatabaseActivity`
  started the intent it had been handed, and that intent was null.
  - The cause: an in-process launch of the app's own activity went out through OH's Want and was
    rebuilt from its JSON. JSON keeps strings and numbers but not Parcelable extras, and the
    activity's undotted action `upgrade_databases` came back under OH's prefix.
  - Instagram's `ModalActivity` failed the same way: "Required value was null" in onCreate.
  - Build 85 hands such a launch the Intent the app passed, copied when `startActivity` is
    called. With it, K-9 and Instagram draw.
- **CapCut:** a thread pool restored a saved priority of 0 and threw "Priority out of range: 0".
  - The cause: ART asks its palette for the Java priority of a thread it attaches, and the
    runtime's palette stub answered 0.
  - The fix: the stub now answers NORM_PRIORITY. The deployed libart was recovered from a board
    stage and has no build tree, so it is patched in place, four instructions.
  - With the patch CapCut draws its home screen. A SIGSEGV then hits a worker thread in
    `libmetasec_ov.so`, ByteDance's security library. This is open.
- **Draw Anywhere:** its overlay service now runs and adds its windows (TYPE_APPLICATION_OVERLAY,
  no token). The windows get no display-sized frame, so its placement math went negative. This is
  open: overlay windows.
- **OsmAnd:** this is our reading, not yet verified.
  - Its map engine's PROJ guards its globals with `core_lock`, a static mutex with Bionic's
    recursive initializer.
  - musl locked it as a normal mutex. With the adoption it recurses, and PROJ then reports
    "Cannot find proj.db" in an exception nothing catches.
  - The app ships `assets/proj.db` and points PROJ at a copy. Whether the copy is missing or late
    is not known yet.
  - The A/B is deterministic: it draws without the adoption and aborts with it.
- **Zoom:** it drew on build 83 with the earlier shim, and stops at bound with every shim since. A
  SIGSEGV hits its main thread just after its libraries load through the routed-dlopen redirect.
  This is open; the next step is bisecting the shim changes.

### Loading by name never took effect

The shim opens an app library by name when that name finds the staged file, so that musl records the
library's short name and later DT_NEEDED entries match it.

- **The check failed every time.** It confirmed the name opened the same file through
  `dlinfo(RTLD_DI_LINKMAP)`.
  - OH's `dlopen` returns a random handle mapped to the library, and musl's `dlinfo` rejects it as
    invalid.
  - So every library fell back to its path, and econverter's Chaquopy libraries crashed as before.
- **The harness missed it.** It marked the row supplied because it found the function in the
  source.
- **The fix:** the check now re-opens the path with `RTLD_NOLOAD` and compares handles. OH's
  loader keeps one handle per library.
