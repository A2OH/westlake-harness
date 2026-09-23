# What the loader actually answers

The runtime half of `sym:runtime-resolved`. The static half can only say that a public NDK name
appears as a string inside a library; this performs the lookup the app would perform and reports
what comes back, and from which file.

```
RUNTIME_RESOLVE app-namespace candidates=84 library-unavailable=42 null=27 resolved=15
     9 resolved from /data/local/tmp/asx/liboh_hwui_shim.so
     6 resolved from /data/local/tmp/asx/liboh_android_runtime.so
```

## Why a symbol table cannot answer this

An app reaches a platform entry point in one of two ways. A **declared** dependency is recorded in
the ELF — `DT_NEEDED` plus an undefined symbol — so the loader resolves it at load time and a
missing one fails the load loudly. That is what `oh-resolve` reads.

A **runtime** lookup declares nothing:

```c
void* h = dlopen("libandroid.so", RTLD_NOW);
fn = dlsym(h, "ASurfaceControl_createFromWindow");
```

The name exists only as a string. Nothing records the dependency, and a missing entry point
returns null instead of failing. An engine looking up fourteen NDK SurfaceControl entry points
still scanned as **288 of 289 resolved**, and losing them cost hardware compositing with no error
raised anywhere — the caller simply carried on without the capability.

Three things follow, and only the third needs a device:

| Question | Answered by |
|---|---|
| which names could be looked up | the scanner, from string literals in the `.so` |
| which of those are real platform entry points | the NDK surface — 4018 candidates to 84 |
| whether the lookup succeeds, and which file answers | **this** |

## The column nothing else produces

Not one of the 15 resolved symbols above came from `libandroid.so` itself. They resolve through
its dependency tree. On 2026-09-22 two `libandroid.so` shipped — the runtime's exported none of
the NDK SurfaceControl surface, the WebView one exported all 27 — and the search path reached the
wrong one first. Both files have the same name, so no import list and no symbol table can express
that. Only asking the loader can.

## Running it

```bash
OHOS_SDK_NATIVE=<oh-sdk>/native ./build.sh

python3 run.py \
    --run-sh   <launch-out>/run.sh \        # the search path, taken not reconstructed
    --runtime  /data/app/el2/.../a2hlab-source-<hash> \
    --candidates candidates.tsv \           # <library><TAB><symbol>, from the map's rows
    --namespace-helper /data/local/tmp/a2hlab-app-<hash>/source_app_namespace \
    --hdc <hdc> --serial <serial> --out runtime-resolve.json
```

`--namespace-helper` is what makes the answer the app's answer. The child runs in a private mount
namespace where `/data/local/tmp/asx` is the staged runtime; outside it that same path is
something else entirely. Running without the helper is supported and is recorded in the report as
`global-namespace-with-substituted-runtime`, because it measures a different process's view — the
first run of this tool did exactly that and resolved a different set of symbols out of a stale
copy of that directory.

## What it does not say

A resolved symbol is not proof the app asks for it, and an unresolved one is only a gap if it
does. The tool answers *would this name resolve*, not *does this app look it up*. Deciding that
needs the app to run, which is what the Frida `dlsym` traces in `harness/jniprobe/` record.

It also runs as the app's uid but not as the app's process: a library the app has already loaded,
or one loaded with a different handle, can resolve differently.

## Failure modes it refuses rather than reports

Each of these cost a wrong number before being fixed, and each would have been reported as a
smaller, plausible answer:

- **a short read** — the resolver's per-library diagnostics go to stderr, `hdc` interleaves the two
  streams, and a diagnostic landing mid-row silently costs one symbol per library group. The
  streams are separated on the device, and a row count that disagrees with the candidate count is
  an error rather than a result.
- **a failed send** — `hdc` cannot write into `/data/app/el2`, and cannot read a WSL path when it
  is a Windows binary. Both now fail with the reason instead of leaving an empty run.
- **the header parsed as data** — the namespace helper prints a line of its own first, so the
  header is matched by content rather than skipped by position.
