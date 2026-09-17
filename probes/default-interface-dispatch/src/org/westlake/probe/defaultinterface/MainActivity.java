package org.westlake.probe.defaultinterface;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.TextView;

public final class MainActivity extends Activity {
    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        String activityVerdict = DispatchProbe.run("activity");
        boolean pass = ProbeApplication.applicationVerdict.contains("PASS_")
                && activityVerdict.contains("PASS_");
        TextView view = new TextView(this);
        view.setGravity(Gravity.CENTER);
        view.setTextSize(22f);
        view.setTextColor(Color.WHITE);
        view.setBackgroundColor(pass ? Color.rgb(0, 110, 45) : Color.rgb(150, 0, 0));
        view.setText((pass ? "PASS" : "FAIL") + "\nDefault interface dispatch\n\n"
                + ProbeApplication.applicationVerdict + "\n\n" + activityVerdict);
        setContentView(view);
    }
}
