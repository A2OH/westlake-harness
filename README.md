# westlake-harness

Requirements, analysis and tooling for **systematically finding what a stock Android APK needs that
an Android-compatibility layer on OpenHarmony does not yet provide** — and classifying each gap so
it gets the right repair instead of a guess.

This repo is the *method*. The runtime itself (ART, bridge, framework jars) lives elsewhere.

---

## Why this exists

Bringing up a real, unmodified Android app on OpenHarmony was, until now, an
exception-by-exception process: launch, crash, read the stack, fix one thing, repeat. That is
expensive, and it is expensive in a specific and avoidable way — **the failure modes actively hide
from you**:

- A missing native throws an `Error` that kills a background thread with no report. You learn about
  them strictly one at a time.
- A tolerated `<clinit>` failure leaves a class half-initialised with null statics. Nothing throws
  where the damage is; a `NullPointerException` appears later, somewhere unrelated.
- A **presence probe** — code that only asks *"does this class exist?"* — produces no error at all
  at the missing class. It silently takes the wrong branch, and the failure surfaces in another
  package, naming nothing useful.
- A **hollow stub** fails only when the app calls the one method that was omitted.
- A **present name can hide a broken contract**: `JobScheduler` is a complete class but
  `getSystemService` returns null; `getServiceInfo` is implemented but filters out every component;
  `mkfifo` resolves in musl but the kernel policy denies the pipe it creates. Each of these passed
  every name check and failed on the board, one launch at a time.

Each of those cost real time on the hardest apps attempted. **All of them were statically visible.**

The core claim of this repo:

> The APK's DEX already lists every platform API it can touch. The runtime's boot jars already list
> what is provided. **Subtract before you launch**, rank by where the gap is reached, and apply the
> cheapest repair that the gap's class allows.

Subtraction finds missing *names*. The contracts behind names that do resolve (services, package
manager semantics, kernel policy, library loading) are checked against models extracted from the
Westlake and OpenHarmony sources, and the result is one **gap map** per APK: every place it touches
OpenHarmony, the shim each gap needs, and what that shim costs.

---

## Layout

