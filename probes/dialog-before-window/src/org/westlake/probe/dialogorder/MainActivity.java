package org.westlake.probe.dialogorder;

import android.app.Activity;
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
 */
public final class MainActivity extends Activity implements View.OnClickListener, Runnable {
    private static final String TAG = "WL-DIALOG-ORDER";
    private View dialogDecor;

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
    }

    private static void report(String result) {
        Log.i(TAG, result);
        System.err.println("[" + TAG + "] " + result);
    }
}
