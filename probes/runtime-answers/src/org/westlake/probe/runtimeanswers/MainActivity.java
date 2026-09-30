package org.westlake.probe.runtimeanswers;

import android.app.Activity;
import android.app.ActivityManager;
import android.content.Context;
import android.media.AudioFormat;
import android.media.AudioRecord;
import android.media.MediaRecorder;
import android.net.TrafficStats;
import android.net.wifi.WifiManager;
import android.os.Bundle;
import android.os.Process;
import android.system.Os;
import android.telephony.PhoneStateListener;
import android.telephony.TelephonyManager;
import android.widget.TextView;
import java.io.ByteArrayInputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import javax.xml.parsers.SAXParserFactory;
import org.xml.sax.Attributes;
import org.xml.sax.helpers.DefaultHandler;

/**
 * Records, one line each, the answers commercial apps read at startup and that the top-apps blind
 * batch found wrong or refused on Westlake: thread priorities (Instagram, CapCut), service answers
 * (CNN's memory class, NYTimes' Wi-Fi info, Waze's telephony and TrafficStats), and file operations
 * in app storage (Meta's SoLoader, CapCut). Each line is "[WL-ANSWERS] <name> = <value>" with what
 * Android answers alongside, so the log alone says which differ.
 */
public class MainActivity extends Activity {
    private final StringBuilder shown = new StringBuilder();

    private void put(String name, Object value, String android) {
        String line = name + " = " + value + "   (Android: " + android + ")";
        System.err.println("[WL-ANSWERS] " + line);
        shown.append(line).append('\n');
    }

    private interface Check { Object run() throws Throwable; }

