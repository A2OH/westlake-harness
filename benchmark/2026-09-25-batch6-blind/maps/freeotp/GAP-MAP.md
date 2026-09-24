# org.liberty.android.freeotpplus 3.4 → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `2b21e1200d`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 36.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 11 | 11 | 9×verify, 1×S, 1×M |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 25 | 11 | 1×verify, 7×S, 3×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 1 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 7 | 6 | 1×verify, 2×S, 3×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 3 | 0 | — |
| Windows & surfaces | how the first screen renders → whether it needs a surface of its own → OH window/surface model | 0 | 0 | — |
| Framework natives | platform classes the app uses → their native methods → libraries the runtime registers them from | 12 | 12 | 2×S, 9×M, 1×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 0 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 0 | 0 | — |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 2 | 1 | 1×verify |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 1 | 1 | 1×M |
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
| `jni:android.hardware.Camera` | missing | opencamera (loop-1), open |
| `jca:AndroidKeyStore` | supplied | burgerking (blind-bk), fixed in 21fdcda |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | missing | C4 | M | window_manager / render_service | implement the members over window_manager / render_service<br>android.view.accessibility.AccessibilityNodeInfo$AccessibilityAction.ACTION_SET_EXTENDED_SELECTION, android.view.accessibility.AccessibilityNodeInfo$CollectionItemInfo$Builder.setSortDirection, android.view.accessibility.AccessibilityNodeInfo$CollectionItemInfo.getSortDirection |
| Other Android | missing | C1/C5 | S | unmapped | port from AOSP, or confirm the caller tolerates absence<br>android.window.BackEvent.<init> |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.Canvas.disableZ, android.graphics.Canvas.enableZ, android.graphics.Matrix.hashCode |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.Button.onTextChanged, android.widget.EditText.isInEditMode, android.widget.EditText.onDetachedFromWindow |
| Camera | hollow-candidate | C9 | verify | multimedia/camera_framework | check each hollow body against AOSP<br>android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureBufferLost, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureCompleted, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureFailed |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayOutputStream.close, java.io.ByteArrayOutputStream.flush, java.io.FileOutputStream.flush |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.ActionBar.getThemedContext, android.app.ActionBar.setHomeActionContentDescription, android.app.ActionBar.setHomeAsUpIndicator |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.getAttributionTag, android.content.Context.isRestricted |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.IBinder.getSuggestedMaxIpcSizeBytes |
| Media store | hollow-candidate | C9 | verify | multimedia/media_library | check each hollow body against AOSP<br>android.provider.MediaStore.getPickImagesMaxLimit |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>No default CameraXConfig.Provider specified in meta-data. The most likely cause is you did not include a default implementation in your build such as 'camera-camera2'., androidx.sharetarget.ShortcutInfoCompatSaverImpl, com.bumptech.glide.GeneratedAppGlideModuleImpl |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>4 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.onKeyUpPanel `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1627` |
| camera | inert | C4 | M | multimedia/camera_framework | Android CameraManager facade over multimedia/camera_framework<br>5 call sites, e.g. androidx.camera.camera2.adapter.PipeCameraPresenceSource.<init> |
| phone | inert | C4 | M | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>2 call sites, e.g. androidx.media3.common.util.NetworkTypeObserver$Api31.disambiguate4gAnd5gNsa |
| biometric | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.biometric.BiometricManager$Api29Impl.create |
| device_policy | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites; Kotlin casts it non-null in 1 methods (e.g. androidx.camera.camera2.pipe.config.CameraPipeModule$Companion.provideDevicePolicyManagerWrapper): a null answer throws there, it is not skipped |
| grammatical_inflection | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.core.app.GrammaticalInflectionManagerCompat$Api34Impl.getGrammaticalInflectionManager |
| jobscheduler | hollow | C9 | S | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>1 call sites, e.g. androidx.core.app.JobIntentService$JobWorkEnqueuer.<init> `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2189` |
| keyguard | null | C4 | S | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>1 call sites, e.g. androidx.biometric.KeyguardUtils$Api23Impl.getKeyguardManager |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>1 call sites, e.g. androidx.core.os.UserManagerCompat$Api24Impl.isUserUnlocked `framework/package-manager/java/OHUserManager.java:82` |
| wifi | null | C4 | S | communication/wifi | Android WifiManager facade over communication/wifi<br>1 call sites, e.g. androidx.media3.common.util.WifiLockManager$WifiLockManagerInternal.updateWifiLock |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper$Api26Impl.getTextClassifier `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>17 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>4 call sites, e.g. androidx.core.content.pm.ShortcutManagerCompat.getIconDimensionInternal |
| appops | supplied | C0 | verify | unmapped | none<br>6 call sites, e.g. androidx.core.app.AppOpsManagerCompat$Api29Impl.getSystemService |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>2 call sites, e.g. androidx.appcompat.widget.AppCompatReceiveContentHelper.maybeHandleMenuActionViaPerformReceiveContent |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>2 call sites, e.g. androidx.media3.common.util.NetworkTypeObserver.getNetworkTypeFromConnectivityManager |
| display | supplied | C0 | verify | display_manager | none<br>8 call sites, e.g. androidx.camera.camera2.impl.DisplayInfoManager.<init> |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>10 call sites, e.g. androidx.activity.ImmLeaksCleaner.onStateChanged `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>68 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| locale | supplied | C0 | verify | unmapped | none<br>3 call sites, e.g. androidx.appcompat.app.AppCompatDelegate.getLocaleManagerForApplication |
| location | supplied | C0 | verify | location | none<br>1 call sites, e.g. androidx.appcompat.app.TwilightManager.getInstance |
| notification | supplied | C0 | verify | notification (ANS) | none<br>5 call sites, e.g. androidx.core.content.ContextCompat.checkSelfPermission |
| power | supplied | C0 | verify | powermgr | none<br>3 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$AutoBatteryNightModeManager.<init> |
| uimode | supplied | C0 | verify | display / theme | none<br>7 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.mapNightMode |
| window | supplied | C0 | verify | window_manager | none<br>12 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.openPanel `framework/core/java/OHServiceManager.java:96` |

