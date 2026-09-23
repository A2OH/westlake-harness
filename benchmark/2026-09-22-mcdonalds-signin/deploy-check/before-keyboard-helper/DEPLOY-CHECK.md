# Deployment check: sign-in launch before the keyboard helper was staged

297 files staged; the runtime asks for 39 libraries by name.

**Missing: 6. Older than their source: 2.**

## Asked for, not deployed

| Library | How | If absent | Where |
|---|---|---|---|
| `/data/local/tmp/asx/webview-t-lib/libwebviewchromium.so` | dlopen | caller decides | `framework/webview-shim/oh_webview_navigation_probe.cpp:41`, `framework/webview-shim/oh_webview_navigation_probe.cpp:66`, `framework/webview-shim/oh_webview_navigation_probe.cpp:553` |
| `libjavacore.so` | dlopen | caller decides | `framework/android-runtime/include/AndroidRuntime.cpp:280`, `framework/android-runtime/src/AndroidRuntime.cpp:3812`, `framework/android-runtime/src/libcore_util_NativeAllocationRegistry_guard.cpp:121` |
| `liboh_ime_helper.so` | dlopen | caller decides | `framework/window/jni/input_method_bridge.cpp:121` |
| `liboh_ime_helper_capi.so` | System.loadLibrary | throws | `framework/window/java/OhImeBridge.java:59` |
| `libwebviewchromium.so` | dlopen | caller decides | `framework/webview-shim/oh_webview_navigation_probe.cpp:49`, `framework/webview-shim/oh_webview_navigation_probe.cpp:73`, `framework/webview-shim/oh_webview_navigation_probe.cpp:555` |
| `libwestlake_asset_bridge.so` | dlopen | caller decides | `framework/webview-shim/libandroid_webview_shim.c:439` |

## Deployed binaries and their source

A source file counts when the binary holds some of its log strings; it is stale when it holds some but not all.

| Binary | Verdict | Stale source files | Example string absent |
|---|---|---|---|
| `liboh_adapter_bridge.so` | older than source | `oh_window_manager_client.cpp` | `[WESTLAKE-GONW] 4 GetSurface returned` (oh_window_manager_client.cpp) |
| `liboh_android_runtime.so` | older than source | `AndroidRuntime.cpp`, `android_graphics_compat_shim.cpp`, `android_view_DisplayEventReceiver.cpp` | `[WESTLAKE-458] WlAmsBind.install not found` (AndroidRuntime.cpp) |

Matching their source: `libandroid_native_network_compat.so`, `liboh_hwui_shim.so`, `libsoundpool.so`, `libwestlake_bionic.so`.
