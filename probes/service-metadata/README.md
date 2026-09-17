# ServiceInfo metadata white-box probe

This APK isolates the Android PackageManager contract used by Firebase component
discovery. It asks for its declared service with `GET_META_DATA` and verifies
that `ServiceInfo`, its component identity, and both service-scoped manifest
metadata entries are returned.

The pass marker is:

```text
[WL-SERVICE-META] verdict=PASS_SERVICE_INFO_METADATA info=true metadata=2 registrar=org.westlake.probe.ComponentRegistrar second=second-value
```

Run the exact signed APK unchanged before and after the generic shim fix. The
baseline Westlake adapter is expected to fail because `getServiceInfo()` is a
stub; conforming Android behavior passes.

The probe intentionally uses the package identity
`org.westlake.probe.defaultinterface`. The current test board cannot register a
new APK while its BMS process cannot load `libapk_installer.so`, so this lets the
probe run through the already-registered white-box slot. Always back up and
restore that slot's `base.apk` byte-for-byte around a run.
