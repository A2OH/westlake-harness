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

## Results

The twenty were launched on r88's provider, each with its own map's launch args.

- **Drawing:** 19 of 20. **The predictions:** 19 of 20 right; every app predicted to draw drew,
  except socks5.
- **Start-up:** 17 report a drawn first frame, median 1.75 s, the slowest Hammer at 2.9 s.
- **socks5**, the miss, died starting its first activity. Its `onCreate` calls
  `VpnService.prepare`, which fetches vpn_management's binder (`IVpnManager`) itself, through
  `VpnService`'s own `getService`, and calls it with no null check. With no such service in
  Westlake, that is a NullPointerException inside the framework. No `getSystemService` request
  names the service, so no row of its map did.

Files: `b21-lifecycle.json` (the twenty classified) and `b21-score.json` (their stops scored
against their maps, with the change below).

## What the harness learned

- **Services framework methods fetch themselves** (`implicit_service_census`):
  - The framework's sources are read for public methods that fetch a registered service's binder
    through `ServiceManager`, in their own body or through their class's helpers: 52 classes,
    387 methods.
  - A call the app makes to one of them is a service request of its own. Where Westlake
    provides no binder of that name and the method does not check it, the row lists the method
    (`framework_fetch_throws`) and the binder interface.
  - socks5's map now has `svc:vpn_management`, and its stop is named by it (the scorer names an
    exception on a null binder interface by the row listing the interface).
- **Not a blocking signal:** on r88's corpus, seven apps call `VpnService` with no vpn_management
  behind it, and only socks5, calling `prepare` in `onCreate`, was blocked at its first screen.
  Adaway, blockads, DuckDuckGo, Intra, Rethink and stable call it later or off the main thread
  (blockads's VPN thread threw the same NullPointerException, and it drew). The predictor leaves
  the row out of its rule, as it does the package manager's, and still predicts socks5 to draw.

## The fix

Westlake now answers vpn_management in process (f57467d), as on a device where the user has not
yet consented to this app's VPN: `prepareVpn` answers false, so `VpnService.prepare` hands the app
the consent Intent, and every other call answers its type's default. Tested on build 97:
- socks5 draws its main screen ("Disconnected", a Connect button);
- blockads no longer throws on its VPN thread (r88: the `IVpnManager` NullPointerException and
  50 uncaught-exception lines);
- Rethink, Intra, Adaway and stable draw, as do the controls.
