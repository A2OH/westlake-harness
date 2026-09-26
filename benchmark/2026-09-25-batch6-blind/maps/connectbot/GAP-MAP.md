# org.connectbot 1.10.9-oss → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `2b21e1200d`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 36.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 9 | 9 | 7×verify, 2×S |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 21 | 7 | 2×verify, 5×S |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 1 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 6 | 5 | 1×verify, 2×S, 2×M |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 3 | 0 | — |
| Windows & surfaces | how the first screen renders → whether it needs a surface of its own → OH window/surface model | 0 | 0 | — |
| Framework natives | platform classes the app uses → their native methods → libraries the runtime registers them from | 4 | 4 | 1×S, 1×M, 2×L |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 4 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 1 | 0 | — |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 2 | 1 | 1×verify |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 0 | 0 | — |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 0 | 0 | — |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Rows that have blocked an app at startup before

From the blockers ledger: gaps this app has in common with an app that died on them.

| Row | Verdict | Blocked |
|---|---|---|
| `svc:locale` | supplied | ooniprobe (loop-1), fixed in 95dba94 |
| `svc:notification` | supplied | tusky (corpus-2), fixed in 886b89b |
| `svc:uimode` | supplied | burgerking (blind-bk), fixed in d689e67 |
| `jca:AndroidKeyStore` | supplied | burgerking (blind-bk), fixed in 21fdcda |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Views & windows | missing | C4 | S | window_manager / render_service | implement the members over window_manager / render_service<br>android.view.accessibility.AccessibilityNodeInfo$AccessibilityAction.ACTION_SET_EXTENDED_SELECTION |
| App framework | missing | C4 | S | ability_runtime | implement the members over ability_runtime<br>android.app.Notification$Action$Builder.setEmphasisHint, android.app.Notification$Action$Builder.setStyleHint |
| Graphics | hollow-candidate | C9 | verify | render_service / graphic_2d | check each hollow body against AOSP<br>android.graphics.Canvas.disableZ, android.graphics.Canvas.enableZ, android.graphics.Canvas.getMaximumBitmapHeight |
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.ByteArrayOutputStream.close, java.io.InputStream.available, java.io.InputStream.close |
| Other Android | hollow-candidate | C9 | verify | unmapped | check each hollow body against AOSP<br>android.animation.Animator.cancel, android.animation.Animator.end, android.animation.Animator.setTarget |
| Java extensions | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>javax.net.ssl.X509ExtendedKeyManager.chooseEngineClientAlias, javax.net.ssl.X509ExtendedKeyManager.chooseEngineServerAlias |
| Widgets | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>android.widget.AbsListView.layoutChildren, android.widget.TextView.onTextChanged |
| Content & intents | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.content.Context.isRestricted |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>kotlin.reflect.jvm.internal.ReflectionFactoryImpl, org.apache.harmony.security.utils.AlgNameMapper |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| audio | hollow | C9 | S | audio_framework | replace the hollow binder with an implementation over audio_framework<br>1 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.dispatchKeyEvent `framework/appspawn-x/java/com/android/internal/os/AppSpawnXInit.java:1627` |
| biometric | null | C5 | S | unmapped | truthful local manager (feature absent)<br>1 call sites, e.g. androidx.biometric.BiometricManager$Api29Impl.create |
| keyguard | null | C4 | S | theme/screenlock | Android KeyguardManager facade over theme/screenlock<br>1 call sites, e.g. androidx.biometric.KeyguardUtils$Api23Impl.getKeyguardManager |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>1 call sites, e.g. org.connectbot.service.TerminalManager.onCreate |
| wifi | null | C4 | S | communication/wifi | Android WifiManager facade over communication/wifi<br>1 call sites, e.g. org.connectbot.service.ConnectivityMonitor.<init> |
| textclassification | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. androidx.appcompat.widget.AppCompatTextClassifierHelper$Api26Impl.getTextClassifier `SystemServiceRegistry.java:413` |
| vibrator_manager | unresolved | CU | verify | unmapped | trace the helper's binder; then treat as null, inert or supplied<br>1 call sites, e.g. org.connectbot.service.TerminalManager.onCreate `SystemServiceRegistry.java:796` |
| accessibility | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>7 call sites, e.g. androidx.appcompat.widget.TooltipCompatHandler.onHover |
| autofill | inert | C5 | none | unmapped | none: the manager is written to run without its service<br>1 call sites, e.g. com.google.android.material.checkbox.MaterialCheckBox.setCheckedState |
| activity | supplied | C0 | verify | ability_runtime (AMS) | none<br>1 call sites, e.g. androidx.room.RoomDatabase$Builder.build |
| appops | supplied | C0 | verify | unmapped | none<br>1 call sites, e.g. androidx.core.os.BundleCompat.checkSelfPermission |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>10 call sites, e.g. androidx.appcompat.widget.AppCompatEditText.onTextContextMenuItem |
| connectivity | supplied | C0 | verify | netmanager (NetConnManager) | none<br>1 call sites, e.g. org.connectbot.service.ConnectivityMonitor.<init> |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>11 call sites, e.g. androidx.appcompat.widget.AppCompatTextView.onDetachedFromWindow `framework/core/java/OHServiceManager.java:105` |
| layout_inflater | supplied | C0 | verify | unmapped | none<br>21 call sites, e.g. androidx.appcompat.app.AlertController$AlertParams.<init> `SystemServiceRegistry.java:593` |
| locale | supplied | C0 | verify | unmapped | none<br>2 call sites, e.g. androidx.appcompat.app.AppCompatDelegate$$ExternalSyntheticLambda0.run |
| location | supplied | C0 | verify | location | none<br>1 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.getAutoTimeNightModeManager |
| notification | supplied | C0 | verify | notification (ANS) | none<br>3 call sites, e.g. androidx.core.app.NotificationManagerCompat.<init> |
| power | supplied | C0 | verify | powermgr | none<br>1 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl$AutoTimeNightModeManager.<init> |
| uimode | supplied | C0 | verify | display / theme | none<br>1 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.mapNightMode |
| window | supplied | C0 | verify | window_manager | none<br>14 call sites, e.g. androidx.appcompat.app.AppCompatDelegateImpl.closePanel `framework/core/java/OHServiceManager.java:96` |

