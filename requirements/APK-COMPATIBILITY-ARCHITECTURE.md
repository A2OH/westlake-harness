# Westlake APK Compatibility Architecture Direction

Last updated: 2026-04-24; measured status added 2026-11-07

This note captures the current first-principles architecture conclusion for
Westlake.

It exists to keep the program aligned on the real goal:
- unchanged Android APK compatibility on the phone
- with McDonald's as the proving application
- without drifting into host-side execution or custom app-facing semantics that
  make the result look portable while breaking actual Android compatibility

## Executive Conclusion

For existing APK compatibility, the least-wrong architecture is:
- a real Android compatibility subsystem
- minimal custom semantics
- preserve ART, framework, native, service, lifecycle, and rendering behavior
  as directly as possible
- translate only at the outer boundary to OHOS

The key strategic conclusion is that Westlake should behave more like an
Android compatibility layer and less like a new application framework.

## Confidence Statement

The current confidence is not:
- "there is a clean Java-above / OHOS-below split"

The current confidence is:
- there is a plausible Android-semantics-above / backend-below split

That distinction matters.

The likely clean cutoff is:
- preserve Android-observable semantics above the boundary
- swap only backend implementations below the boundary

That is why the real cutoff is around lifecycle/runtime/resources/window/input/
surface/service semantics, not around raw JNI symbol count.

That does not mean every Android system implementation must be copied verbatim.
It means the app-facing contract must remain as close as possible to Android's
real execution model.

## The First-Principles Problem

The original simplifying assumption was:
- most McDonald's code is JVM app logic
- ART plus `framework.jar` plus a thin JNI/service shim should let most of the
  app run

That assumption was directionally useful at the start, but it is no longer
adequate.

What the codebase and accepted phone artifacts now show is:
- `framework.jar` classes are only one part of Android app execution
- modern Android apps depend on a large ambient runtime contract
- that contract includes lifecycle timing, classloader behavior, Looper/main
  thread rules, AndroidX bootstrap, rendering semantics, Binder/service
  behavior, resource/theme behavior, and native entrypoint integrity
- once those invariants drift, app failures appear as many local Java nulls,
  casts, and AndroidX breakages even when the deeper cause is below the app

So the main challenge is not "mapping a few syscalls" or "making Java methods
exist." The main challenge is reproducing enough of Android's execution
environment that the APK believes it is still running inside Android.

## Why ART Plus `framework.jar` Is Not Enough

`framework.jar` gives Java class bodies. It does not automatically provide:
- a coherent boot image / runtime entrypoint set
- zygote/app-process startup invariants
- Binder-backed system-service behavior
- native peers behind many framework classes
- resource, theme, inflater, and window-management semantics
- rendering and input behavior
- the exact async timing assumptions used by app code and AndroidX

The current Westlake phone path still makes this visible:
- the accepted path is forced into imageless mode because the packaged boot
  image set is not coherent on the live phone path
- ART is patched to override stale trampolines, clear JNI entrypoints, and
  force broad interpreter fallback
- the accepted phone baseline survives well past splash, but the live blocker
  is still a delayed post-splash `OHBridge` `SIGBUS`

That is not an app-business-logic failure. It is a substrate-integrity failure.

## Why JNI-to-System Mapping Turned Out Harder Than Expected

The portable part is smaller than it first appears.

Straightforward cases:
- files
- sockets
- logging
- environment and property reads
- simple service wrappers

Hard cases:
- activity and fragment lifecycle semantics
- AndroidX, ViewModel, and coroutine startup timing
- Looper, MessageQueue, and Choreographer behavior
- Canvas, Surface, Skia/HWUI style rendering assumptions
- resources, themes, inflation, and configuration changes
- hidden contracts between framework Java code and native peers
- class loading, boot image, JNI registration, and method-entry correctness

Android did not "mess up" here by accident. Android was designed as a full
product platform, not as a clean cross-platform app VM. Performance, battery,
security, backwards compatibility, and device integration all pushed it toward a
tightly integrated runtime.

## Why Flutter and React Native Look Better

Flutter and React Native solve a different problem.

They make source-portability feasible by changing the app contract:
- the app is written against Flutter or RN abstractions
- those frameworks own rendering and much of app behavior
- platform access is pushed behind explicit plugin/module boundaries

That works because the app was built for that abstraction from the beginning.

Westlake is trying to do something harder:
- run an existing Android APK
- compiled against Android APIs and Android runtime assumptions
- without redesigning the app
- on a different substrate

