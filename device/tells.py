#!/usr/bin/env python3
"""tells.py <tag> [<tag>...]  -- what the runtime told about each app, and how each app ended.

Step T0 of analysis/RUNTIME-TELLS.md: no runtime change. It reads the markers the runtime already
writes as tells, together with any `[WESTLAKE-TELL]` lines, from each app of a round in
$WL_SC/inputs/logs/<tag>/:
  hk-<package>.stderr          the app's stderr (tells, Java ends, loader reasons)
  hk-<package>.hilog           the system log (fatal signals, the crash dumper timing out, PM stubs)
  hk-<package>.cppcrash        a crash dump taken after the launch, when there is one
  hk-<package>.explore/        the Level 2 explorer's explore.json (whether and when the app ended)

For each app that ended, it names how it ended. In order of precedence:
  java-exit        System.exit, with the stack that called it ([WESTLAKE-EXIT] ... called on thread)
  self-signal      the process signalled itself, with the stack ([WESTLAKE-KILL])
  uncaught         an uncaught Java exception ([UNCAUGHT], or [INITCHILD-FAIL] at startup)
  explorer-back    the explorer pressed Back on the app's last screen, and Westlake ended the process
                   where Android keeps it cached. A signal during that exit is noted in the detail: on
                   2026-11-07 two apps' GPU driver thread aborted while their process was going away
  crash            a fatal signal (the system's signal handler line, or a crash dump)
  dump-timeout     a fatal signal whose dump timed out: no crash site anywhere (a sub-kind of crash)
  exit-no-stack    the shutdown hook ran, with no System.exit on any thread
  silent           none of the above: each one is a tell still missing. When the app's own signal
                   handler took a signal first (a protector's deliberate trap), the detail says so

It also gathers each app's tells: the contract, the answer, whether the answer is Android's, the
detail, and the stderr line where it was first seen. For an app that ended, the last tell in its
stderr before the end that is a failure or a stand-in, and that not nearly every app reports, is
printed as the candidate cause. It is a candidate, never a proof.

Writes <tag>-tells.json beside the logs and prints, for each tag, the counts of how apps ended, the
silent apps, and the contracts told by the most apps. Contracts told by nearly every app (90% or
more) describe the provider, not the app, and are listed apart (ADR-0001)."""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ENDS = ["java-exit", "self-signal", "uncaught", "explorer-back", "crash", "dump-timeout", "exit-no-stack", "silent"]

# Markers the runtime writes today, read as tells: (pattern, contract, answer, fidelity, detail).
LEGACY = [
    (re.compile(r"\[WESTLAKE-LOADER\] (\S+) by name failed \((.*)\); opening the path"),
     lambda m: ("load:" + m[1], "failed", "stand-in", m[2])),
    (re.compile(r"\[WESTLAKE-LOADER\] (\S+) by name gave another library"),
     lambda m: ("load:" + m[1], "another", "unknown", "older message: the open may have failed")),
    (re.compile(r'\[OHServiceManager\] getService\("([^"]+)"\) → null'),
     lambda m: ("svc:" + m[1], "null", "unknown", "")),
    (re.compile(r"^\[(Adapter\w+?)(?:-stub)?\] (\w+) \(no-op\)$"),
     lambda m: ("binder:" + m[1] + "." + m[2], "default", "unknown", "")),
    (re.compile(r"\[WESTLAKE-STALE-DESTROY\] dropped"),
     lambda m: ("lifecycle:stale-destroy", "dropped", "android", "a destroy for an activity already gone")),
    (re.compile(r'Unable to set property "([^"]*)"'),
     lambda m: ("sym:__system_property_set", "refused", "android", m[1])),
]
HILOG_TELLS = [
    (re.compile(r"OH_PMAdapter: \[STUB\] (\w+)"), lambda m: ("binder:IPackageManager." + m[1], "stub", "unknown", "")),
    (re.compile(r"OH_WSAdapter: \[STUB\] (\w+)"), lambda m: ("binder:IWindowSession." + m[1], "stub", "unknown", "")),
    (re.compile(r"OH_WSAdapter: \[STAND-IN\] (\w+) - (.*)"),
     lambda m: ("binder:IWindowSession." + m[1], "fixed", "stand-in", m[2].strip())),
]
TELL = re.compile(r"\[WESTLAKE-TELL\] (\{.*\})")
CHILD = re.compile(r"adapter_child_(\d+)\.stderr")
FRAME = re.compile(r"^\s*at ([\w$.<>]+)\(")
PLATFORM = ("java.", "javax.", "android.", "androidx.", "com.android.", "dalvik.", "libcore.", "sun.", "kotlin.",
            "kotlinx.", "adapter.")


