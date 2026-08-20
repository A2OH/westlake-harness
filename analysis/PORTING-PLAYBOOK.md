# Porting playbook — four ways to find a wall

How to debug an Android app running on this OpenHarmony/ART port, ordered by cost. Run them
**in parallel across different APKs** — the board is the only serial resource (~5 min per launch),
so analysis, instrumentation and host builds should never queue behind it.

Derived from the 2026-08-14/16 Toutiao bring-up, where every tier was used and three of the four
produced a wrong answer at least once.

---

## Tier 0 — instrument the RUNTIME (cheapest, app-agnostic, do this first)

Add or un-gate diagnostics in libart / the bridge / appspawn-x. One change serves every app.

**Why first:** the biggest wins of the session came from here, not from app instrumentation.
`PFCUT-NPE-ARRAY-LENGTH` already existed and had **never fired** because it was gated on an
environment variable; un-gating it named the bug that was blocking `Application.onCreate` in a
single run — on a closed-source, obfuscated app, with no app-side work at all.

**Cost:** one libart rebuild (~2 min) + one board run.

### Gating rules (each learned the hard way)
| Rule | Why |
|---|---|
| ⛔**Never gate on `getenv()`** | environment variables do **not** reach appspawn-x children. Verified: exported in `run_*.sh`, 0 hits in the child's `/proc/<pid>/environ`. §657 |
| ✅**Gate on a file** | the child runs as an app uid; it can **read** root-owned `/data/local/tmp/asx` but not write there. Use `access("/data/local/tmp/asx/FLAG", F_OK)`. For per-process triggers use the world-writable `/data/service/el1/public/appspawnx/` |
| ⚠️**Caps hide the rare event** | §643's cap was `static int … < 30`, **global across all callers**. `CRC32.update` exhausted it before the method I was hunting ever ran, and I wrote down "definitively dead" for a hypothesis that was true. Filter first, then cap, and make the cap per-key |
| ⚠️**Hot-path logging owns the clock** | the PFCUT predicate layer already costs ~31% of interpreter time vs 3.67% actually interpreting. §650: 54,168 trace lines made a **stalled** app look like it was progressing |
| ⚠️**Check the file is compiled** | `art-latest/patches/**` is only used where `Makefile.ohos-arm64` has an explicit rule. `common_throws.cc` has none, so the patches/ copy is dead code and edits do nothing. `grep -n <basename> Makefile.ohos-arm64` first |

---

## Tier 1 — WHITE BOX: app sources available

noice (`com.github.ashutoshgngwr.noice`) and the Material Design Catalog are open source.

**The real value is not logging your own app — it is the DIFFERENTIAL.** Run the same instrumented
build on a real Android device and on the port, then diff the API call sequence. What that yields is
knowledge about the **shim**, which is app-agnostic and transfers to the closed-source apps.

Use for: mapping which framework surface an app touches; proving a shim returns the wrong *value*
(as opposed to failing outright); building a conformance probe.

⚠️Do **not** rebuild these apps from source just to instrument them — see Tier 2, which works off
the on-device APK and additionally preserves prior smali surgery that a source rebuild would discard.

---

## Tier 2 — GRAY BOX: only the dex (works on obfuscated apps)

**Already built in this tree** — no Gradle, no AGP, no Kotlin toolchain, no app sources:

- `westlake-arm64/arm64-session-2026-07-29/recipes/patch-noice-trace.sh` — the template. Line 15
  pulls the APK **off the device**, injects, pushes back.
- `…/tools/InjectTrace.java`, `PatchLog.java`, `DexMerge.java` (+21 more dexlib2 tools)
- `…/java/westlake/WlTrace.java` → `adapter/compat/WlProbe.java` → native sink in `AndroidRuntime.cpp`
- dexlib2 3.0.3 classpath exported by `recipes/env.sh` as `DEXLIB_CP`

**`PatchLog.java` injects at every `MOVE_EXCEPTION`** — i.e. every catch handler — so it finds
*swallowed* exceptions in classes named `X.AMO`. Obfuscation does not matter.

★Design trick worth reusing (`InjectTrace.java:14-17`): make **each trace site a distinct zero-arg
static method**, so the injected instruction needs no free register. Register reallocation is where
dex injection normally breaks.

Use for: closed-source apps; finding where an exception is caught and discarded; bisecting which
code path is reached.

---

## Tier 3 — BLACK BOX: run, fault, disassemble (slowest AND most error-prone)

Only when nothing above applies. Tools in `bridge-build-arm64/`: `pttrap2.c` (PTRACE_SEIZE +
re-deliver, all 31 GPRs + siginfo), `memrd.c` (`/proc/pid/mem`, no ptrace, no perturbation),
`sym.py` (maps → file offset → **owning PT_LOAD** → vaddr → `st_size` containment).

⛔**This tier produced a completely wrong, fully-argued root cause.** A missing `p_vaddr − p_offset`
delta (0x1000) symbolized one page off, into a neighbouring function with a plausible name, and
generated a whole "32-bit method linker in a 64-bit process" story. See `sym.py` and §630.

★The check that catches it: **can the instruction you landed on actually fault?** A register-only
`add x10, x10, #1` can never SIGSEGV. If the instruction cannot produce the signal you observed,
the address is wrong — do not rationalize it.

---

## The rule that outranks the tiers

**Measure the value; do not infer it.**

- §641 — three rounds of post-mortem register analysis produced one wrong hypothesis and no answer.
  A 20-line probe that simply *logged the arguments the shim received* answered it in one run
  (`thiz == env + 4` ⇒ the caller was passing raw vreg-slot addresses).
- §657 — the diagnostic that named the blocking bug had existed all along, disabled.
- §652 — `memrd` on the bytes **around** a contended futex returned the owner TID directly.

Corollary: when a hypothesis needs a build to test, first ask whether **config alone** can test it.
§653 disproved an entire theory by launching with one environment variable omitted — no build at all.

---

## Running the three boxes in parallel

The board is one device; everything else is not. In practice:

1. Keep **one** app on the board at a time, and batch several probes into that single build.
2. Meanwhile: dex-inject a second APK (Tier 2), diff a third against real Android (Tier 1),
   and run source analysis / codex consults on the host.
3. Land Tier 0 fixes continuously — they benefit whichever app is on the board next.

⛔**Always run the control.** Every runtime change is global: noice and the catalog must still launch
after it. That control run caught an over-broad §632 guard and a §634b change that broke the zygote.
