package org.westlake.probe.contracts;

import android.app.Activity;
import android.os.Bundle;

import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.CountDownLatch;

/**
 * Started by the am:launch-lifecycle check, which reads the callbacks it got: Android creates, starts
 * and resumes an activity an app starts, and pauses it only when something covers it or it finishes.
 */
public class LifecycleActivity extends Activity {
    private static final List<String> CALLS = new ArrayList<>();
    static final CountDownLatch RESUMED = new CountDownLatch(1);
    static final CountDownLatch DESTROYED = new CountDownLatch(1);
    static volatile LifecycleActivity current;

    private static void record(String call) {
        synchronized (CALLS) {
            CALLS.add(call);
        }
    }

    static String seen() {
        synchronized (CALLS) {
            return String.join(" ", CALLS);
        }
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        current = this;
        record("onCreate");
    }

    @Override
    protected void onStart() {
        super.onStart();
        record("onStart");
    }

    @Override
    protected void onResume() {
        super.onResume();
        record("onResume");
        RESUMED.countDown();
    }

    @Override
    protected void onPause() {
        record("onPause");
        super.onPause();
    }

    @Override
    protected void onStop() {
        record("onStop");
        super.onStop();
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        DESTROYED.countDown();
    }
}
