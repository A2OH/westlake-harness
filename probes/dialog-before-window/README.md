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

McDonald's sign-in bottom sheet is this case. The same dialog carries two more contracts: WMS
centres it (`placement=CENTRED at x,y` is logged), and a tap delivered at screen coordinates must
reach its button in the dialog's own coordinates (`button center=x,y` tells a runner where to tap;
`dialog button clicked` confirms it). A tap can only press the button if the dialog is the topmost
window under it, so the click also confirms the stacking. Build with `./build.sh`.

## 2026-09-22 result

On the OpenHarmony board (Westlake `f4e0366`): only the green activity is visible. The board's
window list has the activity's window, created second, on top. See
`benchmark/2026-09-22-mcdonalds-signin/`.

With Westlake `5df440b`, which holds a dialog's OpenHarmony session back until its activity's window
has one, the red dialog shows above the green activity. It sits at the top-left rather than centred:
the window adapter lays every window out at (0,0) (`wm:window-placement`), and nothing is dimmed
behind it (`wm:dim-behind`).