So Flutter and RN are useful conceptually, but not as proof that arbitrary
unchanged Android APKs can be made portable with a thin custom shim. They prove
that portability is much easier when the app was designed for a portable
runtime.

## What We Got Wrong

The biggest strategic mistake was mixing two different goals:
- unchanged APK compatibility
- a clean new portable abstraction for future apps

Those goals want different architectures.

For unchanged APK compatibility, inventing new app-facing semantics is usually a
liability. Every difference from Android behavior becomes a compatibility bug.

For source-available migration, a custom abstraction can be the right answer.

Westlake started with useful prototype moves, but too much of the current stack
is now custom in exactly the places where Android fidelity matters most:
- `MiniActivityManager` owns large parts of lifecycle behavior
- `OHBridge` owns a custom graphics/native contract
- the host/guest render path uses a custom pipe/display-list subsystem

These moves helped get the guest booting and drawing. They are much less
convincing as the foundation for high-fidelity APK compatibility.

## Where We Likely Wasted the Most Time

From an engineering perspective, the most expensive drift was:
- treating each local Java exception as the main blocker
- after the real failure frontier had already moved into runtime, bridge, and
  lifecycle integrity

Examples of lower-leverage work patterns:
- clearing one app-specific null or cast seam at a time
- widening custom launcher or lifecycle recovery logic
- growing broad shim-side behavior to compensate for missing Android semantics
- accepting partial bridge behavior as "good enough for now"

That work was not useless. It moved the frontier and exposed deeper truths. But
once the accepted path showed "splash can finish, guest stays alive briefly, no
downstream activity launch, then delayed bridge/runtime crash," the main battle
was no longer app patching.

## Architecture Direction From Here

### Primary Rule

Preserve Android semantics as deep into the stack as possible. Translate only at
the boundary where Android behavior must finally land on OHOS services,
graphics, input, storage, network, or device capabilities.

### Concrete Implications

- Prefer a real Android-compatible subsystem shape over new Westlake-specific
  app-facing abstractions.
- Minimize custom lifecycle ownership.
- Minimize custom render semantics.
- Minimize custom guest-visible service behavior.
- Reuse AOSP behavior directly when feasible instead of recreating it in a new
  shim contract.
- Treat custom compatibility layers as temporary bootstrap tools, not the target
  steady state.

## Controlled Validation Strategy

The fastest way to prove or disprove this cutoff is a controlled backend swap.

The control experiment should keep fixed:
- Westlake standalone guest `dalvikvm`
- guest pid/process ownership
- guest classloader/dex ownership
- the same real canary APK

Then it should swap only the backend below the tested cutoff:
- `control_android_backend`
- `target_ohos_backend`

This is the key point:
- the phone's stock ART may remain present as part of the host OS
- but the guest APK must still execute inside Westlake guest ART/process

If the canary fails in `control_android_backend`, the cutoff is wrong or the
upper runtime is still broken.

If the canary succeeds in `control_android_backend` but fails in
`target_ohos_backend`, the failing backend family is the real target.

See `$OHOS_ROOT/WESTLAKE-CONTROLLED-CUTOFF-VALIDATION.md`
for the concrete stage ladder.

## Why This Is Not "Fake"

The control run is not valid if the guest APK simply runs on the phone's normal
Android app process.

The control run is valid if:
- Westlake still owns the guest runtime/process/classloader
- Android is only used as the lower backend beneath the cutoff

So the integrity test is:
- who executes the guest bytecode?
- who owns the guest classloader/runtime?
- did only the lower backend swap?

If Westlake still owns those things, the control is legitimate.

### Design Rule For New Work

For every new compatibility patch, ask:
1. Does this preserve Android app-facing semantics?
2. Or does it invent a new Westlake-visible behavior that the app only happens
   to tolerate?

If it invents new semantics, the default answer should be "do not do this"
unless it is explicitly marked as a temporary proving cut.

## What This Means For Current Westlake Workstreams

The current critical path is not "more app-specific fixes."

The first-order battles are:
- runtime/ART entrypoint integrity on the accepted phone path
- `OHBridge` correctness and completeness
- faithful downstream activity-flow truth after splash self-finish

The second-order battles are:
- AndroidX/AppCompat fidelity on top of that substrate
- only then real McDonald's UI and interaction milestones

This reframes the active question from:
- "what is the next local McD exception?"

to:
- "what Android runtime invariant is still broken?"

