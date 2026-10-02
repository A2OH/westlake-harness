# gl-contracts probe

One launch checks the graphics contracts that Telegram, X, a video camera app and three games
depended on, each found by a whole-corpus run rather than before it:

| check | what it exercises | the regression it would have caught |
|---|---|---|
| `egl-init` | an app's own GL thread initializes EGL14 and finds an ES2 window config | EGL wrappers resolving the board's entry points with `RTLD_NEXT` (libGDX: "requires OpenGL ES 2.0"; Godot: "eglInitialize failed") |
| `textureview-frames` | frames an app renders into a TextureView are consumed by the UI | hwui's buffer import sent to the wrong EGL implementation (`EGL_BAD_DISPLAY`), a failing release fence |
| `consumer-stall` | the producer survives the UI thread blocking for 4 s and resumes | OH's 3000 ms buffer-request timeout, after which the Mali driver crashed on the failed dequeue |
| `terminate-keeps-display` | an app's `eglTerminate` leaves the display hwui draws with alone | the display torn down under hwui (`EGL_NOT_INITIALIZED`, X) |

It also records `answer compiled-code`: ART's view of whether the app's own code is precompiled.
Each check logs `[WL-GL-PROBE] check=<name> verdict=PASS|FAIL`; the probe ends with
`verdict=ALL_PASS` or `verdict=SOME_FAIL`. A crash ends it early, so a missing PASS is a failure.
Android passes every check.

Build: `./build.sh` (pure Java; javac, d8, aapt, apksigner from the Android SDK).
