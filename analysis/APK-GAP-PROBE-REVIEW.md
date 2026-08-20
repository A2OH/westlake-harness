# Critical review — WESTLAKE-APK-GAP-PROBE-PROCESS.md v0.1

**2026-08-19.** Reviewed against what was actually measured bringing up **noice**, **Material
Catalog** and **Toutiao**. Every criticism below cites a specific defect from those bring-ups.

**Verdict:** the architecture is sound and the taxonomy is better than a flat list. Two things
would stop it being useful in practice: (1) the cheapest, highest-yield detectors are missing
entirely, and (2) the roadmap builds the portfolio machinery before the detectors that justify it.
Seven substantive gaps follow, each with a concrete fix.

---

## 0. Keep these — they encode real lessons

- **`O` (observation system) as a first-class contract layer.** This is the single best idea in the
  document. It directly encodes the most expensive error of the Toutiao bring-up: a screenshot
  oracle that was *lying by design*.
- **`CU` — insufficient evidence — as an explicit class**, and Hard Rule 6 "unknown remains
  unknown." Nine hypotheses were argued confidently and refuted; a mandatory "not yet classified"
  state is the structural fix for that.
- **Hard Rule 5, preserve the first causal failure**, and §11.4 keeping competing hypotheses
  separate until causality is proven.
- **§20 retaining refuted hypotheses.** Re-deriving a disproven explanation is the dominant waste
  at portfolio scale.
- **§14: "No fix is promoted merely because the original crash disappears. The expected
  user-visible stage must advance."** This is exactly the §675 `ColorMatrix` lesson — the fix was
  real, removed two `<clinit>` failures, and moved the app forward *not at all*.
- **§15 calibrate before expanding.**

---

## 1. ⛔ The highest-yield detector in the whole method is missing: **existence probes**

**The gap.** `Class.forName` / `forName` / `findClass` appear **zero times** in the document.
Phase B §7.2 collects "reflection, class-name … string candidates" and then demotes them:
*"String candidates are hints, not confirmed dependencies… lower-confidence."*

**Why that is backwards.** The single fix that unblocked Toutiao's entire network stack was exactly
such a string. OkHttp's platform detection does nothing but ask *"does
`com.android.org.conscrypt.SSLParametersImpl` exist?"* to choose a code path. It never calls a
method on it. The class was absent from all ten BCP jars, both builders returned null,
`Platform.<clinit>` threw `NullPointerException: No platform found on Android`, and **every HTTP
request silently died** — feed empty, category names empty.

That failure is invisible three ways over:
- no error at the missing class (the probe just returns null);
- the exception names a *different package* and no missing symbol;
- a naive reference diff marks it **satisfied-adjacent** — the string is referenced, nothing is
  invoked, so member-level diffing finds nothing.

**Fix — add a distinct mismatch class and a detector.**

| new class | definition | correct response |
|---|---|---|
| `C8` **probe-only absence** | referenced *solely* as a class-name string reaching `Class.forName`/`findClass`, with **no invoke/field access** on the resulting type | **presence-only stub**: an empty class with the correct FQN, documented as "resolvable, never callable" |

Detector (≈50 lines of dexlib2): find `const-string` → `invoke-static Class.forName` / `findClass`
pairs; resolve the string against the platform index; if absent **and** the type has no
method/field reference anywhere in the corpus, emit `C8`.

**This also requires amending Hard Rule 4.** As written — *"Do not stub by name alone. A symbol
name does not establish ABI, lifecycle, state, timing, security, or failure semantics"* — it forbids
the correct fix for `C8`. The rule is right for callable contracts and wrong for probes. Amend to:

> Do not stub by name alone **for any contract the app invokes**. Where static evidence proves the
> app only tests for existence and never invokes the type, a presence-only stub *is* the faithful
> answer, and must be recorded as `C8` with the proving call sites.

---

## 2. ⛔ No class for **hollow** contracts — and this port manufactures them

**The gap.** `hollow`/`empty body` appear zero times. `C0` is "present and compatible"; a
reference-level diff sees `android.graphics.ColorMatrix` in `adapter-mainline-stubs.jar` and marks
it satisfied. The deployed class was **`<init>()V` and nothing else** — no `set(float[])`, no
`setSaturation`, no `setScale`.

