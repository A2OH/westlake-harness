# Calibration flows

A few pinned apps driven through what a user does, each flow scored against what the gap map
predicted for it: the end-to-end plan's calibration layer
([plan](../../analysis/E2E-FUNCTIONAL-HARNESS-PLAN.md), layers 5 and 6). Since 2026-10-09 each build
gets the conformance probes ([ADR-0001](../../analysis/adr/0001-measured-provider-conformance.md)), the apps
that reach the contract it changed, and these flows; full corpus rounds run only when a change
reaches every app (the runtime, the loader or shim, the window or input bridge) or a milestone is
recorded.

`probes/flows.json` holds the flows: the steps (taps at fixed positions, which hold because the
APKs are pinned), the evidence (screenshots, a recording of the board's output, the app's logs),
the checks that decide the outcome, and the prediction with the rows it rests on.
`probes/run_flows.py` runs them and scores each prediction:

- **confirmed:** the flow came out as predicted;
- **false alarm:** predicted to fail, it worked;
- **miss:** predicted to work, it failed.

## Build 101 (Westlake main c314489, 2026-10-09)

Eight flows in five apps on the OH 6.1 board, launched as the corpus is: build 101 with the AAudio
shim and its runtime-library override. `results-build101.json` holds each flow's checks.

| flow | what the user does | predicted | observed | verdict | what decided it |
|---|---|---|---|---|---|
| `noice-play` | play a sound | works | works | confirmed | 562,798 non-zero samples of sound in 12 s |
| `mpv-play-file` | play a video picked in the app's file picker | works | fails | **miss** | silence: the picked file never reaches the player |
| `justplayer-choose` | choose a video and play it | fails | fails | confirmed | silence, and "No video files found" |
| `markor-type` | type into a note | works | fails | **miss** | no keyboard: the lower screen does not change when the editor is tapped |
| `markor-preview` | preview a note, in a WebView | fails | works | false alarm | the app lives, and the heading renders |
| `fclock-timer` | a 5-minute timer rings when it ends | works | fails | **miss** | silence at expiry |
| `fclock-menu` | open the overflow menu | works | fails | **miss** | nothing drawn under the menu button |
| `fclock-dialog` | edit a timer in its dialog | fails | works | false alarm | the dialog in the middle, the screen behind it dimmed |

Two predictions confirmed, two false alarms, four misses. Of the three flows predicted to fail,
one did (precision 0.33); of the five that failed, one was predicted (recall 0.2). The gap map's
startup scoring has looked like this before its rules caught up (r77: 9 of 57 stops named), and
the misses below are what it lacks.

On build 100, before the audio service fix, `noice-play` fails: the board stays silent. That
build's audio service answered every call with its type default, so a focus request read as
refused (on build 101 the log shows Noice asking for focus before it plays). On build 101 it
plays: the fix taken from the top of the conformance queue is what a user hears.

## Build 102: the first fix from the calibration

Build 102 delivers activity results between the app's own activities (Westlake: the start records
its caller, the launch binds it to the new activity, and finishActivity sends the result in an
ActivityResultItem). The framework-contracts probe's new `am:activity-result` line passes
(onActivityResult gets `RESULT_OK` and the answer), and the gap map's `am:activity-result` row reads
the provider's source. In `mpv-play-file` the picked file now reaches mpv: its player opens and
shows the clip's first frame. The flow still fails, one step further: playback stays at 0:00 and
silent. mpv's audio renderer is created and its write thread starts, but its clock never moves.
That is the flow's next blocker.

## Build 103: a started activity resumed once

The frozen clock was not audio. mpv's own log (`msg-level=all=v` in its config) shows the app
setting `pause=true` 0.48 s after it loads the file, before it has chosen the audio track; playback
then stops at 0:00, "audio=ready, video=playing (paused)". mpv pauses its player in `onPause` and
does not resume it in `onResume`, and every activity Westlake started in process got an `onPause`
and an `onResume` just after it started. The launch transaction resumed it, then the native start
resumed it again in a transaction carrying an empty `ActivityResultItem`, and `ActivityThread`
pauses a resumed activity before it delivers results.

