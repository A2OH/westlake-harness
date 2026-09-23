# The three boundaries that decide whether an app can open a WebView screen

Each was reached by driving Wikipedia to an article on 2026-09-22, and each took the process down
in a way no static check could see. All three are properties of the runtime and the launch rather
than of the app: a build that changes one changes it for every app at once, which is why they are
worth measuring on every build instead of rediscovering per app.

```
phase=multiprocess  verdict=PASS_SINGLE_PROCESS effective=false flagV2=false flagWrapper=false service=false
phase=searchpath    verdict=OBSERVED_SHADOWING dirs=11 shadowed=3
                    libandroid.so     =[first:/data/local/tmp/asx shadowed:…/webview-t-lib]
                    libjnigraphics.so =[first:/data/local/tmp/asx shadowed:…/webview-t-lib]
                    libc++_shared.so  =[first:/system/lib64       shadowed:/vendor/lib64]
phase=windowcontext verdict=PASS_ANSWERED display=0 widthDp=533 heightDp=814 densityDpi=360 clientAttachState=1
```

## 1. The multiprocess decision

`WebViewDelegate.isMultiProcessEnabled()` reads a compiled-in flag and returns `true` without ever
asking `IWebViewUpdateService`. So the adapter's answer, which was `false` all along, never
reached Chromium: it took the multiprocess path and died in `ChildProcessLauncherHelperImpl`
resolving sandboxed child services the provider manifest does not declare here.

The probe reports the flag **and** the service **and** the effective value, in the order the
delegate reads them. Reporting the service alone is the trap — it says the opposite of what
happens.

## 2. Same-named libraries on the search path

Chromium reaches the NDK SurfaceControl surface with `dlopen("libandroid.so")` plus `dlsym`, and
gets whichever copy the search path names first. Two ship: the runtime's exports **none** of the
27 entry points, and the WebView one exports all of them. The search path lists the runtime
directory first, so the whole `ASurfaceTransaction` family failed to load.

Nothing in a symbol table shows this. Both files are called `libandroid.so`, and the choice is
made at runtime by search order — the same reason `oh-resolve` reported `288/289 resolved` for an
app whose WebView could not find fourteen functions.

**This check found a second instance before anything tripped over it**: `libjnigraphics.so` sits in
exactly the same position, WebView copy shadowed by the runtime's. That is why the shim now
resolves *any* bare soname against the WebView library directory for WebView's callers rather than
naming libraries one at a time.

`OBSERVED_SHADOWING` is not a failure. Shadowing only bites when the later copy is the one holding
the symbols the caller wants, and the probe reports the condition so the map can name the pair
instead of guessing. It stays `OBSERVED` after the shim fix, because both files still exist — what
changed is which one a WebView caller gets.

## 3. The window context

Chromium asks for one from `DisplayAndroidManager` while its browser process starts. The adapter
threw `UnsupportedOperationException`, and a throw here is fatal rather than degrading: every JNI
return path runs `CheckException`, so a pending Java exception below native code aborts the
process. A null would have been survivable.

The probe separates four outcomes a call site cannot tell apart — throws, null, answers with an
empty `Configuration`, answers properly.

### What `clientAttachState` does not say

It is the client's own record: `STATUS_INITIALIZED` 0, `ATTACHED` 1, `FAILED` 2.
`WindowContextController` sets it to `ATTACHED` whenever the call returns without throwing, so an
adapter that answers with a `Configuration` and registers nothing with OH reads **identically** to
a real attachment.

It separates answered from refused, and nothing more. Whether a configuration change is ever
delivered to the token has to be measured by waiting for one, which this probe does not do — so
the row it backs is `inert`, not `supplied`. An earlier draft of this probe called the field
`connected` and claimed it distinguished registration from a snapshot; it does not, and a probe
that overstates its reach is worse than no probe, because its output becomes evidence in the map.