## Keystore & crypto providers

_JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Android keystore provider ("AndroidKeyStore") | supplied | C0 | verify | security/huks (OH Universal Keystore); keystore2 has no OH counterpart | install an "AndroidKeyStore" provider whose keys come from KeyGenParameterSpec and stay per app: software keys in app data (days), or OH HUKS for hardware-backed keys (weeks). A blocker wherever the app opens it at startup (secure storage, encrypted preferences, biometric crypto, attestation)<br>1 classes name it, e.g. Landroidx/biometric/CryptoObjectUtils;; calls KeyGenerator.getInstance("AES"), KeyStore.getInstance("AndroidKeyStore") `framework/core/java/SoftwareAndroidKeyStore.java:65` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| PackageManager.queryBroadcastReceivers | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1233` |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1226` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1254` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1728` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1716` |
| Content providers installed at bind (1, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>InitializationProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>3 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

## Activity, window & process contracts

_what system_server would answer, answered in-process by Westlake in direct launch → white-box probes_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Dialogs stack above their activity's window, whatever the add order | supplied | C0 | verify | window_manager (sub-window z-order: creation order) | stack a base application window below the dialogs already attached to its token<br>app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added before the activity's own window `framework/window/java/WindowSessionAdapter.java:370` — probe: `probes/dialog-before-window` |
| Windows placed by LayoutParams gravity and x/y (dialogs centred) | supplied | C0 | verify | window_manager (session rect) | compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:346` — probe: `probes/dialog-before-window` |
| FLAG_DIM_BEHIND dims what is under a dialog | supplied | C0 | verify | render_service (a layer under the window) | draw a dim layer of dimAmount under the window (OH has no dim flag)<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:84` — probe: `probes/dialog-before-window` |

## Framework natives

_platform classes the app uses → their native methods → libraries the runtime registers them from_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| android.media.MediaDrm: 43 of 43 natives unregistered | missing | C3 | L | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.drm.DrmManagerClient: 19 of 19 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: _acquireDrmInfo(ILandroid/drm/DrmInfoRequest;)Landroid/drm/DrmInfo;, _canHandle(ILjava/lang/String;Ljava/lang/String;)Z, _checkRightsStatus(ILjava/lang/String;I)I, _closeConvertSession(II)Landroid/drm/DrmConvertedStatus;, _convertData(II[B)Landroid/drm/DrmConvertedStatus;, _getAllSupportInfo(I)[Landroid/drm/DrmSupportInfo;, _getConstraints(ILjava/lang/String;I)Landroid/content/ContentValues;, _getDrmObjectType(ILjava/lang/String;Ljava/lang/String;)I |
| android.hardware.Camera: 29 of 29 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: _addCallbackBuffer([BI)V, _enableShutterSound(Z)Z, _getCameraInfo(IIIILandroid/hardware/Camera$CameraInfo;)V, _getNumberOfCameras(II)I, _startFaceDetection(I)V, _stopFaceDetection()V, _stopPreview()V, enableFocusMoveCallback(I)V |
| android.hardware.camera2.DngCreator: 9 of 9 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeClassInit()V, nativeInit(Landroid/hardware/camera2/impl/CameraMetadataNative;Landroid/hardware/camera2/impl/CameraMetadataNative;Ljava/lang/String;)V |
| android.media.AudioRecord: 27 of 27 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_disableDeviceCallback()V, native_enableDeviceCallback()V, native_finalize()V, native_getMetrics()Landroid/os/PersistableBundle;, native_getPortId()I, native_getRoutedDeviceId()I, native_get_active_microphones(Ljava/util/ArrayList;)I, native_get_buffer_size_in_frames()I |
| android.media.ImageReader: 10 of 10 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeClassInit()V, nativeInit(Ljava/lang/Object;IIIJII)V |
| android.media.ImageWriter: 8 of 8 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeClassInit()V, nativeInit(Ljava/lang/Object;Landroid/view/Surface;IIIZIIJ)J |
| android.media.MediaExtractor: 26 of 26 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.media.MediaMetadataRetriever: 13 of 13 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.media.MediaMuxer: 8 of 8 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeAddTrack(J[Ljava/lang/String;[Ljava/lang/Object;)I, nativeRelease(J)V, nativeSetLocation(JII)V, nativeSetOrientationHint(JI)V, nativeSetup(Ljava/io/FileDescriptor;I)J, nativeStart(J)V, nativeStop(J)V, nativeWriteSampleData(JILjava/nio/ByteBuffer;IIJI)V |
| android.media.CamcorderProfile: 4 of 4 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.opengl.GLUtils: 4 of 4 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_getInternalFormat(Landroid/graphics/Bitmap;)I, native_getType(Landroid/graphics/Bitmap;)I, native_texImage2D(IIILandroid/graphics/Bitmap;II)I, native_texSubImage2D(IIIILandroid/graphics/Bitmap;II)I |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |
| Libraries mapped straight out of the APK (2 .so, extractNativeLibs=false) | supplied | C0 | verify | OH dynamic linker (cannot map zip!/ members: board test 2026-09-18) | extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too) `manifest/tools/prepare_app.py:75` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create lnk_file in app data | denied | C5 | M | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>java.nio.file.Files:createSymbolicLink `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## Limits of this map

- 29 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'newer-than-reference': 20, 'absent-from-platform': 5}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
