# Strategy: package AOSP, weld the bottom — and the MVP that tests it

**Principle: make it work first, then make it fast.** Every choice below trades performance for
behavioural fidelity, deliberately. Nested composition costs a GPU pass; GPU-only composition gives
up hardware overlays; reusing AOSP drags in more code than a hand-written shim. All accepted, because
the expensive failures so far have been behavioural, not slow.

---

## 1. Why hand-written shims keep losing

An app reaches the platform by three paths, and only the first is the one people picture.

| Path | How it reaches OH | Measured on Toutiao |
|---|---|---|
| App → Android framework → OH | framework is ours; only its bottom edge touches OH | the bulk of UI |
| App → NDK API → OH, no framework in between | direct; we must implement the API | **23 libraries, 273 symbols** |
| App → `dlopen`/`dlsym`/`eglGetProcAddress` → OH | invisible to the import table | **~840 GLES names, 110 OpenCL** |

A shim written per symbol answers path 2 and misses the emergent behaviour that paths 1 and 3
depend on. `MaxTextureSize` and the `AdapterAnw` double-wrap were both translation defects at a
boundary we had authored ourselves — invisible in a symbol list, invisible in AOSP source, and
visible immediately in a side-by-side trace.

## 2. The real question is where to cut, and it is partly forced

`ANativeWindow.cpp` is 337 lines because it forwards to `Surface` → `BufferQueue` →
SurfaceFlinger → HAL. The depth is below the NDK entry point, so "implement the NDK" is a choice
about **how much AOSP to keep**, not a fixed amount of work.

Three constraints push the cut upward whether we like it or not:

- **The GPU driver ABI.** We cannot ship AOSP's `libEGL`; it is a loader for a vendor driver, and
  the driver on the board is built against OH's window and buffer types. AOSP must stop just above
  it. This is also the seam where symbol scope decides who answers — the Mali zlib leak was this.
- **The compositor.** Shipping `libgui` whole means a second compositor contending with OH's.
- **The binder context.** Only one process is context manager per binder node, and samgr holds
  handle 0.

## 3. Tiering: what needs welding and what does not

Read the includes, not the symbol names.

| Component | AOSP source | Bottom dependency | Weld |
|---|---|---|---|
| `ALooper_*` | `system/core/libutils/Looper.cpp` | `<sys/eventfd.h>` and nothing else | **none** |
| `AAsset*` | `asset_manager.cpp` + `libandroidfw` (59 files) | file I/O and zip | **paths only** |
| `AndroidBitmap_*` | `graphics/jni/bitmap.cpp` (113 lines) | Bitmap pixel storage | thin |
| `ANativeWindow_*` | `nativewindow/ANativeWindow.cpp` | `GraphicBuffer`, gralloc usage | **buffers** |
| OpenSL ES | `frameworks/wilhelm` (160 files) | audio HAL | **audio** |
| EGL / GLES | — | vendor driver | **never ship; use OH's** |

So the welding surface is five things: **buffer allocation, window/present, sync fences, audio —
and libc ABI.** The fifth is easy to miss. The NDK platform libraries are AOSP *source* and come out
of the OH toolchain speaking musl. The app's own prebuilt `.so` files do not: they were compiled
against bionic's headers and import bionic-private names (`__sF`, `__errno`, `__pthread_cleanup_push`,
`__FD_SET_chk`) that no cut below them can rebuild away. Those must be translated. Measured on the
board, the whole residue for McDonald's ten libraries was thirteen symbols — see
`benchmark/2026-09-18-oh-board/REPORT.md`. Shipping bionic instead would put two libcs in one
process, since everything above the app is already musl-built; the shim is the right branch.

Everything above the welds is AOSP source we already hold and currently hand-shim.

## 4. Nested SurfaceFlinger

Implement the composer HAL as a shim whose single display's output buffer is an OH native window
buffer. SurfaceFlinger believes it drives a display; it actually drives one OH app window, and OH
composites that window like any other.

