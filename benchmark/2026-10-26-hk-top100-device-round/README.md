# HK top-1000: device round on the top 100 (builds 120 and 122)

The device half of gate G1: the 100 most popular Hong Kong Play apps (ranks 1-100 of
`2026-10-25-hk-top1000-static-baseline/apps.csv`) launched one at a time on the board, in rank
order. It measures where they stop, and it checks the first-screen predictor against commercial
apps, where the static baseline suspected it fails.

**59 of 98 drew their first screen on build 120.** Build 122 fixes three more (two now draw).

## Setup

- Build 120, with r90's launch settings except host-compiled app code (no app AOT). Each app's
  launch arguments come from its build-120 gap map.
- One launch per app, scored on the rung ladder (`scripts/score_first_blockers.py`): 1
  runtime-init, 2 bound, 3 activity, 4 view, 5 drawing.
- 98 apps were launched. Chrome and the Google app were not: their scans list no launch
  activity. Chrome's launcher is declared in an isolated split's manifest, which the scanner does
  not read.
- `results.csv`: rank, package, title, source, prediction, rung, stage, cause and first blocker
  per app, plus the build-122 result for the six apps relaunched there.

Two harness bugs were fixed while the round ran. Both caused launch failures, not app stops:

- Network-ABI launch targets named a library's SONAME rather than its file. The launcher refused
  the whole launch, which hit Amap, Surfshark, AlipayHK and Kling. Fixed in #60. 29 of the 982
  maps carried it and were regenerated before those apps were relaunched.
- An app with no launch activity stopped the round's preparation step, so Omi was skipped. Omi
  was relaunched.

## Where they stop

| rung | apps |
|---|---|
| 5 drawing | 59 |
| 4 view | 13 |
| 3 activity | 3 |
| 2 bound | 7 |
| 1 runtime-init | 16 |

The 39 that stopped, by cause:

| cause | apps | which |
|---|---|---|
| no frame, no error | 9 | WeChat, Outlook, Grok, AlipayHK, DramaWave, Omi, All Browser, TransitNow, Crushie |
| PairIP (`libpairipcore.so`) | 7 | NetShort, DramaBox, Grok Bot, Surfshark, NordVPN, WePlay, Grindr |
| native crash | 7 | Douyin, Facebook, ReelShort, Bigo Live, KKBOX, BlinkDrama, Meitu |
| framework (Java) | 5 | JOOX, iQIYI, 红果短剧, myTV SUPER, CamScanner |
| missing native method or library | 5 | Apple Music, TataLand, Kling, QuickDoc, FlickReels (`librs_jni.so`) |
| process identity (fixed in build 122) | 3 | FuSu, Adobe Acrobat Reader, Microsoft Copilot |
| `libnativewindow.so` absent | 2 | Google Maps, YouTube |
| OpenHarmony platform library | 1 | Meta AI (`libimage_native` needs `libohosffmpeg.z.so`) |

**PairIP is the largest single native blocker.** Google Play's automatic integrity protection
packages `libpairipcore.so`, which crashes before the app's Application is created (SIGSEGV on its
`<pre-initialize>` thread), or stalls in `com.pairip.VMRunner.executeVM` (Surfshark). Every one
of the 7 top-100 apps that carry it stopped there. It ships in 78 of the 982 apps, whatever store
the copy came from.

**Process identity.** Three apps failed in `Application.onCreate` on how a process names itself:

- FuSu read its process name from `/proc/self/cmdline` and got the launcher's path, because
  `setArgV0` set only the thread name.
- Microsoft Copilot read `ApplicationInfo.processName` and got null; PackageManagerService
  names an application without `android:process` after its package.
- Adobe Reader got no `RestrictionsManager` from `getSystemService`.

Build 122 fixes all three. FuSu and Adobe Reader now draw their login screens. Copilot gets to the
view stage and stops on a native heap fault. Spotify, Bilibili and Amap, relaunched as controls,
still draw.

**`libnativewindow.so`.** Google Maps' and YouTube's main libraries link it for
`AHardwareBuffer_*`, `ASurfaceTexture_*` and two `ANativeWindow_*` dataspace calls. Westlake's
Android namespace provides `ANativeWindow_*` and `ASurfaceTransaction_*` in its `libandroid.so`,
but not this library. 12 of the 982 apps link it.

**Facebook** drew in r90 (version 580) and stops here (version 584) on a CheckJNI abort: native
`com.facebook.proxygen.EventBase.init()` calls a Java method whose lookup returned null.

## The first-screen predictor on commercial apps

Rule v3 against the build-120 outcomes:

| prediction | drew | stopped |
|---|---|---|
| draws | 41 | 29 |
| blocked | 18 | 10 |

51 of 98 are right (52%). Always predicting "draws" scores 59 (60%). The rule caught 10 of the
39 stops. Its blocked calls are mostly `ndk:weak-api`, and 18 of those apps drew, as the static
baseline expected. The causes above are mostly ones the rule has no signal for: PairIP, Java
framework gaps, silent stops. Packaged `libpairipcore.so` is a perfect signal here (7 of 7), and
the process-identity, restrictions and `libnativewindow` stops now have gap-map evidence to
become rows. A rule re-fitted on this round should be checked on the next 100 before it is used.

## Next

1. PairIP: what `libpairipcore.so` reads before it crashes (78 apps).
2. `libnativewindow.so` for the Android namespace: AHardwareBuffer over OpenHarmony native
   buffers (12 apps, including Maps and YouTube).
3. The 9 silent stops, which need a trace rather than a crash report.
4. Ranks 101-1000 at the same settings.

Provider: build 120 (westlake e8d4b20), as recovered from the board; build 122 (westlake 67f61ba)
was built from source, with its boot image compiled at speed. Build 120 rebuilt the same way
matches the board's copy in 26 of 27 boot-image files; `boot.art` differs in its checksum and 3
bytes of image data.
