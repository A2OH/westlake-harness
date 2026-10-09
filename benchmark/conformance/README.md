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