| Path | Contents |
|---|---|
| `requirements/APK-GAP-PROBE-PROCESS.md` | **The process specification (v0.3).** Taxonomy, phases, stage ladder, gap registry, prioritisation, roadmap, done-criteria. Start here. |
| `requirements/APK-COMPATIBILITY-ARCHITECTURE.md` | The compatibility architecture this process measures against. |
| `analysis/APK-GAP-PROBE-REVIEW.md` | **Critical review of the process**, in two passes: missing detectors, then internal consistency. Every criticism cites a specific measured defect. |
| `analysis/API-GAP-METHODOLOGY.md` | The static gap-analysis method in condensed form: pipeline, taxonomy, limits, validation gate. |
| `analysis/BIONIC-MUSL-PLAN.md` | The **native/libc** boundary taxonomy (`C0`–`C3`) that the Java-side classes extend. |
| `analysis/PORTING-PLAYBOOK.md` | Four investigation tiers, and which to run first. |
| `analysis/AOSP-PACKAGING-STRATEGY.md` | **Package AOSP, weld the bottom** — where to cut the native stack, nested SurfaceFlinger, binder findings, and the MVP plan against Toutiao and McDonald's. |
| `analysis/NATIVE-GAP-PROCESS-AMENDMENT.md` | **Amendment closing the native half of the subtraction**: native import resolution, blast radius, `N-C8` probe-only absence, provenance-driven repair routing, `N-C9` hollow shims, coverage accounting. |
| `analysis/GAP-MAP-METHOD.md` | **The gap map**: one table per APK of every surface where it touches OpenHarmony (Java API, system services, package manager, native symbols and loading, sandbox policy, external SDKs), with verdict, shim class, effort and conformance probe per row, and a backtest against failures already hit on the board. |
| `analysis/NATIVE-PROVENANCE-AND-SURFACE.md` | **Native side of the same subtraction**: which upstream component a stripped `.so` contains, and which Android surfaces each registered JNI method reaches. |
| `evidence/TOUTIAO-BRINGUP-HANDOFF.md` | The empirical base: a full app bring-up with fixes, **nine refuted hypotheses**, build hazards, and harness notes. |
| `harness/westlake_gap/` | Production static scanner: ordered runtime index, multidex/split APK inventory, member resolution, `C8`/`C9` detection, ELF/JNI evidence, gap registry, and report. `nativeprov.py` adds component provenance and per-method platform-surface reach (`native-surface`). |
| `runtime/TRACE-EVIDENCE.md` | Native/reflection watchlists, structured event envelope, ART hook points, and evidence-promotion rules. |
| `harness/` | `ttwalk.sh` (launch/drive/measure), `shotlit.py` (quantify a capture), and older focused dexlib2 investigation tools. |
| `harness/westlake_gap/platformapi.py` | API-level classifier (`annotate-api-levels`): splits an absence list into what a reference device could actually reach, what postdates it, and what was never Android. Cut McDonald's 138 absences to 58. |
| `harness/westlake_gap/gapmap.py`, `services.py`, `contracts.py` | `gap-map` command. `services.py` joins the APK's `getSystemService` requests with AOSP's registry and what Westlake answers for each binder; `contracts.py` models the package manager and manifest contract; `data/oh-app-data-policy.json` is the OH app-data policy, queried from the kernel. |
| `probes/avq.c` | Asks the loaded SELinux policy for an access decision through `/sys/fs/selinux/access`; this is how the OH app-data matrix was measured. |
| `harness/jniprobe/` | Frida agent and scenario drivers that record `RegisterNatives`, `dlopen` and `dlsym` from a running app, plus the Frida-17 and Magisk obstacles the first run hit. |
| `tests/` | Executable known-answer fixtures: `ColorMatrix.set`, a Conscrypt existence probe, an unbound vendor native, and an arm64 JNI library whose platform-coupled and pure methods are known in advance. |
| `corpus/` | Reproducible top-ten selection plus exact download hashes. APK/XAPK binaries are deliberately ignored. |
| `benchmark/2026-08-20/` | Completed ten-app benchmark report, deduplicated registry, and runtime lock. |
| `benchmark/2026-08-21/` | ABI-aware redo against the current ARM64 runtime lock; the prior benchmark remains preserved. |
| `benchmark/2026-08-23-toutiao/native-analysis/ANDROID11-RESOLUTION.md` | **99.7% of 3415 native imports decided** against stock Android 11, and the IFUNC parser defect that finding exposed. |
| `benchmark/2026-09-18-oh-board/` | **First resolution against the deployed OpenHarmony runtime**: 90% of both apps' native imports resolve; the real gap is 58 symbols in five clusters, led by `__sF` at 40 importing libraries. |
| `benchmark/2026-09-18-mcdonalds/` | Cheap validation of the second MVP app: in-APK library loading is required (WebView needs it too), the gap list, and a working Android baseline that touches only six native methods. |
| `benchmark/2026-09-21-gapmap/` | **McDonald's gap map and backtest**: against the provider it actually ran on, the map flags 6 of the 8 board failures before any launch; against the real source build 68 gaps remain (1×OH, 1×L, 20×M, 24×S, 22×verify), 43 of them on the path to sign-in. |
| `benchmark/2026-09-21-android-baseline/` | **McDonald's traced on real Android, cold start to sign-in**: 43 of its 68 open gaps are on that path; all 8 OH-board failures are on it; no Google services is not a blocker. First-execution order places OH at rank 34,988 of 44,451, inside the sign-in activity. Of 18,493 framework methods that ran, none at the public boundary is missing, hollow or unbound in the real build, and 83% are also run by Toutiao on OH. |
| `benchmark/2026-09-21-ndk-coverage/` | **The entire NDK against the OH board**: of 4,449 public symbols, OH provides 59%, Westlake 3%; the missing 1,719 reduce to ten welds plus the libc shim, and 165 are already built by Westlake but not deployed. |
| `benchmark/2026-09-18-mvp-target/` | The Android-specific platform contract of both MVP apps: 206 symbols, of which 48 are ours to implement. |
| `benchmark/2026-08-23-toutiao/runtime-evidence/android-baseline/` | **Static reading versus running**, on a OnePlus 6T: 280 methods and five whole libraries that no APK scan can see, 43 failing `dlsym` lookups, 463 methods never exercised. |
| `benchmark/2026-08-23-toutiao/native-analysis/` | Provenance and surface reach over 138 stripped arm64 libraries: 1417 recovered JNI methods, 47% touching no platform surface. |

