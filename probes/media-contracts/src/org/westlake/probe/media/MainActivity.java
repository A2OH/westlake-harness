package org.westlake.probe.media;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.ImageFormat;
import android.media.AudioAttributes;
import android.media.AudioFormat;
import android.media.AudioTrack;
import android.media.ImageReader;
import android.media.MediaCodec;
import android.media.MediaExtractor;
import android.media.MediaFormat;
import android.media.MediaMetadataRetriever;
import android.os.Bundle;
import android.util.Log;
import android.view.Surface;
import android.widget.TextView;

import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.ByteBuffer;

/**
 * Media contracts, measured on the provider.
 *
 * Each check exercises one contract the gap map reports open in many apps, on a one-second clip
 * bundled as an asset (160x120 H.264 at 10 fps, a 1 kHz AAC tone), and prints one line named by the
 * gap-map row it measures:
 *
 *   [WL-CONTRACT] <row id> PASS <what worked>
 *   [WL-CONTRACT] <row id> FAIL <exception or wrong answer>
 *
 * then "[WL-CONTRACT] done". The checks run off the main thread, as apps decode, and each is
 * independent: one failing does not stop the next. media:decode-file, a whole decode through
 * MediaExtractor and MediaCodec, has no row of its own.
 */
public class MainActivity extends Activity {
    private static final String TAG = "WL-CONTRACT";

    private interface Check {
        String run() throws Throwable;
    }

    private static void line(String row, String outcome, String detail) {
        String text = "[" + TAG + "] " + row + " " + outcome + " " + detail;
        System.err.println(text);
        Log.i(TAG, text);
    }

    private static void check(String row, Check check) {
        try {
            line(row, "PASS", check.run());
        } catch (Throwable t) {
            StackTraceElement[] at = t.getStackTrace();
            line(row, "FAIL", t.getClass().getName() + ": " + t.getMessage()
                    + (at.length > 0 ? " at " + at[0] : ""));
        }
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        TextView view = new TextView(this);
        view.setText("Westlake media contracts probe");
        setContentView(view);
        new Thread(this::runAll, "media-contracts").start();
    }