## Validation Rules For This Strategy

The strategy only remains justified if it produces evidence on these questions:

1. Can the accepted phone runtime identify the owner of the delayed post-splash
   `SIGBUS`?
2. Does the app actually attempt the downstream activity launch, or does
   Westlake lose it in lifecycle management?
3. Is `OHBridge` fully and correctly registered, or is partial/incorrect bridge
   behavior still masking as app-level failure?
4. Are we preserving Android semantics, or merely adding more local tolerance?
5. Can a real canary APK advance stage by stage under a controlled backend swap?

If the answer to these stays unknown while more app-level seams are patched,
that is a sign of architectural drift rather than progress.

## Where the cut stands, measured (2026-11-07)

The rules above ask for evidence. This is what the Hong Kong top-1000 runs on build 177, and the
first Level 2 run (the top 100 drawing apps, each used for three minutes by an automatic explorer),
show.

**What holds: the app side.**
- Real ART and the AOSP framework run the app's unchanged code: 755 of 960 scored apps draw their
  first screen.
- 81 of the top 100 drawing apps keep running through three minutes of use. Running is not
  working, though: 27 of those 81 reached two screens or fewer.
- Only 20 of the 205 apps that do not draw are first stopped by a Java framework error.
- Name-based prediction no longer finds the blockers (recall between 0 and 0.22; harness
  ADR-0001). The missing-name gap is mostly closed.

**What does not: three seams, none of them names.**

| seam | what is there | evidence |
|---|---|---|
| system services and lifecycle | Android's system server does not run. Westlake's in-process adapters answer its calls: activity and task manager, package manager, broadcasts, jobs, settings, and a table of fixed answers | 28 of the 55 Westlake commits since Oct 23 change these adapters. Level 2 ends here: an activity destroyed twice, a pending start lost when the app restarts its own process, no calendar provider, no app store |
| native ABI and process image | app libraries built for bionic run on musl through the shim, in Westlake's process layout | 19 of the 55 commits change the native shims, which were rebuilt about thirty times since Oct 27; one build broke 43 drawing apps. 14 of the 59 native crashes with a dump stop inside musl (10 of them aborts, so the cause may be above it). PairIP's library accounts for about 56 of the 122 native-crash stops. The same apps get past it on an Android phone without Google; ptrace and SELinux are ruled out, and the first measured difference is how it reads its own `/proc/self/maps` |
| OS policy | OH's rules for app domains differ from Android's | pipes and symlinks in app data are refused (symlinks by a neverallow), and app domains cannot register services. No shim reaches these |

**The test this note asks for has not been run.** The controlled backend swap (the same Westlake
guest runtime over an Android backend and over the OH backend) has never been built. The
Android-phone comparison of the end-to-end plan is a different test, Android's own runtime against
Westlake on OH, and it has not run either.

**So the cut is unproven, not disproven.**
- The app side holds.
- The services seam is where this note's primary rule is not being followed. Hand answers are
  custom guest-visible behaviour, the thing "What We Got Wrong" warns against, and their number
  keeps rising.
- The guard added this week for TP-Link drops a destroy for an activity already gone. It is that
  kind of tolerance. The duplicate comes from two Westlake destroy paths, one of them in a native
  bridge that cannot be rebuilt today, and removing one of the two paths is the real fix.

Two harness changes are decided (not built yet), so that this section can be re-measured every
round instead of re-argued:
- native rows resolve in the importing library's scope, against the deployed runtime (harness
  `analysis/adr/0002-native-imports-in-scope.md`);
- the runtime tells where it answers an app differently from Android, or where a process ends
  (harness `analysis/RUNTIME-TELLS.md`). Each round then reports which seam its fatal answers fall
  in.

If the services seam dominates, the next step is AOSP's own services in place of the hand answers,
not more answers.

## Non-Goals

This note does not argue that:
- all custom Westlake code was a mistake
- source-level migration frameworks like Flutter or RN are not useful
- the current prototype path has no value

It argues something narrower and more important:
- a custom app-facing shim can be useful for bootstrap and experimentation
- but unchanged APK compatibility ultimately wants Android-faithful behavior,
  not a second application framework

## Bottom Line

If the goal is unchanged APK compatibility:
- Westlake should converge toward an Android compatibility subsystem
- not toward a novel portable runtime surface

If the goal is source-available migration in the future:
- a thinner portable abstraction may be correct
- but that is a different product and should not be confused with the current
  APK-compatibility mission
