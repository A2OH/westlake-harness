# chat.fluffy.fluffychat 2.9.5 → OpenHarmony: API shim gap map

Provider: Westlake `provider-authority-resolution` @ `0b5c9af4ce`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 36.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 10 | 10 | 8×verify, 2×S |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 28 | 15 | 2×verify, 11×S, 2×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 1 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 10 | 9 | 1×verify, 3×S, 5×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 5 | 1 | 1×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 4 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 3 | 2 | 2×M |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 2 | 1 | 1×verify |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 1 | 1 | 1×M |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 0 | 0 | — |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | missing | C4 | S | window_manager / render_service | implement the members over window_manager / render_service<br>android.view.accessibility.AccessibilityNodeInfo$AccessibilityAction.ACTION_SET_EXTENDED_SELECTION, android.view.accessibility.AccessibilityNodeInfo.setChecked |
| Other Android | missing | C1/C5 | S | unmapped | port from AOSP, or confirm the caller tolerates absence<br>android.window.BackEvent.<init> |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.drawable.Drawable$ConstantState.canApplyTheme, android.graphics.drawable.Drawable.applyTheme, android.graphics.drawable.Drawable.canApplyTheme |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.Activity.onActivityResult, android.app.Activity.onCreateContextMenu, android.app.Activity.onCreateView |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayOutputStream.close, java.io.InputStream.available, java.io.InputStream.close |
| Other | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>org.xml.sax.helpers.DefaultHandler.endDocument, org.xml.sax.helpers.DefaultHandler.error, org.xml.sax.helpers.DefaultHandler.startDocument |
| Media | hollow-candidate | C9 | verify | multimedia | check each hollow body against AOSP<br>android.media.AudioDeviceCallback.onAudioDevicesAdded, android.media.AudioDeviceCallback.onAudioDevicesRemoved, android.media.AudioTrack.getMaxVolume |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.TextView.onTextChanged |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.isRestricted |
| Media store | hollow-candidate | C9 | verify | multimedia/media_library | check each hollow body against AOSP<br>android.provider.MediaStore.getPickImagesMaxLimit |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>18 call sites, e.g. B0.s.a `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1599` |
| notification | hollow | C9 | M | notification (ANS) | replace the hollow binder with an implementation over notification (ANS)<br>16 call sites, e.g. K.r.<init> `framework/android-runtime/src/AndroidRuntime.cpp:821` |
| biometric | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. u.e$a.b |
| camera | inert | C4 | S | multimedia/camera_framework | Android CameraManager facade over multimedia/camera_framework<br>5 call sites, e.g. com.cloudwebrtc.webrtc.GetUserMediaImpl.getUserVideo |
| keyguard | null | C4 | S | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>4 call sites, e.g. M3.q.F |
| media_metrics | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. I0.C1.H0 |
| media_projection | inert | C5 | S | unmapped | truthful local manager (feature absent)<br>3 call sites, e.g. com.cloudwebrtc.webrtc.GetUserMediaImpl$ScreenRequestPermissionsFragment.requestStart |
| phone | inert | C4 | S | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>2 call sites, e.g. D0.U.V |
| sensor | inert | C4 | S | sensors | Android SensorManager facade over sensors<br>2 call sites, e.g. r3.b.c |
| textservices | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. Y4.G.m |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>1 call sites, e.g. r3.e.d |
| wifi | null | C4 | S | communication/wifi | Android WifiManager facade over communication/wifi<br>3 call sites; Kotlin casts it non-null in 1 methods (e.g. com.pravera.flutter_foreground_task.service.ForegroundService.e): a null answer throws there, it is not skipped |
| wifip2p | null | C4 | S | communication/wifi (p2p) | Android WifiP2pManager facade over communication/wifi (p2p)<br>1 call sites, e.g. org.webrtc.NetworkMonitorAutoDetect$WifiDirectManagerDelegate.<init> |
| captioning | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. a1.n.N `SystemServiceRegistry.java:337` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. q.A$a.a `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>11 call sites, e.g. Q2.q.s |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>5 call sites, e.g. K4.e$a.c |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>4 call sites, e.g. K4.e$a.b |
| appops | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. K.f$a.c |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>6 call sites, e.g. io.flutter.plugin.editing.l.b |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>2 call sites, e.g. D0.x.h |
| display | supplied | C0 | verify | display_manager | none<br>8 call sites, e.g. D0.U.W |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>6 call sites, e.g. K2.l$a.run `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>39 call sites, e.g. Q2.z.<init> `SystemServiceRegistry.java:593` |
| location | supplied | C0 | verify | location | none<br>5 call sites, e.g. j.v.a |
| power | supplied | C0 | verify | powermgr | none<br>7 call sites, e.g. D0.Z$a.f |
| uimode | supplied | C0 | verify | display / theme | none<br>2 call sites, e.g. D0.U.J0 |
| window | supplied | C0 | verify | window_manager | none<br>19 call sites, e.g. D0.U.W `framework/core/java/OHServiceManager.java:96` |

## Keystore & crypto providers

_JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Android keystore provider ("AndroidKeyStore") | supplied | C0 | verify | security/huks (OH Universal Keystore); keystore2 has no OH counterpart | install an "AndroidKeyStore" provider whose keys come from KeyGenParameterSpec and stay per app: software keys in app data (days), or OH HUKS for hardware-backed keys (weeks). A blocker wherever the app opens it at startup (secure storage, encrypted preferences, biometric crypto, attestation)<br>4 classes name it, e.g. LG6/c;, LN3/i;, LN3/j;, Lu/i;; calls Cipher.getInstance("RSA/ECB/OAEPPadding"), KeyGenerator.getInstance("AES"), KeyPairGenerator.getInstance("RSA"), KeyStore.getInstance("AndroidKeyStore") `framework/core/java/SoftwareAndroidKeyStore.java:65` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| PackageManager.queryBroadcastReceivers | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1232` |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1225` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1253` |
| PackageManager.queryIntentServices | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1246` |
| PackageManager.resolveService | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1239` |
| PackageManager.getInstallSourceInfo | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1528` |
| PackageManager.getInstallerPackageName | stub | C9 | S | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1521` |
| PackageManager.getSystemAvailableFeatures | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1814` |
| Content providers installed at bind (3, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>ImagePickerFileProvider, ShareFileProvider, InitializationProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>4 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

## Activity, window & process contracts

_what system_server would answer, answered in-process by Westlake in direct launch → white-box probes_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| WebView's renderer runs in an isolated service process | missing | C4 | L | process spawn (appspawn): an isolated Android service process with its own sandbox | host the renderer: spawn an isolated child and bind Chromium's SandboxedProcessService over a local channel; or build the framework with the update-service flag off so WebView runs single-process<br>app constructs WebViews and calls 7 WebView methods `frameworks-base/core/java/android/webkit/WebViewDelegate.java:215` |
| ActivityManager process-table queries (getRunningAppProcesses, getRunningServices) | supplied | C0 | verify | none (the caller's own process is the answer) | answer with the caller's process: name, pid, uid, foreground importance, its package<br>app calls getRunningAppProcesses, getRunningServices `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1381` — probe: `probes/running-app-processes` |
| Dialogs stack above their activity's window, whatever the add order | supplied | C0 | verify | window_manager (sub-window z-order: creation order) | stack a base application window below the dialogs already attached to its token<br>app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added before the activity's own window `framework/window/java/WindowSessionAdapter.java:370` — probe: `probes/dialog-before-window` |
| Windows placed by LayoutParams gravity and x/y (dialogs centred) | supplied | C0 | verify | window_manager (session rect) | compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:346` — probe: `probes/dialog-before-window` |
| FLAG_DIM_BEHIND dims what is under a dialog | supplied | C0 | verify | render_service (a layer under the window) | draw a dim layer of dimAmount under the window (OH has no dim flag)<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:84` — probe: `probes/dialog-before-window` |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libdartjni.so → 5 classes, 10 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/ByteArrayOutputStream, java/io/PrintStream, java/lang/Exception, java/lang/Long |
| libdatastore_shared_counter.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/IOException |
| libflutter.so → 14 classes, 36 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/graphics/Bitmap, android/graphics/Bitmap$Config, android/graphics/Path, android/graphics/Path$FillType |
| libjingle_peerconnection_so.so → 14 classes, 49 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Boolean, java/lang/ClassLoader, java/lang/Double, java/lang/Enum |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libandroid.so entry points looked up by name at runtime, not supplied (14) | unresolved | C1/C2 | M | dlopen("libandroid.so") + dlsym, resolved against whatever the search path reaches first | supply libandroid.so's entry points, or confirm the caller degrades without them: this row cannot tell a lookup that happens from a string that is never used<br>14 public NDK symbols of libandroid.so appear as literals: AChoreographer_getInstance, AChoreographer_postFrameCallback, AChoreographer_postFrameCallback64, AHardwareBuffer_fromHardwareBuffer, ASurfaceControl_createFromWindow, ASurfaceControl_release … — probe: `probes/webview-boundaries measures the search path; resolving each name on the board is what settles whether the lookup would succeed` |
| libnativewindow.so entry points looked up by name at runtime, not supplied (6) | unresolved | C1/C2 | M | dlopen("libnativewindow.so") + dlsym, resolved against whatever the search path reaches first | supply libnativewindow.so's entry points, or confirm the caller degrades without them: this row cannot tell a lookup that happens from a string that is never used<br>6 public NDK symbols of libnativewindow.so appear as literals: AHardwareBuffer_describe, AHardwareBuffer_getId, AHardwareBuffer_isSupported, AHardwareBuffer_lock, AHardwareBuffer_unlock, ANativeWindow_acquire — probe: `probes/webview-boundaries measures the search path; resolving each name on the board is what settles whether the lookup would succeed` |
| libc calls carrying a constant each libc numbers differently (sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>sysconf: 5 libraries, e.g. libflutter.so, libjingle_peerconnection_so.so, libsqlcipher.so `framework/webview-shim/webview_bionic_shim.c:1308` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |
| Libraries mapped straight out of the APK (9 .so, extractNativeLibs=false) | supplied | C0 | verify | OH dynamic linker (cannot map zip!/ members: board test 2026-09-18) | extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too) `manifest/tools/prepare_app.py:75` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create lnk_file in app data | denied | C5 | M | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>libflutter.so:symlinkat `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## Limits of this map

- 21 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'newer-than-reference': 12, 'absent-from-platform': 2}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
