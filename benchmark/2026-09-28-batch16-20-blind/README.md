# Batches 16–20: 100 new F-Droid apps, predicted and launched blind (framework 68)

A test of generalization. Everything below was fixed before any of these apps was launched, and
nothing in Westlake or the harness changes until all 100 have been launched and judged:

- **Harness:** westlake-harness 13974d5, predictor rule v3 (`scripts/predict_first_screen.py`).
- **Provider:** framework 68, native runtime opengl11, runtime data tz2, bionic shim nw9.
- **Runner:** each app's launch remedies are taken from its gap map (`launch_args`).

The earlier batches mixed launching and fixing. This one measures how far the fixes made for the
first 200 apps carry to apps nobody looked at.

## Selection

The same rule as batches 11–15, applied to the apps not yet tried. The source is the F-Droid index
(2026-09-23). Eligible apps:

- were updated within the last 12 months;
- target SDK 30 or later;
- are at most 80 MB;
- ship arm64 native code or none.

That left 2,068 apps in 112 categories. The pick is one app per category in turn, with the most
maintained app first in each category. All 100 downloads verified against the index's sha256
(`apps.json`).

## Prediction

Rule v3, static maps, no Android traces: **5 of 100 predicted blocked** (`predictions.json`). v3's
recall on the first 200 apps was 0.25, so most blocked apps are expected to go unpredicted.

## Judging (pre-registered)

Each app is launched once, with one screenshot 30 s after launch. An app **draws** when the screenshot
shows the app's own screen. That covers a splash, onboarding or main screen, the same bar as the
earlier batches, with these exclusions:

- **Blocked:** the OH host screen (the app left or died), an empty or blank window, an app-drawn error
  page (crash report or library-load error), or a screen with part missing (a region the app should
  draw is empty).
- **Reported separately:** "past splash", counting apps whose screenshot shows more than a logo or
  loading splash. It is the stricter number.
- **Hdc drops:** a launch the hdc connection dropped is relaunched and does not count as a result.

## Result (launched 2026-09-28, judged by the rules above)

**79 of 100 draw; 78 past splash** (K-9's "Upgrading databases" is the one splash-only screen).
All 100 launched first time; no hdc drops. `outcomes.json` holds the judgement for each app and the
five screenshots the screen check passed but the rules exclude: two blank or black windows, an
app-drawn SDL error, an empty camera-preview region and an empty browser page.

For comparison on the same framework: batches 11–15, whose blockers were fixed as they were found,
draw 70 of 99. The fixes carried over to apps nobody looked at. One caution: this is the second pick
in each category, which may be simpler apps than the first.

**The predictor did not generalize.** It predicted 5 blocked. Result: precision 0.60 (3 true, 2 false
-- ndk:package on Nora and Time Tracking, both of which draw), recall 0.14 (18 of 21 blocked apps
missed). As a first-screen predictor the static map is weak. Its value is the gap list and the fix
queue, not the yes/no call.

The 21 blocked apps, by cause:

| cause | apps |
|---|---|
| media natives unregistered at startup (MediaPlayer.native_init, AudioSystem, AudioTrack) | doorsofdoom, game, ntfy, mousepounce, musekit |
| OpenSL ES Android configuration interface (SL_IID_ANDROIDCONFIGURATION) | jigsaw, v3 |
| activity start: InflateException | clauncher, facebooknotifica |
| activity start: ArithmeticException | aat |
| stops after bind, nothing logged | drawanywhere, shortcut, insigno, playmaker |
| libGLESv1_CM.so absent (SDL) | anarchre |
| bionic getprogname unresolved | linphone |
| blank or black window | accelerace, spacebeam |
| a region empty (camera preview, web page) | fairscan, standard |
| leaves after drawing, nothing logged | wormhole2 |

## Follow-up: the media cluster (after the blind judgement)

Fixed afterwards in westlake `5ae6b75`, tested with the rebuilt `libwl_missing_natives.so` as a
runtime-library override on build 68. The blind numbers above are unchanged; this is the fix loop.

| app | before | after |
|---|---|---|
| ntfy | MediaPlayer.native_init | draws its main screen |
| Astro Loop | MediaPlayer.native_init | draws, in game |
| Doors of Doom | MediaPlayer.native_init | draws, in game; its music plays |
| Mouse Pounce | AudioSystem.getParameters | past audio (ExoPlayer plays through the AudioTrack shim); its Flutter window then fails with EGL_BAD_SURFACE on resize and never shows |
| MuseKit | AudioTrack buffer size | past AudioTrack; stops on AudioRecord, microphone capture, which is not ported |

So 3 of the 5 now draw, 82 of 100 in all. Doors of Doom's music was checked by recording the
board's output, not by the player's state logs: see `probes/audio-capture`. The recording matches
the game's music1.mp3 at the expected position (r = 0.62; shuffled control 0.07).

The harness saw only MediaPlayer, the one class with none of its natives registered. AudioTrack
and AudioSystem are partly registered, and an app reaches their missing natives through public
wrappers (AudioTrack.getBufferSizeInFrames, AudioManager.getPlaybackOffloadSupport, two calls
deep). Two changes now find them. The runtime index records the natives each framework method
reaches, three calls deep. And a class named by a runtime library counts as bound only for the
method names that library also holds.

## Follow-up: OpenSL ES (after the media cluster)

Jigsaw and V3 (Godot) failed to load their engine: OH's libOpenSLES has no
SL_IID_ANDROIDCONFIGURATION. Fixed in westlake `1e98162` (the Android configuration interface, and
interface IDs handed to OH by its own addresses) and `c7d2992` (Oboe's dlopen of libOpenSLES routed
to the adapter; the buffer queue no longer pads OH's pulls with silence), in shim bionic-shim-nw11.
Both now draw: **84 of 100** with the fixes, still on framework 68 with overrides.

The sound was checked by ear and by recording: the buffer-queue fix took a 1 kHz test tone from
48-73% silent 10 ms windows to none (`probes/audio-capture`), and `probes/audio-tone` then found
and confirmed the fix for AudioTrack float writes through a ByteBuffer (westlake `21676bd`).
