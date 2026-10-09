package org.westlake.probe.dialogorder;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Dialog;
import android.graphics.Color;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.Window;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.TextView;

/**
 * A dialog shown from onCreate, before the activity's own window exists.
 *
 * WindowManagerService stacks an activity's dialogs above its base window whatever order they
 * were added in, so on Android the screen shows the red dialog over the green activity. A window
 * system that stacks in creation order shows only green: the base window is added after the
 * dialog, in handleResumeActivity, and covers it. McDonald's sign-in sheet is such a dialog.
 *
 * The app cannot see the stacking itself; the oracle is the screen (red over green) or the
 * platform's window list. The log line records the order the windows were added in.
 *
 * Two more contracts ride on the same dialog: WMS centres it (its window's screen position is
 * logged and checked), and a touch on its button must reach the dialog in the dialog's own
 * coordinates ("dialog button clicked" is logged). The dim behind it is visible on screen only.
 *
 * For the per-build conformance run it also prints one line per gap-map row it measures, then
 * "[WL-CONTRACT] done": wm:window-placement (both dialogs centred and on screen) and
 * wm:dialog-stacking (the runner's tap at the button's logged position reaches the dialog, so the
 * dialog is above its activity; no tap within 20 s fails it). wm:dim-behind has no line.
 */
public final class MainActivity extends Activity implements View.OnClickListener, Runnable {
    private static final String TAG = "WL-DIALOG-ORDER";
    private View dialogDecor;
    private View alertDecor;
    private AlertDialog alertDialog;
    private View button;
    private String placement;
    private boolean placed;
    private boolean stackingDecided;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        TextView content = new TextView(this);
        content.setText("ACTIVITY (green). A red dialog should cover the middle of the screen.");
        content.setTextSize(22);
        content.setTextColor(Color.BLACK);
        content.setBackgroundColor(Color.rgb(0x2e, 0xb8, 0x4f));
        content.setGravity(Gravity.CENTER_HORIZONTAL);
        content.setPadding(40, 120, 40, 40);
        setContentView(content);

        Dialog dialog = new Dialog(this);
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setGravity(Gravity.CENTER);
        panel.setBackgroundColor(Color.rgb(0xd0, 0x21, 0x2a));
        panel.setPadding(60, 120, 60, 120);
        TextView body = new TextView(this);
        body.setText("DIALOG (red), shown from onCreate");
        body.setTextSize(28);
        body.setTextColor(Color.WHITE);
        body.setGravity(Gravity.CENTER);
        panel.addView(body);
        Button button = new Button(this);
        this.button = button;
        button.setText("TAP ME");
        button.setOnClickListener(this);
        panel.addView(button);
        dialog.setContentView(panel);
        dialog.setCancelable(false);
        dialog.show();
        boolean decorAttached = getWindow().getDecorView().isAttachedToWindow();
        String result = "phase=onCreate dialogShowing=" + dialog.isShowing()
                + " activityWindowAddedYet=" + decorAttached
                + " expected=RED_DIALOG_OVER_GREEN_ACTIVITY";
        Log.i(TAG, result);
        System.err.println("[" + TAG + "] " + result);
        WindowManager.LayoutParams lp = dialog.getWindow().getAttributes();
        System.err.println("[" + TAG + "] dialogType=" + lp.type + " activityType="
                + getWindow().getAttributes().type);
        dialogDecor = dialog.getWindow().getDecorView();
        dialogDecor.postDelayed(this, 1500);
    }

    @Override
    public void onClick(View v) {
        report("dialog button clicked");
        stacking(true, "the tap at the button's logged position reached the dialog's button");
    }

    private synchronized void stacking(boolean passed, String detail) {
        if (stackingDecided) return;
        stackingDecided = true;
        contract("wm:dialog-stacking", passed ? "PASS" : "FAIL", detail);
        contract("done", "", "");
    }

    private static void contract(String row, String outcome, String detail) {
        String text = "[WL-CONTRACT] " + row + " " + outcome + " " + detail;
        Log.i("WL-CONTRACT", text);
        System.err.println(text);
    }

    @Override
    public void run() {
        int[] loc = new int[2];
        dialogDecor.getLocationOnScreen(loc);
        int screen = getResources().getDisplayMetrics().widthPixels;
        int expected = (screen - dialogDecor.getWidth()) / 2;
        boolean centred = Math.abs(loc[0] - expected) <= 2 && loc[1] > 0;
        report("placement=" + (centred ? "CENTRED" : "NOT_CENTRED") + " at " + loc[0] + ","
                + loc[1] + " size=" + dialogDecor.getWidth() + "x" + dialogDecor.getHeight()
                + " screenWidth=" + screen);
        // A window wider than the display puts its buttons where no finger can reach them:
        // McDonald's upgrade dialog landed off the right edge on some launches and could not be
        // dismissed at all. Centred is not enough; it has to fit.
        boolean fits = loc[0] >= 0 && loc[0] + dialogDecor.getWidth() <= screen;
        report("width=" + (fits ? "FITS" : "OVERFLOWS") + " right=" + (loc[0] + dialogDecor.getWidth())
                + " screenWidth=" + screen);
        if (placement == null) {
            placed = centred && fits;
            placement = "dialog at " + loc[0] + "," + loc[1] + " size " + dialogDecor.getWidth() + "x"
                    + dialogDecor.getHeight() + " on a " + screen + " px screen (centred x=" + expected + ")";
        }
        if (alertDecor == null) {
            // The shape that actually broke: a stock AlertDialog whose message is long enough that
            // its preferred width exceeds the display. McDonald's upgrade dialog came out 1282 px
            // wide on a 1200 px screen and put its OK button where no finger could reach it.
            AlertDialog alert = new AlertDialog.Builder(this)
                    .setTitle("Upgrade")
                    .setMessage("We've been doing some work behind the scenes and are excited to show you the"
                            + " latest. Please update to the latest version of the app for an upgraded"
                            + " experience, with more of everything you already like about it.")
                    .setPositiveButton("OK", null)
                    .create();
            alert.show();
            alertDialog = alert;
            alertDecor = alert.getWindow().getDecorView();
            alertDecor.postDelayed(this, 1200);
            return;
        }
        int[] alertAt = new int[2];
        alertDecor.getLocationOnScreen(alertAt);
        boolean alertFits = alertAt[0] >= 0 && alertAt[0] + alertDecor.getWidth() <= screen;
        report("alertWidth=" + (alertFits ? "FITS" : "OVERFLOWS") + " at " + alertAt[0]
                + " right=" + (alertAt[0] + alertDecor.getWidth()) + " screenWidth=" + screen);
        contract("wm:window-placement", placed && alertFits ? "PASS" : "FAIL", placement
                + "; the alert at " + alertAt[0] + " to " + (alertAt[0] + alertDecor.getWidth()));
        // The alert has been measured; dismissed, it cannot take the tap meant for the dialog.
        alertDialog.dismiss();
        dialogDecor.postDelayed(() -> stacking(false,
                "no tap reached the dialog's button within 20 s of its position being logged"), 20000);
        // Where a tap must land to press the button: a runner delivering screen coordinates reads
        // it here instead of assuming a layout. Reported once the alert has been measured, so the
        // runner taps the probe's own button rather than the alert on top of it.
        int[] at = new int[2];
        button.getLocationOnScreen(at);
        report("button center=" + (at[0] + button.getWidth() / 2) + "," + (at[1] + button.getHeight() / 2));
    }

    private static void report(String result) {
        Log.i(TAG, result);
        System.err.println("[" + TAG + "] " + result);
    }
}
