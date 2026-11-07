# ADR-0002: Resolve native imports where the loader looks, against the runtime that is deployed

- **Status:** accepted
- **Date:** 2026-11-07
- **Amends:** process spec §8 (Phase C) and Hard Rule 2; the native rows of
  [the gap map](../GAP-MAP-METHOD.md)
- **Companion:** [runtime tells](../RUNTIME-TELLS.md), the runtime half of the same lesson

## Context

The first Level 2 run (Nov 7: the top 100 drawing apps of the Hong Kong corpus, each used for
three minutes by the automatic explorer) ended OnSpace at startup and Amap during use. Both logs
had the same line:

```text
[WESTLAKE-LOADER] libdpsdk.so by name gave another library; opening the path
```

The line was wrong. The shim printed it whenever opening a library by name did not give back the
library at the path, and that includes the case where the open failed and gave back nothing. Once
the shim printed the loader's own reason, both apps said the same thing:

```text
Error relocating .../libamaptbt.so: __system_property_set: symbol not found
```

OnSpace's `libdpsdk.so` and Amap's `libamaptbt.so` import a bionic function the runtime does not
give app libraries. Amap's earlier `UnsatisfiedLinkError` on `NaviManager.nativeSetConfig` came
from it: the library that registers that native never loaded.

**The map had said the symbol was provided.** All 9 of the 982 apps whose libraries import
`__system_property_set` carry it as `provider-resolved`, class `C0`, provider `libbase.so`.
`libbase.so` is internal to the runtime:
- it is not in the namespace ART makes for the app's libraries;
- it is not loaded globally;
- no app library depends on it.

The loader never looks there. What the map called provided was a definition somewhere in the
runtime, not one the importing library can reach. That definition is libbase's own non-Android
stand-in, an in-process map, so forwarding to it would also have been wrong: it lets an app set a
property and read it back, which a phone refuses an app.

**The resolver has no notion of scope.** `nativeprov.resolve_native_imports` counts an import as
resolved if any library in three combined export tables (system, bridge, APK) defines it. Nothing
models:
- which namespace the importing library is loaded into;
- what that namespace can see (its search path, what it inherits, what is loaded globally);
- the importing library's own dependency closure;
- symbol versions (`_symbol_sources` keeps names only; the board resolution in `ohresolve.py`
  reads `import_versions`, the main resolver does not).

**The same kind of credit holds up 3,482 imports in 674 apps**, those 9 among them: across the
982 maps, these are the imports whose only providers are libraries internal to the runtime. An
import credited to two of these libraries is counted under each.

| provider credited | imports | apps | e.g. |
|---|---|---|---|
| `libhwui.so` | 3,208 | 672 | `ANativeWindow_fromSurface`, `ANativeWindow_acquire` |
| `liboh_android_runtime.so` | 182 | 24 | `ASurfaceControl_create`, `ASurfaceTransaction_apply` |
| `libart.so` | 44 | 1 | `art::ThreadList::RunCheckpoint` |
| `liboh_hwui_shim.so` | 28 | 6 | `AChoreographerFrameCallbackData_*` |
| `libbase.so` | 14 | 10 | `__system_property_set`, `android::base::LogMessage` |
| none of those five: `libft2.so`, `libcutils.so`, JNI libraries | 11 | 4 | `FT_Get_Glyph`, `property_get`, `JNI_OnLoad` |

Each one is either a load failure waiting to happen, as `__system_property_set` was, or answered
at run time by a library the index does not hold. The map cannot say which. The `ANativeWindow`
calls are probably the second kind: apps that make them draw, and the `libandroid.so` that the
app's namespace loads is Westlake's NDK-facing build, which is not in the index. "Probably" is
the right word, because nothing has measured it.

**The maps were also resolved against the wrong runtime.** All 982 were resolved against an index
made on Oct 24 from build 120. The board runs build 178. The shim, the missing-natives library and
the framework have all changed since. Hard Rule 2 says to resolve against the runtime that is
deployed. Each map records the `runtime_lock_id` it was resolved against, but nothing compares it
with what the board runs.

## Decision

