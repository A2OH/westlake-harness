package org.westlake.probe.runningprocesses;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

public final class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        String activityResult = ProbeApplication.probe(this, "activity");
        TextView view = new TextView(this);
        view.setText("ActivityManager.getRunningAppProcesses()\n\n"
                + ProbeApplication.applicationResult + "\n\n" + activityResult);
        view.setTextSize(18f);
        view.setPadding(32, 48, 32, 32);
        setContentView(view);
    }
}
