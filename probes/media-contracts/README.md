# media-contracts probe

Measures the media contracts the gap map reports open in many apps, on the provider, per build
(ADR-0001). It decodes a one-second clip bundled as an asset (`assets/clip.mp4`: 160x120 H.264 at
10 fps with a 1 kHz AAC tone, made with ffmpeg; and `assets/clip-320.mp4`, 320x240 H.264 Main profile (as real streams are) at
10 fps without audio, large enough for hardware decoders whose smallest size is above 160x120) and prints one line per contract, named by the
gap-map row it measures:

    [WL-CONTRACT] <row id> PASS <what worked>
    [WL-CONTRACT] <row id> FAIL <exception or wrong answer>
    [WL-CONTRACT] done

| row | the check |
|---|---|
| `jni:android.media.MediaMetadataRetriever` | `setDataSource`, the duration, and a frame at 0 |
| `jni:android.media.MediaExtractor` | `setDataSource`, the tracks, and a first sample |
| `jni:android.media.MediaCodec` | an AVC decoder created, configured and started, and an input buffer within 1 s |
| `jni:android.media.ImageReader` | a YUV_420_888 reader with a valid surface |
| `jni:android.media.AudioTrack` | a 48 kHz stereo 16-bit track that plays 100 ms |
| `media:decode-file` | the clip's video decoded through MediaExtractor and MediaCodec (no row of its own) |
| `media:decode-hw` | the 320x240 clip decoded the same way, which reaches a hardware decoder where the device has one (no row of its own) |
| `media:decode-surface` | the 320x240 decode rendered into a Surface over a SurfaceTexture, which must report a frame (no row of its own) |

`probes/run_suite.py` records each line as a result of its own, and `gap-map --probe-results` applies
it to the row it names. Build with `./build.sh`; the APK is pinned in the launcher's
`app-inputs.lock.json` as `media-contracts-probe`.
