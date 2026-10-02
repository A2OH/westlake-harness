# Scoring the gap maps against a run's first blockers (r77, 2026-10-01)

A blind batch scores the harness on new apps. This record scores it on every app at once, and on
the blocker a run actually hit. r77 was the whole corpus (327 apps: the F-Droid batches and the
top-apps batch) on framework 77. For each app that did not draw, the lifecycle classifier took the
first blocker from the child log. `scripts/score_first_blockers.py` then looked for it in that app's
gap map, made before launch against the same provider.

- **named:** a row that is not supplied names the blocker. The harness predicted it.
- **supplied:** the row exists, but says the gap is closed.
- **not named:** no row names it. This is a blind spot.
- **unscorable:** the log names no blocker, or it is a symptom no row type can name: an app
  exception with no platform symbol, a native crash, or the app's own native class.

Files: `lifecycle.json` (`python -m westlake_gap.lifecycle <logs> --json`) and `score.json`, the
result after the changes below. `r82-lifecycle.json` classifies the regression run at the end.

## Result

| | apps short of drawing | scorable | named | not named | unscorable |
|---|---|---|---|---|---|
| first pass | 59 | 15 | 8 | 7 | 44 |
| after the changes below | 57 | 11 | 9 | 2 | 46 |

The 9 named:

| app | first blocker | row |
|---|---|---|
| aaaaxy | `AConfiguration_delete` missing | `ndk:package` |
| duckrun, playmaker | `libcamera2ndk.so` missing | `load:needed-missing` |
| spotify | `libmediandk.so` missing | `load:needed-missing` |
| emacs | `fts_open` missing | `ndk:libc-abi` |
| linphone | UsageStatsManager on a null service | `svc:usagestats` |
| opencamera | `Camera._getCameraInfo` unregistered | `jni:android.hardware.Camera` |
| translator | the board's library shadows the app's | `load:shadowed-by-board` |
| instagram | `AHardwareBuffer_unlock` missing | `load:android-namespace-ndk:libandroid.so` (new) |

No row claimed a gap was closed when it was not.

The 46 unscorable apps:
- 21 log no blocker at all. They need hilog capture.
- 17 stop on an app exception.
- 7 stop on a native crash.
- 1 fails a library load the scorer could not tie to a row.

## The seven blind spots of the first pass

Three were the classifier's errors, not the harness's.

- **WhatsApp, `Process.readProcFile`:** a missing native the app caught. Its bind completed
  afterwards. A missing platform native now counts as a blocker only if no later lifecycle
  progress follows it.
- **AppManager, Snapchat, Fossify Voice Recorder, "no surface until its activity's window has an
  OH session":** each starts a second activity from its first. The first activity's window was
  held back while the second one drew. A held-back window followed by a swapped frame now counts
  as drawing. AppManager and Snapchat draw. Voice Recorder's real first blocker is an
  IllegalStateException in its process init.

One was a real gap the maps could not see:

- **Instagram, `AHardwareBuffer_unlock`:**
  - Libraries routed to the Android namespace, and libraries the app writes at run time, find
    `libandroid.so` in the WebView shim's directory before the runtime's.
  - That copy has about 75 exports and no `AHardwareBuffer_*`. The map had counted the symbol as
    supplied, because the runtime's `libhwui.so` exports it.
  - New row: `load:android-namespace-ndk:<lib>`, driven by `gap-map --android-namespace-dir`.
  - Westlake now forwards `AHardwareBuffer_*`, `android_res_*` and `AChoreographer_*` from the
    bionic shim. Instagram's packed `libscrollmerged.so` loads.
  - A three-library chain on the board confirmed that OH musl does resolve through transitive
    dependencies. The cause was the wrong copy of `libandroid.so`, not musl's symbol scope.

Two, Telegram and the video camera app geotagvideocamer, aborted in hwui with
`AutoBackendTextureRelease: Invalid GrBackendTexture`. No static row predicts this. TextureView is
referenced by 157 corpus apps, and only these two hit the abort: what differs is a producer actually
sending frames. It was fixed in the runtime instead, below.

## The TextureView chain, fixed in the bionic shim

Each fix exposed the next problem:

1. **Import.** Westlake's AHardwareBuffer is an OH native buffer, but hwui imported it the Android
   way (`EGL_NATIVE_BUFFER_ANDROID`). The shim now makes an OH window buffer over it and imports
   that with `EGL_NATIVE_BUFFER_OHOS`. geotagvideocamer draws.
2. **Damage region.** The board rejected `eglSetDamageRegionKHR` (`EGL_BAD_ACCESS`; Telegram,
   after 120 frames), and the deployed libhwui treats any failure as fatal. The hint is no longer
   passed on.
