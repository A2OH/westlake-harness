# org.videolan.vlc 3.7.1 → OpenHarmony: API shim gap map

Provider: Westlake `burgerking-startup-fixes` @ `02cbace7fb`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 36.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 14 | 14 | 14×verify |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 29 | 16 | 2×verify, 11×S, 3×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 1 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 14 | 13 | 1×verify, 6×S, 5×M, 1×L |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 4 | 0 | — |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 3 | 1 | 1×verify |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 1 | 0 | — |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 1 | 1 | 1×XS |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 1 | 1 | 1×M |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 0 | 0 | — |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | hollow-candidate | C9 | verify | window_manager / render_service | check each hollow body against AOSP<br>android.view.ActionProvider.hasSubMenu, android.view.ActionProvider.isVisible, android.view.ActionProvider.onPerformDefaultAction |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayOutputStream.close, java.io.ByteArrayOutputStream.flush, java.io.FileOutputStream.flush |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.Canvas.disableZ, android.graphics.Canvas.enableZ, android.graphics.drawable.Drawable$ConstantState.canApplyTheme |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.Button.onTextChanged, android.widget.EditText.isInEditMode, android.widget.EditText.onFinishInflate |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.ActionBar.getThemedContext, android.app.ActionBar.setHomeActionContentDescription, android.app.ActionBar.setHomeAsUpIndicator |
| Networking | hollow-candidate | C9 | verify | netmanager | check each hollow body against AOSP<br>android.net.ConnectivityManager$NetworkCallback.onAvailable, android.net.ConnectivityManager$NetworkCallback.onCapabilitiesChanged, android.net.ConnectivityManager$NetworkCallback.onLost |
| Java extensions | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>javax.net.ssl.X509ExtendedKeyManager.chooseEngineClientAlias, javax.net.ssl.X509ExtendedKeyManager.chooseEngineServerAlias, javax.security.auth.Destroyable.isDestroyed |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.AsyncTask.onPostExecute, android.os.Handler.handleMessage |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.getAttributionTag, android.content.Context.isRestricted |
| Location | hollow-candidate | C9 | verify | location | check each hollow body against AOSP<br>android.location.GnssMeasurementsEvent$Callback.onGnssMeasurementsReceived, android.location.GnssMeasurementsEvent$Callback.onStatusChanged |
| Media | hollow-candidate | C9 | verify | multimedia | check each hollow body against AOSP<br>android.media.AudioDeviceCallback.onAudioDevicesAdded, android.media.tv.TvInputService.onDestroy |
| Media store | hollow-candidate | C9 | verify | multimedia/media_library | check each hollow body against AOSP<br>android.provider.MediaStore.getPickImagesMaxLimit |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>androidx.sharetarget.ShortcutInfoCompatSaverImpl, androidx.window.extensions.WindowExtensions, androidx.window.extensions.WindowExtensionsProvider |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>11 call sites, e.g. android.support.v4.media.session.MediaSessionCompat$MediaSessionImplBase.<init> `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1569` |
| notification | hollow | C9 | M | notification (ANS) | replace the hollow binder with an implementation over notification (ANS)<br>4 call sites, e.g. androidx.core.app.NotificationManagerCompat.<init> `framework/android-runtime/src/AndroidRuntime.cpp:821` |
| phone | inert | C4 | M | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>1 call sites, e.g. org.videolan.resources.AndroidDevices.<clinit> |
| appops | null | C5 | S | unmapped | truthful local manager (feature absent)<br>5 call sites, e.g. androidx.core.app.AppOpsManagerCompat$Api29Impl.getSystemService |
| download | inert | C4 | S | miscservices/download_server | Android DownloadManager facade over miscservices/download_server<br>1 call sites, e.g. org.videolan.vlc.util.VLCDownloadManager.<clinit> |
| fingerprint | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. androidx.core.hardware.fingerprint.FingerprintManagerCompat$Api23Impl.getFingerprintManagerOrNull |
| grammatical_inflection | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.core.app.GrammaticalInflectionManagerCompat$Api34Impl.getGrammaticalInflectionManager |
| jobscheduler | hollow | C9 | S | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>1 call sites, e.g. androidx.core.app.JobIntentService$JobWorkEnqueuer.<init> `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2088` |
| keyguard | null | C4 | S | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>2 call sites, e.g. org.videolan.vlc.PlaybackService.onCreate |
| locale | null | C5 | S | unmapped | truthful local manager (feature absent)<br>3 call sites, e.g. androidx.appcompat.app.AppCompatDelegate.getLocaleManagerForApplication |
| media_router | inert | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. org.videolan.libvlc.util.DisplayManager.<init> |
| usb | null | C4 | S | usb_manager | Android UsbManager facade over usb_manager<br>1 call sites, e.g. org.videolan.vlc.ExternalMonitor.checkNewStorages |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>1 call sites, e.g. androidx.core.os.UserManagerCompat$Api24Impl.isUserUnlocked `framework/package-manager/java/OHUserManager.java:72` |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>1 call sites, e.g. org.videolan.vlc.gui.audio.AudioPlayer$LongSeekListener$seekRunnable$1.run |
| print | unresolved | CU | verify | print_service | trace the helper's binder; then treat as null, inert or supplied<br>2 call sites, e.g. androidx.print.PrintHelper.printBitmap `SystemServiceRegistry.java:893` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper$Api26Impl.getTextClassifier `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>17 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| media_session | not-a-platform-service | C5 | none | none | none (null on Android too)<br>1 call sites, e.g. androidx.media.MediaSessionManagerImplApi28.<init> |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>6 call sites, e.g. androidx.core.content.pm.ShortcutManagerCompat.getIconDimensionInternal |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>1 call sites, e.g. org.videolan.vlc.TvReceiver.scheduleRecommendationUpdate |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>6 call sites, e.g. androidx.appcompat.widget.AppCompatReceiveContentHelper.maybeHandleMenuActionViaPerformReceiveContent |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>3 call sites, e.g. org.videolan.tools.KotlinExtensionsKt.isConnected |
| display | supplied | C0 | verify | display_manager | none<br>6 call sites, e.g. androidx.car.app.CarContext.attachBaseContext |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>17 call sites, e.g. androidx.activity.ImmLeaksCleaner.onStateChanged `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>6 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| location | supplied | C0 | verify | location | none<br>3 call sites, e.g. androidx.appcompat.app.TwilightManager.getInstance |
| power | supplied | C0 | verify | powermgr | none<br>6 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$AutoBatteryNightModeManager.<init> |
| uimode | supplied | C0 | verify | display / theme | none<br>7 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.mapNightMode |
| window | supplied | C0 | verify | window_manager | none<br>18 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.openPanel `framework/core/java/OHServiceManager.java:96` |

## Keystore & crypto providers

_JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Android keystore provider ("AndroidKeyStore") | supplied | C0 | verify | security/huks (OH Universal Keystore); keystore2 has no OH counterpart | install an "AndroidKeyStore" provider whose keys come from KeyGenParameterSpec and stay per app: software keys in app data (days), or OH HUKS for hardware-backed keys (weeks). A blocker wherever the app opens it at startup (secure storage, encrypted preferences, biometric crypto, attestation)<br>1 classes name it, e.g. Lorg/videolan/vlc/remoteaccessserver/ssl/SecretGenerator;; calls KeyGenerator.getInstance("AES"), KeyPairGenerator.getInstance("RSA"), KeyStore.getInstance("AndroidKeyStore") `framework/core/java/SoftwareAndroidKeyStore.java:65` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Components in secondary processes: :logger | missing | C4 | L | appspawn (second process) | spawn and route secondary Android processes |
| PackageManager.queryBroadcastReceivers | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1232` |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1225` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1253` |
| PackageManager.queryIntentServices | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1246` |
| PackageManager.resolveContentProvider | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1288` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1699` |
| PackageManager.getInstallSourceInfo | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1500` |
| PackageManager.getInstallerPackageName | stub | C9 | S | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1493` |
| PackageManager.getNameForUid | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1167` |
| PackageManager.getPackagesForUid | stub | C9 | S | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1158` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1687` |
| Content providers installed at bind (5, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>TVSearchProvider, FileProvider, ArtworkProvider, FileProvider, InitializationProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>9 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

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
| libvlc.so → 28 classes, 204 members | unresolved | CU | verify | through the Java framework | confirm the library tolerates their absence; watch it under the runtime-integrity checks<br>e.g. android/media/AudioFormat, android/media/AudioManager, android/media/AudioTimestamp, android/media/AudioTrack |
| libmla.so → 4 classes, 11 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/os/Build$VERSION, java/lang/IllegalArgumentException, java/lang/IllegalStateException, java/lang/String |
| libvlcjni.so → 7 classes, 2 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/os/Build$VERSION, java/io/FileDescriptor, java/lang/IllegalArgumentException, java/lang/IllegalStateException |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libc calls carrying a constant each libc numbers differently (pathconf, sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>pathconf: 2 libraries, e.g. libc++_shared.so, libvlc.so; sysconf: 3 libraries, e.g. libc++_shared.so, libmla.so, libvlc.so `framework/webview-shim/webview_bionic_shim.c:1189` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Packaged libraries a board library of the same name shadows (libc++_shared.so) | missing | C3 | XS | OH dynamic linker search order: /system/lib64/libc++_shared.so comes before the app's library directory | load these 4 libraries in the isolated Android namespace so DT_NEEDED picks the APK's copy (e.g. NDK libc++_shared is std::__ndk1; OH's is not): libc++_shared.so libmla.so libvlc.so libvlcjni.so<br>4 APK libraries reach them through DT_NEEDED `manifest/tools/probe_source_app.py:44` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create lnk_file in app data | denied | C5 | M | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>java.nio.file.Files:createSymbolicLink, libc++_shared.so:symlink `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## Limits of this map

- 9 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 19}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
