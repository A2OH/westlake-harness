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

## Results

Seven launches on the OH board. The first ran on Westlake `f6dc615`, as predicted; later launches carry
the fixes below. Launches 3 to 7 ran with SELinux permissive, because under enforcing every line the
app logs is dropped (see "What the launches taught the harness"). The board was set back to
enforcing afterwards.

**Where it got to.** React Native starts, the OTA update applies, and the app's storage migrations run
(`React app started`, `[OTA] Update applied!`). The process then dies creating its first WebView,
because WebView's renderer needs a process that direct launch cannot start (B5). There is no Burger King
screen yet.

### The predictions, scored

| # | Outcome | What happened |
|---|---|---|
| overall | right effect, wrong cause | launch 1 did not reach a React Native screen, but not because of SoLoader |
| P1 | **wrong** | SoLoader loaded every library from the extracted directory (`SoLoader initialized: 8`); no zip-member load was attempted. Launch 1 did die in `MainApplication.onCreate`, for the reason in B1 |
| P2 | **wrong** | launch 1 failed on a native link: `libreactnative.so` could not relocate `std::__ndk1::__shared_weak_count::__release_weak` (B1). `oh-resolve` had counted the APK's own `libc++_shared.so` as the provider without checking which copy the loader picks. CameraX was not exercised |
| P3 | right | no `NoSuchMethodError` or `NoClassDefFoundError` from a platform API in seven launches |
| P4 | right | `providers populated: 9`: the app's 8 plus Westlake's settings provider; Firebase and Datadog providers ran |
| P5 | **wrong** | appops and locale were survived, uimode was not: React Native's `AndroidInfoModule.uiMode` casts the manager non-null (B3) |
| P6 | right | WorkManager logs `getAllPendingJobs() is not reliable on this device` (null `ParceledListSlice`) and runs nothing |
| P7 | right | "requires the Google Play Store, but it is missing", `SERVICE_INVALID`, no crash |
| P8 | right | no symlink or fifo was created in app data across the permissive launches |
| P9 | not reached | |
| P10 | right | the app's native "Something went wrong" dialog (launches 4 and 5): centred, dimmed, above the activity |
| P11 | **wrong** | the first WebView aborts the process twice over: B4, then B5 |
| P12 | not reached | |

Six right, four wrong, two not reached. All four wrong ones were startup blockers, and every one
was a claim that something would be fine.

### Blockers, in the order they surfaced

[blockers.json](blockers.json). The "row" column is the row that should have flagged it.

| | Launch | Symptom | Row in the blind map | Fix |
|---|---|---|---|---|
| B1 | 1 | `libc++_shared.so` resolves to `/system/lib64`'s copy, which the child's search path puts first | none | isolate 20 libraries in the Android namespace (launcher option) |
| B2 | 3 | `AndroidKeyStore not found` while the JS bundle loads; ReactHost tears down | none | westlake `21fdcda`: software AndroidKeyStore provider |
| B3 | 5 | `null cannot be cast to non-null type android.app.UiModeManager` in a JS host function | `svc:uimode` null, judged survivable | westlake `d689e67`: uimode, power, alarm, clipboard in process |
| B4 | 6 | WebView's policy read hits the in-process `IUserManager`, which throws; Chromium aborts | `svc:user` "hollow": wrong, the runtime replaces that binder with one that throws | westlake `9b8b861`: restriction and profile answers |
| B5 | 7 | WebView cannot start its sandboxed renderer process; Chromium traps | none | open (L): host the renderer, or single-process WebView |

The blind map had a row for 2 of the 5. Neither row said "blocker".

### What the launches taught the harness

Each miss became a check. These checks were written after seeing the failures, so the rescan below is
a regression test, not a second blind test. The next app is the blind test for them.

| Miss | New check | Row |
|---|---|---|
| B1: a symbol that resolves in the APK can still bind to the board's library | packaged libraries whose name a board library in an earlier search directory shadows, and every APK library whose DT_NEEDED graph reaches one (`gap-map --board-libs`) | `load:shadowed-by-board`, with the exact `--android-native-target` list; launches 4 to 7 used it |
| B2: a class that exists says nothing about a provider selected by name | the scanner records JCA `getInstance(type, provider)` calls and the `"AndroidKeyStore"` constant; the model looks for who installs such a provider | `jca:AndroidKeyStore` (new category: keystore and crypto providers) |
| B3: "null service" rows cannot say whether a null is survived | the scanner records Kotlin's `null cannot be cast to non-null type android.…` messages: each is a site that throws on null | null services now say how many methods throw, and which (uimode 2, alarm 4, power 2, clipboard 1) |
| B4: the service model read only the seeded binder | binders published into `ServiceManager.sCache` anywhere in the tree; a proxy that throws by default gets its own verdict | `svc:user` **strict**: answers N methods, every other call throws |
| B5: nothing modelled WebView's process | reads AOSP `WebViewDelegate.isMultiProcessEnabled()` (true under `Flags.updateServiceV2()`, whatever the update service answers) and looks for renderer hosting in Westlake | `wv:renderer-process` missing, L |

Backtest with the new checks, same APK, same provider (`f6dc615`): **5 of 5**
([map-rescan](map-rescan/GAP-MAP.md)). Against the fixed tree `9b8b861`
([map-fixed](map-fixed/GAP-MAP.md)), B2 and B3 are closed. B1 is left as configuration the launcher
does not yet do by itself. B4 is partly closed: `user` still throws for methods nobody has asked for.
B5 is open.

Two gaps in what the harness can see, still open:

- **Under enforcing, the app's log is lost.** The child inherits the spawner's `su`-labelled log
  socket, and every write is denied. The JS error behind B2 was invisible until the board went
  permissive. This is a defect in the measurement, not in a contract.
- **WebView's own code is not scanned.** B4's caller was Chromium, not the app. The WebView APK is a
  runtime input and could be scanned like an app.

The rescans need a scan made with this harness version: rerun `scan` on the pinned XAPK.
`burgerking-scan.json` is the scan the blind predictions were made from.