---

## The taxonomy in one table

Every finding carries a **contract layer** (`N` native · `J` Java framework · `S` system/lifecycle ·
`G` graphics/device · `R` runtime integrity · `V` vendor · `O` observation), a **mismatch class**,
and a **fault origin**.

| Class | Meaning | Repair |
|---|---|---|
| `C0` | Present and compatible | none |
| `C1` | Missing name/entrypoint, implementation exists | wire it — forward, export, register |
| `C2` | Same name, incompatible layout/encoding/ownership | explicit translation; never a name-only shim |
| `C3` | Loader/namespace/duplicate-runtime collision | isolation or deterministic ordering |
| `C4` | No Android-side implementation; an OH capability exists | supply the AOSP-facing contract over an OH backend |
| `C5` | Genuinely absent or provably optional | truthful unsupported behaviour |
| `C6` | Exists, but state/lifecycle/ordering/timing differ | repair the boundary state machine |
| `C7` | Runtime violates an Android invariant | prove it, then fix generically |
| `C8` | **Probe-only absence** — existence tested, never invoked | presence-only class, under strict proof |
| `C9` | **Declared but hollow** — placeholder or constant body | implement the member from the AOSP contract |
| `C10` | **Our own** build/deployed ABI epoch skew | move to a stable C ABI; never guess vtable slots |
| `CU` | Insufficient evidence | collect more |

`O`-layer findings use `O-OK` / `O-DEFECT` / `O-BLIND` / `O-UNKNOWN` — an observation defect is a
property of the *measurement*, not of a contract.

`C8`, `C9` and `C10` were each added because a real defect had no home in the original taxonomy.
`C8` in particular is the one that crash-driven debugging cannot find at all.

---

## Hard-won rules encoded here

These are in the process spec as hard rules. They exist because each was learned the expensive way.

1. **Always run the control** — and prefer the *narrowest* one. A within-process differential (two
   surfaces of the same app, same run) holds every variable constant except the one under test, and
   proved decisive where cross-app comparison was ambiguous.
2. **Know how every marker is emitted.** A count or an absence is not evidence until you know the
   sampling, gating, thread identity, and whether it fires before or after a fallback. Counters that
   log only at `n==1 || n%30==0` were read as totals and produced a confident, wrong conclusion.
3. **Oracles can be blind by design.** A compositor that deliberately blacks out protected layers in
   captures will return black for a perfectly healthy window. Never judge such a window by a
   screenshot.
4. **Stop scanning at the boundary.** If the APK contract resolves clean and behaviour still fails,
   the defect is probably platform skew, runtime integrity, or the observation system — not a
   missing API.
5. **A fix is not promoted because the crash disappeared.** The user-visible stage must advance.
6. **An unretired app patch is an open platform gap wearing a disguise**, and a patched APK is not a
   valid control.
7. **Retain refuted hypotheses.** Re-deriving a disproven explanation is the dominant waste at
   scale. Nine are recorded in `evidence/`.

---

## What the harness measures

One APK in, one map out. Each surface below has an **app side** read from the APK and a **provider
side** read from the Westlake/OpenHarmony sources or measured on the board, and every provider fact
carries a `file:line`.

### Java surface

- Indexes an ordered boot classpath (first definition wins) and scans every DEX in APK, XAPK and APKM
  base/split containers.
- Resolves classes, methods and fields through inheritance; separates directly absent members from
  hollow constant/no-op bodies (`C9` candidates).
