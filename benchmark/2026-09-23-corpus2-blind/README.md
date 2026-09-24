# Ten more apps: blind predictions from the map, then the launches

The first loop corpus reached 8 of 10. This one tests whether the harness predicts, rather than
discovers. Ten popular F-Droid apps, each with surfaces the first ten did not cover. Every app was
run through the whole pipeline and predicted **before any launch**. The score is added after the
launches, without editing the predictions.

Provider: Westlake main at `0b5c9af`: framework build 38, native runtime with the Java OpenGL
bindings, and the bionic shim with the OpenSL ES translation layer. The board is OpenHarmony
6.1.0.31, arm64.

## Corpus

Original arm64 APKs from the F-Droid main repository, unmodified. Each download's sha256 matches
the index entry ([downloads.lock.json](downloads.lock.json)).

| App | Version | Why it is here |
|---|---|---|
| VLC | 3.7.1 | libvlc native media engine, video surfaces |
| Organic Maps | 2026.08.27 | native C++ map engine drawing into a SurfaceView |
| Thunderbird | 23.0 | mail, Compose, accounts |
| KeePassDX | 4.5.4 | native crypto, file pickers |
| Fossify Gallery | 1.13.1 | MediaStore, media permissions |
| Tusky | 32.2 | Mastodon client: networking, Room, media3 |
| Element | 1.6.62 | Matrix: Rust crypto SDK, React Native pieces, WebRTC, Realm |
| FluffyChat | 2.9.5 | Flutter |
| Breezy Weather | 6.2.2 | Compose, location, WorkManager |
| Fennec (Firefox) | 156.0 | Gecko engine, multiprocess, NDK media |

## Pipeline

`snapshot-runtime` over the deployed boot jars, native runtime, bionic shim and seven OH system
libraries pulled from the board. Then, per app: `scan`, `annotate-api-levels` (28/33/34/35/36,
reference 35), `oh-resolve`, and `gap-map` with NDK coverage, the board's library listing and the
staged runtime. The maps are in [maps/](maps/).

| App | Native imports resolved | Rows | Gaps |
|---|---|---|---|
| VLC | 889 / 889 | 70 | 46 |
| Organic Maps | 307 / 307 | 49 | 27 |
| Thunderbird | 27 / 27 | 58 | 34 |
| KeePassDX | 20 / 20 | 51 | 29 |
| Fossify Gallery | 308 / 308 | 58 | 32 |
| Tusky | 133 / 133 | 56 | 32 |
| Element | 979 / 1034 | 92 | 57 |
| FluffyChat | 541 / 541 | 64 | 39 |
| Breezy Weather | 132 / 132 | 49 | 24 |
| Fennec | 1827 / 1884 | 81 | 51 |

### Three harness defects, fixed before predicting

The first maps from this corpus were wrong in ways the first corpus never exposed:

1. **Fat APKs were resolved across every ABI.** Eight of these APKs carry arm64, armv7, x86 and
   x86_64 libraries in one file. `oh-resolve` and nine `gap-map` sites read every copy, so Tusky
   was charged 12 missing `__aeabi_*` symbols that only armv7 code imports. The first corpus had
   arm64-only APKs, so this never showed. Now only the target ABI's libraries count.
2. **A guard read as a stub.** `resolveContentProvider` answers by authority (the round-2 fix),
   and calls `logStub` only when the authority is null. The model treated any `logStub` as a stub,
   so the map reported a fixed gap as open. A method is now a stub only when every return is a
   constant. Four methods changed verdict; no others moved.
3. **Another library's symbols were filed as libc.** Element's `libjsctooling.so` imports 55
   JavaScriptCore symbols from `libjsc.so`, which the APK does not ship. They were grouped as
   "bionic libc ABI: translate onto musl". They now form their own row: a library the APK needs
   but does not ship, a blocker only if something loads the importer.

## Predictions

The overall prediction: **7 of 10 draw a first screen.** Machine-readable form:
[predictions.json](predictions.json).

