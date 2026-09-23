# Ten apps, one launch each: what breadth finds that depth does not

Launch every app in the corpus once against one build, record the **first** blocker, and do not
iterate on any of them. Then fix what repeats.

The point is not throughput. It is that a blocker hit by one app is indistinguishable from an app
bug until a second, unrelated app hits the same one. Depth-first cannot make that distinction at
all — it fixes whatever is in front of it, and the map it leaves behind says "markor needed X"
rather than "X is missing".

```
build framework-signin-device27 · shim bionic-shim-nw1 · 2026-09-22
10 launched · 2 rendering · 0 UnsupportedOperationException
```

| app | outcome | first blocker | category |
|---|---|---|---|
| **aegis** | **rendering** (screenshot) | — | — |
| **antennapod** | **drawing** (22 relayouts) | — | — |
| markor | bind failed | `Couldn't find meta-data for provider with authority …markor.provider` | package-manager |
| anki | bind failed | `…with authority com.squareup.leakcanary.fileprovider.com.ichi2.anki` | package-manager |
| ooniprobe | bind failed | `LocaleManager.setOverrideLocaleConfig` on a null service | system-services |
| termux | activity failed | `bindService() failed` | system-services |
| mindustry | init failed | `SL_IID_ANDROIDSIMPLEBUFFERQUEUE: symbol not found` (`libarc.so`) | native-symbols |
| opencamera | init failed | `android.hardware.Camera._getNumberOfCameras` no implementation | native-upcalls |
| newpipe | SIGTRAP | `ASurfaceTransaction_*` unavailable, then abort | native-loading |
| ppsspp | no surface | `held back: no surface until its activity's window has an OH session` | app-framework |

## The one thing that repeated

Nine distinct blockers across ten apps. Eight were hit by exactly one app. One was hit by two:

```
IPackageManager.resolveContentProvider(String authority, long flags, int userId)  ->  null
```

markor and anki share no code, no vendor and no authority string — markor resolves
`net.gsantner.markor.provider`, anki dies on LeakCanary's
`com.squareup.leakcanary.fileprovider.com.ichi2.anki`. Both throw the identical message, because
both reach androidx `FileProvider.parsePathStrategy`, which resolves a provider **by authority**
and throws `IllegalArgumentException("Couldn't find meta-data for provider with authority …")` when
it gets null. Recent androidx does this from `attachInfo`, so the throw lands inside
`handleBindApplication` and takes the whole binding down before any activity starts.

What made it a gap rather than two app bugs is that the adapter already answers the *other* keying:

| lookup | keyed by | state |
|---|---|---|
| `getProviderInfo` → `ProviderInfoResolver.resolve` | `ComponentName` | implemented, populates `metaData` |
| `resolveContentProvider` | authority string | `logStub` + `return null` |

Same component set, same manifest parse, same `ProviderInfo` objects — which already carry
`authority` and `metaData`. Only one of the two ways of asking for them was wired up.

**Six of the ten declare a FileProvider authority**: aegis, anki, antennapod, markor, ooniprobe,
newpipe. The four that did not die on it died earlier, so closing this is necessary for them and
sufficient for none — which is the honest claim, and the reason round 2 re-runs all ten rather than
the two that failed here.

## What the loop got wrong, and how that was caught

Two of the ten results in the first pass were not results:

- **anki** did not fail. `hdc` dropped the transport (`connect failed status:-4039`) and the harness
  never spawned a child. Scored as a blocker it would have been a fabricated data point; re-run, it
  produced the finding above. Breadth multiplies setup errors, so every failure has to answer "is
  this mine?" before it is counted.
- **aegis** was recorded as a failed launch from a stale table while a screenshot of *aegis
  rendering* sat unread. The screenshot was being attributed to antennapod.

Both are the same mistake — reporting a run's outcome from something other than that run's own
evidence — and both are why `results.json` records `stderr_lines` per app and lists
`harness_errors_excluded_from_scoring` explicitly.

