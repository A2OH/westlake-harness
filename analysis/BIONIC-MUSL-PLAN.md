# Bionic ↔ musl compatibility — the plan (arm64, 2026-08-15)

**Problem.** Prebuilt Android `.so` files are compiled against **bionic**. This board runs **musl**
(`/system/lib/ld-musl-aarch64.so.1`). Our own recompiled code is fine (we build against musl); the
hazard is **third-party prebuilt native libraries we cannot rebuild** — e.g. Toutiao ships **138**
arm64 `.so` (64 MB), Unity ships a 17 MB engine.

Grounding: [[bionic-musl-class2-abi-detection]] (taxonomy + arm32 measurements) and the §617-§624
Toutiao evidence in [[toutiao-bringup-attempt-2026-08-14]].

---

## 1. Taxonomy (unchanged — it holds up)

| Class | Definition | Fixable by a name shim? |
|---|---|---|
| **0** | Present in both, ABI-identical (`malloc`, `memcpy`, math) | n/a — safe |
| **1** | **bionic-only names** (`__system_property_get`, `__errno`, `pthread_cond_timedwait_relative_np`, `__android_log_print`, `ANativeWindow_*`) | ✅ YES — forward to musl/OHOS |
| **2** | **Same name in both, but the argument is an OPAQUE STRUCT whose size/layout/encoding differs** | ⛔ NO — the layout is frozen inside the prebuilt binary |

Class-2 has two flavours: **(2a) size mismatch** → the bionic binary reserved N bytes, musl writes M>N
→ adjacent fields smashed, futex word at the wrong offset → corruption/hang. **(2b) same size,
different encoding** (`pthread_once_t`) → no corruption, state misread → only runtime finds it.

## 2. ★What changed on arm64 — the arm32 size table does NOT transfer

The memory's size table was **measured on arm32 (lp32)**, where `pthread_mutex_t` is bionic **4 B** vs
musl **24 B** (6×) — catastrophic. **On aarch64 (lp64) the sizes appear to MATCH** (bionic
`int32_t __private[10]` = 40 B; musl 40 B; cond 48/48; rwlock 56/56).

⚠️**ACTION ZERO (do this before anything else): re-measure the LP64 table from the actual headers on
this box** — bionic from the NDK sysroot `bits/pthread_types.h`, musl from the OHOS aarch64 sysroot
`bits/alltypes.h`. Do not reuse the arm32 numbers.

**If the LP64 sizes really do match, the strategy changes fundamentally:** Class-2a (the "deadly"
one) largely evaporates on this board, residual risk collapses to Class-2b encoding differences, and
the expensive fix paths (§4B/§4C) become unnecessary. This is the single highest-value experiment in
this document and it costs one afternoon.

**Supporting evidence that 2a is NOT currently biting us:** Toutiao's libs call musl's pthread
surface heavily (`libnpth` imports mutex/cond/rwlock/attr/sigmask) and we see **no corruption
signature** — no SIGSEGV storm, no smashed adjacent data, faults bounded at 6. A 6× struct-size
mismatch would not be that quiet.

## 3. What is already solved (keep doing this)

- **Class-1 shimming works and is the project's bread and butter.** Every `JNIMISS`/`UnsatisfiedLinkError`
  we've cleared (`libcore.io.Linux.memfd_create` §611d, the `§424` socket/DNS family, `FlippedV2Impl`
  §618) is the same move: export the symbol from the bridge, let ART's `dlsym` resolution find it.
  ★ART resolves natives by **dlsym**, so a plain exported symbol wins — no `RegisterNatives` timing.
- **The ELF is the analysis surface**, not the DEX. `llvm-nm -D -u lib.so` is the authoritative
  undefined-symbol set; the DEX only shows the Java↔native boundary.

## 4. ★NEW hazard found this session: the **libc++ collision** (this one is real and bit us)

Not in the old taxonomy — call it **Class-3: two libc++ runtimes in one process.**

