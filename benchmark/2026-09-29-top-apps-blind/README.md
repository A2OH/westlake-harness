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