## What "rendering" means here

`aegis` is confirmed visually. `antennapod` is inferred from 22 `OH_WSA-relayout` entries and two
traversals, with no screenshot taken — a weaker claim, recorded as `drawing` rather than
`launched`.

Note also that **alive is not launched**: ooniprobe and markor processes were still running when
polled, with `Application binding failed; activity launch withheld` in their logs. A liveness check
alone would have scored both as successes.

---

# Round 2: one function, re-run all ten

Build 28 differs from 27 by a single adapter method. Every app was launched again, including the
eight that had nothing to do with the change — because the question "did this break anything" is
only answerable by running the ones you did not aim at.

```
build framework-signin-device28 · 2026-09-22
10 launched · 3 rendering (was 2) · 1 blocker closed · 1 app advanced past bind
```

| app | round 1 | round 2 | |
|---|---|---|---|
| **markor** | bind failed | **rendering** | **closed** |
| **anki** | bind failed | binds, crashes later | **advanced** |
| aegis | rendering | rendering | unchanged |
| antennapod | drawing | drawing | unchanged |
| ooniprobe | bind failed (LocaleManager) | same | unchanged |
| newpipe | SIGTRAP | same | unchanged |
| termux | `bindService()` failed | same | unchanged |
| mindustry | `SL_IID_*` not found | same | unchanged |
| opencamera | Camera native missing | same | unchanged |
| ppsspp | no surface | same | unchanged |

```
[WESTLAKE-PM] resolveContentProvider net.gsantner.markor.provider
              -> androidx.core.content.FileProvider metadata=1
[WESTLAKE-PM] resolveContentProvider com.squareup.leakcanary.fileprovider.com.ichi2.anki
              -> leakcanary.internal.LeakCanaryFileProvider metadata=1
```

Zero `Couldn't find meta-data` throws in either. markor went 390 → 759 stderr lines and rendered;
anki went 410 → 533 and bound successfully.

## The control matters as much as the result

ppsspp, mindustry and termux produced **identical line counts** across both rounds (374, 448, 411)
and never called `resolveContentProvider` — correct, since ppsspp and mindustry declare no
providers and termux's two carry no meta-data. The change is inert for apps that do not use it,
which is what makes "markor moved" attributable to it rather than to run-to-run variance.

The two apps that were already rendering also stayed rendering (aegis 631 vs 633, antennapod 668
vs 681). Those deltas are the noise floor; markor's +369 is not.

## What closing a blocker reveals

anki did not start working. It stopped failing at bind and began failing **where newpipe fails** —
`ASurfaceTransaction_*` unresolvable through `dlopen("libandroid.so")`, then `SIGTRAP` in
`CrBrowserMain`.

That is the loop's actual product. Before round 2, that gap had one victim and looked like a
NewPipe problem. It now has two, and the second one was *hidden behind* the provider gap — no
amount of staring at anki's round-1 log would have shown it, because anki never got far enough to
reach it. Depth-first on newpipe would have found the same crash and still not known it was shared.

**Next round's target, chosen the same way it was chosen this time: the blocker with the highest
app count.** That is now `ASurfaceTransaction_*` at two, and it is already understood — it is the
`libandroid.so` shadowing documented in `probes/webview-boundaries/`, where the runtime's copy
exports none of the 27 NDK SurfaceControl entry points and the WebView copy exports all of them.

## Second harness error, same discipline

`aegis` failed its round-2 launch with `host_spawn: No such file or directory` — a staging fault,
not a gap. Re-run, it rendered as before. That is two harness faults in twenty launches (anki in
round 1, aegis in round 2), both of which would have been scored as app blockers by a loop that
trusts its own exit codes. Breadth makes these more likely, not less, so the rule holds: **a
failure is not a result until it has been shown not to be ours.**

---

# Round 3: the target turned out to be our own dead code

