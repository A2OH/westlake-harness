# Batch 4: mechanical predictions

Ten more F-Droid apps: Material Files, Mastodon, LibreTube, Etar, Fossify Calendar, App Manager,
Conversations, KDE Connect, Shattered Pixel Dungeon and Tasks.org. Each download's sha256 was
checked against the F-Droid index ([downloads.lock.json](downloads.lock.json)).

Provider: Westlake `corpus2-fixes` at `1c883ad`, framework 43 (native runtime opengl4, bionic shim
nw8). The maps use the build-43 runtime index and the blockers ledger.

## How the predictions were made

No hand judgment this time. `scripts/predict_first_screen.py` applies one fixed rule to each map:
an app is predicted blocked when it has an unresolved native import, a framework-side null throw,
or a run-time lookup of an NDK library the runtime does not supply. The signals were chosen by how
well each one separated drawing from blocked apps among the 31 already launched (in-sample
accuracy 0.81, precision 0.83, recall 0.50; see the script's docstring).

## Predictions

[predictions.json](predictions.json), committed before any launch:

- **Rule: 9 of 10 draw.** Only App Manager is flagged, for an unresolved bionic libc import.
- **Calibrated: 2 to 4 draw.** On first launch, fresh apps drew 4 of 20 in corpora 2 and 3. Their
  blockers were mostly one missing Android behaviour each, which the rule cannot see. So the rule's
  "draws" means "no known blocker", not "will draw".

## Results

Not yet run.
