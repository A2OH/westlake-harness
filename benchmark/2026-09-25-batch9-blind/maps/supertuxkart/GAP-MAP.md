# org.supertuxkart.stk 1.4 → OpenHarmony: API shim gap map

Provider: Westlake `corpus2-fixes` @ `1baca65181`; OH board: OpenHarmony 6.1.0.31, arm64, SELinux enforcing policy as loaded. Target SDK 30.

## Summary

| Category | How it reaches OH | Rows | Gaps | Effort profile |
|---|---|---|---|---|
| Java framework API | APK dex references − Westlake boot jars, filtered by API level | 4 | 4 | 4×verify |
| System services | getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem | 8 | 4 | 1×verify, 2×S, 1×M |
| Keystore & crypto providers | JCA provider names the code selects → providers the Westlake runtime installs → OH HUKS | 0 | 0 | — |
| Package manager & manifest | manifest features and PackageManager calls → Westlake PM semantics | 0 | 0 | — |
| Activity, window & process contracts | what system_server would answer, answered in-process by Westlake in direct launch → white-box probes | 0 | 0 | — |
| Windows & surfaces | how the first screen renders → whether it needs a surface of its own → OH window/surface model | 1 | 1 | 1×L |
| Framework natives | platform classes the app uses → their native methods → libraries the runtime registers them from | 3 | 3 | 1×S, 2×M |
| Java APIs called from native code | JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars | 1 | 0 | — |
| Native platform symbols | packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence) | 6 | 5 | 1×XS, 1×S, 2×M, 1×L |
| Native loading & packaging | how the libraries are packaged → what the OH linker can map | 1 | 1 | 1×verify |
| Process sandbox & policy | objects the code creates → what OH SELinux lets an app create | 0 | 0 | — |
| External services & SDK behaviour | SDKs that expect Google services or probe the device | 0 | 0 | — |

Effort: **XS** hours: configuration, labelling, or forwarding one symbol; **S** about a day: a truthful local answer, a missing export, or a handful of methods; **M** days: an Android facade over an existing OH capability, for the methods this app calls; **L** weeks: port or build a subsystem or bridge; **OH** needs an OpenHarmony platform change (policy, kernel, system ability): outside Westlake; **verify** implemented according to source; run the conformance probe before trusting it

## Rows that have blocked an app at startup before

From the blockers ledger: gaps this app has in common with an app that died on them.

| Row | Verdict | Blocked |
|---|---|---|
| `svc:uimode` | supplied | burgerking (blind-bk), fixed in d689e67 |
| `window:engine-surface` | missing | ppsspp (loop-1), open; mindustry (loop-1), open; shatteredpd (batch-4), open; unciv (batch-5), open |

## Java framework API

_APK dex references − Westlake boot jars, filtered by API level_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Java library | hollow-candidate | C9 | verify | none (library code inside Westlake) | check each hollow body against AOSP<br>java.io.InputStream.close, java.net.InetAddress.getHostAddress |
| App framework | hollow-candidate | C9 | verify | ability_runtime | check each hollow body against AOSP<br>android.app.Activity.onWindowFocusChanged |
| Views & windows | hollow-candidate | C9 | verify | window_manager / render_service | check each hollow body against AOSP<br>android.view.View.onKeyPreIme |
| Other | probe-only | C8 | verify | unmapped | confirm the probed class should (not) exist on this platform<br>com.getkeepsafe.relinker.ReLinker, com.getkeepsafe.relinker.ReLinker$LoadListener |

## System services

_getSystemService name → AOSP fetcher/binder → Westlake provision → OH subsystem_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| usb | null | C4 | M | usb_manager | Android UsbManager facade over usb_manager<br>1 call sites, e.g. org.libsdl.app.HIDDeviceManager.initializeUSB |
| sensor | inert | C4 | S | sensors | Android SensorManager facade over sensors<br>1 call sites, e.g. org.libsdl.app.SDLSurface.<init> |
| vibrator | inert | C4 | S | sensors/miscdevice | Android Vibrator facade over sensors/miscdevice<br>1 call sites, e.g. org.libsdl.app.SDLHapticHandler.pollHapticDevices |
| bluetooth | unresolved | CU | verify | communication/bluetooth | trace the helper's binder; then treat as null, inert or supplied<br>2 call sites, e.g. org.libsdl.app.HIDDeviceManager.initializeBluetooth `BluetoothFrameworkInitializer.java:100` |
| clipboard | supplied | C0 | verify | miscservices/pasteboard | none<br>1 call sites, e.g. org.libsdl.app.SDLClipboardHandler.<init> |
| input_method | supplied | C0 | verify | inputmethod_framework | none<br>6 call sites, e.g. org.libsdl.app.SDLActivity$SDLCommandHandler.handleMessage `framework/core/java/OHServiceManager.java:105` |
| uimode | supplied | C0 | verify | display / theme | none<br>1 call sites, e.g. org.libsdl.app.SDLActivity.isAndroidTV |
| window | supplied | C0 | verify | window_manager | none<br>4 call sites, e.g. org.libsdl.app.SDLActivity.sendCommand `framework/core/java/OHServiceManager.java:96` |

## Windows & surfaces

_how the first screen renders → whether it needs a surface of its own → OH window/surface model_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| First screen drawn by an engine into its own SurfaceView | missing | C9 | L | window_manager / render_service: one OH window per activity | give each SurfaceView its own OH surface (a child RS node) instead of the activity's window<br>packages SDL, a NativeActivity engine |