1. **An import is resolved only by a library the importing library can reach.** For each packaged
   library E:
   - **scope(E)** is made of two parts:
     - the global libraries of the namespace E is loaded into: what it inherits from the default
       namespace (libc, which in musl also answers for libdl and libm; libz; liblog), and the
       bionic shim, which Westlake loads globally;
     - E's own dependency closure: each `DT_NEEDED` name looked up the way that namespace looks
       it up. That means the app's native library directory first (the APK's libraries and the
       copies of libraries the app writes), then Westlake's NDK-facing libraries, then the
       runtime's NDK libraries on the namespace's path.
   - An import is resolved when a library in scope(E) defines it, under the same version if the
     import names one.
   - The provider recorded is the definition the loader takes: the global libraries first, then
     the closure in load order.
   - A symbol defined only outside scope(E) gets a new state, **`out-of-scope`**, class
     `N-C1`-candidate, and the row names where it is defined. For a strong import that means the
     library does not load; for a weak one, the address is null. It is never `C0`.
   - The repair for an `out-of-scope` row is to supply the name in scope with Android's answer.
     Widening the scope to whatever library happens to define it is not a repair.
2. **The scope is data from the launcher, not knowledge in the scanner.**
   - The namespace's search path, inherited libraries and global preloads are the launcher's
     configuration already. The launcher writes them out for each build, and the resolver reads
     them.
   - `probes/runtime-resolve` checks the model on every build against three known answers: one
     symbol from the global libraries, one from a dependency, and one defined only outside scope.
3. **Resolve against the runtime that is deployed, and say when a map was not.**
   - The export index is built from the files staged for the deployed build, the same files
     `deploy-check` reads, including Westlake's NDK-facing libraries.
   - Re-resolving does not need a rescan. Each scan keeps every packaged library's `needed`,
     `soname`, undefined symbols and `import_versions`. A new index therefore re-resolves 982 maps
     in minutes, where scanning them took about 13 hours.
   - The round scorer compares each map's `runtime_lock_id` with the deployed lock, and reports the
     native rows of a stale map as unverified.
4. **A loader that refuses says why.**
   - The shim now prints the loader's own reason when a library fails to open by name
     (`by name failed (<reason>)`).
   - It keeps "gave another library" for the case where that really happened.
   - Loader failures are runtime tells ([RUNTIME-TELLS.md](../RUNTIME-TELLS.md)).

## Consequences

- **Gains:**
  - `__system_property_set` would have been a row before any launch: `out-of-scope`, defined only
    in `libbase.so`, effort XS.
  - It was fixed that way: the shim now answers as a phone answers an app, with a refusal (-1, the
    same log line as bionic). On the next run Amap loaded the library and used its full exploration
    time (nine screens). OnSpace got past the load and still ends at startup, for a reason nothing
    names yet.
  - Provider attribution names the file that answers. The `ANativeWindow` rows need that before
    anyone can say whether they are conformant.
- **Costs:**
  - The scope description has to follow the launcher. A new global preload or a reordered path
    changes how imports resolve, and the runtime-resolve check is there to catch a model that has
    drifted.
  - Rows will move. Some of the 3,482 credits will become `out-of-scope` candidates, and others
    will be re-attributed to Westlake's own NDK-facing libraries.
- **Not covered:**
  - Names looked up at run time (`dlsym`) stay `sym:runtime-resolved` candidates, which the probe
    decides.
  - When two files share a soname, which one wins is still decided by the path. The scope model
    reads the path, but it cannot verify which file wins.

## How we will know

| milestone | done when |
|---|---|
| S1: scope model | the resolver reads a namespace description, and a known-answer fixture (a library importing a name defined only outside its scope) reads `out-of-scope` |
| S2: backtest | re-resolving the 982 maps flags `__system_property_set` in all 9 apps that import it, and each of the 3,482 credits to libraries internal to the runtime is either re-attributed or flagged |
| S3: probe | runtime-resolve on the deployed build agrees with the model on the three known answers, and on a sample of the re-attributed `ANativeWindow` imports |
| S4: freshness | the round scorer names stale maps, and no round is scored on a map from another lock without saying so |

## Alternatives considered

- **Probe every import on the board.** Exact, but it multiplies the probe by every distinct
  import of every library. The scope model is cheap, and the probe checks the model, not every
  symbol.
- **Drop the libraries internal to the runtime from the index.** Simpler, but wrong in the other
  direction: an app library that lists one of them in `DT_NEEDED`, or a library the launcher loads
  globally, can reach it.
- **Keep the union and let launches find the rest.** That is how this one was found: one app at a
  time, behind a misleading message.
