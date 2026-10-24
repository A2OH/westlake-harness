# r90: the per-build changes in the whole corpus (2026-10-22)

r90 reran the whole corpus, r89's 369 apps, on build 119. It is the first full round since ADR-0001
moved the loop to per-build conformance probes, the apps a change reaches and the calibration flows.
Every Westlake change since r89 had passed those checks one build at a time; r90 tried them together
on every app.
- **Build 119:** build 99, plus the Westlake changes since r89: the audio service, activity results,
  the launch lifecycle, popup windows, the window configuration, focus handoff after a dialog,
  notifications, recreation, dialog placement, alarms, jobs, starts that leave the app, and toasts.
- **The bionic shim:** AAudio over OHAudio. **The runtime override:** r89's, plus the natives for the
  audio port, the notification switch and the transaction listener.
- **The gap maps' launch args:** r88's, as in r89.
- Host-compiled code for the same eleven apps, against build 119's boot image, and the input cache.
- SELinux enforcing throughout; 9.5 hours.

This record covers what r90 found against r89, build 120's fixes for its regressions, what still
stops the apps short of drawing, and the harness changes the round asked for.

Files, made with today's harness:
- `r90-lifecycle.json`: r90 classified
  (`python -m harness.westlake_gap.lifecycle <logs> --json r90-lifecycle.json`).
- `r90-score.json`: its first blockers scored against gap maps made with today's harness, against
  build 119 (`scripts/score_first_blockers.py`).
- `r90-build120-lifecycle.json`: the twelve apps that drew in r89 and not in r90, again on build 120.

## Regression check against r89

- **Coverage:** all 369 apps ran.
- **Drawing:** 346 of 369 (r89: 356).
- **Up:** usp and Zoom, both flaky in r89's record. usp's GL thread and libhwui race to make its
  window's EGL surface, and libhwui won this time. Zoom's video thread did not fault.
- **Down:** twelve apps.
  - **Seven died on a start that threw.** Since build 114, a start that nothing here handles throws
    ActivityNotFoundException, as on Android, where it is thrown for an intent no installed app
    handles. These apps started screens that every Android device has, and none of them catches the
    exception:
    - a screen of Settings: aat (all-files access), Clock and LuxAlarm (full-screen
      notifications), stims (usage access) and WiFiAnalyzer (location);
    - socks5: the VPN consent that `VpnService.prepare` names (`com.android.vpndialogs`);
    - viewer: the document picker (`OPEN_DOCUMENT`), from its library's `onStart`.

    Before build 114 such a start reported success and opened nothing, and in r89 all seven drew.
  - **AnkiDroid died as it started.** Its launcher activity starts its deck picker for a result and
    finishes at once. The result was checked against a caller that was still there, then
    scheduled; by the time it ran, the caller's destroy had removed its record, and the transaction
    threw "Activity client record must not be null" on the main thread. The activity-result probe
    line passed on build 119: its caller never finished first.
  - **Obtainium and ObtainX abort in Mali's backend thread.** Both drew. About 3 s after start,
    WorkManager's job runs their background update check: a second, headless Flutter engine with
    its own Impeller Vulkan context. The worker reports success, and 0.1 to 0.2 s later
    `mali-cmar-backe` aborts in `base_jd_event_term`. Before build 113 no job ran, and the check never
    ran either. Waterfly III runs two Flutter Vulkan engines and keeps both; what trips Mali here,
    the headless engine's teardown or a second Vulkan device in the process, is open.
  - **Waze and Reddit drew no frame before the screenshot.** Both are timing, not the build.
    - Waze's own start-up marks are the same in r89 and r90: its main screen at 15 s, then a 37 s
      stall on the main thread, ready at 54 s.
    - About 58 s after start, its map's SurfaceView gets an OH window of its own, which shows black
      until the map draws into it. The screenshot comes at about 60 s. It showed black whenever it
      fell within about a second of that window (r90, and three of four relaunches with the same
      wait), and Waze when the window came earlier (r89; 53 s in one relaunch).
    - With a 90 s wait it drew in both relaunches on build 120.
    - Reddit's splash waits on its servers, as in r88 and r89.

## Build 120: the regressions fixed

