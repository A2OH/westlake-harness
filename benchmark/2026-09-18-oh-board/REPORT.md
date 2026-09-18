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

---

# In-APK library loading on OpenHarmony — tested, and it fails

**Date.** 2026-09-19, same board.

McDonald's sets `extractNativeLibs="false"` and stores its `.so` entries uncompressed, so Android's
linker maps them straight out of the APK via `…/base.apk!/lib/arm64-v8a/libfoo.so`. WebView loads the
same way, in **both** apps. This is the gate flagged in `benchmark/2026-09-18-mcdonalds/REPORT.md`.

## The test

A payload library exporting `westlake_inapk_probe()`, a stored (uncompressed) zip containing it at
`lib/arm64-v8a/`, and a probe binary calling `dlopen` — all built with the OH SDK's clang for
`aarch64-linux-ohos` and run on the board.

```
control, extracted .so:
  OK    ./libinapk_extracted.so  handle=0x6565…  symbol=found  value=4242

in-APK form:
  FAIL  ./fake.apk!/lib/arm64-v8a/libinapk.so
        dlerror: Error loading shared library …: No error information
  FAIL  /data/local/tmp/wltest/fake.apk!/lib/arm64-v8a/libinapk.so
        dlerror: Error loading shared library …: No error information
```

The control proves the harness and the payload are sound. **OH's dynamic loader does not understand
the `zip!/member` form** — musl treats the whole string as a filesystem path, which does not exist.
Nothing in the deployed Westlake stack advertises handling it either.

## Consequence

On Android the chain is `System.loadLibrary` → `DexPathList.findLibrary` → a `…apk!/lib/<abi>/…`
path → bionic's linker maps the member out of the zip. `libart.so` on the board still carries
`nativeLibraryDirectories`, so the Java half of that chain is present; the linker half is not.

- **McDonald's ten native libraries cannot load at all.** No lifecycle theory is needed to explain a
  missing UI.
- **WebView cannot load** in either app, since the provider APK is loaded the same way.
- Toutiao is unaffected in its own libraries only because it ships them compressed and the installer
  extracts them.

## The cheap fix, consistent with "make it work first"

Extract at deploy time rather than teaching a linker to map zip members: when installing an APK
whose libraries are stored uncompressed, unpack them into the app's private lib directory and point
`nativeLibraryDirectories` there. It costs page sharing and some disk, and it is a deploy-step
change rather than a loader change.

Mapping zip members properly in the loader is the correct long-term answer and is not needed to get
either app running.

---

# McDonald's native libraries on the board: from zero to eight of ten

**Date.** 2026-09-19. Two changes, each proven with the same `dlopen` probe against the real
launch-time preload set (`libwebview_bionic_shim.so`, `libbionic_abi_shim.so`, `libandroid.so`)
and library path.

| Step | Libraries loading | What blocked the rest |
|---|---|---|
| before | **0 of 10** | not on disk — OH cannot map `apk!/lib/…` |
| `prepare_app` stages splits and extracts stored libraries | 0 of 10 | 13 bionic-private symbols |
| shim covers the 13 | **8 of 10** | one missing soname, one packer trap |

**The thirteen** — none are Android APIs the app called; they are what bionic's headers compile
ordinary C into, which musl names differently or provides only as macros:

```
__sF (6 libs)          __pthread_cleanup_push/_pop (2/1)   __system_property_foreach/_find_nth (2/2)
isnan / isinf (1)      __get_h_errno (1)                   ASensor* ×4, ALooper_pollAll (libandroid)
```

Measuring them needed the *complete* preload set: musl's lazy resolution reports one missing
symbol per library, so each fix reveals the next, and a bare `dlopen` without `libandroid.so` and
`libbionic_abi_shim.so` in the process over-reports by the symbols those two already provide.

**The two that remain are not symbol problems.**

- `libpanorenderer.so` — needs the soname `libGLESv1_CM.so`. OH ships it as
  `/vendor/lib64/chipsetsdk/libGLESv1_impl.so`; an alias closes it. VR pano viewer, not on the
  login path.
- `libakamaibmp.so` — relocates fully with the new shim, then **SIGILL inside its own `DT_INIT`**.
  That entry saves all thirty registers and branches into a 0x79a88-byte section named `.pb`: a
  packer stub that unpacks the real library before any app code runs, importing `mprotect`, `mmap`,
  `getauxval`, `dl_iterate_phdr`, `sigaction`. It is detecting the host and refusing. Same class as
  Toutiao's `libmetasec_ml.so`, and it will not be fixed with a symbol. Akamai Bot Manager **loads
  at startup** on Android, so this decides whether McDonald's reaches its login screen regardless
  of everything else.

**Where the changes live.** Loader side: `manifest` PR #10 (`split-apk-native-staging`). Symbol
side: `westlake` PR #8 (`bionic-shim-mcdonalds-residue`). Neither merged — they change what every
launch stages and preloads, and that call belongs to the runtime owners.

**Correction to the strategy document.** The welding list had four items; it needed five. The
app's own prebuilt `.so` files are bionic-linked binaries that cannot be rebuilt, so their libc
imports must be *translated* at a boundary no other cut removes. Shipping bionic instead would
mean two libcs in one process — the `N-C3` case — because everything above the app is already
musl-built and working. The shim is the right branch and the surface is small.
