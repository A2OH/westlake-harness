# org.nsh07.pomodoro 1.8.5 → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `e2524b1a86` (+5 uncommitted files); OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 36.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 6 | 6 | 5×verify, 1×S |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 15 | 4 | 2×verify, 1×S, 1×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 0 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 4 | 3 | 1×verify, 1×S, 1×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 4 | 0 | — |
| Windows & surfaces | how the first screen renders → whether it needs a surface of its own → OH window/surface model | 0 | 0 | — |
| Framework natives | platform classes the app uses → their native methods → libraries the runtime registers them from | 3 | 3 | 1×M, 2×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 1 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 0 | 0 | — |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 2 | 1 | 1×verify |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 0 | 0 | — |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 0 | 0 | — |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Rows that have blocked an app at startup before

From the blockers ledger: gaps this app has in common with an app that died on them.

| Row | Verdict | Blocked |
|---|---|---|
| `svc:jobscheduler` | hollow | gallery (corpus-2), fixed in 886b89b |
| `svc:notification` | supplied | tusky (corpus-2), fixed in 886b89b |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | missing | C4 | S | window_manager / render_service | implement the members over window_manager / render_service<br>android.view.accessibility.AccessibilityNodeInfo$AccessibilityAction.ACTION_SET_EXTENDED_SELECTION |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.Activity.onActivityResult, android.app.Activity.onNewIntent, android.app.Activity.onPictureInPictureUiStateChanged |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.Canvas.disableZ, android.graphics.Canvas.enableZ, android.graphics.Canvas.getMaximumBitmapHeight |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayInputStream.close, java.io.ByteArrayOutputStream.close, java.io.InputStream.available |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.service.quicksettings.TileService.onClick |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>androidx.datastore.preferences.protobuf.DescriptorMessageInfoFactory, androidx.datastore.preferences.protobuf.Extension, androidx.datastore.preferences.protobuf.ExtensionRegistry |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| vibrator | inert | C4 | M | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>2 call sites, e.g. org.nsh07.pomodoro.service.TimerService$$ExternalSyntheticLambda2.invoke |
| jobscheduler | hollow | C9 | S | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>3 call sites, e.g. androidx.work.impl.WorkManagerImpl.rescheduleEligibleWork `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2189` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.compose.material3.internal.BasicTooltipKt$TooltipPopup$1$1$1.invokeSuspend `SystemServiceRegistry.java:413` |
| vibrator_manager | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>2 call sites, e.g. org.nsh07.pomodoro.service.TimerService$$ExternalSyntheticLambda2.invoke `SystemServiceRegistry.java:796` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>3 call sites, e.g. androidx.compose.material3.DefaultHorizontalFloatingToolbarOverride.HorizontalFloatingToolbar |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>2 call sites, e.g. androidx.compose.ui.platform.AndroidComposeView.<init> |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>3 call sites, e.g. androidx.room.RoomDatabase$Builder.build |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>4 call sites, e.g. androidx.work.impl.background.systemalarm.Alarms.cancelExactAlarm |
| appwidget | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. androidx.glance.appwidget.AppWidgetSession.processEmittableTree$suspendImpl |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>1 call sites, e.g. androidx.compose.ui.platform.AndroidClipboardManager.<init> |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>1 call sites, e.g. androidx.work.impl.constraints.trackers.NetworkStateTracker.<init> |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>6 call sites, e.g. androidx.activity.ComponentDialog$$ExternalSyntheticLambda3.run `framework/core/java/OHServiceManager.java:105` |
| notification | supplied | C0 | verify | notification (ANS) | none<br>4 call sites, e.g. androidx.core.app.NotificationManagerCompat.<init> |
| power | supplied | C0 | verify | powermgr | none<br>2 call sites, e.g. androidx.glance.session.IdleEventBroadcastReceiver.checkIdleStatus$glance |
| window | supplied | C0 | verify | window_manager | none<br>7 call sites, e.g. androidx.compose.ui.window.PopupLayout.<init> `framework/core/java/OHServiceManager.java:96` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1254` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1716` |
| Content providers installed at bind (2, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>InitializationProvider, AndroidContextProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>5 components carry meta-data (0 directBootAware, e.g. ); app calls ['getPackageInfo', 'getProviderInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

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
| android.media.MediaPlayer: 49 of 49 natives unregistered | missing | C3 | L | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.media.MediaMetadataRetriever: 13 of 13 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libandroidx.graphics.path.so → 1 classes, 1 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/graphics/Path |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |
| Libraries mapped straight out of the APK (1 .so, extractNativeLibs=false) | supplied | C0 | verify | OH dynamic linker (cannot map zip!/ members: board test 2026-09-18) | extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too) `manifest/tools/prepare_app.py:75` |

## Limits of this map

- 3 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'newer-than-reference': 10, 'absent-from-platform': 2}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
