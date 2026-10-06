# APK end-to-end functional testing harness

For each APK, predict which user-facing functions fail on Westlake/OH beyond startup, without
running every flow; then measure how good those predictions are with a small, sampled set of real
flows.

Status: proposal, 2026-10-06. Worked out in discussion after the r86 corpus round; nothing in it is
built yet. The facts in the background were checked against the code and the corpus maps when it
was written down.

## Background

- **Corpus rounds stop at the first screen.** Each app is launched cold and watched for 45 to 60 s
  with no input; "drawing" means only that its first screen appeared. Failures during real use are
  expected in:
  - WebView: the first `new WebView` kills the app (its renderer process);
  - opening other apps (below);
  - background work: alarms are accepted and never delivered;
  - hardware: camera, Bluetooth and sensors are not bridged;
  - rendering: SurfaceView stacking and opacity, dialog placement;
  - the default time zone: the zone rules are packaged, but clauncher's clock showed UTC after r86.
- **The gap map is built from the whole APK, but measured only for startup.**
  - The corpus maps hold about 25,000 gaps: 25,262 rows across 331 maps that are not supplied.
  - Their accuracy has been measured only for startup: r86 named 6 of its 18 stops.
  - They over-report, since a reference is not a use, and under-report APIs that exist but answer
    wrongly.
- **Running every app's flows is impossible.** The harness has to predict functional gaps by scan
  and probe, and use a small set of real flows only to measure the predictions.
- **How Android handles app A calling app B:**
  - It binds by capability at run time: PackageManagerService resolves an implicit intent to any
    installed app whose intent filter matches.
  - B's absence is a normal state with defined answers: `ActivityNotFoundException`, null or empty
    resolve and query results, `bindService` returning false.
  - Only the core handlers that Android's compatibility definition requires are guaranteed:
    browser, settings and documents, plus camera and dialer where the hardware exists.
  - Since Android 11, apps declare in `<queries>` which packages and intents they need to see.
  - Only `<uses-library android:required="true">` blocks an install. Google services is a
    privileged app that client libraries bind to. WebView loads into A's own process from a
    provider package, and its renderer runs in a separate process.
- **What Westlake does today when an app starts another app's activity:**
  - The intent goes to OH's ability manager. VIEW, SEND, PICK and MAIN are mapped to OH actions;
    SEND with text is copied to the clipboard instead; every other action passes through as
    `ohos.want.action.<Android action>`.
  - OH's refusal code comes back untranslated. Android counts only its own negative start codes as
    failures, so the app sees success, nothing starts, and no `ActivityNotFoundException` is
    thrown. A start from a worker thread is posted to the main thread and always reports success.
- **So Westlake has to:**
  - provide the core handlers, mapped to OH Wants;
  - decide on Google services: truthfully absent, or a microG-style bridge;
  - answer for a missing third-party app exactly as Android does.

## 1. Principles

- **Test contracts, not flows.**
  - Every app function reduces to platform contracts: framework APIs, binder (AIDL) methods,
    intents, content URIs, NDK symbols (linked or looked up at run time), and other apps'
    components.
  - A probe checks each contract once per provider build, and a static scan maps apps to the
    contracts they use.
  - Cost grows with the number of contracts, not with apps × flows.
- **Android's contract includes absence.** When app B or a capability is missing, the provider must
  answer exactly as an Android device without B does: `ActivityNotFoundException`, a null resolve,
  empty queries, `bindService` returning false. A truthful "absent" is acceptable; a wrong answer or
  a silent no-op is a defect.
- **Flows calibrate, they don't cover.** A few dozen real flows measure the predictions' precision
  and recall, the way startup blockers are scored against the gap map today.

## 2. Architecture

### Layer 1: static contract inventory (extend the scanner)

The scanner already records platform API references and service requests; native imports and
names looked up at run time; JNI upcalls, permissions and features; `uses-library`, the app's own
implicit intents, and Google-services dependencies.

Add:

- **Intents:** action, category, data and MIME strings; `setPackage` and `ComponentName` targets in
  other packages; `ActivityResultContracts` usage (TakePicture, GetContent, OpenDocument,
  RequestPermission, …); PendingIntents; broadcasts sent and received.
- **Cross-app dependencies:** from the manifest, `<queries>` entries and other packages' provider
  authorities and account types; from the dex, `bindService` targets.
- **Provider families:**
  - Google services and Firebase client classes, and push messaging (FCM);
  - WebView, Custom Tabs, and auth flows (OAuth, AppAuth);
  - background work: WorkManager, JobScheduler, AlarmManager, foreground services, boot receivers;
  - hardware: Camera/CameraX, BLE, location, sensors, NFC, telephony and SMS;
  - storage: the document picker (SAF), MediaStore, FileProvider.
- **A class for each cross-app target:** the app's own component; a core handler (browser, share,
  documents, settings; camera and dialer where the hardware exists); Google services; or an
  optional third-party app.

### Layer 2: feature attribution

- Run the existing reachability analysis (`reach.py`) from entry points: activities, services,
  receivers, providers, UI handlers (clicks, menus), navigation-graph destinations and fragments.
- Attribute each contract to the screens and features that reach it, and tag it by when it is
  reached: startup, user interaction, or background.
- Name features from component and fragment names, navigation destinations and menu titles.
- Output: feature → contracts.

### Layer 3: provider conformance probes (on the board, once per build)

