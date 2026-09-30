# runtime-answers probe

Records, one line each (`[WL-ANSWERS] <name> = <value> (Android: <expected>)`), the startup answers
the top-apps blind batch found wrong or refused on Westlake, so a single launch says which differ
from Android:

- thread priorities: the main thread's, a new thread's, `Process.getThreadPriority`, and
  `Thread.setPriority(own priority)` (Instagram, CapCut);
- service answers: `ActivityManager.getMemoryClass`/`getLargeMemoryClass` (CNN), `WifiManager`
  connection info (NYTimes), `TrafficStats` (Waze, Shazam), `TelephonyManager.listen` (Waze);
- app-storage file operations: `File.setWritable`/`setReadOnly` on files and directories,
  `Os.chmod`, and `System.load` of a library copied into app storage and into each app-data
  directory (WhatsApp, CapCut);
- platform natives: a SAX parse (Telegram), `new MediaRecorder()` (MuseKit), `AudioRecord` minimum
  buffer and 0.5 s of microphone capture (MuseKit), and NDK `AAsset_openFileDescriptor` on an
  uncompressed asset, the path Meta's superpack takes (Facebook, Instagram).

    ./build.sh      # out/runtime-answers-probe.apk (Java, a trivial native library to copy and load,
                    # and libprobeassets.so for the NDK asset check)

## First run (framework 70, 2026-09-29)

| answer | Westlake | Android |
|---|---|---|
| main / new thread priority | 0 / 0 | 5 / 5 |
| setPriority(own priority) | throws "Priority out of range: 0" | ok |
| memory class / large memory class | 16 / 16 | e.g. 256 / 512 |
| WifiManager.getConnectionInfo | null | a WifiInfo |
| TrafficStats.getUidRxBytes | throws "TrafficStats not initialized" | a count or UNSUPPORTED |
| TelephonyManager.listen | NullPointerException (no registry) | ok |
| File.setWritable / setReadOnly | false | true |
| Os.chmod | ok | ok |
| System.load from app storage | errno 13 (execute mapping denied) | loads |

Causes: libart's palette stub never writes a priority (every attached thread reads 0); the
SystemProperties table has no dalvik.vm heap sizes; no netstats, telephony registry or Wi-Fi
connection answer; UnixFileSystem's permission natives fail where chmod works; OH's policy refuses
execute mappings of app data files.

## After the fixes (framework 73, shim nw16, natives override, 2026-09-29)

Priorities, memory class, Wi-Fi, TrafficStats, TelephonyManager and the File/chmod answers match
Android. Also:

| answer | Westlake | Android |
|---|---|---|
| System.load from files/, cache/, no_backup/ | loads (the shim retries from a code_cache copy) | loads |
| SAXParser.parse | `a|b=1|t=é中` | same |
| AAsset_openFileDescriptor | fd ok, bytes match | same |
| new MediaRecorder() | "Unable to initialize media recorder" | constructs |
| AudioRecord 0.5 s from the microphone | not initialized: OH refuses the capturer | samples |

The capturer is refused because the host HAP does not request `ohos.permission.MICROPHONE`.
