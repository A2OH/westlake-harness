# Conformance run

The per-build measurement of the provider's contracts ([ADR-0001](../../analysis/adr/0001-measured-provider-conformance.md)).
Probe apps exercise the contracts the gap map reports open in many apps. Each contract probe prints
one line per gap-map row it measures, `probes/run_suite.py` records one result per row, and every
rescan reads them (`gap-map --probe-results`). A row then reads conformant, truthfully absent,
broken (with the probe's finding), or unmeasured. `scripts/conformance_queue.py` ranks the open
rows by apps x measured state / effort.

- `probe-results.json`: every result, keyed by the Westlake commit it was measured on.
- `queue-build100.md`, `queue-build100.json`: the first ranked queue.

## Build 100 (Westlake main 7667b33, 2026-10-09)

The OH 6.1 board under SELinux enforcing, launched as the r89 corpus round was: the bionic shim
with AAudio and the runtime-library override of that round.

### The suite

| probe | result | what it measured |
|---|---|---|
| service-metadata | pass | a service's manifest meta-data, read by its registrar |
| provider-manifest | pass | `<queries>` providers not installed; the `:remote` provider not created in the main process |
| running-app-processes | pass | the app sees itself in `getRunningAppProcesses`, from Application and Activity |
| signin-layout | pass | a sign-in layout inflates and draws (17 views, none zero-sized) |
| dialog-before-window | 1 pass, 1 fail | below |
| asset-list | pass | `AssetManager.list` at the root and nested |
| webview-boundaries | pass | WebView single-process, its search path |
| gl-contracts | pass | EGL on an app's own thread, TextureView frames, a 4 s consumer stall, `eglTerminate` |
| media-contracts | 1 pass, 5 fail | below |
| framework-contracts | 4 pass, 5 truthfully absent, 12 fail | below |
| icu-data | 2 pass | below |

### Contracts, one per gap-map row

| row | outcome | the probe's finding |
|---|---|---|
| `jni:android.media.MediaMetadataRetriever` | broken | `UnsatisfiedLinkError`: `native_init` |
| `jni:android.media.MediaExtractor` | broken | `UnsatisfiedLinkError`: `native_init` |
| `jni:android.media.ImageReader` | broken | `UnsatisfiedLinkError`: `nativeClassInit` |
| `jni:android.media.MediaCodec` | broken | an AVC decoder is created, configured and started, but gives no input buffer in 1 s |
| `media:decode-file` (no row) | broken | `NoClassDefFoundError` for MediaExtractor, after its failed static initializer |
| `jni:android.media.AudioTrack` | conformant | 48 kHz stereo 16-bit plays |
| `am:start-unresolved` (no row yet) | broken | `startActivity` for an intent nothing handles returns; Android throws `ActivityNotFoundException` |
| `svc:audio` | broken | max volume 0, no output devices, focus not granted (sample rate and burst are answered) |
| `pm:call:queryIntentContentProviders` | broken | the probe's own provider is not found by its filter |
| `pm:call:queryIntentActivityOptions` | broken | its own activity is not found by its action |
| `pm:call:queryBroadcastReceivers` | broken | its own receiver is not found by its action |
| `pm:call:setComponentEnabledSetting` | broken | a disabled activity still resolves |
| `pm:call:getComponentEnabledSetting` | broken | reads back 0 (default) after disabling |
| `jni:android.view.KeyCharacterMap` | broken | the virtual keyboard maps `KEYCODE_A` to 0 and "ab" to no events |
| `svc:jobscheduler` | broken | a job is scheduled (not pending) but never runs in 15 s |
| `svc:vibrator` | truthfully absent | `hasVibrator` false, `vibrate` returns |
| `svc:sensor` | truthfully absent | no sensors listed |
| `svc:phone` | truthfully absent | phone type NONE, no SIM |
| `svc:keyguard` | conformant | answers locked/secure |
| `svc:user` | conformant | unlocked, its own user among the profiles, a serial number |
| `svc:captioning` | conformant | a manager with font scale 1.0 |
| `pm:call:getInstallerPackageName` | conformant | null, as for an app installed from a file; the install source answers |
| `svc:textclassification` | truthfully absent | the `NO_OP` classifier, as on a device without one |
| `svc:fingerprint` | truthfully absent | no manager and no `FEATURE_FINGERPRINT` |
| `svc:biometric` | broken | no `BiometricManager`; Android always has one, even without a sensor |
| `svc:media_metrics` | broken | no `MediaMetricsManager` |
| `svc:grammatical_inflection` | broken | no `GrammaticalInflectionManager` |
| `wm:dialog-stacking` | conformant | the runner's tap at the button's logged position reaches the dialog |
| `wm:window-placement` | broken | the dialog at 40,0 rather than centred at x=280 on a 1200 px screen |
| `data:icu-locale-display` | conformant | "German (Germany)" from `Locale` three times, and from `ULocale` |
| `data:tzdata` | conformant | 635 `java.time` zones, 637 ICU zones, Paris at +01:00 |

The gap map's `missing` for the two ICU rows was written from the framework 57 run and was stale:
the fixes it recorded are in the build.

### Probe apps outside the suite

Run once on the same build for the baseline (their output is a record, not per-row results):

- **ndk-assets:** every step works. `AAssetManager_fromJava`, both assets open and read in full,
  the missing asset returns null, and the directory lists.
- **runtime-answers:** 32 of its 33 answers match Android's. On framework 70 about half differed.
  The one left is `new MediaRecorder()`, which throws "Unable to initialize media recorder"
  (`jni:android.media.MediaRecorder`, 28 apps).
- **audio-tone:** last run with a recording of the board's output for the AAudio port (Oct 8 and 9).
  It needs `oh_record` and is not a log probe.
- **default-interface-dispatch:** retired. Its 2026-08-23 run refuted the hypothesis it was written
  for.

## What the gap map reads now

A map now carries what is left after the evidence in hand settles a row, and the run's results decide
the rest. On the corpus's 369 maps, the row-instances open on the build 96 maps and gone on the
build 100 maps, by family:

| family | row-instances | what settled them |
|---|---|---|
| `jni-lifecycle` | 16,236 | the core-class natives the runtime registers itself (44 false rows per map); the rest are provider rows |
| `java` | 3,362 | AOSP's own constant bodies (40,310 findings); probes of library classes (6,888); probes and members Android 15 lacks (1,622) |
| `svc` | 1,274 | measured conformant or truthfully absent |
| `pm` | 436 | measured conformant, or the passing probe that names them |
| `load` | 372 | the runtime's silent library loads, now a provider row |
| `data` | 285 | ICU display names and tzdata measured conformant |
| others | 126 | `jni`, `sym`, `upcall`, `ndk` |

The comparison spans builds 96 to 100, so a few rows closed because the build fixed them, not
because of pruning. Rows that describe the runtime rather than the app now sit in each map's
`provider_rows`, a median of 4 per map: the lifecycle natives still unregistered, and the
runtime's silent library loads.

Of the 40 ledger blockers whose rows were on the build 96 maps, 39 keep their rows. The 40th, Felicity's
`load:needed-missing` for `libaaudio.so`, closed because build 100 supplies the library (AAudio);
its ledger entry is marked fixed.

## The measures (ADR-0001)

| ADR-0001 measure | build 96 maps | build 100 maps | target |
|---|---|---|---|
| median open rows per app (work left) | 72 (76 as the ADR counted) | 15 (21) | M1: 30 or fewer |
| app-specific open rows with a measured verdict | 0 of 27,583 | 5,235 of 8,253 (63%) | more than half |
| the ten most widespread rows, measured | none | 9 of 10 | M3: all |

"As the ADR counted" includes rows with no work left (inert services, truthful absence). The one
unmeasured row of the ten is `wm:dim-behind`, visible on screen only. M2 is met: the suite and the
probe apps that still apply ran on build 100 under enforcing (above). M4 is half met: the queue is
published; the next blind batch reports blocked-app recall (`scripts/score_observed.py`).

## The ranked queue

`queue-build100.md` ranks the open rows by apps x measured state / effort. Its top ten, with the first
fix taken from it:

| rank | row | apps | measured | effort |
|---|---|---|---|---|
| 1 | `svc:audio` | 288 | broken | S |
| 2 | `pm:call:setComponentEnabledSetting` | 268 | broken | S |
| 3 | `pm:call:getComponentEnabledSetting` | 261 | broken | S |
| 4 | `jni:android.view.KeyCharacterMap` | 246 | broken | S |
| 5 | `svc:jobscheduler` | 216 | broken | S |
| 6 | `wm:window-placement` | 318 | broken | M |
| 7 | `pm:call:queryIntentContentProviders` | 313 | broken | M |
| 8 | `jni:android.media.MediaMetadataRetriever` | 282 | broken | M |
| 9 | `pm:call:queryIntentActivityOptions` | 278 | broken | M |
| 10 | `svc:media_metrics` | 84 | broken | S |

**The first fix, `svc:audio` (Westlake #32):** the in-process audio service now answers as a phone
with a speaker: stream volumes that read back, the ringer normal, and focus granted.
`AudioSystem.listAudioPorts` lists a speaker and a microphone. On build 101 (build 100 plus the
fix) the probe passes: max volume 15, volume 5, one output, focus granted, ringer normal. Twenty apps
that ask for focus, devices or volumes all draw, as in r89. The build 101 results are in
`probe-results.json` under the fix's commit.

**Two fixes from the calibration flows** ([calibration](../calibration/README.md)): build 102
(Westlake #33) delivers activity results between the app's own activities, and build 103 (Westlake
#34) resumes an activity the app starts once. Each added a line to framework-contracts:
`am:activity-result` passes on build 102, and `am:launch-lifecycle` reads `onCreate onStart onResume
onPause onResume` on build 102 and `onCreate onStart onResume` on build 103, both under SELinux
enforcing. Their results are in `probe-results.json` under each fix's commit; every other
framework-contracts line reads as on build 101.

**Build 105** (Westlake #35) shows popup windows: a sub-window gets an OH session of its own. The whole
suite, run under its commit, gives each line the outcome of its last run (builds 100 to 103); the fix
shows only on screen, in the calibration flow `fclock-menu`, which is the measurement of the gap map's
`wm:popup-window` row.

**Build 106** (Westlake #36) tells an app where its windows are: each window's configuration has the
display's bounds. `wm:window-placement` passes for the first time (the dialog at 280,634, centred),
and `wm:dialog-stacking` with it. `wv:renderer-process` has a result of its own from this build on:
webview-boundaries' multiprocess line, mapped onto the row (`rows` in `probes/suite.json`).

**Build 107** (Westlake #37) hands window focus on when a window closes. framework-contracts gains
`svc:input_method` (a focused editor is served and the keyboard shown: passes on builds 106 and 107)
and `wm:focus-handoff` (fails on build 106, passes on build 107). `wm:window-placement` failed in this
run on the AlertDialog's first, 1282 px wide layout, which a later layout fits; it caught that on
build 105 as well (see the calibration record).

**Build 108** (Westlake #38) gives the in-process notification service the app's channels and posts,
and plays a post's sound. framework-contracts gains `svc:notification` (a channel created is kept,
`areNotificationsEnabled` answers as `POST_NOTIFICATIONS` does, a post is listed while notifications
are allowed and gone once cancelled): it fails on build 107 (the channel created is not kept) and passes on build 108, whose answers come
from OH's per-application notification switch, allowed for the board's host application in OH
Settings. `wm:window-placement` passed in this run (the AlertDialog at 30 to 1170).

**Build 109** (Westlake #39) relaunches an activity that calls recreate(). framework-contracts gains
`am:recreate`: the probe's own activity calls recreate() once resumed, and a new instance must come
up within 10 s with the state the first saved. It fails on build 108 (no new instance) and passes on
build 109; every other line reads as on build 108. On build 109 before its native was added, the
relaunch ran and the probe died in it: the relaunched window's first draw needed
`SurfaceControl.nativeAddTransactionCompletedListener`, which no library registered.

**Build 110** (Westlake #40) places dialogs where they are drawn. dialog-before-window's
`wm:window-placement` line now also relays the dialog out with its own attributes and checks that
it stays put, and checks that the alert is centred, not only that it fits. On build 109 the
relaid-out dialog moved to (40,0): the window adapter gave every window an attached frame of its
own size, and ViewRootImpl lays a dialog out inside its attached frame. On build 110 it stays at
(280,634); every other line reads as on build 109.

**Build 112** (Westlake #41) delivers alarms in process. framework-contracts gains an `svc:alarm`
line: a listener alarm and a PendingIntent alarm to a receiver the probe's manifest declares, both
set 1.5 s ahead, must arrive within 8 s. On build 110 neither arrived, because the alarm service
accepted every alarm and delivered none. On build 112 both arrive, and
`pm:call:queryBroadcastReceivers` passes too, as the package manager now resolves the app's own
receivers. Every other line reads as on build 110.

**Build 113** (Westlake #42) runs scheduled jobs in process. framework-contracts' `svc:jobscheduler`
line used to check only that a job due at once runs. It now also schedules a job 1.5 s ahead that
needs a network: the job must be pending until it runs, run no sooner than 1.5 s and within 10 s
with a network in its parameters, and no longer be pending once done. Work given through `enqueue`
must reach its job through `dequeueWork`. On build 112 the first job never ran: the scheduler
accepted every job and ran none. On build 113 the delayed job ran after 1517 ms. Every other line
reads as on build 112.

## Running it

On a new build, run the suite with that build's provider flags, merging into this file:

    python3 probes/run_suite.py --manifest <launcher repo> --workspace <source workspace> \
        --westlake-source <westlake checkout> --framework-report <build>/device-report.json \
        --hdc <hdc> --serial <device> --work <scratch dir> \
        --results benchmark/conformance/probe-results.json \
        --launch-args "<the provider flags the corpus round launches with>"

Then rescan with `gap-map ... --probe-results benchmark/conformance/probe-results.json`, and rank:

    python3 scripts/conformance_queue.py <map roots> --top 30 --out queue.md --json queue.json

Results apply only to maps of the same Westlake commit, so a new build reads nothing until its own
run. Follow-ups:
- `wm:dim-behind` needs a screen oracle: the dim shows on screen only;
- `am:start-unresolved` and `media:decode-file` have no row yet;
- runtime-answers' `new MediaRecorder()` could become a line for `jni:android.media.MediaRecorder`.
