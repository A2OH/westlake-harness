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

- **43 of McDonald's 68 open gaps are on this path; 25 are not** (`../2026-09-21-gapmap/current/GAP-MAP.md`,
  section "Gaps on the observed path"). On path: 1×OH, 1×L, 14×M, 15×S, 12×verify. (Against the
  real source build; see the correction below.)
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

## Where OpenHarmony is on this path

A streaming trace emits each method the first time it runs, so record order is first-execution
order: a ruler along the run (`execution_order`). The board's own history lands on it in order:

| Rank | Event | On OpenHarmony |
|---|---|---|
| 14,409 | WorkManager → JobScheduler | crashed (null service), fixed |
| 22,190 | Realm `OsSharedRealm` (named pipe) | denied by policy, passes only in permissive mode |
| 27,426 | `FirebaseInstanceId.getInstance` | crashed (component metadata), fixed in the tree |
| 30,526 | `LoginRegistrationActivity` first touched | reached: the board log shows the activity starting |
| **34,988** | `LocationManager.isProviderEnabled` | **the frontier: last launch died here (null manager); fix written, not yet run** |
| 35,257 | `VelocityTracker.obtain` | unbound at first view attach in an earlier build; fixed |
| 44,451 | sign-in screen drawn | not reached yet |

So McDonald's on OH is 79% of the way along the recorded path, inside the sign-in activity. The
board log also lists services that returned null and were survived: `power`, `locale`, `uimode`,
`appops`, `autofill`, `accessibility`.

## Every framework method that ran, checked against the real build

`trace-framework-check` looks up all 18,493 platform methods the run executed in the runtime
McDonald's actually runs on. That runtime was re-indexed from the 9 boot jars and 48 libraries
staged on the board (lock `32be2a05…`), with JNI bindings recovered from the libraries (93
registration tables, 261 exports). `mcdonalds-framework-check.json`:

| | |
|---|---|
| present, or native and bound | 15,971 |
| compiler-generated names (prove nothing) | 1,050 |
| missing classes or members | 1,213, **none of them public API**: Android 15 QPR internals, feature flags, WebView and okio classes |
| placeholders in Westlake stub jars | 0 |
| also executed by Toutiao, which runs on OH | 15,335 of 18,493 (83%) |
| **boundary failures not proven on OH** | **0** |

After the frontier, 3,758 platform methods remain; 72% are proven by Toutiao and the other 1,064
are all present in the build. WebView's provider is initialized on the path, but no `WebView` is
constructed before sign-in, and every `android.webkit` method used is also used by Toutiao.

**Null services, call site by call site.** Eleven executed app methods call a manager that is
null on OH. Ten run before the frontier and were survived on the board. The one after it, the WiFi
lookup in a fingerprinting SDK (`jP.W.j`, service name decoded at runtime, which is why the scan saw
no request), is wrapped in `catch (Exception)` and returns a fallback string.

**A limit this exposed.** The check cannot see *when* a native is registered. In the pre-fix build
the `VelocityTracker` JNI table existed but was registered lazily on first touch, while McDonald's
needs it at first view attach. The check reports it bound in both builds. Registration order stays
a device-only finding.

## Correction: the stale provider

The first gap map used the August runtime index, which describes the legacy payload. The build
McDonald's runs on is the source build: `framework.jar` has 44,888 classes against 29,331, including
the real AOSP `WifiManager`, `WifiInfo`, `SupplicantState`, `TrafficStats` and
`JobInfo.Builder.setTraceTag`. Re-scanned against it, **McDonald's has no required Java API
absence at all** (all 47 remaining absences were never Android), the "WiFi: 38 members missing (L)"
row disappears, and the map drops from 78 open gaps to 68, of which 43 are on the path. An index
must describe the build under test; `runtime-lock-source-build.json` records this one.

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
westlake-apk-gap trace-framework-check app.xapk --trace app.trace --runtime runtime-index.json \
  --westlake-libs <deployed libs> --proven-trace toutiao.trace --platform-jar android.jar \
  --frontier 'Landroid/location/LocationManager;-><init>' --out framework-check.json
westlake-apk-gap startup-reach app.xapk --runtime runtime-index.json --graph-cache graph.pkl --trace app.trace --out reach.json
```

The 1.6 GB trace is not kept; `mcdonalds-observed.json` holds everything derived from it.
