"""Structured events from a Westlake launch log on OpenHarmony.

A launch's stderr already records most of what the runtime did for the app -- which system
services it asked for and got null, which it answered in process, which natives were missing,
which classes failed to initialise, which activities started and whether a window drew -- but as
free text in several hundred lines. Reading it by hand is how every blocker in the loop was
found. This turns it into an ordered event list, so a launch is comparable with another launch
and with a trace of the same app on Android.

Not visible here: PackageManager stubs and other Log.d output go to hilog, which OH drops under
SELinux enforcing. Those need events emitted to stderr by the runtime itself.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# (kind, pattern, fields extracted from the groups)
_PATTERNS: list[tuple[str, re.Pattern[str], tuple[str, ...]]] = [
    ("uncaught", re.compile(r"\[UNCAUGHT\] thread='([^']+)' ([\w.$]+)(?::\s*(.*))?$"), ("thread", "error", "message")),
    ("bind-failed", re.compile(r"ensureBindApplication FAILED phase=\w+ cause\[(\d+)\]=([\w.$]+)(?::\s*(.*))?$"), ("depth", "error", "message")),
    ("launch-failed", re.compile(r"(?:J_invokeStaticMain_main_threw|FAILED to schedule launch): ([\w.$]+)(?::\s*(.*))?$"), ("error", "message")),
    ("caused-by", re.compile(r"^Caused by: ([\w.$]+)(?::\s*(.*))?$"), ("error", "message")),
    ("caused-by", re.compile(r"\[UNCAUGHT\]\s+caused by: ([\w.$]+)(?::\s*(.*))?$"), ("error", "message")),
    ("service-null", re.compile(r'\[OHServiceManager\] getService\("([^"]+)"\) \S+ null'), ("service",)),
    ("service-local", re.compile(r"\[WESTLAKE-LOCAL-SERVICE\] (\w+) bound in process"), ("service",)),
    ("service-call", re.compile(r"\[WESTLAKE-LOCAL-SERVICE\] (\w+)\.(\w+)$"), ("service", "method")),
    ("native-missing", re.compile(r"No implementation found for (\S+) ([\w.$]+)\("), ("returns", "method")),
    ("library-missing", re.compile(r"Error loading shared library (\S+?):? \(?(?:needed by (\S+?)\))?"), ("library", "needed_by")),
    ("class-init-failed", re.compile(r"class_linker\.cc:\d+\] (L[\w/$]+;) failed initialization: ([\w.$]+)"), ("class", "error")),
    ("native-load", re.compile(r"\[SOURCE-NATIVE-LOAD\] path=(\S+)"), ("path",)),
    ("activity-launch", re.compile(r"\[B47-SLA\] ENTRY bundle=\S+ ability=(\S+)"), ("activity",)),
    ("activity-theme", re.compile(r"\[B47-SLA\] theme from the manifest: (0x[0-9a-f]+)"), ("theme",)),
    ("window-held", re.compile(r"held back \S+: (.+)$"), ("reason",)),
    ("window-relayout", re.compile(r"\[OH_WSA-relayout\] requestedWH=(\S+)"), ("size",)),
    ("service-bind-local", re.compile(r"\[AdapterIAM-stub\] (bindService\w*) -> in-process (\S+)"), ("call", "component")),
    ("pending-intent-send", re.compile(r"\[WESTLAKE-PENDING-INTENT\] send accepted, not delivered: (.+)$"), ("intent",)),
    ("fatal-signal", re.compile(r"Fatal signal (\d+) \((\w+)\)"), ("signal", "name")),
    ("fatal-thread", re.compile(r"Thread: \d+ \"([^\"]+)\""), ("thread",)),
]

_PATTERNS_BY_KIND = {kind: pattern for kind, pattern, _ in _PATTERNS}

# Events that repeat on every frame or every lookup; kept once per distinct value.
_ONCE = {"service-null", "service-local", "service-call", "native-missing", "native-load",
         "window-relayout", "activity-theme"}


def parse(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for number, line in enumerate(text.splitlines(), 1):
        line = line.rstrip()
        for kind, pattern, fields in _PATTERNS:
            match = pattern.search(line)
            if not match:
                continue
            event = {"line": number, "kind": kind}
            for name, value in zip(fields, match.groups()):
                if value is not None:
                    event[name] = value.strip()[:240]
            key = (kind,) + tuple(v for k, v in event.items() if k not in ("line",))
            if kind in _ONCE:
                if key in seen:
                    break
                seen.add(key)
            events.append(event)
            if kind in ("bind-failed", "launch-failed", "caused-by", "uncaught"):
                native = _PATTERNS_BY_KIND["native-missing"].search(line)
                if native and ("native-missing", native.group(2)) not in seen:
                    seen.add(("native-missing", native.group(2)))
                    events.append({"line": number, "kind": "native-missing",
                                   "returns": native.group(1), "method": native.group(2)})
            break
    return events


def summarize(app: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    """The facts a comparison needs, derived from the ordered events."""
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_kind.setdefault(event["kind"], []).append(event)
    failure = next((e for e in events if e["kind"] in
                    ("bind-failed", "launch-failed", "uncaught", "fatal-signal", "window-held")), None)
    root = root_cause(events, failure)
    return {
        "app": app,
        "services_null": sorted({e["service"] for e in by_kind.get("service-null", [])}),
        "services_local": sorted({e["service"] for e in by_kind.get("service-local", [])}),
        "service_calls": sorted({f"{e['service']}.{e['method']}" for e in by_kind.get("service-call", [])}),
        "natives_missing": sorted({e["method"] for e in by_kind.get("native-missing", [])}),
        "libraries_missing": sorted({e["library"] for e in by_kind.get("library-missing", [])}),
        "classes_failed": sorted({f"{e['class']} ({e['error']})" for e in by_kind.get("class-init-failed", [])}),
        "activities": [e["activity"] for e in by_kind.get("activity-launch", [])],
        # A relayout means a window was laid out, not that the app is still on screen: the
        # lifecycle scorer's screenshot check decides that.
        "window_laid_out": bool(by_kind.get("window-relayout")) and not by_kind.get("window-held"),
        "first_failure": failure,
        "root_cause": root,
        "event_count": len(events),
    }


# Exceptions that only wrap the one that matters.
_WRAPPERS = {"java.lang.reflect.InvocationTargetException", "java.lang.RuntimeException",
             "java.lang.ExceptionInInitializerError", "org.koin.core.error.InstanceCreationException",
             "androidx.startup.StartupException"}


def root_cause(events: list[dict[str, Any]], failure: dict[str, Any] | None) -> dict[str, Any] | None:
    """The innermost non-wrapper exception of the first failure's cause chain."""
    if failure is None:
        return None
    if failure["kind"] == "bind-failed":
        chain = [e for e in events if e["kind"] == "bind-failed"]
        chain.sort(key=lambda e: int(e.get("depth", 0)))
    else:
        # Follow the cause chain: each "caused by" continues it while no other failure intervenes.
        chain = [failure]
        for e in events:
            if e["line"] <= failure["line"]:
                continue
            if e["kind"] == "caused-by":
                chain.append(e)
            elif e["kind"] in ("bind-failed", "launch-failed", "uncaught", "fatal-signal"):
                break
    meaningful = [e for e in chain if e.get("error") not in _WRAPPERS]
    root = meaningful[-1] if meaningful else chain[-1]
    if failure["kind"] == "fatal-signal":
        thread = next((e for e in events if e["kind"] == "fatal-thread" and e["line"] > failure["line"]), None)
        if thread:
            root = {**failure, "thread": thread["thread"]}
    return root


def parse_file(path: Path) -> dict[str, Any]:
    events = parse(path.read_text(errors="replace"))
    return {"summary": summarize(path.stem, events), "events": events}
