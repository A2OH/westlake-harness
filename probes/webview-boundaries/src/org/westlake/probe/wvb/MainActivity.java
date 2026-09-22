package org.westlake.probe.wvb;

import android.app.Activity;
import android.content.Context;
import android.content.res.Configuration;
import android.os.Bundle;
import android.view.Display;
import android.widget.TextView;

import java.io.File;
import java.lang.reflect.Method;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * The three boundaries that decide whether an app can open a WebView screen.
 *
 * Each was reached by driving Wikipedia to an article on 2026-09-22, and each killed the process
 * in a way no static check could see. They are measured here rather than inferred, because all
 * three answers are properties of the runtime and the launch, not of the app: a build that
 * changes any of them changes them for every app at once.
 *
 *   1. the multiprocess decision. WebViewDelegate.isMultiProcessEnabled() short-circuits on a
 *      compiled-in flag before it ever asks IWebViewUpdateService. With the flag true, Chromium
 *      takes the multiprocess path and dies resolving sandboxed child services that the provider
 *      manifest does not declare here. The adapter's own answer is never consulted, so reporting
 *      the service's answer alone would say the opposite of what happens.
 *
 *   2. same-named libraries on the search path. Chromium reaches the NDK SurfaceControl surface
 *      with dlopen("libandroid.so") plus dlsym, and gets whichever copy the search path names
 *      first. Two ship, and only one exports that surface. Nothing in a symbol table shows this:
 *      the files have the same name and the choice is made at runtime by search order.
 *
 *   3. the window context. Chromium asks for one while its browser process starts. An adapter
 *      that throws here is fatal rather than degrading, because every JNI return path runs
 *      CheckException: a pending Java exception below native code aborts the process.
 */
public final class MainActivity extends Activity {
    private static final String TAG = "[WL-WVB] ";