This buys every Android composition behaviour — z-order, transforms, blending, BufferQueue latching
— because it is the same code that runs on a real phone. It costs one extra GPU pass, roughly one
frame of latency, and hardware overlays (so video loses direct scanout). Under "work first", accept
all three. It removes the window and composition weld, which is the behaviour-sensitive one; it does
**not** remove the buffer weld, since SF's buffers must be OH-allocated to be presentable.

## 5. Binder: transport compatible, semantics not

Already established in `docs/engine/V3-DIAG-B-SAMGR-BINDER-COMPAT-2026-05-23.md` (OH tree): same
`/dev/binder`, same protocol version, identical `binder_write_read`, `binder_transaction_data` and
`flat_binder_object`, same commands, samgr at handle 0. Two divergences, both above transport:

- `writeInterfaceToken` — AOSP writes three int32 headers including `kHeader='SYST'`, OHOS writes
  two. The four-byte offset fails every OHOS token check.
- Descriptors and transaction codes are different namespaces entirely.

**The consequence for this strategy is favourable.** AOSP `libgui` talking to AOSP SurfaceFlinger is
AOSP on both ends, so Android-internal binder IPC needs no translation at all. Parcel-rewrite
wrappers are needed only where Android code calls an OH system ability. Android's `servicemanager`
needs its own binder context — a second node via binderfs; the `binder`/`vndbinder`/`hwbinder` split
shows the driver supports it. **Open: confirm the board's kernel exposes binderfs or a spare node.**

## 6. The target surface, measured

Resolved against a stock Android 11 arm64 device (17 system libraries, 12,152 exports):

| | Toutiao | McDonald's | Union |
|---|---|---|---|
| packaged native libraries | 138 | 10 | — |
| platform symbols required | 756 | 550 | **855** |
| Android-specific | 199 | 73 | **206** |
| shared by both apps | — | — | 66 |

Of the 206: **133 are plain GLES and 25 are EGL — the driver provides those.** What we implement is
**48 non-GL entry points**, and they cover both apps completely:

```
AAsset* (6)   ALooper_* (9)   ANativeWindow_* (9)   ASensor* (11)
AndroidBitmap_* (3)           OpenSL ES (10)
```

That is the whole native platform contract for two very different apps. It fits on one page, which
is the strongest argument for packaging AOSP rather than authoring it.

**Measured for the entire NDK (2026-09-21).** Beyond what two apps import: of the 4,449 public NDK
symbols at API 33, OpenHarmony already provides 59% and Westlake's live libraries 3%. The missing
1,719 are 462 to compile from AOSP source, 226 of libc ABI, 309 of truthful absence, and 710 behind
ten welds (media, services, audio, camera, input, buffers, window, sensors, power, sync); 165 are
already built by Westlake and not deployed. See `benchmark/2026-09-21-ndk-coverage/`; the gap map
now classifies every native gap this way (`gap-map --ndk-coverage`).

---

# MVP test plan

Two apps chosen because **they fail in different halves of the system**.

| | Toutiao 13.9.0 | McDonald's 26.31.1 |
|---|---|---|
| targetSdk | 30 | **35** |
| packaging | single APK | **split APK** (base has 0 native libs) |
| native libraries | 138 | 10 |
| Android-specific symbols | 199 | 73 |
| extras needed | OpenSL ES audio, OpenCL | **sensors**, `ANativeWindow_lock` (CPU draw) |
| runtime delivery | 11 plugins, 23 libs, 5 hotfix odex | none observed yet |
| where it fails today | renders; feed empty — `device_register` returns no `device_id` | no real UI — `Activity.attach` / `AppComponentFactory` lifecycle gaps |

Toutiao stresses the native and graphics path. McDonald's stresses Java framework completeness at a
newer SDK level, plus split-APK loading and sensors. Passing both means the strategy holds at both
ends.

## P0 — Baselines on real Android (prerequisite, ~1 day)

