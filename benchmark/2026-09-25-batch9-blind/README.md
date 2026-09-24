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

One launch per app on framework 53. **3 of 10 drew on first launch**: PipePipe, RedReader and
OpenKeychain. After fixes (framework 56, westlake `6c300b3`), Nextcloud Talk and mpv drew too:
**5 of 10**.

| App | Rule | Outcome | Blocker |
|---|---|---|---|
| Element X | draws | **blocked** | native SIGSEGV at a garbage address (open) |
| Nextcloud Talk | draws | **blocked**, then draws | `KeyguardManager` null: its constructor needs the `trust` service (fixed) |
| mpv | blocked | **blocked**, then draws | the AppCompat theme rejection (fixed; see below) |
| SuperTuxKart | blocked | **blocked** | its SDL engine needs `libGLESv1_CM.so`, which OH does not ship; it shows its own error dialog |
| DuckDuckGo | draws | **blocked** | `java.time`: no time-zone rules registered (open) |
| PipePipe | blocked | draws | the flagged libmediandk lookup is not reached at startup |
| StreetComplete | draws | **blocked** | native SIGABRT (open) |
| Briar | blocked | **blocked** | `ProcessEnvironment.environ` unbound (fixed), then "already has an action bar supplied by the window decor" (open) |

- **Rule: 5 of 10 right.**
- **The theme gap is found, and worked around.** The four AppCompat rejections (Seal, FFUpdater,
  Jami, mpv) had one thing in common: no application theme in the manifest. Every app that
  declares one was fine. Giving the activity's `ApplicationInfo` the activity's theme made all
  four draw, so some step of the launch path styles the activity from the application's theme.
  The exact step is not yet located. Seal now draws its own error screen: its bundled Python
  cannot create a symlink, the OH app-data policy wall Termux met.
