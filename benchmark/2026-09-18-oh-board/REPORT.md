# First resolution against the deployed OpenHarmony runtime

**Board.** OpenHarmony 6.1.0.31, API 23, aarch64 (`hdc` target `5cdbf6af…`).
**Index.** 76 libraries — OH's `/system/lib64` core, `platformsdk` and `ndk` graphics, plus the whole
deployed Westlake runtime at `/data/local/tmp/asx` — 896,414 exported symbols.
**Date.** 2026-09-18.

This is the gate `analysis/NATIVE-GAP-PROCESS-AMENDMENT.md` item 1 was written for: until now the
resolver had never been pointed at a real OH runtime, and every native import was `CU`.

## Result

| App | Undefined symbols | Resolved | Missing | of which platform |
|---|---|---|---|---|
| Toutiao 13.9.0 | 3415 | **3077 (90.1%)** | 278 | **46** |
| McDonald's 26.31.1 | 592 | **532 (89.9%)** | 31 | **31** |

232 of Toutiao's 278 are C++ mangled names from plugin-delivered libraries — v8, `napi_v8`,
`F0Detection`, `VolumeDetection` — which **stock Android 11 also lacks**. They arrive after install
and are not a platform gap. The like-for-like Android 11 figure was 99.7% resolved; the gap between
that and 90% here is the subject of the rest of this report.

Indexing only canonical libraries (excluding the 34 dated variants such as `*.pre-*`,
`libart-jit79*`, `bridge_604`) gives **identical** numbers, so no result here depends on a stale
build artefact being present on the board.

## The real platform gap: 58 distinct symbols, five clusters

### 1. bionic-only libc ABI — 14 symbols, and the largest single item

| Symbol | Importing libraries |
|---|---|
| `__sF` | **40** |
| `_ctype_`, `__cmsg_nxthdr`, `__FD_SET_chk` | 2 each |
| `__libc_init` | 3 |
| `__pthread_cleanup_push` / `_pop`, `__FD_CLR_chk`, `__FD_ISSET_chk`, `__aeabi_mem{cpy,set,move,clr,clr4}` | 1 each |

`__sF` is bionic's stdio `FILE` array — `stdin`/`stdout`/`stderr` resolve through it. musl has no such
symbol. Forty libraries import it, far more than anything else in this report.
`libbionic_abi_shim.so` is deployed but does not export it. This is `BIONIC-MUSL-PLAN.md` territory
and it is the highest-leverage fix on the board.

### 2. `AAsset` NDK — 6 symbols, both apps

`AAssetManager_fromJava`, `AAssetManager_open`, `AAsset_close`, `AAsset_getLength`, `AAsset_read`,
`AAsset_getBuffer`. Three importing libraries in Toutiao, two in McDonald's.

Predicted independently from the bridge's export table before the board was available, and confirmed
here. Per `analysis/AOSP-PACKAGING-STRATEGY.md` this needs **no welding**: `asset_manager.cpp` plus
`libandroidfw` depend only on file I/O and zip, and `libandroidfw.so` is *already deployed* — only
the NDK entry points on top of it are absent.

### 3. `ASensor` NDK — 11 symbols, both apps

The whole sensor event-queue API. McDonald's needs the full set; Toutiao a subset.

### 4. bionic property API — 4 symbols, both apps

`__system_property_read`, `_find`, `_find_nth`, `_foreach`. **This is the device-fingerprinting
input path**, and therefore the most likely contributor to Toutiao's `device_register` blocker —
the fingerprinting stack cannot read a single system property today.

### 5. OpenSL ES interface IDs — 2 symbols

`SL_IID_ANDROIDCONFIGURATION`, `SL_IID_ANDROIDSIMPLEBUFFERQUEUE`. OH's `libOpenSLES.so` provides
`slCreateEngine` but not the Android-specific interface IDs, which are data objects.

### Remainder

`isinf` / `isnan` (musl defines these as macros, not symbols), `__register_atfork`, `__openat_2`,
`__get_h_errno`; plus `audio_fading_*` and `xp_*`, which are ByteDance's own and come from libraries
delivered outside the APK.

## What is already working

Confirmed provided by the deployed runtime, and worth recording so nobody re-implements them:

| Symbol | Provider |
|---|---|
| `ALooper_prepare` | `libandctrl.so` |
| `AndroidBitmap_lockPixels` | `liboh_adapter_bridge.so` |
| `ANativeWindow_fromSurface`, `eglSwapBuffers` | `bridge_current.so` |
| `inflate` / zlib family | `/system/lib64/platformsdk/libz.so` |

The deployment also already carries `libhwui`, `libminikin`, `libandroidfw`, `libutils`, `libcutils`,
`libbase`, `libicuuc`, `libharfbuzz_ng`, `libft2` and `libziparchive` — substantially more AOSP than
the strategy document assumed when it proposed "package AOSP, weld the bottom". That strategy is
further along on this board than it was written to describe.

## Order of work implied

1. **`__sF` and the bionic libc ABI shim** — 40 libraries, one shim, no new semantics.
2. **`__system_property_*`** — 4 symbols, and the most plausible single cause of the empty feed.
3. **`AAsset*`** — 6 symbols over an already-deployed `libandroidfw`.
4. **`ASensor*`** — 11 symbols, needed before McDonald's exercises sensors.
5. **OpenSL ES IIDs** — 2 data symbols.

## Reproducing

```
hdc file recv /data/local/tmp/asx/<lib>.so <dir>          # deployed Westlake runtime
hdc file recv /system/lib64/{libc,libc++_shared,libOpenSLES}.so <dir>
hdc file recv /system/lib64/platformsdk/{libEGL,libGLESv3,libz}.so <dir>
hdc file recv /system/lib64/ndk/libGLESv2.so <dir>
```

then resolve each app's packaged ELFs against that index with `resolve_native_imports`. `hdc file
recv` reads stdin, so inside a `while read` loop redirect it from `/dev/null`.

**Caveat.** This is static resolution of the import table. It says nothing about symbols resolved at
runtime through `dlsym` or `eglGetProcAddress`, and nothing about whether a provided symbol
*behaves* correctly — `AndroidBitmap_lockPixels` being present is not evidence that its stride and
format handling match Android's.