Build 120 (Westlake #45) is build 119 with two fixes:
- **Results only to live callers, delivered at once.** A result whose caller is finishing or gone is
  dropped, as the activity manager keeps a result only for a caller still in its task. A live
  caller's result is delivered in the same main-thread step that found it alive, so the caller
  cannot be destroyed in between.
- **Screens every Android device has open nothing.** A start of a Settings action
  (`android.settings.*`), a document or photo picker action, or a component or package of
  Android's own apps opens nothing and reports success, as before build 114. No result comes back,
  as while the user is still on that screen: a `RESULT_CANCELED` at once would bring a resumed
  caller through `onPause` and `onResume`, and an app that asks again in `onResume` would ask
  without end. Any other start that nothing handles still throws.

The twelve apps again, on build 120:

| apps | r90 (build 119) | build 120 |
|---|---|---|
| aat, Clock, LuxAlarm, stims, WiFiAnalyzer, socks5, viewer | died on the start | draw |
| AnkiDroid | died on the result | draws |
| Obtainium, ObtainX | Mali abort | Mali abort, as before |
| Waze, Reddit | no frame at the screenshot | no frame at the screenshot; Waze draws with a 90 s wait |

Clock and LuxAlarm ask for full-screen notifications because `canUseFullScreenIntent` reads false:
the in-process notification service does not answer it. Android 14 answers true for an app that
declares `USE_FULL_SCREEN_INTENT` (or targets an earlier version). They draw on build 120 either
way; the answer is open.

The framework-contracts probe gained what r90 showed:
- `am:activity-result`: then an activity that starts one for a result and finishes at once, as a
  launcher trampoline does, gets no result, and the app goes on. On build 119 the probe died there
  with AnkiDroid's exception; on build 120 it passes.
- `am:start-unresolved`: a screen of Settings, VPN consent and the document picker must not throw.
  It passes on build 120. (On build 119 the probe did not reach it.)
- `intent:system-screen`, a new line: what handles Settings' app details screen and VPN consent on
  the device. Nothing does on the board, on build 120: a truthful absence.

Build 120's checks, under SELinux enforcing:
- **The probe suite:** as on build 119, except for the lines above.
- **The calibration flows:** 15 of 18 confirmed, no false alarms, as on build 119. `keepassdx-open`
  still fails, as it must with no picker on the board, but differently: on build 119 the refused
  start brought up KeePassDX's own "a file manager is required" dialog; on build 120 its button opens
  nothing. An app that catches the exception to explain itself loses that, as it did before
  build 114; one that does not catch it no longer dies. A picker the app can reach is the
  calibration record's open gap 2 (OH's picker, its result passed back by the host application).
- **Build 103's regression set:** 22 of 24 draw, as on build 119: Reddit stops where it does on
  most runs, and Toutiao as always.

## A finding on the way: which ability a window is created for

Chasing Waze turned up a coin toss. Westlake names the OH ability a window is created for after
the first activity in `ActivityThread.mActivities`, an ArrayMap in the order of its tokens'
identity hashes. While two activities are up, as when a splash screen starts the main activity, a
window goes to either one's ability. In r90, 47 apps created a window for another activity's
ability; 81 launched two activities or more. Waze's black screens did not follow it: a throwaway
build that names the window's own activity (build 121) still showed black in two of three
relaunches, and build 120 drew with the other activity's ability at 90 s. The naming is left as
it is, for a change with a corpus round of its own.

## Start-up

- **First frame:** 280 of the 346 apps that draw report a drawn first frame.
  - Median 1.78 s from process start (r89: 1.79 s). 189 drew within 2 s, 271 within 5 s.
  - Three took over 10 s: TikTok (28.2 s), Nextcloud Talk (11.3 s) and Instagram (11.2 s). Waze and
    Reddit, over 10 s in r89, did not draw before the screenshot.
- **Against r89, apps that drew in both:**
  - 267 apps with a first frame in both: median 1.78 s, then 1.77 s;
  - 319 apps that logged a resume in both: median 0.94 s, then 0.88 s.

## What stopped the 23 apps short of drawing

