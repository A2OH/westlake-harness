# me.zhanghai.android.files 1.7.5 → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `1c883ad180`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 36.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 9 | 9 | 6×verify, 3×S |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 19 | 4 | 1×verify, 3×S |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 0 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 9 | 8 | 1×verify, 4×S, 3×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 4 | 1 | 1×L |
| Framework natives | platform classes the app uses → their native methods → libraries the runtime registers them from | 4 | 4 | 1×S, 2×M, 1×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 4 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 1 | 0 | — |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 1 | 1 | 1×verify |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 1 | 1 | 1×M |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 0 | 0 | — |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Rows that have blocked an app at startup before

From the blockers ledger: gaps this app has in common with an app that died on them.

| Row | Verdict | Blocked |
|---|---|---|
| `svc:locale` | supplied | ooniprobe (loop-1), fixed in 95dba94 |
| `svc:notification` | supplied | tusky (corpus-2), fixed in 886b89b |
| `svc:uimode` | supplied | burgerking (blind-bk), fixed in d689e67 |
| `svc:user` | strict | burgerking (blind-bk), fixed in 9b8b861 |
| `wv:renderer-process` | missing | burgerking (blind-bk), open |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | missing | C4 | S | window_manager / render_service | implement the members over window_manager / render_service<br>android.view.accessibility.AccessibilityNodeInfo$AccessibilityAction.ACTION_SET_EXTENDED_SELECTION |
| Graphics | missing | C4 | S | render_service / graphic_2d | implement the members over render_service / graphic_2d<br>android.graphics.pdf.PdfRenderer, android.graphics.pdf.PdfRenderer$Page |
| App framework | missing | C4 | S | ability_runtime | implement the members over ability_runtime<br>android.app.Notification$Action$Builder.setEmphasisHint, android.app.Notification$Action$Builder.setStyleHint |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayOutputStream.close, java.io.InputStream.available, java.io.InputStream.close |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.AutoCompleteTextView.onFinishInflate, android.widget.Button.onTextChanged |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.isRestricted, android.content.ServiceConnection.onNullBinding |
| Java extensions | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>javax.crypto.spec.SecretKeySpec.getFormat, javax.security.auth.Destroyable.isDestroyed |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>kotlin.reflect.jvm.internal.ReflectionFactoryImpl, org.bouncycastle.jsse.provider.BouncyCastleJsseProvider, org.conscrypt.Conscrypt$Version |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | S | audio_framework | replace the hollow binder with an implementation over audio_framework<br>1 call sites, e.g. hb.x `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1627` |
| statusbar | inert | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. me.zhanghai.android.files.ftpserver.FtpServerAddTilePreference.p |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>1 call sites, e.g. ak0.L `framework/package-manager/java/OHUserManager.java:82` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. b.n `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>11 call sites, e.g. ag0.q |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>1 call sites, e.g. xq1.setCheckedState |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>3 call sites, e.g. com.davemorrissey.labs.subscaleview.decoder.SkiaPooledImageRegionDecoder.isLowMemory |
| appops | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. lb1.j |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>2 call sites, e.g. nb.onTextContextMenuItem |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>1 call sites, e.g. te3.a |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>6 call sites, e.g. androidx.appcompat.widget.AppCompatTextView.onDetachedFromWindow `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>59 call sites, e.g. me.zhanghai.android.files.fileproperties.permission.SetPrincipalDialogFragment.f0 `SystemServiceRegistry.java:593` |
| locale | supplied | C0 | verify | unmapped | none<br>3 call sites, e.g. wa.b |
| location | supplied | C0 | verify | location | none<br>1 call sites, e.g. hb.B |
| notification | supplied | C0 | verify | notification (ANS) | none<br>1 call sites, e.g. hz1.<init> |
| power | supplied | C0 | verify | powermgr | none<br>1 call sites, e.g. cb.<init> |
| shortcut | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. b.v |
| uimode | supplied | C0 | verify | display / theme | none<br>1 call sites, e.g. hb.G |
| window | supplied | C0 | verify | window_manager | none<br>7 call sites, e.g. hb.I `framework/core/java/OHServiceManager.java:96` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| PackageManager.queryBroadcastReceivers | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1233` |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1226` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1254` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1728` |
| PackageManager.getInstalledApplications | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1275` |
| PackageManager.getPackagesHoldingPermissions | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1268` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1716` |
| Content providers installed at bind (4, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>AppProvider, FileProvider, ShizukuProvider, InitializationProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>4 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

## Activity, window & process contracts

_what system_server would answer, answered in-process by Westlake in direct launch → white-box probes_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| WebView's renderer runs in an isolated service process | missing | C4 | L | process spawn (appspawn): an isolated Android service process with its own sandbox | host the renderer: spawn an isolated child and bind Chromium's SandboxedProcessService over a local channel; or build the framework with the update-service flag off so WebView runs single-process<br>app constructs WebViews and calls 6 WebView methods `frameworks-base/core/java/android/webkit/WebViewDelegate.java:215` |
| Dialogs stack above their activity's window, whatever the add order | supplied | C0 | verify | window_manager (sub-window z-order: creation order) | stack a base application window below the dialogs already attached to its token<br>app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added before the activity's own window `framework/window/java/WindowSessionAdapter.java:370` — probe: `probes/dialog-before-window` |
| Windows placed by LayoutParams gravity and x/y (dialogs centred) | supplied | C0 | verify | window_manager (session rect) | compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:346` — probe: `probes/dialog-before-window` |
| FLAG_DIM_BEHIND dims what is under a dialog | supplied | C0 | verify | render_service (a layer under the window) | draw a dim layer of dimAmount under the window (OH has no dim flag)<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:84` — probe: `probes/dialog-before-window` |

## Framework natives

_platform classes the app uses → their native methods → libraries the runtime registers them from_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| android.media.MediaDrm: 43 of 43 natives unregistered | missing | C3 | L | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.drm.DrmManagerClient: 19 of 19 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: _acquireDrmInfo(ILandroid/drm/DrmInfoRequest;)Landroid/drm/DrmInfo;, _canHandle(ILjava/lang/String;Ljava/lang/String;)Z, _checkRightsStatus(ILjava/lang/String;I)I, _closeConvertSession(II)Landroid/drm/DrmConvertedStatus;, _convertData(II[B)Landroid/drm/DrmConvertedStatus;, _getAllSupportInfo(I)[Landroid/drm/DrmSupportInfo;, _getConstraints(ILjava/lang/String;I)Landroid/content/ContentValues;, _getDrmObjectType(ILjava/lang/String;Ljava/lang/String;)I |
| android.media.MediaMetadataRetriever: 13 of 13 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.os.storage.StorageManager: 1 of 1 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: setQuotaProjectId(Ljava/lang/String;J)Z |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libarchive-jni.so → 2 classes, 14 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Throwable, java/nio/ByteBuffer |
| libhiddenapi.so → 2 classes, 2 members | supplied | C0 | none | through the Java framework | none<br>e.g. dalvik/system/VMRuntime, java/lang/String |
| libselinux-jni.so → 2 classes, 3 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/system/ErrnoException, java/io/FileDescriptor |
| libsyscall.so → 3 classes, 4 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/system/Int64Ref, android/system/StructStatVfs, java/io/FileDescriptor |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libc calls carrying a constant each libc numbers differently (sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>sysconf: 3 libraries, e.g. libarchive-jni.so, libselinux-jni.so, libsyscall.so `framework/webview-shim/webview_bionic_shim.c:1308` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create lnk_file in app data | denied | C5 | M | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>libsyscall.so:symlink `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## Limits of this map

- 4 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 13, 'newer-than-reference': 8}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
