# Batch 9: mechanical predictions

Element X, Nextcloud Talk, mpv, SuperTuxKart, DuckDuckGo, PipePipe, StreetComplete, RedReader,
Briar and OpenKeychain ([downloads.lock.json](downloads.lock.json)). Heavier apps than batch 8:
two native media engines, a native game, a Chromium browser, a Rust-based Matrix client.

Provider: Westlake `corpus2-fixes` at `1baca65`, framework 53 (native runtime opengl6, bionic
shim nw8).

## Predictions

[predictions.json](predictions.json), committed before any launch:

- **Rule: 6 of 10 draw.** mpv, SuperTuxKart (engine surface plus NDK audio and sensor welds),
  PipePipe (a libmediandk run-time lookup) and Briar (libc ABI) are flagged.
- **Calibrated: about 4 to 5.** Batch 8 drew 4 of 10 on first launch, and this batch is heavier.

## Results

Not yet run.