Consequence: Toutiao's `AsyncImageView` and `UiUtils` both died in `<clinit>` on
`NoSuchMethodError`, and were left half-initialised.

`C6` doesn't cover it — that's state/lifecycle/ordering divergence, not an empty method body.

**This matters doubly here:** the port *deliberately generates* hollow implementations. The `PFCUT`
compat layer returns null for "I don't know," and the mainline-stubs jar is a jar of stubs by
design. Westlake is a **producer** of `C-hollow` gaps, not merely a consumer of them.

**Fix — add:**

| new class | definition | detector | response |
|---|---|---|---|
| `C9` **declared but hollow** | type present, but the required member is absent, or its body is empty / returns only a constant | member-level diff (not class-level); plus `codeUnits <= 2` returning a constant ⇒ flag for review | implement the specific member from the AOSP contract |

★ **Resolution must be member-level, not class-level.** Class-presence resolution would have marked
`ColorMatrix` satisfied and missed the defect entirely.

---

## 3. ⛔ `<clinit>` is absent from the severity model — and it is the worst severity we have

**The gap.** `clinit` appears zero times. §9's `failure_severity` ladder is
*process cannot load / crash / hang / blank UI / broken feature / degraded*.

**What actually happens here.** This runtime **tolerates** static-initialiser failures and logs
`Tolerating clinit failure for L…;`. The class is then left **half-initialised with null statics**.
Nothing throws at the point of damage. The `NullPointerException` arrives later, in unrelated code,
naming nothing useful. On Toutiao this counter ran at **12 per launch**, and two fixes took it to 9.

That is not "crash" and not "degraded" — it is **delayed, displaced corruption**, and it is the
single most expensive severity to debug.

**Fix.**
- Add reachability tier **`clinit-on-launch-path`**, ranked above `direct`.
- Add severity **`deferred-corruption`**, ranked above `crash` (it is *harder*, not milder).
- Wire the existing runtime log as ground truth: the `Tolerating clinit failure` lines are a
  ready-made, per-launch S0 worklist that requires no new tooling.

---

## 4. ⛔ The instrumentation itself is a documented liar — `O` must cover marker semantics

**The gap.** `O` covers oracles (capture, input root, timing) but not **log-marker semantics**.
`sampled` appears zero times. Every one of the following cost real time:

| trap | what it looked like | truth |
|---|---|---|
| `[G214au_HWR]` counters | "only 1 frame ever presented" | markers log **only** at `n==1 \|\| n%30==0` — 28 draws can never print `#2` |
| `[WESTLAKE-JNIMISS]` | "native is unbound" | printed **before** ART's `dlsym(RTLD_DEFAULT)` fallback — does not mean unbound |
| `tid == pid` | "UI thread deadlocked in futex" | tid==pid is **not** the UI thread in this port |
| `onResponse`/`onFailure` greps | "no callbacks ever fire" | useless on an obfuscated app — its callbacks aren't named that |

**Fix.** Add to `O`: *before counting or trusting any marker, read the code that emits it.* Every
normalized event type in §10.2 should carry a "known distortions" field, and every derived count in
a report should record the emitting condition (sampled? gated? pre-fallback?). A count without its
emission rule is not evidence.

---

## 5. ⛔ No class for **our own** ABI skew against the deployed platform — and no stopping rule

**The gap.** The layers describe what the *APK* depends on. But the defect that actually made
Toutiao render as a protected black layer was **ours**: the bridge called OH's `Surface` through
typed C++ virtual calls compiled against a **newer header than the deployed
`libsurface.z.so`**. Slots didn't line up; a nominal getter scribbled a live stack address into
consumer `defaultUsage_`; one stray bit in that garbage meant "DRM-protected."

`N-C3` is loader/namespace/duplicate-runtime collision — not this. `R-C7` is an ART invariant — not
this either.

**Fix — add:**

| new class | definition | detector | response |
|---|---|---|---|
| `C10` **our-side ABI/version skew** | Westlake code calls a deployed OH library through an interface whose build-time layout ≠ the deployed layout | compare build headers vs the **mapped** binary: Build-ID, `nm -D` symbol sets, vtable slot order via `dladdr` on `*vptr` (**never invoke a guessed slot**), struct sizes/offsets | move the call to the stable **C ABI**; treat typed C++ virtual calls across the boundary as unsafe by default |

