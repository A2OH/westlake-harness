# Batch 7: mechanical predictions

Seal, Home Assistant (minimal), Trail Sense, Chrono, Noice, Retro Music, RadioDroid, Kore, openHAB
and AndStatus ([downloads.lock.json](downloads.lock.json)).

Provider: Westlake `corpus2-fixes` at `e2524b1`, framework 47 (native runtime opengl6 with the
audio-effect library, bionic shim nw8).

## Predictions

[predictions.json](predictions.json), from `scripts/predict_first_screen.py`, committed before any
launch:

- **Rule: 8 of 10 draw.** Seal is flagged for an NDK run-time lookup (`libandroid`) and a bionic
  libc import. Home Assistant is flagged for unresolved native imports (libc ABI and an NDK
  package symbol).
- **Calibrated: about 8 to 9.** Batch 6 drew 9 of 10 on first launch.

## Results

Not yet run.
