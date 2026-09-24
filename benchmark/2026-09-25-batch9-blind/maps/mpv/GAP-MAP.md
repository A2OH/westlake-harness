# is.xyz.mpv 2026-09-17-release → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `1baca65181`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 36.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 8 | 8 | 8×verify |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 16 | 2 | 1×verify, 1×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 0 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 7 | 6 | 1×verify, 2×S, 3×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 3 | 0 | — |
| Windows & surfaces | how the first screen renders → whether it needs a surface of its own → OH window/surface model | 0 | 0 | — |
| Framework natives | platform classes the app uses → their native methods → libraries the runtime registers them from | 1 | 1 | 1×S |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 4 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 6 | 5 | 1×S, 2×M, 2×L |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 3 | 2 | 1×verify, 1×XS |
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
| `ndk:weld:media` | missing | fennec (corpus-2), open |
| `load:shadowed-by-board` | missing | burgerking (blind-bk), fixed in launcher --android-native-target |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | hollow-candidate | C9 | verify | window_manager / render_service | check each hollow body against AOSP<br>android.view.ActionProvider.hasSubMenu, android.view.ActionProvider.isVisible, android.view.ActionProvider.onPerformDefaultAction |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.drawable.Drawable$ConstantState.canApplyTheme, android.graphics.drawable.Drawable.applyTheme, android.graphics.drawable.Drawable.canApplyTheme |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.AutoCompleteTextView.onFinishInflate, android.widget.Button.onTextChanged |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.Activity.onActivityResult, android.app.Activity.onCreateContextMenu, android.app.Activity.onCreateView |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayOutputStream.close, java.io.InputStream.available, java.io.InputStream.close |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.isRestricted |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>kotlin.reflect.jvm.internal.ReflectionFactoryImpl |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>2 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.dispatchKeyEvent `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1627` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper$Api26Impl.getTextClassifier `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>9 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>1 call sites, e.g. com.google.android.material.checkbox.MaterialCheckBox.setCheckedState |
| appops | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. androidx.core.math.MathUtils.checkSelfPermission |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>2 call sites, e.g. androidx.appcompat.widget.AppCompatEditText.onTextContextMenuItem |
| display | supplied | C0 | verify | display_manager | none<br>1 call sites, e.g. androidx.core.os.BuildCompat$Api30Impl.getDisplayOrDefault |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>10 call sites, e.g. androidx.activity.ImmLeaksCleaner.onStateChanged `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>37 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| locale | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. androidx.appcompat.app.AppCompatDelegate$$ExternalSyntheticLambda0.run |
| location | supplied | C0 | verify | location | none<br>1 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.getAutoTimeNightModeManager |
| notification | supplied | C0 | verify | notification (ANS) | none<br>3 call sites, e.g. androidx.core.app.NotificationManagerCompat.<init> |
| power | supplied | C0 | verify | powermgr | none<br>1 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$AutoTimeNightModeManager.<init> |
| storage | supplied | C0 | verify | filemanagement/storage_service | none<br>1 call sites, e.g. is.xyz.mpv.Utils.getStorageVolumes |
| uimode | supplied | C0 | verify | display / theme | none<br>2 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.mapNightMode |
| window | supplied | C0 | verify | window_manager | none<br>7 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.closePanel `framework/core/java/OHServiceManager.java:96` |

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
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>1 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

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
| android.os.storage.StorageManager: 1 of 1 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: setQuotaProjectId(Ljava/lang/String;J)Z |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libavcodec.so → 9 classes, 73 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/media/MediaCodec, android/media/MediaCodec$BufferInfo, android/media/MediaCodecInfo, android/media/MediaCodecInfo$CodecCapabilities |
| libavformat.so → 4 classes, 4 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/content/ContentResolver, android/content/Context, android/net/Uri, android/os/ParcelFileDescriptor |
| libmpv.so → 8 classes, 72 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/media/AudioAttributes, android/media/AudioAttributes$Builder, android/media/AudioFormat, android/media/AudioFormat$Builder |
| libplayer.so → 5 classes, 8 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/graphics/Bitmap, android/graphics/Bitmap$Config, java/lang/Boolean, java/lang/Double |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| NDK weld · media: 29 symbols | missing | C4 | L | multimedia/av_codec + player_framework | AOSP NDK source above, multimedia/av_codec + player_framework below<br>open: AMediaCodec_configure, AMediaCodec_createCodecByName, AMediaCodec_createDecoderByType, AMediaCodec_createEncoderByType, AMediaCodec_delete, AMediaCodec_dequeueInputBuffer, AMediaCodec_dequeueOutputBuffer, AMediaCodec_flush |
| libaaudio.so entry points looked up by name at runtime, not supplied (28) | unresolved | C1/C2 | L | dlopen("libaaudio.so") + dlsym, resolved against whatever the search path reaches first | supply libaaudio.so's entry points, or confirm the caller degrades without them: this row cannot tell a lookup that happens from a string that is never used<br>28 public NDK symbols of libaaudio.so appear as literals: AAudioStreamBuilder_delete, AAudioStreamBuilder_setBufferCapacityInFrames, AAudioStreamBuilder_setChannelCount, AAudioStreamBuilder_setDataCallback, AAudioStreamBuilder_setDeviceId, AAudioStreamBuilder_setDirection … — probe: `probes/webview-boundaries measures the search path; resolving each name on the board is what settles whether the lookup would succeed` |
| NDK weld · audio: 1 symbols | missing | C4 | M | audio_framework (OHAudio) | AOSP NDK source above, audio_framework (OHAudio) below<br>open: SL_IID_ANDROIDCONFIGURATION |
| libmediandk.so entry points looked up by name at runtime, not supplied (13) | unresolved | C1/C2 | M | dlopen("libmediandk.so") + dlsym, resolved against whatever the search path reaches first | supply libmediandk.so's entry points, or confirm the caller degrades without them: this row cannot tell a lookup that happens from a string that is never used<br>13 public NDK symbols of libmediandk.so appear as literals: AImageReader_acquireLatestImage, AImageReader_delete, AImageReader_getWindow, AImageReader_newWithUsage, AImage_delete, AMediaCodec_createPersistentInputSurface … — probe: `probes/webview-boundaries measures the search path; resolving each name on the board is what settles whether the lookup would succeed` |
| bionic libc ABI: 1 symbols to translate onto musl | missing | C1/C2 | S | OH musl libc | bionic-ABI shim: forward or translate; never ship a second libc<br>open: getprogname |
| libc calls carrying a constant each libc numbers differently (pathconf, sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>pathconf: 1 libraries, e.g. libc++_shared.so; sysconf: 3 libraries, e.g. libavcodec.so, libc++_shared.so, libmpv.so `framework/webview-shim/webview_bionic_shim.c:1308` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Packaged libraries a board library of the same name shadows (libc++_shared.so) | missing | C3 | XS | OH dynamic linker search order: /system/lib64/libc++_shared.so comes before the app's library directory | load these 3 libraries in the isolated Android namespace so DT_NEEDED picks the APK's copy (e.g. NDK libc++_shared is std::__ndk1; OH's is not): libc++_shared.so libmpv.so libplayer.so<br>3 APK libraries reach them through DT_NEEDED `manifest/tools/probe_source_app.py:44` |
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |
| Libraries mapped straight out of the APK (10 .so, extractNativeLibs=false) | supplied | C0 | verify | OH dynamic linker (cannot map zip!/ members: board test 2026-09-18) | extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too) `manifest/tools/prepare_app.py:75` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create lnk_file in app data | denied | C5 | M | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | neverallow'd for hap_domain on app data; needs a libc-level emulation of symlink(), not a policy rule<br>libc++_shared.so:symlink, libmpv.so:symlink `sepolicy/base/public/hap_domain.te neverallow hap_domain ~{ tmpfs_data_file dev_file ... data_user_file hmdfs ... }:lnk_file *` |

## Limits of this map

- 3 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
