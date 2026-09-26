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

One launch per app on framework 45, SELinux enforcing, 35 s wait, a screenshot each.

**8 of 10 drew on first launch**: Fossify Notes, Clock and File Manager, Amaze, Droid-ify, the
F-Droid client, Antimine and Gadgetbridge.

| App | Rule | Outcome | Why |
|---|---|---|---|
| Fossify Messages | draws | **blocked** | `RoleManager` null (no `role` service). Fixed in `2b21e12`: it now draws its main activity, then closes, because the board has no SMS role to hold. That is correct behaviour for a device without telephony |
| Unciv | draws; **late row: blocked** | **blocked** | libGDX draws into its own SurfaceView (`window:engine-surface`); the IME host stays on screen |

- **Rule: 8 of 10 right.** The calibrated forecast (about 7) was one pessimistic.
- **The engine-surface row was right on its first blind case** (Unciv), predicted and committed
  before Unciv launched.
- The scorer called both failures "drawing". In both cases a window was created and something
  drew, then the process died or finished. **The screenshot decides**, and scoring from the log
  alone would have reported 10 of 10.