Round 2 named `ASurfaceTransaction_*` as the next target because it had two victims. Investigating
it before building anything changed what the fix was — and nearly produced a wrong answer first.

## The wrong answer, and why it was wrong

The first inventory said there was **one** `libandroid.so` on the search path and it exported all
fourteen symbols Chromium wanted, which would have made this a resolution mystery with no obvious
fix. That reading came from `hdc shell ls /data/local/tmp/asx/...`.

That path is not the app's. Inside the child's mount namespace it is bind-mounted from
`/data/app/el2/.../a2hlab-source-<hash>`; from a shell it is a stale shared directory with 20,875
entries dated three weeks earlier. `probes/runtime-resolve/README.md` documents this exact trap,
and the first pass walked into it anyway. **Any claim about what the app can load has to be made
against the staged runtime or through the namespace helper, never through the global path.**

Re-measured against the real runtime:

| copy | position on search path | defined FUNC | `ASurface*` | of the 14 wanted |
|---|---|---|---|---|
| runtime `libandroid.so` | **first** | 117 | **0** | **0** |
| `webview-t-lib/libandroid.so` | **last** | 115 | 27 | **14** |

So `dlopen("libandroid.so")` succeeds against the runtime copy and every `dlsym` returns null.
That is the shadowing `probes/webview-boundaries/` describes, and the shim already has a redirect
written for it.

## Why the redirect never ran

It logged `library resolved` **zero** times. The `.z.so` naming fallback was added after it and
placed above it, and opens the plain name first:

```c
void *plain = real_dlopen(filename, flags);
if (plain != NULL) {
    return plain;          // the runtime's copy — always succeeds
}
```

Every name in the WebView directory also exists in the runtime directory — the redirect's own
comment says so — so the plain open always succeeded and the function returned before reaching the
redirect. It was dead code for exactly the libraries it was written to fix, and silent about it.

Two correct changes, wrong order. Fixed by moving the redirect first and having the `.z.so` probe
open `actual_filename`.

**Redirecting per caller is still right.** The two copies share only 34 symbols; sending every
caller to the WebView copy would lose 83, the `ACanvas`, `AHardwareBuffer` and `ALooper` families
among them. The pre-existing design was correct — only unreachable.

## Result

| app | before | after |
|---|---|---|
| newpipe | SIGTRAP, 14 load failures | **no signal, 0 failures**, 462 → 525 lines |
| anki | SIGTRAP, 14 load failures | **no signal, 0 failures**, VSYNC ticking, storage answering |
| wikipedia | rendering | rendering, `fatal=0`, no regression |
| aegis | rendering | rendering, 637 vs 631/633, no regression |

Neither target renders yet. Both moved to new and *different* blockers, which is the expected shape.

## Two things this round does not establish

- **The shim change was not validated at corpus scale.** It alters library resolution for every
  WebView caller and only four apps were run against it. A full ten-app round at this shim has not
  been done.
- **Wikipedia did not exercise the redirect.** It fired zero times there, because the launch starts
  the app without opening an article. Wikipedia shows the reordering broke nothing; it does not
  show the redirect helps it.

## Next target, and a correction to how to rank

Two apps now die on a **null system-service manager** — ooniprobe on `LocaleManager`, newpipe on
`BatteryManager`. Different services, one mechanism: `OHServiceManager` has no binder for the name,
`getSystemService` returns null, the app dereferences it unchecked. `LocalServiceBinders.get(name)`
is the existing pattern, already carrying `account`, `power`, `alarm` and `clipboard`.

The ask-counts are tempting and misleading:

```
12 apps ask  network_management, netstats, content_capture, appops  -> null
10 apps ask  accessibility                                          -> null
 4 apps ask  locale                                                 -> null
```

`appops` is asked by all twelve, returns null in all twelve, and kills none of them. A null service
is usually survivable; only the ones an app dereferences without checking are fatal. **Rank by the
fatal subset, not by how many apps ask** — otherwise the map optimises for the loudest stub rather
than the one blocking a launch.
