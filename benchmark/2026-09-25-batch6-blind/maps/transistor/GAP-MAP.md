# org.y20k.transistor 4.3.9 → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `2b21e1200d`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 37.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 10 | 10 | 8×verify, 2×S |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 26 | 8 | 2×verify, 3×S, 3×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 0 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 7 | 6 | 1×verify, 2×S, 3×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 4 | 0 | — |
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

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | missing | C4 | S | window_manager / render_service | implement the members over window_manager / render_service<br>android.view.accessibility.AccessibilityNodeInfo$AccessibilityAction.ACTION_SET_EXTENDED_SELECTION |
| App framework | missing | C4 | S | ability_runtime | implement the members over ability_runtime<br>android.app.Notification$Action$Builder.setEmphasisHint, android.app.Notification$Action$Builder.setStyleHint |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.drawable.Drawable$ConstantState.canApplyTheme, android.graphics.drawable.Drawable.applyTheme, android.graphics.drawable.Drawable.canApplyTheme |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayInputStream.close, java.io.ByteArrayOutputStream.close, java.io.InputStream.available |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| Networking | hollow-candidate | C9 | verify | netmanager | check each hollow body against AOSP<br>android.net.ConnectivityManager$NetworkCallback.onAvailable, android.net.ConnectivityManager$NetworkCallback.onBlockedStatusChanged, android.net.ConnectivityManager$NetworkCallback.onCapabilitiesChanged |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.Handler.handleMessage, android.os.IBinder.getSuggestedMaxIpcSizeBytes |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.TextView.onTextChanged |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.isRestricted |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>androidx.media3.datasource.rtmp.RtmpDataSource, androidx.media3.decoder.flac.FlacExtractor, androidx.media3.decoder.flac.FlacLibrary |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>3 call sites, e.g. a7.u `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1627` |
| download | inert | C4 | M | miscservices/download_server | Android DownloadManager facade over miscservices/download_server<br>1 call sites, e.g. g50.K |
| jobscheduler | hollow | C9 | M | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>3 call sites, e.g. oq0.a `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2189` |
| media_metrics | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. zb.run |
| phone | inert | C4 | S | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>2 call sites, e.g. k3.run |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>1 call sites, e.g. vc0.run `framework/package-manager/java/OHUserManager.java:82` |
| captioning | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. v31.j `SystemServiceRegistry.java:337` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. a8.a `SystemServiceRegistry.java:413` |
| ArgUpdateImages | not-a-platform-service | C5 | none | none | none (null on Android too)<br>1 call sites, e.g. org.y20k.transistor.SettingsFragment.b |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>9 call sites, e.g. a52.onHover |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>1 call sites, e.g. ey0.setCheckedState |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>4 call sites, e.g. gi0.h |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>1 call sites, e.g. vc0.c |
| appops | supplied | C0 | verify | unmapped | none<br>1 call sites, e.g. qa2.f |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>4 call sites, e.g. e7.onTextContextMenuItem |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>5 call sites, e.g. l51.run |
| display | supplied | C0 | verify | display_manager | none<br>3 call sites, e.g. bi0.p |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>10 call sites, e.g. k8.onDetachedFromWindow `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>31 call sites, e.g. a52.c `SystemServiceRegistry.java:593` |
| locale | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. h6.run |
| location | supplied | C0 | verify | location | none<br>1 call sites, e.g. a7.y |
| notification | supplied | C0 | verify | notification (ANS) | none<br>4 call sites, e.g. androidx.work.impl.foreground.SystemForegroundService.b |
| power | supplied | C0 | verify | powermgr | none<br>3 call sites, e.g. w6.<init> |
| shortcut | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. ip0.n |
| uimode | supplied | C0 | verify | display / theme | none<br>2 call sites, e.g. a7.C |
| window | supplied | C0 | verify | window_manager | none<br>9 call sites, e.g. a52.a `framework/core/java/OHServiceManager.java:96` |

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
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>3 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

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
| android.media.MediaExtractor: 26 of 26 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.media.MediaMetadataRetriever: 13 of 13 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |

## Limits of this map

- 3 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 1, 'newer-than-reference': 11}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
