# Runtime API gap analysis: light probes that tell

**2026-11-07.** The runtime half of the gap map. Extends [the gap map](GAP-MAP-METHOD.md) (its
evidence ladder), [runtime evidence](../runtime/TRACE-EVIDENCE.md) (its event envelope) and
[the end-to-end plan](E2E-FUNCTIONAL-HARNESS-PLAN.md) (layers 3, 5 and 6). The static half was
amended the same day by [ADR-0002](adr/0002-native-imports-in-scope.md).

## Why

The static map subtracts names, and that half of the gap is nearly closed:
- On build 177, 205 of the 960 apps of the Hong Kong top 1000 that were scored did not draw their
  first screen. Only 20 of those were first stopped by a Java framework error.
- Name-based prediction of blocked apps has had a recall between 0 and 0.22 since batch 16
  ([ADR-0001](adr/0001-measured-provider-conformance.md)).

What stops apps now is **answers**, not names:
- a system service that Westlake answers by hand, with null, a type default or a fixed value.
  Android's system server does not run, and Westlake's in-process adapters stand in for it;
- a call that the native layer refuses or stubs;
- an OS rule that differs from Android's;
- an app that ends itself, or is ended, with nothing in the log.

None of these leaves a name to subtract. Each one happens at a place in the runtime that knows it
is giving the app something other than what Android gives. The runtime should say so there, the
first time it happens. That line is a **tell**: a light probe, built into the runtime, that every
run carries at no extra cost.

## What a few tells did this week

The first Level 2 run (Nov 7: the top 100 drawing apps, each used for three minutes by the
explorer) ended 19 apps. Measured with `device/tells.py`, which reads the markers that exist as
tells (step T0 below):

| how the 19 ended | apps |
|---|---|
| uncaught Java exception | 4 |
| Back on the app's last screen, Westlake ending the process; both with the GPU driver's thread aborting during the exit | 2 |
| fatal signal | 3 |
| fatal signal whose dump timed out | 1 |
| **silent**: no tell, no Java exception, no fatal signal in the system log | **9** |

Three tells were added the same day, each a few lines at the place the answer is given. Reruns of
the silent apps named most of them:

