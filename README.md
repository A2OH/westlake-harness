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
| `evidence/TOUTIAO-BRINGUP-HANDOFF.md` | The empirical base: a full app bring-up with fixes, **nine refuted hypotheses**, build hazards, and harness notes. |
| `harness/` | `ttwalk.sh` (launch/drive/measure), `shotlit.py` (quantify a capture), `tools/` (dexlib2 analysers — the building blocks of the detectors). |

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

## Getting started

1. Read `requirements/APK-GAP-PROBE-PROCESS.md` §1–§4 (purpose, principle, hard rules, taxonomy).
2. Read `analysis/APK-GAP-PROBE-REVIEW.md` for what the process still gets wrong and why.
3. Implement **Milestone 0** — three detectors over a three-APK calibration corpus:
   - `C8` existence-probe scan (`const-string` → `Class.forName`/`findClass`, with no invoke)
   - `C9` member-level resolution and hollow-body scan
   - DEX-native → registered/exported JNI join
4. Gate on the **known-answer fixtures**: the detectors must independently rediscover the documented
   hollow class, the probe-only class and the unbound natives — and must **not** report the runtime
   invariant or the ABI-skew defects, which are not APK gaps.

Miss the first three and the extractor is wrong. Report the last two and the scope is wrong.

---

## Conventions

Paths in these documents are written as environment variables (`$WESTLAKE_ROOT`, `$BRIDGE_ARM64`,
`$OHOS_SDK`, `$HDC`, `$BOARD_SERIAL`, …) rather than absolute local paths. See `env.sample.sh`.
Device serials, usernames and host paths are deliberately excluded from this repo.
