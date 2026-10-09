# Conformance queue

369 gap maps. Median open rows per app: 15. Measured: 5235 of 8253 app-specific open rows (63%). Provider rows, counted apart: 4.

| rank | row | apps | measured | effort | score | the probe's finding |
|---|---|---|---|---|---|---|
| 1 | `svc:audio` | 288 | broken | S | 144.0 | the probe found it broken: FAIL answers Android would not give: maxVolume=0 volume=0 sampleRate=48000 framesPerBuffer=1024 outputs=0 focus=0 ringerMode=0 |
| 2 | `pm:call:setComponentEnabledSetting` | 268 | broken | S | 134.0 | the probe found it broken: FAIL disabled activity still resolves (1 found) |
| 3 | `pm:call:getComponentEnabledSetting` | 261 | broken | S | 130.5 | the probe found it broken: FAIL read back 0 after disabling, not 2 |
| 4 | `jni:android.view.KeyCharacterMap` | 246 | broken | S | 123.0 | the probe found it broken: FAIL KEYCODE_A -> 0, events for "ab" 0 |
| 5 | `svc:jobscheduler` | 216 | broken | S | 108.0 | the probe found it broken: FAIL scheduled (pending=false) but never ran in 15 s |
| 6 | `wm:window-placement` | 318 | broken | M | 79.5 | the probe found it broken: FAIL dialog at 40,0 size 640x651 on a 1200 px screen (centred x=280); the alert at 0 to 1140 |
| 7 | `pm:call:queryIntentContentProviders` | 313 | broken | M | 78.2 | the probe found it broken: FAIL no provider for its own filter ([]) |
| 8 | `jni:android.media.MediaMetadataRetriever` | 282 | broken | M | 70.5 | the probe found it broken: FAIL java.lang.UnsatisfiedLinkError: No implementation found for void android.media.MediaMetadataRetriever.native_init() (tried Java_ |
| 9 | `pm:call:queryIntentActivityOptions` | 278 | broken | M | 69.5 | the probe found it broken: FAIL no activity for its own filter ([]) |
| 10 | `svc:media_metrics` | 84 | broken | S | 42.0 | the probe found it broken: FAIL no MediaMetricsManager |
| 11 | `svc:biometric` | 80 | broken | S | 40.0 | the probe found it broken: FAIL no BiometricManager; Android always has one, even without a sensor |
| 12 | `wm:dim-behind` | 318 | unmeasured | M | 39.8 |  |
| 13 | `pm:call:queryBroadcastReceivers` | 145 | broken | M | 36.2 | the probe found it broken: FAIL no receiver for its own filter ([]) |
| 14 | `svc:grammatical_inflection` | 62 | broken | S | 31.0 | the probe found it broken: FAIL no GrammaticalInflectionManager |
| 15 | `jni:android.media.ImageReader` | 115 | broken | M | 28.8 | the probe found it broken: FAIL java.lang.UnsatisfiedLinkError: No implementation found for void android.media.ImageReader.nativeClassInit() (tried Java_android |
| 16 | `jni:android.media.PublicFormatUtils` | 115 | unmeasured | S | 28.8 |  |
| 17 | `jni:android.media.MediaExtractor` | 112 | broken | M | 28.0 | the probe found it broken: FAIL java.lang.UnsatisfiedLinkError: No implementation found for void android.media.MediaExtractor.native_init() (tried Java_android_ |
| 18 | `jni:android.media.MediaCodec` | 110 | broken | M | 27.5 | the probe found it broken: FAIL java.lang.IllegalStateException: video/avc gave no input buffer in 1 s at org.westlake.probe.media.MainActivity.lambda$runAll$2( |
| 19 | `policy:lnk_file` | 184 | unmeasured | M | 23.0 |  |
| 20 | `load:shadowed-by-board` | 45 | unmeasured | XS | 22.5 |  |
| 21 | `java:Media store` | 125 | unmeasured | verify | 20.8 |  |
| 22 | `jni:android.media.MediaCrypto` | 71 | unmeasured | S | 17.8 |  |
| 23 | `window:surfaceview-opacity` | 59 | unmeasured | S | 14.8 |  |
| 24 | `svc:download` | 58 | unmeasured | S | 14.5 |  |
| 25 | `jni:android.graphics.pdf.PdfDocument` | 57 | unmeasured | S | 14.2 |  |
| 26 | `jni:android.os.storage.StorageManager` | 55 | unmeasured | S | 13.8 |  |
| 27 | `svc:print` | 73 | unmeasured | verify | 12.2 |  |
| 28 | `jni:android.hardware.camera2.utils.SurfaceUtils` | 46 | unmeasured | S | 11.5 |  |
| 29 | `svc:vibrator_manager` | 65 | unmeasured | verify | 10.8 |  |
| 30 | `svc:textservices` | 42 | unmeasured | S | 10.5 |  |
