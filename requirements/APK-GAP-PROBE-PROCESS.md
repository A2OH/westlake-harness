# Westlake APK Gap Probe Process

Status: proposed process, version 0.3  
Scope: unchanged stock Android APK compatibility on OpenHarmony  
Primary objective: scan and probe hundreds, eventually thousands, of APKs to identify the compatibility gaps with the highest platform-wide return on investment

Related architecture:

- [WESTLAKE-APK-COMPATIBILITY-ARCHITECTURE.md](./WESTLAKE-APK-COMPATIBILITY-ARCHITECTURE.md)
- [WESTLAKE-APK-GAP-PROBE-REVIEW.md](./WESTLAKE-APK-GAP-PROBE-REVIEW.md)
- `$BRIDGE_ARM64/BIONIC-MUSL-PLAN.md`

Version 0.2 incorporates the detector-first corrections from the critical review: existence probes, member-level/hollow detection, static-initializer severity, marker semantics, platform-self-skew, re-entrant code scanning, within-process controls, non-reproducible runtime components, split presentation stages, small-corpus scoring suppression, and executable known-answer fixtures.

Version 0.3 incorporates the review's second pass (consistency and implementability), which found four defects *within* the process rather than gaps in its coverage:

- **§4.2 — `O-*` no longer uses `C0`-`C10`.** An observation defect is a property of the measurement, not of a contract. Classifying a lying oracle as `C0` filed it under "no change required" and dropped it from every queue that filters `C0`. `O` now has `O-OK` / `O-DEFECT` / `O-BLIND` / `O-UNKNOWN`, distinguishing an oracle that is *wrong* (fix it, and re-open findings derived from it) from one that is *blind by design* (route around it permanently). The protected-layer capture is `O-BLIND`.
- **§4.2 — `C1` versus `C4` is now decidable.** The two classes overlapped on the corpus's most common finding, and §4.4 previously conceded the ambiguity ("`J-C1` or `J-C4`"). Inconsistent classification splits one defect across two registry keys and corrupts prevalence counts. One question now decides it: *does an Android-side implementation already exist?*
- **§12 — classification removed from gap identity.** `mismatch_class` and `fault_origin` were part of the canonical key while §11 permits reclassification and §20 mandates classifier re-runs. Both operations therefore minted new gaps and orphaned their history. They are now versioned attributes; identity is stable under reclassification.
- **§3 / §15.1 — control purity.** Hard Rule 3 forbids app patches as solutions, but Noice — a named control — currently depends on two. A control only measures unchanged-APK compatibility if the control is unchanged. Patched APKs are now marked `control-impure`, every promoted platform fix must trigger a re-test of the patches that worked around it, and an unretired app patch is treated as an open platform gap wearing a disguise.

## 1. Purpose

Westlake needs a repeatable way to answer four questions before engineers begin app-specific debugging:

1. What Android contracts does this APK depend on?
2. Which of those contracts are absent, incompatible, or semantically incomplete in the deployed Westlake runtime?
3. Which gaps are actually reached and block useful application behavior?
4. Which platform fixes will unlock the largest number of APKs without weakening Android fidelity?

The APK Gap Probe converts APK bring-up from an exception-by-exception investigation into a portfolio-level compatibility program:

```text
inventory -> resolve -> classify -> probe -> reconcile -> prioritize -> fix -> validate -> refine
```

It does not promise that static scanning can predict every runtime failure. Reflection, downloaded code, server-controlled behavior, dynamic native loading, lifecycle timing, and rendering semantics still require runtime probes. The goal is to make those unknowns explicit and bounded rather than discovering everything in the dark.

## 2. Westlake Principle

The process must preserve Android semantics as deeply as possible and translate only where Android behavior lands on OpenHarmony.

The expected ownership chain is:

```text
unchanged APK
    -> stock Android framework-facing behavior
    -> stock ART and managed/native semantics
    -> narrow Android-to-OH backend adapter
    -> OpenHarmony service, graphics, input, storage, network, or device capability
```

A gap report is not permission to add a stub. It is evidence used to locate the correct owner of the missing contract.

## 3. Hard Rules

1. **Scan the artifact that will run.** Identify the APK by cryptographic hash, not only package/version name.
2. **Resolve against the runtime that is deployed.** Framework jars, ART, bridge libraries, provider APKs, loader paths, and configuration must be captured in a runtime lock file.
3. **Do not patch the APK, and know which APKs are already patched.** App bytecode changes can be used only as explicitly labelled diagnostic experiments, never as the compatibility solution. Any APK currently carrying a patch is marked `control-impure` in the runtime lock and is excluded from unchanged-APK metrics until the patch is retired. Every promoted platform fix must trigger a re-test of the app patches that worked around it (see §15.1).
4. **Do not stub callable contracts by name alone.** A symbol name does not establish ABI, lifecycle, state, timing, security, or failure semantics. A presence-only class is permitted only under the strict `C8` proof rule: all known uses test existence, no known code invokes the type, runtime-loaded code has been scanned, and the proving call sites are recorded.
5. **Preserve the first causal failure.** Downstream nulls and crashes must be grouped beneath the earliest broken contract when evidence supports that relationship.
6. **Unknown remains unknown.** An unresolved item must not silently become “optional,” “safe,” or “implemented.”
7. **Change one variable and prove deployment.** Every experiment records artifact hashes and verifies that the intended change took effect.
8. **Use independent oracles.** Process liveness, lifecycle events, view tree, compositor presentation, captured pixels, input response, network/content, and physical display state are distinct observations.
9. **Know how every marker is emitted.** A count or absence is not evidence until the emitting condition is recorded: sampling, gating, thread identity, and whether the marker occurs before or after fallback.
10. **Prefer the narrowest control.** Use within-process differentials first when available, then focused contract tests and cross-app controls such as Noice and Material Catalog.
11. **Stop scanning at the boundary.** If the APK contract resolves cleanly but behavior still fails, investigate Westlake platform skew, runtime integrity, or the observation system rather than inventing more APK gaps.
12. **Remove diagnostics before promotion.** High-volume tracing, provenance repairs, and app-targeted probes are not production features.

