package org.westlake.probe.contracts;

import android.app.Activity;
import android.app.AlarmManager;
import android.app.KeyguardManager;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.job.JobInfo;
import android.app.job.JobScheduler;
import android.app.job.JobWorkItem;
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
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.SystemClock;
import android.os.Process;
import android.os.UserHandle;
import android.os.UserManager;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.service.notification.StatusBarNotification;
import android.telephony.TelephonyManager;
import android.util.Log;
import android.view.KeyCharacterMap;
import android.view.KeyEvent;
import android.view.accessibility.CaptioningManager;
import android.view.textclassifier.TextClassification;
import android.view.textclassifier.TextClassificationManager;
import android.view.textclassifier.TextClassifier;
import android.widget.TextView;
import android.widget.Toast;

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
 * no row of its own; it is measured as am:start-unresolved, where Android throws
 * ActivityNotFoundException. The intent:* lines say what handles a web link, a share and the
 * document picker on the device, or that nothing does: what an app's start of one can reach.
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
    // The start from the main thread, made in onCreate: null once it threw ActivityNotFoundException.
    private volatile String mainThreadStart = "not run";

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
        // Starting an activity nothing handles, on the main thread as an app's button handler does.
        // The am:start-unresolved line reports it, last, with the starts made from the worker thread.
        try {
            startActivity(new Intent(PREFIX + "NOTHING_HANDLES_THIS"));
            mainThreadStart = "startActivity returned for an intent nothing handles; Android throws ActivityNotFoundException";
        } catch (ActivityNotFoundException expected) {
            mainThreadStart = null;
        } catch (Throwable t) {
            mainThreadStart = t.toString();
        }
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
            ComponentName service = new ComponentName(this, ProbeJob.class);
            int result = jobs.schedule(new JobInfo.Builder(ProbeJob.NOW, service).setOverrideDeadline(0).build());
            if (result != JobScheduler.RESULT_SUCCESS) throw fail("schedule returned " + result);
            if (!ProbeJob.RAN.await(15, TimeUnit.SECONDS)) {
                throw fail("scheduled (pending=" + (jobs.getPendingJob(ProbeJob.NOW) != null) + ") but never ran in 15 s");
            }
            // A job 1.5 s ahead that needs a network: pending until it runs, not run before its time,
            // given the network it runs on, and no longer pending once it is done.
            long scheduledAt = SystemClock.elapsedRealtime();
            jobs.schedule(new JobInfo.Builder(ProbeJob.LATER, service).setMinimumLatency(1500)
                    .setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).build());
            boolean pending = jobs.getPendingJob(ProbeJob.LATER) != null;
            if (!ProbeJob.LATER_RAN.await(10, TimeUnit.SECONDS)) {
                int reason = jobs.getPendingJobReason(ProbeJob.LATER);
                jobs.cancel(ProbeJob.LATER);
                throw fail("a job 1.5 s ahead that needs a network never ran in 10 s (pending reason " + reason + ")");
            }
            long waited = ProbeJob.laterAt - scheduledAt;
            if (!pending) throw fail("a job scheduled 1.5 s ahead was not pending before it ran");
            if (waited < 1500) throw fail("a job with a 1.5 s minimum latency ran after " + waited + " ms");
            if (ProbeJob.laterNetwork == null) throw fail("a job that needs a network ran without one (getNetwork null)");
            long until = SystemClock.elapsedRealtime() + 3000;
            while (jobs.getPendingJob(ProbeJob.LATER) != null && SystemClock.elapsedRealtime() < until) Thread.sleep(100);
            if (jobs.getPendingJob(ProbeJob.LATER) != null) throw fail("a job that finished is still pending");
            // Work enqueued for a job reaches it through dequeueWork, as JobIntentService takes it.
            jobs.enqueue(new JobInfo.Builder(ProbeJob.WORK, service).setOverrideDeadline(0).build(),
                    new JobWorkItem(new Intent().putExtra("probe", "work-1")));
            if (!ProbeJob.WORKED.await(10, TimeUnit.SECONDS)) throw fail("enqueued work never reached its job in 10 s");
            if (!"work-1".equals(ProbeJob.work)) throw fail("the job dequeued " + ProbeJob.work + ", not the enqueued work");
            return "a job ran at once; one 1.5 s ahead that needs a network ran after " + waited
                    + " ms with its network and was then no longer pending; enqueued work reached its job";
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
        // The notification service keeps the app's channels and its posts, and answers whether the
        // user allows them the same way it answers POST_NOTIFICATIONS. LOW importance: no sound.
        check("svc:notification", () -> {
            NotificationManager nm = getSystemService(NotificationManager.class);
            nm.createNotificationChannel(new NotificationChannel("wl-probe", "Probe", NotificationManager.IMPORTANCE_LOW));
            NotificationChannel kept = nm.getNotificationChannel("wl-probe");
            if (kept == null) throw fail("the channel created is not kept (getNotificationChannel null)");
            boolean enabled = nm.areNotificationsEnabled();
            boolean permitted = checkSelfPermission("android.permission.POST_NOTIFICATIONS") == PackageManager.PERMISSION_GRANTED;
            if (enabled != permitted) {
                throw fail("areNotificationsEnabled=" + enabled + " but POST_NOTIFICATIONS " + (permitted ? "granted" : "denied"));
            }
            nm.notify(4244, new Notification.Builder(this, "wl-probe")
                    .setSmallIcon(android.R.drawable.ic_dialog_info).setContentTitle("probe").build());
            boolean listed = false;
            for (StatusBarNotification posted : nm.getActiveNotifications()) listed |= posted.getId() == 4244;
            nm.cancel(4244);
            boolean gone = true;
            for (StatusBarNotification posted : nm.getActiveNotifications()) gone &= posted.getId() != 4244;
            if (enabled && !listed) throw fail("posted with notifications allowed, and not among the active notifications");
            if (!enabled && listed) throw fail("listed though the user has not allowed notifications");
            if (!gone) throw fail("still active after cancel");
            return "channel kept; notifications " + (enabled ? "allowed (POST_NOTIFICATIONS granted): the post listed, then cancelled"
                    : "not allowed by the user (POST_NOTIFICATIONS denied): the post dropped, as Android drops it");
        });
        // An alarm set while the app runs is delivered at its time: a listener alarm to its listener,
        // and a PendingIntent alarm to the receiver it names, one declared in this app's manifest.
        check("svc:alarm", () -> {
            AlarmManager am = getSystemService(AlarmManager.class);
            CountDownLatch heard = new CountDownLatch(1);
            long at = SystemClock.elapsedRealtime() + 1500;
            am.setExact(AlarmManager.ELAPSED_REALTIME, at, "wl-probe", heard::countDown,
                    new Handler(Looper.getMainLooper()));
            Intent ring = new Intent(this, ProbeReceiver.class).setAction(ProbeReceiver.ALARM);
            PendingIntent operation = PendingIntent.getBroadcast(this, 7, ring, PendingIntent.FLAG_IMMUTABLE);
            am.set(AlarmManager.ELAPSED_REALTIME, at, operation);
            boolean listened = heard.await(8, TimeUnit.SECONDS);
            boolean received = ProbeReceiver.ALARMED.await(listened ? 2 : 8, TimeUnit.SECONDS);
            am.cancel(operation);
            if (!listened && !received) throw fail("neither alarm arrived in 8 s: an alarm set is accepted and never delivered");
            if (!listened) throw fail("the listener alarm never arrived (the PendingIntent alarm did)");
            if (!received) throw fail("the PendingIntent alarm never reached the receiver it names (the listener alarm arrived)");
            return "a listener alarm, and a PendingIntent alarm to the app's own receiver, each delivered at its time";
        });
        // A text toast shows over this activity and goes after its duration: its callbacks hear it
        // shown and then hidden about 2 s later (LENGTH_SHORT), and the activity keeps window focus,
        // as a toast takes neither focus nor touches.
        check("wm:toast", () -> {
            ToastWatch watch = new ToastWatch();
            boolean focusedBefore = hasWindowFocus();
            long start = SystemClock.uptimeMillis();
            runOnUiThread(() -> {
                Toast toast = Toast.makeText(this, "Westlake probe toast", Toast.LENGTH_SHORT);
                toast.addCallback(watch);
                toast.show();
            });
            if (!watch.shown.await(3, TimeUnit.SECONDS)) throw fail("a text toast was not shown in 3 s (no onToastShown)");
            Thread.sleep(300);
            boolean focusedDuring = hasWindowFocus();
            if (!watch.hidden.await(8, TimeUnit.SECONDS)) throw fail("the toast was shown and not hidden in 8 s (no onToastHidden)");
            long[] at = {watch.shownAt, watch.hiddenAt};
            long showedFor = at[1] - at[0];
            if (focusedBefore && !focusedDuring) {
                throw fail("this activity lost window focus while the toast showed; a toast takes neither focus nor touches");
            }
            if (showedFor < 1500 || showedFor > 6000) {
                throw fail("the toast showed for " + showedFor + " ms; LENGTH_SHORT shows for about 2 s");
            }
            return "a text toast was shown " + (at[0] - start) + " ms after show() and hidden " + showedFor
                    + " ms later" + (focusedBefore ? ", the activity keeping window focus" : "");
        });
        // What handles a web link, a share and the system document picker here. An app that opens
        // one starts whatever does; on a device with none, its start finds nothing.
        check("intent:view-web", () -> handlers(pm,
                new Intent(Intent.ACTION_VIEW, Uri.parse("https://www.example.com/")), "a web link"));
        check("intent:share", () -> handlers(pm,
                new Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, "probe"), "a text share"));
        check("intent:pick-document", () -> handlers(pm,
                new Intent(Intent.ACTION_OPEN_DOCUMENT).addCategory(Intent.CATEGORY_OPENABLE).setType("*/*"),
                "the document picker (OPEN_DOCUMENT)"));
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
        // An activity that calls recreate() is destroyed and a new instance brought up with the
        // state it saved, as when an app applies a new theme or language.
        check("am:recreate", () -> {
            runOnUiThread(() -> startActivity(new Intent(this, RecreateActivity.class)));
            boolean recreated = RecreateActivity.SECOND.await(10, TimeUnit.SECONDS);
            RecreateActivity open = RecreateActivity.current;
            if (open != null) runOnUiThread(open::finish);
            RecreateActivity.FINISHED.await(5, TimeUnit.SECONDS);
            if (!recreated) {
                throw fail("recreate() brought no new instance up in 10 s (" + RecreateActivity.instances + " created)");
            }
            if (RecreateActivity.savedSeen != 42) throw fail("a new instance came up without the state the first saved");
            return "a new instance came up with the state the first saved";
        });
        // A focused editor gets the soft keyboard: the input method manager serves it, and the
        // window's insets report the keyboard. Last, as its activity stays up over this one.
        check("svc:input_method", () -> {
            runOnUiThread(() -> startActivity(new Intent(this, KeyboardActivity.class)));
            if (!KeyboardActivity.KEYBOARD.await(15, TimeUnit.SECONDS)) throw fail(KeyboardActivity.keyboardDetail);
            if (!KeyboardActivity.keyboardPassed) throw fail(KeyboardActivity.keyboardDetail);
            return KeyboardActivity.keyboardDetail;
        });
        // Then a dialog over that editor, closed: WMS gives window focus back to the window under it.
        check("wm:focus-handoff", () -> {
            if (!KeyboardActivity.HANDOFF.await(15, TimeUnit.SECONDS)) throw fail(KeyboardActivity.handoffDetail);
            if (!KeyboardActivity.handoffPassed) throw fail(KeyboardActivity.handoffDetail);
            return KeyboardActivity.handoffDetail;
        });
        // Last, as on Android the chooser stays up over this one. Starting an activity nothing handles
        // throws ActivityNotFoundException, by action from the main thread (onCreate) and from this
        // one, and by name; Intent.createChooser over it opens the chooser and does not throw.
        check("am:start-unresolved", () -> {
            if (mainThreadStart != null) throw fail("from the main thread: " + mainThreadStart);
            try {
                startActivity(new Intent(PREFIX + "NOTHING_HANDLES_THIS"));
                throw fail("startActivity from a worker thread returned for an intent nothing handles; "
                        + "Android throws ActivityNotFoundException");
            } catch (ActivityNotFoundException expected) {
            }
            try {
                startActivity(new Intent().setClassName("org.westlake.probe.absent", "org.westlake.probe.absent.Main"));
                throw fail("startActivity returned for an activity of a package that is not installed; "
                        + "Android throws ActivityNotFoundException");
            } catch (ActivityNotFoundException expected) {
            }
            try {
                startActivity(Intent.createChooser(new Intent(PREFIX + "NOTHING_HANDLES_THIS"), "probe"));
            } catch (ActivityNotFoundException e) {
                throw fail("a chooser over an intent nothing handles threw ActivityNotFoundException; "
                        + "Android's chooser opens and says that nothing does");
            }
            return "ActivityNotFoundException from the main thread and a worker thread, by action and by name; "
                    + "a chooser over the intent does not throw";
        });
        line("done", "", "");
    }

    /** A toast's callbacks, as the toast manager reports it shown and hidden. */
    private static final class ToastWatch extends Toast.Callback {
        final CountDownLatch shown = new CountDownLatch(1);
        final CountDownLatch hidden = new CountDownLatch(1);
        volatile long shownAt;
        volatile long hiddenAt;

        @Override
        public void onToastShown() {
            shownAt = SystemClock.uptimeMillis();
            shown.countDown();
        }

        @Override
        public void onToastHidden() {
            hiddenAt = SystemClock.uptimeMillis();
            hidden.countDown();
        }
    }

    /** What handles the intent on this device, or ABSENT when nothing does. */
    private static String handlers(PackageManager pm, Intent intent, String what) throws Outcome {
        List<ResolveInfo> found = pm.queryIntentActivities(intent, PackageManager.MATCH_DEFAULT_ONLY);
        if (found == null || found.isEmpty()) throw absent("nothing handles " + what + " on this device");
        return found.size() + " handle " + what + ", " + found.get(0).activityInfo.packageName + " first";
    }
}
