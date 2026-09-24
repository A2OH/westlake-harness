# Batch 5: mechanical predictions

Fossify Notes, Clock, Messages and File Manager, Amaze File Manager, Droid-ify, the F-Droid client,
Antimine, Unciv and Gadgetbridge ([downloads.lock.json](downloads.lock.json)).

Provider: Westlake `corpus2-fixes` at `04e9bd5`, framework 45 (native runtime opengl5, bionic shim
nw8). Maps use the build-45 runtime index and the blockers ledger.

## Predictions

[predictions.json](predictions.json), from `scripts/predict_first_screen.py`, committed before any
launch:

- **Rule: 10 of 10 draw.** No map has an unresolved native import, a framework-side throw, or a
  missing NDK run-time lookup.
- **Calibrated: about 7.** Batch 4's first-launch rate on the build before this one. The rule has
  no signal for a libGDX/GLSurfaceView game, and Unciv is one: Shattered Pixel Dungeon, the same
  engine, did not draw.

### A late prediction, still blind

After this batch's predictions were committed, the harness gained `window:engine-surface`: a first
screen drawn by an engine (libGDX, Arc, Flutter, SDL, Unity, Godot, a NativeActivity) into its own
SurfaceView. It flags **Unciv (libGDX): predicted blocked.** This is committed before Unciv's
launch result is known. The other nine are unchanged.

## Results

Not yet run.
