"""How far a launch actually got, instead of whether an app lit up.

"Did it render" is the obvious way to score a launch loop and it is the wrong one, in both
directions. On 2026-09-22 a shim fix took NewPipe and AnkiDroid from SIGTRAP with fourteen
symbol-load failures to no signal and zero -- unambiguously correct, traced to a specific
commit-ordering regression -- and neither app rendered. Scored on rendering, a correct fix reads
as a failure. In the other direction Aegis and AntennaPod rendered before any of it and would have
rendered afterwards regardless; scored on rendering they look like evidence and carry none.

What separates those cases is how far the process got before it stopped, which the launch log
already says. The rungs below are the ones that actually discriminated across a ten-app corpus --
each was checked against apps whose outcome was known from a screenshot, not chosen for being
plausible.

A rung plus the identity of the first blocker is the score. The rung says how far; the blocker
says what to fix; neither alone is enough.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

#: Ordered rungs. Each entry is (name, predicate) and a launch's rung is the highest one whose
#: predicate holds *and* all of whose predecessors hold -- a later marker with an earlier one
#: missing means the markers are wrong, and that is reported rather than smoothed over.
RUNGS = (
    "spawned",
    "runtime-init",
    "bound",
    "activity",
    "view",
    "drawing",
)

#: Markers, established by comparing apps with known outcomes rather than by reading the source.
#:
#: ``activity`` means an activity launch was *attempted*, evidenced either by a view existing or
#: by an explicit activity-launch failure. An earlier version thresholded ``[B47-SLA]`` line counts
#: (five for a request, ten once it proceeds); that held for one round and then failed, because
#: NewPipe and OONI Probe drew forty and eleven frames respectively with only five. Counts of a
#: progress log are not a lifecycle signal. No marker here separates "reached the activity" from
#: "built a view" on its own, so this rung is inferred from the two outcomes that are visible.
#:
#: ``view`` uses DecorView because it was the single cleanest separator found: present only in the
#: apps confirmed rendering by screenshot, absent in every app that stopped earlier.
_MARKERS = {
    "runtime-init": (re.compile(r"kRegJNI loop done"), 1),
    "bound": (re.compile(r"sBindAppDone=true"), 1),
    "activity": (re.compile(r"Unable to (?:start|instantiate) activity|DecorView"), 1),
    "view": (re.compile(r"DecorView"), 1),
}

_RELAYOUT = re.compile(r"OH_WSA-relayout")
_HELD_BACK = re.compile(r"held back")
_FATAL = re.compile(r"Fatal signal")

#: First-blocker patterns, most specific first. Each yields (category, identity).
_BLOCKERS = (
    (re.compile(r"Couldn't find meta-data for provider with authority (\S+)"),
     "package-manager", "resolveContentProvider({0})"),
    (re.compile(r"method '[^']*\b(\w+Manager)\.(\w+)\([^)]*\)' on a null object reference"),
     "system-services", "{0}.{1} on null service"),
    (re.compile(r"Unable to load function (ASurface\w+)"),
     "native-loading", "{0} via dlopen(libandroid.so)"),
    (re.compile(r"No implementation found for [^(]*?([\w.$]+\.\w+)\("),
     "native-upcalls", "{0}"),
    (re.compile(r"Error relocating \S+: (\w+): symbol not found"),
     "native-symbols", "{0}"),
    (re.compile(r"Couldn't load shared library '(\w+)'"),
     "native-loading", "library '{0}'"),
    (re.compile(r"Unable to instantiate activity ComponentInfo\{[^}]*\}: [\w.]*?(\w+(?:Exception|Error)): ([^\n]{0,60})"),
     "app-framework", "instantiate activity: {0}: {1}"),
    (re.compile(r"Unable to start activity ComponentInfo\{[^}]*\}: [\w.]*?(\w+(?:Exception|Error))"),
     "app-framework", "start activity: {0}"),
    (re.compile(r"RuntimeException: (bindService\(\) failed)"),
     "system-services", "{0}"),
    (re.compile(r"held back [\dx]+: (no surface until its activity's window has an OH session)"),
     "app-framework", "{0}"),
)

#: Lines every launch emits. Counting these as blockers was a real error earlier in the work --
#: they look like failures and are load-bearing for nothing.
_NOISE = re.compile(
    r"No field sService in InputManagerGlobal"
    r"|skipping real AMS adapter"
    r"|getService\(\"\w+\"\) . null"
    r"|Unable to open '[^']*\.dm'"
    r"|Unable to find entry classes\d*\.dex"
)


@dataclass
class Score:
    app: str
    rung: int
    rung_name: str
    lines: int
    fatal: int
    relayouts: int
    held_back: int
    blocker_category: str | None = None
    blocker: str | None = None
    blocking: bool = True
    markers: dict = field(default_factory=dict)
    anomaly: str | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()
                if v is not None and not (k == "blocker_category" and self.blocker is None)}


def first_blocker(text: str) -> tuple[str, str] | tuple[None, None]:
    """The first blocker by log order, not by pattern order.

    Scanning pattern-first reports whichever pattern happens to be listed first, which is how an
    app that crashed on one thing gets filed under another. This finds every match, then keeps the
    earliest in the file.

    Earliest-in-file is closer to the cause than pattern order is, but it is not the cause. An
    app's own crash handler runs *after* whatever it caught, so a report-dialog failure can sort
    first while being downstream of the thing worth fixing -- AnkiDroid does exactly this. Treat
    the answer as where to start reading, not as the diagnosis.
    """
    # Blank the noise first, keeping offsets so "earliest match" still means earliest in the log.
    # None of the patterns below match it today; this is so that stays true when one is added.
    text = _NOISE.sub(lambda m: " " * len(m.group(0)), text)
    best: tuple[int, str, str] | None = None
    for pattern, category, template in _BLOCKERS:
        match = pattern.search(text)
        if match is None:
            continue
        if best is None or match.start() < best[0]:
            best = (match.start(), category, template.format(*match.groups()))
    return (best[1], best[2]) if best else (None, None)


def score(app: str, text: str) -> Score:
    lines = text.count("\n")
    counts = {
        name: len(pattern.findall(text)) for name, (pattern, _) in _MARKERS.items()
    }
    relayouts = len(_RELAYOUT.findall(text))
    held = len(_HELD_BACK.findall(text))
    counts["drawing"] = relayouts if held == 0 else 0

    # Every rung is evaluated, and the score is the HIGHEST that passed rather than the longest
    # unbroken run. The markers are not equally reliable and a later one is stronger evidence than
    # an earlier one: an app with a DecorView and forty relayouts reached its activity whatever the
    # activity marker says. Stopping at the first miss meant a weak marker could veto strong
    # evidence above it -- NewPipe drew forty frames and scored "bound" because a count threshold
    # fitted to one round did not hold in the next. A skipped rung is reported, not used to cap.
    passed = {"spawned": True}
    for name in RUNGS[1:]:
        if name == "drawing":
            passed[name] = relayouts > 0 and held == 0
        else:
            pattern, threshold = _MARKERS[name]
            passed[name] = counts[name] >= threshold

    rung = max(i for i, name in enumerate(RUNGS) if passed[name])
    skipped = [name for name in RUNGS[:rung] if not passed[name]]
    anomaly = ("reached %s without %s" % (RUNGS[rung], ", ".join(skipped))) if skipped else None
    category, blocker = first_blocker(text)
    # An app on the top rung with no fatal signal got where it was going. Anything matched in its
    # log is a finding, not the reason it stopped -- AntennaPod draws fine while reporting a
    # missing nPurgePendingResources. Calling that a blocker would put a non-issue at the top of
    # the worklist, which is the same failure as ranking stubs by how many apps ask for them.
    blocking = not (rung == len(RUNGS) - 1 and len(_FATAL.findall(text)) == 0)
    return Score(app=app, rung=rung, rung_name=RUNGS[rung], lines=lines,
                 fatal=len(_FATAL.findall(text)), relayouts=relayouts, held_back=held,
                 blocker_category=category, blocker=blocker, blocking=blocking,
                 markers=counts, anomaly=anomaly)


def score_paths(paths: list[Path]) -> list[Score]:
    return [score(path.stem, path.read_text(errors="replace")) for path in sorted(paths)]


def table(scores: list[Score]) -> str:
    width = max((len(s.app) for s in scores), default=3)
    head = "%-*s  %-4s %-12s %6s %5s  %s" % (width, "app", "rung", "reached", "lines", "fatal",
                                             "first blocker")
    rows = [head, "-" * len(head)]
    for s in sorted(scores, key=lambda s: (-s.rung, s.app)):
        rows.append("%-*s  %-4d %-12s %6d %5d  %s" % (
            width, s.app, s.rung, s.rung_name, s.lines, s.fatal,
            "-" if s.blocker is None
            else "%s%s: %s" % ("" if s.blocking else "(non-blocking) ",
                               s.blocker_category, s.blocker)))
        if s.anomaly:
            rows.append("%-*s  !! %s" % (width, "", s.anomaly))
    return "\n".join(rows)


def compare(before: list[Score], after: list[Score]) -> str:
    """Round-over-round movement. A fix is judged by this, not by whether anything rendered."""
    index = {s.app: s for s in before}
    rows = ["%-12s %-22s %-22s %s" % ("app", "before", "after", "")]
    rows.append("-" * 72)
    for s in sorted(after, key=lambda s: s.app):
        was = index.get(s.app)
        if was is None:
            rows.append("%-12s %-22s %-22s new" % (s.app, "-", s.rung_name))
            continue
        # Rung alone is too coarse to be the whole verdict, which this tool's own first run
        # proved: the shim fix cleared AnkiDroid's fatal signal and carried it two hundred lines
        # further, and a rung-only comparison called that "unchanged". Movement inside a rung is
        # still movement, and clearing a fatal signal is the clearest kind.
        notes = []
        if was.fatal > s.fatal:
            notes.append("fatal %d->%d" % (was.fatal, s.fatal))
        elif s.fatal > was.fatal:
            notes.append("NEW FATAL %d->%d" % (was.fatal, s.fatal))
        if was.lines and abs(s.lines - was.lines) * 10 >= was.lines:
            notes.append("%+d lines" % (s.lines - was.lines))
        if was.blocker != s.blocker:
            notes.append("blocker changed")

        if s.rung > was.rung:
            verdict = "ADVANCED +%d" % (s.rung - was.rung)
        elif s.rung < was.rung:
            verdict = "REGRESSED -%d" % (was.rung - s.rung)
        elif notes:
            verdict = "same rung"
        else:
            verdict = "unchanged"
        if notes:
            verdict += " (" + ", ".join(notes) + ")"
        rows.append("%-12s %-22s %-22s %s" % (
            s.app, "%d %s" % (was.rung, was.rung_name), "%d %s" % (s.rung, s.rung_name), verdict))
    return "\n".join(rows)


def main(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("paths", nargs="+", type=Path,
                        help="child stderr files, or directories of them")
    parser.add_argument("--before", type=Path, help="a directory of the previous round, to compare")
    parser.add_argument("--json", type=Path, help="write the scores here")
    args = parser.parse_args(argv)

    files: list[Path] = []
    for path in args.paths:
        files.extend(sorted(path.glob("*.stderr")) if path.is_dir() else [path])
    if not files:
        parser.error("no .stderr files found")
    scores = score_paths(files)
    print(table(scores))
    if args.before:
        print()
        print(compare(score_paths(sorted(args.before.glob("*.stderr"))), scores))
    if args.json:
        args.json.write_text(json.dumps([s.as_dict() for s in scores], indent=1) + "\n")
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
