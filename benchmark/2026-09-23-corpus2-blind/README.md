# Ten more apps: blind predictions from the map, then the launches

The first loop corpus reached 8 of 10. This one tests whether the harness predicts, rather than
discovers. Ten popular F-Droid apps, each with surfaces the first ten did not cover. Every app was
run through the whole pipeline and predicted **before any launch**. The score is added after the
launches, without editing the predictions.

Provider: Westlake main at `0b5c9af`: framework build 38, native runtime with the Java OpenGL
bindings, and the bionic shim with the OpenSL ES translation layer. The board is OpenHarmony
6.1.0.31, arm64.

## Corpus

Original arm64 APKs from the F-Droid main repository, unmodified. Each download's sha256 matches
the index entry ([downloads.lock.json](downloads.lock.json)).

| App | Version | Why it is here |
|---|---|---|
| VLC | 3.7.1 | libvlc native media engine, video surfaces |
| Organic Maps | 2026.08.27 | native C++ map engine drawing into a SurfaceView |
| Thunderbird | 23.0 | mail, Compose, accounts |
| KeePassDX | 4.5.4 | native crypto, file pickers |
| Fossify Gallery | 1.13.1 | MediaStore, media permissions |
| Tusky | 32.2 | Mastodon client: networking, Room, media3 |
| Element | 1.6.62 | Matrix: Rust crypto SDK, React Native pieces, WebRTC, Realm |
| FluffyChat | 2.9.5 | Flutter |
| Breezy Weather | 6.2.2 | Compose, location, WorkManager |
| Fennec (Firefox) | 156.0 | Gecko engine, multiprocess, NDK media |

## Pipeline

`snapshot-runtime` over the deployed boot jars, native runtime, bionic shim and seven OH system
libraries pulled from the board. Then, per app: `scan`, `annotate-api-levels` (28/33/34/35/36,
reference 35), `oh-resolve`, and `gap-map` with NDK coverage, the board's library listing and the
staged runtime. The maps are in [maps/](maps/).

| App | Native imports resolved | Rows | Gaps |
|---|---|---|---|
| VLC | 889 / 889 | 70 | 46 |
| Organic Maps | 307 / 307 | 49 | 27 |
| Thunderbird | 27 / 27 | 58 | 34 |
| KeePassDX | 20 / 20 | 51 | 29 |
| Fossify Gallery | 308 / 308 | 58 | 32 |
| Tusky | 133 / 133 | 56 | 32 |
| Element | 979 / 1034 | 92 | 57 |
| FluffyChat | 541 / 541 | 64 | 39 |
| Breezy Weather | 132 / 132 | 49 | 24 |
| Fennec | 1827 / 1884 | 81 | 51 |

### Three harness defects, fixed before predicting

The first maps from this corpus were wrong in ways the first corpus never exposed:

1. **Fat APKs were resolved across every ABI.** Eight of these APKs carry arm64, armv7, x86 and
   x86_64 libraries in one file. `oh-resolve` and nine `gap-map` sites read every copy, so Tusky
   was charged 12 missing `__aeabi_*` symbols that only armv7 code imports. The first corpus had
   arm64-only APKs, so this never showed. Now only the target ABI's libraries count.
2. **A guard read as a stub.** `resolveContentProvider` answers by authority (the round-2 fix),
   and calls `logStub` only when the authority is null. The model treated any `logStub` as a stub,
   so the map reported a fixed gap as open. A method is now a stub only when every return is a
   constant. Four methods changed verdict; no others moved.
3. **Another library's symbols were filed as libc.** Element's `libjsctooling.so` imports 55
   JavaScriptCore symbols from `libjsc.so`, which the APK does not ship. They were grouped as
   "bionic libc ABI: translate onto musl". They now form their own row: a library the APK needs
   but does not ship, a blocker only if something loads the importer.

## Predictions

The overall prediction: **7 of 10 draw a first screen.** Machine-readable form:
[predictions.json](predictions.json).

| # | App | Expected | Blocker | Confidence | From |
|---|---|---|---|---|---|
| A1 | VLC | onboarding draws | — | medium | all imports resolve; shadowed-library row applied |
| A2 | Organic Maps | resource screen draws, then the map fails | SurfaceView shares the activity window | medium | **not a row**: round 8 |
| A3 | Thunderbird | onboarding draws | — | medium-high | no L row on the startup path |
| A4 | KeePassDX | database selection draws | — | high | no L row |
| A5 | Fossify Gallery | main screen draws, stuck without media permission | — | medium | **not a row**: permission dialogs |
| A6 | Tusky | login screen draws | — | high | no L row |
| A7 | Element | auth splash draws | — | medium-low | shadowed-library row applied; libjsc unused under Hermes |
| A8 | FluffyChat | no Flutter frame | SurfaceView shares the activity window | medium | **not a row**: round 8 |
| A9 | Breezy Weather | first-run screen draws | — | medium-high | missing APIs are API 36, behind SDK checks |
| A10 | Fennec | dies before its first screen | libxul.so cannot link: 48 `libmediandk` symbols | medium-high | `ndk:weld:media` |

Launch configuration follows the map. Each library a `load:shadowed-by-board` row lists is
launched in the Android namespace (VLC 4, Element 9). The three launchers that are
activity-aliases are launched at their target activity.

Known blind spots, stated in advance:

- No row models a SurfaceView that shares the activity's window. A2 and A8 are predicted from
  round 8, not from the map.
- Permission dialogs are not modelled.
- Which libraries load at startup is judged from the code, not from a trace.

## Results

Not yet run.
