# The gap map: where an APK touches OpenHarmony, and what each gap costs

**2026-09-21.** Extends `API-GAP-METHODOLOGY.md` and `NATIVE-GAP-PROCESS-AMENDMENT.md`.

## Why the subtraction was not enough

The scan subtracts *names*: dex references minus boot-jar definitions, native imports minus
exported symbols. McDonald's then spent a day on the OH board failing, one launch at a time, on
contracts that sat **behind names that all resolved**:

| # | Failure on the board | What the harness said before |
|---|---|---|
| B1 | 0 of 10 libraries load: the OH linker cannot map `.so` out of the APK | flagged by hand in the benchmark report, not by a detector |
| B2 | libraries fail on bionic-only symbols (`__sF`, `__pthread_cleanup_push`, …) | **flagged**: OH-board symbol resolution |
| B3 | `libakamaibmp.so` self-traps with SIGILL | SDK noted by hand as a fingerprinting risk |
| B4 | `getSystemService("jobscheduler")` → null | nothing: `JobScheduler` is a complete class |
| B5 | density-split drawables not found | nothing: split *inventory* only |
| B6 | `LocationManager` null on splash | nothing |
| B7 | Realm `mkfifo` → EACCES | **wrong**: `mkfifo` scored as a resolved import |
| B8 | Firebase: "Instance ID component is not present" | nothing: `getServiceInfo` exists and is bridged |

Every one of B4–B8 is a *contract behind a present name*: a service with no binder, a package
manager that filters out every component, a kernel policy that denies the object a resolved
symbol creates. Trial and error found them in order because each only surfaces once the previous
one is fixed.

## The map

`westlake-apk-gap gap-map` joins the scan with provider models into one table per APK. Each row is
one place the app touches the platform:

| Surface | App side (static) | Provider side (extracted, with `file:line`) |
|---|---|---|
| **Java framework API** | dex member references, API-level filtered | Westlake boot jars |
| **System services** *(new)* | `getSystemService(String\|Class)`, `ContextCompat`, `ServiceManager` call sites, with the manager methods called | AOSP `SystemServiceRegistry` + mainline `*FrameworkInitializer` (name → manager → binders, including binders a manager fetches lazily) × Westlake `OHServiceManager`, `AndroidRuntime.cpp` seeds, `AppSpawnXInit` fetcher overrides |
| **Package manager & manifest** *(new)* | manifest components, `<meta-data>`, `directBootAware`, providers/`initOrder`, splits, processes; `PackageManager` calls | `PackageManagerAdapter` method by method (bridged / stub and what the stub returns); source checks for PMS semantics the source-app path must reproduce |
| **Java APIs called from native code** *(new)* | platform class names, member names and JNI signatures in each `.so`'s data strings (`FindClass`/`Get*ID` go through JNIEnv, not imports) | reference `android.jar` + runtime members, kept only when name and signature both occur; resolved against the boot jars. Hollow counts only in Westlake adapter/stub jars; in `framework.jar` it is a candidate; in upstream libcore it is not a gap |
| **Native platform symbols** | undefined symbols per packaged `.so` | OpenHarmony **plus the NDK Westlake packages** (`--ndk-coverage`): each missing import is classified as package / libc-abi / weld to a named OH subsystem / truthful absence, with the bionic shim's exports and Westlake's build manifests subtracted. Without `--ndk-coverage`, the raw board |
| **Native loading** | `extractNativeLibs`, split ABI libraries | OH linker capability (board test) and the launcher's extraction |
| **Process sandbox & policy** *(new)* | native imports and Java calls that create policy-checked objects (`mkfifo`, `symlink`, …) | OH kernel policy for the app domain, **queried live** (`probes/avq.c`), beside the AOSP rule |
| **External services & SDK behaviour** *(new)* | GMS/Firebase markers, device-probing SDKs | GMS absent on OH; Westlake loader refusal list |

Every row carries: **verdict** · **shim class** (`C0`–`C10`, `CU`) · **effort** · **OH touchpoint** ·
**provider evidence** (`file:line`) · **app evidence** (call sites, libraries, components) ·
**conformance probe**, when one exists.

### Verdicts

`supplied` a real adapter or local implementation answers · `hollow` something non-null answers
nothing (bare binder, default-returning proxy, a scheduler that never runs jobs) · `null` the
manager itself is null · `inert` the manager exists but its binder is null · `unresolved` the
binder is reached through a helper the static read cannot follow · `missing` / `stub` / `denied` /
`refused` / `absent` · `hollow-candidate`, `probe-only`, `environment-sensitive`: evidence to
check, not a verdict.

`unresolved` exists because the first version called any manager with no visible binder
"supplied". `CameraManager`, `TelephonyManager` and `SensorManager` all reach their services
through helper classes; reading them as supplied is exactly the false confidence this tool must
not produce.

### Effort

| | |
|---|---|
| **XS** | hours: configuration, labelling, forwarding one symbol |
| **S** | about a day: a truthful local answer, a missing export, a handful of methods |
| **M** | days: an Android facade over an existing OH capability, *for the methods this app calls* |
| **L** | weeks: port or build a subsystem or bridge |
| **OH** | needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake |
| **verify** | implemented according to source; run the conformance probe before trusting it |

