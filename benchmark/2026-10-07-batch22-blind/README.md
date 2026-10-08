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

## Results

The twenty were launched on build 97 with r88's bionic shim, each with its own map's launch args.

- **Drawing:** 17 of 20. **The predictions:** 17 of 20 right. The three misses each stopped on a
  platform difference no row modelled; each is a row now (below).
- **Start-up:** 14 report a drawn first frame, median 1.54 s, the slowest at 4.3 s.

| app | stop | cause |
|---|---|---|
| yaacc | its own service's listener null, in `onServiceConnected` | its `onStartCommand` threw first, on a null `NetworkInterface.getNetworkInterfaces()`. musl's `if_nametoindex` asks an ioctl that OH's policy refuses an app's domain (EACCES, measured in an app process: `getifaddrs` gives 54 entries, `if_nametoindex` fails for lo, wlan0 and eth0). libcore drops an interface whose index comes back 0, so the enumeration came back null. Westlake caught the service's exception, where Android's process would die, and the app went on without the listener |
| gitling | its account manager null, in its first activity's view model | its Application's preferences helper generates an RSA pair with the legacy `KeyPairGeneratorSpec`, which Android's AndroidKeyStore provider still converts and the in-process one refused. The Application swallowed the exception |
| plusplusbattery | `NoShellException: Unable to create a shell!` in its Application | libsu starts a shell. OH's policy refuses an app's domain `/system/bin/sh` (execute, read and open, checked on the board), and OH's toybox has no `sh` applet |

Files: `b22-lifecycle.json` (the twenty classified) and `b22-score.json` (their stops scored
against maps made with today's harness against build 97, with Westlake pinned to the provider they
ran on): 2 of 3 named, plusplusbattery by `os:shell` and yaacc by `abi:interface-index`. gitling's
stop is unscorable, as its refusal was swallowed and never logged.

## What the harness learned

| change | what it reads | what it names |
|---|---|---|
| `abi:interface-index` | network interface lookups: `NetworkInterface`'s, or a native import of `if_nametoindex`/`if_indextoname`. Supplied where the bionic shim answers the index from `getifaddrs` when the ioctl is refused | yaacc; 91 corpus apps make the Java calls, and the native libraries of 83 import the functions |
| `jca:legacy-keypair-spec` | a `KeyPairGeneratorSpec`, against whether the in-process AndroidKeyStore accepts it | gitling |
| `os:shell` | an app that runs a shell through libsu (the scanner records libraries by a marker class, `library_markers`) | plusplusbattery |
| service failures | exceptions an app's own service threw in `onCreate`, `onStartCommand` or `onBind`, which Westlake's in-process services catch and log. A stop after one is named by a row that lists the exception among its symptoms | yaacc's onStartCommand. In r87 and r88 they also show four apps that draw with a broken service: Felicity (`libaaudio.so` would not load), NewPipe and Retro Music (`NameNotFoundException` for the package `android`), and Fennec (its content process) |

The published r87 and r88 lifecycle records predate the service failures; read again, those four
apps gain them, and nothing else changes.

## The fixes

Westlake answers both platform differences on its side (westlake 1b02ac5 and b97354c):
- **the bionic shim:** if_nametoindex and if_indextoname fall back to `getifaddrs`' link entries
  when the lookup fails;
- **the software keystore:** converts a `KeyPairGeneratorSpec` as Android's provider does.

Tested on build 98 with the new shim:
- yaacc draws, and openhab's NullPointerException is gone;
- gitling gets past its keystore and stops at the next gap, an unregistered
  `sun.nio.fs.UnixNativeDispatcher.futimes`;
- briar, KDE Connect, LocalSend, FluffyChat and the controls draw.

plusplusbattery's shell is an OS boundary: a fix would mean a shell the runtime stages where an
app's domain may execute it.
