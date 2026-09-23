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

---

# Round 4: new scoring, and the shim change validated at corpus scale

Two things changed. The loop stopped being scored on whether an app rendered, and the shim fix
from round 3 was finally run against all ten rather than the four it had been tested on.

## Why the old criterion had to go

Round 3's fix cleared two SIGTRAPs and took fourteen symbol-load failures to zero in both apps.
**Neither rendered.** Scored on rendering, a fix that was traced to a specific commit-ordering
regression reads as a failure and becomes a candidate for reverting. Meanwhile Aegis and
AntennaPod rendered before any of this work and would have rendered without it, so on the same
criterion they look like evidence while carrying none.

`harness/westlake_gap/lifecycle.py` replaces it with how far the process got:

```
spawned → runtime-init → bound → activity → view → drawing
```

Each rung was kept only if it separated apps whose outcome was already known from a screenshot.
`DecorView` turned out to be the cleanest marker for a built view hierarchy — present in every
confirmed-rendering app, absent in every app that stopped earlier.

## What the new scoring immediately caught

It disagreed with this file. Round 2's entry for anki names the `ASurfaceTransaction` SIGTRAP as
its blocker; the scorer, taking the **first** blocker by position rather than the loudest, found
AnkiDroid's crash-report dialog failing two hundred lines earlier. The SIGTRAP was downstream.

It also refuses to call AntennaPod's missing `nPurgePendingResources` a blocker, because AntennaPod
is on the top rung with no fatal signal. Ranking that would repeat the mistake this file already
records about ranking service stubs by how many apps ask for them.

## And then it was wrong, in a way worth keeping

The first comparison it produced called anki **unchanged** between rounds — same rung, same
blocker string — while anki's fatal signal had gone 1 → 0 and its log had grown two hundred lines.
Rung alone is too coarse. `compare()` now reports movement inside a rung, and clearing a fatal
signal is called out explicitly.

That is the same failure as the criterion it replaced, one level down: a coarse pass/fail hiding
real movement. Worth recording rather than quietly patching, because the next coarse metric will
fail the same way.

## The round

```
build framework-signin-device28 · shim bionic-shim-nw2 · all ten · 0 harness faults
```

| rung | apps |
|---|---|
| 5 drawing | aegis, antennapod, markor |
| 3 activity | anki |
| 2 bound | mindustry, newpipe, opencamera, ppsspp, termux |
| 1 runtime-init | ooniprobe |

| | round 2 (nw1) | round 4 (nw2) |
|---|---|---|
| apps taking a fatal signal | 2 | **0** |
| `ASurface` load failures, corpus-wide | 28 | **0** |
| rung regressions | — | **0** |

- **anki** — same rung, `fatal 1→0`, +200 lines
- **newpipe** — same rung, `fatal 1→0`, +70 lines, blocker changed from
  `ASurfaceControl_createFromWindow` to a `NullPointerException` starting the activity
- everything else unchanged, which is the control: seven apps that had nothing to do with the
  change came back identical

**The shim reordering is validated at corpus scale.** It alters library resolution for every
WebView caller, which is why four apps were not enough, and across ten no app lost a rung.

## What the ranking now says

Two apps stop on a null system-service manager — ooniprobe on `LocaleManager`, newpipe on
`BatteryManager` (now its first blocker, previously hidden behind the SIGTRAP). Same mechanism,
`LocalServiceBinders.get(name)` is the existing pattern. That is the next target, and it is the
second time the loop has produced one by the same rule: fix what repeats, count only what blocks.

Round 4 also ran with **zero harness faults**, against one in each of the two previous rounds.

---

# Round 5: two apps to drawing, and the scorer wrong twice more

Target picked the same way as the last two: the blocker hit by more than one app. OONI Probe and
NewPipe both stopped on a **null system-service manager** — `LocaleManager` and `BatteryManager`.
One mechanism: `getSystemService` returns null when a fetcher cannot find its binder, and the NPE
lands wherever the app first touched it.

```
apps drawing: 3 -> 5
ooniprobe  1 runtime-init -> 5 drawing   (+4, screenshot confirmed)
newpipe    3 activity     -> 5 drawing   (+2, markers only)
```

## Reading the fetcher beats reading the stub tally

`BatteryManager`'s fetcher calls `getServiceOrThrow` **twice** — `batterystats` and
`batteryproperties` — and throws if either is missing. Only `batterystats` ever appeared in a log.
Registering the name the logs showed would have changed nothing, which is a concrete instance of
the ranking error this file already warns about: the visible symptom is not the requirement.

## What the new binders are allowed to claim

A locale override is accepted, dropped, and read back as absent. That is truthful for a board with
no per-app locale database rather than a placeholder — an app that sets one and reads it back sees
exactly what a user who never chose one would see. Battery reports a full idle cell and a non-zero
status for ids it does not know, which is what real hardware returns for unsupported properties.
Those values are **invented, not read from OH**, and the code says so: the board does expose
battery state, and wiring it through is worth doing later.

