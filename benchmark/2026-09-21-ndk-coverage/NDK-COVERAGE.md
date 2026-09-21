# The entire NDK (API 33) on the OpenHarmony board

The whole public NDK: **4449 symbols in 25 libraries**.

| Provided by | Symbols | Share |
|---|---|---|
| OpenHarmony | 2613 | 58.7% |
| Westlake (live libraries) | 117 | 2.6% |
| Missing | 1719 | 38.6% |

## How the missing symbols are supplied

| Strategy | Symbols | Meaning |
|---|---|---|
| weld | 710 | AOSP source above, an OpenHarmony subsystem below: the weld is the work |
| package | 462 | AOSP source compiled inside Westlake; no OpenHarmony subsystem underneath beyond what Westlake already provides |
| truthful-absence | 309 | legacy, deprecated or rare: report 'not available' the way a device without it does |
| libc-abi | 226 | bionic ABI translated onto musl in the bionic-ABI shim; Android's libc cannot share a process with OH's musl |
| cxx-runtime | 12 | C++ runtime entry points, provided by libc++ (OH's, or the app's libc++_shared) |

| Weld | Symbols | OpenHarmony subsystem | Effort |
|---|---|---|---|
| media | 274 | multimedia/av_codec + player_framework | L |
| services | 107 | samgr | M |
| audio | 78 | audio_framework (OHAudio) | M |
| camera | 69 | multimedia/camera_framework | L |
| input | 68 | multimodalinput | M |
| buffers | 35 | graphic_surface / native_buffer | M |
| window | 32 | window_manager + render_service | M |
| sensors | 32 | sensors | M |
| power | 12 | powermgr / thermal_manager | S |
| sync | 3 | Linux sync_file (same kernel) | XS |

165 missing symbols already have a Westlake build manifest for their AOSP source (built, not deployed on the measured board). 2 exist only in backup copies of a library, which are not counted.

## Per library

| Library | Symbols | OH | Westlake | Missing | Strategy |
|---|---|---|---|---|---|
| `libc.so` | 1393 | 1170 | 9 | 214 | libc-abi |
| `libGLESv3.so` | 418 | 418 | 0 | 0 | gpu-driver |
| `libandroid.so` | 323 | 0 | 46 | 277 | package |
| `libicu.so` | 306 | 0 | 0 | 306 | package |
| `libmediandk.so` | 300 | 0 | 13 | 287 | weld |
| `libm.so` | 286 | 277 | 0 | 9 | libc-abi |
| `libGLESv1_CM.so` | 278 | 98 | 0 | 180 | gpu-driver |
| `libvulkan.so` | 232 | 229 | 0 | 3 | gpu-driver |
| `libGLESv2.so` | 204 | 204 | 0 | 0 | gpu-driver |
| `libbinder_ndk.so` | 107 | 0 | 0 | 107 | weld |
| `libz.so` | 93 | 93 | 0 | 0 | use-oh |
| `libEGL.so` | 73 | 70 | 0 | 3 | gpu-driver |
| `libcamera2ndk.so` | 69 | 0 | 0 | 69 | weld |
| `libneuralnetworks.so` | 69 | 0 | 0 | 69 | truthful-absence |
| `libaaudio.so` | 67 | 0 | 0 | 67 | weld |
| `libOpenSLES.so` | 56 | 45 | 0 | 11 | use-oh |
| `libOpenMAXAL.so` | 44 | 0 | 0 | 44 | truthful-absence |
| `libjnigraphics.so` | 39 | 0 | 3 | 36 | package |
| `libnativewindow.so` | 26 | 0 | 21 | 5 | weld |
| `liblog.so` | 18 | 0 | 18 | 0 | weld |
| `libamidi.so` | 14 | 0 | 0 | 14 | truthful-absence |
| `libstdc++.so` | 13 | 0 | 1 | 12 | cxx-runtime |
| `libdl.so` | 12 | 9 | 0 | 3 | libc-abi |
| `libnativehelper.so` | 6 | 0 | 6 | 0 | package |
| `libsync.so` | 3 | 0 | 0 | 3 | weld |
