# McDonald's past the sign-in screen: the home dashboard and the ordering flow

The sign-in benchmark stopped at the sign-in sheet. This one drives further: dismiss the sheet,
accept the welcome screen, open the ordering flow. Four blockers, two of them closed, plus two
defects in the harness's own ability to see what happened.

App: `com.mcdonalds.app` 26.31.1. Provider: Westlake `f6dc615` at the start, `8984f3c` at the end,
SELinux enforcing except where noted.

## What it reaches now

The home dashboard renders (menu card, daily deals, bottom tabs) and the ordering flow opens as far
as "Share your location". Tapping Continue there re-opens the same screen: the location permission
request reaches no permission controller in direct launch, so the flow cannot go on. The ordering
screens that need the app's bottom-navigation menu die on a null (M3).

## Blockers

[blockers.json](blockers.json), and the status of each against the fixed tree in
[map-fixed](map-fixed/GAP-MAP.md).

| | Screen | Cause | Status |
|---|---|---|---|
| M1 | home dashboard | Realm asked for the page size with bionic's selector number; OH musl reads 39 as `_SC_BC_STRING_MAX` and answered 1000, so Realm's rounding produced an unaligned mmap offset and the kernel refused it | closed (westlake `2f70628`) |
| M2 | WebView start-up | the in-process `IUserManager` threw for a method it did not implement, inside a JNI callback, and Chromium aborted | closed (westlake `9b8b861`) |
| M3 | ordering flow | the app's bottom-navigation menu is empty, so `showSelector` dereferences a null `MenuItem`: the ordering host loops on its loading animation, the restaurant picker takes the process down | **open** |
| M4 | welcome screen | the upgrade dialog is laid out wider than the display, putting its OK button off the right edge, and with no working back key it cannot be dismissed | **open** |

### M1 is a class, not an incident

`sysconf` resolves in musl and returns a plausible number, so nothing fails at load time; the wrong
answer only shows up as a rejected mmap offset three layers away. The same is true of every libc
call whose argument is a constant each libc numbers for itself. The new `libc:constant-namespace`
row looks for them, and the first scan it ran on found a second instance nobody had hit yet:
`pathconf`, used by two of McDonald's packaged libraries, where bionic's `_PC_NAME_MAX` is 4 and
musl's is 3. Fixed in the same shape (westlake `8984f3c`) before any app tripped over it.

### M3: configuration the app never loads

McDonald's builds its bottom navigation from configuration, not from a layout:

```java
List menu = AppConfigurationManager.a().v("user_interface_build.applicationmenu");
if (menu == null) menu = AppConfigurationManager.a().v("user_interface.applicationmenu");
menu.iterator();      // throws when both are null; the app swallows it
```

`ConfigHelper.v` reads an in-memory map that a startup step fills. That map stays null, so every
lookup returns null and the menu keeps at most its Home tab. Ruled out so far, each with evidence:

- **not the backend, not Akamai**: the configuration ships in the APK, `assets/server_config.json`,
  with `tabCount: 5` and all 11 menu entries, and the app's own SDK store on the device contains
  them parsed;
- **not asset listing**: the app reads a config file only if `getAssets().list("")` contains its
  name, and the new [asset-list probe](../../probes/asset-list) passes on the board;
- **not startup ordering**: the Application sets the static context its reader uses before the
  loader runs;
- **not the initializer being absent**: `APPSPAWNX_VERBOSE_CLASS=1` shows `AppConfigurationInitializer`
  loaded along with the whole initializer set, and 661 Gson class loads;
- **not CPU starvation**: the app polls `getPackageInfo("com.android.vending")` about 300 times a
  second while Play services are absent, but removing that cost (westlake `1415787`) changed nothing.

What remains is the app's startup chain not completing the configuration step. Settling that needs
method-level tracing, not class-load tracing.

### M4: the display width the app is told changes

The dialog probe now measures whether a dialog fits the display, and reproduces it. One run:

```
placement=CENTRED     ... screenWidth=1200
placement=NOT_CENTRED ... screenWidth=1083      <- after a second window was added
alertWidth=OVERFLOWS at 58 right=1141 screenWidth=1083
```

A later run reported `screenWidth=640`. The display metrics an app reads are not stable across
windows and launches, and a stock AlertDialog sizes itself from them, which is how McDonald's
upgrade dialog ended up unreachable. `wm:window-placement` is now a measured failure
([probe-results.json](probe-results.json)) rather than "supplied per source".

## What the harness could not see

Both were fixed, because a gap the harness cannot observe is a gap it cannot map.

- **Under SELinux enforcing the app's own log output is dropped**: the child inherits the spawner's
  `su`-labelled log socket and every write is denied. The JS error behind the Burger King keystore
  blocker was invisible until the board went permissive.
- **One app's chatter evicted every other log**: `getPackageInfo("com.android.vending")` wrote 59k
  copies of three lines in a single run and pushed everything else out of the hilog ring. Absent
  packages are now remembered and repeated adapter traces capped (westlake `1415787`).
- The default uncaught-exception handler logged an exception's message and no frames, because
  `printStackTrace` is a no-op here. It now walks and prints them (westlake `22d6020`); that is what
  turned "NullPointerException" into `McDBaseActivity.showSelector`.

## New checks from this session

| Check | Catches |
|---|---|
| `libc:constant-namespace` row | libc calls carrying a constant each libc numbers for itself, and whether the shim translates them for the app's own libraries or only for WebView |
| [asset-list probe](../../probes/asset-list) | an app that finds its assets only by listing them |
| dialog probe, `alertWidth` | a dialog wider than the display, which is unreachable however well it is centred |
