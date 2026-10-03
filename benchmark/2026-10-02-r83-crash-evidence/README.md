# r83: the crashes the log never showed (2026-10-02)

r83 reran the whole corpus (329 apps) on build 79, the r82 state plus two changes:
- an app's EGL window waits for a free buffer instead of timing out after 3000 ms;
- app processes keep their logging socket after the switch to their SELinux domain.

Scored by the lifecycle classifier alone, r83 looked like a regression: four apps moved back. OH's
crash dumps and the reruns below show three of the four are crashes the child log never mentioned.
Two of them, and TikTok, are now fixed.

`r83-lifecycle.json` is r83 classified with the crash dumps beside the logs
(`python -m westlake_gap.lifecycle <logs> --json`).

## Regression check against r82

- **Coverage:** all 329 apps ran. Two needed a rerun:
  - libretorrent was lost to a board reboot;
  - insigno's process died before the launcher placed its touch helper.
- **Stages:** of the 328 classified in both rounds, 323 reached the same lifecycle stage. 272 drew
  in each round.
- **Up:** Telegram draws; it no longer crashes on its GL thread.
- **Down:** CapCut, WhatsApp, Files and fmessages.

## The crash dumps

faultloggerd writes each native crash to `/data/log/faultlog/temp/cppcrash-<pid>-<ms>`. hiview
normally moves it to `faultlogger/`.

For about a day hiview moved nothing. Every r83 app's fault-log listing therefore showed the same
three old files. Meanwhile 25 dumps sat in `temp/`, 12 of them from r83 apps.

| app | signal, thread | what the frames show |
|---|---|---|
| TikTok | SIGSEGV, acceleratePlayH | a null library constructor called by musl's `do_init_fini` |
| Threads | SIGSEGV, its startup thread | a constructor at its link-time address: a relocation not applied |
| CapCut | SIGSEGV, aInitSchedule | a fault inside musl's allocator: the heap was already corrupt |
| Files | SIGSEGV, a Poller thread | a fault inside musl's allocator |
| WhatsApp | SIGSEGV, worker | ART's RosAlloc on a pointer with bit 55 set |
| econverter | SIGSEGV | a null function pointer called from `libpython3.11.so` |
| ppsspp | SIGSEGV, androidInit | in the runtime's `libhwui.so`, called from `libppsspp_jni.so` |
| Element X | SIGSEGV | inside `libmatrix_sdk_ffi.so` |
| Messenger | SIGABRT, its network event thread | aborted from `libstartup.so` |
| Waze | SIGABRT | aborted from `libwaze.so` |
| usp | SIGABRT, RenderThread | hwui: "drawRenderNode called on a context with no surface" |
| insigno | SIGABRT, Mali backend thread | aborted inside the Mali driver |

Two caveats on these dumps:
- **libart.so frame names are wrong.** OH's dumper names the nearest exported symbol. These were
  resolved again with the unstripped library.
- **Instagram left no dump at all.** Its hilog shows a SIGILL on the thread that had just made a
  numeric-host `getaddrinfo` call, and that ART did not claim. The process logged nothing after
  it.

The harness now reads both kinds of evidence (`evidence.cppcrash`, `evidence.hilog_signal`). The run
script captures each app's dump, process map, hilog and an ART thread dump, plus the libraries the
app wrote at run time.

## Reruns with that evidence

