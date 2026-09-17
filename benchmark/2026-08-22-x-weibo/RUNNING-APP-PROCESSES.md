# `getRunningAppProcesses()` shim slice

Date: 2026-08-22/23

Runtime lock: `sha256:101c9c5d49eb7371efd1dfb61c0dc4fd332da5d30c9803bd2a06f285fce889ee`

Target: Westlake arm64 on OpenHarmony

## Outcome

The first deterministic X cold-launch blocker is retired. Before the fix, all
three unchanged X runs failed while constructing `TwitterApplication` because
`ActivityManager.getRunningAppProcesses()` returned `null`. After the fix, all
three unchanged runs passed that call and advanced to the same next blocker:
an empty provider class name in the direct-launch manifest/provider path.

The minimal faithful behavior for the no-AMS direct path is a non-null list
containing the caller process. It reports the actual process name, pid, uid,
foreground importance, and package. The production adapter implements the same
fallback when its OpenHarmony process query cannot provide a list.

## Locked applications

| App | Exact version | Container SHA-256 | Static candidates | Direct absences | Unresolved |
| --- | --- | --- | ---: | ---: | ---: |
| X | 12.17.0-release.0 (`312170000`) | `558a30172835845989258ccb22043f055f3fbd734aca9c6c2b938effff1eacb6` | 437 | 131 | 272 |
| Weibo | 16.8.1 (`8113`) | `ffb64d2232fc2c85a9995ca988cf63292ce3808892088aaa86724a7b3e70c0d4` | 747 | 212 | 1,337 |

The Weibo unresolved total includes 1,321 native declarations. Static findings
are prioritization candidates, not 747 or 1,337 confirmed runtime failures.

## Controlled evidence

| Layer | Before | After | Interpretation |
| --- | --- | --- | --- |
| White-box probe, `Application` | `FAIL_NULL` | `PASS_SELF_VISIBLE`, count 1 | Contract fixed at earliest app lifecycle point |
| White-box probe, `Activity` | `FAIL_NULL` | `PASS_SELF_VISIBLE`, count 1 | Same result after Activity creation |
| Unchanged X cold launch | 3/3 `TwitterApplication` NPE | 3/3 pass C6 and reach provider error | Original blocker retired reproducibly |
| Stock Noice 2.5.1 control | n/a | bind OK, MainActivity resumed/visible, repeated `drew=1` | No broad lifecycle/render regression |
| Unchanged Weibo 16.8.1 | n/a | reaches `WeiboApplication`; 28 providers populated | Independent broad stress run; it does not reach C6 before its native-load blocker |

The Weibo run stops at the direct-launch native-library mapping boundary:
`DexPathList.findLibrary aqts -> <missing>`, followed by missing
`HookThreadSuspend.nHookThreadSuspendInit(int)`. The exact 81 arm64 split
libraries are present and device-verified, so the next Weibo task is to carry
split/native library directories into the app classloader. This is separate
from `getRunningAppProcesses()`.

## Why the final fix is at the framework boundary

The direct-mode `IActivityManager` is a Java dynamic proxy. ART currently logs
the interface method but its unresolved interface-dispatch recovery path
synthesizes the default object return (`null`) before reaching the proxy's
`InvocationHandler`. JIT-on and JIT-off runs behave the same. Patching only the
handler therefore cannot repair this path.

The exact deployed `framework.jar` now makes
`ActivityManager.getRunningAppProcesses()` fall back only when the service
result is null or empty. This confines the compatibility behavior to the
Android facade while preserving any real non-empty backend result. The proxy
handler and concrete `ActivityManagerAdapter` also return the same caller
singleton as defense-in-depth and for the future AMS/BMS path.

## Artifacts and rollback

Active device/runtime artifacts:

| Artifact | Patched SHA-256 | Device rollback copy |
| --- | --- | --- |
| `framework.jar` | `a51e47a6dc8e82477ca250cef22a30ed77a5afadc68ec55ec3c2ee9eb27624c5` | `/data/local/tmp/asx/fw/framework.jar.bak-pre-running-procs-20260823` |
| `adapter-runtime-bcp.jar` | `f67733d8655ff330ad04761fa3211276566d2d5bc41c26c82952d5a5d36c2384` | `/data/local/tmp/asx/fw/adapter-runtime-bcp.jar.bak-pre-running-procs-20260823` |
| `oh-adapter-framework.jar` | `8d7d4c6d0add622fc5a539a3294f90776834d99cfaf993682f5da3c0d4651406` | `/data/local/tmp/asx/fw/oh-adapter-framework.jar.bak-pre-running-procs-20260823` |

Durable patched jars are in `fixes/running-app-processes/`. The unchanged X
base APK was rechecked on-device as
`5e9c8e4bbb525a2140292f8f96ab6cc0af403dfcd07667b8678aebb44fb52354`.
The unchanged Weibo base/splits were rechecked as `4754e346...`, `5020b45d...`,
and `58fa1898...`; the canonical device hash over all 81 library hash records is
`64bed70e80ae83c61d0c93a1960064152e92ec09fb3693f8442babd41329062a`.

## Constraints and next priority

- Real BMS/AMS launch could not be exercised: installing either production APK
  fails in the current BMS with error `9568260`, even after moving manual app
  directories out of the way. The controlled runs use the established
  BMS-free direct launcher.
- There is no connected Android device or installed emulator/system image, so
  the Android-side white-box control remains unrun. The probe APK is preserved
  for that control.
- Rebuilding the ten-jar boot image is not currently viable: dex2oat repeats
  the known unstarted-runtime CAS spin. The board is running the jars imageless,
  which makes the deployed bytes authoritative for these runs.
- Highest next X priority is provider metadata fidelity: reject or repair
  manifest provider entries with an empty `ProviderInfo.name`, then rerun the
  unchanged X APK. The later object-graph exception is downstream of the bind
  failure and should not be patched directly.
- Highest next Weibo priority is split/native classloader propagation, not an
  API shim: populate split source/resource paths and the exact arm64 native
  library directory before evaluating its next runtime API call.

## Evidence map

- White-box before/after: `probes/running-app-processes-westlake/` and
  `probes/running-app-processes-after-fix/`
- X before/after, three repetitions each: `runs/x-cold-00{1,2,3}/` and
  `runs/x-after-running-procs-00{1,2,3}/`
- Stock control: `controls/noice-stock-after-fix/`
- Weibo direct runs: `runs/weibo-after-running-procs-00{1,2}/`
- Static scans: `apks/com.twitter.android.json` and `apks/com.sina.weibo.json`
