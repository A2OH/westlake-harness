# com.mcdonalds.app 26.31.1 → OpenHarmony: API shim gap map

Provider: Westlake `75d82d5 (before McDonald's bring-up)` @ `75d82d5 (b`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 35.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 17 | 17 | 16×verify, 1×S |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 33 | 24 | 1×verify, 10×S, 12×M, 1×L |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 21 | 20 | 1×verify, 13×S, 6×M |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 6 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 3 | 2 | 1×S, 1×M |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 1 | 1 | 1×S |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 2 | 2 | 1×M, 1×OH |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 5 | 5 | 4×verify, 1×M |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Gaps on the observed path: cold start to the sign-in screen, LineageOS 15 (no Google services, no network)

Recorded on real Android with full method tracing: 44451 methods executed (25957 of them the app's own), app libraries loaded: libakamaibmp.so, librealm-jni.so, librealmc.so.

**46 of the 71 open gaps were touched on this path; 25 were not.**

| Gap | Category | Verdict | Effort | How we know |
|---|---|---|---|---|
| Create fifo_file in app data | Process sandbox & policy | denied | OH | loaded: librealm-jni.so, librealmc.so |
| phone | System services | inert | L | 3 of 13 requesting methods ran; TelephonyManager code executed |
| Google Play services | External services & SDK behaviour | absent | M | 1979 of its methods executed |
| PackageManager.queryBroadcastReceivers | Package manager & manifest | stub | M | referenced |
| PackageManager.queryIntentContentProviders | Package manager & manifest | stub | M | executed |
| PackageManager.queryIntentServices | Package manager & manifest | stub | M | executed |
| PackageManager.resolveContentProvider | Package manager & manifest | stub | M | executed |
| alarm | System services | null | M | 1 of 18 requesting methods ran; AlarmManager code executed |
| audio | System services | hollow | M | 0 of 6 requesting methods ran; AudioManager code executed |
| camera | System services | inert | M | 0 of 7 requesting methods ran; CameraManager code executed |
| jobscheduler | System services | null | M | 2 of 9 requesting methods ran; JobScheduler code executed |
| location | System services | null | M | 2 of 14 requesting methods ran; LocationManager code executed |
| notification | System services | hollow | M | 1 of 28 requesting methods ran; NotificationManager code executed |
| sensor | System services | inert | M | 0 of 10 requesting methods ran; SensorManager code executed |
| uimode | System services | null | M | 1 of 19 requesting methods ran; UiModeManager code executed |
| user | System services | hollow | M | 1 of 8 requesting methods ran; UserManager code executed |
| wifi | System services | null | M | 0 of 5 requesting methods ran; WifiManager code executed |
| Java library | Java framework API | missing | S | 10 members executed, 0 more referenced by executed methods, of 44 |
| Libraries mapped straight out of the APK (10 .so, extractNativeLibs=false) | Native loading & packaging | missing | S | loaded: libakamaibmp.so, librealm-jni.so, librealmc.so |
| bionic libc ABI: 10 symbols to translate onto musl | Native platform symbols | missing | S | loaded: libakamaibmp.so |
| Component lookups return manifest <meta-data> | Package manager & manifest | missing | S | component lookups executed |
| PackageManager.getComponentEnabledSetting | Package manager & manifest | stub | S | executed |
| PackageManager.getInstalledApplications | Package manager & manifest | stub | S | executed |
| PackageManager.getInstallerPackageName | Package manager & manifest | stub | S | executed |
| PackageManager.getNameForUid | Package manager & manifest | stub | S | referenced |
| PackageManager.getPackagesForUid | Package manager & manifest | stub | S | referenced |
| PackageManager.getReceiverInfo | Package manager & manifest | stub | S | executed |
| PackageManager.setComponentEnabledSetting | Package manager & manifest | stub | S | executed |
| appops | System services | null | S | 1 of 2 requesting methods ran; AppOpsManager code executed |
| batterymanager | System services | null | S | 0 of 1 requesting methods ran; BatteryManager code executed |
| biometric | System services | null | S | 1 of 1 requesting methods ran; BiometricManager code executed |
| fingerprint | System services | null | S | 0 of 1 requesting methods ran; FingerprintManager code executed |
| locale | System services | null | S | 2 of 3 requesting methods ran; LocaleManager code executed |
| power | System services | null | S | 1 of 11 requesting methods ran; PowerManager code executed |
| Firebase component discovery (ComponentDiscoveryService) | External services & SDK behaviour | partial | verify | 153 of its methods executed |
| Firebase component discovery (MlKitComponentDiscoveryService) | External services & SDK behaviour | partial | verify | 28 of its methods executed |
| Akamai Bot Manager | External services & SDK behaviour | environment-sensitive | verify | libakamaibmp.so loaded |
| Forter fraud SDK | External services & SDK behaviour | environment-sensitive | verify | 310 of its methods executed |
| Views & windows | Java framework API | hollow-candidate | verify | 10 members executed, 0 more referenced by executed methods, of 73 |
| Graphics | Java framework API | hollow-candidate | verify | 4 members executed, 0 more referenced by executed methods, of 30 |
| App framework | Java framework API | hollow-candidate | verify | 7 members executed, 0 more referenced by executed methods, of 23 |
| OS services | Java framework API | hollow-candidate | verify | 1 members executed, 0 more referenced by executed methods, of 4 |
| Widgets | Java framework API | hollow-candidate | verify | 1 members executed, 0 more referenced by executed methods, of 3 |
| Content & intents | Java framework API | hollow-candidate | verify | 1 members executed, 0 more referenced by executed methods, of 2 |
| Content providers installed at bind (9, initOrder honoured) | Package manager & manifest | unverified | verify | done by the platform when the process is bound |
| textclassification | System services | unresolved | verify | 0 of 1 requesting methods ran; TextClassificationManager code executed |

"Touched" means the call ran, or a method containing the reference ran; it leans large, never small. A gap that was not touched can still matter for a later screen or feature.

## Backtest against failures already hit on the board

Against the provider state the app actually ran on, of 8 observed blockers: **6** predicted, **1** flagged for verification, **1** missed: row claimed supplied.

| Blocker | Symptom on device | Row | Outcome |
|---|---|---|---|
| B1 | 0 of 10 packaged libraries load: the OH linker cannot map lib/arm64-v8a/*.so out of the APK | `load:in-apk` (missing) | predicted |
| B2 | libraries fail to link on bionic-only symbols (__sF, __pthread_cleanup_push, __system_property_foreach, isnan, ...) | `ndk:libc-abi` (missing) | predicted |
| B3 | libakamaibmp.so self-traps with an uncatchable SIGILL on load | `env:akamai-bot-manager` (environment-sensitive) | flagged for verification |
| B4 | getSystemService("jobscheduler") returns null; WorkManager NPE | `svc:jobscheduler` (null) | predicted |
| B5 | density-split drawables not found: split APKs invisible to resources | `pm:splits` (supplied) | missed: row claimed supplied |
| B6 | LocationManager null on splash (AnalyticsHelper) | `svc:location` (null) | predicted |
| B7 | Realm: Failed to create fifo ... Permission denied (13) | `policy:fifo_file` (denied) | predicted |
| B8 | Firebase Instance ID component is not present (component discovery found no registrars) | `pm:component-metadata` (missing) | predicted |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | On path | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|---|
| Java library | missing | C1/C5 | S | yes | none (library code inside Westlake) | port from AOSP, or confirm the caller tolerates absence<br>java.lang.ClassLoader.getUnnamedModule |
| Views & windows | hollow-candidate | C9 | verify | yes | window_manager / render_service | check each hollow body against AOSP<br>android.view.ActionProvider.hasSubMenu, android.view.ActionProvider.isVisible, android.view.ActionProvider.onPerformDefaultAction |
| Graphics | hollow-candidate | C9 | verify | yes | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.Canvas.disableZ, android.graphics.Canvas.enableZ, android.graphics.Canvas.getMaximumBitmapHeight |
| App framework | hollow-candidate | C9 | verify | yes | ability_runtime | check each hollow body against AOSP<br>android.app.ActionBar.setHomeActionContentDescription, android.app.ActionBar.setHomeAsUpIndicator, android.app.Activity.onActivityResult |
| Other Android | hollow-candidate | C9 | verify | – | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| WebView | hollow-candidate | C9 | verify | – | web (ArkWeb) or bundled Chromium | check each hollow body against AOSP<br>android.webkit.HttpAuthHandler.proceed, android.webkit.SslErrorHandler.cancel, android.webkit.SslErrorHandler.proceed |
| Camera | hollow-candidate | C9 | verify | – | multimedia/camera_framework | check each hollow body against AOSP<br>android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureBufferLost, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureCompleted, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureFailed |
| Networking | hollow-candidate | C9 | verify | – | netmanager | check each hollow body against AOSP<br>android.net.ConnectivityManager$NetworkCallback.onAvailable, android.net.ConnectivityManager$NetworkCallback.onCapabilitiesChanged, android.net.ConnectivityManager$NetworkCallback.onLinkPropertiesChanged |
| OS services | hollow-candidate | C9 | verify | yes | various system abilities | check each hollow body against AOSP<br>android.os.AsyncTask.onPostExecute, android.os.AsyncTask.onPreExecute, android.os.Binder.isBinderAlive |
| Widgets | hollow-candidate | C9 | verify | yes | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.BaseAdapter.isEnabled, android.widget.TextView.onTextChanged |
| Content & intents | hollow-candidate | C9 | verify | yes | ability_runtime | check each hollow body against AOSP<br>android.content.Context.getAttributionTag, android.content.Context.isRestricted |
| Location | hollow-candidate | C9 | verify | – | location | check each hollow body against AOSP<br>android.location.GnssMeasurementsEvent$Callback.onGnssMeasurementsReceived, android.location.GnssMeasurementsEvent$Callback.onStatusChanged |
| Media | hollow-candidate | C9 | verify | – | multimedia | check each hollow body against AOSP<br>android.media.AudioTrack.getMaxVolume, android.media.AudioTrack.getMinVolume |
| Java extensions | hollow-candidate | C9 | verify | – | none (library code inside Westlake) | check each hollow body against AOSP<br>javax.security.auth.Destroyable.isDestroyed |
| Media store | hollow-candidate | C9 | verify | – | multimedia/media_library | check each hollow body against AOSP<br>android.provider.MediaStore.getPickImagesMaxLimit |
| Utilities | hollow-candidate | C9 | verify | – | none (library code inside Westlake) | check each hollow body against AOSP<br>android.util.LruCache.entryRemoved |
| Other | probe-only | C8 | verify | – | unmapped | confirm the probed class should (not) exist on this platform<br>No default CameraXConfig.Provider specified in meta-data. The most likely cause is you did not include a default implementation in your build such as 'camera-camera2'., androidx.window.extensions.WindowExtensions, androidx.window.extensions.WindowExtensionsProvider |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | On path | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|---|
| phone | inert | C4 | L | yes | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>13 call sites, e.g. apptentive.com.android.feedback.platform.AndroidUtils.getTelephonyManager |
| alarm | null | C4 | M | yes | time_service / reminder_agent | Android AlarmManager facade over time_service / reminder_agent<br>18 call sites, e.g. androidx.work.impl.background.systemalarm.Alarms.b |
| audio | hollow | C9 | M | yes | audio_framework | replace the hollow binder with an implementation over audio_framework<br>6 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.K0 `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1558` |
| camera | inert | C4 | M | yes | multimedia/camera_framework | Android CameraManager facade over multimedia/camera_framework<br>7 call sites, e.g. androidx.camera.camera2.internal.compat.CameraManagerCompatBaseImpl.<init> |
| clipboard | null | C4 | M | – | miscservices/pasteboard | Android ClipboardManager facade over miscservices/pasteboard<br>10 call sites, e.g. androidx.appcompat.widget.AppCompatReceiveContentHelper.b |
| download | inert | C4 | M | – | miscservices/download_server | Android DownloadManager facade over miscservices/download_server<br>1 call sites, e.g. com.google.mlkit.common.sdkinternal.model.RemoteModelDownloadManager.<init> |
| jobscheduler | null | C4 | M | yes | resourceschedule/work_scheduler | Android JobScheduler facade over resourceschedule/work_scheduler<br>9 call sites, e.g. androidx.core.app.JobIntentService$JobWorkEnqueuer.<init> |
| location | null | C4 | M | yes | location | Android LocationManager facade over location<br>14 call sites, e.g. androidx.appcompat.app.TwilightManager.a |
| notification | hollow | C9 | M | yes | notification (ANS) | replace the hollow binder with an implementation over notification (ANS)<br>28 call sites, e.g. androidx.browser.trusted.TrustedWebActivityService.onCreate `framework/android-runtime/src/AndroidRuntime.cpp:816` |
| sensor | inert | C4 | M | yes | sensors | Android SensorManager facade over sensors<br>10 call sites, e.g. com.amplifyframework.devmenu.ShakeDetector.<init> |
| uimode | null | C4 | M | yes | display / theme | Android UiModeManager facade over display / theme<br>19 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.E0 |
| user | hollow | C9 | M | yes | account/os_account | replace the hollow binder with an implementation over account/os_account<br>8 call sites, e.g. androidx.core.os.UserManagerCompat$Api24Impl.a `framework/android-runtime/src/AndroidRuntime.cpp:816` |
| wifi | null | C4 | M | yes | communication/wifi | Android WifiManager facade over communication/wifi<br>5 call sites, e.g. com.google.android.libraries.places.internal.zzeb.zza |
| appops | null | C5 | S | yes | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. androidx.core.app.AppOpsManagerCompat$Api29Impl.c |
| batterymanager | null | C4 | S | yes | powermgr/battery_manager | Android BatteryManager facade over powermgr/battery_manager<br>1 call sites, e.g. lib.android.paypal.com.magnessdk.i.x |
| biometric | null | C5 | S | yes | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.biometric.BiometricManager$Api29Impl.b |
| dropbox | null | C5 | S | – | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. com.google.android.libraries.places.internal.zzkp.zza |
| fingerprint | null | C5 | S | yes | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.core.hardware.fingerprint.FingerprintManagerCompat$Api23Impl.c |
| keyguard | null | C4 | S | – | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>3 call sites, e.g. androidx.biometric.KeyguardUtils$Api23Impl.a |
| locale | null | C5 | S | yes | unmapped | truthful local manager (feature absent)<br>3 call sites, e.g. androidx.appcompat.app.AppCompatDelegate.T |
| power | null | C4 | S | yes | powermgr | Android PowerManager facade over powermgr<br>11 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$AutoBatteryNightModeManager.<init> |
| servicediscovery | null | C5 | S | – | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. com.facebook.devicerequests.internal.DeviceRequestsHelper.cleanUpAdvertisementServiceImpl |
| vibrator | inert | C4 | S | – | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>3 call sites, e.g. androidx.compose.ui.platform.HapticDefaults.a |
| textclassification | unresolved | CU | verify | yes | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper$Api26Impl.a `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | yes | unmapped | none: the manager is written to run without its service<br>59 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| autofill | inert | C5 | none | yes | unmapped | none: the manager is written to run without its service<br>4 call sites, e.g. androidx.compose.ui.autofill.AndroidAutofill.<init> |
| credential | inert | C5 | none | – | unmapped | none: the manager is written to run without its service<br>1 call sites, e.g. androidx.credentials.CredentialProviderFrameworkImpl.<init> |
| activity | supplied | C0 | verify | yes | ability_runtime (AMS) | none<br>29 call sites, e.g. androidx.room.RoomDatabase$JournalMode.resolve$room_runtime_release |
| connectivity | supplied | C0 | verify | yes | netmanager (NetConnManager) | none<br>37 call sites, e.g. androidx.work.impl.constraints.WorkConstraintsTrackerKt.a |
| display | supplied | C0 | verify | yes | display_manager | none<br>5 call sites, e.g. androidx.camera.camera2.internal.DisplayInfoManager.<init> |
| input_method | supplied | C0 | verify | yes | inputmethod_framework | none<br>29 call sites, e.g. androidx.activity.ImmLeaksCleaner.f `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | yes | unmapped | none<br>25 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| window | supplied | C0 | verify | – | window_manager | none<br>33 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.O0 `framework/core/java/OHServiceManager.java:96` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | On path | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|---|
| PackageManager.queryBroadcastReceivers | stub | C9 | M | yes | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1177` |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | – | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1170` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | yes | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1198` |
| PackageManager.queryIntentServices | stub | C9 | M | yes | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1191` |
| PackageManager.resolveContentProvider | stub | C9 | M | yes | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1233` |
| PackageManager.resolveService | stub | C9 | M | – | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1184` |
| Component lookups return manifest <meta-data> | missing | C6 | S | yes | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>9 components carry meta-data (2 directBootAware, e.g. ComponentDiscoveryService, MlKitComponentDiscoveryService); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getReceiverInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java` — probe: `probes/service-metadata` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | yes | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1644` |
| PackageManager.getInstallSourceInfo | stub | C9 | S | – | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1445` |
| PackageManager.getInstalledApplications | stub | C9 | S | yes | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1219` |
| PackageManager.getInstallerPackageName | stub | C9 | S | yes | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1438` |
| PackageManager.getNameForUid | stub | C9 | S | yes | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1112` |
| PackageManager.getPackagesForUid | stub | C9 | S | yes | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1103` |
| PackageManager.getPackagesHoldingPermissions | stub | C9 | S | – | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1212` |
| PackageManager.getReceiverInfo | stub | C9 | S | yes | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1037` |
| PackageManager.getSystemAvailableFeatures | stub | C9 | S | – | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1731` |
| PackageManager.getSystemSharedLibraryNames | stub | C9 | S | – | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1724` |
| PackageManager.isSafeMode | stub | C9 | S | – | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1751` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | yes | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1632` |
| Content providers installed at bind (9, initOrder honoured) | unverified | CU | verify | yes | none | install every main-process provider in initOrder before Application.onCreate<br>FileProvider, InitializationProvider, McdAppEngageHeroImageFileProvider, MlKitInitProvider@99, FirebaseInitProvider@100, FacebookInitProvider, SplitAppStartProvider@300, FTRHXContentProvider, AppStartContentProvider@100 — probe: `probes/provider-manifest` |
| Split APKs visible to resources and class loading (3 splits) | supplied | C0 | verify | yes | none (Westlake PM + asset manager) | populate splitNames/splitSourceDirs from the installed split set<br>config.arm64_v8a.apk, config.xxxhdpi.apk, config.en.apk `framework/package-manager/java/SplitApkResolver.java:64` — probe: `none yet (propose: split-resources)` |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | On path | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|---|
| libandroidx.graphics.path.so → 1 classes, 1 members | supplied | C0 | none | – | through the Java framework | none<br>e.g. android/graphics/Path |
| libmlkit_google_ocr_pipeline.so → 3 classes, 2 members | supplied | C0 | none | – | through the Java framework | none<br>e.g. android/os/Environment, java/io/File, java/lang/IllegalArgumentException |
| libpanorenderer.so → 36 classes, 213 members | supplied | C0 | none | – | through the Java framework | none<br>e.g. android/content/Context, android/content/pm/PackageManager, android/content/res/Configuration, android/content/res/Resources |
| librealm-jni.so → 18 classes, 40 members | supplied | C0 | none | yes | through the Java framework | none<br>e.g. java/lang/ArrayIndexOutOfBoundsException, java/lang/Boolean, java/lang/ClassNotFoundException, java/lang/Double |
| librealmc.so → 12 classes, 38 members | supplied | C0 | none | yes | through the Java framework | none<br>e.g. java/io/IOException, java/lang/ArithmeticException, java/lang/IllegalArgumentException, java/lang/IllegalStateException |
| libsqliteJni.so → 2 classes, 0 members | supplied | C0 | none | – | through the Java framework | none<br>e.g. android/database/SQLException, java/lang/OutOfMemoryError |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | On path | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|---|
| NDK weld · sensors: 11 symbols | missing | C4 | M | – | sensors | AOSP NDK source above, sensors below<br>open: ASensorEventQueue_disableSensor, ASensorEventQueue_enableSensor, ASensorEventQueue_getEvents, ASensorEventQueue_setEventRate, ASensorManager_createEventQueue, ASensorManager_destroyEventQueue, ASensorManager_getDefaultSensor, ASensorManager_getInstance |
| bionic libc ABI: 10 symbols to translate onto musl | missing | C1/C2 | S | yes | OH musl libc | bionic-ABI shim: forward or translate; never ship a second libc<br>open: __get_h_errno, __pthread_cleanup_pop, __pthread_cleanup_push, __system_property_find_nth, __system_property_foreach, __system_property_read, isinf, isnan |
| 10 symbols provided since the import resolution was taken | supplied | C0 | none | yes |  | none |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | On path | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|---|
| Libraries mapped straight out of the APK (10 .so, extractNativeLibs=false) | missing | C3 | S | yes | OH dynamic linker (cannot map zip!/ members: board test 2026-09-18) | extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too) |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | On path | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|---|
| Create fifo_file in app data | denied | C4 | OH | yes | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | allow hap_domain normal_hap_data_file_attr:fifo_file { create read write open lock unlink map setattr getattr rename }; (no neverallow in hap_domain.te blocks it) \| bring-up workaround: label the staged app-data tree data_app_el2_file: kernel grants normal_hap dir/file/fifo_file/sock_file there (still no lnk_file)<br>librealm-jni.so:mkfifo, librealmc.so:mkfifo `sepolicy/ohos_policy/bundlemanager/bundle_framework/system/installs.te:199 allow hap_domain data_app_el2_file:fifo_file { create read write open lock unlink map setattr getattr rename }` |
| Create lnk_file in app data | denied | C5 | M | – | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>java.nio.file.Files:createSymbolicLink `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## External services & SDK behaviour

_SDKs that expect Google services or probe the device_

| Item | Verdict | Class | Effort | On path | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|---|
| Google Play services | absent | C5 | M | yes | none: no Google services on OH | decide per feature: truthful 'unavailable' result, or an OH-backed replacement (push, maps, auth)<br>application meta-data com.google.android.gms.version |
| Firebase component discovery (ComponentDiscoveryService) | partial | C5 | verify | yes | none: no Google services on OH | component discovery is local (see pm:component-metadata); GMS-backed components degrade<br>com.google.firebase.components.ComponentDiscoveryService declares 11 registrars |
| Firebase component discovery (MlKitComponentDiscoveryService) | partial | C5 | verify | yes | none: no Google services on OH | component discovery is local (see pm:component-metadata); GMS-backed components degrade<br>com.google.mlkit.common.internal.MlKitComponentDiscoveryService declares 3 registrars |
| Akamai Bot Manager | environment-sensitive | CU | verify | yes | device identity & environment | capture its inputs on the Android baseline; decide load/refuse and what identity to present<br>libakamaibmp.so |
| Forter fraud SDK | environment-sensitive | CU | verify | yes | device identity & environment | capture its inputs on the Android baseline; decide load/refuse and what identity to present<br>com.forter.forter3ds.view.ChallengeActivity, com.forter.mobile.fortersdk.providers.AppStartContentProvider, com.forter.mobile.fortersdk.providers.FTRHXContentProvider, com.forter.mobile.fortersdk.services.CaptchaTextToSpeechService |

## Limits of this map

- 54 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 46}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
