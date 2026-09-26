# cx.ring 20260807-01 → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `e2524b1a86` (+5 uncommitted files); OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 37.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 11 | 11 | 8×verify, 3×S |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 28 | 12 | 2×verify, 8×S, 2×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 1 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 7 | 6 | 1×verify, 2×S, 3×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 3 | 0 | — |
| Windows & surfaces | how the first screen renders → whether it needs a surface of its own → OH window/surface model | 0 | 0 | — |
| Framework natives | platform classes the app uses → their native methods → libraries the runtime registers them from | 12 | 12 | 1×S, 8×M, 3×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 1 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 5 | 4 | 2×S, 1×M, 1×L |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 3 | 2 | 1×verify, 1×XS |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 2 | 2 | 1×M, 1×OH |
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
| `jni:android.hardware.Camera` | missing | opencamera (loop-1), open |
| `load:shadowed-by-board` | missing | burgerking (blind-bk), fixed in launcher --android-native-target |
| `jca:AndroidKeyStore` | supplied | burgerking (blind-bk), fixed in 21fdcda |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | missing | C4 | S | window_manager / render_service | implement the members over window_manager / render_service<br>android.view.accessibility.AccessibilityNodeInfo$AccessibilityAction.ACTION_SET_EXTENDED_SELECTION |
| Graphics | missing | C4 | S | render_service / graphic_2d | implement the members over render_service / graphic_2d<br>android.graphics.pdf.PdfRenderer, android.graphics.pdf.PdfRenderer$Page |
| App framework | missing | C4 | S | ability_runtime | implement the members over ability_runtime<br>android.app.Notification$Action$Builder.setEmphasisHint, android.app.Notification$Action$Builder.setStyleHint |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayOutputStream.close, java.io.InputStream.available, java.io.InputStream.close |
| Camera | hollow-candidate | C9 | verify | multimedia/camera_framework | check each hollow body against AOSP<br>android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureBufferLost, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureCompleted, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureFailed |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.getAttributionTag, android.content.Context.isRestricted, android.content.Loader.onReset |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.TextView.onTextChanged |
| Media store | hollow-candidate | C9 | verify | multimedia/media_library | check each hollow body against AOSP<br>android.provider.MediaStore.getPickImagesMaxLimit |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>No default CameraXConfig.Provider specified in meta-data. The most likely cause is you did not include a default implementation in your build such as 'camera-camera2'., androidx.window.extensions.WindowExtensions, androidx.window.extensions.WindowExtensionsProvider |
| Java extensions | probe-only | C8 | verify | none (library code inside Westlake) | confirm the probed class should (not) exist on this platform<br>javax.persistence.Entity |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>7 call sites, e.g. androidx.leanback.widget.GridLayoutManager.q1 `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1627` |
| camera | inert | C4 | M | multimedia/camera_framework | Android CameraManager facade over multimedia/camera_framework<br>7 call sites, e.g. ax.<init> |
| biometric | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. jo.b |
| device_policy | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. xq0.get |
| jobscheduler | hollow | C9 | S | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>2 call sites, e.g. cx.ring.application.a.e `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2189` |
| keyguard | null | C4 | S | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>1 call sites, e.g. l42.a |
| media_projection | inert | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. av.G1 |
| sensor | inert | C4 | S | sensors | Android SensorManager facade over sensors<br>2 call sites, e.g. com.google.zxing.client.android.AmbientLightManager.start |
| telecom | inert | C5 | S | unmapped | truthful local manager (feature absent)<br>3 call sites, e.g. e22.run |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>1 call sites, e.g. com.google.zxing.client.android.BeepManager.playBeepSoundAndVibrate |
| bluetooth | unresolved | CU | verify | communication/bluetooth | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. yp.<init> `BluetoothFrameworkInitializer.java:100` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. me.a `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>18 call sites, e.g. am0.y |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>1 call sites, e.g. com.google.android.material.checkbox.MaterialCheckBox.setCheckedState |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>3 call sites, e.g. cx.ring.client.LogsActivity.K |
| appops | supplied | C0 | verify | unmapped | none<br>1 call sites, e.g. iz.d |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>5 call sites, e.g. av2.f |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>5 call sites, e.g. cx.ring.service.DRingService.onCreate |
| display | supplied | C0 | verify | display_manager | none<br>2 call sites, e.g. androidx.camera.view.PreviewView.getDisplayManager |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>26 call sites, e.g. an1.onEditorAction `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>83 call sites, e.g. a92.<init> `SystemServiceRegistry.java:593` |
| locale | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. vc.run |
| location | supplied | C0 | verify | location | none<br>2 call sites, e.g. cx.ring.service.LocationSharingService.onCreate |
| notification | supplied | C0 | verify | notification (ANS) | none<br>2 call sites, e.g. bo2.<init> |
| power | supplied | C0 | verify | powermgr | none<br>5 call sites, e.g. av.B0 |
| shortcut | supplied | C0 | verify | unmapped | none<br>4 call sites, e.g. pr1.a |
| uimode | supplied | C0 | verify | display / theme | none<br>2 call sites, e.g. nd.C |
| window | supplied | C0 | verify | window_manager | none<br>17 call sites, e.g. av.G1 `framework/core/java/OHServiceManager.java:96` |

