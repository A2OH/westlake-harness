# net.programmierecke.radiodroid2 0.86 → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `e2524b1a86`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 33.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 10 | 10 | 10×verify |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 29 | 12 | 3×verify, 6×S, 3×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 0 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 5 | 4 | 1×verify, 3×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 3 | 0 | — |
| Windows & surfaces | how the first screen renders → whether it needs a surface of its own → OH window/surface model | 0 | 0 | — |
| Framework natives | platform classes the app uses → their native methods → libraries the runtime registers them from | 5 | 5 | 1×S, 1×M, 3×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 0 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 0 | 0 | — |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 1 | 1 | 1×verify |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 1 | 1 | 1×M |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 0 | 0 | — |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Rows that have blocked an app at startup before

From the blockers ledger: gaps this app has in common with an app that died on them.

| Row | Verdict | Blocked |
|---|---|---|
| `svc:jobscheduler` | hollow | gallery (corpus-2), fixed in 886b89b |
| `svc:notification` | supplied | tusky (corpus-2), fixed in 886b89b |
| `svc:uimode` | supplied | burgerking (blind-bk), fixed in d689e67 |
| `svc:user` | strict | burgerking (blind-bk), fixed in 9b8b861 |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | hollow-candidate | C9 | verify | window_manager / render_service | check each hollow body against AOSP<br>android.view.ActionProvider.hasSubMenu, android.view.ActionProvider.isVisible, android.view.ActionProvider.onPerformDefaultAction |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.Canvas.disableZ, android.graphics.Canvas.enableZ, android.graphics.drawable.Drawable$ConstantState.canApplyTheme |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.Button.onTextChanged, android.widget.EditText.isInEditMode, android.widget.FrameLayout.onConfigurationChanged |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayOutputStream.close, java.io.FileOutputStream.flush, java.io.InputStream.available |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.ActionBar.getThemedContext, android.app.ActionBar.setHomeActionContentDescription, android.app.ActionBar.setHomeAsUpIndicator |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.AsyncTask.onPostExecute, android.os.AsyncTask.onPreExecute, android.os.Handler.handleMessage |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.getAttributionTag, android.content.Context.isRestricted |
| Media | hollow-candidate | C9 | verify | multimedia | check each hollow body against AOSP<br>android.media.DrmInitData.getSchemeInitDataCount |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>androidx.sharetarget.ShortcutInfoCompatSaverImpl, androidx.window.extensions.WindowExtensions, androidx.window.extensions.WindowExtensionsProvider |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>8 call sites, e.g. com.google.android.exoplayer2.util.Util.generateAudioSessionIdV21 `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1627` |
| phone | inert | C4 | M | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>3 call sites, e.g. com.google.android.exoplayer2.util.Util.getCountryCode |
| sensor | inert | C4 | M | sensors | Android SensorManager facade over sensors<br>1 call sites, e.g. com.google.android.exoplayer2.video.spherical.SphericalGLSurfaceView.<init> |
| fingerprint | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. androidx.core.hardware.fingerprint.FingerprintManagerCompat$Api23Impl.getFingerprintManagerOrNull |
| jobscheduler | hollow | C9 | S | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>2 call sites, e.g. androidx.core.app.JobIntentService$JobWorkEnqueuer.<init> `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2189` |
| media_metrics | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. com.google.android.exoplayer2.analytics.MediaMetricsListener.create |
| media_router | inert | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.mediarouter.media.MediaRouterJellybean.getMediaRouter |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>1 call sites, e.g. androidx.core.os.UserManagerCompat$Api24Impl.isUserUnlocked `framework/package-manager/java/OHUserManager.java:82` |
| wifi | null | C4 | S | communication/wifi | Android WifiManager facade over communication/wifi<br>3 call sites, e.g. com.google.android.exoplayer2.WifiLockManager.<init> |
| captioning | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. com.google.android.exoplayer2.trackselection.TrackSelectionParameters$Builder.setPreferredTextLanguageAndRoleFlagsToCaptioningManagerSettingsV19 `SystemServiceRegistry.java:337` |
| print | unresolved | CU | verify | print_service | trace the helper's binder; then treat as null, inert or supplied<br>2 call sites, e.g. androidx.print.PrintHelper.printBitmap `SystemServiceRegistry.java:893` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper$Api26Impl.getTextClassifier `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>17 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>1 call sites, e.g. com.google.android.material.checkbox.MaterialCheckBox.setCheckedState |
| media_session | not-a-platform-service | C5 | none | none | none (null on Android too)<br>1 call sites, e.g. androidx.media.MediaSessionManagerImplApi28.<init> |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>4 call sites, e.g. androidx.core.content.pm.ShortcutManagerCompat.getIconDimensionInternal |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>2 call sites, e.g. net.programmierecke.radiodroid2.alarm.RadioAlarmManager.start |
| appops | supplied | C0 | verify | unmapped | none<br>6 call sites, e.g. androidx.core.app.AppOpsManagerCompat$Api29Impl.getSystemService |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>4 call sites, e.g. androidx.appcompat.widget.AppCompatReceiveContentHelper.maybeHandleMenuActionViaPerformReceiveContent |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>9 call sites, e.g. net.programmierecke.radiodroid2.Utils.hasAnyConnection |
| display | supplied | C0 | verify | display_manager | none<br>7 call sites, e.g. androidx.core.hardware.display.DisplayManagerCompat.getDisplay |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>12 call sites, e.g. androidx.core.view.WindowInsetsControllerCompat$Impl20.hideForType `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>84 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| location | supplied | C0 | verify | location | none<br>1 call sites, e.g. androidx.appcompat.app.TwilightManager.getInstance |
| notification | supplied | C0 | verify | notification (ANS) | none<br>9 call sites, e.g. androidx.core.app.NotificationManagerCompat.<init> |
| power | supplied | C0 | verify | powermgr | none<br>8 call sites, e.g. androidx.legacy.content.WakefulBroadcastReceiver.startWakefulService |
| shortcut | supplied | C0 | verify | unmapped | none<br>24 call sites, e.g. androidx.core.content.pm.ShortcutManagerCompat.addDynamicShortcuts |
| uimode | supplied | C0 | verify | display / theme | none<br>4 call sites, e.g. androidx.core.view.DisplayCompat.isTv |
| window | supplied | C0 | verify | window_manager | none<br>16 call sites, e.g. androidx.appcompat.widget.TooltipPopup.hide `framework/core/java/OHServiceManager.java:96` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| PackageManager.queryBroadcastReceivers | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1233` |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1226` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1254` |
| Content providers installed at bind (4, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>FileProvider, IconicsContentProvider@100, PicassoProvider, InitializationProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>2 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

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
| android.media.ToneGenerator: 6 of 6 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: release()V, startTone(II)Z, stopTone()V |
| android.media.MediaParser: 1 of 1 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeSubmitMetrics(Ljava/lang/String;Ljava/lang/String;ZLjava/lang/String;Ljava/lang/String;JJLjava/lang/String;Ljava/lang/String;Ljava/lang/String;II)V |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create lnk_file in app data | denied | C5 | M | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>java.nio.file.Files:createSymbolicLink `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## Limits of this map

- 7 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 11}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