| # | App | Expected | Blocker | Confidence | From |
|---|---|---|---|---|---|
| A1 | VLC | onboarding draws | — | medium | all imports resolve; shadowed-library row applied |
| A2 | Organic Maps | resource screen draws, then the map fails | SurfaceView shares the activity window | medium | **not a row**: round 8 |
| A3 | Thunderbird | onboarding draws | — | medium-high | no L row on the startup path |
| A4 | KeePassDX | database selection draws | — | high | no L row |
| A5 | Fossify Gallery | main screen draws, stuck without media permission | — | medium | **not a row**: permission dialogs |
| A6 | Tusky | login screen draws | — | high | no L row |
| A7 | Element | auth splash draws | — | medium-low | shadowed-library row applied; libjsc unused under Hermes |
| A8 | FluffyChat | no Flutter frame | SurfaceView shares the activity window | medium | **not a row**: round 8 |
| A9 | Breezy Weather | first-run screen draws | — | medium-high | missing APIs are API 36, behind SDK checks |
| A10 | Fennec | dies before its first screen | libxul.so cannot link: 48 `libmediandk` symbols | medium-high | `ndk:weld:media` |

Launch configuration follows the map. Each library a `load:shadowed-by-board` row lists is
launched in the Android namespace (VLC 4, Element 9). The three launchers that are
activity-aliases are launched at their target activity.

Known blind spots, stated in advance:

- No row models a SurfaceView that shares the activity's window. A2 and A8 are predicted from
  round 8, not from the map.
- Permission dialogs are not modelled.
- Which libraries load at startup is judged from the code, not from a trace.

## Results

One launch per app, same build, SELinux enforcing, 30 s wait, a screenshot each. Organic Maps
was launched twice. The first launch used my pin, which named the launcher
`DownloadResourcesActivity`: that is an activity-alias of `SplashActivity`, and no such class
exists. The harness reports alias names in `main_activities` as if they were classes, and I checked
aliases for only three apps. The second launch, at `SplashActivity`, is the one scored.

**2 of 10 draw**, against 7 predicted: KeePassDX ([shot](shots/keepassdx.jpeg)) and Organic Maps'
download screen ([shot](shots/organicmaps.jpeg)).

### The predictions, scored

| # | App | Outcome | What happened | Row in the map |
|---|---|---|---|---|
| A1 | VLC | **wrong** | `OnboardingActivity` fails to inflate: `TypedArray.getDrawable` cannot resolve a theme attribute (`0x7f040072`) of `Theme.VLC.Transparent` | none |
| A2 | Organic Maps | right (first half) | "Download the world overview map" screen draws; the map screen, where the SurfaceView gap is predicted, was not reached | — |
| A3 | Thunderbird | **wrong** | application bind fails: an NPE in `AndroidAlarmManager.<init>` behind the Koin graph (the null is not yet identified) | none |
| A4 | KeePassDX | right | database selection screen | — |
| A5 | Fossify Gallery | **wrong** | `MainActivity.onCreate` → `JobScheduler.getAllPendingJobs()` → NPE on a null `ParceledListSlice` inside `JobSchedulerImpl` | `svc:jobscheduler` hollow, M: present, judged survivable |
| A6 | Tusky | **wrong** | `TuskyApplication.onCreate` → `NotificationManager.getNotificationChannels()` → NPE on a null `ParceledListSlice` inside the manager | `svc:notification` hollow, M: present, judged survivable |
| A7 | Element | **wrong** | bind fails in an androidx.startup initializer: `EGL14._nativeClassInit` has no implementation. The GL bindings are registered after bind, but providers run during bind | none: the map says the bindings are supplied, not when |
| A8 | FluffyChat | right effect, cause probably wrong | Flutter's `1.raster` thread calls a null function (`pc=0`) right after taking the window: consistent with a runtime-resolved NDK name (`AChoreographer_*`, `ASurfaceControl_*`, `AHardwareBuffer_*`), not yet confirmed | `sym:runtime-resolved:libandroid.so` / `libnativewindow.so`, M: present, not called a blocker |
| A9 | Breezy Weather | **wrong** | `MainActivity.onCreate` → an R8 null check fires right after `locale.getApplicationLocales` (the null is not yet identified) | none |
| A10 | Fennec | right, with the cause | `GeckoLoader`: `Error loading shared library libmediandk.so (needed by libxul.so)` | `ndk:weld:media` |

