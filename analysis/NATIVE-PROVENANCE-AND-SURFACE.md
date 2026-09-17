# Native provenance and platform-surface reach

**What this adds to the method.** The DEX side of the gap analysis answers *which Java APIs an
APK touches*. This is the equivalent question one layer down: for each packaged `.so`, **whose
code is it**, and for each registered JNI method, **which Android platform surfaces does it
actually reach**. Both are answerable from a shipped APK alone, and both stay answerable when
the library carries no symbol table — which, in a commercial APK, is every library.

Implemented in `harness/westlake_gap/nativeprov.py`; run with
`westlake-apk-gap native-surface <lib.so|dir> --out <json>`.

---

## Why the stripped case still works

Stripping removes `.symtab`. It cannot remove what the loader and the Android runtime need at
run time, and that residue is enough.

| Artefact | Why it survives | What it yields |
|---|---|---|
| `DT_NEEDED` | the loader resolves it | the library's **surface ceiling** — what it *can* touch |
| Undefined dynamic symbols | the loader binds them by name | every external function called |
| Exported dynamic symbols | `dlsym` and other objects need them | entry points; C++ types after demangling |
| `RegisterNatives` tables | the runtime matches name + descriptor strings | the **complete Java-facing API with full types** |
| `R_*_JUMP_SLOT` relocations | the loader writes the GOT | PLT stub → imported symbol, i.e. call targets |
| `.rodata` strings | the code reads them | class names, versions, `dlsym` arguments |

`recover_jni_registration_entries` in `native.py` already recovers the tables. This module adds
provenance and reach on top; it does not re-implement ELF parsing.

---

## Provenance: contains vs links-against

A library that *contains* FFmpeg is replaced from upstream at that version. A library that merely
*links against* it is an ordinary consumer. Conflating the two is the most common misattribution,
and the distinction is mechanical:

- **contains** — a version banner appears in the file, **or** enough *defined* (exported) symbols
  match the component's family. A banner is physical evidence: those bytes are in this file.
- **links-against** — the component's symbols appear only as *undefined* imports.

Symbol-only matches require a minimum hit count, so a couple of coincidental names cannot name a
component. Format placeholders are rejected as versions (`x264 - core 0000` yields the component,
no version).

Measured on `benchmark/2026-08-23-toutiao` (138 arm64 libraries, all stripped):

| Library | Verdict | Basis |
|---|---|---|
| `libmffmpeg.so` | contains FFmpeg 3.3.2 and x264; links against OpenSSL | banner; 948 defined FFmpeg symbols; 36 imported OpenSSL symbols |
| `libisecgm.so` | contains mbedTLS 2.1.12 | banner; 459 of 627 exports |
| `libsscronet.so` | contains Cronet; links against OpenSSL and libc++ | 822 defined; 182 and 81 imported |
| `libimagepipeline.so` | contains libjpeg-turbo 1.5.3 | banner only — statically linked, symbols hidden |
| `libhdiffpatch.so` | contains HDiffPatch 3.0.6 | banner only |
| `libbdmpg123.so` | contains mpg123 | banner only |
| `liblens.so` | no known component | neither banner nor symbol family |

The three "banner only" rows are the point of the rule: those libraries export **zero** symbols of
the component they contain, so a symbol census alone would have missed them.

---

## Surface reach: three measurements, three failure modes

```
DT_NEEDED           -> ceiling: what any method in this library could possibly touch
JNI descriptor      -> boundary: what platform objects cross into native code
direct-call walk    -> floor:    what a method's body provably reaches
```

**Ceiling** is free and exact. `liblens.so` needs `libEGL`, `libGLESv2`, `libjnigraphics`,
`libandroid`, `liblog`, `libz` and the C++ runtime, which rules out camera, audio and binder for
all 26 of its methods at once.

**Boundary** is free and exact, and it is the one signal a call-graph walk cannot replace. A
descriptor carrying `Landroid/graphics/Bitmap;` or `Landroid/view/Surface;` means a platform
object is handed to native code; that is coupling regardless of what the body does with it.

**Floor** is the call-graph walk: disassemble (`llvm-objdump`, AArch64 only), map PLT stubs to
imported symbols through `R_AARCH64_JUMP_SLOT`, then walk `bl` edges outward from each method's
recovered entry address and collect the platform imports reached.

Every reach result is stamped `"basis": "direct-bl-lower-bound"` and
`"indirect_calls_followed": false`. **It is a lower bound and must never be read as proof of
absence.** Two blind spots, both observed in the corpus:

1. **Indirect dispatch.** In `libkrypton.so`, `nativeAddSurface` takes a
   `Landroid/view/Surface;` yet reaches no surface by direct calls — it stores the pointer and a
   render thread does the GL work. The boundary signal catches what the walk misses; this is why
   `platform_coupled` is true when *either* signal fires.