## 4. Gap Taxonomy

A single numbered list is too weak. Every finding receives a contract layer, mismatch class, and fault origin.

### 4.1 Contract layers

| Prefix | Contract layer | Examples |
|---|---|---|
| `N` | Native ABI and loader | libc, Bionic/musl, NDK, ELF, SONAME, relocations |
| `J` | Java framework and native peers | classes, methods, fields, framework JNI |
| `S` | Android system and lifecycle | Binder services, activities, fragments, loopers, permissions |
| `G` | Graphics and device-facing framework | resources, fonts, HWUI, surfaces, input, WebView, media |
| `R` | Runtime integrity | ART, class loading, interpreter, JNI transitions, GC roots |
| `V` | App/vendor facilities | bundled SDKs, optional profilers, optimizers, crash SDKs |
| `O` | Observation system | captures, logging, timing gates, probe reliability |

### 4.2 Mismatch classes

The native `C0`-`C3` portion extends the taxonomy in `BIONIC-MUSL-PLAN.md`.

| Class | Definition | Default response |
|---|---|---|
| `C0` | Present and compatible in ABI and observed semantics | No change |
| `C1` | Missing name or entrypoint; an equivalent implementation exists | Thin forwarder or registration |
| `C2` | Same apparent API but incompatible signature, layout, encoding, ownership, or handle type | Explicit translation or isolated compatible runtime; never a name-only shim |
| `C3` | Loader, namespace, version, or duplicate-runtime collision | Namespace isolation or deterministic ownership/order |
| `C4` | Android implementation is missing, but an OH backend capability exists | Preserve/reuse the AOSP-facing implementation and replace only its backend |
| `C5` | Capability is genuinely absent, policy-restricted, or demonstrably optional | Truthful unsupported behavior, feature gating, or a narrowly proven optional no-op |
| `C6` | API exists but state, lifecycle, ordering, timing, or failure semantics differ | Compare state traces and repair the OH boundary state machine |
| `C7` | ART/runtime violates an invariant required by Android semantics | Prove the invariant, then implement a generic runtime correction |
| `C8` | Probe-only absence: code tests whether a class exists but does not invoke that type | Presence-only class after strict static, dynamic, and runtime proof |
| `C9` | A required member is declared but its implementation is a placeholder or hollow constant/no-op body | Flag as a candidate, then implement the member from the AOSP contract after review |
| `C10` | Westlake was built against an ABI/interface epoch that differs from the deployed OH implementation | Move to a stable C ABI or match the deployed interface; never invoke guessed C++ virtual slots |
| `CU` | Insufficient evidence to classify | Collect more static or runtime evidence |

`O-*` findings are kept separate from product gaps. A black protected-layer capture, a tap sent to the wrong root, or a timeout that expires before a measured readiness event can make a working application appear broken.

`O-*` findings do **not** use the `C0`-`C10` classes. Those describe a contract mismatch; an observation defect is a property of the measurement, not of the contract. Classifying a lying oracle as `C0` ("present and compatible") would file the most instructive observation defects under "no change required" and drop them from every queue that filters `C0`.

| Observation class | Definition | Default response |
|---|---|---|
| `O-OK` | The oracle reports the true state for this case | No change |
| `O-DEFECT` | The oracle reports a false state (wrong PID/thread, wrong input root, stale log, sampled counter read as a total, marker emitted before a fallback) | Repair the oracle; re-open every finding that depended on it |
| `O-BLIND` | The oracle *cannot* observe this case by design, and correctly reports nothing usable | Select an independent oracle; record the blindness so the case is never re-measured this way |
| `O-UNKNOWN` | Oracle trustworthiness for this case is unestablished | Validate against a known-good case before use |

The distinction matters operationally: `O-DEFECT` is a bug to fix, `O-BLIND` is a permanent constraint to route around. RenderService blacking out protected layers in captures is `O-BLIND` — the capture path is behaving correctly and will never answer that question.

`C8` is deliberately narrow. Absence of member references in the base APK alone is insufficient: plugin/dynamic DEX must be included, reflection must be checked, and a runtime control must demonstrate that the class is a marker rather than a callable contract.

`C9` does not replace member-level missing-API detection. A missing required member remains `C1` or `C4`; `C9` means the member is present but its implementation is hollow. Tiny bodies such as `codeUnits <= 2` returning a constant are candidates for review, not automatic proof, because legitimate getters and intentional no-ops can be small.

**`C1` versus `C4` — decision rule.** These two overlap on the most common finding in the corpus (a
framework contract that is absent), and an undecidable boundary produces inconsistent classification
between analysts and agents. Inconsistent classification splits one defect across two registry keys
and corrupts prevalence counts. Decide with a single question:

> **Does an Android-side implementation of this contract already exist somewhere in the deployed
> runtime or in AOSP as we ship it?**

- **Yes — it exists and is merely unwired.** ⇒ `C1`. The response is forwarding, symbol export, or
  registration. **No new app-facing semantics are authored.**