def app_frame(lines: list[str], start: int) -> str:
    """The first frame of the stack starting at `start` that is not the platform's: the app's own code."""
    for line in lines[start:start + 40]:
        m = FRAME.match(line)
        if m is None:
            if line.lstrip().startswith(("...", "Caused by", "Suppressed")):
                continue
            break
        if not m[1].startswith(PLATFORM):
            return m[1]
    return ""


def read(path: Path) -> list[str]:
    try:
        return path.read_text(errors="replace").splitlines()
    except OSError:
        return []


def load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def end_of(stderr: list[str], hilog: list[str], crash: list[str], explore: dict, pid: str) -> tuple[str, str, int]:
    """How an app that ended did so: (kind, detail, stderr line or -1)."""
    for i, line in enumerate(stderr):
        if "[WESTLAKE-EXIT]" in line and "called on thread" in line:
            thread = line.split("called on thread", 1)[1].strip()
            return "java-exit", f"thread {thread} {app_frame(stderr, i + 1)}".strip(), i
    for i, line in enumerate(stderr):
        if "[WESTLAKE-KILL]" in line:
            sig = line.rsplit("signal", 1)[-1].strip()
            return "self-signal", f"signal {sig} {app_frame(stderr, i + 1)}".strip(), i
    uncaught = [(i, l) for i, l in enumerate(stderr) if l.startswith("[UNCAUGHT]") or "[INITCHILD-FAIL]   caused by:" in l]
    if uncaught:
        i, line = uncaught[-1]
        return "uncaught", line.split("]", 1)[1].strip()[:200], i
    signal = None
    timeout = False
    for line in hilog:
        cols = line.split()
        if len(cols) < 4 or cols[2] != pid:
            continue
        if "DFX_SignalHandler :: signo(" in line and "threadName(" in line:
            signal = re.search(r"signo\((\d+)\).*threadName\(([^)]*)\)", line)
        elif "DfxSignalHandler: waitpid" in line and "timeout" in line:
            timeout = True
    dump = ""
    if crash:
        reason = next((l.split(":", 1)[1] for l in crash if l.startswith("Reason:")), "")
        top = next((l for l in crash if l.startswith("#00 ")), "").split()
        dump = f"{reason.strip()} at {' '.join(top[3:5]) if len(top) > 3 else '?'}"
    if (explore or {}).get("died_after") == "back":
        during = f"signal {signal[1]} on thread {signal[2]}" if signal is not None else dump
        return "explorer-back", "Back on the app's last screen" + (f"; {during} during the exit" if during else ""), -1
    if dump:
        return "crash", dump, -1
    if signal is not None:
        kind = "dump-timeout" if timeout else "crash"
        return kind, f"signal {signal[1]} on thread {signal[2]}", -1
    for i, line in enumerate(stderr):
        if "[WESTLAKE-EXIT]" in line:
            return "exit-no-stack", "the shutdown hook ran; no System.exit on any thread", i
    handled = None
    for line in hilog:
        cols = line.split()
        if len(cols) >= 4 and cols[2] == pid and "call usr sigaction for signal:" in line:
            handled = line.rsplit("signal:", 1)[1].split()[0]
    if handled is not None:
        return "silent", f"after the app's own handler took signal {handled}", -1
    return "silent", "", -1


