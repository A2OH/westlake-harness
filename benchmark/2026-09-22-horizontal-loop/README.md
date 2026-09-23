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
