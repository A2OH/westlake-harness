# Blind batch: top commercial apps (pre-registered 2026-09-29)

30 widely used commercial apps, downloaded from APKPure with apkeep 0.18.0 (arm64-v8a). Every base
and split APK verifies with apksigner and carries one signing certificate (`apps.json`). Pinterest
(APKPure offers only its ChromeOS web-app stub) and Yahoo (download fails) were replaced by The
Guardian and Microsoft Start before anything was launched.

| group | apps |
|---|---|
| social (12) | Instagram, Facebook, Messenger, WhatsApp, Threads, Snapchat, TikTok, X, Reddit, Telegram, Discord, LinkedIn |
| news (7) | BBC News, CNN, NYTimes, Flipboard, SmartNews, The Guardian, Microsoft Start |
| transit / utility (11) | Moovit, Citymapper, Transit, Uber, Waze, Zoom, Shazam, Duolingo, Spotify, Amazon Shopping, CapCut |

These differ from the F-Droid corpus in what they carry: Google Play Services dependencies, ad,
analytics, crash-reporting and push SDKs, anti-tamper and integrity checks, split APKs, React
Native and custom engines. None has been launched on Westlake before this file was committed.

## Excluded before launch: no arm64 build obtainable

For 13 apps APKPure serves only armeabi-v7a (32-bit) native libraries, even when arm64-v8a is
requested and on retry; Westlake runs arm64 only, so these cannot launch as downloaded: Discord,
Reddit, BBC News, CNN, NYTimes, Flipboard, Citymapper, Transit, Uber, Waze, Zoom, Shazam, Amazon
Shopping. Their predictions and open rows stay in the files; they are not launched or scored
unless an arm64 build is obtained (e.g. from Google Play). 17 apps are launched.

Update, still before any of them launched: 12 of the 13 were then obtained from Google Play with an
anonymous session from Aurora Store's token dispenser (`playfetch.py`: details, purchase, delivery,
as Aurora does), arm64 device profile. Every base and split verifies, and each carries the same
developer certificate as the APKPure copy. Play's versions differ slightly from APKPure's, so these
12 were re-mapped and re-predicted (`predictions-play.json`, `open-rows-play.json`) and committed
before launch; `apps.json` records the Play versions. Amazon Shopping: Play returned no version for
the device profile, so it stays excluded. 29 apps in all.

## Frozen provider

framework-signin-device70 (framework 68's Java build signin67; native runtime native-runtime-opengl13
= the media, AudioTrack/AudioSystem and ActivityThread/SQLiteGlobal natives, westlake d340dea;
runtime data runtime-data-tz2) and shim bionic-shim-nw11 (OpenSL ES adapter, westlake c7d2992).
Maps were made against that runtime and runtime-index-57nc.

## Predictions (made before launch)

- `predictions.json`: predict_first_screen.py (rule v3) on these maps -- 24 draw, 6 blocked:
  Duolingo, Threads, CapCut, Snapchat, TikTok (NDK sensors / NDK package rows), Telegram
  (runtime lookup of libnativehelper).
- `open-rows.json`: every open row per app outside the background families -- the gaps the
  harness names in advance (median 31 per app).

## Judging rules (fixed now)

1. Draws: the app's own UI is on screen at the capture -- a first screen, login, onboarding,
   consent or permission screen of the app counts. Not counted: the host screen (the app left or
   died), a blank or black window, a splash that never advances, the app's own crash or
   "unsupported device" screen, a region left empty where the app's content should be.
2. Blocked apps get a first blocker, from the child log and fault log (and hilog when those are
   silent), and a verdict: named (a pre-registered open row names it), or blind spot.
3. The harness is scored on both: the predictor's precision/recall on draws, and the share of
   first blockers that a pre-registered row named. Each blind spot is a candidate new check.

## Result (launched 2026-09-29, judged by the rules above)

**2 of 29 draw**: LinkedIn (its privacy-agreement dialog) and Duolingo (its welcome screen). The
F-Droid corpus draws about 80% on the same provider; these apps fail far earlier and in more ways.
Per-app outcome, first blocker and harness verdict: `outcomes.json`.

**Predictor** (draw vs blocked, 29 apps): predicted blocked 7 -- Threads, CapCut, Snapchat,
TikTok, Telegram, Transit correctly, Duolingo wrongly. Precision 0.86, recall 0.22 (6 of 27).

**Blocker level** -- did a pre-registered row name the first blocker?

| verdict | apps | n |
|---|---|---|
| named | Snapchat (`__assert`), X and Uber (MediaDrm), Telegram (AudioRecord), Spotify (libmediandk), Discord, BBC News, Shazam (board libc++_shared.so shadows the app's) | 8 |
| carried, cause unconfirmed | TikTok, CapCut (both carry load:shadowed-by-board) | 2 |
| background row only | Waze (telephony hollow-candidate), Citymapper (provider order unverified) | 2 |
| blind spot | Facebook, Messenger, Instagram, Threads, WhatsApp, Transit, SmartNews, CNN, NYTimes, Flipboard | 10 |
| silent, cause unknown | The Guardian, Microsoft Start, Moovit, Reddit, Zoom | 5 |

8 of the 22 blockers found were named in advance (36%); counting the two unconfirmed, 10 of 22.

**Blind-spot clusters -- candidate checks:**

1. App-data file operations Android allows and OH refuses: removing write permission / marking
   read-only (Facebook, Messenger via SoLoader's lib-compressed; CapCut), and mapping a library
   from app data (CapCut, errno 13). The existing policy rows cover symlinks and fifos only.
2. Thread priority 0 rejected (Instagram, CapCut): an argument Android accepts at startup.
3. Services marked "supplied" whose answers are null or 0 where Android's are real: the memory
   class (CNN, LruCache maxSize 0), WifiManager connection info (NYTimes), the telephony registry
   and TrafficStats (Waze). "Supplied" needs to check the specific answers startup code reads.
4. Provider start order: FirebaseInitProvider must run before androidx.startup (Citymapper).
5. The app's own JNI natives unregistered (WhatsApp, Transit; TikTok maybe): cause not yet known.
6. One-offs: a missing ZipEntry (Threads), WorkManager not initialized (SmartNews), an
   UnsupportedOperationException in an initializer (Flipboard).

Five apps die silently; their logs need the hilog capture before they can be classified.