★ **A cheap oracle worth institutionalising:** `Surface::SetDefaultUsage` returned **1790/1920** —
the surface *height*. A setter returning a plausible value from a *different* getter is a
wrong-slot signature. Add "return value looks like another property" to the detector.

★ **And add the stopping rule the document lacks:**

> If the gap probe resolves clean and the app still fails, the defect is probably **on our side of
> the boundary or in the runtime**, not in the API surface. Stop scanning the APK.

Two of Toutiao's four hardest defects (the iftable OOB, this ABI skew) are **invisible to APK
analysis by construction**. Saying so explicitly prevents the scanner being trusted past its scope.

---

## 6. ⚠️ Plugin/dynamic dex is acknowledged but never operationalised

§7.2 collects `System.load`/`loadLibrary` strings, and §1 admits downloaded code is out of scope —
but no phase ever **re-scans dex the app loads at runtime**.

Toutiao ships **Tinker + Mira** and 21 dex files, and loads plugin jars
(`plugins/com.ss.android.share_token_rule.jar` was observed failing to open). For plugin-based
apps — a large fraction of the Chinese app corpus this project targets — the static inventory is
**systematically incomplete**, not merely approximate.

**Fix.** Make the scan **re-entrant**: at `P2`/`P3`, capture every dex/jar the app actually opens
(`DexPathList.findLibrary`, `Linux.open` on `.dex`/`.jar`, `PathClassLoader` construction), feed
those artifacts back through Phase B, and mark the APK's inventory `incomplete-until-reentrant`
until that closes. Track "% of loaded dex covered by static scan" as a §19 metric.

---

## 7. ⚠️ Controls are cross-app only; the strongest control we found was **within-app**

Hard Rule 9 requires control APKs (noice, Material Catalog). Cross-app controls hold the *stack*
constant but vary the app — so a negative result is ambiguous.

The decisive Toutiao measurement was **within a single process, in a single run**: its own
1200×**1790** surface carried a buffer usage byte-identical to noice's clean value, while only its
1200×**1920** surface was corrupt. That killed "Toutiao requests bad usage" instantly and proved
the defect was **per-surface**. Nothing cross-app could have shown that.

It also produced the ASLR observation — the garbage varied between runs (`0x7f0ea86ac0` →
`0x7eee8c6ac0`) — proving a **live pointer** rather than a bad constant.

**Fix.** Add to Hard Rule 9: *prefer within-process differentials (two surfaces, two windows, two
threads, two activities of the same app) before cross-app controls; they hold every variable
constant except the one under test.* Add "within-app differential" as an evidence kind.

---

## 8. ⚠️ The runtime lock assumes hash ⇒ behaviour. One of our components breaks that

§6 locks build IDs and hashes — necessary and good. But **libhwui is not reproducible from source
in this environment**: a rebuild changing only three `fprintf` argument lists produced a binary that
broke child init (`INITCHILD-FAIL=89`, `ViewRootImpl=0`) while showing **identical 3319 dynsyms,
zero symbols added or lost, and sane symbol sizes**. Every pre-deploy check passed; only a full
launch run caught it.

So "same source revision" ≠ "same behaviour," and a hash-based lock will faithfully record two
binaries that behave differently as two legitimate runtimes.

**Fix.** Mark components **non-reproducible** in the lock; forbid rebuilding them as part of a probe
run; preserve known-good binaries as first-class artifacts. Add a §19 metric: *findings invalidated
by a runtime rebuild.*

---

## 9. ⚠️ `P4` conflates "window exists" with "pixels reached the panel"

`P4 = first window and meaningful frame`. Toutiao showed these are separable **and that the pixel
oracle can be definitionally unavailable**: the app had a correct populated view tree, took input,
and loaded live content, while every capture was black **by RenderService design** because the layer
was flagged protected.

**Fix.** Split:
- **`P4a` structural** — ViewRoot present, view tree populated with real geometry/text.
- **`P4b` presented** — a frame demonstrably reached the panel.

A probe must be able to record `P4a=pass, P4b=oracle-unavailable` rather than failing the app. This
is the concrete form of the `O` layer doing its job.

---

## 10. ⛔ The roadmap is inverted — build the detectors before the portfolio

