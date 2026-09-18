# Amendment: closing the native half of the subtraction

**Status.** Item 1 and its fixtures are implemented. Items 2–6 are specified here and not yet built.

The process spec's core claim is *subtract before you launch*: the DEX lists every platform API the
app can touch, the runtime lock lists what is provided, subtract, rank, repair. That subtraction is
performed for Java. **It is not performed for native imports**, and the shim surface Westlake
actually implements is the one nothing measured.

---

## 0. The measured gap

| Evidence | Measurement |
|---|---|
| `read_elf` records `undefined_symbols` | `scanner.py:317` — and no detector consumed it |
| Runtime lock native coverage | **one** bridge library (`liboh_adapter_bridge.so`, 3235 exports); no system libraries |
| What Toutiao's 138 arm64 libraries import | **374 distinct platform-surface symbols** across **53 sonames** — 137 need `libc`, 116 `liblog`, 30 `libandroid`, 13 `libjnigraphics` |
| Findings produced from all of that | **zero** |

The Java side resolves member-level references against an ordered boot classpath. The native side
collected the equivalent inventory and dropped it.

---

## 1. Native import resolution — `N-C1` / `N-C5` *(implemented)*

`resolve_native_imports()` joins every packaged ELF's undefined symbols against three provider
tables in precedence order — deployed system libraries, the bridge, then other app-bundled ELFs —
and emits one record per symbol, aggregating the libraries that import it so the canonical gap
deduplicates across a corpus on the symbol itself.

| State | Class | Meaning |
|---|---|---|
| `provider-resolved` | `C0` | some indexed library exports it |
| `weak-undefined-unresolved` | `N-C5-candidate` | weak undefined; absence is legitimate by design |
| `cxx-runtime-internal` | `CU` | `_ZNSt*`, `__cxa_*` — resolves from whichever libc++ wins the namespace; an `N-C3` ordering question, not a missing shim |
| `runtime-system-index-unavailable` | `CU` | **no system libraries indexed — absence cannot be claimed** |
| `no-provider` | `N-C1-candidate` | indexed runtime, nothing provides it |

The fourth row is the rule that makes the detector safe to turn on today. With the current
one-bridge-library lock, a naive resolver would report all 374 platform symbols as missing. Instead
each one is `CU`, and the scan emits an `O-BLIND` coverage finding naming the missing index, so
"no finding" can never be read as "no gap".

`snapshot-runtime` gains `--system-lib` (repeatable) to index the deployed `libc`, `liblog`,
`libandroid`, `libjnigraphics`, `libEGL` and friends. **Until an operator supplies those, this
detector is honest and nearly silent — which is the correct failure mode.**

---

## 2. Blast radius instead of symbol counts *(implemented for the native half)*

`attribute_unresolved_imports()` walks the call graph from each recovered JNI entry and reports
which registered methods reach an unresolved symbol. `scan --native-reach` attaches the result to
every finding as `reaching_methods`.

That converts *"libX is missing 12 symbols"* into *"this symbol breaks these 4 app-facing methods."*
§13's `impact` formula has a `reachability_factor` with no native input; this supplies one.

**Still to build:** joining those method names back to their DEX call sites, which is what turns a
reaching method into a launch-path verdict. The DEX inventory already records callers, so this is a
join, not new analysis.

---

## 3. `N-C8` — probe-only absence on the native side *(proposed)*

`C8` exists because a presence probe produces **no error at the missing thing**; it silently takes
the wrong branch and fails elsewhere. The native form of that is `dlsym` returning null.

**279 of 1417 recovered methods (20%) reach `dlopen`/`dlsym`.** A symbol resolved that way does not
crash when absent — the app takes a fallback path, and the failure surfaces somewhere else entirely,
which is precisely the diagnostic displacement `C8` was added to catch.

`dynamic_symbol_candidates()` already recovers probed names from the string table. The detector is
that set minus what the runtime exports; each survivor is an `N-C8` candidate carrying
`failure_severity: degraded-behaviour` and `diagnostic_displacement: delayed`. The same strictness
`C8` demands on the Java side applies: a probed name is a candidate, never a proven marker.

