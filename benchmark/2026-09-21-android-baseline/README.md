# McDonald's on real Android: what it touches from cold start to the sign-in screen

The gap map lists what is missing. It could not say which of it stands between process start and
the first usable screen. This run removes that unknown by recording it.

**Device:** OnePlus 6 (enchilada), LineageOS 15 `userdebug`, arm64, **no Google Play services**, no
network. Userdebug makes every app traceable without Frida or Magisk. The exact four APKs the OH
board ran were installed (`install-multiple`), data cleared, and the app cold-started with full ART
method tracing. It reached `LegalRoadBlockActivity` and then `LoginRegistrationActivity`: the real
sign-in screen ("Sign in or sign up", with Facebook, Google and Email options), with no crash.

| | |
|---|---|
| methods executed | 44,451 (25,957 the app's own, the rest framework and libcore) |
| platform members touched by app code | 3,561 (2,318 executed, 1,243 referenced by a method that ran) |
| app native libraries loaded | 3 of 10: `libakamaibmp.so`, `librealm-jni.so`, `librealmc.so` |

## What it settles

- **47 of McDonald's 78 open gaps are on this path; 31 are not** (`../2026-09-21-gapmap/current/GAP-MAP.md`,
  section "Gaps on the observed path"). On path: 1×OH, 2×L, 15×M, 18×S, 11×verify.
- **All 8 failures hit on the OH board are on the observed path.** The recording points at exactly
  the places the trial and error found one launch at a time.
- **No Google Play services is not a blocker for the first screens.** 1,979 GMS client methods ran
  and the app reached sign-in anyway, on a device with no GMS at all.
- **Off the path**, so not needed for sign-in: the sensors weld and the asset/looper package (their
  libraries never load), camera, media store, mDNS, WebView members, biometrics, `clipboard`,
  `download`, `keyguard`, `vibrator`, symlinks, and 7 of the PackageManager stubs.
- Akamai's library loads and runs on real Android. On OH it self-traps and Westlake refuses it; the
  app's behaviour without it is still to be verified.

"Touched" means the call is in the trace, or a method containing the reference ran (that exact
branch may not have). It leans large, never small. It is one run of one scenario: a gap off this
path can still matter on the next screen.

## Static reachability, measured against this run

`startup-reach` stages platform touches from the bytecode alone (call graph from the manifest entry
points, rapid type analysis). Against the trace (`mcdonalds-static-reach-vs-trace.json`):

| Static set | Methods | Recall | Precision |
|---|---|---|---|
| process start | 237,516 | 81% | 8.8% |
| + first activity | 238,688 | 83% | 9.0% |
| + next screens | 319,531 | 84% | 6.8% |

Recall is fair; the 16% it misses are mostly views named only in layouts. Precision is poor: the
app uses Hilt, whose generated providers can construct every object, so nearly everything looks
reachable from `Application.onCreate`. The static pass cannot produce the short list. It stays
useful for one thing the trace cannot give: **the call chain explaining why a gap is reached**
(for JobScheduler it reproduces the board's crash stack:
`Application.onCreate → WorkManager → SystemJobScheduler → JobScheduler`).

## Reproduce

```bash
adb root
adb install-multiple base.apk split_config.arm64_v8a.apk split_config.xxxhdpi.apk split_config.en.apk
adb shell "pm clear com.mcdonalds.app; am start-activity -W -S --start-profiler /data/local/tmp/app.trace --streaming \
  -n com.mcdonalds.app/com.mcdonalds.mcdcoreapp.common.activity.SplashActivity"
# wait for the target screen, then:
adb shell am profile stop com.mcdonalds.app && adb pull /data/local/tmp/app.trace
# loaded libraries: executable mappings in /proc/<pid>/maps; with extractNativeLibs=false they are
# offsets into the split APK, resolved against its zip entries

westlake-apk-gap trace-observe app.xapk --trace app.trace --runtime runtime-index.json \
  --loaded-libs loaded.txt --scenario "cold start to sign-in" --graph-cache graph.pkl --out observed.json
westlake-apk-gap gap-map ... --observed observed.json
westlake-apk-gap startup-reach app.xapk --runtime runtime-index.json --graph-cache graph.pkl --trace app.trace --out reach.json
```

The 1.6 GB trace is not kept; `mcdonalds-observed.json` holds everything derived from it.