| app | before | cause | after |
|---|---|---|---|
| TikTok | dies 25 s in, every launch | `libttffmpeg.so`'s only init array entry is 0. It loads as a dependency of `libttmverify.so`, so ART's own sanitizer, which covers only the library it loads, never sees it | the launcher drops null init/fini entries from every library it stages. TikTok shows its own window; at 90 s its main thread is still building the feed (interpreted code) |
| CapCut | heap fault ~10 s in, twice | the same libraries (CapCut ships seven of TikTok's) | no crash. Its activity resumes and draws a first frame 27 s in, but by the 90 s screenshot its window is gone |
| WhatsApp | stack overrun 4 s in | its superpack libraries run from copies under its data directory. The shim did not count them as Android callers, so Breakpad's `sigaction` reached musl with a 32-byte bionic struct. musl wrote 152 bytes and the setup freed a clobbered string | the shim counts them. WhatsApp draws, twice: its "needs to be installed again" screen, because `libwhatsappmerged.so` cannot find `libqpl.so` by name |
| Files | heap fault | not reproduced | draws |
| fmessages | | varies between rounds | view stage, idle main thread |

On the rest:

- **Facebook draws.**
- **Messenger** aborts again on its network event thread. In a later run it got further:
  - its superpack `libcore.so` failed to relocate `__system_property_read_callback`;
  - the shim defines it, yet the lookup failed in the Android namespace. Open.
- **Threads** crashes again. SoLoader loads `libc++_shared.so` straight out of the split APK, which
  OH's loader can map. That bypasses the staged copy, whose DT_ANDROID_RELR tags were renumbered.
  - The shim now loads the staged copy for such a path, through `dlopen` and through `dlopen_ns`.
    ART uses `dlopen_ns` for the libraries routed to the Android namespace, and a first try on
    `dlopen` alone never saw this load.
  - Threads then got past its library loading. It now dies like Instagram: a SIGILL right after a
    numeric-host `getaddrinfo`.
  - Element (nine Android-namespace libraries) and WhatsApp still drew.
- **Instagram:** translating `sigprocmask` too did not change its SIGILL.
- **Spotify** reaches an activity. Then the library it extracts at run time fails to load for want
  of `libmediandk.so`.

## Libraries written at run time, in the gap map

`scan --unpacked-libs` adds the harvested libraries to an app's scan. They are never launch targets.

| app | harvested | rows | what the harvest changed |
|---|---|---|---|
| WhatsApp (first harvest, 4 s in) | 17 | 136 → 146 | 2 false "needed but not shipped" rows gone; an unshipped library, a symlink policy denial and ART-internals users appear; JNI methods with an implementation 1 → 27 |
| Instagram | 61 | 150 → 197 | `load:android-relocations` supplied → missing is a false alarm (the shim does renumber written libraries; the model followed a renamed function and is fixed); NDK entry points looked up at run time in libaaudio, libandroid, libnativewindow; `abi:signal` open for `sigprocmask` (the shim translated only `pthread_sigmask`) and for lookups by name; JNI methods with an implementation 325 → 812 |
| Facebook | 111 | 72 → 117 | the same runtime-lookup rows, plus libmediandk; JNI upcalls of an unpacked library that do not resolve |

New rows, each from a crash above:
- **`load:null-constructors`:** null or -1 init array entries. Supplied by the launcher's fix for
  packaged libraries, not for written ones.
- **`abi:signal`:** signal calls with bionic's structures. Covered per caller class, plus lookups
  by name: ByteDance's bytesig takes `sigaction` with `dlsym`, past the shim.
- **`art:internals`:** libraries that patch ART through its C++ symbols, at offsets chosen by the
  reported SDK level. Westlake reports 34 and runs an AOSP 15 ART. CapCut has 15 such libraries,
  and Instagram, Facebook and WhatsApp have them too. Unverified.

## gl-contracts probe

The probe was run on build 79 and against the three regressions it is meant to catch:
- the deployed build passes;
- the shim that sent every EGL call to the board's libEGL dies in the TextureView path;
- the shim that took EGL by `RTLD_NEXT` fails `egl-init`.

The GL bindings without the blocking buffer wait passed every in-app check. OH's buffer queue
logged the failed request anyway; the driver survived it that time. The suite now also fails a
probe on hilog markers (`fail_hilog`), and with that the probe tells all four apart.

## Compiled code

Under SELinux enforcing the app domain may not map executable anonymous memory. So the board's ART
has no JIT, and an app's code runs in the interpreter.

Telegram's code was compiled on the host and staged beside its APK. ART loaded it, then aborted at
the first safepoint ("Invalid address for an implicit NullPointerException check: 0x0", two
threads at once).

The cause: dex2oat emits implicit suspend checks for arm64 unless `WESTLAKE_EXPLICIT_NULL_CHECKS=1`
is set, and Westlake's ART installs no handler for them.

Rebuilt with explicit checks, Telegram ran its compiled code (the odex is mapped executable and no
bytecode was verified at run time) and drew, twice. The times below are from start to its first
activity, read from the app's own hilog:

| Telegram, build 79 | activity resumed | first frame |
|---|---|---|
| interpreted | 3.49 s | 3.84 s |
| its code compiled, run 1 | 2.26 s | 2.79 s |
| its code compiled, run 2 | 2.19 s | 2.50 s |

The boot image was then compiled at "speed" with explicit checks and deployed as build 80. Its
contract checks passed, with no class initialization failures. Seven apps, first frame:

| app | build 79, interpreted | build 80, boot image compiled |
|---|---|---|
| X | 29.01 s | 4.72 s |
| NewPipe | 7.12 s | 4.07 s |
| Telegram | 3.84 s | 1.75 s (its own code compiled too) |
| AntennaPod | 3.33 s | 2.66 s |
| geotagvideocamer | 3.21 s | 2.07 s |
| Aegis | 2.07 s | 1.61 s |
| Burger Party | 1.28 s | 1.03 s |

All seven drew on both builds, with no fatal signal. Most of an app's start-up runs in the
framework, so the compiled boot image matters more than the app's own code: X, which spent 29 s
interpreting, starts six times sooner.

## Commits

All local; none pushed yet.

- Harness:
  - `089ade1` crash dumps and hilog-only signals;
  - `9e814cf` probe hilog markers;
  - `2e804ac` written libraries and the three rows;
  - `9df761a` startup times from the app's hilog;
  - `64d7d97` libraries SoLoader may load from inside a split APK.
- Launcher (manifest):
  - `ac38c4e` staging host-compiled code;
  - `58493c6` null init/fini entries.
- Westlake:
  - `35e9b00` written libraries count as Android callers;
  - `c76f8f8` `sigprocmask` translated;
  - `a900571` a library inside an APK loads from its staged copy.
