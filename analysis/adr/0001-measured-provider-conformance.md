# ADR-0001: Measure provider conformance on every build, and let the gap map read it

- **Status:** accepted
- **Date:** 2026-10-09
- **Implements:** phase 1 of [the end-to-end functional testing plan](../E2E-FUNCTIONAL-HARNESS-PLAN.md)

## Context

The harness has grown in six phases since August:
1. static scanning, and resolving an APK's imports against the provider;
2. the gap map;
3. runtime instruments and white-box probes;
4. the prediction loop: blind batches, the lifecycle scorer and the blockers ledger;
5. a 329-app corpus with first-blocker scoring;
6. a round cadence that added about 20 row types in a week.

The records show where that leaves it.

**Getting apps to their first screen is close to saturated:**
- In the corpus, 272 of 329 apps drew in r83. r89 drew 356 of 369, with batches 21 and 22 included.
- Fresh F-Droid apps drawing on their first launch went from 2 in 10 (Sep 23), to 79 in 100
  (Sep 28), to 36 in 40 (Oct 7).
- First-blocker scoring shows what is left:

  | round | stops | named by a row | outside every row type |
  |---|---|---|---|
  | r77 | 57 | 9 | 46 |
  | r89 | 13 | 2 | 9 |

  The stops a row could name got fixed. What remains is Google Play services, device answers, app
  bugs, an OS boundary (`os:shell`) and native crashes in vendor or app code. A corpus round now
  costs about 9.7 hours of board time and moves one or two apps.

**The predictor's recall on blocked apps is low, and lately zero.**

| batch | recall on blocked apps |
|---|---|
| batch 4 | 0.50 |
| batches 16 to 20 | 0.14 (3 of 21) |
| top apps | 0.22 (6 of 27) |
| batches 21 and 22 | 0 of 4 |

Batches 21 and 22 scored 19 of 20 and 17 of 20 by predicting that every app draws, which is the
base rate. Each of their misses was a failure class no row described: a framework method fetching
the VPN service itself, an interface-index ioctl the app's domain is refused, a legacy key pair
spec, a shell. Each became a row only after it was seen.

**The gap map is noisy, and nothing measures most of what it reports.**
- **Volume:** a map holds a median of 76 open rows.
- **Provider-wide rows:** 50 row types appear in at least 95% of the 369 maps. 44 of them are
  lifecycle natives of core classes (`Object`, `String`, `Class`, `Thread`, `Math`, ...) that
  every app's own log shows the runtime binding at startup. They describe the provider, not the
  app, and they are false.
- **App-specific rows:** a median of 26 open rows per app. About 13 per app are explicitly
  unverified (`hollow-candidate`, `probe-only`, `unverified`, `unresolved`).
- **The most widespread are functional:**

  | row | apps |
  |---|---|
  | `queryIntentContentProviders` stub | 313 |
  | audio service, hollow | 283 |
  | MediaMetadataRetriever natives | 282 |
  | `queryIntentActivityOptions` stub | 278 |
  | component enabled-setting calls | 268 |
  | KeyCharacterMap natives | 246 |
  | JobScheduler, hollow | 216 |
  | WebView's renderer process | 143 |
  | MediaCodec, MediaExtractor, ImageReader | about 110 each |

- **Launch runs cannot settle them.** r89's 369 launches logged two `UnsatisfiedLinkError`s in all
  (Jami's JNI, and the missing `libaaudio.so`), none in the media classes. Apps reach those
  contracts when someone uses a feature, not at launch.

**The tool for measuring them exists and is dormant.**
- `probes/run_suite.py` runs 15 white-box probe apps against a build. It records verdicts keyed by
  the Westlake commit, which `gap-map --probe-results` reads.
- The only recorded results are from Sep 21 and 22, on Westlake commits of those days, with
  SELinux permissive. The per-round rescans do not pass `--probe-results`.
- AAudio showed the cost. `ndk:weld:audio` read "missing" for weeks. Its effect surfaced only in
  a drawing app's swallowed service failure (Felicity's player), and only a purpose-built tone
  probe proved the fix.

## Decision

1. **Prune with evidence already in hand.**
   - Natives the runtime registers itself (ART's own core-class natives, and the classes
     Westlake's runtime binds at startup) count as supplied.
   - Rows that describe the provider rather than the app are reported once per provider, not in
     every map.
2. **Measure conformance on every build.**
   - The probe suite is revived on the current build under SELinux enforcing.
   - It is extended with contract probes for the most widespread open rows: media decode,
     metadata, codec and frames; the audio service; the package manager's queries; key character
     maps; JobScheduler; starting another app's activity; and the absence semantics of sensors,
     vibrator and telephony.
   - Every rescan reads the results (`--probe-results`). A row then reads conformant, truthfully
     absent, broken, or unmeasured.
3. **Rank Westlake's work by measured impact:** apps that call the contract, times whether the
   probe found it broken, divided by effort.
4. **Change the cadence.**
   - The conformance run goes with every build.
   - Full corpus rounds become a weekly regression check.
   - Blind batches continue, scored on precision and recall for blocked apps, not on accuracy.

## Consequences

- **Gains:**
  - A row says whether it was measured or inferred.
  - A conformance run costs about half an hour of board time, against about 9.7 hours for a corpus
    round.
  - Functional gaps are found before an app trips on them, rather than after.
- **Costs:**
  - Probes test the platform's mechanisms, not an app's own data paths.
  - They need upkeep as contracts change.
  - Contracts that need hardware the board lacks (camera, telephony) can only be checked for
    truthful absence.
- **Kept:** corpus rounds stay, less often, as the regression check that probes cannot replace.
  The calibration flows and Android baseline of the end-to-end plan come after this.

## Alternatives considered

- **More first-screen corpus rounds as the main loop:** 13 stops remain, 9 of them outside every
  row type; diminishing returns.
- **Tuning the predictor:** its misses are classes no row describes. No threshold predicts a
  contract that is not modelled.
- **Scripted interaction flows, or calibration on an Android phone, first:** costlier and more
  fragile, and the baseline phone is not attached. They are worth more once the probes say which
  contracts to drive.

## Milestones and how we will know

| milestone | done when |
|---|---|
| M1: pruning | median open rows per app fall from 76 to 30 or fewer, and no blocker a row names in the ledger loses its row |
| M2: revival | the 15 existing probes run on the current build under enforcing, and a baseline is recorded |
| M3: contract probes | the contracts behind the ten most widespread app-specific open rows have measured verdicts |
| M4: ranking | the first ranked queue is published, and the next blind batch reports blocked-app recall |

Success overall: more than half of the corpus's app-specific open rows carry a measured verdict
(about none today), and the next Westlake fix is the top of the ranked queue.
