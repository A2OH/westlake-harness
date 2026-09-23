package org.westlake.probe.signinlayout;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.View;
import android.view.ViewTreeObserver;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.RelativeLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/**
 * The McDonald's sign-in sheet, rebuilt in code with the same view classes and drawing paths:
 * a scroll view over nested LinearLayouts; TextViews with typefaces loaded from assets (the
 * McDTextView path), an underlined link span, a gradient-bordered button row with an ImageView.
 *
 * The verdict is taken after the first real draw: every view must have measured to a non-zero
 * size, the typefaces must have loaded, and drawing the root into a bitmap must produce pixels
 * other than the background.
 */
public final class MainActivity extends Activity implements ViewTreeObserver.OnPreDrawListener, Runnable {
    private View root;
    private TextView header;
    private boolean fontsLoaded;
    private String fontNote;
    private boolean reported;
    private static final String TAG = "WL-SIGNIN-LAYOUT";

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        final FrameLayout root = new FrameLayout(this);
        this.root = root;
        root.setBackgroundColor(Color.WHITE);
        ScrollView scroll = new ScrollView(this);
        scroll.setFillViewport(true);
        RelativeLayout parent = new RelativeLayout(this);
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        int pad = dp(24);
        column.setPadding(pad, dp(40), pad, pad);

        Typeface speedee = null, lovin = null;
        String fontError = "";
        try {
            speedee = Typeface.createFromAsset(getAssets(), "fonts/Speedee-Bold.ttf");
            lovin = Typeface.createFromAsset(getAssets(), "fonts/LovinSans-Regular.otf");
        } catch (Throwable t) {
            fontError = " fontError=" + t;
        }

        final TextView header = this.header = text("Sign in or sign up", 24, Color.rgb(0x29, 0x29, 0x29), speedee);
        column.addView(header);
        TextView agree = text("By signing in, you agree to McDonald's", 16, Color.rgb(0x6f, 0x6f, 0x6f), lovin);
        agree.setPadding(0, dp(24), 0, 0);
        column.addView(agree);
        TextView links = text("Terms & Conditions and Privacy Statement.", 16, Color.rgb(0x1a, 0x5a, 0xcf), lovin);
        links.setPaintFlags(links.getPaintFlags() | Paint.UNDERLINE_TEXT_FLAG);
        column.addView(links);
        TextView california = text("California Privacy Notice", 16, Color.rgb(0x1a, 0x5a, 0xcf), lovin);
        california.setPaintFlags(california.getPaintFlags() | Paint.UNDERLINE_TEXT_FLAG);
        california.setPadding(0, dp(24), 0, dp(24));
        column.addView(california);

        String[] labels = {"Continue with Facebook", "Continue with Google", "Continue with Email"};
        for (String label : labels) {
            LinearLayout row = new LinearLayout(this);
            row.setOrientation(LinearLayout.HORIZONTAL);
            row.setGravity(Gravity.CENTER_VERTICAL);
            GradientDrawable border = new GradientDrawable();
            border.setColor(Color.WHITE);
            border.setStroke(dp(2), Color.rgb(0x29, 0x29, 0x29));
            border.setCornerRadius(dp(6));
            row.setBackground(border);
            row.setPadding(dp(16), dp(18), dp(16), dp(18));
            ImageView icon = new ImageView(this);
            Bitmap dot = Bitmap.createBitmap(dp(28), dp(28), Bitmap.Config.ARGB_8888);
            Canvas c = new Canvas(dot);
            Paint p = new Paint(Paint.ANTI_ALIAS_FLAG);
            p.setColor(Color.rgb(0x18, 0x77, 0xf2));
            c.drawCircle(dp(14), dp(14), dp(14), p);
            icon.setImageBitmap(dot);
            row.addView(icon, new LinearLayout.LayoutParams(dp(28), dp(28)));
            TextView t = text(label, 20, Color.rgb(0x29, 0x29, 0x29), lovin);
            t.setPadding(dp(24), 0, 0, 0);
            row.addView(t);
            LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                    LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
            lp.topMargin = dp(16);
            column.addView(row, lp);
        }
        parent.addView(column, new RelativeLayout.LayoutParams(
                RelativeLayout.LayoutParams.MATCH_PARENT, RelativeLayout.LayoutParams.WRAP_CONTENT));
        scroll.addView(parent);
        root.addView(scroll);
        setContentView(root);

        this.fontsLoaded = speedee != null && lovin != null;
        this.fontNote = fontError;
        root.getViewTreeObserver().addOnPreDrawListener(this);
    }

    @Override
    public boolean onPreDraw() {
        if (!reported) {
            reported = true;
            root.post(this);
        }
        return true;
    }

    @Override
    public void run() {
        report(root, header, fontsLoaded, fontNote);
    }

    private void report(View root, TextView header, boolean fontsLoaded, String fontNote) {
        int zero = countZeroSized(root);
        int total = countViews(root);
        String draw;
        int nonWhite = -1;
        try {
            Bitmap bmp = Bitmap.createBitmap(Math.max(1, root.getWidth()), Math.max(1, root.getHeight()), Bitmap.Config.ARGB_8888);
            root.draw(new Canvas(bmp));
            nonWhite = 0;
            int step = Math.max(1, bmp.getWidth() * bmp.getHeight() / 200000);
            for (int i = 0; i < bmp.getWidth() * bmp.getHeight(); i += step) {
                if ((bmp.getPixel(i % bmp.getWidth(), i / bmp.getWidth()) & 0xffffff) != 0xffffff) nonWhite++;
            }
            draw = "ok";
        } catch (Throwable t) {
            draw = "exception=" + t;
        }
        boolean pass = zero == 0 && total >= 12 && fontsLoaded && nonWhite > 50 && root.getWidth() > 0
                && header.getLayout() != null && header.getLayout().getLineCount() >= 1;
        String result = "verdict=" + (pass ? "PASS_SIGNIN_LAYOUT_DRAWN" : "FAIL")
                + " views=" + total + " zeroSized=" + zero + " root=" + root.getWidth() + "x" + root.getHeight()
                + " headerLines=" + (header.getLayout() == null ? -1 : header.getLayout().getLineCount())
                + " fonts=" + fontsLoaded + fontNote + " draw=" + draw + " nonWhiteSamples=" + nonWhite;
        ProbeApplication.result = result;
        Log.i(TAG, result);
        System.err.println("[" + TAG + "] " + result);
    }

    private static int countViews(View v) {
        int n = 1;
        if (v instanceof android.view.ViewGroup) {
            android.view.ViewGroup g = (android.view.ViewGroup) v;
            for (int i = 0; i < g.getChildCount(); i++) n += countViews(g.getChildAt(i));
        }
        return n;
    }

    private static int countZeroSized(View v) {
        int n = (v.getWidth() == 0 || v.getHeight() == 0) ? 1 : 0;
        if (v instanceof android.view.ViewGroup) {
            android.view.ViewGroup g = (android.view.ViewGroup) v;
            for (int i = 0; i < g.getChildCount(); i++) n += countZeroSized(g.getChildAt(i));
        }
        return n;
    }

    private TextView text(String value, int sp, int color, Typeface face) {
        TextView t = new TextView(this);
        t.setText(value);
        t.setTextSize(TypedValue.COMPLEX_UNIT_SP, sp);
        t.setTextColor(color);
        if (face != null) t.setTypeface(face);
        return t;
    }

    private int dp(int value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }
}
