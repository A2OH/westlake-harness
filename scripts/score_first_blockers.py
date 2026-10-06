#!/usr/bin/env python3
"""Score gap maps against the first blockers a regression run observed.

For every app that did not reach drawing with its own window on screen, the lifecycle classifier's
first blocker (harness.westlake_gap.lifecycle --json) is looked up in the app's gap map:

  named      a row that is not supplied names the blocker (predicted before launch)
  supplied   the row exists but says supplied: the harness thought the gap closed
  not-named  no row names it: a blind spot to fix in the harness
  device     the rows are supplied, and one answers as a device without the feature that the app
             asked before it closed itself (a role on a board with no telephony): Android on such
             a device stops the app the same way
  unscorable no blocker was recognized in the log, or it is a symptom no row type names: a native
             crash, an app exception with no platform symbol, an app's own native class

An app exception counts when its root cause (lifecycle's root_cause) names a service: a Kotlin cast
of a null manager by the manager's class, a compiled null check by its frame among a service row's
throwing sites.

The blocker text is reduced to a key: a missing symbol needs a row mentioning it (a std::__ndk1 one:
load:shadowed-by-board); an unbound platform native a jni:<class> row; a missing library a load:
or ndk: row naming it; a null system service its svc:<name> row. A graphics abort or a window
the platform never surfaced is a platform gap no row type covers yet, so it counts as not named.
A native crash counts when a row names a library its app frames are in: rows about a library's own
risk (an init array, an import version, a thread start, EGL looked up by handle) list them.
An activity that finished itself on start (lifecycle's self-finish) needs the row for what it asked
first: am:task-root, svc:bluetooth, am:own-implicit-intents, or a service row answering as a device
without the feature, for a service the app called in process before it left. An activity that
resumed and never drew (lifecycle's no-frame) needs a row for what holds its draws: am:post-create,
its own onPostCreate that the provider never called. A window whose buffer requests OH refused, with
the host screen showing (lifecycle's window-buffers), needs window:buffers-geometry: the geometry an
app library set on it in Android's terms.

Usage: score_first_blockers.py <lifecycle.json> <map-root> [<map-root> ...] [--out report.json]
"""
import argparse
import json
import re
from pathlib import Path


def find_map(app, roots):
    for root in roots:
        path = Path(root) / app / "gap-map.json"
        if path.exists():
            return json.loads(path.read_text())
    return None


_SYMBOL = re.compile(r"Error relocating [^:]*: (\w+)(?::|$)")  # the message may be cut short
_LIBRARY = re.compile(r"(?:Error loading shared library |library ')([\w+.-]+?\.so|\w+)\b")
_UPCALL = re.compile(r"No implementation found for [^(]*?([\w.$]+)\.\w+\(")
_PLATFORM = ("android.", "com.android.", "java.", "javax.", "sun.", "libcore.", "dalvik.")


def platform_key(category, blocker):
    """(kind, key) for a blocker a gap map could name, or None for one it cannot."""
    symbol = _SYMBOL.search(blocker)
    if symbol:
        return "symbol", symbol.group(1)
    upcall = _UPCALL.search(blocker)
    if upcall or category == "native-upcalls":
        owner = upcall.group(1) if upcall else blocker.rsplit(".", 1)[0]
        # An app's own native class: its library failed to load before, which is the blocker.
        return ("upcall", owner) if owner.startswith(_PLATFORM) else None
    library = _LIBRARY.search(blocker)
    if library and ("UnsatisfiedLinkError" in blocker or category == "native-loading"):
        return "library", library.group(1)
    if category == "native-symbols":
        return "symbol", blocker
    if category == "system-services" and " on null service" in blocker:
        manager = blocker.split(".")[0]
        service = manager[:-len("Manager")].lower() if manager.endswith("Manager") else manager.lower()
        return "service", {"telephony": "phone"}.get(service, service)
    if category in ("graphics", "package-manager") or blocker.startswith("no surface"):
        return "platform", blocker
    if category == "self-finish":
        return "exit", blocker
    if category == "no-frame":
        return "no-frame", blocker
    if category == "window-buffers":
        return "window-buffers", blocker
    return None  # a native crash or an app exception: a symptom no row type names


_NONNULL_CAST = re.compile(r"null cannot be cast to non-null type (android\.[\w.$]+)")


def root_cause_rows(cause, rows):
    """Service rows that name an app exception's root cause, or None if it names none: a Kotlin cast
    of a null manager names the manager's class; a compiled null check (getClass() on null) names
    no type, but its frame is one of the throwing sites a service row lists."""
    message = cause.get("message") or ""
    cast = _NONNULL_CAST.search(message)
    if cast:
        manager = "L" + cast.group(1).replace(".", "/") + ";"
        return [r for r in rows if r["id"].startswith("svc:") and (r.get("aosp_contract") or "").startswith(manager)]
    frame = cause.get("frame")
    if cause.get("exception") == "NullPointerException" and "getClass()" in message and frame:
        return [r for r in rows if r["id"].startswith("svc:") and frame in (r.get("throwing_sites") or [])]
    return None


_APP_DIRS = ("/data/local/tmp/asx/lib/", "/data/data/", "/data/user/")


