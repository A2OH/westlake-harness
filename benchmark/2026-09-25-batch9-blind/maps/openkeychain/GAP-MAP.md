# org.sufficientlysecure.keychain 6.0.4 → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `1baca65181`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 34.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 11 | 11 | 11×verify |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 22 | 7 | 1×verify, 5×S, 1×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 0 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 7 | 6 | 1×verify, 2×S, 2×M, 1×L |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 4 | 0 | — |
| Windows & surfaces | how the first screen renders → whether it needs a surface of its own → OH window/surface model | 0 | 0 | — |
| Framework natives | platform classes the app uses → their native methods → libraries the runtime registers them from | 4 | 4 | 1×S, 2×M, 1×L |
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
| `jni:android.hardware.Camera` | missing | opencamera (loop-1), open |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | hollow-candidate | C9 | verify | window_manager / render_service | check each hollow body against AOSP<br>android.view.ActionProvider.hasSubMenu, android.view.ActionProvider.isVisible, android.view.ActionProvider.onPerformDefaultAction |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.drawable.Drawable$ConstantState.canApplyTheme, android.graphics.drawable.Drawable.applyTheme, android.graphics.drawable.Drawable.canApplyTheme |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayInputStream.close, java.io.ByteArrayOutputStream.close, java.io.InputStream.available |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.ActionBar.getThemedContext, android.app.ActionBar.setHomeActionContentDescription, android.app.ActionBar.setHomeAsUpIndicator |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.AutoCompleteTextView.onFinishInflate, android.widget.BaseAdapter.getItemViewType |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| Job scheduling | hollow-candidate | C9 | verify | resourceschedule/work_scheduler | check each hollow body against AOSP<br>android.app.job.JobService.onCreate, android.app.job.JobService.onDestroy |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.AsyncTask.onPostExecute, android.os.AsyncTask.onPreExecute |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.isRestricted |
| Java extensions | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>javax.security.auth.Destroyable.isDestroyed |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>androidx.work.impl.background.gcm.GcmScheduler, kotlin.internal.JRE7PlatformImplementations, kotlin.internal.JRE8PlatformImplementations |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| usb | null | C4 | M | usb_manager | Android UsbManager facade over usb_manager<br>3 call sites, e.g. org.sufficientlysecure.keychain.securitytoken.UsbConnectionDispatcher.<init> |
| audio | hollow | C9 | S | audio_framework | replace the hollow binder with an implementation over audio_framework<br>1 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.onKeyUpPanel `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1627` |
| jobscheduler | hollow | C9 | S | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>3 call sites, e.g. androidx.work.impl.background.systemjob.SystemJobScheduler.<init> `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2189` |
| sensor | inert | C4 | S | sensors | Android SensorManager facade over sensors<br>2 call sites, e.g. com.google.zxing.client.android.AmbientLightManager.start |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>1 call sites, e.g. androidx.core.os.UserManagerCompat$Api24Impl.isUserUnlocked `framework/package-manager/java/OHUserManager.java:82` |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>1 call sites, e.g. com.google.zxing.client.android.BeepManager.playBeepSoundAndVibrate |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper$Api26Impl.getTextClassifier `SystemServiceRegistry.java:413` |
| PassphraseCacheService: Sending message failed | not-a-platform-service | C5 | none | none | none (null on Android too)<br>1 call sites, e.g. org.sufficientlysecure.keychain.service.PassphraseCacheService.onStartCommand |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>7 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>3 call sites, e.g. androidx.room.RoomDatabase$JournalMode.resolve$room_runtime_release |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>4 call sites, e.g. androidx.work.impl.background.systemalarm.Alarms.cancelExactAlarm |
| appops | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. androidx.core.app.AppOpsManagerCompat$Api29Impl.getSystemService |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>9 call sites, e.g. androidx.appcompat.widget.AppCompatReceiveContentHelper.maybeHandleMenuActionViaPerformReceiveContent |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>2 call sites, e.g. androidx.work.impl.constraints.trackers.NetworkStateTracker24.<init> |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>24 call sites, e.g. com.google.android.material.internal.ViewUtils.getInputMethodManager `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>92 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| locale | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. androidx.appcompat.app.AppCompatDelegate.getLocaleManagerForApplication |
| location | supplied | C0 | verify | location | none<br>1 call sites, e.g. androidx.appcompat.app.TwilightManager.getInstance |
| notification | supplied | C0 | verify | notification (ANS) | none<br>5 call sites, e.g. androidx.core.app.NotificationManagerCompat.<init> |
| power | supplied | C0 | verify | powermgr | none<br>2 call sites, e.g. androidx.work.impl.utils.WakeLocks.newWakeLock |
| uimode | supplied | C0 | verify | display / theme | none<br>1 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.mapNightMode |
| window | supplied | C0 | verify | window_manager | none<br>11 call sites, e.g. androidx.appcompat.view.menu.MenuPopupHelper.createPopup `framework/core/java/OHServiceManager.java:96` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Components in secondary processes: :UsbEventReceiverActivityProcess, :passphrase_cache, :remote_api, :remote_api_2, :remote_ssh_api | missing | C4 | L | appspawn (second process) | spawn and route secondary Android processes |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1226` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1254` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1728` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1716` |
| Content providers installed at bind (4, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>KeychainProvider, KeychainExternalProvider, TemporaryFileProvider, InitializationProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>15 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

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
| android.media.MediaPlayer: 49 of 49 natives unregistered | missing | C3 | L | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.hardware.Camera: 29 of 29 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: setDisplayOrientation(I)V, setPreviewTexture(Landroid/graphics/SurfaceTexture;)V, startPreview()V |
| android.hardware.usb.UsbDeviceConnection: 13 of 13 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_bulk_request(I[BIII)I, native_claim_interface(IZ)Z, native_close()V, native_control_request(IIII[BIII)I, native_get_desc()[B, native_get_fd()I, native_get_serial()Ljava/lang/String;, native_open(Ljava/lang/String;Ljava/io/FileDescriptor;)Z |
| android.hardware.usb.UsbDevice: 2 of 2 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_get_device_id(Ljava/lang/String;)I, native_get_device_name(I)Ljava/lang/String; |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |

## Limits of this map

- 7 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 8}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
