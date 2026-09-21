# The entire NDK against the OpenHarmony board

The native strategy (`analysis/AOSP-PACKAGING-STRATEGY.md`) is to package AOSP's NDK libraries
inside Westlake, the way the framework jars are packaged, and weld only their bottoms to
OpenHarmony. This benchmark measures how far that is from done for the **whole public NDK**, not
just the symbols two apps happen to import.

Inputs: the NDK r25 API-33 stub libraries (4,449 public symbols in 25 libraries); 7 OpenHarmony
system libraries and the 68 Westlake runtime libraries pulled from the board on 2026-09-21
(`/data/local/tmp/asx`). 38 of those 68 are backup or experimental copies (`libart.pre-jit790.so`,
`bridge_604.so`); they are excluded, and only 2 symbols existed solely in them.

| Provided by | Symbols | Share |
|---|---|---|
| OpenHarmony (musl `libc`/`libm`, GLES 2/3, EGL, Vulkan, zlib, basic OpenSL ES) | 2,613 | 58.7% |
| Westlake live libraries (`liblog`, parts of `libandroid`, `libnativewindow`, `libjnigraphics`, `libnativehelper`) | 117 | 2.6% |
| Missing | 1,719 | 38.6% |

## What the missing 1,719 take

| Strategy | Symbols | What it is |
|---|---|---|
| **package** | 462 | AOSP source, no OH subsystem underneath: ICU C API (306), the pure parts of `libandroid` (120: configuration, assets, fonts, shared memory, trace, storage), image decoder (36) |
| **libc-abi** | 226 | bionic names translated onto musl: GNU extras, bionic-private names, resolver internals, fdsan, system properties, fortify wrappers |
| **weld** | 710 | AOSP source above a named OH subsystem, ten welds: media 274 (L), services/samgr 107 (M), audio 78 (M), camera 69 (L), input 68 (M), buffers 35 (M), window 32 (M), sensors 32 (M), power 12 (S), sync 3 (XS) |
| **truthful-absence** | 309 | GLES 1.x fixed-function (180), NNAPI (69, deprecated), OpenMAX AL (44), MIDI (14), two NV EGL extensions |
| **cxx-runtime** | 12 | `libstdc++` entry points, provided by `libc++` |

**165 of the missing symbols already have a Westlake build manifest** for their AOSP source: binder
NDK (107), image decoder (36), assets and looper (19), sync (3). They are built, not deployed on
this board. Two pieces are never packaged: `libc` (two C libraries cannot share a process) and the
GPU driver (EGL/GLES/Vulkan come from OH's driver; only Android's extensions are added).

So the entire NDK reduces to **ten welds plus the libc shim**, and window, buffers, audio and input
are welds the Java framework path needs anyway.

## Effect on the McDonald's gap map

Before, the map checked imports against the raw board and reported "`libandroid`: 17 symbols
missing, **L**". With the NDK as the provider model, the same 31 missing imports read:

| Row | Symbols | Effort |
|---|---|---|
| NDK weld · sensors → OH `sensors` | 11 | M |
| bionic libc ABI (13 covered by the Westlake shim; open: `__system_property_read`, provided nowhere) | 14 | S |
| NDK package (`asset_manager.cpp`, `looper.cpp`): built by Westlake, not deployed | 6 | XS |

## Caveats

- "Provided" means the name is exported. OH's OpenSL ES has the standard names and none of
  Android's extensions; behaviour still needs probes.
- The board payload predates the source build: it lacks the 13-symbol bionic shim and the AOSP
  `libandroid`/binder NDK outputs, so Westlake's share is understated.
- The weld model (`harness/westlake_gap/data/ndk-weld-model.json`) is curated per library and API
  family. Sources not yet imported: `frameworks/wilhelm` (OpenSL ES, OpenMAX AL) and NNAPI.
- The full NDK is a ceiling. The two MVP apps use 48 non-GL entry points; priority follows what
  apps call.

## Reproduce

```bash
# pull (hdc file recv needs a Windows path when run from WSL)
hdc file recv /data/local/tmp/asx/<lib>.so <westlake-libs>/        # each deployed Westlake library
hdc file recv /system/lib64/{libc,libOpenSLES}.so <oh-libs>/
hdc file recv /system/lib64/platformsdk/{libEGL,libGLESv3,libvulkan,libz}.so <oh-libs>/
hdc file recv /system/lib64/ndk/libGLESv2.so <oh-libs>/

westlake-apk-gap ndk-coverage \
  --ndk-api-dir $ANDROID_HOME/ndk/<ver>/toolchains/llvm/prebuilt/linux-x86_64/sysroot/usr/lib/aarch64-linux-android/33 \
  --oh-libs <oh-libs> --westlake-libs <westlake-libs> --westlake <westlake source> --out .
westlake-apk-gap gap-map ... --ndk-coverage ndk-coverage.json
```
