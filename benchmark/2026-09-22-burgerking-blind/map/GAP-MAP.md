# com.emn8.mobilem8.nativeapp.bk 7.82.0 → OpenHarmony: API shim gap map

Provider: Westlake `mcdonalds-signin-fixes` @ `f6dc615029`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 36.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 12 | 12 | 12×verify |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 33 | 24 | 3×verify, 11×S, 9×M, 1×L |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 18 | 15 | 9×S, 6×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 4 | 0 | — |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 21 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 1 | 1 | 1×M |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 1 | 0 | — |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 1 | 1 | 1×M |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 3 | 3 | 2×verify, 1×M |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | hollow-candidate | C9 | verify | window_manager / render_service | check each hollow body against AOSP<br>android.view.ActionProvider.hasSubMenu, android.view.ActionProvider.isVisible, android.view.ActionProvider.onPerformDefaultAction |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.Canvas.disableZ, android.graphics.Canvas.enableZ, android.graphics.Canvas.getMaximumBitmapHeight |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayInputStream.close, java.io.ByteArrayOutputStream.close, java.io.InputStream.available |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.Activity.onActivityResult, android.app.Activity.onCreateContextMenu, android.app.Activity.onCreateView |
| Camera | hollow-candidate | C9 | verify | multimedia/camera_framework | check each hollow body against AOSP<br>android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureBufferLost, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureCompleted, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureFailed |
| WebView | hollow-candidate | C9 | verify | web (ArkWeb) or bundled Chromium | check each hollow body against AOSP<br>android.webkit.HttpAuthHandler.proceed, android.webkit.SslErrorHandler.cancel, android.webkit.WebChromeClient.onCreateWindow |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.AsyncTask.onPostExecute, android.os.AsyncTask.onPreExecute, android.os.Binder.isBinderAlive |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.getAttributionTag, android.content.Context.isRestricted, android.content.ServiceConnection.onBindingDied |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.TextView.getDefaultMovementMethod, android.widget.TextView.onTextChanged |
| Networking | hollow-candidate | C9 | verify | netmanager | check each hollow body against AOSP<br>android.net.ConnectivityManager$NetworkCallback.onCapabilitiesChanged, android.net.ConnectivityManager$NetworkCallback.onLost |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>No default CameraXConfig.Provider specified in meta-data. The most likely cause is you did not include a default implementation in your build such as 'camera-camera2'., androidx.compose.ui.node.LayoutNode, androidx.compose.ui.node.NodeChain |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| phone | inert | C4 | L | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>14 call sites, e.g. com.amplitude.reactnative.a$a.e |
| alarm | null | C4 | M | time_service / reminder_agent | Android AlarmManager facade over time_service / reminder_agent<br>8 call sites, e.g. androidx.work.impl.background.systemalarm.a.b |
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>9 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.I0 `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1569` |
| camera | inert | C4 | M | multimedia/camera_framework | Android CameraManager facade over multimedia/camera_framework<br>3 call sites, e.g. Z.d.<init> |
| clipboard | null | C4 | M | miscservices/pasteboard | Android ClipboardManager facade over miscservices/pasteboard<br>4 call sites, e.g. androidx.appcompat.widget.k.b |
| jobscheduler | hollow | C9 | M | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>7 call sites, e.g. androidx.work.impl.background.systemjob.g.<init> `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2088` |
| notification | hollow | C9 | M | notification (ANS) | replace the hollow binder with an implementation over notification (ANS)<br>19 call sites, e.g. androidx.core.app.NotificationManagerCompat.<init> `framework/android-runtime/src/AndroidRuntime.cpp:821` |
| sensor | inert | C4 | M | sensors | Android SensorManager facade over sensors<br>10 call sites, e.g. androidx.media3.exoplayer.video.spherical.SphericalGLSurfaceView.<init> |
| user | hollow | C9 | M | account/os_account | replace the hollow binder with an implementation over account/os_account<br>4 call sites, e.g. I0.p$a.a `framework/android-runtime/src/AndroidRuntime.cpp:821` |
| wifi | null | C4 | M | communication/wifi | Android WifiManager facade over communication/wifi<br>4 call sites, e.g. androidx.media3.exoplayer.m1$a.a |
| appops | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. androidx.core.app.g$b.c |
| batterymanager | null | C4 | S | powermgr/battery_manager | Android BatteryManager facade over powermgr/battery_manager<br>2 call sites, e.g. x7.b.<init> |
| biometric | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. p.e$a.b |
| download | inert | C4 | S | miscservices/download_server | Android DownloadManager facade over miscservices/download_server<br>1 call sites, e.g. com.reactnativecommunity.webview.l.h |
| fingerprint | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. D0.a$b.c |
| keyguard | null | C4 | S | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>2 call sites, e.g. p.m$a.a |
| locale | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. androidx.appcompat.app.f.Q |
| media_metrics | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. C1.D1.G0 |
| power | null | C4 | S | powermgr | Android PowerManager facade over powermgr<br>11 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$n.<init> |
| uimode | null | C4 | S | display / theme | Android UiModeManager facade over display / theme<br>8 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.C0 |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>2 call sites, e.g. com.facebook.react.modules.vibration.VibrationModule.getVibrator |
| captioning | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>8 call sites, e.g. S1.n.K `SystemServiceRegistry.java:337` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.m$a.a `SystemServiceRegistry.java:413` |
| vibrator_manager | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>2 call sites, e.g. com.facebook.react.modules.vibration.VibrationModule.getVibrator `SystemServiceRegistry.java:796` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>13 call sites, e.g. T0.a.<init> |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>23 call sites, e.g. Q2.v$d.k |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>21 call sites, e.g. com.braze.dispatch.f.<init> |
| display | supplied | C0 | verify | display_manager | none<br>9 call sites, e.g. V1.k$c.a |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>12 call sites, e.g. androidx.appcompat.widget.AppCompatTextView.onDetachedFromWindow `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>4 call sites, e.g. Q0.c.<init> `SystemServiceRegistry.java:593` |
| location | supplied | C0 | verify | location | none<br>7 call sites, e.g. androidx.appcompat.app.y.a |
| shortcut | supplied | C0 | verify | unmapped | none<br>3 call sites, e.g. expo.modules.quickactions.a.G |
| window | supplied | C0 | verify | window_manager | none<br>28 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.M0 `framework/core/java/OHServiceManager.java:96` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| PackageManager.queryBroadcastReceivers | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1186` |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1179` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1207` |
| PackageManager.queryIntentServices | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1200` |
| PackageManager.resolveContentProvider | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1242` |
| PackageManager.resolveService | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1193` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1653` |
| PackageManager.getInstallSourceInfo | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1454` |
| PackageManager.getInstalledApplications | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1228` |
| PackageManager.getInstallerPackageName | stub | C9 | S | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1447` |
| PackageManager.getNameForUid | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1121` |
| PackageManager.getPackagesForUid | stub | C9 | S | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1112` |
| PackageManager.getReceiverInfo | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1037` |
| PackageManager.getSystemAvailableFeatures | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1740` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1641` |
| Split APKs visible to resources and class loading (3 splits) | supplied | C0 | verify | none (Westlake PM + asset manager) | populate splitNames/splitSourceDirs from the installed split set<br>config.arm64_v8a.apk, config.en.apk, config.xxhdpi.apk `framework/package-manager/java/SplitApkResolver.java:115` — probe: `none yet (propose: split-resources)` |
| Component lookups return manifest <meta-data> | supplied | C0 | none | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>10 components carry meta-data (2 directBootAware, e.g. ComponentDiscoveryService, MlKitComponentDiscoveryService); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getReceiverInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |
| Content providers installed at bind (8, initOrder honoured) | supplied | C0 | none | none | install every main-process provider in initOrder before Application.onCreate<br>RNCWebViewFileProvider, ReactNativeFirebaseAppInitProvider@99, SharingFileProvider, DdRumContentProvider, InitializationProvider, FileSystemFileProvider, FirebaseInitProvider@100, MlKitInitProvider@99 — probe: `probes/provider-manifest` |

