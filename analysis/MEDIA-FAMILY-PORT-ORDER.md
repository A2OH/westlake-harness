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

## MediaCodec is not missing natives; it has no video

The row reads "26 of 46 natives unregistered", which suggests a partial port. Reading the provider
says something else. The 20 natives the runtime does register come from the bridge's
`framework/core/jni/oh_mediacodec_shim.cpp`, written for one app's MP3 stream:

- `native_setup` creates an **audio** codec (`OH_AudioCodec_CreateByMime`) whatever the type. For
  `video/avc` that call fails, the failure is only logged, and the codec stays null, so
  `dequeueInputBuffer` never returns a buffer. That is exactly the probe's failure: "video/avc gave
  no input buffer in 1 s".
- `MediaCodecList` reports **one** codec, `OH.audio.mp3.decoder`, supporting only `audio/mpeg`. An
  app that asks the list for an H.264 or HEVC decoder — ExoPlayer, every short-video and
  short-drama player — is told there is none. Even AAC is absent from the list, though
  `createDecoderByType("audio/mp4a-latm")` would reach OH's AAC decoder.

So no app can decode video here, and the gap map cannot see it: by its per-native count the class
is mostly there. That is a harness blind spot (the provider's `MediaCodecList` answer should be a
row of its own), and it moves MediaCodec's work from "register the rest" to "a video codec path":
`OH_VideoDecoder` with ByteBuffer and Surface output, `OH_AVCapability` behind `MediaCodecList`, and
the audio path kept. The bridge that holds today's code cannot be rebuilt, so the new path belongs
in `libwl_missing_natives`, whose registrations come after the bridge's and replace them.

It matters out of proportion to its row: of the HK top 100, the short-drama apps alone (DramaBox,
ReelShort, NetShort, FlickReels, DramaWave, BlinkDrama, 红果短剧) exist to play video, and they
are counted as working at the first screen while being unable to play anything.

## What the board's decoders take

Measured with `probes/media-contracts` once the video path existed:

- **The hardware AVC decoder lists Baseline, Main and High, and decodes only Baseline.** On the
  first frame of any Main-profile stream it reports OH error 6 ("unknown error"), whatever the
  level, B-frames, CABAC, or whether the parameter sets arrive in band or in the format. Nearly
  every real stream is Main or High, so an app on the hardware decoder plays nothing (TataLand's
  intro video never decoded). The port answers it by measurement, not by board name: the
  first stream of each AVC profile in a process is preceded by one 176x144 frame of that profile
  through a hardware decoder of its own, and a profile that fails goes to OH's software decoder.
- **The hardware decoders' smallest size is 176x144**, so small clips and thumbnails also go to the
  software decoder, which takes 2x2 up to 4096x4096.
- **There is no software HEVC decoder**, so an HEVC stream the hardware fails has no fallback.
- **In Surface mode OH reports each frame with size 0.** Android reports the frame's size, and
  players drop a size-0 output as empty, so the port reports the frame's YUV size.

That is why the probe's `media:decode-hw` clip is Main profile: a Baseline clip passes on a decoder
that cannot play real video.

## How a port is accepted

`probes/media-contracts` exercises one row per line on the board
(`jni:android.media.MediaMetadataRetriever`, `MediaExtractor`, `MediaCodec`, `ImageReader`,
`AudioTrack`, and `media:decode-file`), so each port has an acceptance test that is independent of
any one app: run the probe, and the row's result in `benchmark/conformance/probe-results.json`
flips from `fail` to `pass`. An app launch is then the second check, not the first.
