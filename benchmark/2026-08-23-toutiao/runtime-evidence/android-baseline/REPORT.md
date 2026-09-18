# Android baseline: what running the app reveals that reading it cannot

**Device.** OnePlus 6T (ONEPLUS A6013), Android 11, arm64-v8a, rooted with Magisk.
**Subject.** `com.ss.android.article.news` 13.9.0 — the same APK as `../../input/toutiao.apk`.
**Date.** 2026-09-18. **Captures.** `capture-scenario-001.jsonl` (scripted scenario),
`capture-attach-001/002.jsonl` (early attach, `dlsym` hooked from the start).

On this device the app runs to completion: feed content loads, all five tabs work. That matters
independently of the numbers below — it is the reference behaviour a port is aiming at.

## Static reading versus running

| | Static scan | Runtime capture |
|---|---|---|
| Libraries yielding JNI tables | 60 of 138 packaged | 37 |
| Registered methods | 1340 | 1157 |
| Registration tables observed | — | 135 |
| Methods the other side missed | 463 never exercised | **280 invisible to static** |
| Union | | **1620** |

Both directions are findings. The 280 are surface no APK scan can reach; the 463 are surface this
scenario never touched, which is the coverage number a single run can't otherwise give you.

## Where the 280 come from

**Five libraries that are not in the APK at all — 240 methods.**

| Library | Methods |
|---|---|
| `libwcdb.so` | 91 |
| `libavmdlv2.so` | 66 |
| `libpreload.so` | 60 |
| `libcachemodule.so` | 17 |
| `libwebviewchromium_plat_support.so` | 6 |

Delivered after install or supplied by the system. This is the re-entrant code inventory the
process spec calls for, measured: **15% of the observed native API surface ships outside the APK.**

**Three packaged libraries opaque to static reading — 36 methods.** `libxbnlog.so` (19),
`libbdsword.so` (16), and one method from `libmetasec_ml.so`, the anti-tamper library that yielded
nothing statically. A library must hand its table to `RegisterNatives` to work, so running defeats
that particular opacity by construction.

**Six code objects loaded from outside the APK**, including three
`files/hotfix-root/install/*/oat/arm64/patch.odex` — live patches, plus the WebView provider's odex.

## `dlsym`: the silent-fallback evidence

43 distinct symbols failed to resolve, in ART's short-then-mangled pairs:

```
Java_com_bytedance_compression_zstd_ZstdCompressCtx_init
Java_com_bytedance_compression_zstd_ZstdCompressCtx_init__
```

A failed `dlsym` does not crash — the caller takes another branch and the consequence appears
somewhere unrelated. That is the `C8` failure mode on the native side, observed rather than argued,
and it is the basis for the proposed `N-C8` class in `analysis/NATIVE-GAP-PROCESS-AMENDMENT.md`.

## Reproducing

```
westlake-apk-gap native-capture-diff --capture capture-scenario-001.jsonl \
  --capture capture-attach-001.jsonl --capture capture-attach-002.jsonl \
  --surface ../../native-analysis/native-surface.json --out static-vs-runtime.json
```

Agent and drivers: `harness/jniprobe/`, which also records the four Frida and Magisk obstacles
this run hit.
