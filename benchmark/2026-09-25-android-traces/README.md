# Android startup traces and OH launch events, 101 apps (framework 57)

The gap map lists what an app needs that the provider lacks, but it cannot say whether the app
needs it *before its first screen*. This round records that on real Android and scores the map
again against what the OH board showed.

- **Android side.** A cold start of each APK on an Android 15 `userdebug` phone (OnePlus 6),
  recorded with ART method tracing for its first 25 s:
  `am start-activity -W -S --start-profiler <file> --streaming -n <pkg>/<activity>`. Each trace
  (16–460 MB) went through `trace-observe` and was deleted. The app's own native libraries
  loaded by then were read from `/proc/<pid>/maps`, including libraries mapped straight out of
  the APK (matched to zip entries by offset). The phone had network through adb reverse
  tethering. 100 of 101 apps were traced; Termux clashed with a differently signed copy
  already installed on the phone.
- **Maps.** Every map was re-made with `gap-map --observed`, which marks each row
  `observed.on_path` when the recorded run reached it.
- **OH side.** All 101 apps relaunched on framework 57; `scripts/oh_events.py` turned each
  launch log into ordered events and a root cause.

`score-observed.txt` is the output of `scripts/score_observed.py`: every check family and the
predictor, scored on all rows (static) and on only the rows on the traced path. `apps.json` is
the per-app record: board outcome, trace size and scope, rows on the path, both predictions,
and the OH stage reached with its root cause.

## Results

24 of the 100 traced apps are blocked on the board, 76 draw.

| | static | on the traced path |
|---|---|---|
| predictor, before this round | precision 0.69, recall 0.38 (9 / 4 false) | precision 0.82, recall 0.38 (9 / 2 false) |
| predictor, with this round's rows | precision 0.71, recall 0.42 (10 / 4 false) | **precision 0.82, recall 0.58 (14 / 3 false)** |

Per check, blocked / drawing apps flagged:

| check | static | on the path |
|---|---|---|
| ICU locale display names (new) | 16 / 51 | **3 / 0** |
| framework class initializer native unregistered | 20 / 69 | 2 / 2 |
| framework natives, any unregistered | 22 / 70 | 10 / 17 |
| NDK name looked up at run time | 6 / 5 | 6 / 2 |
| unresolved NDK/libc import | 2 / 7 | 2 / 1 |
| engine draws into its own SurfaceView | 7 / 1 | 7 / 1 |
| services null/hollow/strict | 23 / 74 | 19 / 59 |

- **The trace removes false alarms, not detections.** Gallery and Home Assistant stop being
  flagged: their NDK lookups and imports sit in code that does not run at startup. Every
  blocked app flagged statically is still flagged on the path.
- **Class-initializer natives were mostly noise.** They flagged 20 blocked apps, but only 2
  of those apps touched the class at startup; the other 18 are blocked by something else.
- **A family that is useless statically can be exact on the path.** 67 of 100 apps reference
  `Locale.getDisplayName`; 3 call it at startup, and all 3 are blocked.

## What the OH events added

About a dozen blocked apps reached only generic rows, so no check named their blocker. Their
launch logs show a class the map had no row for: **platform calls that resolve but answer
wrongly on this runtime**.

- `data:tzdata`: DuckDuckGo, `ZoneRulesException: No time-zone data files registered`.
  `LocalDate.now()` and `Clock.systemDefaultZone()` are not triggers: three apps that call
  them at startup draw.
- `data:icu-locale-display`: WiFiAnalyzer, NPE inside `Locale.getDisplayName` from
  `LanguagePreference.<init>`. Breezy Weather and AndStatus also call it at startup and are
  blocked, but their logs do not show this failure, so for them it is correlation, not a
  confirmed cause.

**Correction (after this was first published).** The first version of this README blamed both
rows on ICU data never being loaded, because `libicuuc` exports no `u_setDataDirectory` and 91
of 101 launches log that. `probes/icu-data` measured it on the board and that was wrong: ICU data
loads (ICU4J has its data file, display names and French day names come out right). The two
gaps are narrower:

- **Time zones:** the runtime's `tzdata` directory is staged empty. ICU4J lists 0 zones,
  `java.util.TimeZone` answers GMT for every zone, and `java.time` registers none.
- **Locale display names:** AOSP compiles all native code with zero-initialized locals, and
  `ScopedIcuLocale` in `libicu_jni` relies on it (its `UErrorCode` is uninitialized). The
  runtime's copy was built without that, so `LocaleNative` returns null on about half of all
  calls, depending on stack contents. Rebuilt with `-ftrivial-auto-var-init=zero`, every probe
  call succeeds and WiFiAnalyzer draws. Breezy Weather then fails on
  `UserManager.getProfileType` and AndStatus leaves after drawing: Locale was not their blocker.

A runtime-data row counts in the predictor only when a trace puts it on the path.

Also added to the predictor: `sym:runtime-resolved:libnativehelper.so`. `JNI_GetCreatedJavaVMs`
is looked up by name by Rust's `jni` crate (Element X's `libmatrix_sdk_ffi`) and by VLC. It
flags 2 blocked apps and none that draw. Element X's SIGSEGV address is ASCII text, consistent
with a bad lookup.

A harness bug found on the way (fixed): `apply_observed` had no case for engine-surface,
framework-native and runtime-lookup rows, so a trace never put them on the path.

## Still missed (10)

| app | OH stage | what is known |
|---|---|---|
| OpenCamera | bound | `Camera._getNumberOfCameras` unregistered: framework-internal call, invisible to the trace summary (below) |
| Scrambled Exif | bound | app name null: the launch path zeroes `labelRes` |
| LibreTube | runtime-init | Coil disk cache `size must be > 0` |
| Rethink | bound | stops after bind, nothing logged |
| Voice Recorder | view | window held back: no surface until its activity's window has an OH session |
| Fossify Messages | view | stalls after its fixed RoleManager blocker; next cause not identified |
| GPS Cockpit, Nextcloud, StreetComplete | drawing | draw something, but not the app's screen |
| OsmAnd | view | unstable across builds |

## Limits

- **In sample.** The new rows and the predictor change were chosen by looking at these same
  apps. The next batch is their test.
- **The trace summary drops framework-internal calls.** `observed.json` keeps the platform
  members the app's own code references and the names of platform classes that ran. It
  cannot say whether the framework itself called a missing native, as with OpenCamera.
  Keeping executed platform methods in `trace-observe` needs a re-trace.
- **One run per app, first 25 s.** The phone's network (tethered) and locale differ from the
  board's.
