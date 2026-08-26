# Toutiao API scan — deployed ARM64 runtime

Captured 2026-08-23 (America/Los_Angeles) with the production `westlake_gap` scanner and a fresh runtime trace.

## Verdict

Toutiao **works through live feed population on the scanned runtime**. The fresh JIT-enabled child reached the side-channel gate, stayed alive, and exposed current Chinese headlines in `FeedTitleTextView` widgets. The scan nevertheless found real compatibility defects in optional/background paths. None of the observed API failures prevented feed construction in this run.

The raw count is not a blocker count: **626 static candidates** decomposes into 148 directly absent contracts, 32 probe-only candidates, and 446 hollow-body heuristic candidates. A further 1,945 unresolved native contracts are `CU` evidence records and are explicitly not counted as gaps.

## Content and runtime lock

- APK: Toutiao 13.9.0 (`com.ss.android.article.news`, version code 13900), 138,641,340 bytes.
- APK SHA-256: `a1112a0c941f865847c2fab9138cf815735268fbfcd41d697412fb80992c7395`.
- Target ABI: `arm64-v8a`; the APK contains ARM64 native libraries.
- Runtime: `sha256:96366a206a3fe68c5b78a68fafc9addc63932d8ecee1ee166ab802ea62322b2b`, 38,316 classes.
- Bridge: MD5 `77de9978da7d1d49e48e49510acf2311`, identical on host and board.

The runtime index was built from exact JAR copies pulled from `/data/local/tmp/asx/fw`. This matters: the deployed `adapter-mainline-stubs.jar`, `framework.jar`, `adapter-runtime-bcp.jar`, and `oh-adapter-framework.jar` did **not** match the nominal host `runtime/westlake-arm64-current.txt` artifacts. Results therefore describe the board that actually ran Toutiao, not the stale host set.

## Static result

| Bucket | Count | Interpretation |
|---|---:|---|
| Directly absent classes/members | 148 | 32 missing classes, 103 methods, 13 fields |
| `C1/C4` | 40 | 8 direct method call sites plus 32 missing reference-pool types |
| `C8-candidate` | 32 | Presence probes; 26 are vendor/app types and 6 platform types |
| `C9-candidate` direct | 108 | 95 missing methods and 13 missing fields in demonstrably stub-like runtime classes |
| `C9-candidate` hollow body | 446 | Heuristic only; includes legitimate base no-ops and callbacks |
| Native `CU` | 1,945 | Unresolved JNI contracts, retained for runtime attribution, not gaps |

The highest-reference direct absences are dominated by the loaded `adapter-mainline-stubs.jar`: `MediaStore` content URI fields/methods, Wi-Fi information, `TrafficStats`, and network-usage APIs. The highest-reference hollow candidates include base methods such as `InputStream.close`, `Activity.onWindowFocusChanged`, and drawable callbacks; reference count alone is not evidence that these need implementation.

The largest C8 probes are OEM-specific notch/performance classes (`HwNotchSizeUtil`, `FtFeature`, Flyme/MIUI/Qualcomm/MediaTek types). Their absence is the faithful non-OEM behavior and they should not be added merely to reduce the count.

## Runtime-reached Java gaps

The live run exposed four unique Java contracts. Three map to scanner findings; one is a platform-to-platform call outside the APK-reference scan.

| Contract | Static finding | Runtime effect | Feed blocker? |
|---|---|---|---|
| `MediaStore.Images.Media.EXTERNAL_CONTENT_URI` | `sha256:6d1134b0...`, C9, 107 refs | Two tolerated class-initializer failures (`PrivateApiLancetImpl` and `X/Ad4`) | No |
| `TrafficStats.getTotalRxBytes()J` | `sha256:7da5cbad...`, C9, 8 refs | Uncaught `NoSuchMethodError` exits a background `HandlerThread` | No, but real stability/telemetry defect |
| `NetworkStatsManager` | `sha256:119fe65e...`, C1/C4 reference-pool type | `NoClassDefFoundError` causes a tolerated `X/B71` initializer failure | No |
| `TelephonyFrameworkInitializer.getTelephonyServiceManager()` | Static blind spot: caller is deployed platform code | Uncaught `NoSuchMethodError` exits a background `HandlerThread` | No, but real platform defect |

