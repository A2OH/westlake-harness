package org.westlake.probe.glcontracts;

import android.app.Activity;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.SurfaceTexture;
import android.opengl.EGL14;
import android.opengl.EGLConfig;
import android.opengl.EGLContext;
import android.opengl.EGLDisplay;
import android.opengl.EGLSurface;
import android.opengl.GLES20;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.TextureView;
import android.view.View;
import android.widget.LinearLayout;
import java.lang.reflect.Method;

/**
 * The graphics contracts Telegram, X, a video camera app and three games depended on, checked in one
 * launch: an app's own GL thread initializes EGL; frames it renders into a TextureView are consumed
 * by the UI (hwui imports the buffer and hands it back with a release fence); the producer survives
 * the UI thread stalling longer than a buffer request's timeout; and an app's eglTerminate leaves the
 * display hwui draws with alone. Each check logs "[WL-GL-PROBE] check=<name> verdict=PASS|FAIL"; a
 * crash ends the probe, so a missing PASS is a failure too. Android passes every check.
 */
public class MainActivity extends Activity implements TextureView.SurfaceTextureListener {
    private static final String TAG = "[WL-GL-PROBE] ";
    private final Handler main = new Handler(Looper.getMainLooper());
    private volatile int consumed;
    private volatile int produced;
    private volatile int drawn;
    private volatile boolean producing = true;
    private volatile String producerError;
    private boolean allPass = true;

    private void verdict(String check, boolean pass, String detail) {
        allPass &= pass;
        System.err.println(TAG + "check=" + check + " verdict=" + (pass ? "PASS" : "FAIL") + " " + detail);
    }

    /** Redraws every frame and counts the frames hwui draws for the window. Static: javac 21 records a
     *  nameless outer-instance parameter for an inner class's constructor, which d8 rejects. */
    private static class Counter extends View {
        private final MainActivity owner;
        Counter(MainActivity owner) { super(owner); this.owner = owner; }
        @Override protected void onDraw(Canvas canvas) {
            owner.drawn++;
            canvas.drawColor(owner.drawn % 2 == 0 ? Color.LTGRAY : Color.GRAY);
            invalidate();
        }
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        TextureView texture = new TextureView(this);
        texture.setSurfaceTextureListener(this);
        layout.addView(texture, new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        layout.addView(new Counter(this), new LinearLayout.LayoutParams(LinearLayout.LayoutParams.MATCH_PARENT, 0, 1));
        setContentView(layout);
        System.err.println(TAG + "started");
    }

    @Override
    public void onSurfaceTextureAvailable(SurfaceTexture surface, int width, int height) {
        new Thread(() -> produce(surface), "GlContractsProducer").start();
        main.postDelayed(this::checkFrames, 3000);
    }

    @Override public boolean onSurfaceTextureDestroyed(SurfaceTexture surface) { return true; }
    @Override public void onSurfaceTextureSizeChanged(SurfaceTexture surface, int width, int height) { }
    @Override public void onSurfaceTextureUpdated(SurfaceTexture surface) { consumed++; }

    /** An app's own GL thread rendering into the TextureView, as Telegram's intro does. */
    private void produce(SurfaceTexture surface) {
        EGLDisplay display = EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY);
        int[] version = new int[2];
        boolean initialized = EGL14.eglInitialize(display, version, 0, version, 1);
        int[] attributes = {EGL14.EGL_RENDERABLE_TYPE, EGL14.EGL_OPENGL_ES2_BIT, EGL14.EGL_SURFACE_TYPE,
                EGL14.EGL_WINDOW_BIT, EGL14.EGL_RED_SIZE, 8, EGL14.EGL_GREEN_SIZE, 8, EGL14.EGL_BLUE_SIZE, 8,
                EGL14.EGL_NONE};
        EGLConfig[] configs = new EGLConfig[1];
        int[] count = new int[1];
        boolean chosen = initialized && EGL14.eglChooseConfig(display, attributes, 0, configs, 0, 1, count, 0)
                && count[0] > 0;
        verdict("egl-init", chosen, "initialize=" + initialized + " configs=" + count[0]
                + " error=0x" + Integer.toHexString(EGL14.eglGetError()));
        if (!chosen) return;
        EGLContext context = EGL14.eglCreateContext(display, configs[0], EGL14.EGL_NO_CONTEXT,
                new int[] {EGL14.EGL_CONTEXT_CLIENT_VERSION, 2, EGL14.EGL_NONE}, 0);
        EGLSurface window = EGL14.eglCreateWindowSurface(display, configs[0], surface,
                new int[] {EGL14.EGL_NONE}, 0);
        if (!EGL14.eglMakeCurrent(display, window, window, context)) {
            producerError = "eglMakeCurrent 0x" + Integer.toHexString(EGL14.eglGetError());
            return;
        }
        while (producing) {
            float shade = (produced % 60) / 60f;
            GLES20.glClearColor(shade, 0.3f, 1f - shade, 1f);
            GLES20.glClear(GLES20.GL_COLOR_BUFFER_BIT);
            if (!EGL14.eglSwapBuffers(display, window)) {
                producerError = "eglSwapBuffers 0x" + Integer.toHexString(EGL14.eglGetError());
                return;
            }
            produced++;
        }
    }

    private void checkFrames() {
        verdict("textureview-frames", consumed >= 30, "consumed=" + consumed + " produced=" + produced
                + (producerError != null ? " producer=" + producerError : ""));
        // Hold the UI thread past OH's 3000 ms buffer-request timeout: the producer must wait for a
        // buffer, as Android's dequeue does, and resume when the UI does.
        int before = consumed;
        try { Thread.sleep(4000); } catch (InterruptedException ignored) { }
        main.postDelayed(() -> {
            verdict("consumer-stall", producerError == null && consumed >= before + 10,
                    "consumed " + before + "->" + consumed
                    + (producerError != null ? " producer=" + producerError : ""));
            checkTerminate();
        }, 2000);
    }

    /** An app initializing and terminating the default display, as a GL check or an EGL14 helper does. */
    private void checkTerminate() {
        Thread terminator = new Thread(() -> {
            EGLDisplay display = EGL14.eglGetDisplay(EGL14.EGL_DEFAULT_DISPLAY);
            int[] version = new int[2];
            EGL14.eglInitialize(display, version, 0, version, 1);
            EGL14.eglTerminate(display);
        }, "GlContractsTerminate");
        terminator.start();
        try { terminator.join(2000); } catch (InterruptedException ignored) { }
        int drawnBefore = drawn;
        int consumedBefore = consumed;
        main.postDelayed(() -> {
            verdict("terminate-keeps-display", drawn >= drawnBefore + 30 && consumed >= consumedBefore + 10,
                    "drawn " + drawnBefore + "->" + drawn + " consumed " + consumedBefore + "->" + consumed);
            answerCompiledCode();
            System.err.println(TAG + "verdict=" + (allPass ? "ALL_PASS" : "SOME_FAIL"));
            producing = false;
        }, 2000);
    }

    /** Whether this app's own code runs compiled: ART's view of the APK's compiled state. */
    private void answerCompiledCode() {
        String status;
        try {
            Method method = Class.forName("dalvik.system.DexFile")
                    .getMethod("getDexFileStatus", String.class, String.class);
            status = String.valueOf(method.invoke(null, getApplicationInfo().sourceDir, "arm64"));
        } catch (Throwable t) {
            status = "THROWS " + t;
        }
        System.err.println(TAG + "answer compiled-code = " + status);
    }
}
