# Batch 22: twenty fresh F-Droid apps, predicted before launch (2026-10-07)

Twenty F-Droid apps the corpus had not run, chosen from a fresh copy of the F-Droid index by the
rule `corpus-all/build_candidates.py` applies (in the inputs tree): updated within the last year,
arm64 among their native ABIs when they have any, targeting SDK 30 or newer, at most 80 MB, taken
round-robin across F-Droid's categories with the most published versions first. Their gap maps
were made with today's harness against build 97 (r88's provider with vpn_management answered in
process), and their first screens predicted from the maps alone with
`scripts/predict_first_screen.py` before any of them was launched.

It predicts all twenty draw. The open rows below are the ones that could still matter (leaving
out the accessibility, autofill, text classification, captioning and input services nearly every
app lists); none of them is a signal the rule counts as blocking. No map has a framework method
that fetches a service Westlake does not provide (`framework_fetch_throws`).

| app | title | predicted | open rows | routed |
|---|---|---|---|---|
| aihub | AI Hub (AI Chat) | draws | none | none |
| run | Cube Run (Action Game) | draws | `svc:audio` (hollow), `svc:fingerprint` (null), `svc:grammatical_inflection` (null), `svc:jobscheduler` (hollow), `svc:sensor` (inert) | libgdx.so |
| luxalarm | Lux Alarm (Alarm Clock) | draws | `svc:audio` (hollow), `svc:sensor` (inert), `svc:vibrator` (inert), `svc:vibrator_manager` (unresolved) | none |
| soothingloop | Soothing Noise Player (Ambient Sound) | draws | `svc:audio` (hollow), `svc:fingerprint` (null), `svc:jobscheduler` (hollow), `svc:print` (unresolved), `svc:user` (strict) | none |
| activitymanager | Activity Manager (App Manager) | draws | `svc:audio` (hollow), `svc:user` (strict) | none |
| izzyondroid | IzzyOnDroid (unofficial) (App Store & Updater) | draws | `svc:audio` (hollow) | none |
| homerplayer2 | Homer Audio Player for Seniors (Audiobook) | draws | `svc:audio` (hollow), `svc:jobscheduler` (hollow), `svc:media_metrics` (null), `svc:phone` (inert), `svc:sensor` (inert) | none |
| plusplusbattery | Plus Plus Battery (Battery) | draws | `svc:jobscheduler` (hollow), `svc:user` (strict), `svc:vibrator` (inert) | none |
| gnubg | CBG -- Clavierhaus BackGammon (Board Game) | draws | `svc:fingerprint` (null), `svc:grammatical_inflection` (null), `svc:jobscheduler` (hollow), `svc:user` (strict), `load:shadowed-by-board` (missing) | libgio-2.0.so, libz.so |
| webstack | WebStack (Bookmark) | draws | none | none |
| browser | FOSS Browser (Browser) | draws | `svc:audio` (hollow), `svc:download` (inert), `svc:print` (unresolved) | none |
| unitto | Unitto — calculator and unit converter (Calculator) | draws | `svc:audio` (hollow), `svc:jobscheduler` (hollow), `svc:user` (strict), `svc:vibrator` (inert) | none |
| persiancalendar | Persian Calendar (Calendar & Agenda) | draws | `svc:audio` (hollow), `svc:jobscheduler` (hollow), `svc:keyguard` (inert), `svc:phone` (inert), `svc:sensor` (inert) | none |
| websocketcam | Websocket CAM (Camera) | draws | `svc:audio` (hollow), `svc:camera` (inert), `svc:grammatical_inflection` (null), `svc:jobscheduler` (hollow), `svc:print` (unresolved) | none |
| solitaire | MA Solitaire (Card Game) | draws | none | none |
| yaacc | YAACC (Cast) | draws | `svc:audio` (hollow), `svc:fingerprint` (null), `svc:jobscheduler` (hollow), `svc:media_metrics` (null), `svc:media_projection` (inert) | none |
| bouncy | Vector Pinball (Casual Game) | draws | `svc:audio` (hollow), `svc:sensor` (inert), `svc:vibrator` (inert) | libgdx-box2d.so |
| binclockwidget | BinClockWidget (Clock) | draws | `svc:audio` (hollow), `svc:grammatical_inflection` (null), `svc:jobscheduler` (hollow), `svc:profiling` (unresolved), `svc:user` (strict) | none |
| liseur | Liseur (Cloud Storage & File Sync) | draws | `svc:jobscheduler` (hollow), `svc:user` (strict) | none |
| gitling | Gitling (Code & Forge) | draws | `svc:audio` (hollow), `svc:fingerprint` (null), `svc:grammatical_inflection` (null), `svc:jobscheduler` (hollow), `svc:profiling` (unresolved) | libconscrypt_jni.so |

`predictions.json` is the predictor's output. The results are scored against it after launch.
