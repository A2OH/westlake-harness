package org.westlake.probe.runningprocesses;

import android.app.ActivityManager;
import android.app.Application;
import android.content.Context;
import android.os.Process;
import android.util.Log;

import java.util.List;

public final class ProbeApplication extends Application {
    static volatile String applicationResult = "application=not-run";

    @Override
    public void onCreate() {
        super.onCreate();
        applicationResult = probe(this, "application");
    }

    static String probe(Context context, String phase) {
        ActivityManager manager =
                (ActivityManager) context.getSystemService(Context.ACTIVITY_SERVICE);
        List<ActivityManager.RunningAppProcessInfo> processes =
                manager == null ? null : manager.getRunningAppProcesses();

        int myPid = Process.myPid();
        int myUid = Process.myUid();
        String myProcess = context.getPackageName();
        boolean pidSeen = false;
        boolean nameSeen = false;
        boolean uidSeen = false;
        int count = processes == null ? -1 : processes.size();
        if (processes != null) {
            for (ActivityManager.RunningAppProcessInfo process : processes) {
                if (process == null) {
                    continue;
                }
                pidSeen |= process.pid == myPid;
                uidSeen |= process.uid == myUid;
                nameSeen |= myProcess.equals(process.processName);
            }
        }

        String verdict = processes == null
                ? "FAIL_NULL"
                : (pidSeen && nameSeen ? "PASS_SELF_VISIBLE" : "FAIL_SELF_MISSING");
        String result = "phase=" + phase
                + " verdict=" + verdict
                + " manager=" + (manager != null)
                + " listNull=" + (processes == null)
                + " count=" + count
                + " myPid=" + myPid
                + " myUid=" + myUid
                + " pidSeen=" + pidSeen
                + " uidSeen=" + uidSeen
                + " nameSeen=" + nameSeen;
        Log.i("WL-RUNNING-PROCS", result);
        System.err.println("[WL-RUNNING-PROCS] " + result);
        return result;
    }
}
