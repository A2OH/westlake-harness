package org.westlake.probe.contracts;

import android.app.Activity;
import android.app.KeyguardManager;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.content.ActivityNotFoundException;
import android.content.ComponentName;
import android.content.Intent;
import android.app.GrammaticalInflectionManager;
import android.content.pm.InstallSourceInfo;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.hardware.Sensor;
import android.hardware.biometrics.BiometricManager;
import android.hardware.fingerprint.FingerprintManager;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.media.AudioDeviceInfo;
import android.media.AudioFocusRequest;
import android.media.AudioManager;
import android.media.metrics.MediaMetricsManager;
import android.media.metrics.PlaybackSession;
import android.os.Bundle;
import android.os.Process;
import android.os.UserHandle;
import android.os.UserManager;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.telephony.TelephonyManager;
import android.util.Log;
import android.view.KeyCharacterMap;
import android.view.KeyEvent;
import android.view.accessibility.CaptioningManager;
import android.view.textclassifier.TextClassification;
import android.view.textclassifier.TextClassificationManager;
import android.view.textclassifier.TextClassifier;
import android.widget.TextView;

import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/**
 * Framework contracts, measured on the provider.
 *
 * Each check exercises one contract the gap map reports open in many apps and prints one line named
 * by the gap-map row it measures:
 *
 *   [WL-CONTRACT] <row id> PASS <what Android's answer looked like>
 *   [WL-CONTRACT] <row id> ABSENT <the truthful answer of a device without the feature>
 *   [WL-CONTRACT] <row id> FAIL <exception, or an answer Android would not give>
 *
 * then "[WL-CONTRACT] done". The package manager's queries are asked for this probe's own components,
 * declared in its manifest, so each has one right answer. Starting an activity nothing handles has
 * no row yet; it is measured as am:start-unresolved, where Android throws ActivityNotFoundException.
 */
public class MainActivity extends Activity {
    private static final String TAG = "WL-CONTRACT";
    private static final String PREFIX = "org.westlake.probe.contracts.";

    private interface Check {
        String run() throws Throwable;
    }

    /** A check's outcome other than PASS, with its detail. */
    private static final class Outcome extends Exception {
        final String kind;

        Outcome(String kind, String detail) {
            super(detail);
            this.kind = kind;
        }
    }

    /** Counts the first sensor event. (A named class: d8 fails on an anonymous one inside a lambda.) */
    private static final class EventLatch implements SensorEventListener {
        final CountDownLatch event = new CountDownLatch(1);

        @Override
        public void onSensorChanged(SensorEvent e) {
            event.countDown();
        }

        @Override
        public void onAccuracyChanged(Sensor sensor, int accuracy) {
        }
    }

    private static void line(String row, String outcome, String detail) {
        String text = "[" + TAG + "] " + row + " " + outcome + " " + detail;
        System.err.println(text);
        Log.i(TAG, text);
    }

    private static void check(String row, Check check) {
        try {
            line(row, "PASS", check.run());
        } catch (Outcome o) {
            line(row, o.kind, o.getMessage());
        } catch (Throwable t) {
            StackTraceElement[] at = t.getStackTrace();
            line(row, "FAIL", t.getClass().getName() + ": " + t.getMessage() + (at.length > 0 ? " at " + at[0] : ""));
        }
    }

    private static Outcome fail(String detail) {
        return new Outcome("FAIL", detail);
    }

    private static Outcome absent(String detail) {
        return new Outcome("ABSENT", detail);
    }

