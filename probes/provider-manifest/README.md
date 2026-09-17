# Provider-manifest white-box probe

This APK distinguishes three manifest cases that the direct-launch boundary must
not conflate:

- two `<queries><provider>` package-visibility declarations, which must never be
  installed as `ContentProvider` components;
- one provider in the application's main process, which must be created once;
- one provider in `:remote`, which must not be installed in the main process.

The pass marker is:

```text
[WL-PROVIDER-PROBE] verdict=PASS_QUERY_EXCLUDED_REMOTE_FILTERED mainProviderCreates=1 remoteProviderCreates=0
```

Run the exact signed APK first against the baseline Westlake parser and then
unchanged against the corrected parser. A stock Android run is an additional
control when an Android target is available.