    private void runAll() {
        File clip;
        try {
            clip = copyAsset("clip.mp4");
        } catch (Throwable t) {
            line("probe:media-contracts", "FAIL", "could not stage clip.mp4: " + t);
            line("done", "", "");
            return;
        }
        final String path = clip.getPath();
        check("jni:android.media.MediaMetadataRetriever", () -> {
            MediaMetadataRetriever retriever = new MediaMetadataRetriever();
            try {
                retriever.setDataSource(path);
                String duration = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION);
                String mime = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_MIMETYPE);
                Bitmap frame = retriever.getFrameAtTime(0);
                if (duration == null) throw new IllegalStateException("no duration (mime " + mime + ")");
                if (frame == null) throw new IllegalStateException("duration " + duration + " ms but no frame");
                return "duration=" + duration + "ms mime=" + mime + " frame=" + frame.getWidth() + "x" + frame.getHeight();
            } finally {
                retriever.release();
            }
        });
        check("jni:android.media.MediaExtractor", () -> {
            MediaExtractor extractor = new MediaExtractor();
            try {
                extractor.setDataSource(path);
                int tracks = extractor.getTrackCount();
                StringBuilder mimes = new StringBuilder();
                for (int i = 0; i < tracks; i++) {
                    mimes.append(i == 0 ? "" : ",").append(extractor.getTrackFormat(i).getString(MediaFormat.KEY_MIME));
                }
                if (tracks == 0) throw new IllegalStateException("no tracks");
                extractor.selectTrack(0);
                int size = extractor.readSampleData(ByteBuffer.allocate(256 * 1024), 0);
                if (size <= 0) throw new IllegalStateException("tracks " + mimes + " but no sample data");
                return "tracks=" + tracks + " (" + mimes + ") firstSample=" + size + "B";
            } finally {
                extractor.release();
            }
        });
        // MediaCodec on its own, then a whole decode through MediaExtractor, which apps also do: a
        // decode that fails on the extractor says nothing about the codec.
        check("jni:android.media.MediaCodec", () -> {
            MediaCodec codec = MediaCodec.createDecoderByType("video/avc");
            try {
                String name = codec.getName();
                codec.configure(MediaFormat.createVideoFormat("video/avc", 160, 120), null, null, 0);
                codec.start();
                int input = codec.dequeueInputBuffer(1000000);
                codec.stop();
                if (input < 0) throw new IllegalStateException(name + " gave no input buffer in 1 s");
                return "decoder=" + name + " configured and started, input buffer " + input;
            } finally {
                codec.release();
            }
        });
        check("media:decode-file", () -> decodeVideo(path));
        check("jni:android.media.ImageReader", () -> {
            ImageReader reader = ImageReader.newInstance(160, 120, ImageFormat.YUV_420_888, 2);
            try {
                Surface surface = reader.getSurface();
                if (surface == null || !surface.isValid()) throw new IllegalStateException("no valid surface");
                return "YUV_420_888 reader, valid surface, maxImages=" + reader.getMaxImages();
            } finally {
                reader.close();
            }
        });
        check("jni:android.media.AudioTrack", () -> {
            int rate = 48000;
            int min = AudioTrack.getMinBufferSize(rate, AudioFormat.CHANNEL_OUT_STEREO, AudioFormat.ENCODING_PCM_16BIT);
            if (min <= 0) throw new IllegalStateException("getMinBufferSize=" + min);
            AudioTrack track = new AudioTrack.Builder()
                    .setAudioAttributes(new AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).build())
                    .setAudioFormat(new AudioFormat.Builder().setSampleRate(rate)
                            .setChannelMask(AudioFormat.CHANNEL_OUT_STEREO)
                            .setEncoding(AudioFormat.ENCODING_PCM_16BIT).build())
                    .setBufferSizeInBytes(min * 2).build();
            try {
                short[] silence = new short[rate / 10 * 2];
                track.play();
                int written = track.write(silence, 0, silence.length);
                track.stop();
                if (written <= 0) throw new IllegalStateException("write returned " + written);
                return "minBuffer=" + min + "B wrote=" + written + " samples";
            } finally {
                track.release();
            }
        });
        line("done", "", "");
    }

    /** Decodes the clip's video track with MediaCodec into ByteBuffers, as players without a surface do. */
    private static String decodeVideo(String path) throws Throwable {
        MediaExtractor extractor = new MediaExtractor();
        MediaCodec codec = null;
        try {
            extractor.setDataSource(path);
            MediaFormat format = null;
            for (int i = 0; i < extractor.getTrackCount(); i++) {
                MediaFormat f = extractor.getTrackFormat(i);
                if (f.getString(MediaFormat.KEY_MIME).startsWith("video/")) {
                    extractor.selectTrack(i);
                    format = f;
                    break;
                }
            }
            if (format == null) throw new IllegalStateException("no video track");
            codec = MediaCodec.createDecoderByType(format.getString(MediaFormat.KEY_MIME));
            String name = codec.getName();
            codec.configure(format, null, null, 0);
            codec.start();
            MediaCodec.BufferInfo info = new MediaCodec.BufferInfo();
            int frames = 0;
            boolean inputDone = false;
            long deadline = System.currentTimeMillis() + 8000;
            while (frames < 3 && System.currentTimeMillis() < deadline) {
                if (!inputDone) {
                    int in = codec.dequeueInputBuffer(10000);
                    if (in >= 0) {
                        int size = extractor.readSampleData(codec.getInputBuffer(in), 0);
                        if (size < 0) {
                            codec.queueInputBuffer(in, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM);
                            inputDone = true;
                        } else {
                            codec.queueInputBuffer(in, 0, size, extractor.getSampleTime(), 0);
                            extractor.advance();
                        }
                    }
                }
                int out = codec.dequeueOutputBuffer(info, 10000);
                if (out >= 0) {
                    if (info.size > 0) frames++;
                    codec.releaseOutputBuffer(out, false);
                    if ((info.flags & MediaCodec.BUFFER_FLAG_END_OF_STREAM) != 0) break;
                }
            }
            codec.stop();
            if (frames == 0) throw new IllegalStateException("decoder " + name + " produced no frames in 8 s");
            return "decoder=" + name + " frames=" + frames;
        } finally {
            if (codec != null) codec.release();
            extractor.release();
        }
    }

    private File copyAsset(String name) throws Exception {
        File out = new File(getFilesDir(), name);
        try (InputStream in = getAssets().open(name); OutputStream os = new FileOutputStream(out)) {
            byte[] buffer = new byte[16384];
            for (int n; (n = in.read(buffer)) > 0; ) os.write(buffer, 0, n);
        }
        return out;
    }
}