    /** Libraries whose name appearing twice on the search path has already cost a debugging day. */
    private static final String[] WATCHED = {"libandroid.so", "libjnigraphics.so", "libc++_shared.so"};

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        List<String> report = new ArrayList<>();
        report.add(multiprocess());
        report.add(searchPath());
        report.add(windowContext());
        for (String line : report) {
            System.err.println(TAG + line);
        }
        System.err.flush();
        TextView view = new TextView(this);
        view.setText("WebView boundaries\n\n" + String.join("\n\n", report));
        view.setTextSize(14f);
        view.setPadding(32, 48, 32, 32);
        setContentView(view);
    }

    // ---- 1. the multiprocess decision -------------------------------------------------------

    /**
     * Reports the answer the delegate would give, and where it comes from.
     *
     * The flag is read first because that is the order the delegate reads it in: when it is true
     * the service is never asked, so a service answering false does not make WebView
     * single-process. Both are reported so a wrong build is visible as a disagreement rather than
     * as one number.
     */
    private String multiprocess() {
        String flag = booleanByName("android.webkit.Flags", "updateServiceV2");
        String wrapper = booleanByName("android.webkit.Flags", "updateServiceIpcWrapper");
        String service = "unreached";
        try {
            Class<?> factory = Class.forName("android.webkit.WebViewFactory");
            Method get = factory.getDeclaredMethod("getUpdateService");
            get.setAccessible(true);
            Object updateService = get.invoke(null);
            if (updateService == null) {
                service = "null";
            } else {
                Method enabled = updateService.getClass().getMethod("isMultiProcessEnabled");
                enabled.setAccessible(true);
                service = String.valueOf(enabled.invoke(updateService));
            }
        } catch (Throwable t) {
            service = "threw:" + t.getClass().getSimpleName();
        }
        // The delegate returns true on either flag without asking; only otherwise does the
        // service's answer reach Chromium.
        String effective;
        if ("true".equals(flag) || "true".equals(wrapper)) {
            effective = "true";
        } else if ("true".equals(service) || "false".equals(service)) {
            effective = service;
        } else {
            effective = "unknown";
        }
        String verdict = "true".equals(effective) ? "FAIL_MULTIPROCESS"
                : "false".equals(effective) ? "PASS_SINGLE_PROCESS" : "FAIL_UNDECIDABLE";
        return "phase=multiprocess verdict=" + verdict + " effective=" + effective
                + " flagV2=" + flag + " flagWrapper=" + wrapper + " service=" + service;
    }

    private static String booleanByName(String className, String method) {
        try {
            Method m = Class.forName(className).getDeclaredMethod(method);
            m.setAccessible(true);
            return String.valueOf(m.invoke(null));
        } catch (Throwable t) {
            return "threw:" + t.getClass().getSimpleName();
        }
    }

    // ---- 2. same-named libraries on the search path -----------------------------------------

    /**
     * Walks the library search path the way the loader does and reports every directory holding
     * each watched name, in order. The first is what dlopen returns; any later one is shadowed,
     * and an app or engine that needs the later copy's symbols will not find them.
     */
    private String searchPath() {
        String raw = System.getenv("LD_LIBRARY_PATH");
        if (raw == null || raw.isEmpty()) {
            return "phase=searchpath verdict=FAIL_NO_PATH";
        }
        String[] directories = raw.split(":");
        Map<String, List<String>> found = new LinkedHashMap<>();
        for (String name : WATCHED) {
            List<String> hits = new ArrayList<>();
            for (String directory : directories) {
                if (directory.isEmpty()) {
                    continue;
                }
                if (new File(directory, name).isFile()) {
                    hits.add(directory);
                }
            }
            if (!hits.isEmpty()) {
                found.put(name, hits);
            }
        }
        StringBuilder detail = new StringBuilder();
        int shadowed = 0;
        for (Map.Entry<String, List<String>> entry : found.entrySet()) {
            List<String> hits = entry.getValue();
            if (hits.size() > 1) {
                shadowed++;
                detail.append(' ').append(entry.getKey()).append("=[first:").append(hits.get(0))
                        .append(" shadowed:").append(String.join(",", hits.subList(1, hits.size())))
                        .append(']');
            } else {
                detail.append(' ').append(entry.getKey()).append("=[only:").append(hits.get(0)).append(']');
            }
        }
        // Not a failure on its own: shadowing only bites when the later copy is the one with the
        // symbols the caller wants. Reported so the map can name the pair rather than guess.
        return "phase=searchpath verdict=" + (shadowed == 0 ? "PASS_NO_SHADOWING" : "OBSERVED_SHADOWING")
                + " dirs=" + directories.length + " shadowed=" + shadowed + detail;
    }

    // ---- 3. the window context ---------------------------------------------------------------

    /**
     * Asks for a window context the way Chromium's display manager does, and reports whether it
     * answers, what it answers with, and whether it is connected.
     *
     * The answer is the measurement: a throw here aborts the process, a null degrades it, and a
     * Configuration without width or density is a third outcome the call site cannot tell apart.
     * What this cannot see is whether the token was registered with the window system, so it
     * reports the client's own attach state and says so rather than claiming a connection.
     */
    private String windowContext() {
        Context windowContext;
        try {
            windowContext = createWindowContext(
                    android.view.WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY, null);
        } catch (Throwable t) {
            // The case that aborts Chromium: a throw, not a null.
            return "phase=windowcontext verdict=FAIL_THREW " + t.getClass().getName() + ": " + t.getMessage();
        }
        if (windowContext == null) {
            return "phase=windowcontext verdict=FAIL_NULL";
        }
        String displayId = "none";
        try {
            Display display = windowContext.getDisplay();
            displayId = display == null ? "null" : String.valueOf(display.getDisplayId());
        } catch (Throwable t) {
            displayId = "threw:" + t.getClass().getSimpleName();
        }
        Configuration configuration = windowContext.getResources().getConfiguration();
        boolean sized = configuration.screenWidthDp > 0 && configuration.densityDpi > 0;
        // A window context that reports no size is answering with a default-constructed
        // Configuration, which is a different failure from throwing and from being unconnected.
        return "phase=windowcontext verdict=" + (sized ? "PASS_ANSWERED" : "FAIL_EMPTY_CONFIGURATION")
                + " display=" + displayId
                + " widthDp=" + configuration.screenWidthDp
                + " heightDp=" + configuration.screenHeightDp
                + " densityDpi=" + configuration.densityDpi
                + " clientAttachState=" + clientAttachState(windowContext);
    }

    /**
     * The client's own record of how the attach call went: STATUS_INITIALIZED 0, ATTACHED 1,
     * FAILED 2.
     *
     * This is not evidence that the window system knows the token. WindowContextController sets
     * it to ATTACHED whenever the call returns without throwing, so an adapter that answers with
     * a Configuration and registers nothing reads exactly the same as a real attachment. It
     * separates answered from refused, and nothing more; whether a configuration change is ever
     * delivered to this token has to be measured by waiting for one, which this probe does not do.
     * Reported as unknown when the field is not where this platform build keeps it, because
     * "unknown" and "not attached" are different claims.
     */
    private static String clientAttachState(Context windowContext) {
        try {
            Class<?> windowContextClass = Class.forName("android.window.WindowContext");
            if (!windowContextClass.isInstance(windowContext)) {
                return "unknown:not-a-WindowContext";
            }
            java.lang.reflect.Field controllerField =
                    windowContextClass.getDeclaredField("mController");
            controllerField.setAccessible(true);
            Object controller = controllerField.get(windowContext);
            if (controller == null) {
                return "false";
            }
            java.lang.reflect.Field attached =
                    controller.getClass().getDeclaredField("mAttachedToDisplayArea");
            attached.setAccessible(true);
            return String.valueOf(attached.get(controller));
        } catch (NoSuchFieldException e) {
            return "unknown:" + e.getMessage();
        } catch (Throwable t) {
            return "unknown:" + t.getClass().getSimpleName();
        }
    }
}
