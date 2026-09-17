package org.westlake.probe.defaultinterface;

import android.app.Application;

public final class ProbeApplication extends Application {
    static volatile String applicationVerdict = "NOT_RUN";

    @Override
    public void onCreate() {
        super.onCreate();
        applicationVerdict = DispatchProbe.run("application");
    }
}