| app | stop | cause |
|---|---|---|
| aat, Clock, LuxAlarm, stims, WiFiAnalyzer | ActivityNotFoundException | a screen of Settings (above); draw on build 120 |
| socks5 | ActivityNotFoundException | VPN consent (above); draws on build 120 |
| viewer | ActivityNotFoundException | the document picker (above); draws on build 120 |
| AnkiDroid | IllegalArgumentException on the main thread | a result for a caller that had finished (above); draws on build 120 |
| Obtainium, ObtainX | Mali's backend thread aborts | after their first background job (above); open |
| Waze, Reddit | no frame at the screenshot | timing (above): Waze draws with a 90 s wait; Reddit's splash waits on its servers |
| plusplusbattery | process init: `NoShellException` | `os:shell`, as in r89 |
| cclauncher | idle, host screen | `wm:show-wallpaper`, as in r89 |
| spacebeam | drawing frames, black screen | its GLSurfaceView's own OH window shows nothing; open |
| Fossify Messages | finished itself | no SMS role on a board without telephony: a device's answer |
| opflashcontrol | slider out of range | a flashlight app on a board with no camera exposed to Android: a device's answer |
| Shortcut | finished itself | a launcher for Android's file manager: nothing handles its `BROWSE` intent |
| facebooknotifica | InflateException | its preference XML names a class its bundled androidx lacks; Android fails the same way |
| NYTimes, Flipboard | Google Play services | out of scope |
| insigno | Mali's backend thread aborts | at bind, as Flutter's Vulkan backend imports a native buffer; open |
| OsmAnd | an abort on a Qt pool thread | PROJ's uncaught `FactoryException`, as in r86 to r89; open |

## Scoring

r90's first blockers were scored against gap maps made with today's harness, against build 119:
- **Scorable:** 14 of 23.
  - **Named:** 9. aat, Clock, LuxAlarm, stims, WiFiAnalyzer and socks5 by `intent:system-screen`;
    viewer by `intent:pick-document`; plusplusbattery by `os:shell`; cclauncher by
    `wm:show-wallpaper`.
  - **Marked supplied:** 3. AnkiDroid by `am:activity-result`, measured conformant on build 119 by a
    probe whose caller never finished first. Waze and Reddit by `am:post-create`, rightly: their stop
    is the screenshot's timing, not a gap.
  - **A device's answer:** Fossify Messages.
  - **Not named:** Shortcut.
- **The 9 unscorable:**
  - app exceptions with no platform symbol: facebooknotifica, NYTimes, Flipboard and opflashcontrol;
  - crashes in code no row names: insigno, Obtainium and ObtainX in Mali, OsmAnd in libc++;
  - a stall no row names: spacebeam.

Before this round's harness changes, 6 of the 23 were scorable: the seven start stops and
AnkiDroid's were unscorable, as app exceptions with no platform symbol.

**What the per-build loop missed.** Build 114's change reached every app that starts another app's
screen: 358 of the corpus's 371 APKs name one of the four families, and 285 name a screen of
Android's own apps. Build 114 was checked with the probes, the calibration flows and build 103's
regression set. None of those apps died on such a start, and the maps had no row for the screens of
Android's own apps. A change to what every start does reaches every app, and ADR-0001 asks a full
round of such a change.

## Harness changes since the r89 record

The per-build loop's changes came with the records of builds 100 to 119 (`benchmark/conformance`,
`benchmark/calibration`): the conformance run and its queue, the calibration flows and blind batch
2, and rows with contract lines for activity results, the launch lifecycle, popup windows, focus
handoff, notifications, recreation, dialog placement, alarms, jobs, starts that leave the app and
toasts. This round's:

| change | what it reads | what it names in r90 |
|---|---|---|
| `intent:system-screen` | an app's code that names a Settings action (`android.settings.*`) or calls `VpnService.prepare`; framework-contracts' line of the same name measures what handles Settings' app details screen and VPN consent on the device | aat, Clock, LuxAlarm, stims, WiFiAnalyzer, socks5 |
| scoring starts | an ActivityNotFoundException is scored by what the app started: the `intent:*` row for a web link, a share, the document picker or a screen of Android's own apps | the above, and viewer by `intent:pick-document` |
| scoring transaction items | an exception from a client transaction item the provider scheduled is scored by the item's contract: an `ActivityResultItem` by `am:activity-result` | AnkiDroid (marked supplied) |
| `am:activity-result` | the probe line also starts an activity that starts one for a result and finishes at once | |
| `am:start-unresolved` | the probe line also starts a screen of Settings, VPN consent and the document picker, which must not throw | |
