# org.mozilla.firefox 156.0 → OpenHarmony: API shim gap map

Provider: Westlake `burgerking-startup-fixes` @ `02cbace7fb`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 37.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 11 | 11 | 9×verify, 1×S, 1×M |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 37 | 21 | 5×verify, 10×S, 6×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 1 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 16 | 14 | 1×verify, 6×S, 6×M, 1×L |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 4 | 0 | — |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 7 | 1 | 1×verify |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 6 | 5 | 2×S, 2×M, 1×L |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 1 | 0 | — |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 2 | 2 | 1×M, 1×OH |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 2 | 2 | 1×verify, 1×M |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | missing | C4 | M | window_manager / render_service | implement the members over window_manager / render_service<br>android.view.accessibility.AccessibilityEvent.getTextChangeTypes, android.view.accessibility.AccessibilityEvent.setTextChangeTypes, android.view.accessibility.AccessibilityNodeInfo$AccessibilityAction.ACTION_SET_EXTENDED_SELECTION |
| App framework | missing | C4 | S | ability_runtime | implement the members over ability_runtime<br>android.app.Notification$Action$Builder.setEmphasisHint, android.app.Notification$Action$Builder.setStyleHint |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.Canvas.disableZ, android.graphics.Canvas.enableZ, android.graphics.Canvas.getMaximumBitmapHeight |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayInputStream.close, java.io.ByteArrayOutputStream.close, java.io.InputStream.available |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| Networking | hollow-candidate | C9 | verify | netmanager | check each hollow body against AOSP<br>android.net.ConnectivityManager$NetworkCallback.onAvailable, android.net.ConnectivityManager$NetworkCallback.onCapabilitiesChanged, android.net.ConnectivityManager$NetworkCallback.onLost |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.getAttributionSource, android.content.Context.getAttributionTag, android.content.Context.isRestricted |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.Binder.isBinderAlive, android.os.Handler.handleMessage, android.os.IBinder.getSuggestedMaxIpcSizeBytes |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.TextView.onTextChanged |
| Media store | hollow-candidate | C9 | verify | multimedia/media_library | check each hollow body against AOSP<br>android.provider.MediaStore.getPickImagesMaxLimit |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>androidx.datastore.preferences.protobuf.DescriptorMessageInfoFactory, androidx.datastore.preferences.protobuf.ExtensionRegistry, androidx.datastore.preferences.protobuf.ExtensionSchemaFull |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>9 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.dispatchKeyEvent `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1569` |
| jobscheduler | hollow | C9 | M | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>4 call sites, e.g. androidx.work.impl.WorkManagerImpl$$ExternalSyntheticLambda0.invoke `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2088` |
| keyguard | null | C4 | M | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>12 call sites, e.g. androidx.biometric.KeyguardUtils$Api23Impl.getKeyguardManager |
| notification | hollow | C9 | M | notification (ANS) | replace the hollow binder with an implementation over notification (ANS)<br>25 call sites, e.g. androidx.core.app.NotificationManagerCompat.<init> `framework/android-runtime/src/AndroidRuntime.cpp:821` |
| phone | inert | C4 | M | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>5 call sites, e.g. androidx.media3.common.util.NetworkTypeObserver$Receiver$$ExternalSyntheticLambda0.run |
| sensor | inert | C4 | M | sensors | Android SensorManager facade over sensors<br>5 call sites, e.g. androidx.media3.exoplayer.video.spherical.SphericalGLSurfaceView.<init> |
| appops | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.core.content.PermissionChecker.checkSelfPermission |
| biometric | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.biometric.BiometricManager$Api29Impl.create |
| camera | inert | C4 | S | multimedia/camera_framework | Android CameraManager facade over multimedia/camera_framework<br>9 call sites, e.g. mozilla.components.support.ktx.android.content.ContextKt.hasCamera |
| download | inert | C4 | S | miscservices/download_server | Android DownloadManager facade over miscservices/download_server<br>1 call sites, e.g. mozilla.components.feature.downloads.AbstractFetchDownloadService$addToDownloadSystemDatabaseCompat$1.invokeSuspend |
| locale | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. androidx.appcompat.app.AppCompatDelegate$$ExternalSyntheticLambda0.run |
| media_metrics | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.media3.exoplayer.ExoPlayerImpl$Api31$$ExternalSyntheticLambda0.run |
| storagestats | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. org.mozilla.fenix.perf.StorageStatsMetrics$report$1.invokeSuspend |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>3 call sites, e.g. androidx.core.os.UserManagerCompat.isUserUnlocked `framework/package-manager/java/OHUserManager.java:72` |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>4 call sites, e.g. org.mozilla.fenix.settings.PairFragment$$ExternalSyntheticLambda0.invoke |
| wifi | null | C4 | S | communication/wifi | Android WifiManager facade over communication/wifi<br>1 call sites, e.g. org.mozilla.gecko.GeckoNetworkManager.wifiDhcpGatewayAddress |
| captioning | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.media3.exoplayer.trackselection.MappingTrackSelector.selectTracks `SystemServiceRegistry.java:337` |
| input | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>3 call sites, e.g. org.mozilla.gecko.AndroidGamepadManager$1.run `SystemServiceRegistry.java:545` |
| print | unresolved | CU | verify | print_service | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. org.mozilla.geckoview.GeckoView$GeckoViewPrintDelegate.onPrintWithStatus `SystemServiceRegistry.java:893` |
| profiling | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. io.sentry.android.core.PerfettoProfiler.<init> `ProfilingFrameworkInitializer.java:73` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>3 call sites, e.g. androidx.appcompat.widget.AppCompatTextView.getTextClassifier `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>27 call sites, e.g. androidx.compose.material3.internal.BasicTooltipKt.BasicTooltipBox |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>8 call sites, e.g. androidx.compose.ui.autofill.PlatformAutofillManagerImpl.getPlatformAndroidManager |
| credential | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>3 call sites, e.g. org.mozilla.geckoview.WebAuthnTokenManager.lambda$webAuthnGetAssertion$19 |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>22 call sites, e.g. androidx.room.RoomDatabase$Builder.build |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>1 call sites, e.g. androidx.work.impl.utils.ForceStopRunnable.setAlarm |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>26 call sites, e.g. androidx.appcompat.widget.AppCompatEditText.onTextContextMenuItem |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>21 call sites, e.g. androidx.media3.common.util.NetworkTypeObserver$Receiver$$ExternalSyntheticLambda0.run |
| display | supplied | C0 | verify | display_manager | none<br>9 call sites, e.g. androidx.media3.common.util.Util.getCurrentDisplayModeSize |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>21 call sites, e.g. androidx.appcompat.widget.AppCompatTextView.onDetachedFromWindow `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| location | supplied | C0 | verify | location | none<br>2 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.getAutoTimeNightModeManager |
| power | supplied | C0 | verify | powermgr | none<br>8 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$AutoBatteryNightModeManager.<init> |
| shortcut | supplied | C0 | verify | unmapped | none<br>14 call sites, e.g. mozilla.components.feature.pwa.WebAppShortcutManager.requestPinShortcut |
| storage | supplied | C0 | verify | filemanagement/storage_service | none<br>1 call sites, e.g. org.mozilla.fenix.settings.downloads.DefaultDownloadLocationFormatter.getFriendlyPath |
| uimode | supplied | C0 | verify | display / theme | none<br>6 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.mapNightMode |
| window | supplied | C0 | verify | window_manager | none<br>21 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.closePanel `framework/core/java/OHServiceManager.java:96` |

