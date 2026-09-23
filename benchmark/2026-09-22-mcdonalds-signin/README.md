# McDonald's 26.31.1 to the sign-in screen: probes first, then the launch

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

| Probe | `0231db6` | `4993809` | `f4e0366` | `5df440b` |
|---|---|---|---|---|
| `service-metadata` (Firebase component discovery) | PASS | — | PASS | PASS |
| `provider-manifest` (providers at bind) | **FAIL**: no provider created | PASS | PASS | PASS |
| `running-app-processes` | **FAIL_NULL** | FAIL_NULL | PASS (both phases) | PASS |
| `signin-layout` (the sign-in sheet's views, fonts and drawing) | — | — | PASS, screen confirmed | PASS |
| `dialog-before-window` | — | — | **FAIL**: dialog hidden under its activity | PASS: dialog above, but at (0,0) |

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

**B11, fixed in `5df440b` without touching native code.** The native window client does not rebuild
from source today (11 of the bridge's 50 sources fail on OH headers missing from the header
carrier), so the fix had to be in Java, and it can be. Android gives a window no surface while its
activity is not yet visible. The window adapter now does the same: a dialog added on an activity
token whose base window has no OH session yet gets its input channel and frames at once, and its
OH session right after the base window's. Creation order, which is what OpenHarmony stacks by, then
equals Android's stacking order. A forced resize makes the dialog relayout onto its new surface. An
activity that never adds a window releases its dialogs after 3 s, the previous behaviour.

With it, **McDonald's shows its sign-in sheet on the board**: "Sign in or sign up", the terms and
privacy links, and Continue with Facebook / Google / Email, above the sign-in activity. The 1140×405
dialog turns out to be McDonald's "Upgrade" notice. The board has network, the reference phone had
none, and the app's remote config asks this version to update. Two differences from Android remain,
both now rows in the map:

- `wm:window-placement` (S): every window is laid out at (0,0). Android centres a dialog, and WMS
  places any window by its gravity and x/y. The "Upgrade" dialog and the probe's red dialog both sit
  at the top-left.
- `wm:dim-behind` (M): nothing is dimmed behind a dialog with `FLAG_DIM_BEHIND`; OpenHarmony has no
  such flag, so the dim layer would have to be drawn.

Touch works: a tap on "Continue with Email", delivered through the in-process tap channel to the
sheet's view root (root 2 of four, in add order: splash, Upgrade dialog, sheet, sign-in activity), opens
McDonald's "Let's start with your email" screen, and the app stays alive. A real finger reaches the
same channel through `touchfwd`. Typing into the email field (the input method) is not tried.

Also seen, not blocking: `SplashActivity`'s window stays in the window list after the sign-in
activity starts (it is at the bottom; why it is not removed is not yet traced), and a WebView-provider
startup retry loops continuously (`configured provider unavailable`, about 5,600 retries in the first
minute).

## Past the sign-in screen: placement, dim, touch, keyboard, SELinux

With the sheet on screen, the remaining differences from Android were fixed and checked on the
board, this time under **enforcing** SELinux:

| Issue | Cause | Fix |
|---|---|---|
| Dialogs at the top-left (B12) | every window laid out at (0,0); relayout gets LayoutParams only when they change | Android's `WindowLayout` places windows that do not fill the display; the render node is moved to the frame after each relayout (westlake `f6dc615`) |
| Taps on a moved window missed it | the native tap channel delivers raw screen coordinates to one root | `OHTouchInjector` picks the topmost touchable (or touch-modal) window under the pointer by OH session order and offsets the event into it |
| No dim behind dialogs (B13) | OpenHarmony has no `FLAG_DIM_BEHIND` | a translucent black window created just below the dimming window; only the topmost one per token is drawn, inactive ones transparent because hiding an OH window does not take effect |
| No keyboard (B14) | `liboh_ime_helper_capi.so` missing from the staged runtime | source-built (byte-identical to the earlier builds) and added to the runtime |
| Keyboard covers the field (B15) | the occupied area was measured against a dialog window's own size and applied to the reporting window | IME insets on the focused window against the physical display; the sheet moves above the keyboard |
| A finished activity's window stays (B17) | `finishActivity` relied on OH `TerminateAbility`, absent in direct launch | a local `DestroyActivityItem` (westlake `4fbb09b`) |
| Dialog released too early | held-back fallback fired at 3 s while McDonald's onCreate was still running | wait while the activity is not yet resumed, up to 60 s |
| Realm's pipe under enforcing (B7) | app data inherits `appdat`, where OH denies `fifo_file` | the launcher relabels the app's data tree `data_app_el2_file` (manifest `66853c2`); OH policy unchanged |
| WebView startup loop | no WebView provider staged for McDonald's | the WebView input is supplied |
| Akamai SIGILL with the WebView (B16) | the WebView input's captured shim predates the loader refusal | `--bionic-shim-build`: a source-built shim replaces it |

Checked on the board: the Upgrade notice centred under a single dim with the sign-in sheet on top;
taps reach the sheet with no aiming; the OH keyboard ("Westlake Pinyin") opens for the email field,
the sheet moves above it, and keys typed on it land in the field. `dialog-before-window` now also
checks centring and a tap on its dialog's button.

Still open, not blocking: under enforcing SELinux the app's worker threads are denied writes to a
datagram socket inherited from the launcher's `su` process (most likely its log connection), so
some logging is lost; the fix is in the native launcher (open the log afresh in the child). Real
finger input still goes through the tap channel (`touchfwd`); OH's own input dispatcher does not
know Westlake's windows.

## What the map says now

`../2026-09-21-gapmap/current/` is regenerated against `f6dc615` with these probe results applied. The
new category **Activity, window & process contracts** holds `am:process-table` (read from the stub's
handler source), `wm:dialog-stacking` (read from the window adapter: is a dialog held back until its
activity's window exists), `wm:window-placement` and `wm:dim-behind`, each confirmed by a probe on
the board. All are on the recorded path: McDonald's executes `getRunningAppProcesses`,
`getProcessMemoryInfo` and `Dialog.show` on its way to sign-in.

Against the 75d82d5 baseline, the updated harness predicts B10 and flags B9 and B11 for
verification, each naming the probe that then decided it. B9 was flagged by the map before any
launch. The `am:process-table` and `wm:dialog-stacking` rows were written after B10 and B11 were
found, so those two outcomes are not blind predictions.

B14, B15 and B17 had no row: the map does not yet check that Westlake's own helper libraries are
staged, and IME insets and activity finish need probes of their own. They are recorded as misses.
