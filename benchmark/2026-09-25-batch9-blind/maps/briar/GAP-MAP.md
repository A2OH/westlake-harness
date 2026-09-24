# org.briarproject.briar.android 1.5.20 → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `1baca65181`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 35.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 8 | 8 | 8×verify |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 21 | 7 | 1×verify, 5×S, 1×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 1 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 6 | 5 | 1×verify, 1×S, 2×M, 1×L |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 3 | 0 | — |
| Windows & surfaces | how the first screen renders → whether it needs a surface of its own → OH window/surface model | 0 | 0 | — |
| Framework natives | platform classes the app uses → their native methods → libraries the runtime registers them from | 5 | 5 | 4×M, 1×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 0 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 2 | 1 | 1×S |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 1 | 1 | 1×verify |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 0 | 0 | — |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 0 | 0 | — |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Rows that have blocked an app at startup before

From the blockers ledger: gaps this app has in common with an app that died on them.

| Row | Verdict | Blocked |
|---|---|---|
| `svc:notification` | supplied | tusky (corpus-2), fixed in 886b89b |
| `svc:uimode` | supplied | burgerking (blind-bk), fixed in d689e67 |
| `svc:wifi` | supplied | openhab (batch-7), fixed in 8eb6ba4 |
| `jni:android.hardware.Camera` | missing | opencamera (loop-1), open |
| `jca:AndroidKeyStore` | supplied | burgerking (blind-bk), fixed in 21fdcda |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | hollow-candidate | C9 | verify | window_manager / render_service | check each hollow body against AOSP<br>android.view.ActionProvider.hasSubMenu, android.view.ActionProvider.isVisible, android.view.ActionProvider.onPerformDefaultAction |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.drawable.Drawable$ConstantState.canApplyTheme, android.graphics.drawable.Drawable.applyTheme, android.graphics.drawable.Drawable.canApplyTheme |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayOutputStream.close, java.io.InputStream.available, java.io.InputStream.close |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.ActionBar.getThemedContext, android.app.ActionBar.setHomeActionContentDescription, android.app.ActionBar.setHomeAsUpIndicator |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.AutoCompleteTextView.onFinishInflate, android.widget.Button.onTextChanged |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.isRestricted |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>com.ibm.icu.text.Collator, com.sun.management.OperatingSystemMXBean, com.sun.tools.javac.Main |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| wifip2p | null | C4 | M | communication/wifi (p2p) | Android WifiP2pManager facade over communication/wifi (p2p)<br>2 call sites, e.g. org.briarproject.briar.android.hotspot.HotspotManager.<init> |
| audio | hollow | C9 | S | audio_framework | replace the hollow binder with an implementation over audio_framework<br>1 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.onKeyUpPanel `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1627` |
| fingerprint | null | C5 | S | unmapped | truthful local manager (feature absent)<br>2 call sites, e.g. androidx.core.hardware.fingerprint.FingerprintManagerCompat$Api23Impl.getFingerprintManagerOrNull |
| keyguard | null | C4 | S | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>2 call sites, e.g. org.briarproject.briar.android.account.UnlockActivity.requestKeyguardUnlock |
| phone | inert | C4 | S | telephony/core_service | Android TelephonyManager facade over telephony/core_service<br>2 call sites, e.g. org.briarproject.onionwrapper.AndroidLocationUtils.getCountryFromPhoneNetwork |
| usagestats | null | C4 | S | resourceschedule/device_usage_statistics | Android UsageStatsManager facade over resourceschedule/device_usage_statistics<br>1 call sites, e.g. org.briarproject.briar.android.reporting.BriarReportCollector.getDeviceInfo |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper$Api26Impl.getTextClassifier `SystemServiceRegistry.java:413` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>13 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>2 call sites, e.g. com.bumptech.glide.load.engine.cache.MemorySizeCalculator$Builder.<init> |
| alarm | supplied | C0 | verify | time_service / reminder_agent | none<br>2 call sites, e.g. org.briarproject.bramble.system.AndroidTaskScheduler.<init> |
| appops | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. androidx.core.app.AppOpsManagerCompat$Api29Impl.getSystemService |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>3 call sites, e.g. androidx.appcompat.widget.AppCompatReceiveContentHelper.maybeHandleMenuActionViaPerformReceiveContent |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>4 call sites, e.g. com.bumptech.glide.manager.SingletonConnectivityReceiver$1.get |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>11 call sites, e.g. androidx.activity.ImmLeaksCleaner.onStateChanged `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>82 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| location | supplied | C0 | verify | location | none<br>1 call sites, e.g. androidx.appcompat.app.TwilightManager.getInstance |
| notification | supplied | C0 | verify | notification (ANS) | none<br>2 call sites, e.g. org.briarproject.briar.android.AndroidNotificationManagerImpl.<init> |
| power | supplied | C0 | verify | powermgr | none<br>5 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$AutoBatteryNightModeManager.<init> |
| uimode | supplied | C0 | verify | display / theme | none<br>1 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.mapNightMode |
| wifi | supplied | C0 | verify | communication/wifi | none<br>5 call sites, e.g. org.briarproject.bramble.network.AndroidNetworkManager.getNetworkStatus |
| window | supplied | C0 | verify | window_manager | none<br>10 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.openPanel `framework/core/java/OHServiceManager.java:96` |

## Keystore & crypto providers

_JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Android keystore provider ("AndroidKeyStore") | supplied | C0 | verify | security/huks (OH Universal Keystore); keystore2 has no OH counterpart | install an "AndroidKeyStore" provider whose keys come from KeyGenParameterSpec and stay per app: software keys in app data (days), or OH HUKS for hardware-backed keys (weeks). A blocker wherever the app opens it at startup (secure storage, encrypted preferences, biometric crypto, attestation)<br>1 classes name it, e.g. Lorg/briarproject/briar/android/AndroidKeyStrengthener;; calls KeyGenerator.getInstance("HmacSHA256"), KeyStore.getInstance("AndroidKeyStore") `framework/core/java/SoftwareAndroidKeyStore.java:65` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Components in secondary processes: :briar_error_handler, :briar_startup_failure | missing | C4 | L | appspawn (second process) | spawn and route secondary Android processes |
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1226` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1254` |
| PackageManager.getSystemAvailableFeatures | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1815` |
| Content providers installed at bind (1, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>InitializationProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>32 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

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
| android.drm.DrmManagerClient: 19 of 19 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: _acquireDrmInfo(ILandroid/drm/DrmInfoRequest;)Landroid/drm/DrmInfo;, _canHandle(ILjava/lang/String;Ljava/lang/String;)Z, _checkRightsStatus(ILjava/lang/String;I)I, _closeConvertSession(II)Landroid/drm/DrmConvertedStatus;, _convertData(II[B)Landroid/drm/DrmConvertedStatus;, _getAllSupportInfo(I)[Landroid/drm/DrmSupportInfo;, _getConstraints(ILjava/lang/String;I)Landroid/content/ContentValues;, _getDrmObjectType(ILjava/lang/String;Ljava/lang/String;)I |
| android.hardware.Camera: 29 of 29 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: setDisplayOrientation(I)V, startPreview()V |
| android.media.MediaExtractor: 26 of 26 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.media.MediaMetadataRetriever: 13 of 13 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| bionic libc ABI: 1 symbols to translate onto musl | missing | C1/C2 | S | OH musl libc | bionic-ABI shim: forward or translate; never ship a second libc<br>open: __libc_init |
| libc calls carrying a constant each libc numbers differently (sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>sysconf: 1 libraries, e.g. libtor.so `framework/webview-shim/webview_bionic_shim.c:1308` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |

## Limits of this map

- 7 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 17}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
