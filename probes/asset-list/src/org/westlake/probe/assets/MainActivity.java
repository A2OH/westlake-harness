package org.westlake.probe.assets;

import android.app.Activity;
import android.content.res.AssetManager;
import android.os.Bundle;
import android.widget.TextView;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.util.Arrays;
import java.util.List;

/**
 * Can an app find its own asset files by listing, not only by opening?
 *
 * McDonald's reads every configuration file this way: it calls getAssets().list("") and reads a
 * file only if the listing contains its name. With an empty listing the app loads no
 * configuration at all, its bottom navigation menu stays empty, and each screen that asks the menu
 * for an item dereferences null. An open() that works is not enough; the listing is the contract.
 */
public final class MainActivity extends Activity {
    private static final String TAG = "[WL-ASSET-LIST] ";
    private static final String ROOT_ASSET = "server_config.json";
    private static final String SUBDIRECTORY = "nested";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        String verdict = run();
        System.err.println(TAG + verdict);
        System.err.flush();
        TextView view = new TextView(this);
        view.setText("Asset listing boundary\n\n" + verdict);
        view.setTextSize(18f);
        view.setPadding(32, 48, 32, 32);
        setContentView(view);
    }

    private String run() {
        AssetManager assets = getAssets();
        String[] root;
        try {
            root = assets.list("");
        } catch (Exception e) {
            return "verdict=FAIL_LIST_THREW " + e;
        }
        if (root == null || root.length == 0) {
            return "verdict=FAIL_LIST_EMPTY root=" + (root == null ? "null" : "0 entries");
        }
        List<String> names = Arrays.asList(root);
        System.err.println(TAG + "root entries=" + root.length + " " + names);
        if (!names.contains(ROOT_ASSET)) {
            return "verdict=FAIL_LIST_MISSING_FILE looked for " + ROOT_ASSET + " in " + names;
        }
        String[] nested;
        try {
            nested = assets.list(SUBDIRECTORY);
        } catch (Exception e) {
            return "verdict=FAIL_SUBDIR_THREW " + e;
        }
        if (nested == null || nested.length == 0) {
            return "verdict=FAIL_SUBDIR_EMPTY " + SUBDIRECTORY;
        }
        String content;
        try (InputStream stream = assets.open(ROOT_ASSET)) {
            ByteArrayOutputStream buffer = new ByteArrayOutputStream();
            byte[] chunk = new byte[4096];
            for (int read = stream.read(chunk); read > 0; read = stream.read(chunk)) {
                buffer.write(chunk, 0, read);
            }
            content = buffer.toString("UTF-8").trim();
        } catch (Exception e) {
            return "verdict=FAIL_OPEN_THREW " + e;
        }
        if (!content.contains("tabCount")) {
            return "verdict=FAIL_CONTENT content=" + content;
        }
        return "verdict=PASS_ASSETS_LISTED root=" + root.length + " nested=" + nested.length
                + " bytes=" + content.length();
    }
}