## Keystore & crypto providers

_JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Android keystore provider ("AndroidKeyStore") | supplied | C0 | verify | security/huks (OH Universal Keystore); keystore2 has no OH counterpart | install an "AndroidKeyStore" provider whose keys come from KeyGenParameterSpec and stay per app: software keys in app data (days), or OH HUKS for hardware-backed keys (weeks). A blocker wherever the app opens it at startup (secure storage, encrypted preferences, biometric crypto, attestation)<br>6 classes name it, e.g. Landroidx/biometric/CryptoObjectUtils;, Lorg/connectbot/service/TerminalManager;, Lorg/connectbot/transport/SSH;, Lorg/connectbot/util/BiometricKeyManagerImpl;; calls KeyGenerator.getInstance("AES"), KeyPairGenerator.getInstance("EC"), KeyPairGenerator.getInstance("RSA"), KeyStore.getInstance("AndroidKeyStore") `framework/core/java/SoftwareAndroidKeyStore.java:65` |

## Package manager & manifest

_manifest features and PackageManager calls → Westlake PM semantics_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| PackageManager.queryIntentActivityOptions | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1226` |
| PackageManager.queryIntentContentProviders | stub | C9 | M | none | resolve against the APK's intent filters `framework/package-manager/java/PackageManagerAdapter.java:1254` |
| PackageManager.getComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1728` |
| PackageManager.setComponentEnabledSetting | stub | C9 | S | none | answer from the APK/package state `framework/package-manager/java/PackageManagerAdapter.java:1716` |
| Content providers installed at bind (1, initOrder honoured) | unverified | CU | verify | none | install every main-process provider in initOrder before Application.onCreate<br>InitializationProvider — probe: `probes/provider-manifest` |
| Component lookups return manifest <meta-data> | supplied | C0 | verify | none (answered from the APK inside Westlake) | apply updateFlagsForComponent semantics in the source-app PM path<br>2 components carry meta-data (0 directBootAware, e.g. ); app calls ['getActivityInfo', 'getApplicationInfo', 'getPackageInfo', 'getProviderInfo', 'getServiceInfo'] `framework/package-manager/java/SourcePackageRegistry.java:77` — probe: `probes/service-metadata` |

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
| android.media.MediaMetadataRetriever: 13 of 13 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_init()V |
| android.app.backup.BackupDataOutput: 5 of 5 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: ctor(Ljava/io/FileDescriptor;)J, dtor(J)V, setKeyPrefix_native(JLjava/lang/String;)V, writeEntityData_native(J[BI)I, writeEntityHeader_native(JLjava/lang/String;I)I |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libandroidx.graphics.path.so → 1 classes, 1 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/graphics/Path |
| libcom_google_ase_Exec.so → 3 classes, 5 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/FileDescriptor, java/lang/OutOfMemoryError, java/lang/String |
| libconscrypt_jni.so → 30 classes, 13 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/io/EOFException, java/io/FileDescriptor, java/io/IOException, java/io/InputStream |
| libjni_cb_term.so → 3 classes, 11 members | supplied | C0 | none | through the Java framework | none<br>e.g. java/lang/Character, java/util/ArrayList, java/util/List |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libc calls carrying a constant each libc numbers differently (sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>sysconf: 2 libraries, e.g. libconscrypt_jni.so, libjni_cb_term.so `framework/webview-shim/webview_bionic_shim.c:1308` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |
| Libraries mapped straight out of the APK (4 .so, extractNativeLibs=false) | supplied | C0 | verify | OH dynamic linker (cannot map zip!/ members: board test 2026-09-18) | extract at install/launch, or teach the loader zip-member mapping (WebView needs the latter too) `manifest/tools/prepare_app.py:75` |

## Limits of this map

- 6 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {'absent-from-platform': 5, 'newer-than-reference': 7}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