Build 103 (Westlake #34) resumes a started activity once. The framework-contracts probe's new
`am:launch-lifecycle` line reads `onCreate onStart onResume onPause onResume` on build 102 and
`onCreate onStart onResume` on build 103. The gap map's `am:launch-lifecycle` row reads the
provider's source; it reaches 280 of the 369 corpus apps (those that declare more than one activity
and start activities). Build 102's twenty regression apps draw on build 103, and so do noice and
linphone (that run was under SELinux permissive); reddit and toutiao stop on build 103 where they
also stop on build 102, under either mode.

On build 103 `mpv-play-file` works: between the flow's two screenshots the clip's own clock moves
from 00:00:01.000 to 00:00:04.133, and the recording holds 234,285 non-zero samples of its 1 kHz
tone. The flow now makes the app's `external/Android` folder before it opens the picker
(a `mkdir` step): mpv makes the folder on its first start at a time of its own, and without it the
clip is listed second rather than third.

The eight flows on build 103 (`results-build103.json`, Westlake main 79ef37d, SELinux enforcing):
three confirmed, two false alarms, three misses (precision 0.33, recall 0.25); `mpv-play-file` moved
from miss to confirmed.

| flow | predicted | observed | verdict | what decided it |
|---|---|---|---|---|
| `noice-play` | works | works | confirmed | 554,012 non-zero samples of sound in 12 s |
| `mpv-play-file` | works | works | confirmed | the picture moves; 234,285 non-zero samples of the clip's tone |
| `justplayer-choose` | fails | fails | confirmed | silence, and "No video files found" |
| `markor-type` | works | fails | **miss** | no keyboard: the lower screen does not change when the editor is tapped |
| `markor-preview` | fails | works | false alarm | the app lives, and the heading renders |
| `fclock-timer` | works | fails | **miss** | silence at expiry |
| `fclock-menu` | works | fails | **miss** | nothing drawn under the menu button |
| `fclock-dialog` | fails | works | false alarm | the dialog in the middle, the screen behind it dimmed |

Activity results changed what Markor does after its intro, as on Android: the intro is started for
a result, so when it finishes, Markor's main activity hears it and opens its changelog. Both Markor
flows now close it first; without that step they tap into the dialog.

## Build 105: popup windows shown