Capture on the OnePlus 6T what a working run looks like, with `harness/jniprobe`.

- Toutiao baseline exists: 1157 methods, 135 tables, 43 failed `dlsym`, 11 plugins.
- **Do the same for McDonald's**, installing all splits.
- Extend the probe to hook `eglGetProcAddress`, closing the path-3 blind spot.
- Add a `__system_property_get`/`_read` hook and record every property read plus its value.

**Exit:** both apps have a committed baseline capture and a static-vs-runtime diff.

## P1 — Weld-free AOSP (proves the model cheaply, ~1 week)

Compile `system/core/libutils` (Looper) and `frameworks/base/libs/androidfw` (AAsset) for OH and
drop them in. **No welding required** — Looper needs only `eventfd`, AAsset needs only file and zip.

**Exit:** 11 of the 12 `libandroid` symbols currently missing from the bridge are served by AOSP
code; the hand-written shims for them are deleted; both apps still reach their current furthest
point. If this does not go smoothly, the whole strategy is in doubt and we learn it for one week's
cost instead of three months'.

## P2 — Buffer and window weld, then nested SurfaceFlinger (~3-4 weeks)

1. gralloc-equivalent over OH's allocator; `GraphicBuffer` backed by OH buffers.
2. Composer HAL shim: one display, output buffer is an OH native window.
3. Drive SF's vsync from OH's vsync.

**Exit:** Toutiao renders its feed through nested SF with no `AdapterAnw`-style translation layer,
and a differential trace of the 48 entry points against the 6T shows no divergence in call
sequence, arguments, return codes, or granted stride and format.

## P3 — Sensors and audio (~1 week)

`ASensor*` over OH sensors, OpenSL ES (`frameworks/wilhelm`) over OH audio. McDonald's needs
sensors; Toutiao needs audio. Neither is on the critical path for first frame, so do them after P2.

## P4 — Binder edge (~2 weeks)

Android `servicemanager` on its own binder context. Parcel-rewrite wrappers only for the OH system
abilities actually called — enumerate them from a binder trace of each app rather than guessing.

**Exit:** no Android-internal IPC translation anywhere; a named, closed list of OH SAs wrapped.

## P5 — App gates

| App | Gate | Currently |
|---|---|---|
| Toutiao | cold start → feed with real article content | blocked: no `device_id` |
| McDonald's | `SplashActivity` → first real frame → one interaction | blocked: lifecycle gaps |

**Toutiao's specific lead:** the `com.bytedance.deviceinfo` plugin carries 13 native libraries
including the Pitaya engine. Check whether it installs and loads on the board at all. If plugin
loading fails, fingerprinting never runs, `device_register` has nothing to send, and the feed is
empty exactly as observed — one root cause for the headline blocker, testable in minutes.

## Measurement gates (use the harness, not opinion)

1. `snapshot-runtime --system-lib <deployed OH libs>` then `scan --native-reach` → **zero
   `N-C1-candidate` for libraries that actually load.**
2. JNI capture on the board versus the 6T → **runtime-only method sets match.**
3. Differential trace of the 48 entry points → **no divergence in sequence, arguments, returns.**
4. Every failure that reaches a user without a prior static finding becomes a fixture.

## Explicitly deferred (the "then speed" half)

Hardware overlays and direct scanout; eliminating the second composition pass; zero-copy buffer
paths; frame-latency tuning; startup time. None of these are allowed to influence P1–P5 design.

## Known risks

- **The OH index has never been scanned.** The first run will likely surface a tooling defect before
  a real gap — the IFUNC bug proved that a detector never pointed at a real platform can be
  confidently wrong. Treat an implausible first result as a parser problem.
- **binderfs availability** on the board is unconfirmed.
- **Runtime-delivered code** is 15% of Toutiao's observed native surface. A shim validated against
  the APK alone will pass and then fail in production.
- **targetSdk 35** exercises framework paths Toutiao never touches; McDonald's may need framework
  work that has nothing to do with this strategy.
