package org.westlake.probe.contracts;

import android.app.Activity;
import android.app.AlertDialog;
import android.os.Bundle;
import android.view.WindowInsets;
import android.view.WindowManager;
import android.view.inputmethod.InputMethodManager;
import android.widget.EditText;

import java.util.concurrent.CountDownLatch;

/**
 * Started by the svc:input_method and wm:focus-handoff checks.
 *
 * Its one EditText takes focus once the window has it and asks for the soft keyboard. On Android the
 * input method manager serves the focused editor, the keyboard comes up, and the window's insets
 * report it (WindowInsets.Type.ime()), which is how an app sees it and how adjustResize makes room.
 *
 * Then it shows a dialog and closes it. WMS gives the dialog window focus and, when the dialog goes,
 * gives it back to the activity's window. The input method manager serves only the focused
 * window's editor: an editor under a closed dialog that never gets focus back never gets a keyboard.
 */
public class KeyboardActivity extends Activity implements Runnable {
    static final CountDownLatch KEYBOARD = new CountDownLatch(1);
    static volatile boolean keyboardPassed;
    static volatile String keyboardDetail = "the activity's window never got focus";
    static final CountDownLatch HANDOFF = new CountDownLatch(1);
    static volatile boolean handoffPassed;
    static volatile String handoffDetail = "the keyboard check did not finish";

    private EditText field;
    private InputMethodManager imm;
    private boolean asked;
    private int polls;
    private AlertDialog dialog;
    private boolean lostToDialog;
    private boolean regained;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_STATE_ALWAYS_VISIBLE
                | WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        field = new EditText(this);
        field.setHint("the soft keyboard types here");
        setContentView(field);
        imm = getSystemService(InputMethodManager.class);
    }

    @Override
    public void onWindowFocusChanged(boolean hasFocus) {
        super.onWindowFocusChanged(hasFocus);
        if (dialog != null) {
            if (!hasFocus && dialog.isShowing()) lostToDialog = true;
            if (hasFocus && !dialog.isShowing()) regained = true;
            return;
        }
        if (!hasFocus || polls > 0) return;
        polls = 1;
        field.requestFocus();
        asked = imm.showSoftInput(field, 0);
        field.postDelayed(this, 500);
    }

    @Override
    public void run() {
        WindowInsets insets = field.getRootWindowInsets();
        boolean shown = insets != null && insets.isVisible(WindowInsets.Type.ime());
        int height = insets == null ? 0 : insets.getInsets(WindowInsets.Type.ime()).bottom;
        boolean served = imm.isActive(field);
        if (shown && height > 0) {
            keyboard(true, "served, the keyboard shown: ime insets " + height + " px");
        } else if (polls++ < 12) {
            field.postDelayed(this, 500);
        } else {
            keyboard(false, "showSoftInput=" + asked + " served=" + served + " imeVisible=" + shown
                    + " imeInsets=" + height + " after 6 s"
                    + (served ? "" : "; Android serves the focused editor of the focused window"));
        }
    }

    private void keyboard(boolean ok, String text) {
        keyboardPassed = ok;
        keyboardDetail = text;
        KEYBOARD.countDown();
        dialog = new AlertDialog.Builder(this).setMessage("A dialog over the editor, closed in 1.5 s").create();
        dialog.show();
        field.postDelayed(() -> {
            dialog.dismiss();
            field.postDelayed(this::handoff, 3000);
        }, 1500);
    }

    private void handoff() {
        boolean focused = hasWindowFocus();
        handoffPassed = lostToDialog && regained && focused;
        handoffDetail = "the dialog " + (lostToDialog ? "took" : "did not take") + " window focus; after it closed the"
                + " activity's window " + (regained ? "got it back" : "never got it back")
                + " (hasWindowFocus=" + focused + " 3 s later)";
        HANDOFF.countDown();
    }
}
