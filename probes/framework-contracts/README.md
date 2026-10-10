# framework-contracts probe

Measures the framework contracts the gap map reports open in many apps, on the provider, per build
(ADR-0001). One line per contract, named by the gap-map row it measures:

    [WL-CONTRACT] <row id> PASS <what Android's answer looked like>
    [WL-CONTRACT] <row id> ABSENT <the truthful answer of a device without the feature>
    [WL-CONTRACT] <row id> FAIL <exception, or an answer Android would not give>
    [WL-CONTRACT] done

The package manager's queries are asked for the probe's own components, declared in its manifest
(an activity, a receiver and a provider, each with its own action), so each has one right answer.

| row | the check |
|---|---|
| `svc:audio` | stream volumes, the output sample rate and burst, output devices, audio focus |
| `pm:call:queryIntentContentProviders` | its own provider, found by its intent filter |
| `pm:call:queryIntentActivityOptions` | its own second activity, found by its action |
| `pm:call:queryBroadcastReceivers` | its own receiver, found by its action |
| `pm:call:setComponentEnabledSetting` | the second activity disabled no longer resolves |
| `pm:call:getComponentEnabledSetting` | the disabled state read back |
| `jni:android.view.KeyCharacterMap` | the virtual keyboard's map: `KEYCODE_A` and the events for "ab" |
| `svc:jobscheduler` | a job with no deadline, scheduled and run within 15 s |
| `svc:vibrator` | `hasVibrator`, and `vibrate` returning (ABSENT when there is none) |
| `svc:sensor` | the sensor list, and accelerometer events within 5 s (ABSENT when none is listed) |
| `svc:phone` | the phone type, SIM state and operator (ABSENT when the type is NONE) |
| `svc:keyguard` | `isKeyguardLocked` and `isDeviceSecure` |
| `svc:textclassification` | the classifier classifies a URL off the main thread (ABSENT when it is `NO_OP`) |
| `svc:user` | `isUserUnlocked`, the profiles hold the app's own user, a serial number |
| `svc:fingerprint` | the manager and its hardware (ABSENT with neither the manager nor `FEATURE_FINGERPRINT`) |
| `svc:biometric` | a `BiometricManager`, which Android always has; `canAuthenticate` (ABSENT for no hardware) |
| `svc:captioning` | a `CaptioningManager` with a font scale |
| `svc:media_metrics` | a `MediaMetricsManager` that creates a playback session |
| `svc:grammatical_inflection` | a `GrammaticalInflectionManager` that answers the app's grammatical gender |
| `pm:call:getInstallerPackageName` | the installer's name (null, as for an app installed from a file) and the install source |
| `am:launch-lifecycle` | the probe's own LifecycleActivity, started: its callbacks over 2 s on top are onCreate, onStart, onResume, with no pause |
| `am:activity-result` | startActivityForResult to the probe's own ResultActivity, which sets a result and finishes: onActivityResult gets it |
| `am:start-unresolved` | starting an activity nothing handles throws ActivityNotFoundException (no row yet) |

`probes/run_suite.py` records each line as a result of its own, and `gap-map --probe-results` applies
it to the row it names. Build with `./build.sh`; the APK is pinned in the launcher's
`app-inputs.lock.json` as `framework-contracts-probe`.
