# McDonald's 26.31.1 — cheap validation, 2026-09-18

Three checks against `com.mcdonalds.app` 26.31.1 (minSdk 28, **targetSdk 35**, split APK).
Static scan against the arm64 runtime lock, runtime capture on the OnePlus 6T baseline.

## 1. In-APK library loading — **required, and not just here**

McDonald's declares `extractNativeLibs="false"` and stores its `.so` entries uncompressed, so the
linker maps them straight out of the APK. Confirmed on the device:

```
/data/app/…/split_config.arm64_v8a.apk!/lib/arm64-v8a/librealm-jni.so
/data/app/…/split_config.arm64_v8a.apk!/lib/arm64-v8a/libakamaibmp.so
/data/app/…/com.google.android.webview.beta-…/base.apk!/lib/arm64-v8a/libwebviewchromium.so
```

**The third line is the important one.** WebView loads the same way in the *Toutiao* capture too, so
`apk!/lib/...` support is not a McDonald's quirk — **any app that uses WebView needs it.** Toutiao
happens to extract its own libraries, which is why this never surfaced before.

**Open:** whether the Westlake/OH linker accepts the `!/` form and maps an uncompressed zip member.
The board was not connected for this session (`hdc list targets` empty). This is a gate: if it does
not, all 10 McDonald's libraries and WebView fail to load, and no lifecycle theory is needed to
explain a missing UI.

## 2. Static scan — the gap list, without launch-path attribution

1106 findings against the arm64 runtime lock:

| Classification | Count |
|---|---|
| `CU` | 608 |
| `C9-candidate` (hollow) | 317 |
| `C1/C4` | 82 |
| `C8-candidate` (existence probe) | 56 |
| `N-C5-candidate` (weak undefined) | 42 |
| `O-BLIND` | 1 |

585 of the `CU` are `native_import` findings, correctly undecided because no system libraries are
indexed, plus the single `O-BLIND` coverage finding that records why. The detector behaved as
designed on its first real app.

Missing platform members cluster hard on **WiFi**: `WifiManager` 15, `WifiInfo` 10, `ScanResult` 7,
`WifiConfiguration` 5, then `TrafficStats` 5, `MediaStore` 4, `BluetoothDevice` 2, `SigningInfo` 2,
`NetworkRequest` 2, plus `android.adservices.*`.

**Limitation found:** `missing_class` findings carry empty `evidence`, so nothing attributes them to
the nine startup providers. The launch-path question the scan was run to answer cannot be answered
from this output — that is amendment item 2 (blast radius) on the Java side, and it is the reason
the device run below matters more than the scan.

## 2b. Filtered by API level — 138 absences become 58

The phone runs this app at **SDK 30**. Anything introduced after that cannot exist there, so the
app already tolerates its absence. `westlake-apk-gap annotate-api-levels` applies that filter
against the platform jars:

| Verdict | Count | Meaning |
|---|---|---|
| **required** | **58** | declared at API ≤ 30 — the app can really reach it |
| `newer-than-reference` | 23 | introduced after API 30; absent on the 6T too |
| `absent-from-platform` | 48 | never an Android API |
| `member-not-in-indexed-jars` | 9 | class exists, member newer than the newest jar supplied |

The 48 that were never Android are `java.beans`, `javax.activation`, `javax.naming`,
`javax.script`, `javax.security.sasl`, `java.awt.Image`, `java.lang.Module` — JavaSE classes reached
by libraries with a desktop code path — plus ten `com.android.tools.lint.*` classes (a build-time
API shipped inside a library by mistake) and the old `android.support.annotation` compile-time
annotations. None of them can ever execute.

The 23 newer ones are the twelve `android.adservices.*` Privacy Sandbox classes (API 34) and
scattered API 31-34 members.

**The 58 that remain concentrate almost entirely in one place:**

| Area | Findings | Examples |
|---|---|---|
| **WiFi** | **38** | `WifiManager.getScanResults/getConnectionInfo/getConfiguredNetworks/getDhcpInfo/isWifiEnabled`, `WifiInfo.getBSSID/getSSID/getMacAddress/getRssi`, `ScanResult.BSSID/SSID/level/frequency`, `WifiConfiguration`, `WifiEnterpriseConfig`, `WifiP2pManager` |
| networking | 13 | `NsdManager` + 3 listeners + `NsdServiceInfo`, `DhcpInfo`, `TrafficStats.getTotalRx/TxBytes`, `ConnectivityManager.getDefaultProxy` |
| media / content | 5 | `MediaStore$Images$Media.getBitmap/insertImage/EXTERNAL_CONTENT_URI` |
| bluetooth | 2 | `BluetoothAdapter.getBondedDevices`, `BluetoothDevice.getAddress` |

On top of that, `WifiManager` and `WifiInfo` are the 4th and 6th largest **hollow** classes — 15 and
10 methods present but stubbed. Part of the WiFi surface is not missing, it is answering with
nothing, which is harder to notice and worse to debug.

### Why WiFi is the risk, not the volume

`libakamaibmp.so` (Akamai Bot Manager) is one of only two app libraries that load at startup, and
Forter's fraud SDK owns two of the nine startup content providers. SSID, BSSID, scan results and MAC
are textbook device fingerprinting inputs. Stubs do not crash these SDKs — they make the session
look wrong to a backend, which is the same shape as Toutiao's `device_register` blocker: no crash,
no missing symbol, just a service declining to proceed.

Capture what these return on the 6T before implementing, so "plausible" has a reference.

## 3. Android baseline — it works, and barely touches native code

The app reaches `com.mcdonalds.account.activity.LoginRegistrationActivity` with a real sign-in
screen ("Sign in or sign up", "Continue with Email / Facebook / Google"). No crashes.

| Measure | Value |
|---|---|
| libraries loaded | 18 |
| registration tables | **3** |
| registered methods | **6** |
| `dlsym` lookups | 0 |

**All six registered methods are WebView's** (`nativeGetFunctionTable`, `nativeCreateGLFunctor`,
`nativeSetChromiumAwDrawGLFunction`, `nativeGetDrawSWFunctionTable`, …). Of McDonald's own ten
libraries, only `librealm-jni.so` and `libakamaibmp.so` load at all; the rest — ML Kit OCR, the
image processing JNI, the pano renderer — are behind features a login screen never reaches.

It also pulls the full vendor graphics stack: `gralloc.sdm845.so`, `mapper@2.0-impl-qti-display`,
`libEGL_adreno`, `libGLESv2_adreno`, `libadreno_utils`.

## What this changes in the plan

**McDonald's first-frame gate is almost entirely a Java framework problem.** Six native methods,
all of them WebView's, stand between a cold start and a usable login screen. That is consistent
with the recorded failure being `Activity.attach` / `AppComponentFactory` lifecycle rather than
anything native, and it means the 73 Android-specific symbols measured for this app are mostly
*not* on the path to first frame.

Two consequences:

- The MVP gate for McDonald's should be **first real frame plus sign-in screen**, which tests
  framework completeness, WebView, and in-APK loading — and almost nothing else.
- Exercising McDonald's native surface needs a scenario that goes **past login** into camera, OCR
  or offline storage. Worth building later; not on the critical path now.

Also worth recording: the manifest declares the stock `androidx.core.app.CoreComponentFactory` and
**no custom `Application` class**. Whatever component-factory machinery Westlake carries for this
app only has to reproduce generic AOSP behaviour.
