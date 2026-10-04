#!/usr/bin/env python3
"""Score gap maps against the first blockers a regression run observed.

For every app that did not reach drawing with its own window on screen, the lifecycle classifier's
first blocker (harness.westlake_gap.lifecycle --json) is looked up in the app's gap map:

  named      a row that is not supplied names the blocker (predicted before launch)
  supplied   the row exists but says supplied: the harness thought the gap closed
  not-named  no row names it: a blind spot to fix in the harness
  unscorable no blocker was recognized in the log, or it is a symptom no row type names: a native
             crash, an app exception with no platform symbol, an app's own native class

An app exception counts when its root cause (lifecycle's root_cause) names a service: a Kotlin cast
of a null manager by the manager's class, a compiled null check by its frame among a service row's
throwing sites.

The blocker text is reduced to a key: a missing symbol needs a row mentioning it (a std::__ndk1 one:
load:shadowed-by-board); an unbound platform native a jni:<class> row; a missing library a load:
or ndk: row naming it; a null system service its svc:<name> row. A graphics abort or a window
the platform never surfaced is a platform gap no row type covers yet, so it counts as not named.
An activity that finished itself on start (lifecycle's self-finish) needs the row for what it asked
first: am:task-root, or svc:bluetooth.

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


def candidate_rows(category, blocker, rows, cause=None):
    """Rows that would name this blocker; None if it is not one a gap map could name."""
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
        # root, or for hardware the device does not have.
        return [r for r in rows if r["id"] in ("am:task-root", "svc:bluetooth")]
    return []  # a platform behaviour no row type covers yet


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
            rows = candidate_rows(category, blocker, gap["rows"], entry.get("root_cause"))
            if rows is None:
                outcome, rows = "unscorable", []
            elif not rows:
                outcome = "not-named"
            elif any(r["verdict"] != "supplied" for r in rows):
                outcome = "named"
            else:
                outcome = "supplied"
        results.append({"app": app, "stage": entry["rung_name"], "category": category, "blocker": blocker,
                        "outcome": outcome, "rows": [r["id"] + "=" + r["verdict"] for r in rows][:3]})
    counts = {}
    for r in results:
        counts[r["outcome"]] = counts.get(r["outcome"], 0) + 1
    scorable = counts.get("named", 0) + counts.get("supplied", 0) + counts.get("not-named", 0)
    print(f"{len(results)} apps short of drawing; scorable {scorable}: "
          f"named {counts.get('named', 0)}, marked supplied {counts.get('supplied', 0)}, "
          f"not named {counts.get('not-named', 0)}; unscorable {counts.get('unscorable', 0)}; "
          f"no map {counts.get('no-map', 0)}")
    for r in sorted(results, key=lambda r: (r["outcome"], r["app"])):
        if r["outcome"] != "unscorable":
            print(f"  {r['outcome']:10} {r['app']:18} {r['category']}: {r['blocker']}  {' '.join(r['rows'])}")
    if args.out:
        args.out.write_text(json.dumps({"counts": counts, "results": results}, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
