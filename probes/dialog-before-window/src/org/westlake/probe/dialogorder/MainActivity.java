package org.westlake.probe.dialogorder;

import android.app.Activity;
import android.app.Dialog;
import android.graphics.Color;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.view.Window;
import android.view.WindowManager;
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
 */
public final class MainActivity extends Activity {
    private static final String TAG = "WL-DIALOG-ORDER";

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
        TextView body = new TextView(this);
        body.setText("DIALOG (red), shown from onCreate");
        body.setTextSize(28);
        body.setTextColor(Color.WHITE);
        body.setBackgroundColor(Color.rgb(0xd0, 0x21, 0x2a));
        body.setGravity(Gravity.CENTER);
        body.setPadding(60, 200, 60, 200);
        dialog.setContentView(body);
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
    }
}
