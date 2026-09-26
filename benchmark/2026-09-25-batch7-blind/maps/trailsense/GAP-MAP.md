# com.kylecorry.trail_sense 8.2.0 → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `e2524b1a86`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 37.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 13 | 13 | 10×verify, 2×S, 1×M |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 28 | 10 | 2×verify, 4×S, 4×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 0 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 7 | 6 | 1×verify, 2×S, 3×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 4 | 0 | — |
| Windows & surfaces | how the first screen renders → whether it needs a surface of its own → OH window/surface model | 0 | 0 | — |
| Framework natives | platform classes the app uses → their native methods → libraries the runtime registers them from | 8 | 8 | 2×S, 5×M, 1×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 1 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 1 | 0 | — |
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

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| App framework | missing | C4 | M | ability_runtime | implement the members over ability_runtime<br>android.app.Notification$Action$Builder.setEmphasisHint, android.app.Notification$Action$Builder.setStyleHint, android.app.Notification$Action.getEmphasisHint |
| Views & windows | missing | C4 | S | window_manager / render_service | implement the members over window_manager / render_service<br>android.view.accessibility.AccessibilityNodeInfo$AccessibilityAction.ACTION_SET_EXTENDED_SELECTION |
| Graphics | missing | C4 | S | render_service / graphic_2d | implement the members over render_service / graphic_2d<br>android.graphics.pdf.PdfRenderer, android.graphics.pdf.PdfRenderer$Page |
| Camera | hollow-candidate | C9 | verify | multimedia/camera_framework | check each hollow body against AOSP<br>android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureBufferLost, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureCompleted, android.hardware.camera2.CameraCaptureSession$CaptureCallback.onCaptureFailed |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.AutoCompleteTextView.onFinishInflate, android.widget.Button.onTextChanged |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayInputStream.close, java.io.ByteArrayOutputStream.close, java.io.InputStream.available |
| Job scheduling | hollow-candidate | C9 | verify | resourceschedule/work_scheduler | check each hollow body against AOSP<br>android.app.job.JobService.onCreate, android.app.job.JobService.onDestroy |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.getAttributionTag, android.content.Context.isRestricted |
| Location | hollow-candidate | C9 | verify | location | check each hollow body against AOSP<br>android.location.LocationManager.addNmeaListener, android.location.LocationManager.removeNmeaListener |
| Networking | hollow-candidate | C9 | verify | netmanager | check each hollow body against AOSP<br>android.net.ConnectivityManager$NetworkCallback.onBlockedStatusChanged |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.AsyncTask.onPostExecute |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>No default CameraXConfig.Provider specified in meta-data. The most likely cause is you did not include a default implementation in your build such as 'camera-camera2'., kotlin.reflect.jvm.internal.ReflectionFactoryImpl, pl.droidsonroids.gif.GifDrawable |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| camera | inert | C4 | M | multimedia/camera_framework | Android CameraManager facade over multimedia/camera_framework<br>10 call sites, e.g. h90.v |
| jobscheduler | hollow | C9 | M | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>3 call sites, e.g. fn4.a `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2189` |
| phone | inert | C4 | M | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>1 call sites, e.g. hb0.a |
| sensor | inert | C4 | M | sensors | Android SensorManager facade over sensors<br>30 call sites, e.g. su0.K |
| audio | hollow | C9 | S | audio_framework | replace the hollow binder with an implementation over audio_framework<br>2 call sites, e.g. to4.h `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1627` |
| device_policy | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. x5.get |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>1 call sites, e.g. na.x `framework/package-manager/java/OHUserManager.java:82` |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>1 call sites, e.g. bw1.b |
| print | unresolved | CU | verify | print_service | trace the helper's binder; then treat as null, inert or supplied<br>2 call sites, e.g. il3.<init> `SystemServiceRegistry.java:893` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. pa.L `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>19 call sites, e.g. androidx.preference.CheckBoxPreference.t |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>1 call sites, e.g. com.google.android.material.checkbox.MaterialCheckBox.setCheckedState |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>5 call sites, e.g. com.kylecorry.andromeda.views.subscaleview.decoder.SkiaPooledImageRegionDecoder.isLowMemory |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>11 call sites, e.g. cv4.onClick |
| appops | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. xs2.k |
| batterymanager | supplied | C0 | verify | powermgr/battery_manager | none<br>1 call sites, e.g. hj.a |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>6 call sites, e.g. bc.onTextContextMenuItem |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>3 call sites, e.g. ox.<init> |
| display | supplied | C0 | verify | display_manager | none<br>2 call sites, e.g. androidx.camera.view.PreviewView.getDisplayManager |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>14 call sites, e.g. fd.onDetachedFromWindow `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>43 call sites, e.g. androidx.appcompat.view.menu.ListMenuItemView.getInflater `SystemServiceRegistry.java:593` |
| locale | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. ib.run |
| location | supplied | C0 | verify | location | none<br>14 call sites, e.g. com.kylecorry.trail_sense.settings.ui.CalibrateGPSFragment.u0 |
| notification | supplied | C0 | verify | notification (ANS) | none<br>2 call sites, e.g. androidx.work.impl.foreground.SystemForegroundService.a |
| power | supplied | C0 | verify | powermgr | none<br>12 call sites, e.g. com.kylecorry.andromeda.background.DailyWorker.d |
| shortcut | supplied | C0 | verify | unmapped | none<br>1 call sites, e.g. pa.X |
| uimode | supplied | C0 | verify | display / theme | none<br>1 call sites, e.g. vb.B |
| window | supplied | C0 | verify | window_manager | none<br>7 call sites, e.g. gs4.a `framework/core/java/OHServiceManager.java:96` |

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
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>20 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

## Activity, window & process contracts

_what system_server would answer, answered in-process by Westlake in direct launch → white-box probes_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| ActivityManager process-table queries (getRunningAppProcesses) | supplied | C0 | verify | none (the caller's own process is the answer) | answer with the caller's process: name, pid, uid, foreground importance, its package<br>app calls getRunningAppProcesses `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1409` — probe: `probes/running-app-processes` |
| Dialogs stack above their activity's window, whatever the add order | supplied | C0 | verify | window_manager (sub-window z-order: creation order) | stack a base application window below the dialogs already attached to its token<br>app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added before the activity's own window `framework/window/java/WindowSessionAdapter.java:370` — probe: `probes/dialog-before-window` |
| Windows placed by LayoutParams gravity and x/y (dialogs centred) | supplied | C0 | verify | window_manager (session rect) | compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:346` — probe: `probes/dialog-before-window` |
| FLAG_DIM_BEHIND dims what is under a dialog | supplied | C0 | verify | render_service (a layer under the window) | draw a dim layer of dimAmount under the window (OH has no dim flag)<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:84` — probe: `probes/dialog-before-window` |

## Framework natives

_platform classes the app uses → their native methods → libraries the runtime registers them from_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| android.media.MediaDrm: 43 of 43 natives unregistered | missing | C3 | L | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.drm.DrmManagerClient: 19 of 19 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: _acquireDrmInfo(ILandroid/drm/DrmInfoRequest;)Landroid/drm/DrmInfo;, _canHandle(ILjava/lang/String;Ljava/lang/String;)Z, _checkRightsStatus(ILjava/lang/String;I)I, _closeConvertSession(II)Landroid/drm/DrmConvertedStatus;, _convertData(II[B)Landroid/drm/DrmConvertedStatus;, _getAllSupportInfo(I)[Landroid/drm/DrmSupportInfo;, _getConstraints(ILjava/lang/String;I)Landroid/content/ContentValues;, _getDrmObjectType(ILjava/lang/String;Ljava/lang/String;)I |
| android.hardware.camera2.DngCreator: 9 of 9 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeClassInit()V, nativeInit(Landroid/hardware/camera2/impl/CameraMetadataNative;Landroid/hardware/camera2/impl/CameraMetadataNative;Ljava/lang/String;)V |
| android.media.ImageReader: 10 of 10 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeClassInit()V, nativeInit(Ljava/lang/Object;IIIJII)V |
| android.media.ImageWriter: 8 of 8 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeClassInit()V, nativeInit(Ljava/lang/Object;Landroid/view/Surface;IIIZIIJ)J |
| android.media.MediaMetadataRetriever: 13 of 13 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.graphics.pdf.PdfDocument: 5 of 5 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeClose(J)V, nativeCreateDocument()J, nativeFinishPage(J)V, nativeStartPage(JIIIIII)J, nativeWriteTo(JLjava/io/OutputStream;[B)V |
| android.media.CamcorderProfile: 4 of 4 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libdatastore_shared_counter.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/IOException |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libc calls carrying a constant each libc numbers differently (sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>sysconf: 1 libraries, e.g. librenderscript-toolkit.so `framework/webview-shim/webview_bionic_shim.c:1308` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |

## Limits of this map

- 11 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 9, 'newer-than-reference': 9}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
