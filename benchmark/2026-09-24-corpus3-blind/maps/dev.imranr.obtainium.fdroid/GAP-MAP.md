# dev.imranr.obtainium.fdroid 1.6.17 → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `8fa7346b68`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 36.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 10 | 10 | 8×verify, 2×S |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 22 | 6 | 1×verify, 4×S, 1×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 0 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 25 | 24 | 1×verify, 20×S, 3×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 5 | 1 | 1×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 3 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 3 | 2 | 2×M |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 2 | 1 | 1×verify |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 1 | 1 | 1×M |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 0 | 0 | — |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | missing | C4 | S | window_manager / render_service | implement the members over window_manager / render_service<br>android.view.accessibility.AccessibilityNodeInfo.setChecked |
| Package manager | missing | C4 | S | bundle_framework | implement the members over bundle_framework<br>android.content.pm.PackageInstaller.<init> |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayInputStream.close, java.io.ByteArrayOutputStream.close, java.io.InputStream.available |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.Activity.onNewIntent, android.app.Activity.onWindowFocusChanged, android.app.Dialog.onCreate |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.drawable.Drawable.getConstantState, android.graphics.drawable.Drawable.getIntrinsicHeight, android.graphics.drawable.Drawable.getIntrinsicWidth |
| WebView | hollow-candidate | C9 | verify | web (ArkWeb) or bundled Chromium | check each hollow body against AOSP<br>android.webkit.HttpAuthHandler.cancel, android.webkit.HttpAuthHandler.proceed, android.webkit.HttpAuthHandler.useHttpAuthUsernamePassword |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.getAttributionTag, android.content.Context.isRestricted |
| Networking | hollow-candidate | C9 | verify | netmanager | check each hollow body against AOSP<br>android.net.ConnectivityManager$NetworkCallback.onAvailable, android.net.ConnectivityManager$NetworkCallback.onBlockedStatusChanged |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.database.ContentObserver.onChange |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>androidx.datastore.preferences.protobuf.DescriptorMessageInfoFactory, androidx.datastore.preferences.protobuf.ExtensionRegistry, androidx.datastore.preferences.protobuf.ExtensionSchemaFull |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| jobscheduler | hollow | C9 | M | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>3 call sites, e.g. e6.a `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2162` |
| device_policy | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. x4.t |
| phone | inert | C4 | S | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>1 call sites, e.g. pk.d |
| textservices | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. rl.onCreate |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>1 call sites, e.g. cp.run `framework/package-manager/java/OHUserManager.java:82` |
| bluetooth | unresolved | CU | verify | communication/bluetooth | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. pk.d `BluetoothFrameworkInitializer.java:100` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>1 call sites, e.g. rl.onCreate |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>1 call sites, e.g. io.flutter.plugin.editing.b.<init> |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>5 call sites, e.g. a70.a |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>4 call sites, e.g. b40.a |
| appops | supplied | C0 | verify | unmapped | none<br>1 call sites, e.g. mu0.g |
| batterymanager | supplied | C0 | verify | powermgr/battery_manager | none<br>1 call sites, e.g. l4.l |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>4 call sites, e.g. kt.performContextMenuAction |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>3 call sites, e.g. f10.<init> |
| display | supplied | C0 | verify | display_manager | none<br>6 call sites, e.g. h7.a |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>5 call sites, e.g. androidx.appcompat.widget.SearchView$SearchAutoComplete.setImeVisibility `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>3 call sites, e.g. androidx.appcompat.widget.SearchView.<init> `SystemServiceRegistry.java:593` |
| location | supplied | C0 | verify | location | none<br>1 call sites, e.g. pk.d |
| notification | supplied | C0 | verify | notification (ANS) | none<br>17 call sites, e.g. androidx.work.impl.foreground.SystemForegroundService.b |
| power | supplied | C0 | verify | powermgr | none<br>4 call sites, e.g. b40.a |
| uimode | supplied | C0 | verify | display / theme | none<br>3 call sites, e.g. io.flutter.view.a.<init> |
| window | supplied | C0 | verify | window_manager | none<br>7 call sites, e.g. aa.a `framework/core/java/OHServiceManager.java:96` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1253` |
| PackageManager.queryIntentServices | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1246` |
| PackageManager.resolveService | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1239` |
| PackageManager.canonicalToCurrentPackageNames | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1062` |
| PackageManager.checkSignatures | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:926` |
| PackageManager.currentToCanonicalPackageNames | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1055` |
| PackageManager.getApplicationEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1740` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1727` |
| PackageManager.getInstallSourceInfo | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1528` |
| PackageManager.getInstalledApplications | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1274` |
| PackageManager.getInstallerPackageName | stub | C9 | S | bundle_framework (for other packages) | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1521` |
| PackageManager.getPackageGids | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1048` |
| PackageManager.getPackagesHoldingPermissions | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1267` |
| PackageManager.getSuspendedPackageAppExtras | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1644` |
| PackageManager.getSystemAvailableFeatures | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1814` |
| PackageManager.getSystemSharedLibraryNames | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1807` |
| PackageManager.getTargetSdkVersion | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1069` |
| PackageManager.isSafeMode | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1834` |
| PackageManager.setApplicationCategoryHint | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1497` |
| PackageManager.setApplicationEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1734` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1715` |
| PackageManager.setInstallerPackageName | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1485` |
| PackageManager.verifyPendingInstall | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1934` |
| Content providers installed at bind (4, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>FileProvider, ShizukuProvider, ShareFileProvider, InitializationProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>4 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getReceiverInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

## Activity, window & process contracts

_what system_server would answer, answered in-process by Westlake in direct launch → white-box probes_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| WebView's renderer runs in an isolated service process | missing | C4 | L | process spawn (appspawn): an isolated Android service process with its own sandbox | host the renderer: spawn an isolated child and bind Chromium's SandboxedProcessService over a local channel; or build the framework with the update-service flag off so WebView runs single-process<br>app constructs WebViews and calls 27 WebView methods `frameworks-base/core/java/android/webkit/WebViewDelegate.java:215` |
| ActivityManager process-table queries (getRunningAppProcesses) | supplied | C0 | verify | none (the caller's own process is the answer) | answer with the caller's process: name, pid, uid, foreground importance, its package<br>app calls getRunningAppProcesses `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1409` — probe: `probes/running-app-processes` |
| Dialogs stack above their activity's window, whatever the add order | supplied | C0 | verify | window_manager (sub-window z-order: creation order) | stack a base application window below the dialogs already attached to its token<br>app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added before the activity's own window `framework/window/java/WindowSessionAdapter.java:370` — probe: `probes/dialog-before-window` |
| Windows placed by LayoutParams gravity and x/y (dialogs centred) | supplied | C0 | verify | window_manager (session rect) | compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:346` — probe: `probes/dialog-before-window` |
| FLAG_DIM_BEHIND dims what is under a dialog | supplied | C0 | verify | render_service (a layer under the window) | draw a dim layer of dimAmount under the window (OH has no dim flag)<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:84` — probe: `probes/dialog-before-window` |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libdartjni.so → 5 classes, 10 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/ByteArrayOutputStream, java/io/PrintStream, java/lang/Exception, java/lang/Long |
| libdatastore_shared_counter.so → 1 classes, 0 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/IOException |
| libflutter.so → 14 classes, 36 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/graphics/Bitmap, android/graphics/Bitmap$Config, android/graphics/Path, android/graphics/Path$FillType |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libandroid.so entry points looked up by name at runtime, not supplied (14) | unresolved | C1/C2 | M | dlopen("libandroid.so") + dlsym, resolved against whatever the search path reaches first | supply libandroid.so's entry points, or confirm the caller degrades without them: this row cannot tell a lookup that happens from a string that is never used<br>14 public NDK symbols of libandroid.so appear as literals: AChoreographer_getInstance, AChoreographer_postFrameCallback, AChoreographer_postFrameCallback64, AHardwareBuffer_fromHardwareBuffer, ASurfaceControl_createFromWindow, ASurfaceControl_release … — probe: `probes/webview-boundaries measures the search path; resolving each name on the board is what settles whether the lookup would succeed` |
| libnativewindow.so entry points looked up by name at runtime, not supplied (6) | unresolved | C1/C2 | M | dlopen("libnativewindow.so") + dlsym, resolved against whatever the search path reaches first | supply libnativewindow.so's entry points, or confirm the caller degrades without them: this row cannot tell a lookup that happens from a string that is never used<br>6 public NDK symbols of libnativewindow.so appear as literals: AHardwareBuffer_describe, AHardwareBuffer_getId, AHardwareBuffer_isSupported, AHardwareBuffer_lock, AHardwareBuffer_unlock, ANativeWindow_acquire — probe: `probes/webview-boundaries measures the search path; resolving each name on the board is what settles whether the lookup would succeed` |
| libc calls carrying a constant each libc numbers differently (sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>sysconf: 1 libraries, e.g. libflutter.so `framework/webview-shim/webview_bionic_shim.c:1308` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |
| Libraries mapped straight out of the APK (4 .so, extractNativeLibs=false) | supplied | C0 | verify | OH dynamic linker (cannot map zip!/ members: board test 2026-09-18) | extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too) `manifest/tools/prepare_app.py:75` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create lnk_file in app data | denied | C5 | M | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>libflutter.so:symlinkat `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## Limits of this map

- 9 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'newer-than-reference': 7}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
