#!/usr/bin/env python3
"""tone_timeline.py <recording.wav>: which audio path played, at what pitch, with what gaps.

For a playback-capture recording (probes/audio-capture/oh_record, source 2) made while the
audio-tone probe runs. Each 50 ms window is labelled by its dominant tone: A = AudioTrack 16-bit
48 kHz (1000 Hz), B = AudioTrack 16-bit 44.1 kHz (1500 Hz), C = AudioTrack float ByteBuffer
(2500 Hz), M = MediaPlayer (2000 Hz), '.' = silent, '?' = sound that is none of them.
A correct path shows solid runs of its letter at its exact frequency, about 4 s per round.
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "audio-capture"))
from tone_check import rebuild  # noqa: E402

RATE, WIN = 48000, 2400
TONES = {1000: ("A", "AudioTrack 16-bit 48 kHz"), 1500: ("B", "AudioTrack 16-bit 44.1 kHz"),
         2500: ("C", "AudioTrack float ByteBuffer"), 2000: ("M", "MediaPlayer")}


def main():
    y = rebuild(sys.argv[1])
    labels, freqs = [], {t: [] for t in TONES}
    for i in range(len(y) // WIN):
        seg = y[i * WIN:(i + 1) * WIN]
        if np.sqrt(np.mean(seg ** 2)) < 300:
            labels.append(".")
            continue
        spec = np.abs(np.fft.rfft(seg * np.hanning(WIN)))
        k = int(np.argmax(spec))
        f = k * RATE / WIN
        if 0 < k < len(spec) - 1:
            a, b, c = np.log(spec[k - 1:k + 2] + 1e-9)
            f += 0.5 * (a - c) / (a - 2 * b + c) * RATE / WIN
        near = min(TONES, key=lambda t: abs(t - f))
        if abs(near - f) < 60:
            labels.append(TONES[near][0])
            freqs[near].append(f)
        else:
            labels.append("?")
    line = "".join(labels)
    print(f"{len(y) / RATE:.1f} s rebuilt; timeline in 50 ms windows:")
    for i in range(0, len(line), 80):
        print("  " + line[i:i + 80])
    for tone, (letter, name) in TONES.items():
        fs = freqs[tone]
        print(f"  {letter} {name:28} " + (f"{len(fs) * 0.05:5.1f} s, median {np.median(fs):7.1f} Hz (expected {tone})"
                                          if fs else "not heard"))
    print(f"  ? unrecognised sound: {line.count('?') * 0.05:.1f} s")


if __name__ == "__main__":
    main()
