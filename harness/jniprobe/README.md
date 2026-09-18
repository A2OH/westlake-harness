# jniprobe — runtime JNI, `dlopen` and `dlsym` capture

Static reading of an APK cannot see code delivered after install, libraries whose registration
tables are built at runtime, or names resolved through `dlsym`. This agent records all three from
a running process, and `westlake-apk-gap native-capture-diff` joins the result to the static
`native-surface` scan of the same APK.

What it hooks:

| Hook | Recovers |
|---|---|
| `RegisterNatives` | the full `{name, signature, function}` table per class, with the owning library |
| `dlopen` / `android_dlopen_ext` | every library and code object actually loaded, including ones absent from the APK |
| `dlsym` | dynamically resolved names **and the ones that fail**, which is ART's unbound-native fallback |

## Running it

```
pip install 'frida==17.9.1' frida-tools          # host side; must match the server
adb push frida-server /data/local/tmp/ && adb shell su -c '/data/local/tmp/frida-server &'
ADB=adb PKG=<package> ACT=<package>/<activity> python run_scenario.py capture.jsonl
```

`run_scenario.py` force-stops the app, launches it, attaches, then drives a fixed scenario
(settle, scroll, each bottom tab, return) so two runs are comparable. `run_attach.py` is the bare
version for an app already running. Requires root on the device.

## Four things that will waste a day if you rediscover them

1. **Frida 17 removed the legacy APIs.** `Module.findExportByName(null, ...)`, `Process.findModuleByName`
   and the global `Java` bridge are all gone. This agent uses `Module.findGlobalExportByName` and
   reaches ART through the raw JNI vtables, so it needs no bridge and no `frida-compile` step.
2. **Spawn injection does not work on a Magisk device.** `device.spawn()` dies in zygote
   specialization with `selinux_android_setcontext(...) failed`; with SELinux permissive it instead
   gets killed by ActivityManager with `start timeout`. Attach after launch. The cost is the first
   second of process life, which is why `run_scenario.py` launches and attaches in one step.
3. **`GetEnv` returns `JNI_EDETACHED` (-2)** for the agent's own thread. Call `AttachCurrentThread`
   (JavaVM vtable index 4), read the `RegisterNatives` pointer out of the JNIEnv table (index 215),
   then detach. The table is process-wide, so one hook covers every thread and every library.
4. **Hooking `dlsym` at startup costs the app its attach budget.** It fires thousands of times while
   libraries load, and the added latency makes ActivityManager kill the process for failing to
   attach within 10s. The hook is therefore installed on demand through `rpc.exports.enabledlsym()`,
   after startup has settled.

## Known limitation

`clazz` comes back as `?`. The class-name lookup builds `FindClass` / `GetMethodID` /
`CallObjectMethod` from the JNIEnv table and does not resolve on Android 11; method names,
signatures and owning libraries are unaffected. Until it is fixed, a method's Java class has to be
inferred from the library and the signature.
