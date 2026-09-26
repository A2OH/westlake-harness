# io.element.android.x 26.09.1 → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `1baca65181`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 37.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 14 | 14 | 11×verify, 2×S, 1×M |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 31 | 14 | 3×verify, 6×S, 5×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 1 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 8 | 7 | 1×verify, 3×S, 3×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 5 | 1 | 1×L |
| Windows & surfaces | how the first screen renders → whether it needs a surface of its own → OH window/surface model | 0 | 0 | — |
| Framework natives | platform classes the app uses → their native methods → libraries the runtime registers them from | 11 | 11 | 3×S, 6×M, 2×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 6 | 1 | 1×verify |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 2 | 1 | 1×S |
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
| `svc:wifi` | supplied | openhab (batch-7), fixed in 8eb6ba4 |
| `jca:AndroidKeyStore` | supplied | burgerking (blind-bk), fixed in 21fdcda |
| `wv:renderer-process` | missing | burgerking (blind-bk), open |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | missing | C4 | M | window_manager / render_service | implement the members over window_manager / render_service<br>android.view.accessibility.AccessibilityEvent.getTextChangeTypes, android.view.accessibility.AccessibilityEvent.setTextChangeTypes, android.view.accessibility.AccessibilityNodeInfo$AccessibilityAction.ACTION_SET_EXTENDED_SELECTION |
| Graphics | missing | C4 | S | render_service / graphic_2d | implement the members over render_service / graphic_2d<br>android.graphics.pdf.PdfRenderer, android.graphics.pdf.PdfRenderer$Page |
| Networking | missing | C4 | S | netmanager | implement the members over netmanager<br>android.net.ssl.SSLSockets.setEchConfigList |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayInputStream.close, java.io.ByteArrayOutputStream.close, java.io.InputStream.available |
| Camera | hollow-candidate | C9 | verify | multimedia/camera_framework | check each hollow body against AOSP<br>android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureBufferLost, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureCompleted, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureFailed |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.Activity.onActivityResult, android.app.Activity.onCreateContextMenu, android.app.Activity.onCreateView |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.setTarget, android.animation.Animator.start |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.AsyncTask.onPostExecute, android.os.Handler.handleMessage, android.os.IBinder.getSuggestedMaxIpcSizeBytes |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.getAttributionTag, android.content.Context.isRestricted |
| Media | hollow-candidate | C9 | verify | multimedia | check each hollow body against AOSP<br>android.media.DrmInitData.getSchemeInitDataCount, android.media.projection.MediaProjection$Callback.onStop |
| WebView | hollow-candidate | C9 | verify | web (ArkWeb) or bundled Chromium | check each hollow body against AOSP<br>android.webkit.WebViewClient.onPageStarted, android.webkit.WebViewClient.onReceivedHttpError |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.TextView.onTextChanged |
| Media store | hollow-candidate | C9 | verify | multimedia/media_library | check each hollow body against AOSP<br>android.provider.MediaStore.getPickImagesMaxLimit |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>No default CameraXConfig.Provider specified in meta-data. The most likely cause is you did not include a default implementation in your build such as 'camera-camera2'., androidx.datastore.preferences.protobuf.DescriptorMessageInfoFactory, androidx.datastore.preferences.protobuf.ExtensionRegistry |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>7 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.dispatchKeyEvent `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1627` |
| camera | inert | C4 | M | multimedia/camera_framework | Android CameraManager facade over multimedia/camera_framework<br>5 call sites, e.g. androidx.camera.camera2.adapter.PipeCameraPresenceSource.<init> |
| jobscheduler | hollow | C9 | M | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>4 call sites, e.g. androidx.media3.exoplayer.scheduler.PlatformScheduler.<init> `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2189` |
| phone | inert | C4 | M | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>3 call sites, e.g. androidx.media3.common.util.NetworkTypeObserver$Api31.disambiguate4gAnd5gNsa |
| sensor | inert | C4 | M | sensors | Android SensorManager facade over sensors<br>3 call sites, e.g. androidx.media3.exoplayer.video.spherical.SphericalGLSurfaceView.<init> |
| biometric | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.biometric.BiometricManager$Api29Impl.create |
| device_policy | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. okio.PriorityQueue.get |
| keyguard | null | C4 | S | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>2 call sites, e.g. androidx.biometric.KeyguardUtils$Api23Impl.getKeyguardManager |
| media_metrics | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. androidx.media3.exoplayer.analytics.MediaMetricsListener.create |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>1 call sites, e.g. androidx.work.impl.utils.ForceStopRunnable.run `framework/package-manager/java/OHUserManager.java:82` |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>1 call sites, e.g. coil3.util.BitmapsKt.vibrate$default |
| captioning | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>3 call sites, e.g. androidx.media3.exoplayer.trackselection.DefaultTrackSelector.getPreferredLanguageFromCaptioningManager `SystemServiceRegistry.java:337` |
| profiling | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. io.sentry.android.core.PerfettoProfiler.<init> `ProfilingFrameworkInitializer.java:73` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>2 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper$Api26Impl.getTextClassifier `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>8 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>13 call sites, e.g. androidx.compose.ui.unit.DensityKt.createWorkManager |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>1 call sites, e.g. androidx.work.impl.utils.ForceStopRunnable.setAlarm |
| appops | supplied | C0 | verify | unmapped | none<br>1 call sites, e.g. androidx.tracing.Trace.checkPermission |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>6 call sites, e.g. androidx.appcompat.widget.AppCompatEditText.onTextContextMenuItem |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>13 call sites, e.g. androidx.media3.common.util.NetworkTypeObserver.getNetworkTypeFromConnectivityManager |
| display | supplied | C0 | verify | display_manager | none<br>5 call sites, e.g. androidx.camera.camera2.impl.DisplayInfoManager.<init> |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>14 call sites, e.g. androidx.appcompat.widget.AppCompatTextView.onDetachedFromWindow `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>31 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| locale | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. androidx.appcompat.app.AppCompatDelegate$$ExternalSyntheticLambda0.run |
| location | supplied | C0 | verify | location | none<br>3 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.getAutoTimeNightModeManager |
| notification | supplied | C0 | verify | notification (ANS) | none<br>6 call sites, e.g. androidx.compose.ui.autofill.PlatformAutofillManagerImpl.createNotification |
| power | supplied | C0 | verify | powermgr | none<br>13 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$AutoTimeNightModeManager.<init> |
| shortcut | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. androidx.core.os.BuildCompat$Api30Impl.disableShortcuts |
| uimode | supplied | C0 | verify | display / theme | none<br>2 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.mapNightMode |
| wifi | supplied | C0 | verify | communication/wifi | none<br>1 call sites, e.g. androidx.media3.common.util.WifiLockManager$WifiLockManagerInternal.updateWifiLock |
| window | supplied | C0 | verify | window_manager | none<br>20 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.closePanel `framework/core/java/OHServiceManager.java:96` |