def crash_rows(dump, rows):
    """Rows that name a library the crash's app frames are in, for a native crash: a row about a
    library's own risk (an init array, an import version, a thread start, EGL by handle) lists it in
    `libraries`. None when no such row names one, which leaves the crash unscorable."""
    frames = (dump or {}).get("frames") or []
    names = {frame["library"] for frame in frames
             if str(frame.get("path", "")).startswith(_APP_DIRS) and frame.get("library")}
    symbols = [frame["symbol"] for frame in frames if frame.get("symbol")]
    in_libraries = {frame.get("library") for frame in frames}
    # A row about one kind of call (a thread start, an allocator) also names the frames such a crash
    # shows; PPSSPP's crash in libhwui is not a thread-handle crash because its library has one.
    found = [r for r in rows if names & {str(name).rsplit("/", 1)[-1] for name in r.get("libraries") or []}
             and (not r.get("crash_symbols") or any(re.search(r["crash_symbols"], s) for s in symbols))
             and (not r.get("crash_libraries") or in_libraries & set(r["crash_libraries"]))
             and (not r.get("crash_kinds") or (dump or {}).get("kind") in r["crash_kinds"])]
    return found or None


def candidate_rows(category, blocker, rows, cause=None, finished=None, dump=None):
    """Rows that would name this blocker; None if it is not one a gap map could name."""
    if category == "native-crash" and dump:
        return crash_rows(dump, rows)
    key = platform_key(category, blocker)
    if key is None:
        return root_cause_rows(cause, rows) if cause else None
    kind, value = key
    text = lambda row: json.dumps(row)
    if kind == "symbol":
        # An NDK libc++ symbol missing means the board's libc++ was picked instead of the APK's,
        # which load:shadowed-by-board predicts.
        shadowed = value.startswith(("_ZNSt6__ndk1", "_ZNKSt6__ndk1"))
        return [r for r in rows if value in text(r) or (shadowed and r["id"] == "load:shadowed-by-board")]
    if kind == "upcall":
        return [r for r in rows if r["id"] == "jni:" + value]
    if kind == "library":
        return [r for r in rows if r["id"].startswith(("load:", "ndk:")) and value in text(r)]
    if kind == "service":
        return [r for r in rows if r["id"] == "svc:" + value]
    if kind == "exit":
        # An activity that closes itself on start asked something first: whether it is its task's
        # root, for hardware the device does not have, or for one of its own activities by an
        # implicit intent. A service answering as a device without the feature counts only if the
        # app called it in process before it left.
        called = set((finished or {}).get("local_services") or [])
        return [r for r in rows if r["id"] in ("am:task-root", "svc:bluetooth", "am:own-implicit-intents")
                or (r.get("device_answer") and r["id"].startswith("svc:") and r["id"][4:] in called)]
    if kind == "no-frame":
        return [r for r in rows if r["id"] == "am:post-create"]
    if kind == "window-buffers":
        return [r for r in rows if r["id"] == "window:buffers-geometry"]
    return []  # a platform behaviour no row type covers yet


def outcome_of(rows):
    """The outcome for the rows that would name a blocker: not-named when there are none, named when
    one is not supplied, device when all are and one answers as a device without the feature."""
    if not rows:
        return "not-named"
    if any(r["verdict"] != "supplied" for r in rows):
        return "named"
    if any(r.get("device_answer") for r in rows):
        return "device"
    return "supplied"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("lifecycle", type=Path)
    parser.add_argument("roots", nargs="+")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    results = []
    for entry in json.loads(args.lifecycle.read_text()):
        if entry["rung_name"] == "drawing" and entry.get("screen") != "host":
            continue
        app, category, blocker = entry["app"], entry.get("blocker_category"), entry.get("blocker")
        gap = find_map(app, args.roots)
        if gap is None:
            outcome, rows = "no-map", []
        elif not blocker:
            outcome, rows = "unscorable", []
        else:
            rows = candidate_rows(category, blocker, gap["rows"], entry.get("root_cause"), entry.get("self_finish"),
                                  entry.get("crash_dump"))
            if rows is None:
                outcome, rows = "unscorable", []
            else:
                outcome = outcome_of(rows)
        results.append({"app": app, "stage": entry["rung_name"], "category": category, "blocker": blocker,
                        "outcome": outcome, "rows": [r["id"] + "=" + r["verdict"] for r in rows][:3]})
    counts = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    scorable = sum(counts.get(k, 0) for k in ("named", "supplied", "not-named", "device"))
    print(f"{len(results)} apps short of drawing; scorable {scorable}: "
          f"named {counts.get('named', 0)}, marked supplied {counts.get('supplied', 0)}, "
          f"not named {counts.get('not-named', 0)}, a device's answer {counts.get('device', 0)}; "
          f"unscorable {counts.get('unscorable', 0)}; no map {counts.get('no-map', 0)}")
    for r in sorted(results, key=lambda r: (r["outcome"], r["app"])):
        if r["outcome"] != "unscorable":
            print(f"  {r['outcome']:10} {r['app']:18} {r['category']}: {r['blocker']}  {' '.join(r['rows'])}")
    if args.out:
        args.out.write_text(json.dumps({"counts": counts, "results": results}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
