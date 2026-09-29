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

Playback capture on the OH 6.1 board delivers about 240800 frames a second while reporting
48000. The recorder writes the measured rate into the WAV header when the two disagree.

## First use: MediaPlayer on OH AVPlayer (Doors of Doom)

Recorded for 6 s while Doors of Doom played music1.mp3 through the new MediaPlayer port:

| recording | RMS | peak |
|---|---|---|
| playback capture, nothing playing | 0 | 0 |
| playback capture, game running | 470 | 5088 |
| microphone, nothing playing | 30 | 125 |
| microphone, game running | 39 | 271 |

Matched against music1.mp3 decoded from the APK (log-energy envelope, 20 ms hops), the capture
lines up at 16.3 s into the track with r = 0.62. A shuffled control scores 0.07. 16 s is about
how long the game had been running, so this is the game's music at the right position.
