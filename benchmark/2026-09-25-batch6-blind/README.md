# Batch 6: mechanical predictions

ConnectBot, GH4A, FitoTrack, Loop Habit Tracker, FreeOTP+, Just Player, Voice, Transistor,
Nextcloud Notes and LibreTorrent ([downloads.lock.json](downloads.lock.json)).

Provider: Westlake `corpus2-fixes` at `2b21e12`, framework 46 (native runtime opengl5, bionic shim
nw8).

## Predictions

[predictions.json](predictions.json), from `scripts/predict_first_screen.py` (now with the
engine-surface signal), committed before any launch:

- **Rule: 10 of 10 draw.**
- **Calibrated: about 8.** Batch 5's first-launch rate on the build before this one.

## Results

One launch per app on framework 46, SELinux enforcing, 35 s wait, a screenshot each. From this
batch on, the lifecycle scorer checks each screenshot against the host screen itself.

**9 of 10 drew on first launch**: ConnectBot, GH4A, FitoTrack, Loop Habit Tracker, FreeOTP+,
Voice, Transistor, Nextcloud Notes and LibreTorrent.

Just Player died on `libaudioeffect_jni.so`, the second app to do so after corpus 3's Fossify
Music Player, so the blocker had repeated. The runtime now ships that library with a
device-without-effects' answers (westlake `e2524b1`). On framework 47 both players draw:
**10 of 10**.

- **Rule: 9 of 10 right.** Calibrated forecast (about 8): one pessimistic.
- The map had this blocker's row (`jni:android.media.audiofx.AudioEffect`, from the
  framework-natives check), and the ledger had marked it since corpus 3. The predictor does not
  use class-init natives, because across the first 31 apps they flagged far more apps that drew
  than apps that were blocked.