def tells_of(stderr: list[str], hilog: list[str]) -> list[dict]:
    found: dict[tuple, dict] = {}

    def add(contract, answer, fidelity, detail, where, source):
        key = (contract, answer, detail)
        if key in found:
            found[key]["count"] += 1
        else:
            found[key] = {"contract": contract, "answer": answer, "fidelity": fidelity, "detail": detail,
                          "count": 1, "line": where, "source": source}

    for i, line in enumerate(stderr):
        m = TELL.search(line)
        if m:
            try:
                t = json.loads(m[1])
                add(t.get("contract", "?"), t.get("answer", "?"), t.get("fidelity", "unknown"),
                    str(t.get("detail", ""))[:200], i, "tell")
            except ValueError:
                pass
            continue
        for pattern, make in LEGACY:
            m = pattern.search(line)
            if m:
                add(*make(m), i, "marker")
                break
    for line in hilog:
        for pattern, make in HILOG_TELLS:
            m = pattern.search(line)
            if m:
                add(*make(m), -1, "hilog")
    return sorted(found.values(), key=lambda t: (t["line"] if t["line"] >= 0 else 10**9))


def one_app(logs: Path, app: str) -> dict:
    stderr = read(logs / f"{app}.stderr")
    hilog = read(logs / f"{app}.hilog")
    crash = read(logs / f"{app}.cppcrash")
    explore = load_json(logs / f"{app}.explore" / "explore.json")
    pid = next((m[1] for m in (CHILD.search(l) for l in stderr[:5]) if m), "")
    tells = tells_of(stderr, hilog)
    record = {"explored": explore is not None, "tells": tells}
    if explore is not None:
        record["explore"] = {k: explore.get(k) for k in ("seconds", "screens", "died_at", "died_after")}
    ended = explore is not None and explore.get("died_at") is not None
    record["ended"] = ended
    if ended:
        kind, detail, at = end_of(stderr, hilog, crash, explore, pid)
        record["end"] = {"kind": kind, "detail": detail, "line": at}
    return record


def cause_candidate(record: dict, wide: set) -> str:
    """The last failure or stand-in the app's stderr told before it ended, among tells not nearly every app gives."""
    at = record["end"]["line"]
    before = [t for t in record["tells"] if t["line"] >= 0 and (at < 0 or t["line"] <= at)
              and (t["contract"], t["answer"]) not in wide
              and (t["answer"] in ("failed", "another", "refused") or t["fidelity"] == "stand-in")]
    if not before:
        return ""
    last = before[-1]
    return f"{last['contract']} {last['answer']}" + (f": {last['detail']}" if last["detail"] else "")


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__.splitlines()[0], file=sys.stderr)
        return 2
    root = Path(os.environ.get("WL_SC", "")) / "inputs" / "logs"
    for tag in sys.argv[1:]:
        logs = root / tag
        apps = sorted(p.name[:-len(".stderr")] for p in logs.glob("hk-*.stderr"))
        if not apps:
            print(f"{tag}: no app logs in {logs}", file=sys.stderr)
            continue
        result = {app: one_app(logs, app) for app in apps}

        reach = defaultdict(set)
        for a in apps:
            for t in result[a]["tells"]:
                reach[(t["contract"], t["answer"])].add(a)
        wide = {k for k, v in reach.items() if len(apps) >= 10 and len(v) >= 0.9 * len(apps)}
        explored = [a for a in apps if result[a]["explored"]]
        ended = [a for a in explored if result[a]["ended"]]
        for a in ended:
            candidate = cause_candidate(result[a], wide)
            if candidate:
                result[a]["cause_candidate"] = candidate
        (logs.parent / f"{tag}-tells.json").write_text(json.dumps(result, indent=1))
        kinds = Counter(result[a]["end"]["kind"] for a in ended)
        print(f"== {tag}: {len(apps)} apps, {len(explored)} explored, {len(ended)} ended, "
              f"{kinds.get('silent', 0)} silent")
        for kind in ENDS:
            if kinds.get(kind):
                print(f"  {kinds[kind]:4d}  {kind}")
        for a in ended:
            r = result[a]
            cause = f"  <- {r['cause_candidate']}" if "cause_candidate" in r else ""
            print(f"    {a[3:]:44s} {r['end']['kind']:13s} {r['end']['detail'][:70]}{cause[:110]}")

        top = sorted(((len(v), k) for k, v in reach.items() if k not in wide), reverse=True)[:15]
        if top:
            print("  told by the most apps:")
            for n, (contract, answer) in top:
                print(f"    {n:4d}  {contract} {answer}")
        if wide:
            print("  told by nearly every app (the provider, not the app): "
                  + ", ".join(f"{c} {a}" for c, a in sorted(wide)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
