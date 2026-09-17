# Running-app-processes white-box probe

This probe exercises `ActivityManager.getRunningAppProcesses()` twice: first from
`Application.onCreate()` (matching X's first blocker), then from `Activity.onCreate()`.
It records whether the result is null and whether it contains the caller's PID, UID, and
process name.

The Android API permits a null result only when there are no running processes. During either
probe phase the caller is itself a running process, so the conformance oracle is a non-null list
containing the caller. An empty list is insufficient even though it avoids X's Kotlin null check.

Build with:

```bash
./build.sh
```

Run the same signed APK unchanged on a stock Android control and Westlake. Compare the two
`[WL-RUNNING-PROCS]` markers rather than accepting launch survival alone.
