# McDonald's 26.31.1: the gap map, and a backtest against the board

Method: `analysis/GAP-MAP-METHOD.md`. Input APK: the exact four APKs the OH board ran (base
`2fdb9b0b…`, splits `arm64_v8a`, `xxxhdpi`, `en`), scanned against runtime lock `96366a20…` —
the scan reproduces the 2026-09-18 findings exactly (1106/1106) and adds service requests.

| File | Contents |
|---|---|
| `mcdonalds-known-blockers.json` | The failures McDonald's hit on the board (B1–B8 through 2026-09-18, B9–B11 found on 2026-09-21/22), each naming the row that should predict it |
| `backtest-75d82d5/` | Map against the provider McDonald's actually ran on (Westlake `75d82d5`, launcher `f229702`) |
| `current/` | Map against today's provider (Westlake `f6dc615`), with the board's probe results applied (`../2026-09-22-mcdonalds-signin/`) |
| `runtime-lock-source-build.json` | Lock of the runtime McDonald's runs on: 9 boot jars and 48 libraries pulled from the board |
| `mcdonalds-scan.json` | The scan against that runtime, with `service_requests`, `platform_method_names` and `native_upcalls` (`--platform-jar android-34`) |
| `toutiao-native-upcalls.json` | Java APIs Toutiao 13.9.0's native libraries call back into, per library |

## Backtest: would the map have saved the trial and error?

Against the provider the app ran on: **6 of 8 predicted**, 1 flagged for verification, 1 missed.

| Blocker | Row | Outcome |
|---|---|---|
| B1 libraries not mappable out of the APK | `load:in-apk` missing | predicted |
| B2 bionic-only symbols | `sym:bionic libc` missing | predicted |
| B3 Akamai self-trap (SIGILL) | `env:akamai-bot-manager` | flagged for verification |
| B4 `jobscheduler` null | `svc:jobscheduler` null | predicted |
| B5 split resources invisible | `pm:splits` supplied | **missed**: mechanism present, naming convention wrong; needs a probe |
| B6 `location` null | `svc:location` null | predicted |
| B7 Realm `mkfifo` EACCES | `policy:fifo_file` denied | predicted |
| B8 Firebase component discovery empty | `pm:component-metadata` missing | predicted |

Before this change the harness's detectors flagged only B2, and scored B7's `mkfifo` as resolved.

## What is left today

88 rows, **68 open gaps**: 1×OH, 1×L, 20×M, 24×S, 22×verify; 43 are on the recorded path to sign-in.

**Provider corrected.** The scan now uses the runtime McDonald's really runs on, re-indexed from the
boot jars staged on the board (`runtime-lock-source-build.json`). The earlier map used the August
index of the legacy payload and reported 58 required Java absences, led by WiFi. Against the real
build there are **none**: its `framework.jar` carries the real AOSP WiFi, `TrafficStats` and job
classes. Native gaps are classified against the NDK provider model (`../2026-09-21-ndk-coverage/`).

| Effort | Items |
|---|---|
| **OH** | Create `fifo_file` in app data: OH policy denies what Android allows (Realm). One allow rule, no `neverallow` conflict; bring-up workaround: label the app-data tree `data_app_el2_file` |
| **L** | `phone` (TelephonyManager, binder unprovisioned) |
| **M** | NDK sensors weld: 11 `ASensor*` symbols over OH `sensors` (off the sign-in path). Services: `alarm`, `clipboard`, `uimode`, `wifi` null; `camera`, `sensor`, `download` inert; `audio`, `notification`, `user`, `jobscheduler` hollow. PackageManager `query*`/`resolve*` stubs. Networking, mDNS, media store. Symlinks (neverallow'd: needs a libc emulation). Google Play services |
| **XS** | NDK package: 6 `AAsset*`/`ALooper*` symbols. Westlake already builds `asset_manager.cpp` and `looper.cpp`; they are not deployed |
| **S** | bionic libc ABI: 13 of 14 covered by the shim, `__system_property_read` open. 10 small services (`power`, `keyguard`, `appops`, `locale`, …), 12 PackageManager stubs, the last sysprop symbol, `TrafficStats.setThreadStatsTag` hollow under `libpanorenderer.so`, and several small Java areas |
| **verify** | Providers at bind (`probes/provider-manifest`), component metadata (`probes/service-metadata`), splits (probe to write), hollow-candidate framework bodies, Firebase, Akamai refusal, Forter |

Known blockers against today's provider: 5 closed per source, **2 open**, 1 open-verify. The open
ones are B7 (policy) and **B4**: the JobScheduler that stopped the crash is a no-op, so WorkManager
jobs are accepted and never run.

## On the path to sign-in

Recorded on real Android (`../2026-09-21-android-baseline/`): **43 of the 68 open gaps are touched
between cold start and the sign-in screen** (1×OH, 1×L, 14×M, 15×S, 12×verify); 25 are not. Both
maps carry an "On path" column and a section listing those gaps with the evidence for each.

## Native code calling back into Java

A library reaches Java through `FindClass`/`GetMethodID` on the JNIEnv table, never through an
import, so neither the dex scan nor native-import resolution saw these calls. Matched from library
strings against `android-34/android.jar` and the runtime:

| | Libraries calling Java | Platform classes named | Members | Not present |
|---|---|---|---|---|
| McDonald's | 6 of 10 | 58 | 294 | `libpanorenderer.so` → `TrafficStats.setThreadStatsTag`, **hollow** in `adapter-mainline-stubs.jar` |
| Toutiao | 46 of 138 | 116 | 645 | `libttmplayer.so` → `AudioTrack.getMaxVolume` (constant in `framework.jar`, likely AOSP's own: candidate only) |

Toutiao's `libsysoptimizer`, `libjato`, `libart_sym` and `libreparo` also name nine classes that
neither the SDK nor Westlake has: `java/lang/reflect/ArtMethod`, `ArtField`, `AbstractMethod`,
`android/view/GLES20Canvas`, `android/view/RenderNode` (moved to `android/graphics` in API 29) and
`com/android/dex/Dex`. These libraries probe ART and old-Android internals across versions. That is
a runtime-integrity risk, not an API gap, and the map reports it as `CU` with that label.

The first McDonald's run reported 17 false "missing" members and 14 false "hollow" ones. They came
from four traps, each now a known-answer test:
- constructors are not inherited;
- SDK stub jars carry package-private placeholder constructors;
- an empty body in upstream libcore (`OutputStream.flush`) is upstream behaviour;
- a constant body in AOSP-compiled `framework.jar` may be AOSP's own (Toutiao's
  `AudioTrack.getMaxVolume`), so it is only a candidate there.

## Reproduce

```bash
westlake-apk-gap scan mcdonalds-26.31.1.xapk --runtime ../2026-08-23-toutiao/runtime-index.json \
  --platform-jar $ANDROID_HOME/platforms/android-34/android.jar --out mcdonalds-scan.json
westlake-apk-gap gap-map --scan mcdonalds-scan.json --apk mcdonalds-26.31.1.xapk \
  --api-levels mcdonalds-scan.json --aosp <imports> \
  --westlake <westlake at 75d82d5> --manifest-repo <manifest at f229702> \
  --oh-resolution ../2026-09-18-oh-board/oh-import-resolution.json --app-key mcdonalds \
  --ndk-coverage ../2026-09-21-ndk-coverage/source-build/ndk-coverage.json \
  --blockers mcdonalds-known-blockers.json --out backtest-75d82d5
```

The xapk is `manifest.json` plus the four APKs above, stored uncompressed.
