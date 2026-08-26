# Why the 32,736-record result was redone

The preserved 2026-08-20 result contained 32,736 `CU` records: 32,653 native declaration records
(19,887 unique contracts) and 83 reflective-load records (47 unique target contracts). It was not a
count of missing shim functions. The native detector treated every packaged ABI as usable, treated
any `JNI_OnLoad` as a reason to keep every unmatched declaration opaque, and did not consult
runtime-bridge JNI exports.

## Corrected ARM64 result

The API-gap result is stable: 1,586 unique Java candidates, including 594 directly absent
classes/members. The native/reflection `CU` headline is now 37,330 records: 37,247 native plus the
same 83 reflection records.

The increase is a correction, not a regression:

- Amazon Shopping, Discord, and Yahoo Mail contain only `armeabi-v7a`. The old scan borrowed 4,596
  direct JNI exports from those 32-bit ELFs while describing an ARM64 runtime. The corrected ARM64
  scan marks all 6,516 declarations in those apps `target-abi-unavailable`.
- Two TikTok native declarations resolve through the runtime bridge and are no longer `CU`.
- Net change: `+4,596 - 2 = +4,594` native `CU` records.

Across all 49,941 DEX native declaration records, the corrected ARM64 funnel is:

| State | Records | Meaning for porting |
|---|---:|---|
| APK JNI export resolved | 12,692 | remove from native shim queue |
| Runtime bridge export resolved | 2 | remove from queue; the old scanner missed these |
| Target ABI unavailable | 6,516 | architecture/corpus readiness issue, not an API-shim gap |
| Static registration-table candidate | 2,649 | provider narrowed; wait for runtime binding evidence |
| Library/load-scoped candidate | 9,989 | provider scope narrowed; wait for runtime binding evidence |
| Registration source unattributed | 18,093 | highest-value native trace queue |

After excluding the wrong-ABI cohort, the executable ARM64 runtime watchlist contains 30,731 native
records and 102 caller-keyed reflection sites. `runtime-watchlist.json` is generated locally and
ignored because it is large; the report and registry retain the aggregate counts.

## ARMv7 supplement

The same three containers were scanned separately against a real ARMv7 Westlake runtime lock. That
ABI-correct cohort turns its 6,516 declarations into 4,596 direct JNI-export resolutions, 1,736
static table candidates, 157 load-scoped candidates, and 27 unattributed records. See
[`../2026-08-21-armv7/README.md`](../2026-08-21-armv7/README.md).

An APKPure retry using [apkeep's documented `arch=arm64-v8a`
option](https://github.com/EFForg/apkeep/blob/master/USAGE-apkpure.md) returned files byte-identical
to the preserved inputs for all three packages, so no ARM64 artifact was relabeled or substituted.

## Dynamic evidence status

The harness now parses existing Westlake JNI markers and structured events into safe states. In
particular, `[WESTLAKE-JNIMISS]` is a primary-lookup miss, not a terminal failure; a later registry
or global-`dlsym` hit wins. A read-only live control snapshot contained 20 such primary misses and
20 corresponding fallback hits, which validated the parser against real output.

That control was not merged into this benchmark. Its deployed boot JAR hashes differed from the
ARM64 runtime lock and the board was running a separate `libart` JIT experiment. A top-ten runtime
ledger must be collected on the exact runtime lock, with the APK hash and loaded `libart` hash in
every run envelope. See [`../../runtime/TRACE-EVIDENCE.md`](../../runtime/TRACE-EVIDENCE.md).

## Verification

```bash
python3 scripts/verify_benchmark.py --benchmark benchmark/2026-08-21
python3 scripts/verify_benchmark.py \
  --benchmark benchmark/2026-08-21-armv7 \
  --download-lock corpus/downloads-armv7.lock.json \
  --corpus-dir corpus/apks-armv7 \
  --allow-subset
PYTHONPATH=harness python3 -m unittest discover -s tests -v
```