This is the strongest fix queue from the Java scan. The generic platform fix is to stop exposing hollow mainline stubs as runtime implementations (or provide faithful implementations/semantics for these contracts), with Noice and Material Catalog controls before deployment.

## Native and boundary result

The ARM64 scan inventoried 3,257 APK native declarations. It resolved 1,312 statically and retained 1,945 as `CU`. The fresh trace observed seven APK native contracts with primary-lookup misses only; it captured no terminal miss for those seven, so they remain unresolved rather than promoted gaps.

Native-load tracing recorded 44 `dlopen` attempts: 15 succeeded and 29 failed across 20 unique paths. It also recorded 15 `JNI_OnLoad` lookups; five missing `JNI_OnLoad` symbols are not by themselves load failures because that entry point is optional.

The failed loads cluster at the Android/NDK boundary:

- missing or incomplete C++ ABI surface: `libstdc++.so` and multiple `std::__ndk1` symbols;
- missing support libraries: `libnpth.so`, `libnpth_dl.so`, `libbytehook.so`, `libsoundpool.so`, `libnetworkpredictor.so`, and Godzilla helper libraries;
- missing NDK API export: `ASensorManager_getDefaultSensor`;
- missing platform JNI: `UNIXProcess.initIDs()` and `MediaMetadataRetriever.native_init()` produced terminal lookup failures.

`libsscronet.so` failed six load attempts on a missing libc++ `basic_string` destructor, yet the feed populated. Therefore sscronet is **not required for feed networking in this run**; Toutiao used another network path or fallback. The feed-empty hypothesis is not reproduced by this runtime epoch.

## ART/JIT observation

The log explicitly reports `CreateJit()` returning with a live JIT code cache. Toutiao then built and populated its feed. JIT mode is therefore operational for this scenario.

The same run logged one `WESTLAKE-CHILDSEGV` event in the ART interpreter's `GOTO` handler. Child 25055 remained alive and the feed was visible afterward. This is a real runtime-integrity signal, but it is not an API gap and the evidence does not establish that JIT caused it; JIT-enabled processes still execute uncompiled methods in the interpreter.

## Recommended fix order

1. Replace/complete the reached hollow mainline contracts: `MediaStore` URI constants, `TrafficStats.getTotalRxBytes`, `NetworkStatsManager`, and the telephony initializer/service-manager path.
2. Repair the generic Android NDK compatibility boundary, prioritizing libc++/`libstdc++` symbol coverage and missing support libraries. This addresses many Toutiao libraries with one platform fix.
3. Implement or route platform JNI for `UNIXProcess`, `MediaMetadataRetriever`, and `SoundPool` according to Android semantics.
4. Reproduce the interpreter `GOTO` SIGSEGV with Toutiao plus Noice/Material controls; keep it separate from API-gap work.
5. Do not implement C8 OEM probes or all 446 hollow candidates without runtime reachability and semantic controls.

## Artifacts

- `REPORT.md`: generated static benchmark report.
- `apks/com.ss.android.article.news.json`: complete per-APK findings and evidence sites.
- `gap-registry.json`: deduplicated one-app gap registry.
- `runtime-lock.json`: content hashes and ordered deployed boot classpath.
- `SCAN-PROVENANCE.json`: concise APK/runtime/live-run lock.
- `trace-watchlist.json`: native/reflection watchlist.
- `runtime-evidence/live-run/EVIDENCE.md`: scanner-ingested runtime evidence.
- `runtime-evidence/live-run/view-tree.txt`: live feed widget oracle.
- `runtime-evidence/live-run/adapter_child_25055.stderr`: frozen raw runtime trace.

## Limits

Static references include dead and optional code. The production evidence ingester currently promotes JNI/reflection traces, but it does not ingest the legacy Java `NoSuchMethodError`/`NoSuchFieldError`/`NoClassDefFoundError` or `WESTLAKE-NATIVELOAD-754` lines; those were correlated manually above against the content-locked scan. Downloaded/plugin code not present in the stock APK remains outside the static inventory.