## Keystore & crypto providers

_JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Android keystore provider ("AndroidKeyStore") | supplied | C0 | verify | security/huks (OH Universal Keystore); keystore2 has no OH counterpart | install an "AndroidKeyStore" provider whose keys come from KeyGenParameterSpec and stay per app: software keys in app data (days), or OH HUKS for hardware-backed keys (weeks). A blocker wherever the app opens it at startup (secure storage, encrypted preferences, biometric crypto, attestation)<br>7 classes name it, e.g. Landroidx/biometric/BiometricManager;, Lcom/google/crypto/tink/integration/android/AndroidKeystore;, Ldev/chrisbanes/haze/Pool;, Lio/element/android/libraries/cryptography/impl/KeyStoreSecretKeyRepository$MetroFactory;; calls KeyGenerator.getInstance("AES"), KeyStore.getInstance("AndroidKeyStore") `framework/core/java/SoftwareAndroidKeyStore.java:65` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| PackageManager.queryBroadcastReceivers | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1233` |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1226` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1254` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1728` |
| PackageManager.getInstallerPackageName | stub | C9 | S | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1522` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1716` |
| Content providers installed at bind (7, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>InitializationProvider, FileProvider, NotificationsFileProvider, AndroidContextProvider, SentryInitProvider, SentryPerformanceProvider@200, SentryNdkPreloadProvider@2000000000 — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>5 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

## Activity, window & process contracts

_what system_server would answer, answered in-process by Westlake in direct launch → white-box probes_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| WebView's renderer runs in an isolated service process | missing | C4 | L | process spawn (appspawn): an isolated Android service process with its own sandbox | host the renderer: spawn an isolated child and bind Chromium's SandboxedProcessService over a local channel; or build the framework with the update-service flag off so WebView runs single-process<br>app constructs WebViews and calls 16 WebView methods `frameworks-base/core/java/android/webkit/WebViewDelegate.java:215` |
| ActivityManager process-table queries (getRunningAppProcesses, getRunningServices) | supplied | C0 | verify | none (the caller's own process is the answer) | answer with the caller's process: name, pid, uid, foreground importance, its package<br>app calls getRunningAppProcesses, getRunningServices `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1409` — probe: `probes/running-app-processes` |
| Dialogs stack above their activity's window, whatever the add order | supplied | C0 | verify | window_manager (sub-window z-order: creation order) | stack a base application window below the dialogs already attached to its token<br>app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added before the activity's own window `framework/window/java/WindowSessionAdapter.java:370` — probe: `probes/dialog-before-window` |
| Windows placed by LayoutParams gravity and x/y (dialogs centred) | supplied | C0 | verify | window_manager (session rect) | compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:346` — probe: `probes/dialog-before-window` |
| FLAG_DIM_BEHIND dims what is under a dialog | supplied | C0 | verify | render_service (a layer under the window) | draw a dim layer of dimAmount under the window (OH has no dim flag)<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:84` — probe: `probes/dialog-before-window` |

## Framework natives

_platform classes the app uses → their native methods → libraries the runtime registers them from_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| android.media.MediaDrm: 43 of 43 natives unregistered | missing | C3 | L | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.renderscript.RenderScript: 128 of 128 natives unregistered | missing | C3 | L | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: _nInit()V, nContextDeinitToClient(J)V, nContextGetErrorMessage(J)Ljava/lang/String;, nContextGetUserMessage(J[I)I, nContextInitToClient(J)V, nContextPeekMessage(J[I)I, nDeviceCreate()J, nDeviceDestroy(J)V |
| android.hardware.SyncFence: 7 of 7 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nCreate(I)J, nGetDestructor()J, nGetFd(J)I, nGetSignalTime(J)J, nIncRef(J)V, nIsValid(J)Z, nWait(JJ)Z |
| android.media.AudioRecord: 27 of 27 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_disableDeviceCallback()V, native_enableDeviceCallback()V, native_finalize()V, native_getMetrics()Landroid/os/PersistableBundle;, native_getPortId()I, native_getRoutedDeviceId()I, native_get_active_microphones(Ljava/util/ArrayList;)I, native_get_buffer_size_in_frames()I |
| android.media.ImageReader: 10 of 10 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeClassInit()V, nativeInit(Ljava/lang/Object;IIIJII)V |
| android.media.ImageWriter: 8 of 8 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeClassInit()V, nativeInit(Ljava/lang/Object;Landroid/view/Surface;IIIZIIJ)J |
| android.media.MediaMetadataRetriever: 13 of 13 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.media.MediaMuxer: 8 of 8 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeAddTrack(J[Ljava/lang/String;[Ljava/lang/Object;)I, nativeRelease(J)V, nativeSetLocation(JII)V, nativeSetOrientationHint(JI)V, nativeSetup(Ljava/io/FileDescriptor;I)J, nativeStart(J)V, nativeStop(J)V, nativeWriteSampleData(JILjava/nio/ByteBuffer;IIJI)V |
| android.media.CamcorderProfile: 4 of 4 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.media.MediaParser: 1 of 1 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeSubmitMetrics(Ljava/lang/String;Ljava/lang/String;ZLjava/lang/String;Ljava/lang/String;JJLjava/lang/String;Ljava/lang/String;Ljava/lang/String;II)V |
| android.opengl.GLUtils: 4 of 4 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_getInternalFormat(Landroid/graphics/Bitmap;)I, native_getType(Landroid/graphics/Bitmap;)I, native_texImage2D(IIILandroid/graphics/Bitmap;II)I, native_texSubImage2D(IIIILandroid/graphics/Bitmap;II)I |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libsqlcipher.so → 77 classes, 208 members | unresolved | CU | verify | through the Java framework | confirm the library tolerates their absence; watch it under the runtime-integrity checks<br>e.g. android/app/ActivityThread, android/content/Context, android/database/CharArrayBuffer, android/database/sqlite/SQLiteAbortException |
| libandroidx.graphics.path.so → 1 classes, 1 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/graphics/Path |
| libdatastore_shared_counter.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/IOException |
| lib/arm64-v8a/libjnidispatch.so → 28 classes, 116 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Boolean, java/lang/Byte, java/lang/Character, java/lang/Class |
| libmaplibre.so → 26 classes, 132 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/graphics/Bitmap, android/graphics/Bitmap$Config, android/graphics/BitmapFactory, android/graphics/PointF |
| libzxingcpp_android.so → 4 classes, 8 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/graphics/Point, java/lang/RuntimeException, java/util/ArrayList, java/util/Set |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libnativehelper.so entry points looked up by name at runtime, not supplied (1) | unresolved | C1/C2 | S | dlopen("libnativehelper.so") + dlsym, resolved against whatever the search path reaches first | supply libnativehelper.so's entry points, or confirm the caller degrades without them: this row cannot tell a lookup that happens from a string that is never used<br>1 public NDK symbols of libnativehelper.so appear as literals: JNI_GetCreatedJavaVMs — probe: `probes/webview-boundaries measures the search path; resolving each name on the board is what settles whether the lookup would succeed` |
| libc calls carrying a constant each libc numbers differently (pathconf, sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>pathconf: 1 libraries, e.g. libmaplibre.so; sysconf: 5 libraries, e.g. libjnidispatch.so, libmaplibre.so, libmatrix_sdk_ffi.so `framework/webview-shim/webview_bionic_shim.c:1308` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |
| Libraries mapped straight out of the APK (13 .so, extractNativeLibs=false) | supplied | C0 | verify | OH dynamic linker (cannot map zip!/ members: board test 2026-09-18) | extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too) `manifest/tools/prepare_app.py:75` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create lnk_file in app data | denied | C5 | M | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>libmaplibre.so:symlink `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## Limits of this map

- 14 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'newer-than-reference': 14, 'absent-from-platform': 8}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
