# HK top-1000: static baseline (build 120)

The first pass over the new target corpus, the 1,000 most popular Google Play apps in Hong Kong:
every app the corpus could obtain was scanned and mapped against build 120, before any of them
was launched. This is the static half of gate G1. The device half (where apps actually stop) is
the next round. Its first finding is that the first-screen predictor, fitted on F-Droid apps, does
not carry over to commercial apps (below).

## Corpus

`apps.csv`: rank, package, title, kind (706 apps, 294 games), source, and the predictions. The
ranking is a reciprocal-rank fusion (k=60, overall charts weighted x3) of the 102 HK Play charts
(top free and top grossing, overall and every category, 200 each) of 2026-10-23. It is an interim
ranking until market data replaces it.

982 of the 1,000 were obtained, all for arm64-v8a:

| source | apps | |
|---|---|---|
| APKPure | 543 | already carried arm64-v8a |
| Google Play | 334 | APKPure served armeabi-v7a only, despite `arch=arm64-v8a` |
| Google Play only | 65 | not on APKPure |
| APKPure, older build | 37 | Play refused; APKPure's version list had an arm64 build of an earlier release |
| Huawei AppGallery | 1 | Scameter (HK Police); same version code as Play |
| armeabi-v7a only | 2 | myTV SUPER's Android TV build; com.egsl.zhy.gp1 |
| missing | 18 | Wear OS watch faces, Taiwan-region games, delisted ids |

