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

One launch per app on framework 43, SELinux enforcing, 35 s wait, a screenshot each.

**7 of 10 drew on first launch**: Material Files, Mastodon, Etar, Fossify Calendar, App Manager
(its keystore dialog over the splash), Conversations and KDE Connect. After two fixes (framework
45), Tasks.org drew too: **8 of 10**.

| # | App | Rule said | Outcome | Blocker |
|---|---|---|---|---|
| 1 | Material Files | draws | draws | — |
| 2 | Mastodon | draws | draws | — |
| 3 | LibreTube | draws | **blocked** | no storage device for its own data path (fixed), then a Coil disk cache of size 0 (open) |
| 4 | Etar | draws | draws | — |
| 5 | Fossify Calendar | draws | draws | — |
| 6 | App Manager | **blocked** (libc import) | draws | the flagged import is not reached at startup |
| 7 | Conversations | draws | draws | — |
| 8 | KDE Connect | draws | draws | — |
| 9 | Shattered Pixel Dungeon | draws | **blocked** | libGDX's GL surface: likely the shared SurfaceView window |
| 10 | Tasks.org | draws | **blocked**, then draws | my `getNanoTimeAdjustment` binding used the wrong calling convention |

The rule was right for 6 of 10. The calibrated forecast (2 to 4) was far too pessimistic: its base
rate came from corpora 2 and 3, before the fixes those corpora produced. **The fixes carried over
to new apps.** Fresh apps went from 2 of 10 drawing on first launch to 7 of 10, on a build that
had been changed only for other apps.

What the harness learns from this batch:

- **The base rate moves with the provider.** A calibrated forecast needs the recent first-launch
  rate, not the historical one.
- **A misapplied fix is a gap of its own.** Tasks.org died on my own binding of a
  `@CriticalNative` method. The framework-natives check should compare a binding's calling
  convention with the method's annotation, not only whether a binding exists.