- Traces string flows into `Class.forName`/`findClass`/`loadClass`: presence probes (`C8`) that
  crash-driven debugging cannot find at all.
- `annotate-api-levels` drops absences a reference device could not reach either (introduced after
  its API level, or never Android). On McDonald's that turned 138 absences into 58.

### Native surface: the developer's own C/C++

Stripped libraries carry no source and no useful names. The harness does not try to understand
what the code computes; it measures **where each library crosses into the platform**, because only
those crossings touch OpenHarmony. Eight layers, each answering one question:

| # | Question | How | Detail |
|---|---|---|---|
| 1 | What does the library need from the platform? | Undefined dynamic symbols per `.so`, read from the APK and splits (pyelftools, IFUNC-correct), resolved against the **real** system libraries of a stock Android 11 device and of the OH board | [`ANDROID11-RESOLUTION.md`](benchmark/2026-08-23-toutiao/native-analysis/ANDROID11-RESOLUTION.md), [OH board](benchmark/2026-09-18-oh-board/REPORT.md) |
| 2 | Whose code is inside it? | Component provenance: about 50 upstream components (OpenSSL/BoringSSL, SQLite, Realm, Skia, V8/Hermes, Flutter, Unity, WebRTC, TFLite, …) by version banners and exported-symbol families | [`NATIVE-PROVENANCE-AND-SURFACE.md`](analysis/NATIVE-PROVENANCE-AND-SURFACE.md) |
| 3 | What can Java call into, even when stripped? | `Java_*` exports plus `RegisterNatives` tables rebuilt from relocations as {name, signature, function} | same |
| 4 | Which Java APIs does the library call back into? | `FindClass`/`Get*ID` go through the JNIEnv table, not imports, so neither scan saw them. Platform class names in the library's data strings; for each class, members enumerated from a reference `android.jar` and the runtime, kept only when name **and** exact JNI signature are both in the library; then resolved like dex references (`scan --platform-jar`) | [`nativeupcall.py`](harness/westlake_gap/nativeupcall.py) |
| 5 | Which platform surface does each JNI method reach? | Call graph from each JNI entry through PLT stubs to the imports, following tail calls; imports grouped into surfaces (GLES/EGL, Vulkan, `libandroid`, media, audio, binder, sysprop, dynamic load, net, file, thread) | same; blast radius in [`NATIVE-GAP-PROCESS-AMENDMENT.md`](analysis/NATIVE-GAP-PROCESS-AMENDMENT.md) |
| 6 | What happens when it actually runs? | Frida capture on the Android baseline of `RegisterNatives`, `dlopen`, `dlsym`; `dlsym` name strings found statically | [`harness/jniprobe/`](harness/jniprobe/README.md), [baseline](benchmark/2026-08-23-toutiao/runtime-evidence/android-baseline/) |
| 7 | How is a missing symbol supplied? | The provider is OpenHarmony **plus the NDK Westlake packages**, not the raw board. `ndk-coverage` measures the entire public NDK against the board and classifies each missing symbol with a weld model: **package** (compile AOSP source), **libc-abi** (translate onto musl), **weld** (AOSP above a named OH subsystem), **truthful-absence**; and checks whether Westlake already has a build manifest for the source | [NDK coverage](benchmark/2026-09-21-ndk-coverage/README.md), [`ndk.py`](harness/westlake_gap/ndk.py) |
| 8 | Does a resolved symbol actually work on OH? | Policy-checked calls (`mkfifo`, `symlink`, `mknod`, `link`) against the live OH kernel policy; in-APK loading against the OH linker; missing symbols minus the Westlake bionic shim's exports and the loader's refusal list | [`GAP-MAP-METHOD.md`](analysis/GAP-MAP-METHOD.md) |

What it has shown so far:

- Toutiao: 99.7% of 3,415 imports decided against Android 11. That resolution exposed a parser
  bug that had reported `strlen` and friends missing in 103 libraries.
- On the OH board, 90% of both apps' imports resolve. The real gap is 58 symbols in five clusters,
  led by `__sF` in 40 libraries.
