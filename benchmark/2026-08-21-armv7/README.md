# ARMv7 native-evidence supplement

This is a separate native-evidence cohort for the three top-ten containers that do not ship an
ARM64 split: Amazon Shopping, Discord, and Yahoo Mail. It uses the legacy ARMv7 Westlake runtime
lock `sha256:acd4b44a4ef5cae0cc9485c6a16658f3f2609f4daf9391140cd19dfe8281c335`.

Do not merge its Java/API-gap counts with the current ARM64 benchmark. The runtime has a different
boot classpath and therefore a different contract universe. Its native evidence is useful for
explaining the records that the ARM64 run must truthfully label `target-abi-unavailable`.

For 6,516 DEX native declarations, the ABI-correct scan found:

- 4,596 direct APK JNI-export resolutions;
- 1,736 static `JNINativeMethod` table candidates;
- 157 same-library-load-scope unresolved records;
- 27 records with no attributable registration source.

The last three states remain `CU` until runtime registration/lookup evidence is captured; table
recovery narrows the provider but does not prove which class `JNI_OnLoad` registers it against.

Verify the locked subset with:

```bash
python3 scripts/verify_benchmark.py \
  --benchmark benchmark/2026-08-21-armv7 \
  --download-lock corpus/downloads-armv7.lock.json \
  --corpus-dir corpus/apks-armv7 \
  --allow-subset
```