Milestone 0 finalises schema and taxonomy; Milestone 1 is a full static scanner with a platform
index and hash dedup; prioritisation and dashboards follow. Meanwhile the three detectors that would
have caught **every API-level Toutiao defect before the first launch** are each roughly a day's work
against tooling that already exists in `westlake-arm64/.../tools/` (dexlib2: `FindClassRefs`,
`FindCallers`, `FindCatch`, `DumpCls`, `HasCls`).

`FindClassRefs.java`'s own header records the precedent: §506 enumerated everything ExoPlayer could
call on `AudioTrack`, bound the lot in one pass, and collapsed a sequence of ~15-minute
device rounds into one. **It was applied to one class and never generalised.**

**Proposed re-ordering:**

| new milestone | content | why first |
|---|---|---|
| **M0 — three detectors, one corpus** | `C8` probe-scan · `C9` hollow/member-level diff · `C1/J` unbound-native diff (`nm -D` bridge ∩ dex `native`), run over **Toutiao + noice + Catalog only** | one week; must rediscover all three known API fixes or the extractor is wrong |
| **M1 — severity gate** | `<clinit>`-on-launch-path tier, wired to the existing `Tolerating clinit failure` log | turns a raw diff of hundreds into a ranked worklist |
| **M2 — re-entrant scan** | capture runtime-loaded dex, rescan | without it, plugin apps are silently under-scanned |
| **M3 — runtime lock + probe ladder** | as written, plus `P4a/P4b` and non-reproducible marking | now the infrastructure has something to schedule |
| **M4 — registry, dedup, portfolio scoring** | as written | only meaningful once N is large |

---

## 11. Scoring: don't publish a number before it means something

`impact = weighted_blocked_apks × reachability × severity × confidence`, and
`priority = impact / (effort × (1+risk))`, require a corpus to be meaningful. Below ~25 APKs,
`weighted_blocked_apks` is noise and the formula manufactures false precision over a sample too
small to support it.

**Fix.** Until the corpus is stratified and ≥25, rank by **(stage transition unblocked on the
calibration corpus) × (cheapness of the correct fix for its class)** — which correctly ranks a `C8`
presence stub (trivial fix, unblocked an entire network stack) above an expensive `C6`. Publish the
underlying counts before the score, and suppress the score entirely while N is small.

---

## 12. Regression fixture — make v1 prove itself against known answers

§22 says "known Toutiao gaps are classified without app-bytecode fixes." Make that executable:

| must produce | class | why it is a real test |
|---|---|---|
| `android.graphics.ColorMatrix.set([F)V` | `C9` hollow | class-level resolution marks this satisfied — catches over-coarse diffing |
| `com.android.org.conscrypt.SSLParametersImpl` | `C8` probe-only | catches the "strings are only hints" demotion |
| ByteDance optimizer/profiler natives | `J-C1` unbound native | catches a missing bridge-symbol join |
| ByteDance handler threads dying on those natives | `S`-layer, killed Looper | catches failure-chain reconstruction |
| iftable OOB read | **must NOT appear** | scope test — `R-C7`, not an APK gap |
| `Surface` vtable epoch mismatch | **must NOT appear** as an APK gap | scope test — `C10`, our side |

Miss any of the first four ⇒ the extractor is wrong. Report either of the last two as an APK
dependency ⇒ the scope is wrong.

---

## 13. Bottom line

The document is a good **program design** and a weak **detection design**. It specifies the registry,
scoring, schema and dashboards in detail, and does not yet specify the three cheap scans that would
have found every API-level defect in the hardest app we have attempted, before it was ever launched.

Add `C8` (probe-only), `C9` (hollow), and `C10` (our-side ABI skew); make `<clinit>` a first-class
severity; make resolution member-level; make the scan re-entrant over runtime-loaded dex; allow
within-process differentials as evidence; and ship the detectors before the portfolio.

Then it will be worth pointing at a thousand APKs.

---

# Second pass — internal consistency and implementability

Reviewed 2026-08-19 against the unchanged v0.1 (539 lines). These are defects *within* the document,
independent of the missing detectors in §1-§12 above.

## 14. ⛔ Hard Rule 3 contradicts the shipped state of a control APK

Hard Rule 3: *"Do not patch the APK. App bytecode changes can be used only as explicitly labelled
diagnostic experiments, never as the compatibility solution."*