---

## 4. Provenance as repair routing *(proposed)*

Three decisions that currently need a human, made mechanical by `identify_components()`:

| Evidence | Classification | Why the current process misses it |
|---|---|---|
| Unresolved symbol belongs to a component the library *contains* | not a platform gap; app-bundled and self-contained | would otherwise inflate `apk-dependency` frequency counts |
| Same component contained by app **and** runtime, different versions | `N-C3` duplicate-runtime candidate | §4.4 names `libc++_shared.so` capture as the example and nothing detects it — Toutiao contains libc++ in **9** libraries *and* ships `libc++_shared.so` |
| Runtime provides the same soname at a different version | `N-C2`, never `C0` | symbol-name matching alone calls it present; Hard Rule 4 forbids exactly that |

The third row makes Hard Rule 4 mechanical instead of advisory: mbedTLS 2.1.12 and OpenSSL 1.0.2 vs
3.x match by name and differ in semantics.

---

## 5. `N-C9` — hollow shim detector, pointed at our own bridge *(proposed)*

Today an exported name in `liboh_adapter_bridge.so` resolves as `C0` whether it is an
implementation or `mov w0, #0; ret`. The Java side already has `C9` for a member that is present but
hollow; the native side has no equivalent, and a name-only shim is the specific thing Hard Rule 4
forbids.

Detector: disassemble each bridge export, flag bodies under an instruction-count threshold whose
only effect is to return a constant. Same discipline as Java `C9` — a candidate for AOSP comparison,
never automatic proof, because legitimate getters and deliberate no-ops are also small. Fault origin
is `platform-self-skew`, not `apk-dependency`: this is our defect, and it belongs in the integrity
queue beside `C10`.

---

## 6. Honest coverage accounting *(partly implemented)*

- **78 of 138 libraries** yield no statically recoverable registration table. Emit an `O-BLIND`
  finding per library so silence is recorded as blindness, not absence.
- The reach walk is **AArch64 only**; the corpus carries an armv7 benchmark. Per-ABI `O-BLIND`
  until the arm32 PLT form is handled.
- Two metrics for §19: **native resolution coverage** (share of undefined symbols with a decided
  classification) and **unproven verdict share** (methods whose clean result depends on unread
  `dlsym` strings — currently 20%).

---

## 7. Known-answer fixtures (§22.1)

| Fixture | Asserts | Status |
|---|---|---|
| Library importing one symbol the runtime provides and one it does not | exactly one `N-C1-candidate`, and it names the reaching method | **implemented** |
| No system libraries indexed | unresolved symbols are `CU`, never `N-C1` | **implemented** |
| Weak undefined symbol | `N-C5-candidate`, never missing | **implemented** |
| `dlsym`-probed absent symbol | one `N-C8` candidate | to build |
| Constant-return bridge export | one `N-C9` candidate, origin `platform-self-skew` | to build |

---

## 8. Correction to the earlier measurements

The first corpus run followed only `bl` edges. At -O2 a function whose last act is another call
compiles to an unconditional `b`, so whole subtrees were invisible. Tail calls into known function
entries are now followed, and the figures moved substantially:

| Measure | First run (`bl` only) | Corrected |
|---|---|---|
| methods reaching no platform surface | 878 (62%) | **659 (47%)** |
| platform-coupled methods | 68 (5%) | **175 (12%)** |
| methods reaching `dlopen`/`dlsym` | 227 (16%) | **279 (20%)** |
| methods reaching `libandroid` | 16 (1%) | **122 (9%)** |
| methods reaching `ptrace`/`fork`/`prctl` | 165 (12%) | **333 (24%)** |

Every one of those moved in the same direction, which is the expected direction for a lower bound
that was missing edges. It is also a reminder that a lower bound is only as good as the edge types
it follows, and that indirect calls — still unfollowed — mean the corrected numbers are themselves
a floor.