## Activity, window & process contracts

_what system_server would answer, answered in-process by Westlake in direct launch → white-box probes_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| ActivityManager process-table queries (getRunningAppProcesses, getRunningServices) | supplied | C0 | none | none (the caller's own process is the answer) | answer with the caller's process: name, pid, uid, foreground importance, its package<br>app calls getRunningAppProcesses, getRunningServices `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1351` — probe: `probes/running-app-processes` |
| Dialogs stack above their activity's window, whatever the add order | supplied | C0 | none | window_manager (sub-window z-order: creation order) | stack a base application window below the dialogs already attached to its token<br>app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added before the activity's own window `framework/window/java/WindowSessionAdapter.java:370` — probe: `probes/dialog-before-window` |
| Windows placed by LayoutParams gravity and x/y (dialogs centred) | supplied | C0 | none | window_manager (session rect) | compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:346` — probe: `probes/dialog-before-window` |
| FLAG_DIM_BEHIND dims what is under a dialog | supplied | C0 | none | render_service (a layer under the window) | draw a dim layer of dimAmount under the window (OH has no dim flag)<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:84` — probe: `probes/dialog-before-window` |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libNitroMmkv.so → 1 classes, 2 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/NullPointerException |
| libNitroModules.so → 14 classes, 73 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Boolean, java/lang/ClassCastException, java/lang/Double, java/lang/Float |
| libappmodules.so → 1 classes, 1 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/String |
| libbarhopper_v3.so → 2 classes, 1 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/IllegalArgumentException, java/lang/String |
| libdatastore_shared_counter.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/IOException |
| libexpo-modules-core.so → 13 classes, 73 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Boolean, java/lang/ClassCastException, java/lang/Double, java/lang/Float |
| libfast-rsa.so → 5 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Exception, java/lang/IllegalArgumentException, java/lang/NullPointerException, java/lang/OutOfMemoryError |
| libfbjni.so → 12 classes, 56 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/os/Build$VERSION, java/io/IOException, java/lang/ArrayIndexOutOfBoundsException, java/lang/NullPointerException |
| libgifimage.so → 2 classes, 2 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/IllegalArgumentException, java/lang/IllegalStateException |
| libhermesvm.so → 9 classes, 39 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Boolean, java/lang/ClassCastException, java/lang/Double, java/lang/Integer |
| libimagepipeline.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/RuntimeException |
| libmmkv.so → 1 classes, 2 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/String |
| libnative-filters.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/RuntimeException |
| libnative-imagetranscoder.so → 3 classes, 4 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/InputStream, java/io/OutputStream, java/lang/RuntimeException |
| libreact_codegen_rnscreens.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/String |
| libreact_codegen_rnsvg.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/String |
| libreactnative.so → 16 classes, 77 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Boolean, java/lang/Class, java/lang/ClassCastException, java/lang/Double |
| libreanimated.so → 2 classes, 2 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/NullPointerException, java/lang/Object |
| librnscreens.so → 2 classes, 2 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Integer, java/lang/NullPointerException |
| libstatic-webp.so → 5 classes, 8 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/FileDescriptor, java/io/InputStream, java/lang/IllegalArgumentException, java/lang/IllegalStateException |
| libworklets.so → 1 classes, 1 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/NullPointerException |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| NDK weld · window: 2 symbols | missing | C4 | M | window_manager + render_service | AOSP NDK source above, window_manager + render_service below<br>open: ANativeWindow_lock, ANativeWindow_unlockAndPost |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Libraries mapped straight out of the APK (34 .so, extractNativeLibs=false) | supplied | C0 | verify | OH dynamic linker (cannot map zip!/ members: board test 2026-09-18) | extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too) `manifest/tools/prepare_app.py:75` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create lnk_file in app data | denied | C5 | M | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>libc++_shared.so:symlink, libjsi.so:symlink, libreactnative.so:symlink `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## External services & SDK behaviour

_SDKs that expect Google services or probe the device_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Google Play services | absent | C5 | M | none: no Google services on OH | decide per feature: truthful 'unavailable' result, or an OH-backed replacement (push, maps, auth)<br>application meta-data com.google.android.gms.version |
| Firebase component discovery (ComponentDiscoveryService) | partial | C5 | verify | none: no Google services on OH | component discovery is local (see pm:component-metadata); GMS-backed components degrade<br>com.google.firebase.components.ComponentDiscoveryService declares 14 registrars |
| Firebase component discovery (MlKitComponentDiscoveryService) | partial | C5 | verify | none: no Google services on OH | component discovery is local (see pm:component-metadata); GMS-backed components degrade<br>com.google.mlkit.common.internal.MlKitComponentDiscoveryService declares 3 registrars |

## Limits of this map

- 7 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'newer-than-reference': 8}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
