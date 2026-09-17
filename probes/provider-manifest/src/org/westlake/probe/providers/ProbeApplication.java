package org.westlake.probe.providers;

import android.app.Application;
import android.util.Log;

public final class ProbeApplication extends Application {
    static volatile String result = "application=not-run";

    @Override
    public void onCreate() {
        super.onCreate();
        boolean pass = ProbeState.mainProviderCreates == 1
                && ProbeState.remoteProviderCreates == 0;
        result = "verdict=" + (pass ? "PASS_QUERY_EXCLUDED_REMOTE_FILTERED" : "FAIL")
                + " mainProviderCreates=" + ProbeState.mainProviderCreates
                + " remoteProviderCreates=" + ProbeState.remoteProviderCreates;
        Log.i("WL-PROVIDER-PROBE", result);
        System.err.println("[WL-PROVIDER-PROBE] " + result);
    }
}
