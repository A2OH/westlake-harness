#!/usr/bin/env python3
"""tells.py <tag> [<tag>...]  -- what the runtime told about each app, and how each app ended.

Step T0 of analysis/RUNTIME-TELLS.md: no runtime change. It reads the markers the runtime already
writes as tells, together with any `[WESTLAKE-TELL]` lines, from each app of a round in
$WL_SC/inputs/logs/<tag>/:
  hk-<package>.stderr          the app's stderr (tells, Java ends, loader reasons)
  hk-<package>.hilog           the system log (fatal signals, the crash dumper timing out, PM stubs)
  hk-<package>.cppcrash        a crash dump taken after the launch, when there is one
  hk-<package>.explore/        the Level 2 explorer's explore.json (whether and when the app ended)
  hk-<package>.maps            the app's memory map, when the round took one (whose a signal handler is)

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
                   handler took a signal first, the detail says so, and names the library the handler is
                   in when the memory map shows it: a protector's deliberate trap, or, as for Honor of
                   Kings on 2026-11-08, a crash reporter (CrashSight) that took the signal and left no dump

A crash, dump timeout or silent end inside the app's own protection (anti-tamper, code virtualization,
app hardening) also names the protector: a frame of the fault thread is in its library, or, for an app
that never showed a screen, its library was the last one loaded before the fatal signal. Such ends are
observed, not worked around, and are counted apart from the ends Westlake can fix.

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


def surfaceview_order(placed):
    """Where a SurfaceView's own OH window sits, from the adapter's line (westlake #117 adds `placed`).
    Android stacks a SurfaceView below its window unless the app asks for it on top."""
    contract = "window:surfaceview-order"
    if placed is None:
        return (contract, "on top", "unknown", "above its activity's window (a build before z-levels)")
    if placed == "on top":
        return (contract, "on top", "android", "the app put it on top (setZOrderOnTop), or the runtime was told to")
    if placed == "hidden":
        return (contract, "hidden", "stand-in", "never shown (WESTLAKE_SURFACEVIEW_ORDER=hidden)")
    m = re.match(r"below its window \(z-level (-?\d+), rc=(-?\d+)\)", placed)
    if m and m[2] == "0":
        return (contract, "below", "android", f"z-level {m[1]}")
    return (contract, "failed", "unknown", placed)


# Contracts the runtime answers and goes on from whatever the answer: never why an app ended.
NEVER_FATAL = {"window:keep-screen-on", "window:surfaceview-order"}

# Markers the runtime writes today, read as tells: (pattern, contract, answer, fidelity, detail).
LEGACY = [
    (re.compile(r"\[WESTLAKE-LOADER\] (\S+) by name failed \((.*)\); opening the path"),
     lambda m: ("load:" + m[1], "failed", "stand-in", m[2])),
    (re.compile(r"\[WESTLAKE-LOADER\] (\S+) by name gave another library"),
     lambda m: ("load:" + m[1], "another", "unknown", "older message: the open may have failed")),
    # dlsym by a handle to the runtime's libandroid.so, answered with the bionic shim's definition. The
    # surface-control calls create no surface (stand-in); the rest are judged by what the shim does.
    (re.compile(r"\[WESTLAKE-LOADER\] libandroid\.so by handle: (\w+) from the bionic shim"),
     lambda m: ("dlsym:libandroid.so#" + m[1], "shim", "stand-in" if m[1].startswith("ASurface") else "unknown",
                "looked up by handle; the runtime's libandroid.so lacks it")),
    # The Mali kernel driver ended the process's GPU context (kbase's job-dispatch termination), and the
    # driver's own thread aborts next. Every Flutter 3.27/3.29 app drawing with Impeller's Vulkan backend
    # ended this way in the 1000-app round, before it created a window surface (Sushiro, EPD Green).
    (re.compile(r"\((mali-[\w-]+)\) BASE: .*\b(base_jd_event_\w+)"),
     lambda m: ("gpu:mali-context", "failed", "unknown", f"the GPU driver ended the context ({m[2]}, thread {m[1]})")),
    # FLAG_KEEP_SCREEN_ON, set on the owning OH session (OhWindowPolicy). Until westlake #115 its native was
    # loaded from a library the launcher never named: every app that asked for the flag (233 of 960 in the
    # 1000-app round) logged the failure, and the screen timed out as usual.
    (re.compile(r"\[OH_WINDOW_POLICY\] update failed (.*)"),
     lambda m: ("window:keep-screen-on", "not applied", "stand-in", m[1].strip())),
    (re.compile(r"\[OH_WINDOW_POLICY\] session=\d+ keepScreenOn=(true|false) rc=(-?\d+)"),
     lambda m: ("window:keep-screen-on", "applied" if m[2] == "0" else "failed",
                "android" if m[2] == "0" else "unknown", f"keepScreenOn={m[1]} rc={m[2]}")),
    # A SurfaceView's own OH window: before westlake #117 always above its activity's, and 38 apps of the
    # 1000-app round that stopped with one showed a pure black screen over their views.
    (re.compile(r"\[OH_WSA\] SurfaceView '[^']*' \S+ at \S+ -> own sessionId=\d+(?:, (.*))?$"),
     lambda m: surfaceview_order(m[1])),
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
# Libraries of an app's own protection. PairIP's crashes mostly have no backtrace (28 of 58 in the
# 1000-app round), so for an app that never drew, the last library loaded before the fault counts.
PROTECTORS = [(re.compile(r"libpairipcore\.so"), "PairIP"), (re.compile(r"libbaiduprotect"), "Baidu app hardening"),
              (re.compile(r"libmetasec_(?:ml|ov)"), "ByteDance MetaSec"),
              (re.compile(r"libsg(?:main|securitybody)"), "Alibaba SecurityGuard"),
              (re.compile(r"libdexprotector"), "DexProtector"), (re.compile(r"libijm"), "ijiami"),
              (re.compile(r"libDexHelper|libsecexe|libSecShell"), "Bangcle"), (re.compile(r"libFairGuard"), "FairGuard"),
              (re.compile(r"libakamaibap"), "Akamai Bot Manager"), (re.compile(r"libnesec"), "NetEase Yidun"),
              (re.compile(r"libcovault"), "AppSealing")]
# The shim's signal witness (WESTLAKE_SEGV_WITNESS for SIGSEGV; SIGILL, SIGTRAP and SIGBUS always): the
# library the faulting pc is in, which a silent end has no crash dump to name.
WITNESS = re.compile(r"\[WESTLAKE-SIGNAL-WITNESS\] .* at (\S+)\+0x[0-9a-f]+ ")
NATIVE_LOAD = re.compile(r"\[SOURCE-NATIVE-LOAD\] path=(\S+)")
DUMP_FRAME = re.compile(r"^#\d\d pc ")
FATAL = re.compile(r"^Fatal signal |^\*\*\* \*\*\* \*\*\*|abort message: |^terminating with uncaught exception")
TELL = re.compile(r"\[WESTLAKE-TELL\] (\{.*\})")
CHILD = re.compile(r"adapter_child_(\d+)\.stderr")
MAPPING = re.compile(r"^([0-9a-f]+)-([0-9a-f]+)\s+\S+\s+[0-9a-f]+\s+\S+\s+\S+\s+(\S.*)$")
HANDLER_INSTALL = re.compile(r"\[WESTLAKE-SIGNAL-INSTALL\] android signal=(\d+) .*handler=0x([0-9a-f]+)")
# Westlake's Bionic shim installs its own forwarder for a handler an Android library installs through it.
SHIM = "libwebview_bionic_shim.so"
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


def library_at(maps: list[str], address: int) -> str:
    """The base name of the file mapped at `address` in a memory map, or ""."""
    for line in maps:
        m = MAPPING.match(line)
        if m and int(m[1], 16) <= address < int(m[2], 16):
            return m[3].rsplit("/", 1)[-1]
    return ""


def handler_library(maps: list[str], stderr: list[str], signo: str, address: int) -> str:
    """The library of the handler that took signal `signo`: the one at `address`, or, when that is the
    shim's forwarder, the handler the app last installed for the signal through the shim."""
    library = library_at(maps, address)
    if library == SHIM:
        installs = [m[2] for m in (HANDLER_INSTALL.search(line) for line in stderr) if m and m[1] == signo]
        library = library_at(maps, int(installs[-1], 16)) if installs else ""
    return library


def end_of(stderr: list[str], hilog: list[str], crash: list[str], explore: dict, pid: str,
           maps: list[str] = ()) -> tuple[str, str, int]:
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
            handled = line
    if handled is not None:
        signo = handled.rsplit("signal:", 1)[1].split()[0]
        address = re.search(r"sa_sigaction=([0-9a-f]+)", handled)
        owner = handler_library(maps, stderr, signo, int(address[1], 16)) if address else ""
        return "silent", f"after the app's own handler took signal {signo}" + (f" (in {owner})" if owner else ""), -1
    return "silent", "", -1


def protector_of(stderr: list[str], crash: list[str], explore: dict) -> str:
    """The app's own protection an end happened in, or "": a fault-thread frame in its library, the
    library the signal witness saw the fault in, or, for an app that never showed a screen, its library
    the last one loaded before the fatal signal."""
    at = next((i for i, line in enumerate(crash) if line.startswith("Fault thread info")), None)
    if at is not None:
        for line in crash[at + 2:]:
            if not DUMP_FRAME.match(line):
                break
            for pattern, name in PROTECTORS:
                if pattern.search(line):
                    return name
    # Moneyback and ParknShop: SIGILL in the constructor musl's do_init_fini called in libakamaibap.so.
    for m in (WITNESS.search(line) for line in stderr):
        if m:
            found = next((name for pattern, name in PROTECTORS if pattern.search(m[1].rsplit("/", 1)[-1])), "")
            if found:
                return found
    if (explore or {}).get("screens"):
        return ""
    # Other threads load libraries while the dump is taken (Youku loaded SecurityGuard 190 lines after its
    # APM library's abort), so only loads before the fatal point count, and without one there is no rule.
    fatal = next((i for i, line in enumerate(stderr) if FATAL.search(line)), None)
    if fatal is None:
        # A silent end: the log stops a few lines after the protector's library loaded (AppSealing's
        # libcovault-appsec.so installs a SIGILL and a SIGSYS handler, and nothing follows).
        tail = [m[1] for m in (NATIVE_LOAD.search(line) for line in stderr[-8:]) if m]
        last = tail[-1].rsplit("/", 1)[-1] if tail else ""
        return next((name for pattern, name in PROTECTORS if last and pattern.search(last)), "")
    loads = [m[1] for m in (NATIVE_LOAD.search(line) for line in stderr[:fatal]) if m]
    last = loads[-1].rsplit("/", 1)[-1] if loads else ""
    return next((name for pattern, name in PROTECTORS if last and pattern.search(last)), "")


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
    maps = read(logs / f"{app}.maps")
    explore = load_json(logs / f"{app}.explore" / "explore.json")
    pid = next((m[1] for m in (CHILD.search(l) for l in stderr[:5]) if m), "")
    tells = tells_of(stderr, hilog)
    record = {"explored": explore is not None, "tells": tells}
    if explore is not None:
        record["explore"] = {k: explore.get(k) for k in ("seconds", "screens", "died_at", "died_after")}
    ended = explore is not None and explore.get("died_at") is not None
    record["ended"] = ended
    if ended:
        kind, detail, at = end_of(stderr, hilog, crash, explore, pid, maps)
        record["end"] = {"kind": kind, "detail": detail, "line": at}
        protector = protector_of(stderr, crash, explore) if kind in ("crash", "dump-timeout", "silent") else ""
        if protector:
            record["end"]["protector"] = protector
    return record


def cause_candidate(record: dict, wide: set) -> str:
    """The last failure or stand-in the app's stderr told before it ended, among tells not nearly every app gives."""
    at = record["end"]["line"]
    before = [t for t in record["tells"] if t["line"] >= 0 and (at < 0 or t["line"] <= at)
              and (t["contract"], t["answer"]) not in wide and t["contract"] not in NEVER_FATAL
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
        protected = Counter(result[a]["end"]["protector"] for a in ended if result[a]["end"].get("protector"))
        if protected:
            print(f"  {sum(protected.values()):4d}  of them inside the app's own protection (observed, not worked around): "
                  + ", ".join(f"{name} {n}" for name, n in protected.most_common()))
        for a in ended:
            r = result[a]
            cause = f"  <- {r['cause_candidate']}" if "cause_candidate" in r else ""
            shield = f" [{r['end']['protector']}]" if r["end"].get("protector") else ""
            print(f"    {a[3:]:44s} {r['end']['kind']:13s} {r['end']['detail'][:70]}{shield}{cause[:110]}")

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
