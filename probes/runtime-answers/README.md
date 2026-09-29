# runtime-answers probe

Records, one line each (`[WL-ANSWERS] <name> = <value> (Android: <expected>)`), the startup answers
the top-apps blind batch found wrong or refused on Westlake, so a single launch says which differ
from Android:

- thread priorities: the main thread's, a new thread's, `Process.getThreadPriority`, and
  `Thread.setPriority(own priority)` (Instagram, CapCut);
- service answers: `ActivityManager.getMemoryClass`/`getLargeMemoryClass` (CNN), `WifiManager`
  connection info (NYTimes), `TrafficStats` (Waze, Shazam), `TelephonyManager.listen` (Waze);
- app-storage file operations: `File.setWritable`/`setReadOnly` on files and directories,
  `Os.chmod`, and `System.load` of a library copied into app storage (Facebook, Messenger, CapCut).

    ./build.sh      # out/runtime-answers-probe.apk (Java + one trivial native library to copy and load)

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