## Framework natives

_platform classes the app uses → their native methods → libraries the runtime registers them from_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| android.hardware.usb.UsbDeviceConnection: 13 of 13 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_bulk_request(I[BIII)I, native_claim_interface(IZ)Z, native_close()V, native_control_request(IIII[BIII)I, native_get_desc()[B, native_get_fd()I, native_get_serial()Ljava/lang/String;, native_open(Ljava/lang/String;Ljava/io/FileDescriptor;)Z |
| android.media.AudioRecord: 27 of 27 natives unregistered | missing | C3 | M | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_disableDeviceCallback()V, native_enableDeviceCallback()V, native_finalize()V, native_getMetrics()Landroid/os/PersistableBundle;, native_getPortId()I, native_getRoutedDeviceId()I, native_get_active_microphones(Ljava/util/ArrayList;)I, native_get_buffer_size_in_frames()I |
| android.hardware.usb.UsbDevice: 2 of 2 natives unregistered | missing | C3 | S | the JNI half of the framework class (libandroid_runtime in AOSP) | port the AOSP JNI source for the class and register it at startup, before application bind<br>open: native_get_device_id(Ljava/lang/String;)I, native_get_device_name(I)Ljava/lang/String; |

## Java APIs called from native code

_JNIEnv FindClass/Get*ID names in packaged .so → Westlake boot jars_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libSDL2.so → 4 classes, 15 members | supplied | C0 | none | through the Java framework | none<br>e.g. android/content/IntentFilter, android/os/Environment, java/lang/Class, java/lang/String |

## Native platform symbols

_packaged .so imports → OpenHarmony plus the NDK Westlake packages (package / libc-abi / weld / absence)_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| libaaudio.so entry points looked up by name at runtime, not supplied (19) | unresolved | C1/C2 | L | dlopen("libaaudio.so") + dlsym, resolved against whatever the search path reaches first | supply libaaudio.so's entry points, or confirm the caller degrades without them: this row cannot tell a lookup that happens from a string that is never used<br>19 public NDK symbols of libaaudio.so appear as literals: AAudioStreamBuilder_delete, AAudioStreamBuilder_openStream, AAudioStreamBuilder_setErrorCallback, AAudioStreamBuilder_setFormat, AAudioStreamBuilder_setSampleRate, AAudioStream_close … — probe: `probes/webview-boundaries measures the search path; resolving each name on the board is what settles whether the lookup would succeed` |
| NDK weld · audio: 1 symbols | missing | C4 | M | audio_framework (OHAudio) | AOSP NDK source above, audio_framework (OHAudio) below<br>open: SL_IID_ANDROIDCONFIGURATION |
| NDK weld · sensors: 11 symbols | missing | C4 | M | sensors | AOSP NDK source above, sensors below<br>open: ASensorEventQueue_disableSensor, ASensorEventQueue_enableSensor, ASensorEventQueue_getEvents, ASensorEventQueue_setEventRate, ASensorManager_createEventQueue, ASensorManager_destroyEventQueue, ASensorManager_getInstance, ASensorManager_getSensorList |
| NDK package: 5 symbols compiled from AOSP source | missing | C1 | S | none beyond what Westlake already provides | compile the AOSP source (configuration.cpp) and deploy it<br>open: AConfiguration_delete, AConfiguration_fromAssetManager, AConfiguration_getCountry, AConfiguration_getLanguage, AConfiguration_new |
| NDK truthful-absence: 19 symbols | absent | C5 | XS |  | export entry points that report the feature unavailable<br>open: glBindFramebufferOES, glBlendEquationOES, glBlendEquationSeparateOES, glBlendFuncSeparateOES, glCheckFramebufferStatusOES, glColor4f, glColorPointer, glDeleteFramebuffersOES |
| libc calls carrying a constant each libc numbers differently (sysconf) | supplied | C0 | verify | OH musl: the same selector number means a different limit than in bionic | translate the selector by name at the libc boundary for every library built against bionic; the call resolves and returns a plausible number either way, so nothing fails at load time<br>sysconf: 2 libraries, e.g. libSDL2.so, libmain.so `framework/webview-shim/webview_bionic_shim.c:1308` |

## Native loading & packaging

_how the libraries are packaged → what the OH linker can map_

| Item | Verdict | Class | Effort | OH touchpoint | Shim / evidence |
|---|---|---|---|---|---|
| Runtime libraries its own loader will not open (libicu_jni.so) | unresolved | C3 | verify | Runtime.nativeLoad in the runtime's own OpenJDK stub | compare the staged library's methods against the tables the runtime's own stubs register (art-build/stubs, registerNativesOrSkip) and ship any remainder under a name the filter does not match. ship the library under a name none of those substrings match, or narrow the stub to the libraries the runtime really does link in. A load that reports success it did not perform cannot be told from one that worked, so nothing downstream can detect this.<br>a property of the runtime, not of this app: it holds for every app it launches `art-build/stubs/openjdk_stub.c:1315` |

## Limits of this map

- 0 service requests use computed names and are not resolved statically.
- Java absences excluded by API level: {}.
- Native code calling back into Java was matched from library strings against a reference android.jar; names built at runtime or encrypted are invisible.
- `supplied` means the provider source answers the contract; `verify` rows need their conformance probe on the board.
- Semantic mismatches (right name, wrong behaviour) remain invisible until a probe or the Android baseline compares them.