## Keystore & crypto providers

_JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Android keystore provider ("AndroidKeyStore") | supplied | C0 | verify | security/huks (OH Universal Keystore); keystore2 has no OH counterpart | install an "AndroidKeyStore" provider whose keys come from KeyGenParameterSpec and stay per app: software keys in app data (days), or OH HUKS for hardware-backed keys (weeks). A blocker wherever the app opens it at startup (secure storage, encrypted preferences, biometric crypto, attestation)<br>5 classes name it, e.g. Lff;, Lgo;, Lkg;, Ltp0;; calls KeyGenerator.getInstance("AES"), KeyStore.getInstance("AndroidKeyStore") `framework/core/java/SoftwareAndroidKeyStore.java:65` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| PackageManager.queryBroadcastReceivers | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1233` |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1226` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1254` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1728` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1716` |
| Content providers installed at bind (2, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>FileProvider, InitializationProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>5 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

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
| android.media.MediaPlayer: 49 of 49 natives unregistered | missing | C3 | L | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.renderscript.RenderScript: 128 of 128 natives unregistered | missing | C3 | L | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: _nInit()V, nContextDeinitToClient(J)V, nContextGetErrorMessage(J)Ljava/lang/String;, nContextGetUserMessage(J[I)I, nContextInitToClient(J)V, nContextPeekMessage(J[I)I, nDeviceCreate()J, nDeviceDestroy(J)V |
| android.hardware.Camera: 29 of 29 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: setDisplayOrientation(I)V, setPreviewTexture(Landroid/graphics/SurfaceTexture;)V, startPreview()V, unlock()V |
| android.hardware.camera2.DngCreator: 9 of 9 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeClassInit()V, nativeInit(Landroid/hardware/camera2/impl/CameraMetadataNative;Landroid/hardware/camera2/impl/CameraMetadataNative;Ljava/lang/String;)V |
| android.media.ImageReader: 10 of 10 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeClassInit()V, nativeInit(Ljava/lang/Object;IIIJII)V |
| android.media.ImageWriter: 8 of 8 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeClassInit()V, nativeInit(Ljava/lang/Object;Landroid/view/Surface;IIIZIIJ)J |
| android.media.MediaExtractor: 26 of 26 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.media.MediaMetadataRetriever: 13 of 13 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.media.MediaMuxer: 8 of 8 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeAddTrack(J[Ljava/lang/String;[Ljava/lang/Object;)I, nativeRelease(J)V, nativeSetLocation(JII)V, nativeSetOrientationHint(JI)V, nativeSetup(Ljava/io/FileDescriptor;I)J, nativeStart(J)V, nativeStop(J)V, nativeWriteSampleData(JILjava/nio/ByteBuffer;IIJI)V |
| android.media.MediaRecorder: 36 of 36 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.media.CamcorderProfile: 4 of 4 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libjami-core-jni.so → 17 classes, 114 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/media/AudioTrack, android/media/MediaCodec, android/media/MediaCodec$BufferInfo, android/media/MediaCodecInfo |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libmediandk.so entry points looked up by name at runtime, not supplied (30) | unresolved | C1/C2 | L | dlopen("libmediandk.so") + dlsym, resolved against whatever the search path reaches first | supply libmediandk.so's entry points, or confirm the caller degrades without them: this row cannot tell a lookup that happens from a string that is never used<br>30 public NDK symbols of libmediandk.so appear as literals: AMediaCodec_configure, AMediaCodec_createCodecByName, AMediaCodec_createDecoderByType, AMediaCodec_createEncoderByType, AMediaCodec_createPersistentInputSurface, AMediaCodec_delete … — probe: `probes/webview-boundaries measures the search path; resolving each name on the board is what settles whether the lookup would succeed` |
| NDK weld · audio: 22 symbols | missing | C4 | M | audio_framework (OHAudio) | AOSP NDK source above, audio_framework (OHAudio) below<br>open: AAudioStreamBuilder_delete, AAudioStreamBuilder_openStream, AAudioStreamBuilder_setDataCallback, AAudioStreamBuilder_setDirection, AAudioStreamBuilder_setErrorCallback, AAudioStreamBuilder_setFormat, AAudioStreamBuilder_setPerformanceMode, AAudioStreamBuilder_setSharingMode |
| bionic libc ABI: 1 symbols to translate onto musl | missing | C1/C2 | S | OH musl libc | bionic-ABI shim: forward or translate; never ship a second libc<br>open: getprogname |
| libaaudio.so entry points looked up by name at runtime, not supplied (3) | unresolved | C1/C2 | S | dlopen("libaaudio.so") + dlsym, resolved against whatever the search path reaches first | supply libaaudio.so's entry points, or confirm the caller degrades without them: this row cannot tell a lookup that happens from a string that is never used<br>3 public NDK symbols of libaaudio.so appear as literals: AAudioStreamBuilder_setContentType, AAudioStreamBuilder_setInputPreset, AAudioStreamBuilder_setUsage — probe: `probes/webview-boundaries measures the search path; resolving each name on the board is what settles whether the lookup would succeed` |
| libc calls carrying a constant each libc numbers differently (pathconf, sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>pathconf: 1 libraries, e.g. libc++_shared.so; sysconf: 2 libraries, e.g. libc++_shared.so, libjami-core-jni.so `framework/webview-shim/webview_bionic_shim.c:1308` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Packaged libraries a board library of the same name shadows (libc++_shared.so) | missing | C3 | XS | OH dynamic linker search order: /system/lib64/libc++_shared.so comes before the app's library directory | load these 2 libraries in the isolated Android namespace so DT_NEEDED picks the APK's copy (e.g. NDK libc++_shared is std::__ndk1; OH's is not): libc++_shared.so libjami-core-jni.so<br>2 APK libraries reach them through DT_NEEDED `manifest/tools/probe_source_app.py:44` |
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |
| Libraries mapped straight out of the APK (4 .so, extractNativeLibs=false) | supplied | C0 | verify | OH dynamic linker (cannot map zip!/ members: board test 2026-09-18) | extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too) `manifest/tools/prepare_app.py:75` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create fifo_file in app data | denied | C4 | OH | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | allow hap_domain normal_hap_data_file_attr:fifo_file { create read write open lock unlink map setattr getattr rename }; (no neverallow in hap_domain.te blocks it) \| bring-up workaround: label the staged app-data tree data_app_el2_file: kernel grants normal_hap dir/file/fifo_file/sock_file there (still no lnk_file)<br>libjami-core-jni.so:mkfifo, libjami-core-jni.so:mknod `sepolicy/ohos_policy/bundlemanager/bundle_framework/system/installs.te:199 allow hap_domain data_app_el2_file:fifo_file { create read write open lock unlink map setattr getattr rename }` |
| Create lnk_file in app data | denied | C5 | M | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>android.system.Os:symlink, libc++_shared.so:symlink, libjami-core-jni.so:symlink `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## Limits of this map

- 5 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 15, 'newer-than-reference': 7}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
