# com.mcdonalds.app 26.31.1 → OpenHarmony: API shim gap map

Provider: Westlake `burgerking-startup-fixes` @ `8984f3c772`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 35.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 17 | 17 | 12×verify, 5×S |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 33 | 19 | 1×verify, 10×S, 7×M, 1×L |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 0 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 20 | 19 | 1×verify, 12×S, 6×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 5 | 4 | 3×M, 1×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 6 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 4 | 3 | 2×S, 1×M |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 1 | 0 | — |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 2 | 2 | 1×M, 1×OH |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 5 | 5 | 4×verify, 1×M |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Known blockers: status against this provider

Of 4 blockers already hit on the board: **2** open, **1** closed per source (confirm on device), **1** no row.

| Blocker | Symptom on device | Row | Status |
|---|---|---|---|
| M1 | Realm: mmap() failed (size 496, offset 81944): Invalid argument. Its page size came from sysconf(_SC_PAGESIZE): bionic numbers that selector 39, OH musl reads 39 as _SC_BC_STRING_MAX and answers 1000, so Realm's power-of-two rounding produced an unaligned offset and the activity died opening its database | `libc:constant-namespace` (supplied) | closed per source (confirm on device) |
| M2 | UserManager.getApplicationRestrictions reached the in-process IUserManager, which threw UnsupportedOperationException inside a JNI callback; Chromium aborted the process | `svc:user` (strict) | open |
| M3 | the app's bottom-navigation menu is empty, so McDBaseActivity.showSelector dereferences a null MenuItem: the ordering host loops on its loading animation and the restaurant picker takes the process down. The menu is built from configuration that ConfigHelper never loads (its map stays null); the configuration itself is present, bundled in assets/server_config.json and parsed into the app's own SDK store | `—` (—) | no row |
| M4 | the app's Upgrade dialog is laid out wider than the 1200 px display on some launches (a window bounds of 1282 px was logged), putting its OK button off the right edge; with no working back key the dialog cannot be dismissed at all | `wm:window-placement` (missing) | open |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | missing | C4 | S | window_manager / render_service | implement the members over window_manager / render_service<br>android.view.DisplayListCanvas, android.view.HardwareCanvas, android.view.RenderNode |
| Java library | missing | C1/C5 | S | none (library code inside Westlake) | port from AOSP, or confirm the caller tolerates absence<br>java.awt.Image, java.beans.BeanDescriptor, java.beans.BeanInfo |
| Java extensions | missing | C1/C5 | S | none (library code inside Westlake) | port from AOSP, or confirm the caller tolerates absence<br>javax.activation.ActivationDataFlavor, javax.activation.DataContentHandler, javax.activation.DataHandler |
| Other | missing | C1/C5 | S | unmapped | port from AOSP, or confirm the caller tolerates absence<br>com.android.tools.lint.client.api.IssueRegistry, com.android.tools.lint.detector.api.Category, com.android.tools.lint.detector.api.Detector |
| Other Android | missing | C1/C5 | S | unmapped | port from AOSP, or confirm the caller tolerates absence<br>android.support.annotation.NonNull, android.support.annotation.UiThread |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.Canvas.disableZ, android.graphics.Canvas.enableZ, android.graphics.Canvas.getMaximumBitmapHeight |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.ActionBar.setHomeActionContentDescription, android.app.ActionBar.setHomeAsUpIndicator, android.app.Activity.onActivityResult |
| WebView | hollow-candidate | C9 | verify | web (ArkWeb) or bundled Chromium | check each hollow body against AOSP<br>android.webkit.HttpAuthHandler.proceed, android.webkit.SslErrorHandler.cancel, android.webkit.SslErrorHandler.proceed |
| Camera | hollow-candidate | C9 | verify | multimedia/camera_framework | check each hollow body against AOSP<br>android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureBufferLost, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureCompleted, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureFailed |
| Networking | hollow-candidate | C9 | verify | netmanager | check each hollow body against AOSP<br>android.net.ConnectivityManager$NetworkCallback.onAvailable, android.net.ConnectivityManager$NetworkCallback.onCapabilitiesChanged, android.net.ConnectivityManager$NetworkCallback.onLinkPropertiesChanged |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.AsyncTask.onPostExecute, android.os.AsyncTask.onPreExecute, android.os.Binder.isBinderAlive |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.BaseAdapter.isEnabled, android.widget.TextView.onTextChanged |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.getAttributionTag, android.content.Context.isRestricted |
| Location | hollow-candidate | C9 | verify | location | check each hollow body against AOSP<br>android.location.GnssMeasurementsEvent$Callback.onGnssMeasurementsReceived, android.location.GnssMeasurementsEvent$Callback.onStatusChanged |
| Media | hollow-candidate | C9 | verify | multimedia | check each hollow body against AOSP<br>android.media.AudioTrack.getMaxVolume, android.media.AudioTrack.getMinVolume |
| Media store | hollow-candidate | C9 | verify | multimedia/media_library | check each hollow body against AOSP<br>android.provider.MediaStore.getPickImagesMaxLimit |
| Utilities | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.util.LruCache.entryRemoved |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| phone | inert | C4 | L | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>13 call sites, e.g. apptentive.com.android.feedback.platform.AndroidUtils.getTelephonyManager |
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>6 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.K0 `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1569` |
| camera | inert | C4 | M | multimedia/camera_framework | Android CameraManager facade over multimedia/camera_framework<br>7 call sites, e.g. androidx.camera.camera2.internal.compat.CameraManagerCompatBaseImpl.<init> |
| download | inert | C4 | M | miscservices/download_server | Android DownloadManager facade over miscservices/download_server<br>1 call sites, e.g. com.google.mlkit.common.sdkinternal.model.RemoteModelDownloadManager.<init> |
| jobscheduler | hollow | C9 | M | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>9 call sites, e.g. androidx.core.app.JobIntentService$JobWorkEnqueuer.<init> `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2088` |
| notification | hollow | C9 | M | notification (ANS) | replace the hollow binder with an implementation over notification (ANS)<br>28 call sites, e.g. androidx.browser.trusted.TrustedWebActivityService.onCreate `framework/android-runtime/src/AndroidRuntime.cpp:821` |
| sensor | inert | C4 | M | sensors | Android SensorManager facade over sensors<br>10 call sites, e.g. com.amplifyframework.devmenu.ShakeDetector.<init> |
| wifi | null | C4 | M | communication/wifi | Android WifiManager facade over communication/wifi<br>5 call sites, e.g. com.google.android.libraries.places.internal.zzeb.zza |
| appops | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. androidx.core.app.AppOpsManagerCompat$Api29Impl.c |
| batterymanager | null | C4 | S | powermgr/battery_manager | Android BatteryManager facade over powermgr/battery_manager<br>1 call sites, e.g. lib.android.paypal.com.magnessdk.i.x |
| biometric | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.biometric.BiometricManager$Api29Impl.b |
| dropbox | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. com.google.android.libraries.places.internal.zzkp.zza |
| fingerprint | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.core.hardware.fingerprint.FingerprintManagerCompat$Api23Impl.c |
| keyguard | null | C4 | S | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>3 call sites, e.g. androidx.biometric.KeyguardUtils$Api23Impl.a |
| locale | null | C5 | S | unmapped | truthful local manager (feature absent)<br>3 call sites, e.g. androidx.appcompat.app.AppCompatDelegate.T |
| servicediscovery | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. com.facebook.devicerequests.internal.DeviceRequestsHelper.cleanUpAdvertisementServiceImpl |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>8 call sites, e.g. androidx.core.os.UserManagerCompat$Api24Impl.a `framework/package-manager/java/OHUserManager.java:72` |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>3 call sites, e.g. androidx.compose.ui.platform.HapticDefaults.a |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper$Api26Impl.a `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>59 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>4 call sites, e.g. androidx.compose.ui.autofill.AndroidAutofill.<init> |
| credential | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>1 call sites, e.g. androidx.credentials.CredentialProviderFrameworkImpl.<init> |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>29 call sites, e.g. androidx.room.RoomDatabase$JournalMode.resolve$room_runtime_release |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>18 call sites, e.g. androidx.work.impl.background.systemalarm.Alarms.b |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>10 call sites, e.g. androidx.appcompat.widget.AppCompatReceiveContentHelper.b |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>37 call sites, e.g. androidx.work.impl.constraints.WorkConstraintsTrackerKt.a |
| display | supplied | C0 | verify | display_manager | none<br>5 call sites, e.g. androidx.camera.camera2.internal.DisplayInfoManager.<init> |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>29 call sites, e.g. androidx.activity.ImmLeaksCleaner.f `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>25 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| location | supplied | C0 | verify | location | none<br>14 call sites, e.g. androidx.appcompat.app.TwilightManager.a |
| power | supplied | C0 | verify | powermgr | none<br>11 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$AutoBatteryNightModeManager.<init> |
| uimode | supplied | C0 | verify | display / theme | none<br>19 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.E0 |
| window | supplied | C0 | verify | window_manager | none<br>33 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.O0 `framework/core/java/OHServiceManager.java:96` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| PackageManager.queryBroadcastReceivers | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1232` |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1225` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1253` |
| PackageManager.queryIntentServices | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1246` |
| PackageManager.resolveContentProvider | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1288` |
| PackageManager.resolveService | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1239` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1699` |
| PackageManager.getInstallSourceInfo | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1500` |
| PackageManager.getInstalledApplications | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1274` |
| PackageManager.getInstallerPackageName | stub | C9 | S | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1493` |
| PackageManager.getNameForUid | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1167` |
| PackageManager.getPackagesForUid | stub | C9 | S | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1158` |
| PackageManager.getPackagesHoldingPermissions | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1267` |
| PackageManager.getReceiverInfo | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1083` |
| PackageManager.getSystemAvailableFeatures | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1786` |
| PackageManager.getSystemSharedLibraryNames | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1779` |
| PackageManager.isSafeMode | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1806` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1687` |
| Content providers installed at bind (9, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>FileProvider, InitializationProvider, McdAppEngageHeroImageFileProvider, MlKitInitProvider@99, FirebaseInitProvider@100, FacebookInitProvider, SplitAppStartProvider@300, FTRHXContentProvider, AppStartContentProvider@100 — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>9 components carry meta-data (2 directBootAware, e.g. ComponentDiscoveryService, MlKitComponentDiscoveryService); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getReceiverInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

## Activity, window & process contracts

_what system_server would answer, answered in-process by Westlake in direct launch → white-box probes_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| WebView's renderer runs in an isolated service process | missing | C4 | L | process spawn (appspawn): an isolated Android service process with its own sandbox | host the renderer: spawn an isolated child and bind Chromium's SandboxedProcessService over a local channel; or build the framework with the update-service flag off so WebView runs single-process<br>app constructs WebViews and calls 38 WebView methods `frameworks-base/core/java/android/webkit/WebViewDelegate.java:215` |
| Dialogs stack above their activity's window, whatever the add order | missing | C6 | M | window_manager (sub-window z-order: creation order) | stack a base application window below the dialogs already attached to its token<br>app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added before the activity's own window `framework/window/java/WindowSessionAdapter.java:370` — probe: `probes/dialog-before-window` |
| Windows placed by LayoutParams gravity and x/y (dialogs centred) | missing | C6 | M | window_manager (session rect) | compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:346` — probe: `probes/dialog-before-window` |
| FLAG_DIM_BEHIND dims what is under a dialog | missing | C6 | M | render_service (a layer under the window) | draw a dim layer of dimAmount under the window (OH has no dim flag)<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:84` — probe: `probes/dialog-before-window` |
| ActivityManager process-table queries (getRunningAppProcesses, getRunningServices, getProcessMemoryInfo) | supplied | C0 | verify | none (the caller's own process is the answer) | answer with the caller's process: name, pid, uid, foreground importance, its package<br>app calls getRunningAppProcesses, getRunningServices, getProcessMemoryInfo `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1351` — probe: `probes/running-app-processes` |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libandroidx.graphics.path.so → 1 classes, 1 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/graphics/Path |
| libmlkit_google_ocr_pipeline.so → 3 classes, 2 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/os/Environment, java/io/File, java/lang/IllegalArgumentException |
| libpanorenderer.so → 36 classes, 213 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/content/Context, android/content/pm/PackageManager, android/content/res/Configuration, android/content/res/Resources |
| librealm-jni.so → 18 classes, 40 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/ArrayIndexOutOfBoundsException, java/lang/Boolean, java/lang/ClassNotFoundException, java/lang/Double |
| librealmc.so → 12 classes, 38 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/IOException, java/lang/ArithmeticException, java/lang/IllegalArgumentException, java/lang/IllegalStateException |
| libsqliteJni.so → 2 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/database/SQLException, java/lang/OutOfMemoryError |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libandroid: 13 symbols missing on the OH board | missing | C4 | M | OH NDK equivalents (ArkUI/graphic/resource manager) | NDK surface over OH equivalents<br>open: ANativeWindow_lock, ANativeWindow_unlockAndPost, ASensorEventQueue_disableSensor, ASensorEventQueue_enableSensor, ASensorEventQueue_getEvents, ASensorEventQueue_setEventRate, ASensorManager_createEventQueue, ASensorManager_destroyEventQueue |
| bionic-private (not in the NDK): 28 symbols missing on the OH board | missing | C1/C2 | S | OH musl / system libraries | bionic-ABI shim: forward or translate to musl<br>open: MallocExtension_Internal_GetNumericProperty, MallocExtension_Internal_MarkThreadBusy, MallocExtension_Internal_MarkThreadIdle, MallocExtension_Internal_ProcessBackgroundActions, _ZN25googledata_third_party_tz22zoneinfo_embedded_sizeEv, _ZN25googledata_third_party_tz24zoneinfo_embedded_createEv, _ZN25googledata_third_party_tz25zoneinfo_embedded_versionEv, _ZN4absl19leak_check_internal12DoIgnoreLeakEPKv |
| libc: 1 symbols missing on the OH board | missing | C1/C2 | S | OH musl / system libraries | bionic-ABI shim: forward or translate to musl<br>open: __system_property_read |
| libc calls carrying a constant each libc numbers differently (pathconf, sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>pathconf: 2 libraries, e.g. libba4e.so, libe448.so; sysconf: 8 libraries, e.g. libakamaibmp.so, libba4e.so, libe448.so `framework/webview-shim/webview_bionic_shim.c:1189` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Libraries mapped straight out of the APK (10 .so, extractNativeLibs=false) | supplied | C0 | verify | OH dynamic linker (cannot map zip!/ members: board test 2026-09-18) | extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too) `manifest/tools/prepare_app.py:75` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create fifo_file in app data | denied | C4 | OH | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | allow hap_domain normal_hap_data_file_attr:fifo_file { create read write open lock unlink map setattr getattr rename }; (no neverallow in hap_domain.te blocks it) \| bring-up workaround: label the staged app-data tree data_app_el2_file: kernel grants normal_hap dir/file/fifo_file/sock_file there (still no lnk_file)<br>librealm-jni.so:mkfifo, librealmc.so:mkfifo `sepolicy/ohos_policy/bundlemanager/bundle_framework/system/installs.te:199 allow hap_domain data_app_el2_file:fifo_file { create read write open lock unlink map setattr getattr rename }` |
| Create lnk_file in app data | denied | C5 | M | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>java.nio.file.Files:createSymbolicLink `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## External services & SDK behaviour

_SDKs that expect Google services or probe the device_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Google Play services | absent | C5 | M | none: no Google services on OH | decide per feature: truthful 'unavailable' result, or an OH-backed replacement (push, maps, auth)<br>application meta-data com.google.android.gms.version |
| Firebase component discovery (ComponentDiscoveryService) | partial | C5 | verify | none: no Google services on OH | component discovery is local (see pm:component-metadata); GMS-backed components degrade<br>com.google.firebase.components.ComponentDiscoveryService declares 11 registrars |
| Firebase component discovery (MlKitComponentDiscoveryService) | partial | C5 | verify | none: no Google services on OH | component discovery is local (see pm:component-metadata); GMS-backed components degrade<br>com.google.mlkit.common.internal.MlKitComponentDiscoveryService declares 3 registrars |
| Akamai Bot Manager | refused | C5 | verify | device identity & environment | confirm the app degrades cleanly without it, and whether its backend then rejects the session<br>libakamaibmp.so `framework/webview-shim/webview_bionic_shim.c:881` |
| Forter fraud SDK | environment-sensitive | CU | verify | device identity & environment | capture its inputs on the Android baseline; decide load/refuse and what identity to present<br>com.forter.forter3ds.view.ChallengeActivity, com.forter.mobile.fortersdk.providers.AppStartContentProvider, com.forter.mobile.fortersdk.providers.FTRHXContentProvider, com.forter.mobile.fortersdk.services.CaptchaTextToSpeechService |

## Limits of this map

- 54 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
