# The media natives: what to port, in what order

The largest family of open gap-map rows is `android.media`'s JNI half: classes the runtime
declares but never registers, so the first call into one throws `UnsatisfiedLinkError` — and for
the classes whose static initializer calls `native_init`, the class itself dies and takes the app
with it. This note ranks them by the reach measured on the HK top-1000 corpus
(`2026-10-25-hk-top1000-static-baseline`, 982 maps) and names the OpenHarmony API each one can be
built on, so the order of work follows the evidence rather than the order apps were launched in.

## Reach

`reach` is the number of the 982 maps that carry the row; `calls` is how many of those call the
class directly (the rest reach it through a library). Both come from the maps, not from launches.

| row | reach | calls | unregistered | OH counterpart |
|---|---|---|---|---|
| `jni:android.media.MediaMetadataRetriever` | 932 | 923 | 13 of 13 | `OH_AVMetadataExtractor` (metadata, album cover) + `OH_AVImageGenerator` (frame at a time) |
| `jni:android.view.KeyCharacterMap` | 912 | 912 | 2 of 14 | the runtime registers the rest; only `nativeApplyOverlay` is open |
| `jni:android.media.MediaCodec` | 857 | 857 | 26 of 46 | `OH_AVCodec` video/audio decoder and encoder (`native_avcodec_*`) |
| `jni:android.media.AudioTrack` | 783 | 783 | 17 of 54 | the bridge plays through OHAudio; the open ones are buffer sizing and loops |
| `jni:android.media.ImageReader` | 756 | 756 | 10 of 10 | `OH_ImageReceiver` / `OH_NativeImage` over a producer window |
| `jni:android.media.PublicFormatUtils` | 750 | 0 | 3 of 3 | format translation only, no OH call needed |
| `jni:android.renderscript.RenderScript` | 729 | 729 | 128 of 128 | none: RenderScript has no OH equivalent (and is deprecated on Android) |
| `jni:android.media.MediaExtractor` | 705 | 705 | 26 of 26 | `OH_AVSource` + `OH_AVDemuxer` |
| `jni:android.media.MediaDrm` | 662 | 662 | 35 of 43 | none: no DRM plugin; answered truthfully as "no scheme supported" |
| `jni:android.media.MediaCrypto` | 619 | 619 | 1 of 7 | as above |
| `jni:android.media.MediaMuxer` | 357 | 357 | 8 of 8 | `OH_AVMuxer` |
| `jni:android.media.MediaParser` | 300 | 300 | 1 of 1 | its own extractor; can sit on `MediaExtractor` |

## What that ordering says

1. **MediaMetadataRetriever first.** The highest reach of any open row in the corpus, the smallest
   surface of the big ones (13 natives), and OH has a near-exact counterpart. A title, a duration
   or a thumbnail is what most of those 923 callers want.
2. **MediaExtractor next.** It is the other half of "read a media file", it has a direct OH
   counterpart, and `MediaParser` (300) can be answered through it later.
3. **MediaCodec after those two**, and the three together are what `media:decode-file` needs: an
   app that decodes a clip itself (every video feed, every short-drama app) needs all three.
4. **ImageReader** is the camera and GPU-readback path; it matters once camera work starts.
5. **RenderScript, MediaDrm and MediaCrypto are not ports.** RenderScript has no OH counterpart
   and 128 natives; the truthful answer for all three is the one AOSP's own JNI gives on a device
   without the service, which is what the runtime answers today. An app that *requires* DRM
   playback cannot be made to work here, and the map should say so rather than imply a port.

Two accidents of measurement to keep in mind when reading the table: `PublicFormatUtils` has a
reach of 750 and no direct callers, because the framework reaches it on the app's behalf; and
`AudioTrack`'s 17 open natives are the ones the native bridge's own registration leaves out, not a
missing port.

## How a port is accepted

`probes/media-contracts` exercises one row per line on the board
(`jni:android.media.MediaMetadataRetriever`, `MediaExtractor`, `MediaCodec`, `ImageReader`,
`AudioTrack`, and `media:decode-file`), so each port has an acceptance test that is independent of
any one app: run the probe, and the row's result in `benchmark/conformance/probe-results.json`
flips from `fail` to `pass`. An app launch is then the second check, not the first.
