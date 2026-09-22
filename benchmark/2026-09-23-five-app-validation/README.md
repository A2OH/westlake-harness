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

Added after the launches; [predictions.json](predictions.json) is unchanged. Details in
[results.json](results.json).

| App | Predicted | What happened | Verdict |
|---|---|---|---|
| LocalSend | `libflutter.so` will not load | it did not: `ANativeWindow_lock`, `ANativeWindow_unlockAndPost`, `__openat_2` are GLOBAL UND | **right**, mechanism and effect |
| Subway Surfers | `libunity.so` will not load | `Unable to load library libunity.so: Error loading shared library libmediandk.so` | **right**, mechanism and effect |
| VLC | dies without namespace isolation, otherwise first screen | died before loading any engine library, on a theme attribute it could not resolve while inflating | **untested** |
| Wikipedia | first screen renders | `AccountManager.get()` returned null in `BaseActivity.onCreate` and the app dereferenced it | **wrong** |
| Firefox | `libxul.so` will not load | it loaded; Gecko ran, then hit the strict user proxy, a window context that is not attached, and an activity result for a record that does not exist | **wrong** (the `svc:user` row was right) |

Two of five headline predictions right, two wrong, one untested. Both correct ones came from native
symbol resolution; both wrong ones were Java and framework side.

### What the misses have in common

None of them is an app-specific accident.

- **Wikipedia**: the account service is reached through `AccountManager.get(context)`. The scanner
  only sees direct `getSystemService` and `ServiceManager` call sites, so the map had **no row at
  all** for a service whose absence killed the app in `onCreate`. Every service with a static
  accessor is invisible the same way.
- **VLC**: nothing in the map models theme or attribute resolution, so an app that cannot inflate
  its own layout has no row to land in.
- **LocalSend**: the second gap, after the predicted one, is that an app cannot map executable code
  out of its own data directory. `sandbox-policy` models fifo and symlink creation, not execute.
- **Firefox**: window context attachment and activity result delivery have no rows either, though
  `app-framework` covers the process table, dialogs and placement.

### Process findings

1. **A map is only valid for a launch configuration, and does not say which.** Firefox was first
   launched without the bionic shim and died on `__register_atfork`, which the map counted as
   resolved *because the shim exports it*. The resolution was generated with the shim in its index
   and never records that dependency. Fix: state the provider inputs a resolution assumed.
2. **Evidence collected and not read.** Two downloads were 32-bit behind an arm64 filename; the scan
   said `target-abi-unavailable` before any prediction was written. Fix: surface `abi_status` in the
   gap map, where predictions are actually made.
3. **Predict the library, not the screen.** The native predictions named the right library both
   times. The Java-side predictions named a screen and were wrong both times, even where the
   underlying row was right.

### One miss already closed

The scanner now treats a static framework accessor as a service request: `AccountManager.get`,
`LayoutInflater.from`, `NotificationManagerCompat.from` and the rest ask the platform for a service
inside the framework, leaving no call site in the app's dex. Rescanning the same Wikipedia build
produces the row that was missing:

```
svc:account | null | M | no Westlake provision: getSystemService returns null
```

That is the row whose absence let the app be predicted as "first screen renders" when it dies in
`onCreate`. The other four gap classes found here — theme attribute resolution, execute from app
data, window context attachment, activity result delivery — do not have rows yet.

### Rows confirmed on apps they were not written for

`svc:user` (written for McDonald's WebView) caught Firefox's `getUserSerialNumber`.
`libc:constant-namespace` reported supplied for VLC and LocalSend, and neither showed a page-size
or limit failure. `load:shadowed-by-board` is still unproven: VLC never reached its engine.
