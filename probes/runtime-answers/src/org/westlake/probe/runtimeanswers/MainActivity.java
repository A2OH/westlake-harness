package org.westlake.probe.runtimeanswers;

import android.app.Activity;
import android.app.ActivityManager;
import android.content.Context;
import android.net.TrafficStats;
import android.net.wifi.WifiManager;
import android.os.Bundle;
import android.os.Process;
import android.system.Os;
import android.telephony.PhoneStateListener;
import android.telephony.TelephonyManager;
import android.widget.TextView;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;

/**
 * Records, one line each, the answers commercial apps read at startup and that the top-apps blind
 * batch found wrong or refused on Westlake: thread priorities (Instagram, CapCut), service answers
 * (CNN's memory class, NYTimes' Wi-Fi info, Waze's telephony and TrafficStats), and file operations
 * in app storage (Meta's SoLoader, CapCut). Each line is "[WL-ANSWERS] <name> = <value>" with what
 * Android answers alongside, so the log alone says which differ.
 */
public class MainActivity extends Activity {
    private final StringBuilder shown = new StringBuilder();

    private void put(String name, Object value, String android) {
        String line = name + " = " + value + "   (Android: " + android + ")";
        System.err.println("[WL-ANSWERS] " + line);
        shown.append(line).append('\n');
    }

    private interface Check { Object run() throws Throwable; }

    private void check(String name, String android, Check check) {
        Object value;
        try {
            value = check.run();
        } catch (Throwable t) {
            value = "THROWS " + t;
        }
        put(name, value, android);
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        check("main thread priority", "5", () -> Thread.currentThread().getPriority());
        check("new thread priority", "same as creator", () -> new Thread().getPriority());
        check("Process.getThreadPriority(myTid)", "a nice value, e.g. 0 or -10",
                () -> Process.getThreadPriority(Process.myTid()));
        check("Thread.setPriority(current)", "no exception", () -> {
            Thread.currentThread().setPriority(Thread.currentThread().getPriority());
            return "ok";
        });
        check("ActivityManager.getMemoryClass", "> 0 (MB), e.g. 256",
                () -> ((ActivityManager) getSystemService(Context.ACTIVITY_SERVICE)).getMemoryClass());
        check("ActivityManager.getLargeMemoryClass", "> 0 (MB), e.g. 512",
                () -> ((ActivityManager) getSystemService(Context.ACTIVITY_SERVICE)).getLargeMemoryClass());
        check("Runtime.maxMemory", "> 0", () -> Runtime.getRuntime().maxMemory());
        check("WifiManager.getConnectionInfo", "non-null WifiInfo",
                () -> String.valueOf(((WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE))
                        .getConnectionInfo()));
        check("TrafficStats.getUidRxBytes(myUid)", ">= 0 or UNSUPPORTED (-1)",
                () -> TrafficStats.getUidRxBytes(Process.myUid()));
        check("TelephonyManager.listen", "no exception", () -> {
            ((TelephonyManager) getSystemService(Context.TELEPHONY_SERVICE))
                    .listen(new PhoneStateListener(), PhoneStateListener.LISTEN_NONE);
            return "ok";
        });
        File dir = new File(getFilesDir(), "probe-dir");
        dir.mkdirs();
        File file = new File(dir, "probe-file");
        check("File.setWritable(false) on a file", "true", () -> {
            new FileOutputStream(file).close();
            return file.setWritable(false);
        });
        check("File.setReadOnly on a file", "true", () -> file.setReadOnly());
        check("File.setWritable(true) back", "true", () -> file.setWritable(true));
        check("File.setWritable(false) on a directory", "true", () -> dir.setWritable(false));
        check("File.setWritable(true) on a directory", "true", () -> dir.setWritable(true));
        check("Os.chmod(file, 0400)", "ok", () -> { Os.chmod(file.getPath(), 0400); return "ok"; });
        check("Os.chmod(dir, 0500)", "ok", () -> { Os.chmod(dir.getPath(), 0500); return "ok"; });
        check("Os.chmod(dir, 0700)", "ok", () -> { Os.chmod(dir.getPath(), 0700); return "ok"; });
        check("System.load of a library copied to app storage", "loads", () -> {
            File lib = new File(getFilesDir(), "libcopied.so");
            try (ZipFile apk = new ZipFile(getApplicationInfo().sourceDir)) {
                ZipEntry entry = apk.getEntry("lib/arm64-v8a/libprobeanswers.so");
                if (entry == null) return "no library in the APK";
                try (InputStream in = apk.getInputStream(entry); FileOutputStream out = new FileOutputStream(lib)) {
                    byte[] b = new byte[65536];
                    for (int n; (n = in.read(b)) > 0; ) out.write(b, 0, n);
                }
            }
            lib.setReadOnly();
            System.load(lib.getPath());
            return "loaded";
        });
        TextView text = new TextView(this);
        text.setText(shown);
        setContentView(text);
    }
}
