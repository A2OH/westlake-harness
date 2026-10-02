package org.westlake.probe.ndkassets;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

import java.io.InputStream;

/**
 * Does the NDK asset manager reach the APK's assets? React Native loads its JavaScript bundle
 * through AAssetManager (native) and fails with "Unable to load script" when that returns
 * nothing. The Java AssetManager is read first, as the control: a file it opens and the NDK
 * does not is an NDK-side gap. Every step prints a [WL-NDKASSET] line to stderr.
 */
public class MainActivity extends Activity {
    static {
        System.loadLibrary("ndkassets");
    }

    private static native void probe(Object assets);

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        String java;
        try (InputStream in = getAssets().open("probe.bundle")) {
            byte[] buffer = new byte[24];
            int n = in.read(buffer);
            java = "ok " + n + " bytes: " + new String(buffer, 0, Math.max(n, 0));
        } catch (Throwable t) {
            java = "FAILED " + t;
        }
        System.err.println("[WL-NDKASSET] java AssetManager.open(probe.bundle) " + java);
        probe(getAssets());
        TextView view = new TextView(this);
        view.setText("NDK assets probe: see [WL-NDKASSET] lines on stderr");
        setContentView(view);
    }
}