3. **`eglTerminate`.** X's and Telegram's own GL code terminated the display hwui renders with,
   and the next frame failed with `EGL_NOT_INITIALIZED`. On Android, hwui holds the display for
   the whole process, so the app's terminate never takes effect. It now leaves the display
   initialized.
4. **Two EGL implementations.** OH's `libEGL.so` (a wrapper) and the Mali driver serve one process.
   Each accepts only its own display handles, and hwui binds to the driver.
   - The shim first found the board functions with `RTLD_NEXT`. Its answer differed from process
     to process: libGDX reported "requires OpenGL ES 2.0" (burgerparty, doorsofdoom), and Godot
     reported "eglInitialize failed" (jigsaw). All three had drawn before.
   - Forcing `libEGL.so` for every call broke the import with `EGL_BAD_DISPLAY`.
   - Each wrapped call now goes to the implementation whose current display it names.
5. **Release fence.** The driver implements `eglDupNativeFenceFDANDROID` but does not export it.
   - hwui's call bound to `libEGL.so` with the driver's display, logging "invalid display pointer"
     on every TextureView frame (3,051 times in one run).
   - Without a release fence, the SurfaceTexture kept its old buffer, and hwui's swap failed with
     `EGL_BAD_ALLOC` after 150 to 3,200 frames.
   - The call now reaches the driver through its own `eglGetProcAddress`. With that: 0 errors, and
     Telegram ran 4,440 TextureView frames.

Targeted runs on the committed state:
- Telegram shows its welcome screen with the animated intro. That run was the exception: in most
  launches its own GL thread then crashes (see the regression check below).
- X shows its login screen.
- geotagvideocamer draws.
- burgerparty, doorsofdoom and jigsaw draw again.

A caution from this chain: an intermediate build appeared to fix Telegram. In fact its GL never
started. The screenshot had the welcome text but no animated logo, and the log showed 0
TextureView frames. "Drew" is not enough; check that the content the app renders itself is there.

## Other top-app movement

- **Threads:**
  - Facebook's SoLoader picks its native-library split by a path ending
    `split_config.<abi>.apk`; otherwise it reads the base APK.
  - Westlake staged splits as `<app>.<split>.apk`, so SoLoader read the base APK, which has no
    libraries, and got a null ZipEntry.
  - The launcher now stages each split as `split_<name>.apk`, and the split resolver recovers the
    name.
  - Threads now gets past this point and stops on a SIGSEGV on its startup thread (open).
- **Instagram:** its packed libraries load, but it reaches no activity within 45 s (open). Its one
  failed name lookup was a numeric-host probe, not a DNS fault.

## Regression check (r82)

The whole corpus was rerun on the committed state: framework 78 with the shim above.
`r82-lifecycle.json` is its classification.

- **Coverage:** 328 of 329 apps ran. The 327 also classified in r77 compare as 324 at the same
  lifecycle stage, 3 further along and none further back. 272 draw, against 270 in r77.
- **Gained:** X (its login screen) and geotagvideocamer (its map-tiles notice over a live MapLibre
  map, which renders through the TextureView path above). Both are confirmed on the screenshots.
  fmessages moved too, but that app varies from round to round.
- **Threads** stays at runtime-init but stops later: after the split fix it reaches a native crash
  on its startup thread.
- **Telegram is not a gain yet.**
  - It draws its welcome screen. Then its own GL thread (`EGLThread`) crashes with a null
    dereference (SIGSEGV at 0x40), at the same code site every time, about 120 TextureView frames in.
  - That happened in 5 of 6 launches under SELinux enforcing. The one clean launch, above, ran under
    permissive for a hilog capture.
  - The enforcing launches show SELinux denials only for a logging socket. The crash is open.
- **TikTok** had never launched, in r77 or in r82.
  - The harness named two of its Android-namespace libraries by SONAME: TikTok's
    `libeffect_plugin.so` is `libeffect.so`. The launcher refuses a target that is not one of the
    app's files, so it stopped before starting TikTok.
  - The gap map now emits file names. TikTok then launched for the first time, and at 45 s it was
    still binding its application, verifying its large dex.

## Commits

- Harness: `351c42c` (scorer), `54cbe2e` (Android-namespace rows), `e8224d9` (classifier), in #21;
  `f116483` (launch targets by file name).
- Westlake `corpus2-fixes`, in order:
  - `9ec07f4`: AHardwareBuffer forwarders, EGL import, damage region, `eglTerminate`.
  - `8894944`: AChoreographer forwarders.
  - `e9373ed`: `eglTerminate` keeps the display.
  - `db7a120`: split names.
  - `91ea00f`: EGL by display owner, release fence.
- Launcher (manifest): `a9dc34f`, which stages splits as `split_<name>.apk`.