- 1,417 JNI methods were recovered from Toutiao's 138 stripped libraries, and 47% of them touch no
  platform surface, so they port unchanged.
- The Android baseline sees 280 methods and 5 libraries that no APK scan can.
- On McDonald's, Realm's `mkfifo` resolves, but OH denies the pipe it creates.
- Calling back into Java is common. 46 of Toutiao's 138 libraries do it, naming 116 platform classes
  and 645 members, and 6 of McDonald's 10 do. McDonald's `libpanorenderer.so` calls
  `TrafficStats.setThreadStatsTag`, which is hollow in Westlake's mainline stub jar; no other scan
  can see that. Four ByteDance runtime libraries name classes neither the SDK nor Westlake has
  (`java/lang/reflect/ArtMethod`, `android/view/GLES20Canvas`): they probe ART and old-Android
  internals, a runtime-integrity risk rather than an API gap.

Provenance decides the repair route. Known open-source code takes its upstream port. The
developer's own code only needs its **boundary** shimmed, and that boundary is what layers 1, 4, 5, 7
and 8 enumerate.

### Contracts behind present names

| Surface | App side | Provider side |
|---|---|---|
| System services | `getSystemService(String\|Class)`, `ContextCompat`, `ServiceManager` call sites and the manager methods called | AOSP `SystemServiceRegistry` and mainline initializers (name → manager → binders, including lazily fetched ones) × Westlake `OHServiceManager`, runtime seeds, `AppSpawnXInit` overrides → `supplied` / `hollow` / `null` / `inert` / `unresolved` |
| Package manager & manifest | components, `<meta-data>`, `directBootAware`, providers and `initOrder`, splits, processes; `PackageManager` calls | `PackageManagerAdapter` method by method (bridged, or stub and what it returns); PMS semantics the source-app path must reproduce |
| Activity, window & process contracts | `ActivityManager` process-table queries, `Dialog.show` | what system_server answers, answered in-process in direct launch: the `IActivityManager` stub handler (null for any object result it does not answer by name), Android window stacking; decided by probes |
| Sandbox policy | objects the code creates | OH SELinux decision for the app domain, queried from the loaded kernel policy (`probes/avq.c`, `harness/westlake_gap/data/oh-app-data-policy.json`), beside the AOSP rule |
| Loading & packaging | `extractNativeLibs`, split ABI libraries | OH linker capability (board test) and the launcher's extraction |
| External services & SDKs | GMS/Firebase markers; device-probing SDKs | no Google services on OH; the loader's refusal list |

### The output: one gap map per APK

`gap-map` joins all of the above. Every row has a **verdict**, a **shim class** (`C0`–`C10`, `CU`),
an **effort** tier, the **OH touchpoint**, provider and app evidence, and the **conformance probe**
(`probes/`) that settles it on the board when one exists:

| Effort | Meaning |
|---|---|
| XS / S / M / L | hours / a day / days: a facade over an existing OH capability, sized by what the app calls / weeks: a subsystem or bridge |
| OH | needs an OpenHarmony platform change: outside Westlake |
| verify | the source claims it; run the named probe before trusting it |

A row's confidence moves from **static** (APK + provider source) to **probe** (a white-box probe
ran on the board; `--probe-results` applies it, for the exact Westlake commit it was measured on)
to **observed** (the full app on the device). The launch becomes acceptance rather than discovery.
`--blockers` replays failures already paid for. Against the provider McDonald's actually ran on,
the map flags **6 of its 8** board failures before any launch
([benchmark](benchmark/2026-09-21-gapmap/README.md)). The probes then found two more before the
app reached them. The first launch after those fixes reached the sign-in activity and exposed one
more, window stacking, which a probe reproduced and a Java fix closed: McDonald's now shows its
sign-in screen on the board ([benchmark](benchmark/2026-09-22-mcdonalds-signin/README.md)).

### Which gaps are on the path: recorded, not guessed

A gap list does not say what stands between process start and the first screen. Two tools answer
that, and the measured difference between them decides which to trust:

- **`trace-observe`** reads an ART method trace recorded on real Android (`am start-activity
  --start-profiler … --streaming` on a userdebug or rooted device) and marks every gap-map row
  touched or not, with evidence: the platform call is in the trace, a method containing the
  reference ran, the manager class executed, or the library loaded. `gap-map --observed` adds an
  "on path" column and a section listing the gaps on the recorded path. This is the authority.
- **`trace-framework-check`** starts from what *ran* rather than what the app references: every
  platform method in the trace is looked up in the runtime under test (missing, placeholder, or
  native with no JNI binding in the deployed libraries), minus what an app already running on the
  target also executes (`--proven-trace`). It covers the framework calling itself and its own
  native code, where app-side scans are blind. It cannot see *when* a native gets registered.
  `execution_order` turns the trace into a ruler, so known failure points on the target show how far
  along the path the port has got.
- **`startup-reach`** stages platform touches from bytecode alone (call graph from the manifest
  entry points, rapid type analysis, user-input callbacks deferred). Measured on McDonald's against
  the trace it has 84% recall and 7% precision: a dependency-injected app makes nearly everything
  look reachable at process start. Use it for its call-chain explanations of *why* a gap is
  reached, and as an upper bound when no device is available.

### Commands

| Command | Purpose |
|---|---|
| `snapshot-runtime` | index an ordered boot classpath, bridge ELFs and system libraries into a runtime lock |
| `scan` | Java, native and service inventory of one APK/XAPK/APKM against a runtime index; `--platform-jar` adds native calls back into Java |
| `annotate-api-levels` | drop absences a reference device could not reach either |
| `native-surface` | component provenance and per-JNI-method platform-surface reach for packaged ELFs |
| `native-capture-diff` | join a runtime JNI capture (`harness/jniprobe`) to a `native-surface` scan |
| `ndk-coverage` | the entire public NDK against a board's libraries, each missing symbol classified as package / libc-abi / weld / absence |
| `trace-framework-check` | every platform method a recorded run executed, checked against the runtime under test and its deployed JNI bindings |
| `trace-observe` | platform touches and loaded libraries of one run recorded on real Android, from an ART method trace |
| `startup-reach` | static call-graph staging of platform touches (process start / first activity / next screens), with call-chain explanations; `--trace` measures it against a recording |
| `gap-map` | the categorized, effort-rated map; `--observed` marks each gap on or off a recorded path; `--ndk-coverage` classifies native gaps by how the NDK supplies them; `--blockers` for a backtest or status board |
| `benchmark`, `trace-watchlist`, `ingest-trace`, `runtime-summary` | portfolio scans and runtime trace evidence |

Per-app OH-board import resolution is a recipe, not yet a command: pull the board's libraries with `hdc`,
then call `resolve_native_imports` (see the [board report](benchmark/2026-09-18-oh-board/REPORT.md)).

The known-answer fixtures must pass before any portfolio or map is trusted:

```bash
PYTHONPATH=harness:tests python3 -m unittest discover -s tests -v
```

### Known limits

- **The runtime index must describe the build under test.** McDonald's first map used an index of
  the legacy payload and reported 58 required Java absences; re-indexed from the boot jars staged on
  the board, there are none. Snapshot the runtime from the deployed jars, not from memory.

- **Native rows are classified by supply strategy but not yet weighted by reach.** McDonald's
  sensors weld and asset package come only from `libmlkit_google_ocr_pipeline.so` and
  `libpanorenderer.so`, which never load before sign-in on the Android baseline. Until provenance,
  per-JNI-method reach and the baseline capture are joined in, native priority does not reflect what
  startup reaches.
- Native calls back into Java are read from strings. Names built at runtime, encrypted, or
  tail-merged into a longer string are invisible, and a primitive-typed field is matched by name
  alone.
- Computed service names and computed reflection are reported, not guessed.
- Hollow-body candidates include bodies that are empty in AOSP too; they stay `verify`.
- Provider models are extracted from source with patterns and covered by known-answer tests; a
  large refactor of the provider needs the extractor updated.