Correct as policy — but **noice, one of the two named control APKs, currently depends on app-dex
surgery as a solution**:

- `recipes/patch-noice-apk.sh` — *"App-dex surgery: rewrite invoke-interface-on-Proxy call sites to
  invoke-static into a merged westlake/WlProxy helper. **This is what made the sound library load.**"*
- `recipes/patch-noice-room.sh` (§485) — flips the app's own Room DAO `inTransaction` flag to route
  a read off a wedged `TransactionExecutor`.

Neither is diagnostic. Both are compatibility fixes inside app bytecode.

**Why this is serious for the process, not just the rule:** if the control APK's working state
depends on app patches, then "noice passes" does **not** measure unchanged-stock-APK compatibility,
and every portfolio conclusion calibrated against it inherits that bias.

**Fix.**
1. Re-test whether each app patch is still required. `patch-noice-apk.sh` is a strong candidate for
   retirement: it worked around the Proxy-dispatch defect that was later **root-caused and fixed in
   the platform** (the §440/§551 validator defect — `GetNameView()` on cross-dex proxy ArtMethods).
   A platform fix that lands should invalidate the app patch that worked around it.
2. Add a standing rule: **every promoted platform fix must trigger a re-test of the app patches that
   worked around it**, and retired patches must be recorded.
3. Mark any control APK still carrying a patch as `control-impure` in the runtime lock, and exclude
   it from "unchanged APK" metrics until the patch is retired.

## 15. ⛔ The canonical gap key embeds `mismatch_class` — reclassification orphans history

§12 defines the key as including `mismatch_class`. But §11.6 permits `CU → C*` reclassification, and
§20.3 mandates re-running a versioned classifier over retained scan data.

Both operations therefore **mint a new gap identity**. Consequences, all silent:
- dedup counts reset — the same defect appears as two gaps;
- "first confirmed blocker" attribution breaks across the boundary;
- the §19 metric *"time from first observation to classification"* becomes uncomputable, because the
  observation lives under a key that no longer exists.

**Fix.** Identity must be stable under reclassification:

```text
key       = runtime_lock_family | contract_layer | contract_owner | normalized identity | signature
attribute = mismatch_class (versioned, with history)
```

Also: the §12 examples use **four** fields (`N|libc|__system_property_get|C1`) while the spec lists
**six** — `runtime_lock_family` and `signature` are absent from every example. Reconcile them, or the
first implementation will encode the examples.

## 16. ⚠️ `C1` and `C4` overlap, and the document already cannot choose between them

- `C1` — *missing name or entrypoint; an equivalent implementation exists* → thin forwarder
- `C4` — *Android implementation is missing, but an OH backend capability exists* → preserve the
  AOSP-facing implementation, replace only its backend

§4.3's own example concedes the ambiguity: *"Framework Java method exists but its native peer is
absent | **`J-C1` or `J-C4`**"*. An unresolvable class boundary produces inconsistent classification
between analysts and agents, and inconsistent classification breaks dedup — the same defect lands
under two keys.

**Fix — make it decidable by a single question: does an Android-side implementation already exist?**
- **`C1`** — it exists and is merely unwired (forwarding, symbol export, registration). *No new
  app-facing semantics are authored.*
- **`C4`** — no Android-side implementation exists; we must supply one, and the only question is
  which OH capability backs it.

Under that rule the §4.3 example resolves cleanly: a framework Java method whose native peer is
absent is `C1` **if** the peer exists elsewhere and needs exporting/registering, and `C4` **if** the
peer must be written against an OH backend.

## 17. ⚠️ `O-C0` is a category error

§4.3 classifies *"RenderService masks a protected surface in screenshots"* as **`O-C0`**, but `C0` is
defined as *"present and compatible in ABI and observed semantics."* An oracle that reports black for
a healthy window is not "compatible" — it is an **observation defect**, which is precisely why `O`
exists as a layer.

Classing it `C0` means it carries the same class as "no change required," so it will be filtered out
of every worklist that (reasonably) drops `C0`.

**Fix.** Give `O` its own small class set rather than reusing `C0-C7` — e.g. `O-DEFECT` (the oracle
reports a false state), `O-BLIND` (the oracle cannot observe this case at all — the protected-layer
capture is this), `O-OK`. The protected-surface example is `O-BLIND`, and the correct response is
"use an independent oracle," not "no change."
