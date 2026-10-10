package org.westlake.probe.contracts;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;

/** Started for a result by the am:activity-result check: answers 42 and finishes. */
public class ResultActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        setResult(RESULT_OK, new Intent().putExtra("answer", 42));
        finish();
    }
}
