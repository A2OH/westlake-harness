package org.westlake.probe.audiotone;

import android.app.Activity;
import android.content.res.AssetFileDescriptor;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;
import android.media.MediaPlayer;
import android.os.Bundle;
import android.widget.TextView;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;

/**
 * Plays a steady tone through each Android audio path in turn, forever, so one recording of the
 * board's output covers them all. Each path has its own frequency, which is how a recording
 * tells them apart:
 *
 *   1000 Hz  AudioTrack, 48 kHz stereo 16-bit, blocking short[] writes
 *   1500 Hz  AudioTrack, 44.1 kHz stereo 16-bit, blocking short[] writes
 *   2500 Hz  AudioTrack, 48 kHz stereo float, non-blocking ByteBuffer writes (ExoPlayer's pattern)
 *   2000 Hz  MediaPlayer on assets/tone2000.wav (44.1 kHz stereo 16-bit)
 *
 * A path that plays at the wrong rate shifts its tone; one that drops data leaves silent gaps.
 * probes/audio-capture/tone_check.py measures both.
 */
public class MainActivity extends Activity {
    private static final int SECONDS = 4;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        TextView text = new TextView(this);
        text.setText("Westlake audio tone probe: 1000 / 1500 / 2500 / 2000 Hz, 4 s each, looping");
        setContentView(text);
        Thread thread = new Thread(this::loop, "audio-tone");
        thread.setDaemon(true);
        thread.start();
    }

    private static void log(String line) {
        System.err.println("[PROBE-AUDIO] " + line);
    }

    private void loop() {
        for (int round = 0; ; round++) {
            try {
                shorts(48000, 1000);
                shorts(44100, 1500);
                floatsNonBlocking(48000, 2500);
                mediaPlayer();
            } catch (Throwable t) {
                log("round " + round + " failed: " + t);
                try { Thread.sleep(1000); } catch (InterruptedException ignored) { return; }
            }
        }
    }

    private static AudioAttributes music() {
        return new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build();
    }

    private static AudioTrack track(int rate, int encoding) {
        AudioFormat format = new AudioFormat.Builder().setSampleRate(rate).setEncoding(encoding)
                .setChannelMask(AudioFormat.CHANNEL_OUT_STEREO).build();
        int min = AudioTrack.getMinBufferSize(rate, AudioFormat.CHANNEL_OUT_STEREO, encoding);
        return new AudioTrack.Builder().setAudioAttributes(music()).setAudioFormat(format)
                .setBufferSizeInBytes(Math.max(min, 8192)).setTransferMode(AudioTrack.MODE_STREAM).build();
    }

    private void shorts(int rate, double freq) {
        AudioTrack t = track(rate, AudioFormat.ENCODING_PCM_16BIT);
        log("audiotrack16 " + rate + " Hz tone " + freq + " start");
        t.play();
        short[] buf = new short[1024 * 2];
        double phase = 0;
        long total = (long) rate * SECONDS;
        for (long done = 0; done < total; done += 1024) {
            for (int i = 0; i < 1024; i++) {
                short v = (short) (8000 * Math.sin(phase));
                buf[2 * i] = v;
                buf[2 * i + 1] = v;
                phase += 2 * Math.PI * freq / rate;
            }
            int w = t.write(buf, 0, buf.length);
            if (w < 0) { log("write error " + w); break; }
        }
        t.stop();
        t.release();
        log("audiotrack16 " + rate + " end");
    }

    private void floatsNonBlocking(int rate, double freq) throws InterruptedException {
        AudioTrack t = track(rate, AudioFormat.ENCODING_PCM_FLOAT);
        log("audiotrackfloat " + rate + " Hz tone " + freq + " start");
        t.play();
        ByteBuffer buf = ByteBuffer.allocateDirect(1024 * 2 * 4).order(ByteOrder.nativeOrder());
        double phase = 0;
        long total = (long) rate * SECONDS;
        for (long done = 0; done < total; done += 1024) {
            buf.clear();
            for (int i = 0; i < 1024; i++) {
                float v = (float) (0.25 * Math.sin(phase));
                buf.putFloat(v);
                buf.putFloat(v);
                phase += 2 * Math.PI * freq / rate;
            }
            buf.flip();
            while (buf.hasRemaining()) {
                int w = t.write(buf, buf.remaining(), AudioTrack.WRITE_NON_BLOCKING);
                if (w < 0) { log("write error " + w); t.release(); return; }
                if (buf.hasRemaining()) Thread.sleep(2);
            }
        }
        t.stop();
        t.release();
        log("audiotrackfloat " + rate + " end");
    }

    private void mediaPlayer() throws Exception {
        MediaPlayer mp = new MediaPlayer();
        try (AssetFileDescriptor afd = getAssets().openFd("tone2000.wav")) {
            mp.setDataSource(afd.getFileDescriptor(), afd.getStartOffset(), afd.getLength());
        }
        mp.setAudioAttributes(music());
        mp.prepare();
        log("mediaplayer tone 2000 start, duration " + mp.getDuration() + " ms");
        mp.start();
        long end = System.currentTimeMillis() + SECONDS * 1000L + 500;
        while (mp.isPlaying() && System.currentTimeMillis() < end) Thread.sleep(50);
        mp.release();
        log("mediaplayer end");
    }
}
