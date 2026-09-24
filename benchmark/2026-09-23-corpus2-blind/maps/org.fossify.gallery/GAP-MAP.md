# org.fossify.gallery 1.13.1 → OpenHarmony: API shim gap map

Provider: Westlake `provider-authority-resolution` @ `0b5c9af4ce`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 36.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 9 | 9 | 9×verify |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 31 | 15 | 3×verify, 10×S, 2×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 0 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 6 | 5 | 1×verify, 2×S, 2×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 3 | 0 | — |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 4 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 3 | 2 | 1×S, 1×M |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 2 | 1 | 1×verify |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 0 | 0 | — |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 0 | 0 | — |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | hollow-candidate | C9 | verify | window_manager / render_service | check each hollow body against AOSP<br>android.view.ActionProvider.hasSubMenu, android.view.ActionProvider.isVisible, android.view.ActionProvider.onPerformDefaultAction |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.Canvas.disableZ, android.graphics.Canvas.enableZ, android.graphics.Canvas.getMaximumBitmapHeight |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayOutputStream.close, java.io.InputStream.available, java.io.InputStream.close |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.Activity.onActivityResult, android.app.Activity.onCreateContextMenu, android.app.Activity.onCreateView |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.BaseAdapter.getItemViewType, android.widget.TextView.onTextChanged |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.isRestricted |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.AsyncTask.onPostExecute |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>androidx.compose.ui.platform.AndroidCompositionLocals_androidKt, androidx.media3.datasource.rtmp.RtmpDataSource, androidx.media3.decoder.flac.FlacExtractor |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>4 call sites, e.g. androidx.room.u0.run `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1599` |
| notification | hollow | C9 | M | notification (ANS) | replace the hollow binder with an implementation over notification (ANS)<br>2 call sites, e.g. org.fossify.commons.extensions.ContextKt.getNotificationManager `framework/android-runtime/src/AndroidRuntime.cpp:821` |
| biometric | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. r.o.b |
| fingerprint | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. b9.e.b |
| jobscheduler | hollow | C9 | S | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>2 call sites, e.g. org.fossify.gallery.jobs.NewPhotoFetcher.isScheduled `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2118` |
| keyguard | null | C4 | S | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>1 call sites, e.g. r.f0.a |
| media_metrics | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. i5.t.run |
| phone | inert | C4 | S | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>2 call sites, e.g. a8.f.run |
| telecom | inert | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. org.fossify.commons.extensions.ContextKt.getTelecomManager |
| usb | null | C4 | S | usb_manager | Android UsbManager facade over usb_manager<br>1 call sites, e.g. org.fossify.commons.extensions.Context_storageKt.hasOTGConnected |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>1 call sites, e.g. org.fossify.commons.extensions.ContextKt.isCredentialStorageAvailable `framework/package-manager/java/OHUserManager.java:82` |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>1 call sites, e.g. i2.r0.a |
| captioning | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. i5.n0.j `SystemServiceRegistry.java:337` |
| print | unresolved | CU | verify | print_service | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. org.fossify.gallery.activities.ViewPagerActivity$sendPrintIntent$1.onResourceReady `SystemServiceRegistry.java:893` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.y0.a `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>10 call sites, e.g. androidx.core.view.b1.h |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>3 call sites, e.g. b2.z.<init> |
| account | supplied | C0 | verify | account/os_account | none<br>1 call sites, e.g. org.fossify.commons.helpers.ContactsHelper.getDeviceContactSources |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>4 call sites, e.g. androidx.room.b0.b |
| appops | supplied | C0 | verify | unmapped | none<br>1 call sites, e.g. com.bumptech.glide.d.k |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>4 call sites, e.g. androidx.appcompat.widget.a0.onTextContextMenuItem |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>4 call sites, e.g. androidx.room.u0.run |
| display | supplied | C0 | verify | display_manager | none<br>3 call sites, e.g. com.bumptech.glide.f.o |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>13 call sites, e.g. a2.b.invoke `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>47 call sites, e.g. androidx.appcompat.view.menu.ListMenuItemView.getInflater `SystemServiceRegistry.java:593` |
| locale | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. j.n.run |
| location | supplied | C0 | verify | location | none<br>1 call sites, e.g. j.c0.A |
| power | supplied | C0 | verify | powermgr | none<br>2 call sites, e.g. androidx.recyclerview.widget.e.u |
| shortcut | supplied | C0 | verify | unmapped | none<br>4 call sites, e.g. org.fossify.commons.extensions.ContextKt.getShortcutManager |
| uimode | supplied | C0 | verify | display / theme | none<br>2 call sites, e.g. e5.g0.y |
| window | supplied | C0 | verify | window_manager | none<br>9 call sites, e.g. n.t.a `framework/core/java/OHServiceManager.java:96` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1225` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1253` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1727` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1715` |
| Content providers installed at bind (4, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>FileProvider, CropFileProvider, InitializationProvider, PicassoProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>4 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

## Activity, window & process contracts

_what system_server would answer, answered in-process by Westlake in direct launch → white-box probes_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Dialogs stack above their activity's window, whatever the add order | supplied | C0 | verify | window_manager (sub-window z-order: creation order) | stack a base application window below the dialogs already attached to its token<br>app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added before the activity's own window `framework/window/java/WindowSessionAdapter.java:370` — probe: `probes/dialog-before-window` |
| Windows placed by LayoutParams gravity and x/y (dialogs centred) | supplied | C0 | verify | window_manager (session rect) | compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:346` — probe: `probes/dialog-before-window` |
| FLAG_DIM_BEHIND dims what is under a dialog | supplied | C0 | verify | render_service (a layer under the window) | draw a dim layer of dimAmount under the window (OH has no dim flag)<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:84` — probe: `probes/dialog-before-window` |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libandroidx.graphics.path.so → 1 classes, 1 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/graphics/Path |
| libglide-webp.so → 8 classes, 10 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/IOException, java/io/InputStream, java/lang/AssertionError, java/lang/IllegalArgumentException |
| libjxlcoder.so → 6 classes, 12 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/graphics/Bitmap, android/graphics/Bitmap$Config, android/graphics/ColorSpace, android/graphics/ColorSpace$Named |
| libpl_droidsonroids_gif.so → 3 classes, 3 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/NullPointerException, java/lang/OutOfMemoryError, java/lang/RuntimeException |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libnativewindow.so entry points looked up by name at runtime, not supplied (5) | unresolved | C1/C2 | M | dlopen("libnativewindow.so") + dlsym, resolved against whatever the search path reaches first | supply libnativewindow.so's entry points, or confirm the caller degrades without them: this row cannot tell a lookup that happens from a string that is never used<br>5 public NDK symbols of libnativewindow.so appear as literals: AHardwareBuffer_allocate, AHardwareBuffer_describe, AHardwareBuffer_isSupported, AHardwareBuffer_release, AHardwareBuffer_unlock — probe: `probes/webview-boundaries measures the search path; resolving each name on the board is what settles whether the lookup would succeed` |
| libandroid.so entry points looked up by name at runtime, not supplied (1) | unresolved | C1/C2 | S | dlopen("libandroid.so") + dlsym, resolved against whatever the search path reaches first | supply libandroid.so's entry points, or confirm the caller degrades without them: this row cannot tell a lookup that happens from a string that is never used<br>1 public NDK symbols of libandroid.so appear as literals: AHardwareBuffer_toHardwareBuffer — probe: `probes/webview-boundaries measures the search path; resolving each name on the board is what settles whether the lookup would succeed` |
| libc calls carrying a constant each libc numbers differently (sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>sysconf: 3 libraries, e.g. libavif_android.so, libjxl_threads.so, libjxlcoder.so `framework/webview-shim/webview_bionic_shim.c:1308` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |
| Libraries mapped straight out of the APK (12 .so, extractNativeLibs=false) | supplied | C0 | verify | OH dynamic linker (cannot map zip!/ members: board test 2026-09-18) | extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too) `manifest/tools/prepare_app.py:75` |

## Limits of this map

- 6 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 3, 'newer-than-reference': 7}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
