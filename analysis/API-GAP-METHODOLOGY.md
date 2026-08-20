# Static API-gap analysis for stock APKs — stop exploring in the dark

**2026-08-19.** Companion to `BIONIC-MUSL-PLAN.md` (which classifies the **native/libc** boundary).
This document does the same for the **Java/Android API** boundary.

---

## 1. The core claim

**A stock APK already contains the complete list of platform APIs it can ever touch.** Every class,
method and field a dex can reference is in its reference pool. The port's BCP jars contain the
complete list of what we actually provide. The gap is a **set subtraction we can compute before the
app is launched even once**.

We have done this before and it worked. §506 (`tools/FindClassRefs.java`) enumerated everything
ExoPlayer could call on `android.media.AudioTrack`, bound them in one pass, and collapsed a
sequence of ~15-minute device rounds — one per missing native — into a single round. The header of
that tool states the principle outright. **It was applied to one class and never generalised.**

Everything below is that idea, made whole-APK and given a repair strategy per gap type.

### Why crash-driven discovery is so expensive here

The failure modes actively hide from you:

- A missing native throws `UnsatisfiedLinkError` — an `Error` — which kills the calling
  HandlerThread with no report (`ThreadGroup.uncaughtException` is a no-op in this port). You learn
  about them strictly one at a time.
- A tolerated `<clinit>` failure leaves a class **half-initialised with null statics**. Nothing
  throws at the point of damage; you get a `NullPointerException` somewhere unrelated, later.
- A **presence probe** (§676) produces no error at all at the missing class. OkHttp's
  `Class.forName("com.android.org.conscrypt.SSLParametersImpl")` just returned null, and the failure
  surfaced as `NullPointerException: No platform found on Android` in a different package. Nothing
  in that message names the missing class.
- A **hollow stub** (§675 `ColorMatrix`) throws only when the app happens to call the one method
  that was omitted, which may be deep inside a `<clinit>`.

Each of those cost this project days. All four were statically visible.

---

## 2. The pipeline

```
  APK (all classes*.dex)                 BCP jars (10) + bridge .so
        │                                        │
        │ 1. extract REFERENCES                  │ 2. extract DEFINITIONS
        │    (classes/methods/fields)            │    (+ exported JNI symbols)
        ▼                                        ▼
   refs.txt  ────────────► 3. SUBTRACT ◄──────  defs.txt
                                │
                                ▼
                          candidate gaps
                                │
                     4. CLASSIFY (J0..J5, §3)
                                │
                     5. GATE BY SEVERITY (§4)
                                │
                                ▼
                   ranked worklist, per-class repair
```

**Step 1 — references.** Restrict to platform namespaces only:
`android/`, `java/`, `javax/`, `libcore/`, `dalvik/`, `com/android/`, `org/apache/harmony/`,
`org/json/`, `org/w3c/`, `org/xml/`. Everything else is the app's own code and irrelevant.
dexlib2 exposes the reference pool directly; `FindClassRefs.java` already walks it for one class —
generalise it to emit every platform reference with a call count.

**Step 2 — definitions.** Every `ClassDef` and its methods/fields across the ten BCP jars
(`framework.jar`, `core-oj`, `core-libart`, `core-icu4j`, `okhttp`, `bouncycastle`, `apache-xml`,
`oh-adapter-framework`, `adapter-runtime-bcp`, `adapter-mainline-stubs`). Plus
`nm -D --defined-only` on the bridge `.so` for the JNI side.

**Step 3 — subtract.** Three distinct outputs, not one:
- class referenced, **no ClassDef anywhere** → missing class
- class present, **method/field not in it** → missing member (this is the `ColorMatrix` case)
- method present and `native`, **no exported symbol in the bridge** → unbound native

**Step 4/5** are §3 and §4 below.

---

## 3. Taxonomy — and a different repair for each class

Deliberately parallel to `BIONIC-MUSL-PLAN.md`'s native Class 0/1/2a/2b/3.

| Class | Definition | How to detect statically | Repair strategy | Cost |
|---|---|---|---|---|
| **J0** | Present and real | defined, non-trivial body | none | — |
| **J1** | **Absent, genuinely invoked** | not in BCP; reference appears as a real `invoke-*` operand | implement it — port the AOSP source | high |
| **J2** | **Absent, only PROBED for existence** | referenced *only* as a `const-string` fed to `Class.forName`/`findClass`, usually inside try/catch | ✅ **presence-only stub** — an empty class with the right name | **trivial** |
| **J3** | **Present but HOLLOW** | defined, but body empty / `return null,0,false` only / member missing entirely | implement the specific member | low–medium |
| **J4** | **Unbound native** | declared `native` in a BCP class, no matching exported symbol in the bridge | export the symbol from the bridge (native Class-1 move; ART resolves by `dlsym`) | low |
| **J5** | **Present but semantically WRONG** | ⛔ not statically detectable | differential test vs real Android | high |
| **JX** | Not an API gap at all | — | our own boundary misuse or an ART invariant violation | varies |

### Why J2 deserves its own class

This is the discovery that unblocked Toutiao's entire network stack, and it is **invisible to
crash-driven debugging**. The app never calls a method on the class; it only asks whether the class
exists, to decide which code path to take. A missing class therefore produces *no* error at the
missing class — it silently selects the wrong path, and the failure appears far away.