    private static final int RESULT_REQUEST = 4243;
    private final CountDownLatch resultArrived = new CountDownLatch(1);
    private volatile String resultSeen;

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode != RESULT_REQUEST) return;
        resultSeen = "resultCode=" + resultCode + " answer=" + (data == null ? "no data" : data.getIntExtra("answer", -1));
        resultArrived.countDown();
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        TextView view = new TextView(this);
        view.setText("Westlake framework contracts probe");
        setContentView(view);
        // Starting an activity is checked here, on the main thread, as an app's button handler does.
        check("am:start-unresolved", () -> {
            try {
                startActivity(new Intent(PREFIX + "NOTHING_HANDLES_THIS"));
            } catch (ActivityNotFoundException e) {
                return "ActivityNotFoundException, as on Android";
            }
            throw fail("startActivity returned for an intent nothing handles; Android throws ActivityNotFoundException");
        });
        new Thread(this::runAll, "framework-contracts").start();
    }

    private void runAll() {
        final PackageManager pm = getPackageManager();
        check("svc:audio", () -> {
            AudioManager audio = getSystemService(AudioManager.class);
            if (audio == null) throw fail("no AudioManager");
            int max = audio.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
            int volume = audio.getStreamVolume(AudioManager.STREAM_MUSIC);
            String rate = audio.getProperty(AudioManager.PROPERTY_OUTPUT_SAMPLE_RATE);
            String burst = audio.getProperty(AudioManager.PROPERTY_OUTPUT_FRAMES_PER_BUFFER);
            AudioDeviceInfo[] outputs = audio.getDevices(AudioManager.GET_DEVICES_OUTPUTS);
            int focus = audio.requestAudioFocus(new AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN).build());
            String seen = "maxVolume=" + max + " volume=" + volume + " sampleRate=" + rate + " framesPerBuffer=" + burst
                    + " outputs=" + (outputs == null ? "null" : outputs.length) + " focus=" + focus
                    + " ringerMode=" + audio.getRingerMode();
            if (max <= 0 || rate == null || burst == null || outputs == null || outputs.length == 0
                    || focus != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) {
                throw fail("answers Android would not give: " + seen);
            }
            return seen;
        });
        check("pm:call:queryIntentContentProviders", () -> {
            List<ResolveInfo> found = pm.queryIntentContentProviders(new Intent(PREFIX + "PROVIDER"), 0);
            if (found == null || found.isEmpty()) throw fail("no provider for its own filter (" + found + ")");
            return found.size() + " found: " + found.get(0).providerInfo.name;
        });
        check("pm:call:queryIntentActivityOptions", () -> {
            List<ResolveInfo> found = pm.queryIntentActivityOptions(null, null, new Intent(PREFIX + "OPTION"), 0);
            if (found == null || found.isEmpty()) throw fail("no activity for its own filter (" + found + ")");
            return found.size() + " found: " + found.get(0).activityInfo.name;
        });
        check("pm:call:queryBroadcastReceivers", () -> {
            List<ResolveInfo> found = pm.queryBroadcastReceivers(new Intent(PREFIX + "PING"), 0);
            if (found == null || found.isEmpty()) throw fail("no receiver for its own filter (" + found + ")");
            return found.size() + " found: " + found.get(0).activityInfo.name;
        });
        ComponentName second = new ComponentName(this, SecondActivity.class);
        final int[] afterDisable = {-1};
        check("pm:call:setComponentEnabledSetting", () -> {
            pm.setComponentEnabledSetting(second, PackageManager.COMPONENT_ENABLED_STATE_DISABLED,
                    PackageManager.DONT_KILL_APP);
            afterDisable[0] = pm.getComponentEnabledSetting(second);
            List<ResolveInfo> found = pm.queryIntentActivities(new Intent(PREFIX + "OPTION"), 0);
            pm.setComponentEnabledSetting(second, PackageManager.COMPONENT_ENABLED_STATE_DEFAULT,
                    PackageManager.DONT_KILL_APP);
            if (found != null && !found.isEmpty()) {
                throw fail("disabled activity still resolves (" + found.size() + " found)");
            }
            return "disabled activity no longer resolves";
        });
        check("pm:call:getComponentEnabledSetting", () -> {
            if (afterDisable[0] != PackageManager.COMPONENT_ENABLED_STATE_DISABLED) {
                throw fail("read back " + afterDisable[0] + " after disabling, not "
                        + PackageManager.COMPONENT_ENABLED_STATE_DISABLED);
            }
            int now = pm.getComponentEnabledSetting(second);
            return "read back DISABLED, then " + now + " after resetting";
        });
        check("jni:android.view.KeyCharacterMap", () -> {
            KeyCharacterMap map = KeyCharacterMap.load(KeyCharacterMap.VIRTUAL_KEYBOARD);
            int a = map.get(KeyEvent.KEYCODE_A, 0);
            KeyEvent[] events = map.getEvents("ab".toCharArray());
            if (a != 'a' || events == null || events.length == 0) {
                throw fail("KEYCODE_A -> " + a + ", events for \"ab\" " + (events == null ? "null" : events.length));
            }
            return "KEYCODE_A -> 'a', " + events.length + " events for \"ab\", type " + map.getKeyboardType();
        });
        check("svc:jobscheduler", () -> {
            JobScheduler jobs = getSystemService(JobScheduler.class);
            if (jobs == null) throw fail("no JobScheduler");
            int result = jobs.schedule(new JobInfo.Builder(4242, new ComponentName(this, ProbeJob.class))
                    .setOverrideDeadline(0).build());
            if (result != JobScheduler.RESULT_SUCCESS) throw fail("schedule returned " + result);
            if (!ProbeJob.RAN.await(15, TimeUnit.SECONDS)) {
                throw fail("scheduled (pending=" + (jobs.getPendingJob(4242) != null) + ") but never ran in 15 s");
            }
            return "scheduled and ran";
        });
        check("svc:vibrator", () -> {
            Vibrator vibrator = getSystemService(Vibrator.class);
            if (vibrator == null) throw fail("no Vibrator");
            boolean has = vibrator.hasVibrator();
            vibrator.vibrate(VibrationEffect.createOneShot(20, VibrationEffect.DEFAULT_AMPLITUDE));
            if (!has) throw absent("hasVibrator=false, and vibrate() returned");
            return "hasVibrator=true, vibrate() returned";
        });
        check("svc:sensor", () -> {
            SensorManager sensors = getSystemService(SensorManager.class);
            if (sensors == null) throw fail("no SensorManager");
            List<Sensor> all = sensors.getSensorList(Sensor.TYPE_ALL);
            if (all == null) throw fail("getSensorList returned null");
            Sensor accelerometer = sensors.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
            if (all.isEmpty() && accelerometer == null) throw absent("no sensors listed, no accelerometer");
            if (accelerometer == null) return all.size() + " sensors, no accelerometer";
            EventLatch listener = new EventLatch();
            boolean registered = sensors.registerListener(listener, accelerometer, SensorManager.SENSOR_DELAY_NORMAL);
            boolean got = registered && listener.event.await(5, TimeUnit.SECONDS);
            sensors.unregisterListener(listener);
            if (!got) throw fail(all.size() + " sensors listed; the accelerometer "
                    + (registered ? "delivered no event in 5 s" : "refused a listener"));
            return all.size() + " sensors; the accelerometer delivered events";
        });
        check("svc:phone", () -> {
            TelephonyManager phone = getSystemService(TelephonyManager.class);
            if (phone == null) throw fail("no TelephonyManager");
            int type = phone.getPhoneType();
            int sim = phone.getSimState();
            String operator = phone.getNetworkOperatorName();
            String seen = "phoneType=" + type + " simState=" + sim + " operator=" + operator;
            if (type == TelephonyManager.PHONE_TYPE_NONE) throw absent(seen);
            return seen;
        });
        check("svc:keyguard", () -> {
            KeyguardManager keyguard = getSystemService(KeyguardManager.class);
            if (keyguard == null) throw fail("no KeyguardManager");
            return "locked=" + keyguard.isKeyguardLocked() + " secure=" + keyguard.isDeviceSecure();
        });
        check("svc:textclassification", () -> {
            TextClassificationManager manager = getSystemService(TextClassificationManager.class);
            if (manager == null) throw fail("no TextClassificationManager");
            TextClassifier classifier = manager.getTextClassifier();
            if (classifier == null) throw fail("getTextClassifier returned null");
            if (classifier == TextClassifier.NO_OP) throw absent("the NO_OP classifier, as on a device without one");
            String text = "Visit https://example.com today";
            TextClassification result = classifier.classifyText(
                    new TextClassification.Request.Builder(text, 6, 25).build());
            return classifier.getClass().getSimpleName() + " classified a URL: " + result.getEntityCount()
                    + " entities" + (result.getEntityCount() > 0 ? ", first " + result.getEntity(0) : "");
        });
        check("svc:user", () -> {
            UserManager users = getSystemService(UserManager.class);
            if (users == null) throw fail("no UserManager");
            boolean unlocked = users.isUserUnlocked();
            List<UserHandle> profiles = users.getUserProfiles();
            long serial = users.getSerialNumberForUser(Process.myUserHandle());
            String seen = "unlocked=" + unlocked + " profiles=" + profiles + " serial=" + serial
                    + " goat=" + users.isUserAGoat();
            if (!unlocked || profiles == null || !profiles.contains(Process.myUserHandle()) || serial < 0) {
                throw fail("answers Android would not give: " + seen);
            }
            return seen;
        });
        check("svc:fingerprint", () -> {
            FingerprintManager fingerprint = getSystemService(FingerprintManager.class);
            boolean feature = pm.hasSystemFeature(PackageManager.FEATURE_FINGERPRINT);
            if (fingerprint == null) {
                if (feature) throw fail("no FingerprintManager, but FEATURE_FINGERPRINT is claimed");
                throw absent("no FingerprintManager and no FEATURE_FINGERPRINT, as on a device without a sensor");
            }
            boolean hardware = fingerprint.isHardwareDetected();
            if (!hardware) throw absent("isHardwareDetected=false");
            return "hardware detected, enrolled=" + fingerprint.hasEnrolledFingerprints();
        });
        check("svc:biometric", () -> {
            BiometricManager biometric = getSystemService(BiometricManager.class);
            if (biometric == null) throw fail("no BiometricManager; Android always has one, even without a sensor");
            int strong = biometric.canAuthenticate(BiometricManager.Authenticators.BIOMETRIC_STRONG);
            if (strong == BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE
                    || strong == BiometricManager.BIOMETRIC_ERROR_HW_UNAVAILABLE) {
                throw absent("canAuthenticate(BIOMETRIC_STRONG)=" + strong + ", as on a device without a sensor");
            }
            return "canAuthenticate(BIOMETRIC_STRONG)=" + strong;
        });
        check("svc:captioning", () -> {
            CaptioningManager captioning = getSystemService(CaptioningManager.class);
            if (captioning == null) throw fail("no CaptioningManager");
            float scale = captioning.getFontScale();
            if (scale <= 0) throw fail("font scale " + scale);
            return "enabled=" + captioning.isEnabled() + " locale=" + captioning.getLocale() + " fontScale=" + scale;
        });
        check("svc:media_metrics", () -> {
            MediaMetricsManager metrics = getSystemService(MediaMetricsManager.class);
            if (metrics == null) throw fail("no MediaMetricsManager");
            PlaybackSession session = metrics.createPlaybackSession();
            if (session == null) throw fail("createPlaybackSession returned null");
            String id = String.valueOf(session.getSessionId());
            session.close();
            return "a playback session " + id;
        });
        check("svc:grammatical_inflection", () -> {
            GrammaticalInflectionManager inflection = getSystemService(GrammaticalInflectionManager.class);
            if (inflection == null) throw fail("no GrammaticalInflectionManager");
            return "application grammatical gender " + inflection.getApplicationGrammaticalGender();
        });
        check("pm:call:getInstallerPackageName", () -> {
            String installer = pm.getInstallerPackageName(getPackageName());
            InstallSourceInfo source = pm.getInstallSourceInfo(getPackageName());
            if (source == null) throw fail("getInstallSourceInfo returned null");
            return "installer=" + installer + " (as for an app installed from a file), install source answered";
        });
        // These two bring another activity up over this one, so they come last. An activity this app
        // starts is created, started and resumed, and stays resumed while it is on top: a player
        // that pauses in onPause (mpv) stays paused after an extra pause and resume.
        check("am:launch-lifecycle", () -> {
            runOnUiThread(() -> startActivity(new Intent(this, LifecycleActivity.class)));
            if (!LifecycleActivity.RESUMED.await(10, TimeUnit.SECONDS)) {
                throw fail("the started activity was not resumed in 10 s: " + LifecycleActivity.seen());
            }
            Thread.sleep(2000);
            String seen = LifecycleActivity.seen();
            LifecycleActivity started = LifecycleActivity.current;
            if (started != null) runOnUiThread(started::finish);
            LifecycleActivity.DESTROYED.await(5, TimeUnit.SECONDS);
            if (!"onCreate onStart onResume".equals(seen)) {
                throw fail("callbacks " + seen + " in 2 s on top; Android gives onCreate onStart onResume");
            }
            return "onCreate onStart onResume, and no pause in 2 s on top";
        });
        // startActivityForResult to an activity of this app, which sets a result and finishes;
        // Android delivers it to onActivityResult before this activity resumes.
        check("am:activity-result", () -> {
            runOnUiThread(() -> startActivityForResult(new Intent(this, ResultActivity.class), RESULT_REQUEST));
            if (!resultArrived.await(10, TimeUnit.SECONDS)) {
                throw fail("the started activity set a result and finished; onActivityResult never ran in 10 s");
            }
            if (!("resultCode=" + RESULT_OK + " answer=42").equals(resultSeen)) throw fail("wrong result: " + resultSeen);
            return "onActivityResult got " + resultSeen;
        });
        line("done", "", "");
    }
}
