# Corpus 3: the second blind test

Corpus 2 predicted 7 of 10 and got 2. Every miss was optimistic. This corpus is the blind test for
the checks added after corpus 2. Its apps repeat corpus 2's failure mechanisms on purpose:

- a second Flutter app;
- a native OpenGL map;
- a WebView-first client;
- sync and account apps.

As before, the predictions were committed before any launch, and the results are added without
editing them.

Provider: Westlake `corpus2-fixes` at `8fa7346` (framework build 40, the native runtime with the
EGL14 bindings, and bionic shim nw8). The board is OpenHarmony 6.1.0.31, arm64.

## Corpus

Original arm64 APKs from the F-Droid main repository, each download's sha256 checked against the
index ([downloads.lock.json](downloads.lock.json)).

| App | Version | Why it is here |
|---|---|---|
| Aurora Store | 4.8.4 | Compose, network, package installer |
| Nextcloud | 35.0.0 | accounts, sync, WebView login |
| DAVx5 | 4.5.20 | sync adapters, accounts |
| OsmAnd | 5.4.4 | native C++/Qt map engine, OpenGL map view |
| Fossify Music Player | 1.8.1 | media playback service, media permissions |
| Feeder | 2.23.2 | Compose, WorkManager, networking |
| Catima | 2.45.0 | barcodes, camera |
| Jellyfin | 2.7.3 | WebView-first media client |
| Obtainium | 1.6.17 | Flutter (FluffyChat's mechanism, again) |
| FairEmail | 1.2337 | mail: sync service, huge UI |

## Harness changes before predicting

Two came from corpus 2's misses. Two surfaced while building these maps:

1. **`throws_in_framework`** (from corpus 2): a hollow service whose null answer AOSP's own manager
   unwraps throws inside the framework.
2. **The check had to know when the provider fixed it.** On the first corpus-3 maps it fired for
   seven apps on JobScheduler and notification, both of which build 40 fixed. The service model now
   reads `publishLocalService`, and knows a provision that answers empty lists. It still fires on
   the provider corpus 2 was predicted on and is silent on build 40.
3. **Aliases** (from corpus 2): `main_activities` now reports each launcher alias's target activity.
4. **Non-UTF-8 tool output** (new): one byte in OsmAnd's symbol tables aborted the whole scan.

| App | Native imports resolved | Rows | Gaps |
|---|---|---|---|
| Aurora Store | 7 / 7 | 57 | 33 |
| Nextcloud | 760 / 760 | 75 | 48 |
| DAVx5 | 123 / 123 | 56 | 29 |
| OsmAnd | 1508 / 1508 | 59 | 35 |
| Fossify Music Player | 7 / 7 | 53 | 32 |
| Feeder | 63 / 63 | 37 | 19 |
| Catima | 7 / 7 | 48 | 27 |
| Jellyfin | 95 / 95 | 52 | 31 |
| Obtainium | 477 / 477 | 71 | 46 |
| FairEmail | 152 / 152 | 60 | 35 |

## Predictions

Two numbers this time.

- **Row-based: 8 of 10 draw.** This is what the map says.
- **Calibrated: 5 to 6.** In corpus 2, three of ten apps died on causes no row modelled, and every
  miss was optimistic. Scoring both numbers says whether the map's blind spots are shrinking.

| # | App | Expected | Blocker | Confidence | From |
|---|---|---|---|---|---|
| C1 | Aurora Store | onboarding draws | — | medium | no L row on the first screen |
| C2 | Nextcloud | first-run screen draws | — | medium | native first screen; WebView login only after a tap |
| C3 | DAVx5 | accounts screen draws, empty | — | medium-high | no L row |
| C4 | OsmAnd | no usable map screen | shared SurfaceView window | medium-low | **not a row**: round 8 |
| C5 | Fossify Music Player | main screen draws, no-permission state | — | medium-high | same family as Gallery |
| C6 | Feeder | feed list draws, empty | — | medium-high | no L row |
| C7 | Catima | card list draws, empty | — | high | no L row |
| C8 | Jellyfin | native connect screen draws | — | medium | connect screen is Compose; WebView only after connecting |
| C9 | Obtainium | no Flutter frame | an NDK name Flutter resolves at run time | medium | `sym:runtime-resolved`, as for FluffyChat |
| C10 | FairEmail | setup screen draws | — | medium | no L row; a dropped `startService` does not stop the first screen |

Launch configuration comes from the map. The launch activity is the alias-resolved
`main_activities`, and OsmAnd's five shadowed libraries go to the Android namespace.

Known blind spots, stated in advance:

- The shared SurfaceView window still has no row.
- A service started with `startService` is dropped without a row.
- Which NDK name was null for FluffyChat is unconfirmed, so C9 tests a hypothesis.

## Results

Not yet run.