- **No — nothing implements it on the Android side.** ⇒ `C4`. We must supply an implementation, and
  the only open question is which OH capability backs it.

Applied to the ambiguous case in §4.4: a framework Java method whose native peer is absent is `C1`
when the peer exists and needs exporting or registering, and `C4` when the peer must be written
against an OH backend. Record which branch the evidence took.

### 4.3 Fault origin

Every finding records one origin:

| Origin | Meaning |
|---|---|
| `apk-dependency` | The APK requires a contract not supplied faithfully by the runtime |
| `platform-self-skew` | Westlake itself was compiled or wired against the wrong deployed platform contract |
| `runtime-invariant` | ART/runtime violates an invariant independently of the APK API inventory |
| `observation-system` | The probe, marker, input target, capture, or readiness condition is misleading |
| `unknown` | Evidence is not yet sufficient |

Only `apk-dependency` findings contribute to APK-gap frequency counts. Other origins remain in the causal record and platform work queues but cannot inflate the apparent API gap surface.

### 4.4 Examples

| Finding | Classification | Correct response |
|---|---|---|
| Bionic-only `__system_property_get` | `N-C1` | Forward to the equivalent property implementation |
| Opaque pthread layout differs | `N-C2` | Layout-compatible interposer or Bionic namespace |
| App-bundled `libc++_shared.so` captures the process | `N-C3` | Loader ordering or namespace isolation |
| Framework Java method exists, native peer absent, **peer exists and is unwired** | `J-C1` | Export/register the existing peer; author no new semantics |
| Framework Java method exists, native peer absent, **no Android-side implementation exists** | `J-C4` | Write the peer against the Android contract over an OH backend |
| Class name is used only as a `Class.forName` platform marker | `J-C8` | Presence-only class after all strict proof conditions pass |
| Framework member exists but is a generated constant-return stub | `J-C9` candidate | Compare with AOSP and implement the required behavior |
| Fragment lifecycle reaches observers in the wrong order | `S-C6` | Fix lifecycle dispatch at the OH activity boundary |
| Vendor profiler JNI entrypoint is absent | `V-C1`, optionally disposed as `V-C5` | Record the missing entrypoint; no-op only after optionality is proven |
| Managed non-null reference becomes null during interpreter transfer | `R-C7` | Generic ART invariant investigation and correction |
| Bridge C++ vtable epoch differs from deployed OH library | `N-C10`, origin `platform-self-skew` | Replace typed cross-epoch call with a stable C ABI |
| RenderService masks a protected surface in screenshots | `O-BLIND` | Use an independent oracle (view tree, presentation counters, physical panel); never modify rendering on capture evidence alone |
| Sampled counter (`n==1 \|\| n%30==0`) read as a total | `O-DEFECT` | Fix the reading; re-open every finding derived from that count |

## 5. Probe Architecture

The system has five persistent inputs and three principal outputs.

### 5.1 Inputs

1. APK corpus and corpus metadata.
2. Immutable APK/component hashes.
3. Versioned Westlake runtime snapshot.
4. Android contract database derived from the matching AOSP/API level.
5. Runtime evidence from controlled board or emulator probes.

### 5.2 Outputs

1. `apk-compat.json`: per-APK inventory, findings, evidence, and stage results.
2. `gap-registry.json`: deduplicated platform gaps shared across APKs.
3. Portfolio report/dashboard: coverage, blockers, clusters, and ranked platform work.

## 6. Phase A: Freeze the Runtime Under Test

Before scanning APKs, generate `runtime-lock.json` containing at least:

- Westlake build ID and source revision.
- Board model, OH version, architecture, and kernel.
- ART and appspawn executable hashes.
- Boot classpath and framework jar paths/hashes.
- Bridge and shim library paths/hashes.
- WebView provider identity, version, native library path, and hash.
- System ELF search paths and loader namespace/order configuration.
- Available Binder/service adapters.
- Display, GPU, input, media, network, font, locale, and device capabilities.
- Relevant environment flags and launch profile.
- Per-component reproducibility status: reproducible, non-reproducible, unknown.
- Known-good qualification and the behavioral smoke tests passed by fragile components.

Results from different runtime locks must not be silently merged. They may be compared, but the runtime identity remains part of every finding.

A hash identifies a binary; it does not certify that a rebuild is behaviorally equivalent to a known-good artifact. Source revision and exported-symbol parity are also insufficient. Components known to be non-reproducible, such as the current `libhwui` build path, must not be rebuilt as part of a probe run. Preserve and reference the exact known-good binary.

## 7. Phase B: Static APK Inventory

Static scanning runs without a board and should be safe to parallelize and cache.

### 7.1 APK identity and packaging

Extract:

- SHA-256, package name, version code/name, signing certificate identity.
- min/target SDK and split/base relationships.
- Components, exported state, intent filters, processes, providers, permissions, and requested features.
- ABI directories, DEX count, assets, resource table, and compressed/uncompressed native libraries.

### 7.2 DEX contract inventory

Extract and normalize:

- Referenced classes, methods, and fields.
- Declared native methods and their Java signatures.
- Framework API level requirements.
- `System.loadLibrary`, `System.load`, reflection, class-name, service-name, and provider-name string candidates.
- Data-flow pairs from `const-string` class names to `Class.forName`, class-loader `findClass`/`loadClass`, and equivalent platform-existence probes.
- Required members resolved at full owner/name/signature granularity, never only by class presence.
- Static initializer call paths and classes reached during bootstrap/application/activity initialization.
- AndroidX and major embedded framework/library versions when identifiable.
- WebView, Flutter, React Native, Unity, Chromium, media, maps, camera, and other runtime families.