Three right (A2 first half, A4, A10), one right in effect only (A8), six wrong. As in the Burger
King run, **every wrong prediction was a claim that something would be fine.**

### What the harness got wrong

1. **"Hollow" was read as survivable.** Two of the six misses (A5, A6) had a row. In both, the
   hollow binder returns null where AOSP's own manager dereferences the result
   (`ParceledListSlice.getList()`), so the throw happens inside the framework and no app code can
   catch it. Whether a hollow binder is survivable depends on the manager method, not on the service.
2. **"Supplied" does not say when.** A7: the Java OpenGL natives exist, but they are registered
   after application bind, and Element's initializer calls them during bind. The map has no notion
   of when a provider becomes available.
3. **Runtime-resolved NDK names are treated as unlikely.** A8 had the row; the prediction relied
   on the round-8 SurfaceView gap instead.
4. **Activity-aliases.** `main_activities` should resolve aliases to their target activity; it
   cost one of the ten launches.
5. **Unrowed causes** (A1 theme attribute, A3, A9): not yet understood well enough to say which
   check would have caught them.

Also found: Fennec's crash reporter calls `startActivity` from the Gecko thread, and direct launch
instantiated `StartupCrashActivity` on that thread (`addObserver must be called on the main
thread`). A Westlake defect, but secondary: it only runs after Gecko has already failed.

## After the fixes

Fixed in Westlake (branch `corpus2-fixes`), built as framework 40:

| Fix | Apps it unblocked |
|---|---|
| empty `ParceledListSlice` from the no-op JobScheduler | Fossify Gallery |
| `notification` answered in process (no channels, posts dropped) instead of the plain Binder | Tusky |
| `android.opengl.EGL14`/`EGL15`/`EGLExt` ported onto OH's EGL | Element (the first blocker) |
| PendingIntents answered in process (`LocalIntentSenders`) | Element (the second blocker), Thunderbird |

**6 of 10 now draw a first screen**: KeePassDX, Organic Maps, Fossify Gallery
([shot](shots/gallery.jpeg), "No media files have been found"), Tusky ([shot](shots/tusky.jpeg),
login), Element ([shot](shots/element.jpeg), onboarding) and Thunderbird
([shot](shots/thunderbird.jpeg)). Thunderbird's first screen is "Upgrading databases…". It
probably stays there, because `UpgradeDatabaseActivity` waits on a service started with
`startService`, which direct launch's activity manager drops. That is the next gap.

Thunderbird's null in `AndroidAlarmManager.<init>` was a null PendingIntent: the fix for Element
unblocked it too.

Regression on framework 40: aegis, anki, antennapod, markor, newpipe, ooniprobe, termux and
wikipedia draw as before (screenshots checked). Toutiao, KeePassDX and Organic Maps were not
re-run, because the host lost its connection to the board mid-run.

The harness gained the check the two service misses called for (`throws_in_framework`). Run
against the provider the predictions were made on, it flags Tusky's `getNotificationChannels`
and Gallery's `getAllPendingJobs`, plus Tusky's `getAllPendingJobs`, which would have been its
next crash. This is a backtest written after seeing the failures; the next corpus is its blind
test.

Still open: VLC's theme attribute, Breezy Weather's null after the locale call, FluffyChat's
null function on the raster thread, Fennec's `libmediandk.so`, Thunderbird's `startService`,
and `android.opengl.GLUtils`/`Matrix`/`ETC1`, which are not ported yet.
