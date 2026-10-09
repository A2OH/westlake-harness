# audio-capture probe

`oh_record` records what the OH board plays, so an audio port is checked by its output rather
than by its own state logs. A player can report "playing", and a renderer can accept every write,
and still be silent.

    ./build.sh <oh-sdk-native>
    hdc file send out/oh_record /data/local/tmp/oh_record
    hdc shell /data/local/tmp/oh_record /data/local/tmp/out.wav <seconds> [source]

`source` 2 is OH's playback capture: the mixed output, recorded digitally. It is documented as
system-app only, but it works from `hdc shell`. `source` 0 is the microphone, which hears the
speaker: coarser, but independent of the mixer.

Playback capture on the OH 6.1 board returns 4800-sample callbacks in which only the first 960
samples (20 ms at 48 kHz) are audio and the rest is zero padding, so a file holds about five times
the samples of its duration. `oh_record` keeps it raw at the true 48 kHz; `tone_check.py` rebuilds
the audio from the blocks. (An earlier version wrote a "measured" 240 kHz rate into the header.
That was wrong: it was the padding.)

## Pitch and continuity: `tone`

`tone <sl|oh> <rate> <seconds> [freq]` plays a sine. `sl` drives Westlake's Android OpenSL ES
adapter with Android's 4-byte ABI, as a game's audio engine does: engine, output mix, a player on
an Android simple buffer queue, stereo 16-bit, two 1024-frame buffers refilled from the callback.
`oh` plays the same tone through OHAudio as the control. Run it in the background while recording,
with the shim preloaded as it is in an app:

    LD_PRELOAD=<dir>/libwebview_bionic_shim.so LD_LIBRARY_PATH=<dir> ./tone sl 44100 7 &
    /data/local/tmp/oh_record out.wav 4 2
    python3 tone_check.py out.wav 1000

Found with it (heard first on Ball2Box as broken, off-pitch sound): the adapter's buffer queue
filled OH's much larger pull buffers only with what the app had already queued, and padded the
rest with silence.

| path | peak | silent 10 ms windows |
|---|---|---|
| OHAudio control, 48 kHz | 1000 Hz | 0% |
| adapter, 48 kHz, before | 998 Hz | 48% |
| adapter, 44.1 kHz, before | 995 Hz | 73% |
| adapter, 48 kHz, fixed | 1000 Hz | 0% |
| adapter, 44.1 kHz, fixed | 1000 Hz | 0% |

On Ball2Box itself, dropouts fell from 42% of 10 ms windows to 0 (median RMS 306 to 2219).

## AAudio over OHAudio: `tone aa`, `aa16`, `aaw`, `aain`

The AAudio modes open `libaaudio.so` and look its entry points up by handle, as Oboe does, so with
the shim preloaded they reach Westlake's AAudio over OHAudio; without the shim the dlopen fails, as
OH has no such library. Recorded the same way, 4 s from 1 s in, on the OH 6.1 board:

| path | peak | silent 10 ms windows |
|---|---|---|
| OHAudio control, 48 kHz | 1000 Hz | 0% |
| `aa`: data callback, float, 48 kHz | 1000 Hz | 0% |
| `aa`: data callback, float, 44.1 kHz | 1000 Hz | 0% |
| `aa16`: data callback of exactly 192 frames, 16-bit, 48 kHz | 1000 Hz | 0% |
| `aaw`: blocking writes, 16-bit, 48 kHz | 1001 Hz | 0% |
| `aaw`: blocking writes, 16-bit, 44.1 kHz | 998 Hz | 1% |

- `aa16` ran 1788 callbacks, none of another size: OH asks for about 93 ms per callback (4458 frames
  at 48 kHz in its normal latency mode), and the stream cuts and joins the app's buffers to fit.
- The streams counted no underruns. Their timestamps were valid once playing, and invalid before.
- `aain` read float frames from the microphone at room level (RMS 26.5 on the 16-bit scale).

## First use: MediaPlayer on OH AVPlayer (Doors of Doom)

Recorded for 6 s while Doors of Doom played music1.mp3 through the new MediaPlayer port:

| recording | RMS | peak |
|---|---|---|
| playback capture, nothing playing | 0 | 0 |
| playback capture, game running | 470 | 5088 |
| microphone, nothing playing | 30 | 125 |
| microphone, game running | 39 | 271 |

Matched against music1.mp3 decoded from the APK (log-energy envelope, 20 ms hops), the capture
lines up at 16.3 s into the track with r = 0.62 (matched on the raw padded file at the wall-clock
rate, which the envelope tolerates). A shuffled control scores 0.07. 16 s is about
how long the game had been running, so this is the game's music at the right position.
