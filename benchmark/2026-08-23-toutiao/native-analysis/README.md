# Native provenance and surface reach — Toutiao arm64

`native-surface.json` is the output of:

```
westlake-apk-gap native-surface <toutiao.apk>!lib/arm64-v8a --abi arm64-v8a \
  --out benchmark/2026-08-23-toutiao/native-analysis/native-surface.json
```

over the 138 arm64 libraries in `input/toutiao.apk`. Every library in that APK is stripped.

| Measure | Value |
|---|---|
| libraries scanned | 138 |
| libraries yielding a `RegisterNatives` table | 60 |
| registered methods recovered | 1417 |
| methods reaching no platform surface | 659 (47%) |
| methods reaching `dlopen`/`dlsym` — verdict unproven | 279 (20%) |
| platform-coupled methods | 175 (12%) |
| libraries containing an identifiable upstream component | 33 |

Per-method results are a **lower bound**: direct `bl` edges plus `b` tail calls into known
function entries, `"basis": "direct-bl-lower-bound"`. Read `analysis/NATIVE-PROVENANCE-AND-SURFACE.md` for the method, the two
blind spots, and what the numbers do and do not license.
