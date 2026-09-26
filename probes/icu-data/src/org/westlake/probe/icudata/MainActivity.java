package org.westlake.probe.icudata;

import android.app.Activity;
import android.os.Bundle;
import android.widget.TextView;

import java.lang.reflect.Field;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.Callable;

/**
 * Which locale and time-zone data the runtime gives an app. Each check prints one line:
 *
 *   [WL-ICU] <check> ok=<value>        or        [WL-ICU] <check> FAILED <exception>
 *
 * Android answers every check (ICU4J and ICU4C both load icudt, java.time and java.util.TimeZone
 * both have zone rules), so any FAILED or empty value is a gap. The checks separate the loaders:
 * ICU4J (android.icu.*), the native ICU behind java.util.Locale display names, libcore's own
 * tzdata (java.util.TimeZone) and java.time's zone rules provider.
 */
public class MainActivity extends Activity {
    private final StringBuilder shown = new StringBuilder();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        check("env ANDROID_I18N_ROOT", () -> System.getenv("ANDROID_I18N_ROOT"));
        check("env ANDROID_TZDATA_ROOT", () -> System.getenv("ANDROID_TZDATA_ROOT"));
        check("env ICU_DATA", () -> System.getenv("ICU_DATA"));
        check("icu4j data files", () -> {
            Field field = Class.forName("android.icu.impl.ICUBinary").getDeclaredField("icuDataFiles");
            field.setAccessible(true);
            return String.valueOf(((List<?>) field.get(null)).size());
        });
        check("icu4j ULocale display", () -> android.icu.util.ULocale.GERMANY.getDisplayName(android.icu.util.ULocale.US));
        check("icu4j zone ids", () -> String.valueOf(android.icu.util.TimeZone.getAvailableIDs().length));
        // LocaleNative (native ICU4C) answers getDisplayLanguage/Country; repeated and reordered,
        // because a first call can succeed where the next returns null.
        for (int i = 1; i <= 3; i++) {
            final int n = i;
            check("Locale display language #" + n, () -> Locale.GERMANY.getDisplayLanguage(Locale.US));
            check("Locale display country #" + n, () -> Locale.GERMANY.getDisplayCountry(Locale.US));
            check("Locale display script #" + n, () -> Locale.GERMANY.getDisplayScript(Locale.US));
            check("Locale display variant #" + n, () -> Locale.GERMANY.getDisplayVariant(Locale.US));
            check("Locale display name #" + n, () -> Locale.GERMANY.getDisplayName(Locale.US));
        }
        check("Locale display language fr in fr", () -> Locale.FRANCE.getDisplayLanguage(Locale.FRANCE));
        check("Locale display language default", () -> Locale.getDefault() + " -> " + Locale.getDefault().getDisplayLanguage());
        check("LocaleNative direct", () -> {
            java.lang.reflect.Method m = Class.forName("com.android.icu.util.LocaleNative")
                    .getDeclaredMethod("getDisplayLanguage", Locale.class, Locale.class);
            m.setAccessible(true);
            return String.valueOf(m.invoke(null, Locale.ITALY, Locale.US));
        });
        check("SimpleDateFormat day", () -> new java.text.SimpleDateFormat("EEEE", Locale.FRANCE).format(new java.util.Date(0)));
        check("TimeZone Paris", () -> {
            java.util.TimeZone zone = java.util.TimeZone.getTimeZone("Europe/Paris");
            return zone.getID() + " raw=" + zone.getRawOffset();
        });
        check("TimeZone default", () -> java.util.TimeZone.getDefault().getID());
        check("java.time zone ids", () -> String.valueOf(java.time.zone.ZoneRulesProvider.getAvailableZoneIds().size()));
        check("java.time ZoneId.of", () -> java.time.ZoneId.of("Europe/Paris").getRules().toString());
        check("java.time systemDefault", () -> java.time.ZoneId.systemDefault().toString());
        TextView view = new TextView(this);
        view.setText(shown);
        setContentView(view);
    }

    private void check(String name, Callable<String> body) {
        String line;
        try {
            line = "[WL-ICU] " + name + " ok=" + body.call();
        } catch (Throwable t) {
            StringBuilder where = new StringBuilder();
            StackTraceElement[] frames = t.getStackTrace();
            for (int i = 0; i < Math.min(3, frames.length); i++) where.append(" @ ").append(frames[i]);
            line = "[WL-ICU] " + name + " FAILED " + t + where;
        }
        System.err.println(line);
        shown.append(line).append('\n');
    }
}
