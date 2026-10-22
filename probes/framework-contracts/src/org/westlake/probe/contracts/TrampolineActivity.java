package org.westlake.probe.contracts;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;

import java.util.concurrent.CountDownLatch;

/**
 * Started by the am:activity-result check: starts ResultActivity for a result and finishes itself at
 * once, as a launcher trampoline does. A caller that has finished gets no result, and the app goes on.
 */
public class TrampolineActivity extends Activity {
    static final CountDownLatch DESTROYED = new CountDownLatch(1);
    static volatile boolean resultSeen;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        startActivityForResult(new Intent(this, ResultActivity.class), 9);
        finish();
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        resultSeen = true;
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        DESTROYED.countDown();
    }
}
