# Dialog-before-window white-box probe

An activity shows a dialog from `onCreate`, before its own window exists. WindowManagerService
stacks an activity's dialogs above its base window whatever order they were added in, so Android
shows the red dialog over the green activity. A window system that stacks by creation order shows
only green: the base window is added later, in `handleResumeActivity`, and covers the dialog.

The app cannot see the stacking, so the oracle is the screen (red over green) or the platform's
window list. The log line records the order:

```text
[WL-DIALOG-ORDER] phase=onCreate dialogShowing=true activityWindowAddedYet=false expected=RED_DIALOG_OVER_GREEN_ACTIVITY
```

McDonald's sign-in bottom sheet is this case. Build with `./build.sh`.

## 2026-09-22 result

On the OpenHarmony board (Westlake `f4e0366`): only the green activity is visible. The board's
window list has the activity's window, created second, on top. See
`benchmark/2026-09-22-mcdonalds-signin/`.
