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

One launch per app on framework 56. **7 of 10 drew on first launch**: Fossify Contacts, Phone and
Camera (its controls over a black preview; the Camera natives are absent), ICSx5, OpenTracks, Xtra
and Translate You.

| App | Rule | Outcome | Blocker |
|---|---|---|---|
| Editor | draws | **blocked** | switches on the launch intent's action, which direct launch left null. A launcher sends `ACTION_MAIN` in `CATEGORY_LAUNCHER` |
| Fossify Voice Recorder | draws | **blocked** | `IUriGrantsManager` null behind `ContentResolver.getPersistedUriPermissions` (Voice logged the same in batch 6) |
| AdAway | blocked | **blocked** | "already has an action bar supplied by the window decor", as Briar: an action-bar application theme wins over a NoActionBar activity theme |

- **Rule: 7 of 10 right.** Calibrated forecast (5 to 6): one pessimistic.
- All three blockers are fixed in framework 57, which also changes every app's launch intent and
  the theme of every activity that declares one. The results after that build, with a broad
  regression, are in the loop summary.
