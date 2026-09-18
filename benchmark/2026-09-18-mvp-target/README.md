# MVP target surface — Toutiao and McDonald's

`mvp-target-symbols.json` is the Android-specific platform contract of both MVP apps, derived by
resolving every packaged library's undefined symbols against a stock Android 11 arm64 device and
keeping what only the platform can supply.

| | Toutiao 13.9.0 | McDonald's 26.31.1 | Union |
|---|---|---|---|
| packaged arm64 libraries | 138 | 10 | — |
| platform symbols required | 756 | 550 | 855 |
| Android-specific | 199 | 73 | **206** |
| shared by both | — | — | 66 |

Of the 206, **133 are plain GLES and 25 are EGL** — supplied by the GPU driver, not by us. The
implementation target is the remaining **48 non-GL entry points**: `AAsset*` (6), `ALooper_*` (9),
`ANativeWindow_*` (9), `ASensor*` (11), `AndroidBitmap_*` (3), OpenSL ES (10).

Reproduce with the recipe in `../2026-08-23-toutiao/native-analysis/ANDROID11-RESOLUTION.md`, then
resolve each app's libraries against the pulled index.

Strategy and the plan that uses this: `analysis/AOSP-PACKAGING-STRATEGY.md`.