Unconnected strings are hints and remain low-confidence. A string with proven data flow into an existence API is a first-class `C8` candidate because platform-selection code may depend only on whether a class resolves. It still requires the strict `C8` proof gate before a presence-only class is allowed.

### 7.3 ELF contract inventory

For every unique packaged ELF, extract:

- Content hash, architecture, SONAME, `DT_NEEDED`, RPATH/RUNPATH.
- Undefined and exported dynamic symbols.
- Symbol versions and weak/strong binding.
- TLS usage and relocations.
- JNI exports and `JNI_OnLoad` presence.
- References to pthread/synchronization families and opaque ABI structures when detectable.
- Duplicate runtimes such as `libc++_shared.so`.
- Known hooks/interposition frameworks and native SDK families.

ELFs are deduplicated by content hash across the entire corpus. A common SDK library should be analyzed once and associated with every containing APK.

### 7.4 Detector-first calibration set

Before building portfolio infrastructure, implement and run these detectors over Toutiao, Noice, and Material Catalog:

1. **Existence-probe detector (`C8`).** Trace class-name constants into `Class.forName`, `findClass`, and `loadClass`; resolve them against the platform; list every use of the target type.
2. **Member-level and hollow detector (`C1`/`C4`/`C9`).** Diff required methods/fields by full signature. Separately flag present methods with placeholder-sized constant/no-op bodies as `C9` candidates for manual/AOSP comparison.
3. **Unbound-native detector (`J`/`V-C1`).** Join DEX `native` declarations against registered natives, bridge/system exported JNI names, packaged ELF JNI exports, and `JNI_OnLoad` registration evidence.

These detectors must rediscover the known calibration fixtures in §22 before the process expands to a portfolio. Failure to rediscover a known result means the detector or platform index is incomplete.

## 8. Phase C: Resolve Against the Platform Index

Build a versioned platform index from the exact runtime lock:

- Boot/framework class, method, and field signatures.
- Framework native declarations and registered/exported implementations.
- System and bridge ELF exports, versions, and SONAME ownership.
- Known Bionic-to-musl ABI measurements.
- Binder/service names and supported interfaces/transactions where available.
- WebView/provider contracts.
- OH backend capability mappings.

Resolution produces three sets:

1. **Satisfied:** high-confidence `C0` dependencies.
2. **Gap candidates:** missing or incompatible dependencies with a proposed classification.
3. **Unresolved:** reflection, dynamic loading, semantic behavior, or insufficient platform data (`CU`).

Resolution is member-level. Class presence cannot satisfy a referenced method or field, and a declared member with a generated placeholder body is a `C9` candidate rather than `C0`.

Presence is not proof of compatibility. A found method or symbol can still be `C2`, `C6`, `C7`, `C9`, or `C10`.

## 9. Phase D: Reachability and Risk Estimation

Static references must not all receive equal priority.

Assign each candidate:

- `startup_reachability`: manifest/bootstrap/clinit-on-launch-path/direct/lazy/unknown.
- `feature_scope`: core flow, common feature, optional feature, diagnostics/telemetry.
- `evidence_confidence`: confirmed runtime, direct static call, relocation, string-only, inferred.
- `failure_severity`: process cannot load, deferred corruption, crash, hang, blank UI, broken feature, degraded behavior.
- `diagnostic_displacement`: immediate, nearby, delayed/displaced, unknown.
- `fix_risk`: localized boundary, shared framework, graphics/lifecycle, ART/loader.

Static reachability is approximate. Runtime probes update it.

`clinit-on-launch-path` is ranked above an ordinary direct reference for investigation because the current runtime may tolerate a static-initializer exception, leave null/partial static state, and fail later in unrelated code. Record this as `deferred-corruption` with high diagnostic displacement. User-impact severity and diagnostic difficulty remain separate dimensions; deferred corruption is not automatically more user-severe than every crash.

## 10. Phase E: Dynamic Stage Probe

Each APK runs under a deterministic launch profile. Progress is measured by events, not fixed sleeps alone.

### 10.1 Standard stage ladder

| Stage | Milestone | Required evidence |
|---|---|---|
| `P0` | Package parsed and launch target selected | Manifest/resource success |
| `P1` | Process and runtime created | Correct PID, classpath, native namespace |
| `P2` | `Application` attached/created | Lifecycle event and process survival |
| `P3` | First Activity created/resumed | Activity/lifecycle trace |
| `P4a` | Structural UI exists | ViewRoot and populated view tree with meaningful geometry/text |
| `P4b` | Frame reached compositor/presentation path | Surface/buffer/present evidence independent of capture pixels |
| `P4c` | Pixels visually confirmed on the panel | Capture or physical-panel evidence; may be `oracle-unavailable` |
| `P5` | Input changes application state | Targeted input plus resulting state change |
| `P6` | Data/content flow works | Network/local content and rendered state |
| `P7` | Secondary flows work | Back/navigation, WebView, media, dialogs, background work |
| `P8` | Endurance and recovery | Timed survival, pause/resume, relaunch |

Each observation records `pass`, `fail`, or `oracle-unavailable`. For example, a protected layer can produce `P4a=pass`, `P4b=pass`, and `P4c=oracle-unavailable` when RenderService deliberately blackens captures and no physical-panel observation is available.