Size-driven tiers use what the app actually calls (manager methods, members, symbols), not the
size of the Android API.

### Evidence ladder

A row's `confidence` says how far its provider verdict has been established:

1. **static**: APK plus provider source. `supplied` at this level means *the source claims it*.
2. **probe**: a white-box conformance probe (`probes/`) exercised the contract on the board, in
   isolation, with a pass marker. `probes/service-metadata` is the Firebase contract behind B8;
   it existed since August but nothing connected it to an app that needed it. The map now does.
3. **observed**: the full app hit it on the device.

The intended loop is: map → run the probes named by `verify` rows → launch the app as acceptance.
The launch stops being how gaps are discovered.

## Which gaps are on the path

The map alone left one unknown: after the blockers already fixed, what comes next? The answer is
recorded rather than launched into. `trace-observe` turns a full ART method trace from a real
Android device into per-row evidence, and `gap-map --observed` lists the gaps on that path. For
McDonald's, cold start to the sign-in screen: **47 of 78 open gaps on the path, 31 off it, and all
8 board failures on it** (`benchmark/2026-09-21-android-baseline/`).

The static alternative, `startup-reach`, was built and measured against the same trace: 84% recall,
7% precision. Dependency injection defeats a path-insensitive call graph, so it is kept for its
call-chain explanations and as an upper bound, not as the staging authority.

## Backtest

`--blockers` replays failures already paid for. Run against the provider **the app actually ran
on** (Westlake `75d82d5`, launcher `f229702`), the map flags **6 of 8** as gaps before any launch,
flags **1** (B3, Akamai) for verification, and **misses 1**:

- **B5, splits**: `SplitApkResolver` already set `splitSourceDirs`, so the source check passed.
  The real failure was McDonald's staged split names not matching the resolver's naming
  convention: right mechanism, wrong behaviour for this layout. Only a probe catches that. The row
  now names the missing probe (`split-resources`).
- **B3** is `environment-sensitive`, not predicted: that an SDK fingerprints the device is
  visible; that it self-traps with SIGILL on this one is not.

Run against the current provider with `--blockers-status`, the same file becomes a status board:
5 closed per source, 2 open, 1 open-verify. One of the open ones is B4. The JobScheduler fix
removed the crash but installed a no-op scheduler, so WorkManager jobs are accepted and never run.
No crash will ever report that. The map does.

## Running it

```bash
westlake-apk-gap scan app.xapk --runtime runtime-index.json --out scan.json
westlake-apk-gap gap-map --scan scan.json --apk app.xapk --api-levels scan-api-annotated.json \
  --aosp <imports root: frameworks-base, modules-*> --westlake <westlake tree> \
  --manifest-repo <launcher repo> --oh-resolution oh-import-resolution.json --app-key <app> \
  [--blockers known-blockers.json [--blockers-status]] --out out/
```

Output: `gap-map.json` (every row with evidence) and `GAP-MAP.md`. The provider's git commit and
uncommitted files are recorded; a map built on a dirty tree says so.

## Limits

- **Native rows are not yet weighted by reach.** They are classified by how the NDK supplies them,
  and name the importing libraries, but do not yet use provenance, per-JNI-method reach or the
  Android baseline capture (`native-surface`, `native-capture-diff`). McDonald's sensors weld and
  asset package come only from `libmlkit_google_ocr_pipeline.so` and `libpanorenderer.so`, and
  neither loads before sign-in on the Android baseline. Joining those layers in would make each
  native row name the JNI methods and Java features it breaks, and whether startup reaches it.
- **The NDK weld model is curated** per library and API family (`data/ndk-weld-model.json`), and
  "provided" means the name is exported, not that it behaves.
- **Native calls back into Java are matched from strings**, which misses names that are built at
  runtime, encrypted or tail-merged, and matches a primitive-typed field by name alone. Classes
  that neither the SDK nor the runtime knows are `CU`: on Toutiao they are ART and old-Android
  internals probed by runtime-hacking libraries.
- **Computed service names** (54 of 454 McDonald's requests) are reported as dynamic, not guessed.
- **Hollow candidates** include bodies that are empty in AOSP too (`AsyncTask.onPostExecute`).
  They stay `verify` until bodies are compared with AOSP source.
- **Provider extraction reads source with patterns.** Each model is covered by a known-answer test
  (`tests/test_gapmap.py`), and each fact carries `file:line`, but a refactor that changes the
  shape of `OHServiceManager` or `PackageManagerAdapter` needs the extractor updated.
- **Curated tables:** `OH_ANALOG` (service → OH subsystem), `HELPER_BINDERS`, `NULL_TOLERANT`,
  `LOCAL_SERVICES`, the package-area map, and the SDK list. They are knowledge, and are marked as
  such where they decide a verdict.
- **The policy matrix is a snapshot** of one OH build (`data/oh-app-data-policy.json`). Re-query
  it per build with `probes/avq.c`; it takes seconds.
- **Semantic mismatches** remain invisible until a probe or the Android baseline compares them.
