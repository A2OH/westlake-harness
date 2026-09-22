# Burger King 7.82.0: a blind prediction, then the launch

The first app run through the whole harness before anyone launched it on OpenHarmony. The
predictions below were committed before the first launch; the score is added after it, without
editing them.

App: `com.emn8.mobilem8.nativeapp.bk` 7.82.0 (versionCode 100000516), target SDK 36, min SDK 24. A
React Native app (Hermes, Expo, Reanimated, Fresco, Nitro modules), with Firebase, ML Kit barcode,
Datadog, Braze and Amplitude. arm64 XAPK from APKPure; base and three config splits all verify and
carry the same signing certificate (`61d006c3…d2a4`).

Provider: Westlake `f6dc615`, the McDonald's sign-in build, SELinux enforcing, WebView input
supplied with the source-built bionic shim.

## What the harness says

| Step | Result |
|---|---|
| `scan` against the build's boot jars | 250 findings |
| `annotate-api-levels` (android-28/33/34/35/36, reference 35) | all 8 Java absences are Android 16 APIs: none required |
| `oh-resolve` (OH libc, GL, OpenSLES, z + the staged runtime) | 1278/1280 native imports resolved; `ANativeWindow_lock`/`unlockAndPost` missing (CameraX only) |
| `gap-map` with the probe results | 94 rows, 56 gaps ([map](map/GAP-MAP.md)); every probe-backed row supplied |
| `deploy-check` / probe suite | clean for this build (see the McDonald's benchmark) |

No Android trace exists for this app (no phone), so which gaps are on the startup path is judged
from the code, not recorded.

## Predictions

The first launch does **not** reach a React Native screen. The reason predicted is not a map row:
React Native's SoLoader loads the app's libraries from inside the APK (`<apk>!/lib/arm64-v8a/…`,
built by its obfuscated direct-APK source `com.facebook.soloader.e`), and the OH linker cannot map a
zip member. The map's native-loading row says "supplied" because the launcher extracts the
libraries, which only helps `System.loadLibrary`.

| # | Prediction | Expected | Confidence | From |
|---|---|---|---|---|
| P1 | SoLoader's direct-APK loads fail | blocker at startup unless its fallback extraction takes over | high / medium | code reading, not a row |
| P2 | no native link failure at startup; CameraX image processing cannot load | fine; camera scanning fails | high | `oh-resolve` |
| P3 | no missing platform API on the path | fine | high | API levels |
| P4 | 8 providers created at bind, Firebase and ML Kit registrars found | fine | high | probed rows |
| P5 | null power, uimode, locale, appops survived | fine | medium | service rows, McDonald's |
| P6 | WorkManager jobs never run | silent | high | `svc:jobscheduler` |
| P7 | no Google services: messaging, Google sign-in unavailable | degraded | medium | `dep:google-play-services` |
| P8 | `symlink()` denied does not matter at startup | fine | medium-low | `policy:lnk_file` |
| P9 | permission requests show no dialog; a flow waiting on one may stall | degraded or stall | low | code reading, not a row |
| P10 | dialogs stacked, centred, dimmed | fine | high | probed rows |
| P11 | React Native WebView renders | fine | medium | deploy-check |
| P12 | edge-to-edge layout under the status bar | cosmetic | low | not a row |

Machine-readable: [predictions.json](predictions.json).
