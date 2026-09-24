# Batch 10: mechanical predictions

Fossify Contacts, Phone, Camera and Voice Recorder, ICSx5, Editor, OpenTracks, Xtra, Translate You
and AdAway ([downloads.lock.json](downloads.lock.json)). This batch takes the loop past 100 apps.

Provider: Westlake `corpus2-fixes` at `6c300b3`, framework 56 (native runtime opengl7, bionic
shim nw8).

## Predictions

[predictions.json](predictions.json), committed before any launch:

- **Rule: 9 of 10 draw.** AdAway is flagged, for a bionic libc import.
- **Calibrated: about 5 to 6.** Batches 8 and 9 drew 4 and 3 on first launch, before their fixes.
  The theme fix since then covers a whole class of apps. Fossify Camera and Phone touch hardware
  this board lacks or Westlake does not bridge (the Camera natives, telephony).

## Results

Not yet run.
