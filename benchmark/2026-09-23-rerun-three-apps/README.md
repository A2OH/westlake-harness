# Three apps re-run against the current provider

Wikipedia, McDonald's and Toutiao launched on the same build, after a day of fixes, to answer one
question: where is each actually blocked? Every previous answer for two of the three turned out to
describe a symptom rather than a cause.

Provider: Westlake `532633d`, framework build 26 (`update_service_v2=false`), bionic shim with
WebView library resolution and the font root derived from the staged runtime. SELinux enforcing.

## Where each app stands

| App | Reaches | Blocked at | Confidence |
|---|---|---|---|
| Wikipedia | launch → onboarding → feed → **article with rendered, scrolling web content** | not blocked on this path | high |
| McDonald's | sign-in → welcome → **home dashboard**, five bottom tabs | "Start an Order": `setChecked` on a null `MenuItem` | high on site, low on cause |
| Toutiao | **full feed chrome**, nine category tabs, bottom navigation, empty content area | unknown — the content area is empty and nothing in the log explains it | low |

## Toutiao: one blocker closed, one self-inflicted, one still open

**The libc++ namespace collision is closed.** `libvision_core.so` failed to relocate
`_ZNSt6__ndk19to_stringEi` — the NDK's libc++ namespace, which the board's `libc++_shared.so` does
not have. The APK ships its own copy exporting exactly that symbol; the board's copy wins the
search path.

Isolating `libc++_shared.so` alone does **not** fix it: both copies stay mapped and the failure is
unchanged, because the library that needs the symbol is still outside the isolated namespace. It
takes the failing library *and* the shadowed one together — `libvision_core.so` plus
`libc++_shared.so` — after which `libvision_core.so` maps and its load failure is gone. This is
the `load:shadowed-by-board` row, and the fix is a launch flag rather than code.

The set matters in both directions, which is the part this run got wrong the first time; see the
retraction below.

**What that uncovered — and a retraction.** With `libvision_core.so` loading, the app renders its
whole feed chrome — search bar, nine category tabs, bottom navigation — with an empty content
area. Nothing in this run's log mentions device registration — but the prior diagnosis of that
blocker is not unverified, it is simply not visible from the log. It was established earlier by
dumping the feed adapter (no article cells at all, only chrome), by logging every
`IConnectivityManager` call, and by confirming DNS, routing and TCP all work, and it names the
likely cause as the app's anti-abuse layer rejecting the environment.

An earlier version of this record named a null function pointer in `libtttext_lite.so` as
Toutiao's blocker, at ~85% confidence. **That was wrong, and self-inflicted.** The crash appears
only when 67 libraries are isolated:

```
SIGSEGV(SEGV_MAPERR)@0
#00 pc 0x0  Not mapped
#01 libtttext_lite.so
```

`libtttext_lite.so` has seven weak undefined `pthread_*` references. A weak symbol that does not
resolve binds to **zero** rather than failing the load, so calling it lands at address 0. Those
references resolve in the default namespace and not in the isolated one, so isolating the library
created the crash. Neither the non-isolated run nor the two-library run shows it.

**The set was the wrong closure.** 67 is every library that *reaches* `libc++_shared.so` through
`DT_NEEDED` — a reverse closure. The fix needs the *forward* closure of the library that actually
failed, which is `libvision_core.so` plus `libc++_shared.so`. Measured:

| isolation set | `libvision_core.so` | `libtttext_lite.so` | fatal |
|---|---|---|---|
| none | load failed | fine | 0 |
| **2 (forward closure)** | **loads, mapped** | **fine** | **0** |
| 67 (reverse closure) | loads | SIGSEGV@0 | 1 |

Isolating more than necessary is not free, which is the general lesson: `--android-native-target`
changes which libraries a library can see, and that cuts both ways.

### The empty feed is not a transport failure

No app-level network instrument was needed, because the OS owns the sockets. `/proc/<pid>/net/tcp6`
shows Toutiao's own uid holding four HTTPS connections, three ESTABLISHED and unchanged across
samples, with 23 socket fds. The app reaches its servers, completes TLS and goes idle: it is not
retrying and not failing to connect.