    private void check(String name, String android, Check check) {
        Object value;
        try {
            value = check.run();
        } catch (Throwable t) {
            value = "THROWS " + t;
        }
        put(name, value, android);
    }

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        check("main thread priority", "5", () -> Thread.currentThread().getPriority());
        check("new thread priority", "same as creator", () -> new Thread().getPriority());
        check("Process.getThreadPriority(myTid)", "a nice value, e.g. 0 or -10",
                () -> Process.getThreadPriority(Process.myTid()));
        check("Thread.setPriority(current)", "no exception", () -> {
            Thread.currentThread().setPriority(Thread.currentThread().getPriority());
            return "ok";
        });
        check("ActivityManager.getMemoryClass", "> 0 (MB), e.g. 256",
                () -> ((ActivityManager) getSystemService(Context.ACTIVITY_SERVICE)).getMemoryClass());
        check("ActivityManager.getLargeMemoryClass", "> 0 (MB), e.g. 512",
                () -> ((ActivityManager) getSystemService(Context.ACTIVITY_SERVICE)).getLargeMemoryClass());
        check("Runtime.maxMemory", "> 0", () -> Runtime.getRuntime().maxMemory());
        check("WifiManager.getConnectionInfo", "non-null WifiInfo",
                () -> String.valueOf(((WifiManager) getApplicationContext().getSystemService(Context.WIFI_SERVICE))
                        .getConnectionInfo()));
        check("TrafficStats.getUidRxBytes(myUid)", ">= 0 or UNSUPPORTED (-1)",
                () -> TrafficStats.getUidRxBytes(Process.myUid()));
        check("TelephonyManager.listen", "no exception", () -> {
            ((TelephonyManager) getSystemService(Context.TELEPHONY_SERVICE))
                    .listen(new PhoneStateListener(), PhoneStateListener.LISTEN_NONE);
            return "ok";
        });
        File dir = new File(getFilesDir(), "probe-dir");
        dir.mkdirs();
        File file = new File(dir, "probe-file");
        check("File.setWritable(false) on a file", "true", () -> {
            new FileOutputStream(file).close();
            return file.setWritable(false);
        });
        check("File.setReadOnly on a file", "true", () -> file.setReadOnly());
        check("File.setWritable(true) back", "true", () -> file.setWritable(true));
        check("File.setWritable(false) on a directory", "true", () -> dir.setWritable(false));
        check("File.setWritable(true) on a directory", "true", () -> dir.setWritable(true));
        check("Os.chmod(file, 0400)", "ok", () -> { Os.chmod(file.getPath(), 0400); return "ok"; });
        check("Os.chmod(dir, 0500)", "ok", () -> { Os.chmod(dir.getPath(), 0500); return "ok"; });
        check("Os.chmod(dir, 0700)", "ok", () -> { Os.chmod(dir.getPath(), 0700); return "ok"; });
        // Where can a copied library be mapped executable? Each candidate directory gets its own copy.
        String runtimeRoot = System.getenv("WESTLAKE_RUNTIME_ROOT");
        String[][] places = {
            {"code cache", getCodeCacheDir().getPath()},
            {"cache", getCacheDir().getPath()},
            {"no-backup", getNoBackupFilesDir().getPath()},
            {"runtime root", runtimeRoot == null ? "" : runtimeRoot + "/wl-exec-probe"},
        };
        for (String[] place : places) {
            final String dirPath = place[1];
            check("System.load from " + place[0] + " (" + dirPath + ")", "loads", () -> {
                if (dirPath.isEmpty()) return "no such directory";
                File d = new File(dirPath);
                d.mkdirs();
                File lib = new File(d, "libcopied-" + Math.abs(dirPath.hashCode()) + ".so");
                try (ZipFile apk = new ZipFile(getApplicationInfo().sourceDir)) {
                    ZipEntry entry = apk.getEntry("lib/arm64-v8a/libprobeanswers.so");
                    try (InputStream in = apk.getInputStream(entry); FileOutputStream out = new FileOutputStream(lib)) {
                        byte[] b = new byte[65536];
                        for (int n; (n = in.read(b)) > 0; ) out.write(b, 0, n);
                    }
                }
                System.load(lib.getPath());
                return "loaded";
            });
        }
        check("System.load of a library copied to app storage", "loads", () -> {
            File lib = new File(getFilesDir(), "libcopied.so");
            try (ZipFile apk = new ZipFile(getApplicationInfo().sourceDir)) {
                ZipEntry entry = apk.getEntry("lib/arm64-v8a/libprobeanswers.so");
                if (entry == null) return "no library in the APK";
                try (InputStream in = apk.getInputStream(entry); FileOutputStream out = new FileOutputStream(lib)) {
                    byte[] b = new byte[65536];
                    for (int n; (n = in.read(b)) > 0; ) out.write(b, 0, n);
                }
            }
            lib.setReadOnly();
            System.load(lib.getPath());
            return "loaded";
        });
        check("SAXParser.parse (expat natives)", "a|b=1|t=\u00e9\u4e2d",
                () -> {
                    SaxRecorder seen = new SaxRecorder();
                    SAXParserFactory.newInstance().newSAXParser().parse(
                            new ByteArrayInputStream("<a b=\"1\">\u00e9\u4e2d</a>".getBytes("UTF-8")), seen);
                    return seen.toString();
                });
        check("AAsset_openFileDescriptor on an uncompressed asset", "fd ok, bytes match", () -> {
            System.loadLibrary("probeassets");
            return nativeAssetFd(getAssets(), "fd-probe.dat");
        });
        // Meta's SoLoader reads its superpack archive straight out of the APK (useAssetManager=false);
        // the archive is stored uncompressed. Each way of reaching those bytes, first 8 in hex.
        final String apk = getApplicationInfo().sourceDir;
        check("ZipFile.getInputStream of a stored entry", "0001020304050607", () -> {
            try (java.util.zip.ZipFile zip = new java.util.zip.ZipFile(apk);
                 InputStream in = zip.getInputStream(zip.getEntry("assets/fd-probe.dat"))) {
                return hex(in, 8);
            }
        });
        check("FileInputStream.skip to a stored entry's data", "0001020304050607", () -> {
            long offset = storedDataOffset(apk, "assets/fd-probe.dat");
            try (java.io.FileInputStream in = new java.io.FileInputStream(apk)) {
                long skipped = in.skip(offset);
                return (skipped == offset ? "" : "skipped " + skipped + " of " + offset + ": ") + hex(in, 8);
            }
        });
        String[] funopenModes = {"fread 28 (superpack's read path)", "fread 28, unbuffered", "fgetc x8", "fread 1 x8"};
        for (int mode = 0; mode < funopenModes.length; mode++) {
            final int m = mode;
            check("funopen over an InputStream: " + funopenModes[mode], "0001020304050607", () -> {
                try (java.util.zip.ZipFile zip = new java.util.zip.ZipFile(apk);
                     InputStream in = zip.getInputStream(zip.getEntry("assets/fd-probe.dat"))) {
                    return nativeFunopenRead(in, m);
                }
            });
        }
        check("File.setLastModified on a file", "true, read back", () -> {
            File stamp = new File(getFilesDir(), "stamp");
            new FileOutputStream(stamp).close();
            long when = 1700000000000L;
            boolean set = stamp.setLastModified(when);
            return set + (stamp.lastModified() == when ? ", read back" : ", reads " + stamp.lastModified());
        });
        check("ASharedMemory (NDK)", "size 8192, shared yes", () -> nativeSharedMemory());
        check("MappedByteBuffer.load of a mapped file", "loaded, first byte 7", () -> {
            File mapped = new File(getFilesDir(), "mapped");
            try (FileOutputStream out = new FileOutputStream(mapped)) { out.write(new byte[] {7, 8, 9}); }
            try (java.io.RandomAccessFile mappedFile = new java.io.RandomAccessFile(mapped, "r")) {
                java.nio.MappedByteBuffer buffer = mappedFile.getChannel().map(
                        java.nio.channels.FileChannel.MapMode.READ_ONLY, 0, 3);
                buffer.load();
                return "loaded, first byte " + buffer.get(0);
            }
        });
        // Off the main thread, as on Android (NetworkOnMainThreadException otherwise).
        check("NIO SocketChannel over loopback with a Selector", "echoed 5 bytes", () -> {
            final String[] answer = {"no answer"};
            Thread worker = new Thread(() -> { try { answer[0] = nioRoundTrip(); } catch (Throwable t) { answer[0] = "THROWS " + t; } });
            worker.start();
            worker.join(5000);
            return answer[0];
        });
        check("new MediaRecorder()", "constructs", () -> { new MediaRecorder().release(); return "constructs"; });
        check("AudioRecord.getMinBufferSize(48000, mono, 16-bit)", "> 0 (bytes)",
                () -> AudioRecord.getMinBufferSize(48000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT));
        check("AudioRecord 0.5 s from the microphone", "samples read, non-zero level", () -> {
            int min = AudioRecord.getMinBufferSize(48000, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT);
            AudioRecord rec = new AudioRecord(MediaRecorder.AudioSource.MIC, 48000, AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT, Math.max(min, 9600));
            if (rec.getState() != AudioRecord.STATE_INITIALIZED) { rec.release(); return "not initialized"; }
            rec.startRecording();
            short[] buf = new short[24000];
            int got = 0;
            while (got < buf.length) {
                int n = rec.read(buf, got, buf.length - got);
                if (n <= 0) break;
                got += n;
            }
            rec.stop();
            rec.release();
            double sum = 0;
            for (int i = 0; i < got; i++) sum += (double) buf[i] * buf[i];
            return got + " samples, rms " + Math.round(Math.sqrt(sum / Math.max(1, got)));
        });
        TextView text = new TextView(this);
        text.setText(shown);
        setContentView(text);
    }

    /** A SocketChannel round trip through a ServerSocketChannel and a Selector over loopback. */
    private static String nioRoundTrip() throws Exception {
        try (java.nio.channels.ServerSocketChannel server = java.nio.channels.ServerSocketChannel.open();
             java.nio.channels.Selector selector = java.nio.channels.Selector.open()) {
            server.bind(new java.net.InetSocketAddress("127.0.0.1", 0));
            try (java.nio.channels.SocketChannel client = java.nio.channels.SocketChannel.open(server.getLocalAddress());
                 java.nio.channels.SocketChannel accepted = server.accept()) {
                client.write(java.nio.ByteBuffer.wrap("hello".getBytes("UTF-8")));
                accepted.configureBlocking(false);
                accepted.register(selector, java.nio.channels.SelectionKey.OP_READ);
                int ready = selector.select(2000);
                java.nio.ByteBuffer in = java.nio.ByteBuffer.allocate(16);
                int n = accepted.read(in);
                return ready == 1 ? "echoed " + n + " bytes" : "select returned " + ready;
            }
        }
    }

    private static native String nativeFunopenRead(InputStream stream, int mode);

    private static native String nativeSharedMemory();

    private static String hex(InputStream in, int count) throws java.io.IOException {
        StringBuilder out = new StringBuilder();
        for (int i = 0; i < count; i++) {
            int b = in.read();
            if (b < 0) return out + " (end of stream)";
            out.append(String.format("%02x", b));
        }
        return out.toString();
    }

    /** The data offset of a stored entry, from its local file header, as a zip reader computes it. */
    private static long storedDataOffset(String apk, String name) throws java.io.IOException {
        try (java.io.RandomAccessFile file = new java.io.RandomAccessFile(apk, "r")) {
            byte[] all = new byte[(int) Math.min(file.length(), 1 << 20)];
            file.readFully(all);
            byte[] wanted = name.getBytes("UTF-8");
            for (int i = 0; i + 30 + wanted.length < all.length; i++) {
                if (all[i] != 'P' || all[i + 1] != 'K' || all[i + 2] != 3 || all[i + 3] != 4) continue;
                int nameLength = (all[i + 26] & 0xff) | (all[i + 27] & 0xff) << 8;
                int extraLength = (all[i + 28] & 0xff) | (all[i + 29] & 0xff) << 8;
                if (nameLength == wanted.length
                        && new String(all, i + 30, nameLength, "UTF-8").equals(name)) {
                    return i + 30 + nameLength + extraLength;
                }
            }
        }
        throw new java.io.FileNotFoundException(name);
    }

    private static native String nativeAssetFd(android.content.res.AssetManager assets, String name);

    /** Records the SAX events of a one-element document: qName|b=attr|t=text. */
    static final class SaxRecorder extends DefaultHandler {
        private final StringBuilder seen = new StringBuilder();

        @Override public void startElement(String uri, String local, String qName, Attributes attrs) {
            seen.append(qName).append("|b=").append(attrs.getValue("b"));
        }

        @Override public void characters(char[] ch, int start, int length) {
            seen.append("|t=").append(new String(ch, start, length));
        }

        @Override public String toString() {
            return seen.toString();
        }
    }
}
