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

## What the calibration says about the gap map

Each miss is a contract no row describes, or a row that reads supplied while the flow fails;
each false alarm is a row that reads broken while the flow works. The corpus counts are apps
whose scans reference the API behind the contract.

| what the flow showed | the gap map said | apps reaching it | next |
|---|---|---|---|
| **Activity results are dropped.** mpv's file picker returns the chosen file with `setResult` and finishes; Westlake's `finishActivity` ignores the result, so `onActivityResult` never runs and nothing plays | nothing: no row for activity results | 346 call `startActivityForResult` | done in build 102: the row `am:activity-result`, a contract line, and the fix |
| **A started activity is paused and resumed as it starts.** mpv pauses its player in `onPause`; the extra pause and resume left the picked file at 0:00, silent | nothing: no row for a started activity's lifecycle | 280 declare more than one activity and start activities | done in build 103: the row `am:launch-lifecycle`, a contract line, and the fix |
| **No keyboard comes up.** Tapping Markor's editor focuses it, and no soft keyboard appears: there is no way to type | `svc:input_method` supplied | 306 use `EditText` | a contract line (a focused field gets an input connection and the OH keyboard), and the IME bridge |
| **A timer ends silently.** Fossify Clock counts down to 00:00 and posts its notification; no sound and no alert, as `getRingtonePlayer` answers null and notifications reach no OH service | `svc:alarm`, `svc:notification` supplied | 283 post notifications; 20 play ringtones | contract lines for notification delivery and ringtone playback |
| **Popup menus are not drawn.** The overflow menu's window exists and takes taps (a blind tap opened the FAQ), but nothing shows | nothing: no row for popup windows | 311 show popups (`PopupWindow`, menus, dropdowns) | done in build 105: the row `wm:popup-window` and the fix; only the screen shows it, so the flow is its measurement |
| **The media store is empty.** Just Player lists videos from MediaStore and finds none, with the video in `Movies/`; the flow stops before decoding, so the `MediaCodec` prediction was right for another reason | `java:Media store` unmeasured | 125 | a contract line (a file in shared storage is indexed) |
| **WebView renders.** Markor's preview draws the note in a WebView and the app lives | `wv:renderer-process` missing: the first WebView kills the app | 143 | done: the row waits for the webview-boundaries probe, whose multiprocess line is its result (WebView in process on every build since 100) |
| **Ordinary dialogs are placed and dimmed.** Fossify Clock's timer dialog is centred and the screen behind it dimmed | `wm:window-placement` broken, `wm:dim-behind` missing | 318 | done in build 106: the probe's failure was where the app was told its dialog sat (the top left), not where it was drawn; each window's configuration now has the display's bounds and the line passes. The dim was drawn already: the prediction read `wm:dim-behind` from maps older than the dim layer |



## Running it

    python3 probes/run_flows.py --manifest <launcher repo> --workspace <source workspace> \
        --westlake-source <westlake checkout> --framework-report <build>/device-report.json \
        --hdc <hdc> --serial <device> --app-input-root <dir holding prep-<app>> \
        --maps <map root> [--maps <map root>] --work <scratch dir> --results <results.json> \
        --launch-args "<the provider flags the corpus launches with>"

`probes/audio-capture`'s `oh_record` must be on the board (`--recorder`). The fixed tap positions
belong to the pinned APK versions on the 1200x1920 board: a new pin, or another screen, needs them
found again (a screenshot after each step shows where).
