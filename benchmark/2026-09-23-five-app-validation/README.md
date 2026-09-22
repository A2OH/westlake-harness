# Five apps, five runtimes: does the process hold outside the apps it was built on

Every check in this harness was written after watching McDonald's or Burger King fail. Both are
React Native apps on the same provider, so the checks have never faced a different engine. This
corpus is five apps chosen for the runtimes they carry, scanned and mapped before any of them was
launched, with the predictions committed first.

| App | Version | Stack | Native libraries |
|---|---|---|---|
| LocalSend | 643 (F-Droid) | Flutter | `libflutter.so`, `libapp.so`, a Rust library |
| VLC | 3.7.1 | native C/C++ media engine | `libvlcjni.so`, `libvlc.so`, `libmla.so` |
| Wikipedia | 2.7.50606 (F-Droid) | Java/Kotlin only | `libmaplibre.so` for maps |
| Firefox | 156.0, target SDK 37 | Gecko | `libxul.so` and 17 more |
| Subway Surfers | 3.69.1 | Unity with IL2CPP | 20, including `libunity.so` |

Provider: Westlake `02cbace`, SELinux enforcing. Maps in [maps/](maps), predictions in
[predictions.json](predictions.json).

## What the maps say, before any launch

| App | Rows | Hard gaps | The map's headline |
|---|---|---|---|
| LocalSend | 55 | 13 | `libflutter.so` will not load: `ANativeWindow_lock`, `ANativeWindow_unlockAndPost`, `__openat_2` |
| VLC | 68 | 18 | every native import resolves, but `libc++_shared.so` is shadowed by the board's copy: four libraries need the isolated namespace |
| Wikipedia | 57 | 17 | first screen should work; the article WebView needs a renderer process that direct launch cannot start |
| Firefox | 87 | 30 | `libxul.so` will not load: 60 unresolved imports, `AHardwareBuffer`, `AImageReader`, `AMediaCodec` |
| Subway Surfers | 95 | 28 | `libunity.so` will not load: `__system_property_read` and the `AMEDIAFORMAT_KEY_*` symbols from `libmediandk` |

Three of the five are predicted to die at startup on native symbol resolution, one only if launched
without the isolation the map itself lists, and one is predicted to reach its first screen and die
later, on an article.

## Already learned, before the board was touched

Two of the five downloads were **32-bit packages** with an arm64 filename: APKPure's "arm64-v8a"
bundle for Wikipedia ships `config.armeabi_v7a.apk`, and the Flutter app originally chosen carried
only `armeabi-v7a` in its base. Both would have failed on the board for an uninteresting reason.

The scan said so plainly — `abi_status: target-abi-unavailable, available_abis: [armeabi-v7a]` —
and it was in the output before any prediction was written. Nobody read it. The corpus was rebuilt
from F-Droid, which publishes arm64 builds, and the Flutter slot became LocalSend.

That is the same failure mode the harness exists to prevent, one level up: the evidence was
collected and not consulted. It is recorded here because the next person will do it too.

## Scoring

Added after the launches, without editing the predictions.
