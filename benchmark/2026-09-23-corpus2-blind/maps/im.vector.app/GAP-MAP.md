# im.vector.app 1.6.62 → OpenHarmony: API shim gap map

Provider: Westlake `provider-authority-resolution` @ `0b5c9af4ce`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 35.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 17 | 17 | 16×verify, 1×S |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 39 | 24 | 5×verify, 11×S, 8×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 1 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 11 | 10 | 1×verify, 4×S, 5×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 5 | 1 | 1×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 13 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 2 | 1 | 1×verify |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 2 | 2 | 1×verify, 1×XS |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 2 | 2 | 1×M, 1×OH |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 0 | 0 | — |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Java library | missing | C1/C5 | S | none (library code inside Westlake) | port from AOSP, or confirm the caller tolerates absence<br>java.lang.reflect.Constructor.getAnnotatedParameterTypes, java.lang.reflect.Constructor.getAnnotatedReturnType, java.lang.reflect.Method.getAnnotatedParameterTypes |
| Views & windows | hollow-candidate | C9 | verify | window_manager / render_service | check each hollow body against AOSP<br>android.view.ActionProvider.hasSubMenu, android.view.ActionProvider.isVisible, android.view.ActionProvider.onPerformDefaultAction |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.AutoCompleteTextView.onFinishInflate, android.widget.Button.onTextChanged |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.Canvas.disableZ, android.graphics.Canvas.enableZ, android.graphics.Canvas.getMaximumBitmapHeight |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.ActionBar.getThemedContext, android.app.ActionBar.setHomeActionContentDescription, android.app.ActionBar.setHomeAsUpIndicator |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| WebView | hollow-candidate | C9 | verify | web (ArkWeb) or bundled Chromium | check each hollow body against AOSP<br>android.webkit.HttpAuthHandler.proceed, android.webkit.SslErrorHandler.cancel, android.webkit.SslErrorHandler.proceed |
| Networking | hollow-candidate | C9 | verify | netmanager | check each hollow body against AOSP<br>android.net.ConnectivityManager$NetworkCallback.onAvailable, android.net.ConnectivityManager$NetworkCallback.onCapabilitiesChanged, android.net.ConnectivityManager$NetworkCallback.onLost |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.AsyncTask.onPostExecute, android.os.Handler.handleMessage, android.os.IBinder.getSuggestedMaxIpcSizeBytes |
| Job scheduling | hollow-candidate | C9 | verify | resourceschedule/work_scheduler | check each hollow body against AOSP<br>android.app.job.JobService.onCreate, android.app.job.JobService.onDestroy |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.getAttributionTag, android.content.Context.isRestricted |
| Camera | hollow-candidate | C9 | verify | multimedia/camera_framework | check each hollow body against AOSP<br>android.hardware.camera2.CameraManager$AvailabilityCallback.onCameraAccessPrioritiesChanged, android.hardware.camera2.CameraManager$AvailabilityCallback.onCameraUnavailable |
| Location | hollow-candidate | C9 | verify | location | check each hollow body against AOSP<br>android.location.GnssMeasurementsEvent$Callback.onGnssMeasurementsReceived, android.location.GnssMeasurementsEvent$Callback.onStatusChanged |
| Media | hollow-candidate | C9 | verify | multimedia | check each hollow body against AOSP<br>android.media.AudioTrack.getMaxVolume, android.media.DrmInitData.getSchemeInitDataCount |
| Media store | hollow-candidate | C9 | verify | multimedia/media_library | check each hollow body against AOSP<br>android.provider.MediaStore.getPickImagesMaxLimit |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>androidx.datastore.preferences.protobuf.DescriptorMessageInfoFactory, androidx.datastore.preferences.protobuf.Extension, androidx.datastore.preferences.protobuf.ExtensionRegistry |
| Java extensions | probe-only | C8 | verify | none (library code inside Westlake) | confirm the probed class should (not) exist on this platform<br>javax.xml.bind.DatatypeConverter |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>29 call sites, e.g. android.support.v4.media.session.MediaSessionCompat$MediaSessionImplBase.<init> `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1599` |
| camera | inert | C4 | M | multimedia/camera_framework | Android CameraManager facade over multimedia/camera_framework<br>9 call sites, e.g. com.learnium.RNDeviceInfo.RNDeviceModule.isCameraPresentSync |
| jobscheduler | hollow | C9 | M | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>5 call sites, e.g. androidx.core.app.JobIntentService$JobWorkEnqueuer.<init> `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2118` |
| keyguard | null | C4 | M | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>5 call sites, e.g. androidx.biometric.KeyguardUtils$Api23Impl.getKeyguardManager |
| notification | hollow | C9 | M | notification (ANS) | replace the hollow binder with an implementation over notification (ANS)<br>30 call sites, e.g. androidx.browser.trusted.TrustedWebActivityService.onAreNotificationsEnabled `framework/android-runtime/src/AndroidRuntime.cpp:821` |
| phone | inert | C4 | M | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>5 call sites, e.g. androidx.media3.common.util.NetworkTypeObserver$Api31.disambiguate4gAnd5gNsa |
| sensor | inert | C4 | M | sensors | Android SensorManager facade over sensors<br>6 call sites, e.g. androidx.media3.exoplayer.video.spherical.SphericalGLSurfaceView.<init> |
| wifi | null | C4 | M | communication/wifi | Android WifiManager facade over communication/wifi<br>3 call sites, e.g. androidx.media3.exoplayer.WifiLockManager.setEnabled |
| biometric | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.biometric.BiometricManager$Api29Impl.create |
| download | inert | C4 | S | miscservices/download_server | Android DownloadManager facade over miscservices/download_server<br>3 call sites, e.g. com.reactnativecommunity.webview.RNCWebViewModuleImpl.downloadFile |
| fingerprint | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. androidx.core.hardware.fingerprint.FingerprintManagerCompat$Api23Impl.getFingerprintManagerOrNull |
| grammatical_inflection | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.core.app.GrammaticalInflectionManagerCompat$Api34Impl.getGrammaticalInflectionManager |
| media_metrics | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.media3.exoplayer.analytics.MediaMetricsListener.create |
| media_projection | inert | C5 | S | unmapped | truthful local manager (feature absent)<br>3 call sites, e.g. com.oney.WebRTCModule.GetUserMediaImpl.getDisplayMedia |
| restrictions | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. im.vector.app.features.mdm.DefaultMdmService.<init> |
| telecom | inert | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. org.jitsi.meet.sdk.RNConnectionService.startCall |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>1 call sites, e.g. androidx.core.os.UserManagerCompat$Api24Impl.isUserUnlocked `framework/package-manager/java/OHUserManager.java:82` |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>3 call sites, e.g. com.facebook.react.modules.vibration.VibrationModule.getVibrator |
| wifip2p | null | C4 | S | communication/wifi (p2p) | Android WifiP2pManager facade over communication/wifi (p2p)<br>1 call sites, e.g. org.webrtc.NetworkMonitorAutoDetect$WifiDirectManagerDelegate.<init> |
| bluetooth | unresolved | CU | verify | communication/bluetooth | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. im.vector.app.features.call.audio.API21AudioDeviceDetector.start `BluetoothFrameworkInitializer.java:100` |
| captioning | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>4 call sites, e.g. androidx.media3.common.TrackSelectionParameters$Builder.setPreferredTextLanguageAndRoleFlagsToCaptioningManagerSettings `SystemServiceRegistry.java:337` |
| print | unresolved | CU | verify | print_service | trace the helper's binder; then treat as null, inert or supplied<br>2 call sites, e.g. androidx.print.PrintHelper.printBitmap `SystemServiceRegistry.java:893` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper$Api26Impl.getTextClassifier `SystemServiceRegistry.java:413` |
| vibrator_manager | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. com.facebook.react.modules.vibration.VibrationModule.getVibrator `SystemServiceRegistry.java:796` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>21 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| media_session | not-a-platform-service | C5 | none | none | none (null on Android too)<br>2 call sites, e.g. androidx.media.MediaSessionManagerImplApi28.<init> |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>18 call sites, e.g. androidx.core.content.pm.ShortcutManagerCompat.getIconDimensionInternal |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>6 call sites, e.g. androidx.work.impl.background.systemalarm.Alarms.cancelExactAlarm |
| appops | supplied | C0 | verify | unmapped | none<br>6 call sites, e.g. androidx.core.app.AppOpsManagerCompat$Api29Impl.getSystemService |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>10 call sites, e.g. androidx.appcompat.widget.AppCompatReceiveContentHelper.maybeHandleMenuActionViaPerformReceiveContent |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>17 call sites, e.g. androidx.media3.common.util.NetworkTypeObserver.getNetworkTypeFromConnectivityManager |
| display | supplied | C0 | verify | display_manager | none<br>8 call sites, e.g. androidx.core.content.ContextCompat$Api30Impl.getDisplayOrDefault |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>24 call sites, e.g. androidx.activity.ImmLeaksCleaner.onStateChanged `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>115 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| locale | supplied | C0 | verify | unmapped | none<br>5 call sites, e.g. androidx.appcompat.app.AppCompatDelegate.getLocaleManagerForApplication |
| location | supplied | C0 | verify | location | none<br>5 call sites, e.g. androidx.appcompat.app.TwilightManager.getInstance |
| power | supplied | C0 | verify | powermgr | none<br>14 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$AutoBatteryNightModeManager.<init> |
| uimode | supplied | C0 | verify | display / theme | none<br>10 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.mapNightMode |
| window | supplied | C0 | verify | window_manager | none<br>35 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.closePanel `framework/core/java/OHServiceManager.java:96` |

## Keystore & crypto providers

_JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Android keystore provider ("AndroidKeyStore") | supplied | C0 | verify | security/huks (OH Universal Keystore); keystore2 has no OH counterpart | install an "AndroidKeyStore" provider whose keys come from KeyGenParameterSpec and stay per app: software keys in app data (days), or OH HUKS for hardware-backed keys (weeks). A blocker wherever the app opens it at startup (secure storage, encrypted preferences, biometric crypto, attestation)<br>5 classes name it, e.g. Landroidx/biometric/CryptoObjectUtils;, Lim/vector/app/features/pin/lockscreen/crypto/migrations/LegacyPinCodeMigrator;, Lim/vector/app/features/pin/lockscreen/di/LockScreenModule;, Lorg/matrix/android/sdk/api/securestorage/SecretStoringUtils;; calls Cipher.getInstance("RSA/ECB/PKCS1Padding"), KeyGenerator.getInstance("AES"), KeyPairGenerator.getInstance("RSA"), KeyStore.getInstance("AndroidKeyStore") `framework/core/java/SoftwareAndroidKeyStore.java:65` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| PackageManager.queryBroadcastReceivers | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1232` |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1225` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1253` |
| PackageManager.queryIntentServices | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1246` |
| PackageManager.resolveService | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1239` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1727` |
| PackageManager.getInstallerPackageName | stub | C9 | S | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1521` |
| PackageManager.getSystemAvailableFeatures | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1814` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1715` |
| Content providers installed at bind (9, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>InitializationProvider, FileProvider, MatrixSDKFileProvider, MultiPickerFileProvider, RNCWebViewFileProvider, StartTimeProvider@200, SentryInitProvider, SentryPerformanceProvider@200, JLatexMathInitProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>9 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

## Activity, window & process contracts

_what system_server would answer, answered in-process by Westlake in direct launch → white-box probes_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| WebView's renderer runs in an isolated service process | missing | C4 | L | process spawn (appspawn): an isolated Android service process with its own sandbox | host the renderer: spawn an isolated child and bind Chromium's SandboxedProcessService over a local channel; or build the framework with the update-service flag off so WebView runs single-process<br>app constructs WebViews and calls 52 WebView methods `frameworks-base/core/java/android/webkit/WebViewDelegate.java:215` |
| ActivityManager process-table queries (getRunningAppProcesses, getProcessMemoryInfo) | supplied | C0 | verify | none (the caller's own process is the answer) | answer with the caller's process: name, pid, uid, foreground importance, its package<br>app calls getRunningAppProcesses, getProcessMemoryInfo `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1381` — probe: `probes/running-app-processes` |
| Dialogs stack above their activity's window, whatever the add order | supplied | C0 | verify | window_manager (sub-window z-order: creation order) | stack a base application window below the dialogs already attached to its token<br>app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added before the activity's own window `framework/window/java/WindowSessionAdapter.java:370` — probe: `probes/dialog-before-window` |
| Windows placed by LayoutParams gravity and x/y (dialogs centred) | supplied | C0 | verify | window_manager (session rect) | compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:346` — probe: `probes/dialog-before-window` |
| FLAG_DIM_BEHIND dims what is under a dialog | supplied | C0 | verify | render_service (a layer under the window) | draw a dim layer of dimAmount under the window (OH has no dim flag)<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:84` — probe: `probes/dialog-before-window` |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libfbjni.so → 12 classes, 56 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/os/Build$VERSION, java/io/IOException, java/lang/ArrayIndexOutOfBoundsException, java/lang/NullPointerException |
| libhermes.so → 9 classes, 39 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Boolean, java/lang/ClassCastException, java/lang/Double, java/lang/Integer |
| libimagepipeline.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/RuntimeException |
| libjingle_peerconnection_so.so → 12 classes, 35 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Boolean, java/lang/ClassLoader, java/lang/Double, java/lang/Enum |
| lib/arm64-v8a/libjnidispatch.so → 28 classes, 116 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Boolean, java/lang/Byte, java/lang/Character, java/lang/Class |
| libjsctooling.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/NullPointerException |
| libmaplibre.so → 26 classes, 126 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/graphics/Bitmap, android/graphics/Bitmap$Config, android/graphics/BitmapFactory, android/graphics/PointF |
| libnative-filters.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/RuntimeException |
| libnative-imagetranscoder.so → 3 classes, 4 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/InputStream, java/io/OutputStream, java/lang/RuntimeException |
| libreactnative.so → 17 classes, 79 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Boolean, java/lang/Class, java/lang/ClassCastException, java/lang/Double |
| librealm-jni.so → 18 classes, 40 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/ArrayIndexOutOfBoundsException, java/lang/Boolean, java/lang/ClassNotFoundException, java/lang/Double |
| librnscreens.so → 1 classes, 1 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Integer |
| librnworklets.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/NullPointerException |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Library the APK needs but does not ship (libjsc.so): 55 symbols | missing | CU | verify | none: neither Android's NDK nor OH provides it | a blocker only if an importer is loaded: on Android too its load fails without the library; check which code path loads it<br>open: JSClassCreate, JSContextGetGlobalObject, JSEvaluateScript, JSGlobalContextCreateInGroup, JSGlobalContextRelease, JSGlobalContextRetain, JSObjectCallAsConstructor, JSObjectCallAsFunction |
| libc calls carrying a constant each libc numbers differently (pathconf, sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>pathconf: 1 libraries, e.g. libc++_shared.so; sysconf: 7 libraries, e.g. libc++_shared.so, libjingle_peerconnection_so.so, libjnidispatch.so `framework/webview-shim/webview_bionic_shim.c:1308` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Packaged libraries a board library of the same name shadows (libc++_shared.so) | missing | C3 | XS | OH dynamic linker search order: /system/lib64/libc++_shared.so comes before the app's library directory | load these 9 libraries in the isolated Android namespace so DT_NEEDED picks the APK's copy (e.g. NDK libc++_shared is std::__ndk1; OH's is not): libc++_shared.so libfbjni.so libhermes.so libhermestooling.so libjsctooling.so libjsi.so libreactnative.so librnscreens.so librnworklets.so<br>9 APK libraries reach them through DT_NEEDED `manifest/tools/probe_source_app.py:44` |
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create fifo_file in app data | denied | C4 | OH | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | allow hap_domain normal_hap_data_file_attr:fifo_file { create read write open lock unlink map setattr getattr rename }; (no neverallow in hap_domain.te blocks it) \| bring-up workaround: label the staged app-data tree data_app_el2_file: kernel grants normal_hap dir/file/fifo_file/sock_file there (still no lnk_file)<br>librealm-jni.so:mkfifo `sepolicy/ohos_policy/bundlemanager/bundle_framework/system/installs.te:199 allow hap_domain data_app_el2_file:fifo_file { create read write open lock unlink map setattr getattr rename }` |
| Create lnk_file in app data | denied | C5 | M | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>java.nio.file.Files:createSymbolicLink, libc++_shared.so:symlink, libjsi.so:symlink, libreactnative.so:symlink `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## Limits of this map

- 13 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 104}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