- Semantic mismatches (right name, wrong behaviour) stay invisible until a probe or the Android
  baseline compares them.

## Ten-app benchmark

The completed [2026-08-20 report](benchmark/2026-08-20/REPORT.md) scans the first ten third-party
apps in Similarweb's global Google Play top-free chart after excluding Google/OEM system components.
The exact selection is in `corpus/top10.json`; `corpus/downloads.lock.json` records versions,
container/split counts, byte sizes, SHA-256 hashes, retrieval date, and the pinned downloader.

Headline static results against the preserved Westlake runtime lock:

- **1,586** unique Java gap candidates;
- **594** directly absent classes, methods, or fields;
- **408** probe-only absence candidates requiring the strict `C8` runtime gate;
- **584** hollow-body heuristic candidates requiring AOSP/manual review;
- **32,736** unresolved native/reflection records retained as evidence but excluded from gap totals.

The most pervasive direct gaps are the hollow networking surface (`ConnectivityManager`,
`NetworkCapabilities`, and `NetworkInfo`), followed by Wi-Fi/MediaStore coverage and the known
constructor-only `ColorMatrix` class. These are static prevalence results, not launch blockers;
runtime `P0`–`P8` probes are still required for reachability and severity.

### ABI-aware redo

The [2026-08-21 report](benchmark/2026-08-21/REPORT.md) preserves the Java result but corrects the
native evidence model. Of 49,941 DEX native declarations, 12,692 resolve to target-ABI APK exports,
2 resolve to runtime-bridge exports, and 6,516 belong to three ARMv7-only containers and are now
reported as ABI-unavailable instead of borrowing their 32-bit symbols. The remaining executable
ARM64 trace queue is 30,731 records, split into static registration-table, load-scoped, and
unattributed states.

The headline `CU` count rises from 32,736 to 37,330 because the old number was artificially low by
4,596 wrong-ABI export matches; two newly recognized bridge matches offset that by two. The
[redo note](benchmark/2026-08-21/REDO.md) gives the full accounting and links the separate verified
[ARMv7 supplement](benchmark/2026-08-21-armv7/README.md). Results from the two runtime locks are not
merged.

## Reproduce the benchmark

Install the scanner in an isolated Python environment:

```bash
python3 -m pip install -e .
```

Download EFF `apkeep` 1.0.0, verify its published SHA-256
`a23579a3ba366d25a6d69848189b983d65662f4ecf4b9e11e16510811659de4e`, then fetch and lock the
corpus without committing the app binaries:

```bash
python3 scripts/fetch_corpus.py --apkeep /path/to/apkeep-1.0.0
```

Point `BRIDGE_ARM64` at the active build, state the ABI explicitly, and run:

```bash
export BRIDGE_ARM64=/path/to/bridge-build-arm64
TARGET_ABI=arm64-v8a scripts/run_benchmark.sh benchmark/$(date +%F)
```

Verify that every downloaded hash, per-app scan, runtime ID, and registry invariant matches:

```bash
python3 scripts/verify_benchmark.py --benchmark benchmark/2026-08-20
```

`runtime-lock.json` hashes every boot JAR and bridge ELF. Results from different lock IDs must never
be merged silently. Per-APK detailed scans and the 39 MB runtime index are generated locally and
ignored; the compact lock, registry, and report are retained.

For the runtime pass that resolves dynamic JNI registration and caller-keyed reflection outcomes,
follow [`runtime/TRACE-EVIDENCE.md`](runtime/TRACE-EVIDENCE.md). Run legacy logs against one APK scan
at a time; structured events carry package, APK hash, runtime lock, run, and scenario provenance.

---

## Conventions

Paths in these documents are written as environment variables (`$WESTLAKE_ROOT`, `$BRIDGE_ARM64`,
`$OHOS_SDK`, `$HDC`, `$BOARD_SERIAL`, …) rather than absolute local paths. See `env.sample.sh`.
Device serials, usernames and host paths are deliberately excluded from this repo.
