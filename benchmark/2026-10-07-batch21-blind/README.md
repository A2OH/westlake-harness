# Batch 21: twenty more F-Droid apps, predicted before launch (2026-10-07)

Twenty F-Droid apps the corpus had not run, taken in order from the earlier candidate list (the
first twenty whose APKs still verified against the index's sha256). Their gap maps were made with
today's harness against r88's provider, and their first screens predicted from the maps alone with
`scripts/predict_first_screen.py`, before any of them was launched. The rule predicts an app
blocked when its map has a missing native import, a hollow service whose null answer AOSP's own
manager unwraps for a method the app calls, a runtime lookup of an NDK library the runtime does
not supply, or an engine's first screen drawn into its own SurfaceView without a provider for it.

It predicts all twenty draw. The open rows below are the ones that could still matter (leaving
out the accessibility, autofill, text classification, captioning and input services nearly every
app lists); none of them is a signal the rule counts as blocking. Launch args: the libraries each map routes to the
Android namespace.

| app | title | predicted | open rows | routed |
|---|---|---|---|---|
| goodtime | Goodtime: Pomodoro Timer (Timer) | draws | `svc:audio` (hollow), `svc:camera` (inert), `svc:jobscheduler` (hollow), `svc:user` (strict), `svc:vibrator` (inert) | none |
| poetassistant | Poet Assistant (Translation & Dictionary) | draws | `svc:audio` (hollow), `svc:jobscheduler` (hollow), `svc:print` (unresolved) | none |
| minimalcurconv | Minimal Currency Converter (Unit Convertor) | draws | `svc:audio` (hollow) | none |
| socks5 | Socks5 Proxy (VPN & Proxy) | draws | `svc:audio` (hollow) | none |
| duetto | Duetto (Voice & Video Chat) | draws | `svc:audio` (hollow), `svc:camera` (inert), `svc:fingerprint` (null), `svc:grammatical_inflection` (null), `svc:jobscheduler` (hollow) | libc++_shared.so, libfbjni.so, libhermes.so, libhermestooling.so ... |
| soundtoggle | Sound Toggle (Volume) | draws | `svc:audio` (hollow), `svc:vibrator` (inert) | none |
| wallet | Bitcoin Wallet (Wallet) | draws | `svc:bluetooth` (unresolved), `svc:jobscheduler` (hollow), `svc:vibrator` (inert) | none |
| floatdeck | FloatDeck (Wallpaper) | draws | `svc:keyguard` (inert), `svc:sensor` (inert), `svc:vibrator` (inert) | none |
| geoweather | GeoWeather (Weather) | draws | `svc:grammatical_inflection` (null), `svc:jobscheduler` (hollow), `svc:profiling` (unresolved), `svc:user` (strict), `svc:vibrator` (inert) | libsqliteJni.so |
| forkyz | Forkyz (Word Game) | draws | `svc:audio` (hollow), `svc:jobscheduler` (hollow), `svc:sensor` (inert), `svc:user` (strict) | libsqliteJni.so |
| gymbott | Gym Bott (Workout) | draws | none | none |
| hammer | Hammer (Writing) | draws | `svc:audio` (hollow), `svc:jobscheduler` (hollow), `svc:sensor` (inert), `svc:textservices` (null), `svc:user` (strict) | none |
| aiyo | Aiyo (AI Chat) | draws | `svc:vibrator` (inert) | libmmkv.so |
| fafarunner | FaFa Runner (Action Game) | draws | `svc:audio` (hollow), `svc:profiling` (unresolved), `svc:sensor` (inert), `svc:textservices` (null), `window:surfaceview-opacity` (missing) | none |
| clock2 | Clock You (Alarm Clock) | draws | `svc:keyguard` (inert), `svc:sensor` (inert), `svc:user` (strict), `svc:vibrator` (inert) | none |
| ambio | Ambio: Focus Timer & Sounds (Ambient Sound) | draws | `svc:audio` (hollow), `svc:media_metrics` (null), `svc:phone` (inert), `svc:sensor` (inert), `svc:vibrator_manager` (unresolved) | none |
| inure | Inure App Manager (Trial) (App Manager) | draws | `svc:audio` (hollow), `svc:fingerprint` (null), `svc:grammatical_inflection` (null), `svc:jobscheduler` (hollow), `svc:media_session` (not-a-platform-service) | libinure_terminal_emulator.so, librenderscript-toolkit.so |
| repostore | RepoStore (App Store & Updater) | draws | `svc:audio` (hollow), `svc:download` (inert), `svc:fingerprint` (null), `svc:grammatical_inflection` (null), `svc:jobscheduler` (hollow) | none |
| audioanchor | AudioAnchor (Audiobook) | draws | `svc:audio` (hollow), `svc:fingerprint` (null), `svc:grammatical_inflection` (null), `svc:jobscheduler` (hollow), `svc:media_session` (not-a-platform-service) | none |
| batterymonitor | Battery Monitor (Battery) | draws | `svc:audio` (hollow) | none |

`predictions.json` is the predictor's output. The results are scored against it after launch.