An APK can pass one stage and fail the next. “Process alive,” “window exists,” “frame submitted,” and “pixels visible” are never interchangeable.

### 10.2 Structured failure events

Normalize runtime evidence into event types:

- class/method/field resolution failure;
- tolerated or fatal static-initializer failure, including the initialized class and original exception;
- JNI lookup or registration failure;
- `dlopen`, relocation, SONAME, or symbol-version failure;
- service unavailable or Binder transaction unsupported;
- lifecycle transition missing, duplicated, or out of order;
- Looper/thread termination and uncaught exception;
- surface/buffer/fence/compositor failure;
- resource/theme/font/inflation failure;
- input root/focus/dispatch failure;
- WebView/provider/navigation/render failure;
- media/camera/audio/device-capability failure;
- ART invariant violation or native fault;
- probe/oracle failure.

Each event records monotonic time, PID/TID, process, stage, owning component, exception/signal, relevant artifact hashes, and raw evidence references.

Every normalized marker additionally records its emission rule:

- source location and emitting component hash;
- sampled or unsampled;
- counter/logging gate;
- pre-fallback or post-fallback;
- thread naming/identity semantics;
- known false-positive and false-negative modes.

Before counting or trusting a marker, read the code that emits it. A derived count without its emission rule is not admissible evidence.

The existing `Tolerating clinit failure` runtime marker is a launch-path worklist, not ordinary noise. Preserve the first exception for each affected class and connect later null/partial-state failures only when the causal chain is demonstrated.

### 10.3 Independent oracles

At minimum capture:

- process and thread liveness;
- activity/lifecycle state;
- ViewRoot and view tree;
- screenshot/frame statistics;
- active input target and handled result;
- network/content markers where allowed;
- physical-panel observation for protected/capture-sensitive cases.

Controls are ordered from narrowest to broadest:

1. Within-process differential: two surfaces, windows, threads, activities, or paths in one run.
2. Same-APK repeat with one variable changed and deployment proven.
3. Focused contract/micro-APK control.
4. Cross-app control such as Noice or Material Catalog.

Within-process evidence receives its own evidence kind because it holds the runtime, APK, process, timing, and most state constant. Cross-app controls remain required for regression promotion but are not always the strongest causal test.

### 10.4 Re-entrant dynamic-code inventory

The static inventory is incomplete until runtime-loaded code has been reconciled.

At `P2` and later, capture:

- every `.dex`, `.jar`, `.apk`, and native library opened by the process;
- `PathClassLoader`, `DexClassLoader`, `InMemoryDexClassLoader`, and `DexFile` construction/open events;
- Tinker/Mira/plugin paths and content hashes;
- downloaded or extracted code artifacts where policy permits collection;
- in-memory DEX hashes and a retained copy only where legally and technically permitted.

Feed newly observed artifacts back through Phase B, associate their findings with the original run, and repeat resolution. Mark the inventory `incomplete-until-reentrant` until every observed loaded artifact is scanned or explicitly recorded as unavailable.

Track static coverage as both a count and byte/hash ratio of observed loaded DEX/JAR artifacts. A plugin-based APK cannot receive a high-confidence “no API gaps” result while loaded code remains unscanned.

## 11. Phase F: Reconcile and Classify

Static and dynamic findings are merged into a causal record.

The reconciliation engine should:

1. Link runtime failures to the normalized dependency when exact.
2. Promote runtime-confirmed reachability and severity.
3. Group downstream symptoms under an earlier causal gap only when evidence demonstrates the chain.
4. Keep competing hypotheses separate when causality is unproven.
5. Record refuted hypotheses and the control that refuted them.
6. Reclassify `CU` only when new evidence satisfies the class definition.
7. Separate APK dependencies from platform-self-skew, runtime-invariant, and observation-system origins.

Apply the stopping rule: if member-level, native, existence-probe, and re-entrant resolution are clean but behavior still fails, stop extending the APK gap list. Move the investigation to Westlake/OH ABI skew (`C10`), runtime integrity (`C7`), semantic boundary behavior (`C6`), or observation correctness (`O`). APK analysis cannot detect defects that originate solely in Westlake's compiled interface to the deployed OH platform.

For `C10`, compare the build-time headers/interface epoch against the mapped deployed binary using Build-ID, symbol/version data, structure measurements, and safe vtable inspection through `dladdr` on existing function pointers. Never invoke a guessed C++ virtual slot. A setter returning a plausible value belonging to another property is a strong wrong-slot candidate, not proof by itself.

## 12. Gap Registry and Deduplication

The portfolio value comes from deduplicating common gaps. Only `apk-dependency` records contribute to APK-gap prevalence; other origins are ranked in separate integrity work queues.

**Identity must be stable under reclassification.** §11 permits `CU → C*` promotion and §20 mandates
re-running a versioned classifier over retained scan data. If `mismatch_class` or `fault_origin` were
part of the key, both operations would **mint a new gap and orphan its history**: prevalence counts
reset, first-blocker attribution breaks across the boundary, and the §19 metric *time from first
observation to classification* becomes uncomputable — the observation would live under a key that no
longer exists. Anything a classifier can revise is an **attribute**, never part of identity.

Canonical gap key — identity only:

```text
runtime_lock_family
contract_layer
contract_owner
normalized API or symbol identity
signature/version/transaction
```

Versioned attributes carried on the record, each with revision history:

```text
mismatch_class      (C0-C10, CU; or O-OK/O-DEFECT/O-BLIND/O-UNKNOWN for O-layer findings)
fault_origin        (apk-dependency | platform-self-skew | runtime-invariant | observation-system | unknown)
confidence
reachability
severity
classifier_version
```

