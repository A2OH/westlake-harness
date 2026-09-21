# McDonald's 26.31.1: the gap map, and a backtest against the board

Method: `analysis/GAP-MAP-METHOD.md`. Input APK: the exact four APKs the OH board ran (base
`2fdb9b0b…`, splits `arm64_v8a`, `xxxhdpi`, `en`), scanned against runtime lock `96366a20…` —
the scan reproduces the 2026-09-18 findings exactly (1106/1106) and adds service requests.

| File | Contents |
|---|---|
| `mcdonalds-known-blockers.json` | The eight failures McDonald's hit on the board, each naming the row that should predict it |
| `backtest-75d82d5/` | Map against the provider McDonald's actually ran on (Westlake `75d82d5`, launcher `f229702`) |
| `current/` | Map against today's provider (Westlake `c279d16` + 9 uncommitted files, recorded in the map) |
| `mcdonalds-scan.json` | The scan, with `service_requests` and `platform_method_names` |

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

90 rows, **76 open gaps**: 1×OH, 3×L, 22×M, 30×S, 20×verify.

| Effort | Items |
|---|---|
| **OH** | Create `fifo_file` in app data: OH policy denies what Android allows (Realm). One allow rule, no `neverallow` conflict; bring-up workaround: label the app-data tree `data_app_el2_file` |
| **L** | WiFi (38 members over `communication/wifi`); `phone` (TelephonyManager, binder unprovisioned); 17 `libandroid` NDK symbols (`AAsset*`, `ALooper*`, `ASensor*`) |
| **M** | Services: `alarm`, `clipboard`, `uimode`, `wifi` null; `camera`, `sensor`, `download` inert; `audio`, `notification`, `user`, `jobscheduler` hollow. PackageManager `query*`/`resolve*` stubs. Networking, mDNS, media store. Symlinks (neverallow'd: needs a libc emulation). Google Play services |
| **S** | 10 small services (`power`, `keyguard`, `appops`, `locale`, …), 12 PackageManager stubs, the last sysprop symbol, and several small Java areas |
| **verify** | Providers at bind (`probes/provider-manifest`), component metadata (`probes/service-metadata`), splits (probe to write), hollow-candidate framework bodies, Firebase, Akamai refusal, Forter |

Known blockers against today's provider: 5 closed per source, **2 open**, 1 open-verify. The open
ones are B7 (policy) and **B4**: the JobScheduler that stopped the crash is a no-op, so WorkManager
jobs are accepted and never run.

## Reproduce

```bash
westlake-apk-gap scan mcdonalds-26.31.1.xapk --runtime ../2026-08-23-toutiao/runtime-index.json --out mcdonalds-scan.json
westlake-apk-gap gap-map --scan mcdonalds-scan.json --apk mcdonalds-26.31.1.xapk \
  --api-levels ../2026-09-18-mcdonalds/scan-api-annotated.json --aosp <imports> \
  --westlake <westlake at 75d82d5> --manifest-repo <manifest at f229702> \
  --oh-resolution ../2026-09-18-oh-board/oh-import-resolution.json --app-key mcdonalds \
  --blockers mcdonalds-known-blockers.json --out backtest-75d82d5
```

The xapk is `manifest.json` plus the four APKs above, stored uncompressed.