Toutiao ships its own bionic-built `libc++_shared.so`. When its library directory was placed **early**
on `LD_LIBRARY_PATH`, the linker resolved **appspawn-x's own** libc++ against **Toutiao's bionic copy**
→ `Error relocating appspawn-x: __thread_local_data / basic_string::append: symbol not found` →
**the zygote refused to start**.

**Rule (already applied, keep it):** app library directories go **LAST** on `LD_LIBRARY_PATH`, after
`/system/lib64` and the bridge dir, so system/bridge libraries win every soname conflict and only
app-unique libraries resolve from the app dir.

**Related, and why our bridge↔libart calls are safe:** libart and the bridge are built by the *same*
OHOS clang and share the `std::__h` libc++ inline namespace (verified with `nm`), which is what makes
passing a `std::ostringstream` into `Runtime::DumpForSigQuit` legitimate (§624). ⚠️Corollary: a late
`#include <sstream>` in a bridge TU **breaks the forced-include namespace setup** — put libc++
includes with the top-of-file block (cost us one build).

## 5. The three strategy options

**A. Targeted Class-1 shims + libs-last ordering — CURRENT, and recommended to continue.**
Cheap, incremental, evidence-driven (each `JNIMISS` names the next shim), zero ART changes, and it is
how noice + the Material Catalog reached "runs". Limitation: does nothing for a genuine Class-2a hit.

**B. Bionic-layout sync interposer** (only if §2 re-measurement proves a real LP64 mismatch).
Interpose the Class-2 pthread surface for app libraries and implement it on **raw futex syscalls**
using **bionic's** struct layout — the kernel futex ABI is stable across both libcs, so we can honour
the bionic layout the prebuilt binary froze in. Cost: moderate; risk: must cover the whole sync family
consistently (mutex/cond/rwlock/once/sem/barrier) or we corrupt what we meant to fix.

**C. Linker namespace + real bionic for app libraries** (the ARC++/Houdini/Waydroid model).
Give app libraries a namespace backed by an actual bionic libc, so their structs are bionic again and
Class-2 vanishes *by construction*. Highest fidelity, highest cost; requires that the JNI/EGL/
ANativeWindow boundary pass **only C-ABI handles, never a libc struct**. This is the endgame if we
ever need to run a large prebuilt engine (Unity) rather than an app.

## 6. Recommended sequence

1. **Re-measure the LP64 opaque-type table** (§2 ACTION ZERO). Decides whether B/C are needed at all.
2. **Build the static portability gate** (no board required), per the memory's depth ladder:
   `T0` imports × size table → suspect list; `T1` `readelf -r` relocation anchors (a global
   `PTHREAD_MUTEX_INITIALIZER` is 40 zero bytes with **no init call** — invisible at runtime, visible
   statically); `T2` **`abidiff`** when DWARF survives (fully automated, exact offset deltas).
   Output: per-APK Class-1 list (definitive) + Class-2 candidates (necessary, not sufficient).
3. **Keep clearing Class-1 by evidence** — the `JNIMISS` → export → relaunch loop.
4. **Only if 1 says so:** implement B for the sync family; treat C as the Unity-scale endgame.

## 7. Honest status of the Toutiao livelock (do not over-attribute)

musl is a **confirmed** root cause for exactly one thing: the §4 libc++ collision that killed the
zygote. For the current Application-init **livelock**, three musl-flavoured hypotheses were tested and
**none survived**: (i) "the lock protocol isn't musl's" — retracted, healthy ART daemons wait
identically; (ii) NPTH's RT signal handlers vs our sigchain — **exonerated by bisect**; (iii) the
15-process manifest — unsupported, zero actual `bindService`/`startService` calls. Four subsystems are
eliminated (NPTH, ByteHook, Godzilla, MetaSec). The wait is **in-process**, Tinker-adjacent, and still
unnamed — pending the §624 thread dump.

★Discipline that produced the eliminations: change ONE variable, keep the control, and verify the
change actually took effect (bisect #2 lost exactly the `godzilla_async_` thread — that is what makes
"unchanged" mean something).
