# NDK assets probe

The NDK asset path React Native loads its JavaScript bundle through (`JSLoader.cpp`
`loadScriptFromAssets`): `AAssetManager_fromJava`, `AAssetManager_open(..., AASSET_MODE_STREAMING)`,
`AAsset_getLength`, `AAsset_read`, `AAsset_getBuffer`, `AAssetManager_openDir`. It checks one
compressed and one stored asset, plus a missing one, with Java's `AssetManager` as the control.
Each step prints a `[WL-NDKASSET]` line to stderr. Build with `./build.sh` (needs the Android NDK).

## 2026-09-27 result (framework 63)

Every step succeeds for both assets and the missing one returns null, so the NDK asset manager is
not what fails React Native. Its libraries are loaded in the isolated Android namespace, where
`libandroid.so` is the WebView shim's. That shim forwards `AAsset*` to `libwestlake_asset_bridge.so`,
which no current build ships ("Error loading shared library libwestlake_asset_bridge.so"), so
`AAssetManager_fromJava` returns null there and React Native reports "Unable to load script".