| app | what named it | reading |
|---|---|---|
| Outlook | `System.exit` with its stack, from a shutdown hook installed before the app binds | the China edition shows a disclaimer, then exits. Android restarts the process for the pending start; Westlake does not. **A lifecycle gap** |
| Excel, Doubao, Xiaomi Home | a process signalling itself, with the stack, at `Process.sendSignal` | each quit after the explorer refused or cancelled a consent dialog. **An explorer fix**, not a platform gap |
| Pico Live | — | kept running on the rerun, once the explorer stopped refusing consent |
| OnSpace | the loader's own reason for a failed open | `__system_property_set` missing, while the static map said it was provided. **A shim fix and a scanner fix** ([ADR-0002](adr/0002-native-imports-in-scope.md)). With the name supplied it gets past the load and still ends silently |
| WeChat | the system log, on the rerun | a fatal signal on a startup thread; the system's dumper timed out twice, so there is no crash site |
| CamScanner | the system log | its own signal handler took SIGILL (a risk-detection library's trap), then the process ended. Still silent |
| Octopus | — | ends during bind with C++ destructors running and no Java exit line, which points at a native `exit()`. Still silent |

**Nine silent ends became three.** The same reading corrected one of ours: the two Back ends had
been read as a clean close. They are Westlake ending the process on the last activity, where Android
keeps it cached, and in both the GPU driver's thread aborted while the process was going away.

A fourth marker, written where a stale destroy is dropped, showed that TP-Link's Back crash came from
Westlake destroying one activity twice, which is Westlake's own defect.

On the next run the loader tell named two more: Bilibili's `libijkffext.so` needs bionic's
`__fe_dfl_env`, which the static map did list as missing, and Insta360's `libmarsxlogg.so` cannot
find a libc++ constructor that the map said the app's own `libc++_shared.so` provides. One open row
nobody had ranked, and one wrong "provided", each found on its first run.

The method below makes the list of unexplained ends shrink every round, the way unnamed startup
blockers once became rows.

## What a tell is

One line, written where the runtime gives an app an answer Android would not give, or where the
app's process ends. Rules that keep it light:

1. **At the answer site, after the answer is decided.** A tell never changes what the app gets.
2. **Once per contract and caller in a process.** Counts go in a summary line at a normal exit.
3. **Bounded.**
   - One line, at most 512 bytes.
   - The caller is the first Java frame outside the runtime. In native code it is a return address
     that the harness resolves offline from the saved maps; there is no `dladdr` and no allocation
     in signal or loader paths ([hook rules](../runtime/TRACE-EVIDENCE.md)).
4. **Written to the app's stderr file**, which every round already collects whole. Not to hilog:
   under enforcing hilog drops app logs, and the window shim floods its ring.
5. **Says whether the answer is Android's.**
   - `fidelity=android`: a phone gives an app the same answer in the same state. The AOSP source
     line goes next to the code that emits the tell. A refused property set, which is -1 on a phone
     too, is not a gap.
   - `fidelity=stand-in`: Westlake's own answer, which differs from a phone's.
   - `fidelity=unknown`: nobody has compared it yet.
6. **Its emission rule is written down** beside it (process spec §10.2): before or after a
   fallback, gated or not, on which thread. A count of tells without that rule is not evidence.

```text
[WESTLAKE-TELL] {"v":1,"contract":"load:libamaptbt.so","answer":"failed","fidelity":"stand-in","caller":"<first app frame>","t_ms":30110,"detail":"__system_property_set: symbol not found"}
[WESTLAKE-TELL] {"v":1,"contract":"provider:com.android.calendar","answer":"null","fidelity":"stand-in","caller":"<first app frame>","t_ms":41260}
[WESTLAKE-TELL] {"v":1,"contract":"end:java-exit","answer":"exit","fidelity":"android","caller":"<first app frame>","t_ms":8400,"detail":"status 0"}
```

| field | meaning |
|---|---|
| `contract` | `svc:<name>`, `binder:<interface>.<method>`, `provider:<authority>`, `intent:<action>[:<scheme>]`, `lifecycle:<event>`, `load:<library>`, `sym:<name>`, `prop:<name>`, `policy:<call>`, `end:<how>` |
| `answer` | `null`, `default`, `fixed`, `refused`, `stub`, `dropped`, `failed`, `exit`, `signal`, `crash` |
| `fidelity` | `android`, `stand-in`, `unknown` |
| `caller` | the first app frame (`class.method`), or `library+0xoffset` |
| `t_ms` | milliseconds since the process started |
| `detail` | a short reason: the loader's message, the exit status, the signal |

The runtime does not need the taxonomy. The harness maps each contract prefix to a layer:
`svc`, `binder`, `provider`, `intent` and `lifecycle` to `S`, the rest to `N`. `policy` tells
also take the fault origin of OH's policy. Ends are kept apart: an end is a consequence, and the
tells before it are the candidates for its cause.

## Where the tells go: the answer sites

### Services and lifecycle that Westlake answers by hand

| site | tell | today |
|---|---|---|
| a service lookup with no adapter (`OHServiceManager`) | `svc:<name>` `null` | a plain stub line; normalise it |
| the default answers of in-process service proxies: the `IActivityManager` handler's unlisted methods, the fixed-answer table, package manager stubs | `binder:<iface>.<method>` `default`, `fixed` or `stub` | the proxy logs a few "hot" methods; every other method returns a type default silently. The table logs only values that do not fit. **Add** |
| a content resolver with no provider for an authority | `provider:<authority>` `null` | not logged. **Add** (the short-drama app's calendar) |
| an activity start, resolve or bind that finds nothing, or that OH refuses | `intent:<action>:<scheme>` `failed` or `refused` | the exception shows only if the app does not catch it. An OH refusal that the app sees as success is a `stand-in` (end-to-end plan, background). **Add** |
| lifecycle departures | `lifecycle:stale-destroy` `dropped`; `lifecycle:exit-with-pending-start` | the first is logged; **add** the second (Outlook) |

### Native ABI and loader

| site | tell | today |
|---|---|---|
| a library that fails to load | `load:<library>` `failed`, with the loader's reason | **added** in the shim |
| shim functions that refuse or stub (`ASurfaceControl_create` answering null, the media codec calls that answer unsupported, a property set) | `sym:<name>`, with its fidelity | **add**, once per symbol |
| `dlsym` returning null for a name in the NDK surface | `sym:<name>` `null` | the shim already wraps `dlsym` for Android callers. **Add** the tell there |
| a property read with no answer | `prop:<name>` `null` | the shim logs every read today, which is too loud. **Make it** a tell for misses only |

### OS policy

| site | tell | today |
|---|---|---|
| a policy-checked call refused: `mkfifo` or `symlink` in app data, `ptrace` | `policy:<call>` `refused`, with errno and the object's class | **add** in the shim's wrappers. The static row comes from the policy model (`probes/avq.c`) |

### Process ends: none should be silent

| how the process ends | tell | today |
|---|---|---|
| Java `System.exit` | `end:java-exit`, with the stack | exists (`[WESTLAKE-EXIT]`) |
| a signal to itself (`Process.killProcess`) | `end:self-signal`, with the stack | exists (`[WESTLAKE-KILL]`) |
| an uncaught Java exception | `end:uncaught` | exists (`[UNCAUGHT]`, `[INITCHILD-FAIL]`) |
| C library `exit()` or `_exit()` called from app code | `end:native-exit`, with caller and status | **add**: the shim already sits ahead of libc for app libraries (it wraps `sigaction`) |
| a fatal signal | `end:crash`, with the signal and the pc as `library+0xoffset`, written before the system's handler runs | **add** in the shim's signal path. Today the dump is the only record, and it can time out (WeChat, twice) |
| the system's dumper timed out | `end:dump-timeout` | **add** to the harness, from the dumper's `waitpid ... timeout` line |
| killed from outside (low memory, the OS) | `end:external` | **add** to the harness, from the system's kill log |
| none of the above | `end:silent` | the harness counts it. Each one is a tell still missing |

Raw system calls (an `exit_group` or a `kill` issued directly) and protectors that avoid libc are
invisible to wrappers in user space. They stay `end:silent` unless the kernel's own log names them.

## What the harness does with tells

1. **Ingest.** Each run's stderr already comes back per app. The scorer parses the tells into
   `tells.json`: for each contract, the answer, the fidelity, the first time, the count and the
   stage the app had reached. During migration it also reads today's markers: `[WESTLAKE-EXIT]`,
   `[WESTLAKE-KILL]`, `[WESTLAKE-STALE-DESTROY]`, the loader lines, the service-manager stub lines
   and the package manager's `[STUB]` lines.
2. **Cause candidates.** These are the end tell and the tells in the seconds before it, in order.
   The first `stand-in` or `failed` answer before an end is the candidate cause. It is a candidate,
   never a proof (Hard Rule 5); the explorer's `died_after` sits beside it.
3. **Rows.** A told contract becomes a gap-map row `rt:<contract>` at evidence level `observed`.
   - `stand-in` and `failed` answers are gaps.
   - An `android` answer is conformant by design.
   - An `unknown` answer names the probe that would compare it with AOSP: the service census in
     layer 3 of the end-to-end plan.
4. **Ranking.** For each contract in a round:
   - how many apps reached it;
   - how many ended within ten seconds after it;
   - how many apps' exploration stalled after it.

   Divide by effort (process spec §13). The ranked list is the runtime half of the work queue.
5. **The seam count.** Every round reports its fatal tells by where they fall:
   - services and lifecycle;
   - native ABI and process;
   - OS policy;
   - the app's own choice.

   That is the measured answer, every round, to whether the cut is in the right place
   ([architecture](../requirements/APK-COMPATIBILITY-ARCHITECTURE.md), status of 2026-11-07). If
   most fatal tells fall in the services Westlake answers by hand, the evidence points at AOSP's own
   services in place of the hand answers, not at more answers.
6. **The silent count.** Ends with no end tell, every round. It should fall to zero, or to the ends
   that no code in user space can see.

## How it fits with the map and the probes

| | static map | conformance probes | tells |
|---|---|---|---|
| asks | what can this APK reach? | does this contract behave like Android's? | what did the runtime answer, to which app, and what happened next? |
| costs | a scan for each APK | about half an hour for each build | nothing extra: every round, every app |
| cannot see | answers, semantics, and scope until ADR-0002 | which apps reach a contract | contracts that no run reached |

A tell says that a contract was reached and how it was answered. A probe says whether that answer
is Android's. The map says which other apps can reach the contract. Together they make a row
measured instead of inferred.

## How we will know the tells work

- **Backtest.** Each of the 19 Level 2 ends of Nov 7 has to be named by a tell or by a recorded
  explorer reason. After the first tells and reruns, 16 have an end kind; OnSpace, CamScanner and
  Octopus are still silent, and WeChat's fatal signal has no crash site.
- **Fixtures.** A probe app triggers each tell once:
  - a service with no adapter;
  - an unlisted binder method;
  - an unknown authority;
  - an intent nothing resolves;
  - `System.exit`, a self-signal and a native exit;
  - a missing symbol.

  It runs in the conformance run of every build (ADR-0001), so a build that loses a tell fails it.
- **Cost.** Tells per app in a three-minute run stay under a budget, starting at 200 lines. Startup
  time with and without tells, on the calibration flows, differs by less than the run-to-run noise.

## Order of work

1. **T0, harness only.** Parse the markers that exist as tells, and publish the silent count for
   the Nov 7 runs. *Done:* `device/tells.py <tag>...` writes `<tag>-tells.json` and prints how each
   app ended, the candidate causes, and the contracts told by the most apps.
2. **T1, services.** One helper in the framework, called at:
   - the service lookup;
   - the proxies' default answers and the fixed-answer table;
   - the package manager stubs;
   - content resolver misses, intent misses and OH refusals.
3. **T2, native and ends.**
   - shim stubs and refusals;
   - `dlsym` misses for NDK names;
   - native exit and the fatal-signal tell;
   - dump timeouts, parsed by the harness.
4. **T3, rows and ranking.** `rt:` rows in the gap map, the ranked runtime queue, and the seam
   count every round.

Done when two Level 2 rounds in a row end no app silently, apart from ends that user space cannot
see, and the ten highest-ranked runtime rows each have a probe.

## Limits

- **A tell sees only what the runtime does.** An app that takes a wrong branch after a stand-in
  answer, and makes no further call, leaves a tell without a consequence. The explorer and the
  screenshots measure the consequence.
- **Reached is not used.** A contract told once at startup may never matter, so the ranking weights
  by what followed, not by the count.
- **Fidelity is a claim until a probe measures it.** `android` on a tell is the author's statement,
  with the AOSP line beside the code. The conformance probe is what proves it.
- **Tells are not diagnostics under Hard Rule 12.** They stay in production builds, and that is
  acceptable only while they stay light. A tell that fires on every frame or every call, rather than
  on the first occurrence, gets fixed or removed.