Fossify Clock's overflow menu took taps and showed nothing. Westlake asked OH for a popup's window
(an Android sub-window, here type 1002) as an OH main window, which the board refuses (1005), so the
window drew into a surface node with no session, which nothing shows. Build 105 (Westlake #35) asks
for a sub-window's session as an application window, as for a dialog, and its OH window spans the
display, as a dialog's does; the popup's content is still placed at its own frame. Build 104 had the
session but the popup's own width: its OH window was 392 pixels wide at x 0, and the menu's content,
placed at x 788, fell outside it.

The gap map's `wm:popup-window` row reads the provider's source; it reaches 311 of the 369 corpus
apps (those that show a `PopupWindow`, a menu or a dropdown). Only the screen shows a popup, so the
flow `fclock-menu` is the row's measurement: on build 105 the menu draws under its button, and
tapping About closes it and opens the About screen.

The eight flows on build 105 (`results-build105.json`, SELinux enforcing): four confirmed, two false
alarms, two misses (precision 0.33, recall 0.33); `fclock-menu` moved from miss to confirmed. Every
line of the probe suite has the outcome of its last run. Build 103's
regression set draws as on build 103: 22 of 24, with reddit and toutiao stopping where they did.

## Build 106: the two false alarms

Each false alarm was a row reading broken where the flow works, and each was checked against what
the row actually measures.

- **`wv:renderer-process` (markor-preview).** The row inferred from AOSP's `WebViewDelegate` that
  WebView must run multiprocess, but that depends on update-service flags whose value belongs to
  the provider's framework build, which the source does not show. This build has them off, and
  WebView runs in process. The row is now `unverified` unless the renderer service is hosted, and
  webview-boundaries' multiprocess line is its result on each build (`rows` in `probes/suite.json`
  maps an older probe's line onto a row). It has passed in every run, builds 100, 105 and 106.
- **`wm:window-placement` (fclock-dialog).** On screen, dialogs were centred and dimmed, the held-back
  dialog included. The probe's line failed on where the app was told its dialog sat
  (`getLocationOnScreen`: the top left). Westlake gave each window a configuration with the
  window's own size as its bounds, and ViewRootImpl laid the window out inside it. Build 106
  (Westlake #36) gives every window the display's bounds, as WMS does, and the line passes for the
  first time: the dialog at 280,634, and the runner's tap at the reported button centre clicks it.
  `wm:dim-behind` was drawn already; the prediction read it from maps older than the dim layer.

The eight flows on build 106 (`results-build106.json`, SELinux enforcing): six confirmed, no false
alarms, two misses (precision 1.0, recall 0.33). The probe suite passes 27 of 45 lines;
the changes are the placement line and the new WebView row, and every other line has the outcome
of its last run. Build 103's regression set draws as on build 105: 22 of 24. The misses left are
the two contracts no row describes: the soft keyboard (`markor-type`) and the timer's sound
(`fclock-timer`).

## Build 107: the keyboard

The keyboard bridge was there and worked. The framework-contracts probe's new `svc:input_method` line
starts an activity whose focused EditText asks for the keyboard: on build 106 the input method manager
serves it, the board's keyboard comes up, and the window's insets report 826 px of it. Markor's editor
sat under its changelog, which had just closed. OH sends the app's sessions no focus when a window
closes (they are created not focusable), so the window under the dialog never had window focus again,
and Android's input method manager, which serves only the focused window's editor, ignored the editor's
`showSoftInput` ("not served").

Build 107 (Westlake #37) hands window focus to the topmost remaining window when a focused one is
removed, as WMS does. The probe's `wm:focus-handoff` line (a dialog over the editor takes focus;
once closed, the activity's window gets it back) fails on build 106 and passes on build 107. The gap
map's `wm:focus-handoff` row reaches 296 of the 369 corpus apps (text fields, and dialogs or popups).

`markor-type` now types: the flow taps three keys on the board's keyboard through OH's own input (a
`touch` step: the keyboard is an OH window the app's tap channel cannot reach), and "qwe" shows in the
note. The eight flows on build 107 (`results-build107.json`, SELinux enforcing): seven confirmed, no
false alarms, one miss (precision 1.0, recall 0.5). Build 103's regression set draws as on build
106: 22 of 24. The miss left is the timer's sound (`fclock-timer`), a contract no row describes yet.

One line failed in this run for a reason older than this build: `wm:window-placement`, because the
second dialog, a stock AlertDialog with a long message, measured 1282 px wide on the 1200 px screen.
Its first layout comes out that wide and a later one fits it (30 to 1170), and the probe measures it
1.2 s after it shows; it caught the wide layout on build 105 as well. The first dialog stays centred.

## Build 108: the timer rings

Fossify Clock rings an expired timer as Android expects: it posts a notification on a channel whose
sound is the alarm (`content://settings/system/alarm_alert`, alarm usage, insistent), and the
notification service plays it until the notification is cancelled. Westlake's in-process notification
service dropped posts and channels, the board has no ringtone files, and `POST_NOTIFICATIONS` was
mapped to an OH system permission no application holds, so it read as denied for every app.

Build 108 (Westlake #38, with a rebuilt libwl_missing_natives) keeps an app's channels and posts and
plays a post's sound as NotificationManagerService does: the channel's sound, importance DEFAULT and
above, looping when insistent, stopped by cancel. It writes default alarm, notification and ringtone
sounds and opens them for the settings URIs that stand for them. `POST_NOTIFICATIONS` and
`areNotificationsEnabled` answer from OH's per-application notification switch, the host's. That
switch is the user's: with it off the post is dropped, as Android drops it, and the timer stays
silent; the board's host application now has notifications allowed in OH Settings (see Running it).

The framework-contracts probe's new `svc:notification` line (a channel kept, the two notification
answers agreeing, a post listed and cancelled) passes on build 108. At the timer's expiry the board
plays the alarm, four 880 Hz beeps and a pause, looping (367,216 non-zero samples in the flow's
25 s), and resetting the timer stops it.

The eight flows on build 108 (`results-build108.json`, SELinux enforcing): all eight confirmed, no
false alarms, no misses (precision 1.0, recall 1.0). Build 103's regression set draws as on build
107: 22 of 24.

## Batch 2: nine flows predicted blind (build 108)

All nine new flows fail on build 108. The gap map predicted four of the failures, and all four
failed (precision 1.0), but it predicted only four of the nine (recall 0.44), and its rows named the
cause once, for the camera. The other failures are contracts no row describes yet.

With all eight earlier flows confirmed, they no longer tested the map. Batch 2 covers the plan's core
functions not yet calibrated, in seven apps. Before the board was touched, `batch2-plan.json` fixed
each flow's function, what counts as working, and the contracts it needs (row ids or prefixes).
`scripts/predict_flows.py` then read the predictions from maps rebuilt against build 108 with this
harness and the build's probe results. A flow is predicted to fail when a matching row is a hard
gap, the startup backtest's rule (`batch2-predictions.json`, committed before any run). The steps
were found on the board afterwards (`results-batch2.json`, SELinux enforcing).

| flow | what the user does | predicted, from | observed | verdict |
|---|---|---|---|---|
| `fnotes-newline` | type two lines in Fossify Notes | fails: `jni:android.view.KeyCharacterMap` broken | the keyboard's Enter (确认) closes the keyboard; no new line | confirmed, another cause |
| `fnotes-copy-paste` | copy a word and paste it | works: clipboard, popups, keyboard supplied | nothing is selected: in the corpus launch's tap touch mode a held finger arrives as one tap when it lifts, so no long press reaches the app | **miss** |
| `fnotes-link` | open a web link from About | works: no row | nothing opens: the board has no browser, and the start reports success | **miss** |
| `markor-share` | share a note | fails: `pm:call:queryIntentActivityOptions` a stub | no share sheet: the chooser's start goes nowhere | confirmed, another cause |
| `termux-command` | run a command | fails: `jni:android.view.KeyCharacterMap` broken | "Unable to install bootstrap": Termux's programs cannot run | confirmed, another cause |
| `chrono-timer` | a 30-second timer rings | works: alarm, notification, audio supplied | the app dies on Start: a null status-bar service | **miss** |
| `keepassdx-open` | open a database through the system picker | works: no row | no picker shows; the start reports success | **miss** |
| `opencamera-photo` | take a photo | fails: `svc:camera` inert, camera2 natives missing | "Failed to open camera" | confirmed |
| `antennapod-theme` | switch to the dark theme | works: `svc:uimode` supplied | Dark is selected and the screens stay light: the activity is not recreated | **miss** |

What decided the failures:

- **The keyboard's Enter key.** The bridge receives it as "hide the keyboard": the IME session detaches
  and no newline or editor action reaches the app.
- **Long press.** Streamed through the tap channel (`d`, a hold, `u`), the same press selects the word,
  and the toolbar's Copy and Paste work. The flow's `press` step replays a held finger as the
  touch forwarder does for the launch's touch mode, so it measures what a user gets.
- **Starts that go nowhere.** The GitHub link (VIEW), Markor's share (a chooser) and KeePassDX's Open
  (OPEN_DOCUMENT) all report success, and nothing opens. OH has a file picker (`com.ohos.filepicker`),
  but no browser on this board. The only caller of the stub the share prediction read is androidx's
  `MenuBuilder.addIntentOptions`, not the share.
- **Android executables.** Termux's packages are Android programs whose interpreter,
  `/system/bin/linker64`, OH does not have. In one diagnostic run under permissive SELinux the
  packages extract and the second stage exits 127.
- **The status bar.** Chrono's Start calls `TileService.requestListeningState`, which reaches
  `StatusBarManager` with no status-bar service: a NullPointerException on the main thread.
- **Recreation.** AntennaPod recreates its activities to apply a theme, and on Westlake they are not
  recreated.

The batch adds a `press` step to `run_flows.py`, and a `max_fraction` bound for a region that must
not be dark (a camera preview).

## Build 109: activities recreated

AntennaPod's dark theme now applies: build 109 relaunches an activity that calls recreate(). Of
the seventeen flows, thirteen are confirmed, with no false alarms and four misses (precision 1.0,
recall 0.56; `results-build109.json`, SELinux enforcing). Build 103's regression set draws 23 of 24;
Reddit drew this run, as it does on some runs.

ActivityThread does not relaunch an activity whose token is a local Binder, which it takes for one
the system does not know, and Westlake's activity tokens were Binders. Westlake #39 gives in-process
activities a token of their own and adds the completed-listener native that a relaunched window's
first draw needs. It also answers the status-bar service in process. The framework-contracts
probe's new `am:recreate` line fails on build 108 (no new instance) and passes on build 109.

- `antennapod-theme` works: 95% of the settings screen is dark once Dark is chosen.
- `chrono-timer` still fails, for two newer reasons. The app no longer dies when its timer starts,
  and the timer counts down, but at its end the app counts overtime in silence. Its ringing starts
  from an alarm, and Westlake's alarm service accepts every alarm and delivers none. In the flow,
  the app's first-run notice could not be dismissed: it is drawn centred, reports its position as
  the top left of the screen, and a tap on its OK lands outside it. A tap where OK would be at the
  top left dismisses it, on build 108 as well. Before build 109 the flow got past the notice only
  when its tap came before the notice showed; the app now recreates its activity as it starts,
  which shows the notice later.

The map gains three rules from these misses: the row `am:recreate`, from the token type the
provider hands out (267 corpus apps call `Activity.recreate`); static framework helpers in the
implicit-service census, so `TileService.requestListeningState` reaches `svc:statusbar` (12 apps);
and `svc:alarm` reading hollow when every alarm call answers the type default. Rebuilt against
build 108 with these rules, the batch-2 plan, unchanged, predicts the failures of
`antennapod-theme` and `chrono-timer`: 6 of the 9 failures, in sample.

## Build 110: dialogs placed where they are drawn

Chrono's notice can be dismissed: a tap on its OK reaches it. The flow now sets its timer, runs it
and reaches the end, where the app counts overtime in silence. The alarm that starts the ringing
is never delivered, which the map's `svc:alarm` row now reads as hollow. The seventeen flows score
as on build 109: thirteen confirmed, no false alarms, four misses (precision 1.0, recall 0.56;
`results-build110.json`, SELinux enforcing). Build 103's regression set draws 22 of 24:
Toutiao stops as always, and Reddit is back to the stop it shows on most runs.

The notice was drawn centred while its window's position read as the top left, so a tap at the
button's place on screen reached the window outside its bounds. Westlake gave every window an
attached frame of its own size, and ViewRootImpl lays a window that is not laid out in screen, a
dialog, inside its attached frame. When it laid the dialog out itself, in a relayout that moved
nothing but its position (Android 15 does those locally), the centred dialog came out at the top
left of its own frame, while the OH layer stayed where Westlake's placement had put it. Westlake #40
gives an attached frame only to child windows, the parent's as WMS does, and none to others. An
empty rect is not none to ViewRootImpl but a frame of no size, which put every dialog at the top
left in the first attempt; WMS's invalid `(0,0,-1,-1)` is.

The dialog-before-window probe's `wm:window-placement` passed on build 109, because its dialogs
had not laid themselves out. The line now relays the dialog out with its own attributes and checks
the alert is centred: it fails on build 109 (the dialog moves to 40,0) and passes on build 110. 333
corpus apps show dialogs.

## Build 112: alarms delivered

Chrono's timer rings at its end. The alarm the app sets for the expiry fires after 30 s, its
PendingIntent reaches the app's `TimerAlertReceiver`, the receiver starts the app's timer service,
and the board records the ring. Of the seventeen flows, fourteen are confirmed, with no false
alarms and three misses (precision 1.0, recall 0.62; `results-build112.json`, SELinux enforcing).
Build 103's regression set draws 22 of 24, as on build 110: Reddit stops where it does on most
runs, and Toutiao as always.

Westlake's alarm service accepted every alarm and delivered none, and a PendingIntent that was
sent went nowhere. Westlake #41 delivers alarms in process while the app runs: each fires at its
trigger time, a PendingIntent alarm is sent, and a listener alarm calls its listener. A sent
PendingIntent now reaches the app's own receivers, services and activities. The receivers an app
declares in its manifest run in process for a broadcast sent to them by name or within the app's
package; Chrono's alarm reaches its receiver that way. An alarm still lasts only as long as the
app's process: nothing restarts the app for one, and nothing wakes the device.

The framework-contracts probe's new `svc:alarm` line sets a listener alarm and a PendingIntent
alarm to a receiver in the probe's manifest, both 1.5 s ahead. It fails on build 110 (neither
arrives in 8 s) and passes on build 112. `pm:call:queryBroadcastReceivers` passes as well: the
package manager now resolves the app's own receivers. 242 corpus apps schedule alarms.

## What the calibration says about the gap map

Each miss is a contract no row describes, or a row that reads supplied while the flow fails;
each false alarm is a row that reads broken while the flow works. The corpus counts are apps
whose scans reference the API behind the contract.

| what the flow showed | the gap map said | apps reaching it | next |
|---|---|---|---|
| **Activity results are dropped.** mpv's file picker returns the chosen file with `setResult` and finishes; Westlake's `finishActivity` ignores the result, so `onActivityResult` never runs and nothing plays | nothing: no row for activity results | 346 call `startActivityForResult` | done in build 102: the row `am:activity-result`, a contract line, and the fix |
| **A started activity is paused and resumed as it starts.** mpv pauses its player in `onPause`; the extra pause and resume left the picked file at 0:00, silent | nothing: no row for a started activity's lifecycle | 280 declare more than one activity and start activities | done in build 103: the row `am:launch-lifecycle`, a contract line, and the fix |
| **No keyboard comes up.** Tapping Markor's editor focuses it, and no soft keyboard appears: there is no way to type | `svc:input_method` supplied | 306 use `EditText` | done in build 107: the keyboard bridge worked in a window that kept focus (`svc:input_method`, now a contract line); Markor's editor sat under its closed changelog, whose window never handed focus back. The row `wm:focus-handoff`, a contract line, and the fix |
| **A timer ends silently.** Fossify Clock counts down to 00:00 and posts its notification; no sound and no alert, as `getRingtonePlayer` answers null and notifications reach no OH service | `svc:alarm`, `svc:notification` supplied | 283 post notifications; 20 play ringtones | done in build 108: the notification service keeps channels and posts and plays a post's sound; the defaults resolve; `POST_NOTIFICATIONS` is OH's per-app switch; a contract line (`svc:notification`) |
| **Popup menus are not drawn.** The overflow menu's window exists and takes taps (a blind tap opened the FAQ), but nothing shows | nothing: no row for popup windows | 311 show popups (`PopupWindow`, menus, dropdowns) | done in build 105: the row `wm:popup-window` and the fix; only the screen shows it, so the flow is its measurement |
| **The media store is empty.** Just Player lists videos from MediaStore and finds none, with the video in `Movies/`; the flow stops before decoding, so the `MediaCodec` prediction was right for another reason | `java:Media store` unmeasured | 125 | a contract line (a file in shared storage is indexed) |
| **WebView renders.** Markor's preview draws the note in a WebView and the app lives | `wv:renderer-process` missing: the first WebView kills the app | 143 | done: the row waits for the webview-boundaries probe, whose multiprocess line is its result (WebView in process on every build since 100) |
| **Ordinary dialogs are placed and dimmed.** Fossify Clock's timer dialog is centred and the screen behind it dimmed | `wm:window-placement` broken, `wm:dim-behind` missing | 318 | done in build 106: the probe's failure was where the app was told its dialog sat (the top left), not where it was drawn; each window's configuration now has the display's bounds and the line passes. The dim was drawn already: the prediction read `wm:dim-behind` from maps older than the dim layer |
| **Enter closes the keyboard.** Fossify Notes gets no new line: the board keyboard's Enter reaches the bridge as "hide" | `jni:android.view.KeyCharacterMap` broken (another cause) | 154 handle the keyboard's action key; 306 use `EditText` | a contract line (the action key reaches the editor as a newline or an editor action) and the bridge's Enter |
| **No long press.** Text cannot be selected, so nothing is copied | `svc:clipboard` supplied; no row for how touch reaches the app | 280 set long-press listeners | stream a held finger in tap mode (the touch forwarder); a row for the launch's touch mode |
| **Starts go nowhere.** A web link, a share and the system picker report success and open nothing | no rows for other apps' activities (the plan's layer 1 is not built) | 274 call `Intent.createChooser`; 217 use `DocumentsContract` | answer `ActivityNotFoundException` when nothing handles a start (plan gap 1); the picker and share mapped to OH's (gap 2) |
| **Android executables cannot run.** Termux's bootstrap fails | nothing: no row for an app's own programs | 146 start processes | a row for executables that need Android's linker |
| **No status-bar service.** Chrono dies when its timer starts | nothing: no status-bar row | 17 use Quick Settings tiles or `StatusBarManager` | done in build 109: the service answered in process, and `svc:statusbar` from the census's static helpers (12 call `TileService.requestListeningState`) |
| **Activities are not recreated.** AntennaPod's theme does not apply | nothing: no row for recreation | 267 call `Activity.recreate` | done in build 109: the row `am:recreate`, a contract line, and the relaunch |
| **Alarms are never delivered.** Chrono's timer reaches its end and counts overtime in silence | `svc:alarm` supplied | 242 schedule alarms | done in build 112: alarms delivered in process while the app runs, PendingIntents sent to the app's own components, its manifest receivers run; a contract line (`svc:alarm`). Jobs, the rest of plan gap 5, are not run (`svc:jobscheduler` fails) |
| **A dialog's touch area is not where it is drawn.** Chrono's notice is centred, reports the top left as its position, and a tap on its OK misses | `wm:window-placement` passes (the probe's dialogs had not laid themselves out) | 333 show dialogs | done in build 110: the line relays its dialog out and checks the alert is centred, and the fix (an attached frame only for child windows) |



## Running it

    python3 probes/run_flows.py --manifest <launcher repo> --workspace <source workspace> \
        --westlake-source <westlake checkout> --framework-report <build>/device-report.json \
        --hdc <hdc> --serial <device> --app-input-root <dir holding prep-<app>> \
        --maps <map root> [--maps <map root>] --work <scratch dir> --results <results.json> \
        --launch-args "<the provider flags the corpus launches with>"

`probes/audio-capture`'s `oh_record` must be on the board (`--recorder`). The fixed tap positions
belong to the pinned APK versions on the 1200x1920 board: a new pin, or another screen, needs them
found again (a screenshot after each step shows where). The board keyboard keeps its mode (pinyin or
English) and layout between launches, so flows that type tap keys that show text in any state.
OH's own input (`touch`) reaches only OH windows such as the keyboard; the app's windows get taps
through the tap channel. A `press` follows the launch's touch mode, as a finger does. The board's own keyboard takes `touch`
steps (OH input) at the positions of its default input method. Notifications must be allowed for
the host application in OH Settings (Notifications and status bar, Westlake IME host), as a
user allows an app's notifications: until then `POST_NOTIFICATIONS` reads denied and a post is
dropped, so `fclock-timer` stays silent.
