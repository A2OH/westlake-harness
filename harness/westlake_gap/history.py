"""Each app of a round against its own earlier rounds: regressions, improvements and flaky apps.

A single latest verdict mixes three things: a real change in Westlake, an app that draws in some
rounds and not others, and a disturbed run. This sets an app's verdict in a round beside its verdicts
in the rounds before it (the corpus's round-<tag>.log files, ordered by the time each round ended):

    regression   it does not draw now, and drew in every earlier round of the window
    improvement  it draws now, and drew in none of them
    settled      it changed once, in an earlier round, and has stayed so since (a fix landing)
    flaky        it changed more than once in the window
    steady       the same as every earlier round
    new          no earlier round ran it

    python3 -m westlake_gap.history <corpus-dir> <tag> [--window 4] [--json out.json]

With --rates (no tag), each app's pass rate instead: the share of its last <window> rounds in which it
drew, the figure to report where one latest verdict hides flakiness.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
from pathlib import Path

_ROW = re.compile(r"^hk-(\S+)\s+(\d+)\s+(\S+)\s+(\d+)\s+(\d+)\s*(.*)$")
_DONE = re.compile(r"^(\w{3} \w{3} +\d+ \d\d:\d\d:\d\d) \S+ (\d{4}) (\S+) done$")


def read_round(path: Path) -> tuple[float | None, dict[str, tuple[str, str]]]:
    """A round log's end time (seconds, None when it never finished) and its last row per app:
    (rung name, blocker). A log prints its table again after each batch, so the last row counts."""
    verdicts: dict[str, tuple[str, str]] = {}
    ended = None
    for line in path.read_text(errors="replace").splitlines():
        match = _ROW.match(line.rstrip())
        if match:
            verdicts[match[1]] = (match[3], match[6].strip())
            continue
        match = _DONE.match(line.strip())
        if match:
            when = datetime.datetime.strptime(" ".join(match[1].split()) + " " + match[2], "%a %b %d %H:%M:%S %Y")
            ended = when.timestamp()
    return ended, verdicts


def rounds(corpus: Path) -> list[tuple[str, float, dict[str, tuple[str, str]]]]:
    """Every round of the corpus but the shared Play services rounds, oldest first: (tag, end, verdicts).
    A round that never logged its end is placed by its file's modification time."""
    out = []
    for path in corpus.glob("round-*.log"):
        tag = path.name[len("round-"):-len(".log")]
        if tag.endswith("play"):
            continue
        ended, verdicts = read_round(path)
        if verdicts:
            out.append((tag, ended if ended is not None else os.path.getmtime(path), verdicts))
    return sorted(out, key=lambda r: r[1])


def classify(drawing_now: bool, drew_before: list[bool]) -> tuple[str, int | None]:
    """drew_before: the earlier rounds' answers, newest first. Returns the class and, for a settled app,
    the index in drew_before of the round it changed in."""
    if not drew_before:
        return "new", None
    sequence = [drawing_now] + drew_before
    changes = [i for i in range(len(sequence) - 1) if sequence[i] != sequence[i + 1]]
    if not changes:
        return "steady", None
    if len(changes) > 1:
        return "flaky", None
    if changes[0] == 0:
        return ("improvement" if drawing_now else "regression"), None
    return "settled", changes[0] - 1


def compare(corpus: Path, tag: str, window: int = 4) -> list[dict]:
    """Each app of round <tag> with its class, its verdict and its last <window> earlier verdicts."""
    ordered = rounds(corpus)
    index = next((i for i, r in enumerate(ordered) if r[0] == tag), None)
    if index is None:
        raise SystemExit("no round " + tag + " in " + str(corpus))
    _, _, now = ordered[index]
    out = []
    for app, (rung, blocker) in sorted(now.items()):
        before = [(t, v[app]) for t, _, v in reversed(ordered[:index]) if app in v][:window]
        drew_before = [v[0] == "drawing" for _, v in before]
        kind, changed = classify(rung == "drawing", drew_before)
        row = {"app": app, "class": kind, "rung": rung, "blocker": blocker,
               "before": [{"round": t, "rung": v[0]} for t, v in before]}
        if changed is not None:
            row["changed_in"] = before[changed][0]
        out.append(row)
    return out


def pass_rates(corpus: Path, window: int = 4) -> list[dict]:
    """Each app's last <window> verdicts (newest first) and how many of them drew, apps that drew in
    some but not all first."""
    latest: dict[str, list[tuple[str, str]]] = {}
    for tag, _, verdicts in reversed(rounds(corpus)):
        for app, (rung, _) in verdicts.items():
            seen = latest.setdefault(app, [])
            if len(seen) < window:
                seen.append((tag, rung))
    out = [{"app": app, "runs": len(seen), "drew": sum(r == "drawing" for _, r in seen),
            "rounds": [t + ":" + ("drew" if r == "drawing" else r) for t, r in seen]}
           for app, seen in latest.items()]
    return sorted(out, key=lambda r: (not (0 < r["drew"] < r["runs"]), r["drew"] / r["runs"], r["app"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("corpus", type=Path)
    parser.add_argument("tag", nargs="?")
    parser.add_argument("--rates", action="store_true", help="pass rate per app over its last rounds")
    parser.add_argument("--window", type=int, default=4, help="earlier rounds to compare with (default 4)")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    if args.rates:
        rates = pass_rates(args.corpus, args.window)
        if args.json:
            args.json.write_text(json.dumps(rates, indent=1))
        buckets: dict[str, int] = {}
        for row in rates:
            key = "always" if row["drew"] == row["runs"] else ("never" if row["drew"] == 0 else "sometimes")
            buckets[key] = buckets.get(key, 0) + 1
        print("%d apps over their last %d rounds: %s" % (len(rates), args.window,
                                                         ", ".join("%d %s" % (n, k) for k, n in sorted(buckets.items()))))
        for row in rates:
            if 0 < row["drew"] < row["runs"]:
                print("%-45s %d/%d drew  (%s)" % (row["app"][:45], row["drew"], row["runs"], " ".join(row["rounds"])))
        return
    if not args.tag:
        parser.error("a round tag, or --rates")
    rows = compare(args.corpus, args.tag, args.window)
    if args.json:
        args.json.write_text(json.dumps(rows, indent=1))
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["class"]] = counts.get(row["class"], 0) + 1
    print(args.tag + ": " + ", ".join("%d %s" % (n, c) for c, n in sorted(counts.items())))
    for name in ("regression", "improvement", "flaky", "settled"):
        for row in (r for r in rows if r["class"] == name):
            history = " ".join(b["rung"] for b in row["before"])
            note = (" (changed in %s)" % row["changed_in"]) if "changed_in" in row else ""
            print("%-11s %-45s %-12s before: %s%s%s" % (name, row["app"][:45], row["rung"], history, note,
                                                         ("  | " + row["blocker"][:80]) if row["blocker"] not in ("", "-") else ""))


if __name__ == "__main__":
    main()