A suite of probe APKs, run like the existing white-box probes (`icu-data`, `runtime-answers`,
`dialog-before-window`):

- **Core intents:** VIEW http/https; SEND and SEND_MULTIPLE; GET_CONTENT, OPEN_DOCUMENT and
  CREATE_DOCUMENT; DIAL and SENDTO (sms, mailto); IMAGE_CAPTURE and VIDEO_CAPTURE; `geo:` and
  `market:`; settings actions and APPLICATION_DETAILS_SETTINGS. Each is checked for whether it
  reaches an OH equivalent and whether its result comes back.
- **Absence semantics:** start an activity in a package that is not installed, resolve and query
  it; bind its service; query an unknown content authority; `getPackageInfo` on a missing package.
  Each answer is compared with AOSP's.
- **Service census:** call every AIDL method the corpus reaches on each in-process service
  (ActivityManager, user, LauncherApps, …) and classify each answer against the AOSP contract:
  real answer, type default, throws, or null.
- **WebView:** construct one, load a page, use the JavaScript bridge, render.
- **Google services:** availability status, Firebase init, push token.
- **Background:** whether alarms, jobs, WorkManager work and foreground-service notifications are
  delivered.
- **Hardware:** camera open, location fix, sensor list, BLE scan; each must answer as truthfully
  absent or actually bridged.
- **UI and rendering:** SurfaceView stacking and opacity, TextureView; dialog placement and
  dim-behind; showing and hiding the keyboard, text composition, touch and keys.
- **Result:** a conformance table per provider build. Each contract is conformant, truthfully
  absent, a wrong answer, a crash, or untested.

### Layer 4: prediction and reports

- For each app, features × contracts × conformance give a verdict per feature: works, degrades
  gracefully, fails, or unknown.
- A functional risk report per app, next to `GAP-MAP.md`, ranked by feature.
- The impact of each gap: apps × features affected, effort-rated as in today's gap map. This sets
  fix priorities.

### Layer 5: calibration flows (sampled)

- **Sample:** about 20 to 30 apps spanning messaging, browser-like, media, maps, games and utilities,
  with 3 to 5 flows each: login or first screen, open a link, share, pick a file, take a photo, play
  media, open settings, receive a background notification.
- **Driving the board:** scripted taps over the existing touch-input path, located by screenshots or
  UI dumps, plus a bounded automatic explorer (monkey-style, with a fixed time budget per app).
- **Android baseline:** run the same flows on the OnePlus reference phones with method tracing
  (`android_trace.sh`) or Frida. That records which platform calls each flow really makes: ground
  truth to check and weight the static attribution against.
- **Evidence:** extend the startup evidence extractors to flows: crashes and ANRs; exceptions and
  null services; refused calls and `dlsym` failures; `ActivityNotFoundException`; intents that went
  nowhere (adapter logs); blank or unchanged screens (screenshot diffs).

### Layer 6: scoring and ledger

- For each observed flow failure, check whether a predicted row names it.
- Report precision (predicted failures that occur) and recall (observed failures that were
  predicted).
- Record functional failures in the blockers ledger, and turn every failure no row named into a new
  scan rule or probe, as was done for startup.

## 3. Gaps to close first (known, structural)

| # | Gap | Fix | Effort |
|---|---|---|---|
| 1 | Starting another app's activity reports success and nothing starts: OH's refusal code is not translated, and starts from worker threads always report success | Answer as Android does without B: `ActivityNotFoundException`, empty queries | S |
| 2 | Core intents: VIEW, SEND, PICK and MAIN are mapped to OH actions but not checked; the document, capture, dialer and settings actions pass through as `ohos.want.action.<Android action>` | Map each to the OH Want that does it (browser, share sheet, file picker, camera capture, dialer, settings) and return its result | M |
| 3 | WebView: the first `new WebView` kills the app (its renderer process) | Host the sandboxed renderer service | L |
| 4 | Google services and push | Decide: truthfully absent (apps degrade) or a microG-style bridge over OH services | Decision, then M to L |
| 5 | Background work: alarms are accepted and never delivered | Deliver alarms, jobs and WorkManager tasks | M |
| 6 | SurfaceView stacking and opacity | A child render node per SurfaceView (needs a rebuild of the native window bridge) | M to L |

## 4. Phases

0. **Inventory:** the scanner extensions and the cross-app classification rows; corpus counts per
   contract family.
1. **Probes v1:** core intents, absence semantics, the service census; a conformance table per
   build.
2. **Attribution:** the feature → contract mapping; per-app risk reports.
3. **Calibration:** about 20 apps on the board and on the Android baseline; the first precision and
   recall.
4. **Iterate:** fix gaps in priority order. Probes rerun every build (they are cheap); calibration
   flows rerun per milestone.

## 5. Metrics

- **Probe coverage:** the share of the contracts the corpus references that have a probe.
- **Conformance:** the share of contracts that are conformant or truthfully absent, per build.
- **Prediction quality:** precision and recall on the calibration flows.
- **Readiness:** for each app, the share of its features predicted to work.

## 6. Limits and risks

- **Static reachability is imprecise:** reflection, downloaded or unpacked code, and server-driven
  UI escape it.
- **Probes test mechanisms, not an app's own data paths.**
- **Flow automation is fragile:** many apps need accounts. Use test accounts, or score up to the
  login gate.
- **Apps that depend on Google services** stay out of scope until the decision in gap 4 is made.