## The scorer failed twice more, and both were found by using it

1. **A weak marker vetoed strong evidence.** The ladder stopped at the first unmet rung, so NewPipe
   — `DecorView`, forty relayouts, `ReliableSurface::reserveNext returning OK`, no fatal — scored
   `bound`. Fixed: score the **highest rung that passes** and report skipped rungs rather than
   letting them cap.
2. **The activity rung was a fitted threshold.** It counted `[B47-SLA]` lines, ten meaning
   "proceeded". That held for one round. NewPipe and OONI Probe drew with five — the same count as
   apps that never reached an activity at all. Counts of a progress log are not a lifecycle signal.
   Fixed: `activity` now means a launch was *attempted*, evidenced by a view existing or by an
   explicit `Unable to start/instantiate activity` failure. termux correctly moves 2 → 3, because
   it does reach activity start and fails on `bindService` inside it.

No marker here separates "reached the activity" from "built a view" on its own. The rung is
inferred from the two outcomes that are visible, and the docstring says so instead of implying
more precision than the logs support.

## NewPipe is not visually confirmed

Its markers are unambiguous and it is recorded as drawing, but there is no screenshot. Two things
got in the way and both are worth writing down:

- An earlier capture filed as NewPipe was **OONI Probe**, still on top of the window stack because
  NewPipe had not put up a window within the wait. Same misattribution as the aegis/antennapod
  mix-up in round 1 — a screenshot proves what is *on top*, not what was launched last.
- The retry found the screen asleep, then the OH **lock screen**, and the device then dropped off
  USB entirely. `results.json` records NewPipe as `confirmed: markers only`.

## Harness faults: a new kind, and the cause was cumulative

markor and opencamera both failed to launch — `recv: Resource temporarily unavailable`, and OH
refusing with *"too many abilities have been launched"*. `/data` was at **95%**: seventy app stages
and seventy source runtimes had accumulated across five rounds, and no round had ever stopped its
children.

Both ran clean after stopping the leftovers and keeping the newest two stages of each kind, and
both scored unchanged. Three rounds in a row have now produced at least one fault that would have
been scored as an app blocker by a loop trusting its own exit codes — and this one was **caused by
the loop itself**, which no single round would have revealed.

## Addendum: NewPipe confirmed

Taken on 2026-09-23 over **wireless debugging** — USB had failed at the physical layer — NewPipe
renders its live feed: real stream titles, channel names and viewer counts fetched from the network,
the tab bar, and its own *Keep Android Open* dialog on top. That is more than the round-5 markers
claimed: it is network I/O and list rendering, not just a surface.

One thing it does not do: thumbnails. Three captures ten seconds apart were the same size and all
show placeholder play icons. That is recorded as an observation, not a diagnosis — it could be image
loading or just a slow network.

Two things lost the capture for a day and are worth knowing: the board dropped off USB entirely
(nothing enumerated, cable/port level), and a WSL restart wiped `/tmp`, taking every staged app input
with it. The inputs were rebuilt from the launch archives each run keeps, and every APK was checked
against its pinned SHA-256 by `prepare_app.py`, so what ran is provably what ran before.

---

# Round 6 (targeted): Termux reaches its UI

Asked for one more app on screen. Termux was the cheapest: one step short, with a concrete blocker.
It took two gaps, the second hidden behind the first.

1. **`bindService` under direct launch.** Direct launch installs a proxy `IActivityManager` that
   answers every method it does not special-case with the type default. `bindService` → `0` →
   `ContextImpl` reads "bind failed" → Termux throws from `onCreate`. The adapter already binds
   in-app services in process, but direct launch never reaches that adapter. Fixed by routing
   own-package binds from the stub to the same `InProcessServiceBinder`.
2. **`"audio"` answered by name.** Past `onCreate`, `onResume` builds a `SoundPool`. Every
   `SoundPool`/`MediaPlayer`/`AudioTrack` is a `PlayerBase`, and `PlayerBase` fetches its own copy of
   `IAudioService` from `ServiceManager`. The existing audio stub was stamped into `AudioManager`'s
   cache only, so `PlayerBase` got null. Answering the name gives every cache the same binder.

```
build framework-signin-device31 · termux: 3 activity -> 5 drawing (screenshot)
```

**What it does not do yet:** the terminal area is empty. First-run Termux should show its bootstrap
installer, then a prompt. That goes through its own native `libtermux.so` and bootstrap zip and is
**not diagnosed**. A check from the global shell for its data directory was inconclusive for the
namespace reason recorded elsewhere, so no cause is claimed.

Second gap worth noting for the map: the audio one is not Termux-specific. Any app that plays a
sound through the standard players hit it.

Also fixed along the way: both deployers sent files with a flat 55 s timeout, which held over USB
and failed over wireless debugging. Send timeouts are now sized from the file.
