# com.mcdonalds.app 26.31.1 → OpenHarmony: API shim gap map

Provider: Westlake `jobscheduler-service-stub` @ `c279d162c1` (+9 uncommitted files); OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 35.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 25 | 25 | 14×verify, 7×S, 3×M, 1×L |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 33 | 23 | 1×verify, 10×S, 11×M, 1×L |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 21 | 19 | 1×verify, 12×S, 6×M |
| Native platform symbols | packaged .so imports → symbols exported on the OH board | 3 | 2 | 1×S, 1×L |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 1 | 0 | — |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 2 | 2 | 1×M, 1×OH |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 5 | 5 | 4×verify, 1×M |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Known blockers: status against this provider

Of 8 blockers already hit on the board: **5** closed per source (confirm on device), **2** open, **1** open (verify).

| Blocker | Symptom on device | Row | Status |
|---|---|---|---|
| B1 | 0 of 10 packaged libraries load: the OH linker cannot map lib/arm64-v8a/*.so out of the APK | `load:in-apk` (supplied) | closed per source (confirm on device) |
| B2 | libraries fail to link on bionic-only symbols (__sF, __pthread_cleanup_push, __system_property_foreach, isnan, ...) | `sym:bionic libc` (supplied) | closed per source (confirm on device) |
| B3 | libakamaibmp.so self-traps with an uncatchable SIGILL on load | `env:akamai-bot-manager` (refused) | open (verify) |
| B4 | getSystemService("jobscheduler") returns null; WorkManager NPE | `svc:jobscheduler` (hollow) | open |
| B5 | density-split drawables not found: split APKs invisible to resources | `pm:splits` (supplied) | closed per source (confirm on device) |
| B6 | LocationManager null on splash (AnalyticsHelper) | `svc:location` (supplied) | closed per source (confirm on device) |
| B7 | Realm: Failed to create fifo ... Permission denied (13) | `policy:fifo_file` (denied) | open |
| B8 | Firebase Instance ID component is not present (component discovery found no registrars) | `pm:component-metadata` (supplied) | closed per source (confirm on device) |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| WiFi | missing | C4 | L | communication/wifi | implement the members over communication/wifi<br>android.net.wifi.ScanResult.BSSID, android.net.wifi.ScanResult.SSID, android.net.wifi.ScanResult.capabilities |
| Networking | missing | C4 | M | netmanager | implement the members over netmanager<br>android.net.ConnectivityManager.getDefaultProxy, android.net.DhcpInfo, android.net.LinkAddress.getAddress |
| Network service discovery (mDNS) | missing | C4 | M | netmanager/mdns | implement the members over netmanager/mdns<br>android.net.nsd.NsdManager, android.net.nsd.NsdManager$DiscoveryListener, android.net.nsd.NsdManager$RegistrationListener |
| Media store | missing | C4 | M | multimedia/media_library | implement the members over multimedia/media_library<br>android.provider.MediaStore$Images$Media.EXTERNAL_CONTENT_URI, android.provider.MediaStore$Images$Media.getBitmap, android.provider.MediaStore$Images$Media.insertImage |
| Views & windows | missing | C4 | S | window_manager / render_service | implement the members over window_manager / render_service<br>android.view.View.setContentSensitivity, android.view.View.setFrameContentVelocity, android.view.inputmethod.EditorInfo.setStylusHandwritingEnabled |
| Java library | missing | C1/C5 | S | none (library code inside Westlake) | port from AOSP, or confirm the caller tolerates absence<br>java.lang.ClassLoader.getUnnamedModule |
| Bluetooth | missing | C4 | S | communication/bluetooth | implement the members over communication/bluetooth<br>android.bluetooth.BluetoothAdapter.getBondedDevices, android.bluetooth.BluetoothDevice.getAddress |
| Package manager | missing | C4 | S | bundle_framework | implement the members over bundle_framework<br>android.content.pm.SigningInfo.getPublicKeys, android.content.pm.SigningInfo.getSchemeVersion |
| Job scheduling | missing | C4 | S | resourceschedule/work_scheduler | implement the members over resourceschedule/work_scheduler<br>android.app.job.JobInfo$Builder.setTraceTag |
| Biometrics | missing | C4 | S | useriam | implement the members over useriam<br>android.hardware.biometrics.BiometricPrompt$CryptoObject.getOperationHandle |
| Text | missing | C1/C5 | S | none (library code inside Westlake) | port from AOSP, or confirm the caller tolerates absence<br>android.text.StaticLayout$Builder.setUseBoundsForWidth |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.Canvas.disableZ, android.graphics.Canvas.enableZ, android.graphics.Canvas.getMaximumBitmapHeight |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.ActionBar.setHomeActionContentDescription, android.app.ActionBar.setHomeAsUpIndicator, android.app.Activity.onActivityResult |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| WebView | hollow-candidate | C9 | verify | web (ArkWeb) or bundled Chromium | check each hollow body against AOSP<br>android.webkit.HttpAuthHandler.proceed, android.webkit.SslErrorHandler.cancel, android.webkit.SslErrorHandler.proceed |
| Camera | hollow-candidate | C9 | verify | multimedia/camera_framework | check each hollow body against AOSP<br>android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureBufferLost, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureCompleted, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureFailed |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.AsyncTask.onPostExecute, android.os.AsyncTask.onPreExecute, android.os.Binder.isBinderAlive |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.BaseAdapter.isEnabled, android.widget.TextView.onTextChanged |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.getAttributionTag, android.content.Context.isRestricted |
| Location | hollow-candidate | C9 | verify | location | check each hollow body against AOSP<br>android.location.GnssMeasurementsEvent$Callback.onGnssMeasurementsReceived, android.location.GnssMeasurementsEvent$Callback.onStatusChanged |
| Media | hollow-candidate | C9 | verify | multimedia | check each hollow body against AOSP<br>android.media.AudioTrack.getMaxVolume, android.media.AudioTrack.getMinVolume |
| Java extensions | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>javax.security.auth.Destroyable.isDestroyed |
| Utilities | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.util.LruCache.entryRemoved |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>No default CameraXConfig.Provider specified in meta-data. The most likely cause is you did not include a default implementation in your build such as 'camera-camera2'., androidx.window.extensions.WindowExtensions, androidx.window.extensions.WindowExtensionsProvider |
| Privacy Sandbox | probe-only | C8 | verify | none (library code inside Westlake) | confirm the probed class should (not) exist on this platform<br>android.adservices.measurement.MeasurementManager |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| phone | inert | C4 | L | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>13 call sites, e.g. apptentive.com.android.feedback.platform.AndroidUtils.getTelephonyManager |
| alarm | null | C4 | M | time_service / reminder_agent | Android AlarmManager facade over time_service / reminder_agent<br>18 call sites, e.g. androidx.work.impl.background.systemalarm.Alarms.b |
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>6 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.K0 `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1560` |
| camera | inert | C4 | M | multimedia/camera_framework | Android CameraManager facade over multimedia/camera_framework<br>7 call sites, e.g. androidx.camera.camera2.internal.compat.CameraManagerCompatBaseImpl.<init> |
| clipboard | null | C4 | M | miscservices/pasteboard | Android ClipboardManager facade over miscservices/pasteboard<br>10 call sites, e.g. androidx.appcompat.widget.AppCompatReceiveContentHelper.b |
| download | inert | C4 | M | miscservices/download_server | Android DownloadManager facade over miscservices/download_server<br>1 call sites, e.g. com.google.mlkit.common.sdkinternal.model.RemoteModelDownloadManager.<init> |
| jobscheduler | hollow | C9 | M | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>9 call sites, e.g. androidx.core.app.JobIntentService$JobWorkEnqueuer.<init> `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2079` |
| notification | hollow | C9 | M | notification (ANS) | replace the hollow binder with an implementation over notification (ANS)<br>28 call sites, e.g. androidx.browser.trusted.TrustedWebActivityService.onCreate `framework/android-runtime/src/AndroidRuntime.cpp:821` |
| sensor | inert | C4 | M | sensors | Android SensorManager facade over sensors<br>10 call sites, e.g. com.amplifyframework.devmenu.ShakeDetector.<init> |
| uimode | null | C4 | M | display / theme | Android UiModeManager facade over display / theme<br>19 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.E0 |
| user | hollow | C9 | M | account/os_account | replace the hollow binder with an implementation over account/os_account<br>8 call sites, e.g. androidx.core.os.UserManagerCompat$Api24Impl.a `framework/android-runtime/src/AndroidRuntime.cpp:821` |
| wifi | null | C4 | M | communication/wifi | Android WifiManager facade over communication/wifi<br>5 call sites, e.g. com.google.android.libraries.places.internal.zzeb.zza |
| appops | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. androidx.core.app.AppOpsManagerCompat$Api29Impl.c |
| batterymanager | null | C4 | S | powermgr/battery_manager | Android BatteryManager facade over powermgr/battery_manager<br>1 call sites, e.g. lib.android.paypal.com.magnessdk.i.x |
| biometric | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.biometric.BiometricManager$Api29Impl.b |
| dropbox | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. com.google.android.libraries.places.internal.zzkp.zza |
| fingerprint | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.core.hardware.fingerprint.FingerprintManagerCompat$Api23Impl.c |
| keyguard | null | C4 | S | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>3 call sites, e.g. androidx.biometric.KeyguardUtils$Api23Impl.a |
| locale | null | C5 | S | unmapped | truthful local manager (feature absent)<br>3 call sites, e.g. androidx.appcompat.app.AppCompatDelegate.T |
| power | null | C4 | S | powermgr | Android PowerManager facade over powermgr<br>11 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$AutoBatteryNightModeManager.<init> |
| servicediscovery | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. com.facebook.devicerequests.internal.DeviceRequestsHelper.cleanUpAdvertisementServiceImpl |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>3 call sites, e.g. androidx.compose.ui.platform.HapticDefaults.a |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper$Api26Impl.a `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>59 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>4 call sites, e.g. androidx.compose.ui.autofill.AndroidAutofill.<init> |
| credential | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>1 call sites, e.g. androidx.credentials.CredentialProviderFrameworkImpl.<init> |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>29 call sites, e.g. androidx.room.RoomDatabase$JournalMode.resolve$room_runtime_release |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>37 call sites, e.g. androidx.work.impl.constraints.WorkConstraintsTrackerKt.a |
| display | supplied | C0 | verify | display_manager | none<br>5 call sites, e.g. androidx.camera.camera2.internal.DisplayInfoManager.<init> |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>29 call sites, e.g. androidx.activity.ImmLeaksCleaner.f `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>25 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| location | supplied | C0 | verify | location | none<br>14 call sites, e.g. androidx.appcompat.app.TwilightManager.a |
| window | supplied | C0 | verify | window_manager | none<br>33 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.O0 `framework/core/java/OHServiceManager.java:96` |

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
| PackageManager.getPackagesHoldingPermissions | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1221` |
| PackageManager.getReceiverInfo | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1037` |
| PackageManager.getSystemAvailableFeatures | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1740` |
| PackageManager.getSystemSharedLibraryNames | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1733` |
| PackageManager.isSafeMode | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1760` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1641` |
| Content providers installed at bind (9, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>FileProvider, InitializationProvider, McdAppEngageHeroImageFileProvider, MlKitInitProvider@99, FirebaseInitProvider@100, FacebookInitProvider, SplitAppStartProvider@300, FTRHXContentProvider, AppStartContentProvider@100 — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>9 components carry meta-data (2 directBootAware, e.g. ComponentDiscoveryService, MlKitComponentDiscoveryService); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getReceiverInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |
| Split APKs visible to resources and class loading (3 splits) | supplied | C0 | verify | none (Westlake PM + asset manager) | populate splitNames/splitSourceDirs from the installed split set<br>config.arm64_v8a.apk, config.xxxhdpi.apk, config.en.apk `framework/package-manager/java/SplitApkResolver.java:115` — probe: `none yet (propose: split-resources)` |

## Native platform symbols

_packaged .so imports → symbols exported on the OH board_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libandroid: 17 symbols missing on the OH board | missing | C4 | L | OH NDK equivalents (ArkUI/graphic/resource manager) | NDK surface over OH equivalents<br>open: AAssetManager_fromJava, AAssetManager_open, AAsset_close, AAsset_getBuffer, AAsset_getLength, ALooper_pollAll, ASensorEventQueue_disableSensor, ASensorEventQueue_enableSensor |
| sysprop: 4 symbols missing on the OH board | missing | C1/C2 | S | OH musl / system libraries | bionic-ABI shim: forward or translate to musl<br>open: __system_property_read |
| bionic libc: 10 symbols missing on the OH board | supplied | C0 | none | OH musl / system libraries | bionic-ABI shim: forward or translate to musl |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Libraries mapped straight out of the APK (10 .so, extractNativeLibs=false) | supplied | C0 | verify | OH dynamic linker (cannot map zip!/ members: board test 2026-09-18) | extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too) `manifest/tools/prepare_app.py:73` |

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
| Akamai Bot Manager | refused | C5 | verify | device identity & environment | confirm the app degrades cleanly without it, and whether its backend then rejects the session<br>libakamaibmp.so `framework/webview-shim/webview_bionic_shim.c:875` |
| Forter fraud SDK | environment-sensitive | CU | verify | device identity & environment | capture its inputs on the Android baseline; decide load/refuse and what identity to present<br>com.forter.forter3ds.view.ChallengeActivity, com.forter.mobile.fortersdk.providers.AppStartContentProvider, com.forter.mobile.fortersdk.providers.FTRHXContentProvider, com.forter.mobile.fortersdk.services.CaptchaTextToSpeechService |

## Limits of this map

- 54 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'newer-than-reference': 23, 'absent-from-platform': 48}.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