Examples (key | current attributes):

```text
N|libc|__system_property_get|(void)->int                  | C1  apk-dependency
J|android.webkit.WebViewFactory|getProvider()             | C4  apk-dependency
S|activity-lifecycle|fragment ON_CREATE ordering          | C6  apk-dependency
G|font-manager|CJK fallback family resolution             | C4  apk-dependency
R|interpreter|managed object result transfer              | C7  runtime-invariant
N|OH Surface interface epoch|SetDefaultUsage slot         | C10 platform-self-skew
O|render-service|protected-layer capture                  | O-BLIND observation-system
```

`runtime_lock_family` is omitted from the printed examples for brevity but is part of every key.

Filtering by `fault_origin` (per §12's prevalence rule) is a **query over attributes**, not a
property of identity — a gap reclassified from `apk-dependency` to `platform-self-skew` must keep its
history and simply leave the APK-prevalence counts from that revision onward.

Do not merge gaps solely because their exception text looks similar.

## 13. Portfolio Prioritization

Priority must be based on APKs unlocked, not raw reference counts.

For each canonical gap, calculate:

- number of unique APKs containing the dependency;
- number of APKs that reach it dynamically;
- number for which it is the first confirmed blocker;
- weighted importance of those APKs or categories;
- depth of the blocked stage;
- confidence in classification and causality;
- estimated engineering cost;
- regression and architectural risk;
- existence of an upstream/AOSP implementation or OH backend.

Do not publish a composite portfolio score while the corpus is unstratified or contains fewer than 25 APKs. In the calibration phase, rank by:

```text
observed stage transition unlocked
then correctness/cheapness of the class-specific fix
then regression risk
```

Once the corpus is stratified and at least 25 APKs have reproducible results, a useful score is:

```text
impact = weighted_blocked_apks
       * reachability_factor
       * severity_factor
       * confidence_factor

priority = impact / (estimated_effort * (1 + regression_risk))
```

The exact weights must be versioned and visible. The dashboard must display underlying counts before any score so the formula cannot hide weak evidence or manufacture precision from a small sample.

### 13.1 Recommended work queues

Maintain separate queues because risk and review differ:

1. Calibration detector failures and launch-path `<clinit>` damage.
2. Confirmed high-frequency `N-C1`/`J-C1`/`V-C1` entrypoints and strict `C8` markers.
3. Missing or hollow AOSP members (`C4`/confirmed `C9`).
4. Loader and namespace collisions (`N-C3`).
5. Shared lifecycle/service semantic gaps (`S-C6`).
6. Shared graphics/input/resource gaps (`G-C4/C6`).
7. Optional vendor hooks whose `C5` disposition is proven.
8. ABI-layout hazards (`N-C2`).
9. Platform-self-skew (`C10`) in a separate integrity queue.
10. Runtime invariants (`R-C7`) requiring the highest proof threshold.

## 14. Fix Playbooks and Proof Requirements

| Class | Minimum proof before implementation | Promotion gate |
|---|---|---|
| `C1` | Exact signature/ABI and equivalent target behavior | Contract test plus corpus rescan |
| `C2` | Measured structure/signature/encoding difference | Boundary stress test and native controls |
| `C3` | Loader trace showing wrong ownership/version | Deterministic namespace/order test |
| `C4` | AOSP app-facing contract and mapped OH capability | Android control trace versus OH trace |
| `C5` | Evidence that callers tolerate unsupported/no-op outcome | Target feature and unrelated-feature controls |
| `C6` | State/event trace proving semantic divergence | Lifecycle/service/graphics sequence tests |
| `C7` | Impossible transition relative to ART/AOSP invariant | Generic runtime test suite and multi-APK regression |
| `C8` | All identified uses are existence checks; no callable use in base or runtime-loaded code; runtime path advances | Presence-only fixture, target path, and re-entrant rescan |
| `C9` | Member is present; AOSP comparison proves its body is a placeholder rather than legitimate tiny behavior | Specific member contract test and framework controls |
| `C10` | Build/deployed ABI epoch mismatch measured without guessed calls | Stable C-ABI boundary test and known-good runtime smoke suite |

No fix is promoted merely because the original crash disappears. The expected user-visible stage must advance.

## 15. Corpus Strategy

Do not begin with hundreds of arbitrary APKs. Calibrate first, then expand.

### 15.1 Calibration corpus

Start with:

- Noice: known working application control.
- Material Catalog: broad Android widget/theme/layout control.
- Toutiao: multidex, native SDK, WebView, network, media, and vendor complexity.
- Small representative APKs for WebView, audio, video, camera, maps/location, notifications, background services, databases, Compose, Flutter, React Native, and Unity.

The calibration corpus is used to validate scanner precision, stage probes, taxonomy, and false-positive handling.

#### Control purity — audit before trusting any control

A control only measures unchanged-APK compatibility if the control itself is unchanged. **This is not
currently true of the calibration corpus**, and every conclusion calibrated against it inherits the
bias until it is resolved:

| APK | patch | status |
|---|---|---|
| Noice | `recipes/patch-noice-apk.sh` — app-dex surgery rewriting `invoke-interface`-on-Proxy call sites into a `westlake/WlProxy` helper; its own header records *"this is what made the sound library load"* | **`control-impure`** — a compatibility solution, not a diagnostic |
| Noice | `recipes/patch-noice-room.sh` (§485) — flips the app's Room DAO `inTransaction` flag to route a read off a wedged `TransactionExecutor` | **`control-impure`** |
| Noice | `recipes/patch-noice-trace.sh` | permitted — diagnostic instrumentation only |

**Required before Milestone 0 completes:**

1. Re-test each patch against the current runtime. `patch-noice-apk.sh` is the leading retirement
   candidate: it worked around the Proxy-dispatch defect that was subsequently root-caused and fixed
   in the platform (the validator calling `GetNameView()` on cross-dex proxy `ArtMethod`s). **A
   platform fix that lands should invalidate the app patch that worked around it.**
2. Retire every patch that is no longer required, and record the retirement with the platform fix
   that superseded it.
3. For any patch that cannot yet be retired, keep the APK flagged `control-impure`, state which
   flows depend on the patch, and exclude those flows — not the whole APK — from unchanged-APK
   metrics.

Generalised rule: **an unretired app patch is an open platform gap wearing a disguise.** Each one is
a `C*` finding that was worked around instead of being classified, and it should be entered in the
registry as such, with the patch recorded as its current mitigation.

### 15.2 Expansion corpus

Expand in controlled waves:

- 25 APKs across major architecture families.
- 100 APKs after static resolution and dynamic `P0`-`P4c` are reliable.
- 500+ APKs after board scheduling, artifact storage, deduplication, and result reproducibility are proven.

The corpus should be stratified by category, framework family, SDK level, ABI, native-library count, DEX count, popularity/importance, and permission/device dependence. A random convenience sample will bias priorities.

## 16. Scaling and Reproducibility

For hundreds of APKs:

- Cache scans by APK, DEX, ELF, resource, and certificate hash.
- Store raw evidence once and reference it immutably.
- Use clean per-run app data unless persistence is the tested variable.
- Assign a unique run ID and retain the runtime lock ID.
- Gate launches on measured readiness events.
- Enforce per-stage time and storage budgets while distinguishing timeout from crash.
- Detect contaminated runs: wrong PID, stale log, stale surface, sleeping panel, wrong input root, or changed runtime hash.
- Retry infrastructure failures separately from application failures.
- Forbid rebuilding components marked non-reproducible during a probe campaign; use exact preserved known-good artifacts.
- Run the runtime smoke suite after any approved runtime component change before accepting APK findings.
- Schedule destructive board resets only through an explicit board-pool controller.

## 17. Data Model

Illustrative per-finding record:

```json
{
  "finding_id": "sha256:.../finding/17",
  "apk_sha256": "...",
  "runtime_lock_id": "westlake-arm64-...",
  "fault_origin": "apk-dependency",
  "dependency": {
    "layer": "S",
    "owner": "activity-lifecycle",
    "name": "Fragment ON_CREATE host attachment",
    "signature": null
  },
  "classification": "C6",
  "confidence": "runtime-confirmed",
  "reachability": "P3",
  "severity": "first-blocker",
  "diagnostic_displacement": "immediate",
  "inventory_state": "reentrant-complete",
  "evidence": [
    {"kind": "within-app-differential", "uri": "evidence://..."},
    {"kind": "lifecycle-trace", "uri": "evidence://..."},
    {"kind": "exception", "uri": "evidence://..."}
  ],
  "proposed_owner": "OH activity boundary",
  "permitted_fix": "preserve AOSP lifecycle ordering; adapt OH dispatch",
  "status": "open",
  "controls": ["noice", "material-catalog"]
}
```

The production schema should be versioned and validated. Raw evidence is never embedded when it can be content-addressed.

## 18. Proposed Tool Interface

```text
westlake-apk-gap snapshot-runtime --board <target> --out runtime-lock.json
westlake-apk-gap scan <apk-or-directory> --runtime runtime-lock.json
westlake-apk-gap detect-existence-probes <scan-set>
westlake-apk-gap detect-members <scan-set> --platform-index <index>
westlake-apk-gap detect-unbound-natives <scan-set> --runtime runtime-lock.json
westlake-apk-gap resolve <scan-set> --platform-index <index>
westlake-apk-gap plan <resolved-set>
westlake-apk-gap probe <plan> --board-pool <pool> --profile p0-p4c
westlake-apk-gap reconcile <scan-set> <run-set>
westlake-apk-gap prioritize <gap-registry>
westlake-apk-gap report <portfolio>
```

The first implementation can wrap existing tools. A unified custom parser is not required to prove the process.

## 19. Metrics

Track at least:

- APK count and unique component count scanned.
- Static scan success and resolution coverage.
- Required-member resolution coverage, not only class coverage.
- Existence-probe candidates and the fraction passing strict `C8` proof.
- Hollow-member candidates versus confirmed `C9` findings.
- Runtime-loaded DEX/JAR coverage by observed artifact count and bytes/hashes.
- Findings by layer/class/confidence.
- Dynamic probe reproducibility rate.
- Pass rate by stage `P0`-`P8`, including separate `P4a`, `P4b`, and `P4c` states.
- Tolerated `<clinit>` failures on the launch path and their downstream causal dispositions.
- First blockers by canonical gap.
- APKs unlocked per promoted platform fix.
- False-positive and false-causality rates.
- Regression rate against controls.
- Findings invalidated by a runtime rebuild or failed runtime smoke test.
- Derived markers lacking a verified emission rule; target is zero in published reports.
- Time from first observation to classification and fix.
- Number of app-specific patches proposed versus rejected.

The primary success metric is not “number of shims added.” It is the number and depth of unchanged APK flows enabled by Android-faithful platform fixes.

## 20. Refinement Loop

The process itself is a versioned product.

After every scan wave:

1. Review every `CU`, misclassification, false positive, and contaminated probe.
2. Update taxonomy rules without rewriting historical results.
3. Version the classifier and re-run classification over retained scan data.
4. Add a contract test for every promoted fix.
5. Add a probe/oracle test for every infrastructure failure mode.
6. Review marker emission rules and known distortions whenever instrumentation changes.
7. Re-run known-answer calibration fixtures before recalculating portfolio priorities.
8. Publish what changed and why.

Refuted hypotheses are retained. Re-discovering a disproven explanation across many APKs is a portfolio-level waste.

## 21. Implementation Roadmap

### Milestone 0: Three detectors, one calibration corpus

- Run only Toutiao, Noice, and Material Catalog.
- Implement the `C8` existence-probe data-flow scan.
- Implement member-level framework resolution and the `C9` hollow-candidate scan.
- Implement the DEX-native to registered/exported JNI join.
- Produce human-readable evidence including every proving call site.
- Require the known-answer fixtures below to pass before expanding scope.

### Milestone 1: Static-initializer severity gate

- Capture every `Tolerating clinit failure` event with its original exception.
- Add `clinit-on-launch-path`, `deferred-corruption`, and diagnostic displacement.
- Connect downstream symptoms only when the causal chain is demonstrated.
- Use this worklist to rank calibration gaps before any portfolio score exists.

### Milestone 2: Re-entrant code inventory

- Capture runtime-loaded DEX/JAR/APK and native artifacts.
- Rescan Tinker, Mira, plugins, extracted, downloaded, and in-memory code where available.
- Report inventory completeness and dynamic-code coverage.
- Refuse a high-confidence clean result while observed loaded code is unscanned.

### Milestone 3: Runtime lock and dynamic `P0`-`P4c`

- Snapshot the current arm64 runtime, including reproducibility and known-good qualification.
- Establish deterministic launch, PID/log ownership, and marker emission metadata.
- Capture structured exceptions, JNI/loader failures, lifecycle, ViewRoot, compositor presentation, capture, and panel evidence.
- Implement within-process differential evidence and cross-app regressions.
- Produce a reconciled first-blocker report with the fault origin and stopping rule applied.

### Milestone 4: Registry and portfolio prioritization

- Expand to a stratified 25-100 APK corpus.
- Build the canonical gap registry and component-hash deduplication.
- Publish underlying counts before any composite score.
- Enable impact/effort/risk scoring only after at least 25 APKs have reproducible results.
- Add dashboard and class-specific work queues.

### Milestone 5: Deep feature probes and scale

- Probe input, network/content, WebView, media, dialogs, navigation, background work, and pause/resume.
- Expand to `P5`-`P8`.
- Scale to 500+ APK scheduling and immutable evidence retention.

## 22. Definition of Done for Version 1

Version 1 is ready for portfolio decisions when:

- The three calibration detectors pass all known-answer fixtures below.
- The same APK/runtime pair produces reproducible stage and first-blocker results.
- Noice and Material Catalog controls can distinguish scanner/probe regressions from target failures.
- Runtime-loaded code coverage is reported and incomplete inventories cannot appear clean.
- Known Toutiao gaps are classified without app-bytecode fixes, while platform/runtime defects are excluded from APK-gap prevalence.
- At least 100 stratified APKs have complete static scans.
- At least 80% have reproducible `P0`-`P4c` outcomes or an explicitly classified infrastructure/oracle blocker.
- Shared gaps are deduplicated and ranked with visible supporting counts.
- Every top-ranked gap names the required proof and allowed architectural response.
- A promoted fix can demonstrate how many unchanged APKs and stages it unlocked.

### 22.1 Executable known-answer fixtures

| Expected result | Required disposition | What it tests |
|---|---|---|
| `com.android.org.conscrypt.SSLParametersImpl` existence probe | `J-C8` candidate with proving `Class.forName`/loader flow | Existence-only detection rather than string demotion |
| `android.graphics.ColorMatrix.set([F)V` requirement against a hollow/incomplete class | Missing member or `J-C9` candidate according to the exact deployed body | Member-level resolution and hollow detection |
| ByteDance optimizer/profiler native declarations without implementation | `V-C1`; optional `V-C5` disposition only after runtime proof | DEX-native to JNI implementation join |
| ByteDance handler threads terminate after those missing natives | Causal `V`-to-`S` failure chain | First-cause reconstruction across layers |
| ART iftable out-of-bounds read | Must not count as an APK gap; origin `runtime-invariant`, `R-C7` | Scanner scope and stopping rule |
| OH `Surface` build/deployed vtable epoch mismatch | Must not count as an APK gap; origin `platform-self-skew`, `N-C10` | Platform-self-skew detection and scope |
| Protected capture with populated view tree | `P4a=pass`; `P4c=oracle-unavailable` when panel truth is unavailable | Observation-system semantics |

Missing any expected APK-level fixture means the detector is incomplete. Reporting either runtime/platform fixture as an APK dependency means the scope or origin classifier is wrong.

## 23. Bottom Line

The APK Gap Probe is an evidence and prioritization system, not a stub generator.

Its purpose is to tell Westlake where Android compatibility is incomplete, which layer owns the defect, how the defect may be repaired without inventing new app-facing semantics, and how many APKs that repair is likely to unlock.

At scale, this lets the project invest in shared Android/OH boundary completeness instead of repeatedly rediscovering the same failures one APK at a time.
