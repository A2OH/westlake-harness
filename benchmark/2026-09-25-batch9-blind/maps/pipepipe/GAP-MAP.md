# InfinityLoop1309.NewPipeEnhanced 5.3.1 → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `1baca65181`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 36.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 13 | 13 | 11×verify, 2×S |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 28 | 10 | 3×verify, 3×S, 4×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 0 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 9 | 8 | 1×verify, 3×S, 3×M, 1×L |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 5 | 1 | 1×L |
| Windows & surfaces | how the first screen renders → whether it needs a surface of its own → OH window/surface model | 0 | 0 | — |
| Framework natives | platform classes the app uses → their native methods → libraries the runtime registers them from | 5 | 5 | 1×S, 2×M, 2×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 3 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 1 | 1 | 1×L |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 1 | 1 | 1×verify |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 1 | 1 | 1×OH |
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
| `wv:renderer-process` | missing | burgerking (blind-bk), open |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | missing | C4 | S | window_manager / render_service | implement the members over window_manager / render_service<br>android.view.accessibility.AccessibilityNodeInfo$AccessibilityAction.ACTION_SET_EXTENDED_SELECTION |
| App framework | missing | C4 | S | ability_runtime | implement the members over ability_runtime<br>android.app.Notification$Action$Builder.setEmphasisHint, android.app.Notification$Action$Builder.setStyleHint |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.Canvas.disableZ, android.graphics.Canvas.enableZ, android.graphics.Canvas.getMaximumBitmapHeight |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayInputStream.close, java.io.ByteArrayOutputStream.close, java.io.InputStream.available |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.AutoCompleteTextView.onFinishInflate, android.widget.Button.onTextChanged |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| Networking | hollow-candidate | C9 | verify | netmanager | check each hollow body against AOSP<br>android.net.ConnectivityManager$NetworkCallback.onAvailable, android.net.ConnectivityManager$NetworkCallback.onBlockedStatusChanged, android.net.ConnectivityManager$NetworkCallback.onCapabilitiesChanged |
| WebView | hollow-candidate | C9 | verify | web (ArkWeb) or bundled Chromium | check each hollow body against AOSP<br>android.webkit.WebViewClient.onPageFinished, android.webkit.WebViewClient.onReceivedError, android.webkit.WebViewClient.shouldOverrideUrlLoading |
| Job scheduling | hollow-candidate | C9 | verify | resourceschedule/work_scheduler | check each hollow body against AOSP<br>android.app.job.JobService.onCreate, android.app.job.JobService.onDestroy |
| OS services | hollow-candidate | C9 | verify | various system abilities | check each hollow body against AOSP<br>android.os.Handler.handleMessage, android.os.IBinder.getSuggestedMaxIpcSizeBytes |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.isRestricted |
| Media | hollow-candidate | C9 | verify | multimedia | check each hollow body against AOSP<br>android.media.DrmInitData.getSchemeInitDataCount |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>com.android.internal.policy.impl.PhoneWindow$DecorView, com.google.android.exoplayer2.decoder.midi.MidiExtractor, com.google.android.exoplayer2.decoder.midi.MidiRenderer |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | M | audio_framework | replace the hollow binder with an implementation over audio_framework<br>6 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.dispatchKeyEvent `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1627` |
| jobscheduler | hollow | C9 | M | resourceschedule/work_scheduler | replace the hollow binder with an implementation over resourceschedule/work_scheduler<br>5 call sites, e.g. androidx.work.impl.WorkManagerImpl$$ExternalSyntheticLambda0.invoke `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:2189` |
| phone | inert | C4 | M | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>3 call sites, e.g. com.google.android.exoplayer2.util.NetworkTypeObserver$Api31.disambiguate4gAnd5gNsa |
| sensor | inert | C4 | M | sensors | Android SensorManager facade over sensors<br>1 call sites, e.g. com.google.android.exoplayer2.video.spherical.SphericalGLSurfaceView.<init> |
| dropbox | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. org.acra.collector.DropBoxCollector.collect |
| media_metrics | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. com.google.android.exoplayer2.analytics.MediaMetricsListener.create |
| user | strict | C9 | S | account/os_account | answer the methods callers use with Android's value for this device; a throw is never Android's answer (inside a JNI callback, WebView aborts on it)<br>1 call sites, e.g. us.shandian.giga.util.Utility.isUserUnlocked `framework/package-manager/java/OHUserManager.java:82` |
| captioning | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>5 call sites, e.g. com.google.android.exoplayer2.trackselection.TrackSelectionParameters$Builder.setPreferredTextLanguageAndRoleFlagsToCaptioningManagerSettingsV19 `SystemServiceRegistry.java:337` |
| permission_controller | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. leakcanary.AndroidLeakFixes$PERMISSION_CONTROLLER_MANAGER.apply `SystemServiceRegistry.java:1437` |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper$Api26Impl.getTextClassifier `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>17 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>1 call sites, e.g. androidx.compose.ui.autofill.AndroidAutofill.<init> |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>6 call sites, e.g. androidx.room.RoomDatabase$Builder.build |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>1 call sites, e.g. androidx.work.impl.utils.ForceStopRunnable.setAlarm |
| appops | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. org.slf4j.helpers.Util.checkSelfPermission |
| batterymanager | supplied | C0 | verify | powermgr/battery_manager | none<br>1 call sites, e.g. org.schabi.newpipe.util.DeviceUtils.isTv |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>5 call sites, e.g. androidx.appcompat.widget.AppCompatEditText.onTextContextMenuItem |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>13 call sites, e.g. androidx.work.impl.constraints.WorkConstraintsTracker.<init> |
| display | supplied | C0 | verify | display_manager | none<br>4 call sites, e.g. com.google.android.exoplayer2.util.Util.getCurrentDisplayModeSize |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>23 call sites, e.g. androidx.activity.ImmLeaksCleaner.onStateChanged `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>93 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| locale | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. androidx.appcompat.app.AppCompatDelegate$$ExternalSyntheticLambda0.run |
| location | supplied | C0 | verify | location | none<br>1 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.getAutoTimeNightModeManager |
| notification | supplied | C0 | verify | notification (ANS) | none<br>14 call sites, e.g. androidx.core.app.NotificationManagerCompat.<init> |
| power | supplied | C0 | verify | powermgr | none<br>5 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$AutoTimeNightModeManager.<init> |
| uimode | supplied | C0 | verify | display / theme | none<br>3 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.mapNightMode |
| wifi | supplied | C0 | verify | communication/wifi | none<br>2 call sites, e.g. com.google.android.exoplayer2.WifiLockManager.<init> |
| window | supplied | C0 | verify | window_manager | none<br>22 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.closePanel `framework/core/java/OHServiceManager.java:96` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Components in secondary processes: :acra, :phoenix | missing | C4 | L | appspawn (second process) | spawn and route secondary Android processes |
| PackageManager.queryBroadcastReceivers | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1233` |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1226` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1254` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1728` |
| PackageManager.getSystemAvailableFeatures | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1815` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1716` |
| Content providers installed at bind (5, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>FileProvider, InitializationProvider, MainProcessAppWatcherInstaller, PlumberInstaller, PicassoProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>2 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

## Activity, window & process contracts

_what system_server would answer, answered in-process by Westlake in direct launch → white-box probes_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| WebView's renderer runs in an isolated service process | missing | C4 | L | process spawn (appspawn): an isolated Android service process with its own sandbox | host the renderer: spawn an isolated child and bind Chromium's SandboxedProcessService over a local channel; or build the framework with the update-service flag off so WebView runs single-process<br>app constructs WebViews and calls 20 WebView methods `frameworks-base/core/java/android/webkit/WebViewDelegate.java:215` |
| ActivityManager process-table queries (getRunningAppProcesses, getRunningServices) | supplied | C0 | verify | none (the caller's own process is the answer) | answer with the caller's process: name, pid, uid, foreground importance, its package<br>app calls getRunningAppProcesses, getRunningServices `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1409` — probe: `probes/running-app-processes` |
| Dialogs stack above their activity's window, whatever the add order | supplied | C0 | verify | window_manager (sub-window z-order: creation order) | stack a base application window below the dialogs already attached to its token<br>app shows dialogs (Dialog.show referenced); a dialog shown from onCreate/onResume is added before the activity's own window `framework/window/java/WindowSessionAdapter.java:370` — probe: `probes/dialog-before-window` |
| Windows placed by LayoutParams gravity and x/y (dialogs centred) | supplied | C0 | verify | window_manager (session rect) | compute the frame from gravity/x/y against the display, as WindowLayout.computeFrames does<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:346` — probe: `probes/dialog-before-window` |
| FLAG_DIM_BEHIND dims what is under a dialog | supplied | C0 | verify | render_service (a layer under the window) | draw a dim layer of dimAmount under the window (OH has no dim flag)<br>app shows dialogs (Dialog.show referenced) `framework/window/java/WindowSessionAdapter.java:84` — probe: `probes/dialog-before-window` |

## Framework natives

_platform classes the app uses → their native methods → libraries the runtime registers them from_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| android.media.MediaDrm: 43 of 43 natives unregistered | missing | C3 | L | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.media.MediaPlayer: 49 of 49 natives unregistered | missing | C3 | L | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.drm.DrmManagerClient: 19 of 19 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: _acquireDrmInfo(ILandroid/drm/DrmInfoRequest;)Landroid/drm/DrmInfo;, _canHandle(ILjava/lang/String;Ljava/lang/String;)Z, _checkRightsStatus(ILjava/lang/String;I)I, _closeConvertSession(II)Landroid/drm/DrmConvertedStatus;, _convertData(II[B)Landroid/drm/DrmConvertedStatus;, _getAllSupportInfo(I)[Landroid/drm/DrmSupportInfo;, _getConstraints(ILjava/lang/String;I)Landroid/content/ContentValues;, _getDrmObjectType(ILjava/lang/String;Ljava/lang/String;)I |
| android.media.MediaMetadataRetriever: 13 of 13 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.media.MediaParser: 1 of 1 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: nativeSubmitMetrics(Ljava/lang/String;Ljava/lang/String;ZLjava/lang/String;Ljava/lang/String;JJLjava/lang/String;Ljava/lang/String;Ljava/lang/String;II)V |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libandroidx.graphics.path.so → 1 classes, 1 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/graphics/Path |
| libavcodec.so → 8 classes, 65 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/media/MediaCodec, android/media/MediaCodec$BufferInfo, android/media/MediaCodecInfo, android/media/MediaCodecInfo$CodecCapabilities |
| libffmpegkit.so → 1 classes, 4 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/String |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libmediandk.so entry points looked up by name at runtime, not supplied (30) | unresolved | C1/C2 | L | dlopen("libmediandk.so") + dlsym, resolved against whatever the search path reaches first | supply libmediandk.so's entry points, or confirm the caller degrades without them: this row cannot tell a lookup that happens from a string that is never used<br>30 public NDK symbols of libmediandk.so appear as literals: AMediaCodec_configure, AMediaCodec_createCodecByName, AMediaCodec_createDecoderByType, AMediaCodec_createEncoderByType, AMediaCodec_createPersistentInputSurface, AMediaCodec_delete … — probe: `probes/webview-boundaries measures the search path; resolving each name on the board is what settles whether the lookup would succeed` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |

## Process sandbox & policy

_objects the code creates → what OH SELinux lets an app create_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Create fifo_file in app data | denied | C4 | OH | SELinux u:r:normal_hap:s0 → u:object_r:appdat:s0 | allow hap_domain normal_hap_data_file_attr:fifo_file { create read write open lock unlink map setattr getattr rename }; (no neverallow in hap_domain.te blocks it) \| bring-up workaround: label the staged app-data tree data_app_el2_file: kernel grants normal_hap dir/file/fifo_file/sock_file there (still no lnk_file)<br>libffmpegkit.so:mkfifo `sepolicy/ohos_policy/bundlemanager/bundle_framework/system/installs.te:199 allow hap_domain data_app_el2_file:fifo_file { create read write open lock unlink map setattr getattr rename }` |

## Limits of this map

- 8 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 3, 'newer-than-reference': 6}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