One peer reverse-resolves to `ec2-…us-west-2.compute.amazonaws.com` — an overseas edge for an app
whose content APIs are domestic. That does not replace the earlier diagnosis, it sharpens it: the
environment being rejected may include where the device appears to be, not only what it reports
itself to be. An empty feed may therefore be the backend's correct answer to an unregistered,
out-of-region device, in which case it is not a platform gap and no shim can fix it. Deciding that
needs the response body, which is inside TLS.

Worth recording as process: this transport check re-derived a conclusion already written down,
including an explicit note not to re-investigate connectivity. The cost of not reading the whole
prior record was several launches.

This is worth stating as a rule: **an app showing no content is only a platform gap if the platform
caused it.** Counting this one before the response is read would inflate the map with something
Westlake cannot supply.

The board has no `xt_qtaguid` or BPF accounting, so per-uid byte totals are unavailable, and the
netns TCP counters are system-wide — they cannot be attributed to one app.

## McDonald's: M3 confirmed, M4 corrected

**M3 reproduces**, with a stack the earlier record did not have:

```
NullPointerException: 'MenuItem.setChecked(boolean)' on a null object reference
  at McDBaseActivity.showSelector(SourceFile:9)
  at orderv2.navigation.entry_points.NavHostActivity.showSelector
  at NavHostActivity$onCreate$1$1$1$1.invokeSuspend
```

The ordering host asks the bottom-navigation menu for an item during `onCreate`, gets null, and
calls `setChecked` on it. It is an uncaught exception on a coroutine thread, so the process
survives and the ordering flow simply never renders.

This narrows M3. The record said the menu was empty; **it is not** — the dashboard shows all five
tabs, so the configuration loaded. What is null is the one item `NavHostActivity` expects. Which
item, and why that one is absent, is still open.

Tapping the **Order** tab does nothing at all and raises no exception; only "Start an Order"
reaches the failure.

**M4 is not a blocker.** The record states the upgrade dialog "cannot be dismissed" because it is
laid out wider than the display and its OK button sits off the right edge with no working back
key. The button survives the clip and responds at x≈1045: tapping it dismisses the dialog and the
welcome screen proceeds normally. The layout defect is real; the blocker was not.

## What the new runtime-lookup check adds

`sym:runtime-resolved` reports platform entry points an app reaches by name rather than by
declaring them. Against the two MVP apps:

| | Toutiao | McDonald's |
|---|---|---|
| arm64 libraries | 138 | 10 |
| candidates not supplied | 67 | 50 |
| by NDK library | `libmediandk` 36, `libandroid` 24, `libnativewindow` 7 | `libneuralnetworks` 37, `libandroid` 8, `libnativewindow` 5 |

McDonald's existing map has 92 rows and 40 gaps, of which **two** are native-symbol gaps. Its ML
stack probes 37 NNAPI entry points and falls back to CPU when they are absent, with no crash and
no log line.

These are candidates, not gaps: they are `unresolved` with `decidable_by=probe`, because a string
of the right shape may never be passed to `dlsym`. `probes/runtime-resolve` decides them.

## Method notes

- **Read the faultlog, not the app's stderr.** `/data/log/faultlog/temp/cppcrash-<pid>-*` carries
  `Reason:` and a full frame list; the stderr prints `Backtrace:` followed by nothing. Both
  native crashes here were diagnosed there and neither was diagnosable without it.
- **Wait for the process to exit before counting anything.** Three separate conclusions this
  session were artefacts of grepping a log while the run was still in flight, and
  `ps | grep -c appspawn-x` counts spawners, not the child.
- **The last-logged error is usually adjacent, not causal.** Two fixes on Wikipedia's article path
  cleared their error and left the fault byte-identical. What found the real one was reading the
  settled log's whole tail: four consecutive font-configuration failures, which explained a null
  dereference while drawing text in a way one line never could.
