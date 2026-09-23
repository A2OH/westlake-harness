# com.kiloo.subwaysurf 3.69.1 → OpenHarmony: API shim gap map

Provider: Westlake `burgerking-startup-fixes` @ `02cbace7fb`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 36.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 17 | 17 | 16×verify, 1×S |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 40 | 24 | 5×verify, 14×S, 4×M, 1×L |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 1 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 18 | 16 | 1×verify, 9×S, 6×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 5 | 1 | 1×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 7 | 1 | 1×verify |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 4 | 3 | 1×S, 1×M, 1×L |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 0 | 0 | — |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 1 | 1 | 1×M |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 2 | 2 | 1×verify, 1×M |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Java library | missing | C1/C5 | S | none (library code inside Westlake) | port from AOSP, or confirm the caller tolerates absence<br>java.util.concurrent.ScheduledExecutorService.close |
| Views & windows | hollow-candidate | C9 | verify | window_manager / render_service | check each hollow body against AOSP<br>android.view.ActionMode.invalidateContentRect, android.view.ActionProvider.hasSubMenu, android.view.ActionProvider.isVisible |
| WebView | hollow-candidate | C9 | verify | web (ArkWeb) or bundled Chromium | check each hollow body against AOSP<br>android.webkit.SslErrorHandler.cancel, android.webkit.WebChromeClient.getDefaultVideoPoster, android.webkit.WebChromeClient.getVideoLoadingProgressView |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.ActionBar.getThemedContext, android.app.ActionBar.setHomeActionContentDescription, android.app.ActionBar.setHomeAsUpIndicator |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.AutoCompleteTextView.onFinishInflate, android.widget.Button.onDetachedFromWindow |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.Canvas.disableZ, android.graphics.Canvas.enableZ, android.graphics.Canvas.isHardwareAccelerated |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.AsyncTask.onPostExecute, android.os.AsyncTask.onPreExecute, android.os.Binder.isBinderAlive |
| Networking | hollow-candidate | C9 | verify | netmanager | check each hollow body against AOSP<br>android.net.ConnectivityManager$NetworkCallback.onAvailable, android.net.ConnectivityManager$NetworkCallback.onCapabilitiesChanged, android.net.ConnectivityManager$NetworkCallback.onLost |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.getAttributionSource, android.content.Context.getAttributionTag, android.content.Context.isRestricted |
| Job scheduling | hollow-candidate | C9 | verify | resourceschedule/work_scheduler | check each hollow body against AOSP<br>android.app.job.JobService.onCreate, android.app.job.JobService.onDestroy |
| Location | hollow-candidate | C9 | verify | location | check each hollow body against AOSP<br>android.location.GnssMeasurementsEvent$Callback.onGnssMeasurementsReceived, android.location.GnssMeasurementsEvent$Callback.onStatusChanged |
| Privacy Sandbox | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.adservices.AdServicesState.isAdServicesStateEnabled |
| Media | hollow-candidate | C9 | verify | multimedia | check each hollow body against AOSP<br>android.media.DrmInitData.getSchemeInitDataCount |
| Media store | hollow-candidate | C9 | verify | multimedia/media_library | check each hollow body against AOSP<br>android.provider.MediaStore.getPickImagesMaxLimit |
| Utilities | probe-only | C8 | verify | none (library code inside Westlake) | confirm the probed class should (not) exist on this platform<br>android.util.FtDeviceInfo, android.util.FtFeature |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>androidx.datastore.preferences.protobuf.DescriptorMessageInfoFactory, androidx.datastore.preferences.protobuf.Extension, androidx.datastore.preferences.protobuf.ExtensionRegistry |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| phone | inert | C4 | L | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>66 call sites, e.g. com.mbridge.msdk.advanced.common.NetWorkStateReceiver.onReceive |
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>78 call sites, e.g. android.support.v4.media.session.MediaSessionCompat$MediaSessionImplBase.<init> `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1569` |
| jobscheduler | hollow | C9 | M | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>10 call sites, e.g. androidx.core.app.JobIntentService$JobWorkEnqueuer.<init> `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2088` |
| notification | hollow | C9 | M | notification (ANS) | replace the hollow binder with an implementation over notification (ANS)<br>23 call sites, e.g. androidx.browser.trusted.TrustedWebActivityService.onCreate `framework/android-runtime/src/AndroidRuntime.cpp:821` |
| sensor | inert | C4 | M | sensors | Android SensorManager facade over sensors<br>20 call sites, e.g. androidx.media3.exoplayer.video.spherical.SphericalGLSurfaceView.<init> |
| appops | null | C5 | S | unmapped | truthful local manager (feature absent)<br>9 call sites, e.g. androidx.core.app.AppOpsManagerCompat$Api29Impl.getSystemService |
| batterymanager | null | C4 | S | powermgr/battery_manager | Android BatteryManager facade over powermgr/battery_manager<br>1 call sites, e.g. com.google.android.gms.internal.ads.zzexn.zzc |
| camera | inert | C4 | S | multimedia/camera_framework | Android CameraManager facade over multimedia/camera_framework<br>2 call sites, e.g. com.pgl.ssdk.x.b |
| download | inert | C4 | S | miscservices/download_server | Android DownloadManager facade over miscservices/download_server<br>2 call sites, e.g. com.google.android.gms.internal.ads.zzbyt.onClick |
| fingerprint | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. androidx.core.hardware.fingerprint.FingerprintManagerCompat$Api23Impl.getFingerprintManagerOrNull |
| grammatical_inflection | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.core.app.GrammaticalInflectionManagerCompat$Api34Impl.getGrammaticalInflectionManager |
| keyguard | null | C4 | S | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>16 call sites, e.g. com.fyber.inneractive.sdk.util.b0.a |
| locale | null | C5 | S | unmapped | truthful local manager (feature absent)<br>3 call sites, e.g. androidx.core.app.LocaleManagerCompat.getLocaleManagerForApplication |
| media_metrics | null | C5 | S | unmapped | truthful local manager (feature absent)<br>4 call sites, e.g. androidx.media3.exoplayer.analytics.MediaMetricsListener.create |
| servicediscovery | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites; Kotlin casts it non-null in 2 methods (e.g. com.facebook.devicerequests.internal.DeviceRequestsHelper.cleanUpAdvertisementServiceImpl, com.facebook.devicerequests.internal.DeviceRequestsHelper.startAdvertisementServiceImpl): a null answer throws there, it is not skipped |
| storagestats | null | C5 | S | unmapped | truthful local manager (feature absent)<br>4 call sites; Kotlin casts it non-null in 4 methods (e.g. com.inmobi.media.Y5.H, com.inmobi.media.Y5.J, com.inmobi.media.Y5.N): a null answer throws there, it is not skipped |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>3 call sites, e.g. androidx.core.os.UserManagerCompat$Api24Impl.isUserUnlocked `framework/package-manager/java/OHUserManager.java:72` |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>3 call sites, e.g. com.applovin.impl.q7.a |
| wifi | null | C4 | S | communication/wifi | Android WifiManager facade over communication/wifi<br>5 call sites; Kotlin casts it non-null in 1 methods (e.g. com.inmobi.media.Z4.a): a null answer throws there, it is not skipped |
| bluetooth | unresolved | CU | verify | communication/bluetooth | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. com.fyber.inneractive.sdk.serverapi.b.g `BluetoothFrameworkInitializer.java:100` |
| captioning | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>9 call sites; Kotlin casts it non-null in 1 methods (e.g. com.moloco.sdk.internal.services.m.c): a null answer throws there, it is not skipped `SystemServiceRegistry.java:337` |
| input | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. com.pgl.ssdk.y.b `SystemServiceRegistry.java:545` |
| print | unresolved | CU | verify | print_service | trace the helper's binder; then treat as null, inert or supplied<br>2 call sites, e.g. androidx.print.PrintHelper.printBitmap `SystemServiceRegistry.java:893` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper.getTextClassifier `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>14 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>2 call sites, e.g. androidx.compose.ui.autofill.AndroidAutofill.<init> |
| media_session | not-a-platform-service | C5 | none | none | none (null on Android too)<br>1 call sites, e.g. androidx.media.MediaSessionManagerImplApi28.<init> |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>48 call sites, e.g. androidx.core.content.pm.ShortcutManagerCompat.getIconDimensionInternal |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>8 call sites, e.g. androidx.work.impl.background.systemalarm.Alarms.cancelExactAlarm |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>10 call sites, e.g. androidx.appcompat.widget.AppCompatReceiveContentHelper.maybeHandleMenuActionViaPerformReceiveContent |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>98 call sites, e.g. com.mbridge.msdk.advanced.common.NetWorkStateReceiver.onReceive |
| display | supplied | C0 | verify | display_manager | none<br>23 call sites, e.g. androidx.core.content.ContextCompat$Api30Impl.getDisplayOrDefault |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>18 call sites, e.g. androidx.core.view.SoftwareKeyboardControllerCompat$Impl20.lambda$show$0 `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>5 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| location | supplied | C0 | verify | location | none<br>4 call sites, e.g. androidx.appcompat.app.TwilightManager.getInstance |
| power | supplied | C0 | verify | powermgr | none<br>36 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$AutoBatteryNightModeManager.<init> |
| shortcut | supplied | C0 | verify | unmapped | none<br>23 call sites, e.g. androidx.core.content.pm.ShortcutManagerCompat.addDynamicShortcuts |
| storage | supplied | C0 | verify | filemanagement/storage_service | none<br>5 call sites, e.g. com.inmobi.media.Y5.H |
| uimode | supplied | C0 | verify | display / theme | none<br>20 call sites, e.g. androidx.core.view.DisplayCompat.isTv |
| window | supplied | C0 | verify | window_manager | none<br>89 call sites, e.g. androidx.appcompat.widget.TooltipPopup.hide `framework/core/java/OHServiceManager.java:96` |

## Keystore & crypto providers

_JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Android keystore provider ("AndroidKeyStore") | supplied | C0 | verify | security/huks (OH Universal Keystore); keystore2 has no OH counterpart | install an "AndroidKeyStore" provider whose keys come from KeyGenParameterSpec and stay per app: software keys in app data (days), or OH HUKS for hardware-backed keys (weeks). A blocker wherever the app opens it at startup (secure storage, encrypted preferences, biometric crypto, attestation)<br>1 classes name it, e.g. Ld1/c;; calls KeyGenerator.getInstance("AES"), KeyStore.getInstance("AndroidKeyStore") `framework/core/java/SoftwareAndroidKeyStore.java:65` |

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
| PackageManager.getApplicationEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1712` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1699` |
| PackageManager.getInstallSourceInfo | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1500` |
| PackageManager.getInstalledApplications | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1274` |
| PackageManager.getInstallerPackageName | stub | C9 | S | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1493` |
| PackageManager.getNameForUid | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1167` |
| PackageManager.getPackagesForUid | stub | C9 | S | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1158` |
| PackageManager.getReceiverInfo | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1083` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1687` |
| Content providers installed at bind (15, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>FacebookContentProvider, PlayGamesInitProvider@99, AppLovinInitProvider@101, InMobiInitProvider, InitializationProvider, AudienceNetworkContentProvider, FirebaseInitProvider@100, MobileAdsInitProvider@100, BidMachineInitProvider@100, FacebookInitProvider, VungleProvider@102, IronsourceLifecycleProvider, LevelPlayActivityLifecycleProvider, NativeSharingContentProvider, PicassoProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>8 components carry meta-data (1 directBootAware, e.g. ComponentDiscoveryService); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getReceiverInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |
| Split APKs visible to resources and class loading (1 splits) | supplied | C0 | verify | none (Westlake PM + asset manager) | populate splitNames/splitSourceDirs from the installed split set<br>config.arm64_v8a.apk `framework/package-manager/java/SplitApkResolver.java:115` — probe: `none yet (propose: split-resources)` |

## Activity, window & process contracts

_what system_server would answer, answered in-process by Westlake in direct launch → white-box probes_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| WebView's renderer runs in an isolated service process | missing | C4 | L | process spawn (appspawn): an isolated Android service process with its own sandbox | host the renderer: spawn an isolated child and bind Chromium's SandboxedProcessService over a local channel; or build the framework with the update-service flag off so WebView runs single-process<br>app constructs WebViews and calls 82 WebView methods `frameworks-base/core/java/android/webkit/WebViewDelegate.java:215` |
| ActivityManager process-table queries (getRunningAppProcesses) | supplied | C0 | verify | none (the caller's own process is the answer) | answer with the caller's process: name, pid, uid, foreground importance, its package<br>app calls getRunningAppProcesses `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1351` — probe: `probes/running-app-processes` |
| Dialogs stack above their activity's window, whatever the add order | supplied | C0 | verify | window_manager (sub-window z-order: creation order) | stack a base application window below the dialogs already attached to its token<br>app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added before the activity's own window `framework/window/java/WindowSessionAdapter.java:370` — probe: `probes/dialog-before-window` |
| Windows placed by LayoutParams gravity and x/y (dialogs centred) | supplied | C0 | verify | window_manager (session rect) | compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:346` — probe: `probes/dialog-before-window` |
| FLAG_DIM_BEHIND dims what is under a dialog | supplied | C0 | verify | render_service (a layer under the window) | draw a dim layer of dimAmount under the window (OH has no dim flag)<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:84` — probe: `probes/dialog-before-window` |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libunity.so → 145 classes, 1314 members | hollow-candidate | C9 | verify | ability_runtime, location | compare the constant bodies with AOSP<br>android.app.Presentation.onDisplayRemoved()V, android.app.Presentation.onDisplayChanged()V, android.location.LocationListener.onFlushComplete(I)V, android.location.LocationListener.onStatusChanged(Ljava/lang/String;ILandroid/os/Bundle;)V, android.location.LocationListener.onProviderEnabled(Ljava/lang/String;)V, android.location.LocationListener.onProviderDisabled(Ljava/lang/String;)V |
| libFirebaseCppApp-12_10_1.so → 40 classes, 320 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/app/Activity, android/content/ContentResolver, android/content/Context, android/content/Intent |
| libdatastore_shared_counter.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/IOException |
| libil2cpp.so → 2 classes, 3 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/System, java/util/Locale |
| libtt_ugen_layout.so → 2 classes, 4 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/IllegalStateException, java/lang/RuntimeException |
| libunitycoherencenative.so → 4 classes, 8 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Boolean, java/lang/ClassLoader, java/lang/Double, java/lang/Long |
| libvkquality.so → 5 classes, 8 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/app/ActivityThread, android/content/Context, android/content/pm/FeatureInfo, android/content/pm/PackageManager |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| NDK weld · media: 41 symbols | missing | C4 | L | multimedia/av_codec + player_framework | AOSP NDK source above, multimedia/av_codec + player_framework below<br>open: AMEDIAFORMAT_KEY_CHANNEL_COUNT, AMEDIAFORMAT_KEY_COLOR_FORMAT, AMEDIAFORMAT_KEY_DURATION, AMEDIAFORMAT_KEY_FRAME_RATE, AMEDIAFORMAT_KEY_HEIGHT, AMEDIAFORMAT_KEY_LANGUAGE, AMEDIAFORMAT_KEY_MIME, AMEDIAFORMAT_KEY_SAMPLE_RATE |
| NDK weld · sensors: 15 symbols | missing | C4 | M | sensors | AOSP NDK source above, sensors below<br>open: ASensorEventQueue_disableSensor, ASensorEventQueue_enableSensor, ASensorEventQueue_getEvents, ASensorEventQueue_hasEvents, ASensorEventQueue_setEventRate, ASensorManager_createEventQueue, ASensorManager_destroyEventQueue, ASensorManager_getDefaultSensor |
| bionic libc ABI: 3 symbols to translate onto musl | missing | C1/C2 | S | OH musl libc | bionic-ABI shim: forward or translate; never ship a second libc<br>open: __system_property_read, __libc_init, sys_signame |
| libc calls carrying a constant each libc numbers differently (sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>sysconf: 6 libraries, e.g. libFirebaseCppApp-12_10_1.so, libapplovin-native-crash-reporter.so, libcrashlytics-common.so `framework/webview-shim/webview_bionic_shim.c:1189` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create lnk_file in app data | denied | C5 | M | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>java.nio.file.Files:createSymbolicLink, libil2cpp.so:symlink, libunity.so:symlink `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## External services & SDK behaviour

_SDKs that expect Google services or probe the device_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Google Play services | absent | C5 | M | none: no Google services on OH | decide per feature: truthful 'unavailable' result, or an OH-backed replacement (push, maps, auth)<br>application meta-data com.google.android.gms.version |
| Firebase component discovery (ComponentDiscoveryService) | partial | C5 | verify | none: no Google services on OH | component discovery is local (see pm:component-metadata); GMS-backed components degrade<br>com.google.firebase.components.ComponentDiscoveryService declares 13 registrars |

## Limits of this map

- 23 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 2, 'newer-than-reference': 3}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
