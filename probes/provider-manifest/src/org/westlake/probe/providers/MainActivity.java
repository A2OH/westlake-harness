package org.westlake.probe.providers;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

public final class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        TextView view = new TextView(this);
        view.setText("Provider manifest boundary\n\n" + ProbeApplication.result);
        view.setTextSize(18f);
        view.setPadding(32, 48, 32, 32);
        setContentView(view);
    }
}
