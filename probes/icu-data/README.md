# ICU and time-zone data probe

Which locale and time-zone answers the runtime gives an app. Each check prints one line to stderr
(and to the screen):

```text
[WL-ICU] <check> ok=<value>
[WL-ICU] <check> FAILED <exception> @ <top frames>
```

Android answers every check, so any `FAILED`, `null` or empty zone list is a gap. The checks
separate the loaders: ICU4J (`android.icu.*`), the native ICU4C behind `java.util.Locale` display
names (`LocaleNative` in `libicu_jni`), libcore's tzdata (`java.util.TimeZone`), and `java.time`'s
zone rules provider. Display-name calls are repeated in a fixed order, because a call can succeed
once and return null the next time. Build with `./build.sh`.

## 2026-09-26 result (framework 57)

| check | answer | meaning |
|---|---|---|
| ICU4J data files | 1 | ICU data loads |
| `ULocale`, `SimpleDateFormat` (fr) | "German (Germany)", "jeudi" | locale data works |
| `Locale.getDisplayLanguage` / `getDisplayName` | null or NPE on about half the calls | `libicu_jni` bug, below |
| ICU4J zone IDs, `java.time` zone IDs | 0 | no tz data |
| `TimeZone.getTimeZone("Europe/Paris")` | GMT, offset 0 | silently wrong |

- **Display names:** `ScopedIcuLocale` (AOSP `libcore_bridge`) leaves its `UErrorCode`
  uninitialized, and ICU returns early when the status already reads as a failure. AOSP builds
  with `-ftrivial-auto-var-init=zero`, so it never shows there. The runtime's `libicu_jni` was
  built without it. Rebuilt with the flag (Westlake `build_android_native.py`), all 15
  display-name calls succeed.
- **Time zones:** the stage's `tzdata/` directory is empty, so nothing registers zones.
