# org.openhab.habdroid 3.21.1 → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `e2524b1a86`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 35.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 12 | 12 | 12×verify |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 32 | 16 | 5×verify, 6×S, 5×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 1 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 9 | 8 | 1×verify, 3×S, 3×M, 1×L |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 5 | 1 | 1×L |
| Windows & surfaces | how the first screen renders → whether it needs a surface of its own → OH window/surface model | 0 | 0 | — |
| Framework natives | platform classes the app uses → their native methods → libraries the runtime registers them from | 3 | 3 | 2×M, 1×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 0 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 0 | 0 | — |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 1 | 1 | 1×verify |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 0 | 0 | — |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 0 | 0 | — |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Rows that have blocked an app at startup before

From the blockers ledger: gaps this app has in common with an app that died on them.

| Row | Verdict | Blocked |
|---|---|---|
| `svc:jobscheduler` | hollow | gallery (corpus-2), fixed in 886b89b |
| `svc:locale` | supplied | ooniprobe (loop-1), fixed in 95dba94 |
| `svc:notification` | supplied | tusky (corpus-2), fixed in 886b89b |
| `svc:uimode` | supplied | burgerking (blind-bk), fixed in d689e67 |
| `svc:user` | strict | burgerking (blind-bk), fixed in 9b8b861 |
| `jca:AndroidKeyStore` | supplied | burgerking (blind-bk), fixed in 21fdcda |
| `wv:renderer-process` | missing | burgerking (blind-bk), open |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | hollow-candidate | C9 | verify | window_manager / render_service | check each hollow body against AOSP<br>android.view.ActionProvider.hasSubMenu, android.view.ActionProvider.isVisible, android.view.ActionProvider.onPerformDefaultAction |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.drawable.Drawable$ConstantState.canApplyTheme, android.graphics.drawable.Drawable.applyTheme, android.graphics.drawable.Drawable.canApplyTheme |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.ActionBar.getThemedContext, android.app.ActionBar.setHomeActionContentDescription, android.app.ActionBar.setHomeAsUpIndicator |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayOutputStream.close, java.io.InputStream.available, java.io.InputStream.close |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.AutoCompleteTextView.onFinishInflate, android.widget.Button.onTextChanged |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| Networking | hollow-candidate | C9 | verify | netmanager | check each hollow body against AOSP<br>android.net.ConnectivityManager$NetworkCallback.onAvailable, android.net.ConnectivityManager$NetworkCallback.onCapabilitiesChanged, android.net.ConnectivityManager$NetworkCallback.onLost |
| WebView | hollow-candidate | C9 | verify | web (ArkWeb) or bundled Chromium | check each hollow body against AOSP<br>android.webkit.HttpAuthHandler.proceed, android.webkit.SslErrorHandler.cancel, android.webkit.SslErrorHandler.proceed |
| Job scheduling | hollow-candidate | C9 | verify | resourceschedule/work_scheduler | check each hollow body against AOSP<br>android.app.job.JobService.onCreate, android.app.job.JobService.onDestroy |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.isRestricted |
| Package manager | hollow-candidate | C9 | verify | bundle_framework | check each hollow body against AOSP<br>android.content.pm.PackageManager.getBackgroundPermissionOptionLabel |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>androidx.media3.datasource.rtmp.RtmpDataSource, androidx.media3.decoder.av1.Libgav1VideoRenderer, androidx.media3.decoder.ffmpeg.ExperimentalFfmpegVideoRenderer |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>10 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.onKeyUpPanel `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1627` |
| jobscheduler | hollow | C9 | M | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>4 call sites, e.g. androidx.work.impl.background.systemjob.JobSchedulerExtKt.createErrorMessage `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2189` |
| phone | inert | C4 | M | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>3 call sites, e.g. androidx.media3.common.util.NetworkTypeObserver$Api31.disambiguate4gAnd5gNsa |
| sensor | inert | C4 | M | sensors | Android SensorManager facade over sensors<br>1 call sites, e.g. androidx.media3.exoplayer.video.spherical.SphericalGLSurfaceView.<init> |
| wifi | null | C4 | M | communication/wifi | Android WifiManager facade over communication/wifi<br>2 call sites; Kotlin casts it non-null in 1 methods (e.g. org.openhab.habdroid.util.ExtensionFuncsKt.getWifiManager): a null answer throws there, it is not skipped |
| biometric | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.biometric.BiometricManager$Api29Impl.create |
| fingerprint | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. androidx.core.hardware.fingerprint.FingerprintManagerCompat$Api23Impl.getFingerprintManagerOrNull |
| keyguard | null | C4 | S | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>4 call sites; Kotlin casts it non-null in 1 methods (e.g. org.openhab.habdroid.ui.AbstractBaseActivity.promptForDevicePassword): a null answer throws there, it is not skipped |
| media_metrics | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.media3.exoplayer.analytics.MediaMetricsListener.create |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>1 call sites, e.g. androidx.core.os.UserManagerCompat$Api24Impl.isUserUnlocked `framework/package-manager/java/OHUserManager.java:82` |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>1 call sites, e.g. com.github.appintro.internal.VibrationHelper.initializeVibrator |
| bluetooth | unresolved | CU | verify | communication/bluetooth | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites; Kotlin casts it non-null in 1 methods (e.g. org.openhab.habdroid.background.BackgroundTasksManager._init_$lambda$13): a null answer throws there, it is not skipped `BluetoothFrameworkInitializer.java:100` |
| captioning | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>3 call sites, e.g. androidx.media3.common.TrackSelectionParameters$Builder.setPreferredTextLanguageAndRoleFlagsToCaptioningManagerSettings `SystemServiceRegistry.java:337` |
| nfc | unresolved | CU | verify | communication/nfc | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites; Kotlin casts it non-null in 1 methods (e.g. org.openhab.habdroid.ui.WriteTagActivity.onCreate): a null answer throws there, it is not skipped `NfcFrameworkInitializer.java:68` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper$Api26Impl.getTextClassifier `SystemServiceRegistry.java:413` |
| vibrator_manager | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites; Kotlin casts it non-null in 1 methods (e.g. com.github.appintro.internal.VibrationHelper.initializeVibrator): a null answer throws there, it is not skipped `SystemServiceRegistry.java:796` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>15 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>4 call sites, e.g. androidx.core.graphics.drawable.IconCompat.addToShortcutIntent |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>4 call sites, e.g. androidx.work.impl.background.systemalarm.Alarms.cancelExactAlarm |
| appops | supplied | C0 | verify | unmapped | none<br>3 call sites, e.g. androidx.core.app.AppOpsManagerCompat$Api29Impl.getSystemService |
| batterymanager | supplied | C0 | verify | powermgr/battery_manager | none<br>1 call sites, e.g. org.openhab.habdroid.background.BackgroundTasksManager._init_$lambda$5 |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>4 call sites, e.g. androidx.appcompat.widget.AppCompatReceiveContentHelper.maybeHandleMenuActionViaPerformReceiveContent |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>7 call sites, e.g. androidx.media3.common.util.NetworkTypeObserver.getNetworkTypeFromConnectivityManager |
| display | supplied | C0 | verify | display_manager | none<br>4 call sites, e.g. androidx.media3.common.util.Util.getCurrentDisplayModeSize |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>12 call sites, e.g. androidx.activity.ImmLeaksCleaner.onStateChanged `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>64 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| locale | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. androidx.appcompat.app.AppCompatDelegate.getLocaleManagerForApplication |
| location | supplied | C0 | verify | location | none<br>3 call sites, e.g. androidx.appcompat.app.TwilightManager.getInstance |
| notification | supplied | C0 | verify | notification (ANS) | none<br>11 call sites, e.g. androidx.core.content.ContextCompat.checkSelfPermission |
| power | supplied | C0 | verify | powermgr | none<br>4 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$AutoBatteryNightModeManager.<init> |
| uimode | supplied | C0 | verify | display / theme | none<br>3 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.mapNightMode |
| window | supplied | C0 | verify | window_manager | none<br>9 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.openPanel `framework/core/java/OHServiceManager.java:96` |

## Keystore & crypto providers

_JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Android keystore provider ("AndroidKeyStore") | supplied | C0 | verify | security/huks (OH Universal Keystore); keystore2 has no OH counterpart | install an "AndroidKeyStore" provider whose keys come from KeyGenParameterSpec and stay per app: software keys in app data (days), or OH HUKS for hardware-backed keys (weeks). A blocker wherever the app opens it at startup (secure storage, encrypted preferences, biometric crypto, attestation)<br>4 classes name it, e.g. Landroidx/biometric/CryptoObjectUtils;, Landroidx/security/crypto/MasterKeys;, Lcom/google/crypto/tink/integration/android/AndroidKeystoreKmsClient$Builder;, Lcom/google/crypto/tink/integration/android/AndroidKeystoreKmsClient;; calls KeyGenerator.getInstance("AES"), KeyStore.getInstance("AndroidKeyStore") `framework/core/java/SoftwareAndroidKeyStore.java:65` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Components in secondary processes: :acra | missing | C4 | L | appspawn (second process) | spawn and route secondary Android processes |
| PackageManager.queryBroadcastReceivers | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1233` |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1226` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1254` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1728` |
| PackageManager.getSystemAvailableFeatures | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1815` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1716` |
| Content providers installed at bind (1, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>InitializationProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>17 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

## Activity, window & process contracts

_what system_server would answer, answered in-process by Westlake in direct launch → white-box probes_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| WebView's renderer runs in an isolated service process | missing | C4 | L | process spawn (appspawn): an isolated Android service process with its own sandbox | host the renderer: spawn an isolated child and bind Chromium's SandboxedProcessService over a local channel; or build the framework with the update-service flag off so WebView runs single-process<br>app constructs WebViews and calls 21 WebView methods `frameworks-base/core/java/android/webkit/WebViewDelegate.java:215` |
| ActivityManager process-table queries (getRunningAppProcesses, getRunningServices) | supplied | C0 | verify | none (the caller's own process is the answer) | answer with the caller's process: name, pid, uid, foreground importance, its package<br>app calls getRunningAppProcesses, getRunningServices `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1409` — probe: `probes/running-app-processes` |
| Dialogs stack above their activity's window, whatever the add order | supplied | C0 | verify | window_manager (sub-window z-order: creation order) | stack a base application window below the dialogs already attached to its token<br>app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added before the activity's own window `framework/window/java/WindowSessionAdapter.java:370` — probe: `probes/dialog-before-window` |
| Windows placed by LayoutParams gravity and x/y (dialogs centred) | supplied | C0 | verify | window_manager (session rect) | compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:346` — probe: `probes/dialog-before-window` |
| FLAG_DIM_BEHIND dims what is under a dialog | supplied | C0 | verify | render_service (a layer under the window) | draw a dim layer of dimAmount under the window (OH has no dim flag)<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:84` — probe: `probes/dialog-before-window` |

## Framework natives

_platform classes the app uses → their native methods → libraries the runtime registers them from_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| android.media.MediaDrm: 43 of 43 natives unregistered | missing | C3 | L | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.drm.DrmManagerClient: 19 of 19 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: _acquireDrmInfo(ILandroid/drm/DrmInfoRequest;)Landroid/drm/DrmInfo;, _canHandle(ILjava/lang/String;Ljava/lang/String;)Z, _checkRightsStatus(ILjava/lang/String;I)I, _closeConvertSession(II)Landroid/drm/DrmConvertedStatus;, _convertData(II[B)Landroid/drm/DrmConvertedStatus;, _getAllSupportInfo(I)[Landroid/drm/DrmSupportInfo;, _getConstraints(ILjava/lang/String;I)Landroid/content/ContentValues;, _getDrmObjectType(ILjava/lang/String;Ljava/lang/String;)I |
| android.media.MediaMetadataRetriever: 13 of 13 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |

## Limits of this map

- 9 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 1}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
