# `getServiceInfo(GET_META_DATA)` shim slice

Date: 2026-08-23/24

Target: unchanged X 12.17.0 and the Westlake arm64 direct-launch runtime

## Diagnosis

X no longer fails in running-process discovery or provider installation. Its
Firebase initialization provider is created with four metadata entries, but
Firebase still reports `FirebaseCrashlytics component is not present`.

X's exact Firebase component-discovery bytecode asks PackageManager for
`ComponentDiscoveryService` using `GET_META_DATA`. The APK manifest declares 16
registrars on that service, including:

```text
com.google.firebase.components:com.google.firebase.crashlytics.CrashlyticsRegistrar
    = com.google.firebase.components.ComponentRegistrar
```

The bridge implementation made that discovery deterministically empty:
`PackageManagerAdapter.getServiceInfo()` was an explicit stub returning null.
This is an Android PackageManager contract gap, not an app-specific Firebase or
Crashlytics problem.

## White-box baseline

The signed probe at `probes/service-metadata/out/service-metadata-probe.apk`
declares one service and two service-scoped string metadata entries. It calls
the same API from `Application.onCreate()` and verifies the component identity,
metadata count, keys, and values.

Probe SHA-256:
`96aee03964545692e6b04358eb55d2521357a4a86638ad26dfef02a0d57fbced`

Baseline Westlake result:

```text
[WL-SERVICE-META] verdict=FAIL exception=android.content.pm.PackageManager$NameNotFoundException: ComponentInfo{org.westlake.probe.defaultinterface/org.westlake.probe.defaultinterface.MetadataService}
```

Evidence is in `probes/service-metadata-before/`. The test APK uses the
already-registered default-interface probe identity because the board's current
BMS process cannot load `libapk_installer.so`; the original slot APK is backed
up on-device and will be restored byte-for-byte.

## Generic fix under validation

- Parse service-scoped `<meta-data>` without merging it into application or
  provider metadata.
- Preserve `enabled`, `exported`, `directBootAware`, `permission`, and process
  name on the service component.
- Expose a manifest `services` array at the OH boundary.
- Resolve the requested component and populate a typed `Bundle` only when
  `GET_META_DATA` is requested.
- Return null for an unknown component so Android's public facade continues to
  throw `NameNotFoundException`.

No Firebase class or X package name is special-cased.