`Class.forName` probes are cheap to satisfy (an empty class with the right FQN) and cheap to find
statically (string constants passed to `forName`/`findClass`). **Scan for these first — best
effort-to-value ratio in the whole method.**

### Why J3 is the silent killer

A stub that returns `null` doesn't fail where it's wrong; it fails wherever the null lands. This
port's `PFCUT` layer already generates these deliberately, so J3 gaps come from *both* directions:
BCP classes shipped hollow (`ColorMatrix` = a class with only `<init>()V`), and compat shims
returning null for "I don't know". Detection heuristic: `codeUnits <= 2` and the return is a
constant — flag for review, don't auto-classify.

### JX — keep it out of the API worklist

Two of this project's four hardest defects were **not** API gaps:
- the iftable out-of-bounds read (§673) — an ART invariant violation
- the `Surface` vtable epoch mismatch — **our own** code calling OH through typed C++ virtual calls
  compiled against a newer header than the deployed library

No amount of APK analysis surfaces those. They belong to the native/ABI method, not this one.
**Do not let them pollute the API worklist** — and note the corollary: if an app fails and the API
diff is clean, stop looking for missing APIs.

---

## 4. Severity gating — what makes the list actionable

A raw diff over a 21-dex APK yields hundreds of entries, most never executed. Rank by *where the
gap is reached*, not by what it is:

| Sev | Condition | Why it matters |
|---|---|---|
| **S0** | reached from a `<clinit>` of a class on the launch path | tolerated clinit failure ⇒ half-initialised class ⇒ null statics ⇒ damage appears far away, much later |
| **S1** | reached on the launch path, not caught | hard failure, but at least it is loud |
| **S2** | reached inside a `try/catch` | app silently degrades — the J2/J3 pattern |
| **S3** | not reachable from the launch path | ignore until a feature needs it |

Existing tooling covers this: `FindCallers.java` for reachability, `FindCatch.java` for catch
context, and the runtime's own `Tolerating clinit failure for L...;` log lines to confirm S0
empirically. On Toutiao that log went 12 → 9 across two fixes and is a direct S0 worklist.

---

## 5. Honest limits — where static analysis cannot reach

State these up front so the method isn't over-trusted:

1. **Reflection with computed strings.** `Class.forName(a + b)` is invisible. **Mitigation:** the
   runtime already logs every resolution (`[PFCUT] Class.classForName name=...`). Take the **union**
   of the static diff and a runtime reference log from one instrumented launch. Static gives
   coverage; runtime gives the reflective tail.
2. **Dynamically loaded code.** Toutiao ships Tinker + Mira plugin frameworks and 21 dex files;
   plugin dex loaded at runtime is not in the base APK. Re-run the extraction over any dex the app
   loads.
3. **J5 semantic wrongness** is fundamentally out of reach statically — it needs a differential
   against real Android (Tier 1 of `PORTING-PLAYBOOK.md`).
4. **Over-approximation.** The reference pool lists far more than any single run executes. This is
   why §4 gating is not optional — without it the output is noise.
5. **Native side is a different surface.** For prebuilt `.so`, the authoritative input is
   `llvm-nm -D -u lib.so`, not the dex. See `BIONIC-MUSL-PLAN.md`.

---

## 6. What to build (concrete, in priority order)

1. **`ApiRefs.java`** — generalise `FindClassRefs.java`: walk all dex, emit every platform-namespace
   class/method/field reference with a count. *(the whole method depends on this one tool)*
2. **`BcpDefs.java`** — emit every definition across the BCP jars, plus `nm -D` on the bridge.
3. **`ApiDiff`** — subtract, emit the three gap kinds separately (missing class / missing member /
   unbound native).
4. **`ProbeScan`** — find `const-string` → `Class.forName`/`findClass` pairs. **Highest value per
   line of code: this is the J2 detector.**
5. **`HollowScan`** — flag defined methods with `codeUnits <= 2` returning a constant (J3).
6. Wire `FindCallers`/`FindCatch` for the §4 severity gate.

Steps 1–4 are a day's work against tooling that already exists, and would have found `ColorMatrix`,
`SSLParametersImpl` and the unbound ByteDance natives **before the first launch**.

---

## 7. Validation — test the method against known answers first

Do not deploy this on a new app until it reproduces what we already know. Run it against the
**current Toutiao APK and pre-fix BCP jars** and require it to independently rediscover:

| must find | as class |
|---|---|
| `android.graphics.ColorMatrix.set([F)V` | J3 (class present, member absent) |
| `com.android.org.conscrypt.SSLParametersImpl` | J2 (probe-only, via okhttp `Platform`) |
| the ByteDance optimizer/profiler natives | J4 (unbound native) |
| the iftable OOB and the `Surface` ABI defect | **must NOT appear** — they are JX |

If it misses any of the first three, the extractor is wrong. If it reports the last two, the scope
is wrong. Only then point it at a new APK.

---

## 8. The one-line summary

The dex knows what the app needs; the jars know what we have; **subtract before you launch**, sort
by where the gap is reached, and apply the cheapest repair that class allows — a **presence stub**
for a probe, a **real method** for a hollow class, an **exported symbol** for a native. Reserve
runtime exploration for the two things static analysis genuinely cannot see: semantic wrongness,
and our own ABI boundaries.