2. **Runtime resolution.** `liblens.so` uses OpenCL and imports **zero** `cl*` symbols: it
   resolves them through `dlopen`/`dlsym`. Any method reaching `dlopen` is flagged
   `dynamic_resolution`, and `dynamic_symbol_candidates()` recovers the names from the string
   table — 54 OpenCL entry points in that library's case.

---

## Worked example: `liblens.so`

2.1 MB, stripped, three meaningful exports (`Create`, `Destory`, `GetLensVersion`). Recovery gives
26 registered methods across five classes (`com/ss/lens/algorithm/DocAI{Crop,Delight,Deblur,Demoire,Dewarp}`),
and the reach splits them cleanly:

| Method group | Functions reached | Surfaces | Reading |
|---|---|---|---|
| `nativeDocAI*Release` | 3 | none | frees a handle; pure C |
| `nativeDocAIInit*` | 8 | `__android_log` | loads a model; logging is the only tie |
| `nativeDocAICrop/Deblur/Demoire/Dewarp/Delight/Definger` | 57–69 | `AndroidBitmap_*`, `pthread`, `dlopen`, log | the coupled set, and only through pixel access |
| `nativeVideoOclSr*` | 2–5 | none directly | work dispatched elsewhere; see blind spot 1 |

Every method follows `Init → process → Release`, `Init` returning a `long` handle and taking two
model-file paths, `process` taking that handle plus a `Bitmap`. That is a GPU document-scanner
pipeline (deskew, deblur, de-moiré, finger removal, relighting) plus video super-resolution — a
verdict reached without decompiling one function.

---

## What the numbers say about porting cost

Measured over all 138 arm64 libraries in `benchmark/2026-08-23-toutiao`
(`native-analysis/native-surface.json`). 60 libraries yielded registration tables totalling
**1417 methods**; the other 78 register nothing statically recoverable.

| Result | Methods | Share |
|---|---|---|
| reach no platform surface at all | 878 | 62% |
| reach `dlopen`/`dlsym` — verdict unproven | 227 | 16% |
| platform-coupled (surface reached **or** platform type at the boundary) | 68 | 5% |
| carry an `android/*` type across the boundary | 47 | 3% |

The coupling concentrates in a small, enumerable set:

| Surface | Methods | Share | Cost class | Porting implication |
|---|---|---|---|---|
| `pthread` | 414 | 29% | portable | POSIX, not Android |
| `__android_log` | 262 | 18% | shim | a few lines |
| `dlopen`/`dlsym` | 227 | 16% | **blind** | read the string table before believing any verdict |
| file I/O | 190 | 13% | portable | check path assumptions |
| `fork`/`prctl`/`ptrace` | 165 | 12% | integrity | anti-tamper; expect active resistance |
| `__system_property` | 69 | 5% | identity | device identity; needs a decided replacement |
| sockets | 52 | 4% | portable | |
| `AndroidBitmap_*` | 31 | 2% | **platform** | genuine graphics coupling |
| `libandroid` (`AAsset`, `ALooper`) | 16 | 1% | **platform** | asset and looper semantics |
| GLES/EGL | 15 | 1% | **platform** | genuine, and the expensive kind |

At the boundary the platform types are equally concentrated: `Bitmap` on 29 methods, `Surface` on
9, `Context` on 6, and a long tail of two or one.

This ranks native work the way the `C0`–`C10` classes rank Java work: most of it is not
Android-specific, the part that is, is small enough to enumerate — and the honest headline is that
**16% of methods cannot be ruled clean at all** until their `dlsym` strings are read.

Provenance over the same corpus: 33 of 138 libraries contain an identifiable upstream component,
most often the NDK C++ runtime (9), bytehook/xHook (4), then mpg123, zstd, libjpeg-turbo, QuickJS,
FFmpeg and OpenSSL at two each.

---

## Limits

- **AArch64 only.** The reach walk needs an aarch64-capable `llvm-objdump`; the NDK ships one,
  Ubuntu's binutils does not. Other machines return `supported: false` with a reason, never a
  silent empty result.
- **Direct `bl` edges only.** Function pointers, virtual dispatch, callbacks and task queues are
  not followed. Lower bound, always.
- **Obfuscation defeats table recovery.** `libEncryptor.so` and `libmetasec_ml.so` yield no
  registration entries; `libdexvmp.so` is a VM-based obfuscator. Libraries that decrypt their
  payload at load time need a running process, not static reading.
- **Structure, not source.** Knowing a function is a JPEG decoder does not produce compilable C.
- **Filenames lie.** `libmetasec_ml.so` imports `ptrace`, `fork`, `kill`, `prctl`, `waitpid` and
  `dl_iterate_phdr`, and no ML runtime of any kind. Trust the imports.
