package org.westlake.probe.contracts;

import android.app.Activity;
import android.os.Bundle;

import java.util.concurrent.CountDownLatch;

/**
 * Started by the am:recreate check. Its first instance calls recreate() once resumed, as an app does
 * to apply a new theme or language: Android destroys it and brings a new instance up in its place,
 * with the state the first one saved.
 */
public class RecreateActivity extends Activity {
    private static final String SAVED = "probe-saved";
    static final CountDownLatch SECOND = new CountDownLatch(1);
    static final CountDownLatch FINISHED = new CountDownLatch(1);
    static volatile int instances;
    static volatile int savedSeen = -1;
    static volatile RecreateActivity current;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        current = this;
        instances++;
        if (instances == 2) {
            savedSeen = state != null ? state.getInt(SAVED, -1) : -1;
            SECOND.countDown();
        }
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (instances == 1) getWindow().getDecorView().post(this::recreate);
    }

    @Override
    protected void onSaveInstanceState(Bundle out) {
        super.onSaveInstanceState(out);
        out.putInt(SAVED, 42);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (isFinishing()) FINISHED.countDown();
    }
}
