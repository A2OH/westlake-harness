#!/usr/bin/env python3
"""tone_check.py <recording.wav> [freq]: pitch and continuity of a recorded test tone.

oh_record's playback capture on the OH 6.1 board delivers 4800-sample callbacks in which only the
first 960 samples (20 ms at 48 kHz) are audio; the rest is zero padding. This rebuilds the 48 kHz
signal from those blocks, then reports the dominant frequency and, per 10 ms window, whether the
tone is present. A path that drops audio shows silent windows; OHAudio's own renderer shows none.
"""
import sys
import wave

import numpy as np

RATE, BLOCK, VALID = 48000, 4800, 960


def rebuild(path):
    w = wave.open(path)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float)
    start = int(np.flatnonzero(np.abs(x) > 0)[0])
    return np.concatenate([x[i:i + VALID] for i in range(start, len(x) - BLOCK, BLOCK)])


def main():
    path, freq = sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 1000.0
    y = rebuild(path)
    y = y[len(y) // 10:]
    spec = np.abs(np.fft.rfft(y[:RATE] * np.hanning(min(RATE, len(y)))))
    peak = np.fft.rfftfreq(min(RATE, len(y)), 1 / RATE)[int(np.argmax(spec))]
    win = RATE // 100
    windows = len(y) // win
    silent = sum(1 for i in range(windows) if np.sqrt(np.mean(y[i * win:(i + 1) * win] ** 2)) < 300)
    print(f"{path}: {len(y) / RATE:.1f} s, peak {peak:.0f} Hz (expected {freq:.0f}), "
          f"silent 10 ms windows {silent}/{windows} ({100 * silent / max(1, windows):.0f}%)")


if __name__ == "__main__":
    main()