**APKPure ignores the ABI request for about 40% of apps.** 373 of the 916 apps it delivered
carried armeabi-v7a only. A v7a-only copy scans with no arm64 natives and cannot run on Westlake,
so any corpus fetched from APKPure needs the ABI check (every nested split's `lib/<abi>/`)
before it is mapped. corpus-top had the same problem: 12 of its apps were re-fetched from Play
by hand in 2026-09-29-top-apps-blind. Play refused 47 apps at the acquire step
(HTTP 400, `DF-DFERH-01`): age-rated dating and live-streaming apps (Tinder, Bumble, Grindr, Badoo, Bigo)
on any anonymous account, and region-locked apps. APKPure keeps several builds per release, and
the ABI of each can be read from its zip central directory with a ranged request, which is how
37 apps were found in arm64 one or two releases back.

Harness #58 was needed to map them all. 21 games ship 1.1-2.9 GB asset packs, which the scanner
refused, and one PayPal provider had no readable name.

## First-screen prediction, and why it does not hold here

`scripts/predict_first_screen.py` (rule v3) on all 982 maps: 723 draw, 259 blocked. The blocked
calls are almost entirely two signals that were rare on the F-Droid corpora the rule was fitted on:

| signal | apps | what it is |
|---|---|---|
| `ndk:weak-api` | 206 | weak NDK imports the board does not define, bound to 0 |
| `lookup:sym:runtime-resolved:libnativehelper.so` | 59 | `JNI_GetCreatedJavaVMs` looked up by name |
| `ndk:weld:*` | 36 | power 12, buffers 9, window 6, input 6, services 3 |

`ndk:weak-api` splits by library. **libmediandk**, 149 apps (146 Unity games): `AMediaDataSource_*`,
`AMediaCodec_setOutputSurface` and `AMediaExtractor_setDataSourceCustom`, all for Unity's
VideoPlayer. **libandroid**, 39 apps: `ASurfaceTransaction_*` and `ASurfaceControl_createFromWindow`,
in Chromium, androidx graphics-core and Filament. **libc**, 17 apps: fdsan and
`__system_property_serial/wait`, in KOOM and rmonitor. If, like the rule's media welds, the
libmediandk imports count only when media plays (`predicted_media_lazy` in apps.csv), the totals
are 856 draw and 126 blocked.

Backtest on the 22 apps this corpus shares with corpus-top, against their r90 outcomes on
build 119/120:

| prediction | drew | stopped earlier |
|---|---|---|
| blocked (`ndk:weak-api`: Facebook, Messenger, Instagram, Threads, CapCut, Snapchat) | 6 | 0 |
| blocked (`libnativehelper` lookup: Telegram) | 1 | 0 |
| draws | 13 | 2 (NYTimes at the activity, Reddit at the view) |

All 7 blocked predictions are wrong. Both signals flag apps that draw: the imports are guarded, or
not on the startup path. So the rule's "blocked" list says nothing about this corpus, and its
"draws" (13 of 15 right here) are only as good as the device round will show. Until a device round
re-fits it, read the predictions as a list of native risks per app, not as outcomes.

## Open rows by reach

`open-rows.json`: every row with an open verdict, with the number of the 982 maps that carry it.
This is reach (the app's code or manifest can hit the gap), not a startup blocker. The rows
that most apps carry, leaving out C0 contracts (intents and services OpenHarmony answers by
design):

| apps | row | class / effort |
|---|---|---|
| 974 | `dep:google-play-services` (absent) | C5 / M |
| 959 | `am:permission-request` | C9 / XS |
| 955 | `wm:popup-window` | C6 / S |
| 938 | `pm:call:queryIntentActivityOptions` (stub) | C9 / M |
| 937 | `dep:firebase-component-discovery` (partial) | C5 / verify |
| 932 | `jni:android.media.MediaMetadataRetriever` | C3 / M |
| 928, 915 | `pm:call:set/getComponentEnabledSetting` (stub) | C9 / S |
| 917 | `pm:call:queryIntentContentProviders` (stub) | C9 / M |
| 912 | `jni:android.view.KeyCharacterMap` (2 of 14 natives) | C3 / S |
| 857 | `jni:android.media.MediaCodec` (26 of 46 natives) | C3 / M |
| 756, 750 | `jni:android.media.ImageReader`, `PublicFormatUtils` | C3 / M, S |
| 729 | `jni:android.renderscript.RenderScript` | C3 / L |
| 728 | `svc:media_metrics` (null) | C5 / S |
| 705 | `jni:android.media.MediaExtractor` | C3 / M |
| 662, 619 | `jni:android.media.MediaDrm`, `MediaCrypto` | C3 / M, S |
| 561 | `sym:runtime-resolved:libandroid.so` | C1/C2 / M |
| 335 | `window:surfaceview-opacity` | C2 / S |
| 330 | `pm:multiprocess` | C4 / L |
| 206 | `ndk:weak-api` (149 libmediandk, 39 libandroid, 17 libc) | C1 / S |

Media is the largest native family: MediaMetadataRetriever, MediaCodec, MediaExtractor,
ImageReader and MediaDrm each reach 660-930 apps. On the F-Droid corpus they reached 25-75%.

Added after this baseline was published, so it is not yet in `open-rows.json`:
`dep:store-license-check`, the license check the store app answers (C5 / M). **224 of the 982**
carry it, counted from these scans: each declares a `com.pairip.licensecheck` component, which
Play adds to an app it protects. Unlike the other `dep:` rows it stops the launch rather than
degrading a feature, and the device round on the top 100 shows it stopping five apps that the
round had recorded as silent stops. The next regeneration of the 982 maps will carry the row.

## Google services

`gms-reach.json` (`gms_reach.py`): per app, the Google client families its dex references. The
type tables of every dex, nested splits included, are read; R8 renaming makes the counts lower
bounds. Reach means the code can call a family, not that it does at startup. Several families
come in transitively (Firebase pulls in the sign-in client).

| family | apps of 982 |
|---|---|
| any GMS client | 957 |
| Google Sign-In / Identity | 948 |
| Firebase (any) | 944 |
| Play Billing | 875 |
| Firebase Analytics | 874 |
| FCM (push) | 861 |
| AdMob | 813 |
| Fused location | 811 |
| Advertising ID | 780 |
| GoogleApiAvailability check | 728 |
| Crashlytics | 674 |
| Play in-app review | 547 |
| FIDO / passkeys | 543 |
| Play Integrity | 531 |
| SMS retriever / credentials | 512 |
| Play asset delivery / split install | 364 |
| Firebase Auth | 239 |
| ML Kit | 233 |
| Play in-app update | 219 |
| reCAPTCHA | 201 |
| Maps SDK | 182 |
| Play Games | 173 |
| SafetyNet | 27 |

Play Integrity reaches 531 apps, more than half the corpus, and SafetyNet only 27. Play
Billing (875) needs the Play Store side (`com.android.vending`), not only GMS.

## Next

1. A device round on the top of the corpus (rank order, at least the top 100), to measure where
   apps stop and re-fit the first-screen rule on commercial apps.
2. Cheap native closures the maps name: the libmediandk weak imports (149 apps) and the libc
   fdsan/system-property ones (17), defined in the bionic shim.
3. The microG work (W1) is sized by the table above: availability, FCM, sign-in and location
   first. Billing and Integrity need the Play Store side.

Provider: build 120 (westlake e8d4b20, manifest 95701d2), runtime index 120, probe results as of
r90.
