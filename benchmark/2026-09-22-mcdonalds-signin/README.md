# McDonald's 26.31.1 to the sign-in screen: probes first, then one launch

Board: OpenHarmony 6.1.0.31, arm64, SELinux permissive for these runs (Realm's named pipe, B7).
Stack: Westlake Java rebuilt from source; the native runtime staged on the board on 2026-09-19 is
reused unchanged, because its build inputs are not reproducible from the current tree.

The order was deliberate: run the white-box probes behind the gap map's "verify" rows, fix what
they find, and only then launch McDonald's, so the launch tests predictions instead of finding
bugs one crash at a time.

| File | Contents |
|---|---|
| `probe-results.json` | Every probe verdict, per Westlake commit. `gap-map --probe-results` applies a result only to the commit it was measured on |

## Probes

The same signed probe APKs run unchanged on the board (`probes/*`).

| Probe | `0231db6` | `4993809` | `f4e0366` |
|---|---|---|---|
| `service-metadata` (Firebase component discovery) | PASS | — | PASS |
| `provider-manifest` (providers at bind) | **FAIL**: no provider created | PASS | PASS |
| `running-app-processes` | **FAIL_NULL** | FAIL_NULL | PASS (both phases) |
| `signin-layout` (the sign-in sheet's views, fonts and drawing) | — | — | PASS, screen confirmed |
| `dialog-before-window` | — | — | **FAIL**: dialog hidden under its activity |

**Providers (B9, fixed in `4993809`).** `SourcePackageRegistry` left `ComponentInfo.processName`
null for components without `android:process`; PackageManagerService fills that in before anyone
reads it, and the registry is that server side. The bind-time filter keeps only providers whose
process matches, so every main-process provider was dropped and none was created before
`Application.onCreate`. Firebase, Forter and ML Kit all initialize that way. The gap map had this
row as "verify, `probes/provider-manifest`"; the probe decided it.

**Process table (B10, fixed in `f4e0366`).** In direct launch `IActivityManager` is a
`java.lang.reflect.Proxy` whose handler returns a type default: null for every object result.
McDonald's makes 23 distinct `IActivityManager` calls on the recorded path; six return objects.
Each was followed to the app code behind it:

| Call | Android facade | Caller on the path | With null |
|---|---|---|---|
| `getRunningAppProcesses` | returns it as is | Kochava `AppUtil.b` | **iterates it: NPE** |
| `getServices` | `getRunningServices` returns it as is | Kochava `AppUtil.b` | **iterates it: NPE** |
| `getProcessMemoryInfo` | returns it as is | New Relic `Sampler.sampleMemory` | caught, sample dropped |
| `getIntentSenderWithFeature` | `PendingIntent` null | Firebase `zzkr`, WorkManager `ForceStopRunnable` | AlarmManager is null on OH, so skipped; `FLAG_NO_CREATE` path handles null |
| `getContentProvider` | provider not found | SQLite WAL flags reading `settings` | answered by Westlake's local settings provider first |
| `getHistoricalProcessExitReasons` | null becomes an empty list | WorkManager | fine |

Since Android 5.1 an ordinary app sees only its own processes and services, so the faithful answer
needs no OpenHarmony process table. The stub and `ActivityManagerAdapter` now answer from
`CallerProcess`. The August note that interface dispatch returns null before reaching the proxy's
handler does not hold on this runtime: the probe passes through the handler.

## The launch

With both fixed, McDonald's went past the previous frontier (`LocationManager`, rank 34,988 of the
44,451-method Android trace), started `LoginRegistrationActivity`, and kept drawing frames. The
screen stayed white.

The board's window list gives the reason:

| OH window | What it is (Android) | Added | OH type | Z |
|---|---|---|---|---|
| 57 | `SplashActivity`, base window | 1st | 1001 | 103 |
| 58 | a 1140×405 dialog, shown from the sign-in activity before its window exists | 2nd | 1001 | 104 |
| 59 | the sign-in bottom sheet (full-screen dialog) | 3rd | 1001 | 105 |
| 60 | `LoginRegistrationActivity`, base window | 4th | 1001 | **106, on top** |

Android stacks an activity's dialogs above its base window whatever order they were added in.
Here the two dialogs are added from `onCreate`/`onResume`, before `handleResumeActivity` adds the
activity's own window. OpenHarmony stacks this app's sub-windows by creation order, so the opaque
activity window covers the sheet. Three levers were measured, and none changes the order: the
native raise-to-top at creation (§385), skipping it, and creating the base window as
`WINDOW_TYPE_MEDIA` (1000). The last-created window is always on top. `probes/dialog-before-window`
reproduces it without McDonald's: a red dialog shown from `onCreate` is invisible under the green
activity.

**This is the remaining blocker to the sign-in screen (B11).** The fix belongs in the native window
client (`oh_window_manager_client.cpp`): give a base window its place below the dialogs already
attached to its token, for example by creating the activity's session at launch, before `onCreate`
can show a dialog. The Java side cannot do it, because the session is created against the window
that `addToDisplay` receives. The bridge does not currently rebuild from source: 11 of its 50
sources fail on OH headers missing from the header carrier (`json/json.h` from jsoncpp in 9 of them,
plus an input-method and a bundle-manager header).

Also seen, not blocking: `SplashActivity`'s window stays in the window list after the sign-in
activity starts (it is at the bottom; why it is not removed is not yet traced), and a WebView-provider
startup retry loops continuously (`configured provider unavailable`, about 5,600 retries in the first
minute).

## What the map says now

`../2026-09-21-gapmap/current/` is regenerated against `f4e0366` with these probe results applied. The
new category **Activity, window & process contracts** holds `am:process-table` (read from the stub's
handler source; measured PASS) and `wm:dialog-stacking` (measured FAIL, effort M). Both are on the
recorded path: McDonald's executes `getRunningAppProcesses`, `getProcessMemoryInfo` and
`Dialog.show` on its way to sign-in.

Against the 75d82d5 baseline, the updated harness predicts B10 and flags B9 and B11 for
verification, each naming the probe that then decided it. B9 was flagged by the map before any
launch. The `am:process-table` and `wm:dialog-stacking` rows were written after B10 and B11 were
found, so those two outcomes are not blind predictions.

Open before the sign-in screen: B11 (window stacking, native), and B7 (Realm's named pipe:
OpenHarmony policy, the board runs permissive).