## Keystore & crypto providers

_JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Android keystore provider ("AndroidKeyStore") | supplied | C0 | verify | security/huks (OH Universal Keystore); keystore2 has no OH counterpart | install an "AndroidKeyStore" provider whose keys come from KeyGenParameterSpec and stay per app: software keys in app data (days), or OH HUKS for hardware-backed keys (weeks). A blocker wherever the app opens it at startup (secure storage, encrypted preferences, biometric crypto, attestation)<br>4 classes name it, e.g. Landroidx/biometric/BiometricPrompt;, Lcom/adjust/sdk/sig/t1;, Lmozilla/components/lib/dataprotect/Keystore;, Lmozilla/components/lib/dataprotect/SecurePreferencesImpl23;; calls KeyGenerator.getInstance("AES"), KeyGenerator.getInstance("HmacSHA256"), KeyStore.getInstance("AndroidKeyStore") `framework/core/java/SoftwareAndroidKeyStore.java:65` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Components in secondary processes: :StartupCrashActivityProcess, :crashReportingProcess, :crashhelper_disable_art_image_, :gmplugin_disable_art_image_, :gpu_disable_art_image_, :ipdlunittest_disable_art_image_, :isolatedTab_disable_art_image_0, :isolatedTab_disable_art_image_1, :isolatedTab_disable_art_image_10, :isolatedTab_disable_art_image_11, :isolatedTab_disable_art_image_12, :isolatedTab_disable_art_image_13, :isolatedTab_disable_art_image_14, :isolatedTab_disable_art_image_15, :isolatedTab_disable_art_image_16, :isolatedTab_disable_art_image_17, :isolatedTab_disable_art_image_18, :isolatedTab_disable_art_image_19, :isolatedTab_disable_art_image_2, :isolatedTab_disable_art_image_20, :isolatedTab_disable_art_image_21, :isolatedTab_disable_art_image_22, :isolatedTab_disable_art_image_23, :isolatedTab_disable_art_image_24, :isolatedTab_disable_art_image_25, :isolatedTab_disable_art_image_26, :isolatedTab_disable_art_image_27, :isolatedTab_disable_art_image_28, :isolatedTab_disable_art_image_29, :isolatedTab_disable_art_image_3, :isolatedTab_disable_art_image_30, :isolatedTab_disable_art_image_31, :isolatedTab_disable_art_image_32, :isolatedTab_disable_art_image_33, :isolatedTab_disable_art_image_34, :isolatedTab_disable_art_image_35, :isolatedTab_disable_art_image_36, :isolatedTab_disable_art_image_37, :isolatedTab_disable_art_image_38, :isolatedTab_disable_art_image_39, :isolatedTab_disable_art_image_4, :isolatedTab_disable_art_image_5, :isolatedTab_disable_art_image_6, :isolatedTab_disable_art_image_7, :isolatedTab_disable_art_image_8, :isolatedTab_disable_art_image_9, :media, :mozilla.components.lib.crash.CrashHandler, :mozilla.components.lib.crash.CrashReporter, :rdd_disable_art_image_, :socket_disable_art_image_, :tab_disable_art_image_0, :tab_disable_art_image_1, :tab_disable_art_image_10, :tab_disable_art_image_11, :tab_disable_art_image_12, :tab_disable_art_image_13, :tab_disable_art_image_14, :tab_disable_art_image_15, :tab_disable_art_image_16, :tab_disable_art_image_17, :tab_disable_art_image_18, :tab_disable_art_image_19, :tab_disable_art_image_2, :tab_disable_art_image_20, :tab_disable_art_image_21, :tab_disable_art_image_22, :tab_disable_art_image_23, :tab_disable_art_image_24, :tab_disable_art_image_25, :tab_disable_art_image_26, :tab_disable_art_image_27, :tab_disable_art_image_28, :tab_disable_art_image_29, :tab_disable_art_image_3, :tab_disable_art_image_30, :tab_disable_art_image_31, :tab_disable_art_image_32, :tab_disable_art_image_33, :tab_disable_art_image_34, :tab_disable_art_image_35, :tab_disable_art_image_36, :tab_disable_art_image_37, :tab_disable_art_image_38, :tab_disable_art_image_39, :tab_disable_art_image_4, :tab_disable_art_image_5, :tab_disable_art_image_6, :tab_disable_art_image_7, :tab_disable_art_image_8, :tab_disable_art_image_9, :utility_disable_art_image_, :zygoteTab_disable_art_image_ | missing | C4 | L | appspawn (second process) | spawn and route secondary Android processes |
| PackageManager.queryBroadcastReceivers | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1232` |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1225` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1253` |
| PackageManager.queryIntentServices | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1246` |
| PackageManager.resolveContentProvider | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1288` |
| PackageManager.resolveService | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1239` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1699` |
| PackageManager.getInstallSourceInfo | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1500` |
| PackageManager.getInstallerPackageName | stub | C9 | S | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1493` |
| PackageManager.getNameForUid | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1167` |
| PackageManager.getPackagesForUid | stub | C9 | S | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1158` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1687` |
| Content providers installed at bind (11, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>LensFileProvider, ProfilerProvider, InitializationProvider, FileProvider, InitializationProvider, FileProvider, FileProvider, GeckoClipboardContentProvider, FirebaseInitProvider@100, SentryPerformanceProvider@200, SystemLifecycleContentProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>35 components carry meta-data (1 directBootAware, e.g. ComponentDiscoveryService); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |
| Split APKs visible to resources and class loading (2 splits) | supplied | C0 | verify | none (Westlake PM + asset manager) | populate splitNames/splitSourceDirs from the installed split set<br>config.arm64_v8a.apk, config.xhdpi.apk `framework/package-manager/java/SplitApkResolver.java:115` — probe: `none yet (propose: split-resources)` |

## Activity, window & process contracts

_what system_server would answer, answered in-process by Westlake in direct launch → white-box probes_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| ActivityManager process-table queries (getRunningAppProcesses) | supplied | C0 | verify | none (the caller's own process is the answer) | answer with the caller's process: name, pid, uid, foreground importance, its package<br>app calls getRunningAppProcesses `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1351` — probe: `probes/running-app-processes` |
| Dialogs stack above their activity's window, whatever the add order | supplied | C0 | verify | window_manager (sub-window z-order: creation order) | stack a base application window below the dialogs already attached to its token<br>app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added before the activity's own window `framework/window/java/WindowSessionAdapter.java:370` — probe: `probes/dialog-before-window` |
| Windows placed by LayoutParams gravity and x/y (dialogs centred) | supplied | C0 | verify | window_manager (session rect) | compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:346` — probe: `probes/dialog-before-window` |
| FLAG_DIM_BEHIND dims what is under a dialog | supplied | C0 | verify | render_service (a layer under the window) | draw a dim layer of dimAmount under the window (OH has no dim flag)<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:84` — probe: `probes/dialog-before-window` |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libxul.so → 32 classes, 264 members | hollow-candidate | C9 | verify | ability_runtime | compare the constant bodies with AOSP<br>android.content.Context.destroy()V |
| libandroidx.graphics.path.so → 1 classes, 1 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/graphics/Path |
| libcrashtools.so → 4 classes, 6 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/IOException, java/lang/IllegalArgumentException, java/lang/OutOfMemoryError, java/util/LinkedHashMap |
| libdatastore_shared_counter.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/IOException |
| config.arm64_v8a.apk!lib/arm64-v8a/libjnidispatch.so → 28 classes, 116 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Boolean, java/lang/Byte, java/lang/Character, java/lang/Class |
| libmozavcodec.so → 7 classes, 63 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/media/MediaCodec, android/media/MediaCodec$BufferInfo, android/media/MediaCodecInfo, android/media/MediaCodecInfo$CodecCapabilities |
| libmozglue.so → 2 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Exception, java/lang/NullPointerException |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| NDK weld · media: 48 symbols | missing | C4 | L | multimedia/av_codec + player_framework | AOSP NDK source above, multimedia/av_codec + player_framework below<br>open: AMediaCodecCryptoInfo_delete, AMediaCodecCryptoInfo_new, AMediaCodecCryptoInfo_setPattern, AMediaCodec_configure, AMediaCodec_createCodecByName, AMediaCodec_createDecoderByType, AMediaCodec_createEncoderByType, AMediaCodec_delete |
| NDK weld · buffers: 4 symbols | missing | C4 | M | graphic_surface / native_buffer | AOSP NDK source above, graphic_surface / native_buffer below<br>open: AHardwareBuffer_recvHandleFromUnixSocket, AHardwareBuffer_sendHandleToUnixSocket, AImageReader_acquireNextImageAsync, AImageReader_setImageListener |
| NDK weld · window: 3 symbols | missing | C4 | M | window_manager + render_service | AOSP NDK source above, window_manager + render_service below<br>open: ANativeWindow_lock, ANativeWindow_toSurface, ANativeWindow_unlockAndPost |
| bionic libc ABI: 2 symbols to translate onto musl | missing | C1/C2 | S | OH musl libc | bionic-ABI shim: forward or translate; never ship a second libc<br>open: __libc_init, android_dlopen_ext |
| NDK package: 3 symbols compiled from AOSP source | missing | C1 | S | none beyond what Westlake already provides | compile the AOSP source (sharedmem.cpp) and deploy it<br>open: ASharedMemory_create, ASharedMemory_getSize, ASharedMemory_setProt |
| libc calls carrying a constant each libc numbers differently (sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>sysconf: 13 libraries, e.g. libcrashhelper.so, libcrashtools.so, libfreebl3.so `framework/webview-shim/webview_bionic_shim.c:1189` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Libraries mapped straight out of the APK (18 .so, extractNativeLibs=false) | supplied | C0 | verify | OH dynamic linker (cannot map zip!/ members: board test 2026-09-18) | extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too) `manifest/tools/prepare_app.py:75` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create fifo_file in app data | denied | C4 | OH | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | allow hap_domain normal_hap_data_file_attr:fifo_file { create read write open lock unlink map setattr getattr rename }; (no neverallow in hap_domain.te blocks it) \| bring-up workaround: label the staged app-data tree data_app_el2_file: kernel grants normal_hap dir/file/fifo_file/sock_file there (still no lnk_file)<br>libcrashhelper.so:mkfifo, libcrashtools.so:mkfifo, libxul.so:mkfifo `sepolicy/ohos_policy/bundlemanager/bundle_framework/system/installs.te:199 allow hap_domain data_app_el2_file:fifo_file { create read write open lock unlink map setattr getattr rename }` |
| Create lnk_file in app data | denied | C5 | M | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>libcrashhelper.so:symlink, libcrashtools.so:symlink, libxul.so:symlink `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## External services & SDK behaviour

_SDKs that expect Google services or probe the device_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Google Play services | absent | C5 | M | none: no Google services on OH | decide per feature: truthful 'unavailable' result, or an OH-backed replacement (push, maps, auth)<br>application meta-data com.google.android.gms.version |
| Firebase component discovery (ComponentDiscoveryService) | partial | C5 | verify | none: no Google services on OH | component discovery is local (see pm:component-metadata); GMS-backed components degrade<br>com.google.firebase.components.ComponentDiscoveryService declares 6 registrars |

## Limits of this map

- 10 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 17, 'newer-than-reference': 12}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
