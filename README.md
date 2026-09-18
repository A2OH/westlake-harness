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

Each of those cost real time on the hardest app attempted. **All of them were statically visible.**

The core claim of this repo:

> The APK's DEX already lists every platform API it can touch. The runtime's boot jars already list
> what is provided. **Subtract before you launch**, rank by where the gap is reached, and apply the
> cheapest repair that the gap's class allows.

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
| `analysis/NATIVE-GAP-PROCESS-AMENDMENT.md` | **Amendment closing the native half of the subtraction**: native import resolution, blast radius, `N-C8` probe-only absence, provenance-driven repair routing, `N-C9` hollow shims, coverage accounting. |
| `analysis/NATIVE-PROVENANCE-AND-SURFACE.md` | **Native side of the same subtraction**: which upstream component a stripped `.so` contains, and which Android surfaces each registered JNI method reaches. |
| `evidence/TOUTIAO-BRINGUP-HANDOFF.md` | The empirical base: a full app bring-up with fixes, **nine refuted hypotheses**, build hazards, and harness notes. |
| `harness/westlake_gap/` | Production static scanner: ordered runtime index, multidex/split APK inventory, member resolution, `C8`/`C9` detection, ELF/JNI evidence, gap registry, and report. `nativeprov.py` adds component provenance and per-method platform-surface reach (`native-surface`). |
| `runtime/TRACE-EVIDENCE.md` | Native/reflection watchlists, structured event envelope, ART hook points, and evidence-promotion rules. |
| `harness/` | `ttwalk.sh` (launch/drive/measure), `shotlit.py` (quantify a capture), and older focused dexlib2 investigation tools. |
| `harness/jniprobe/` | Frida agent and scenario drivers that record `RegisterNatives`, `dlopen` and `dlsym` from a running app, plus the Frida-17 and Magisk obstacles the first run hit. |
| `tests/` | Executable known-answer fixtures: `ColorMatrix.set`, a Conscrypt existence probe, an unbound vendor native, and an arm64 JNI library whose platform-coupled and pure methods are known in advance. |
| `corpus/` | Reproducible top-ten selection plus exact download hashes. APK/XAPK binaries are deliberately ignored. |
| `benchmark/2026-08-20/` | Completed ten-app benchmark report, deduplicated registry, and runtime lock. |
| `benchmark/2026-08-21/` | ABI-aware redo against the current ARM64 runtime lock; the prior benchmark remains preserved. |
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

## Current implementation

Milestone 0 static detection is implemented. The scanner:

- hashes and indexes an ordered boot classpath, honoring first-definition-wins for duplicate classes;
- scans every supplied DEX across APK, XAPK, and APKM base/split containers;
- resolves classes, methods, and fields through superclass/interface inheritance;
- traces direct string-register flows into `Class.forName`, `findClass`, and `loadClass`;
- flags directly absent contracts separately from small constant/no-op body heuristics;
- inventories target-ABI ELF dependencies, symbols, build IDs, JNI exports, and `JNI_OnLoad` evidence;
- recovers relocation-backed static `JNINativeMethod` tables and correlates them with DEX-native
  contracts and same-DEX `System.loadLibrary` provenance;
- resolves APK and runtime-bridge JNI exports separately, and reports unavailable/mismatched ABIs
  instead of borrowing evidence from another architecture;
- keeps unresolved dynamic JNI registration out of the published gap count;
- emits per-APK JSON, a deduplicated registry, and a Markdown portfolio report;
- generates runtime watchlists and joins structured or legacy Westlake JNI/class-load traces into an
  evidence ledger with safe terminal/non-terminal state transitions.

The executable fixture must pass before portfolio use:

```bash
PYTHONPATH=harness python3 -m unittest discover -s tests -v
```

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
