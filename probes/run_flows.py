#!/usr/bin/env python3
"""Calibration flows: drive a few apps through what a user does, and score the gap map against it.

The end-to-end plan's calibration layer (analysis/E2E-FUNCTIONAL-HARNESS-PLAN.md, ADR-0001): probes
check contracts and the gap map predicts which apps they break, but only a real flow says whether
the prediction holds where users are. Each flow in probes/flows.json names an app, the steps a user
takes (taps at fixed positions, which hold because the APK is pinned), the evidence to collect
(screenshots, a recording of the board's output, the app's logs) and the checks that decide the
outcome, and what the gap map predicted. A run scores each prediction:

- confirmed: the flow came out as predicted;
- false alarm: predicted to fail, it worked (the row over-reports);
- miss: predicted to work, it failed (no row, or a wrong one, describes the failure).

    probes/run_flows.py --flows probes/flows.json --manifest <launcher repo> --workspace <source workspace> \\
        --westlake-source <westlake tree> --framework-report <device-report.json> --hdc <hdc> \\
        --serial <device> --app-input-root <dir holding prep-<app>> --maps <map root> [--maps ...] \\
        --work <scratch dir> --results <results.json> --launch-args "<the provider's launch flags>"

Each flow launches its app fresh, as the corpus launches do, with the app's own launch arguments
from its gap map (--maps) and the provider's (--launch-args).
"""

from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import shlex
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
_SPEC = importlib.util.spec_from_file_location("run_suite", HERE / "run_suite.py")
run_suite = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(run_suite)

STAGE = "/data/local/tmp/flows"


# ---- pure logic (unit-tested) ------------------------------------------------------------------

def audio_nonzero(path: Path) -> int:
    """Non-zero samples in a recording of the board's output. OH's playback capture pads each
    callback with zeros and records silence as exact zeros, so any sound shows as non-zero
    samples: a playing sound gave tens of thousands a second, silence none."""
    with wave.open(str(path)) as recording:
        data = recording.readframes(recording.getnframes())
    import numpy
    return int(numpy.count_nonzero(numpy.frombuffer(data, dtype="<i2")))


def region_diff(first: Path, second: Path, region: list[int]) -> float:
    """Mean absolute difference of two screenshots' grey levels over region [x0, y0, x1, y1]."""
    import numpy
    from PIL import Image
    a = numpy.asarray(Image.open(first).convert("L").crop(tuple(region)), dtype=numpy.int16)
    b = numpy.asarray(Image.open(second).convert("L").crop(tuple(region)), dtype=numpy.int16)
    return float(numpy.abs(a - b).mean())


def dark_fraction(path: Path, region: list[int], below: int = 96) -> float:
    """The share of a region's pixels darker than `below`: text or drawing on a light page."""
    import numpy
    from PIL import Image
    grey = numpy.asarray(Image.open(path).convert("L").crop(tuple(region)))
    return float((grey < below).mean())


def check(spec: dict[str, Any], evidence: dict[str, Any]) -> tuple[bool, str]:
    """One check against a flow's evidence: (passed, what was seen). Evidence that cannot be read
    fails the check, with the reason."""
    try:
        return _check(spec, evidence)
    except (OSError, EOFError, ValueError, wave.Error) as unreadable:
        if "unknown check" in str(unreadable):
            raise
        return False, f"unreadable evidence: {unreadable}"


def _check(spec: dict[str, Any], evidence: dict[str, Any]) -> tuple[bool, str]:
    files = evidence["files"]
    if "audio" in spec:
        recording = files.get(spec["audio"])
        if recording is None:
            return False, f"no recording {spec['audio']}"
        count = audio_nonzero(recording)
        return count >= spec.get("min_nonzero", 20000), f"{count} non-zero samples in {spec['audio']}"
    if "alive" in spec:
        return evidence["alive"] == spec["alive"], "process " + ("alive" if evidence["alive"] else "exited")
    if "log" in spec:
        found = spec["log"] in evidence["log"]
        return found == spec.get("present", True), f"'{spec['log']}' {'in' if found else 'not in'} the app's logs"
    if "changed" in spec:
        first, second = (files.get(name) for name in spec["changed"])
        if first is None or second is None:
            return False, f"missing screenshot of {spec['changed']}"
        diff = region_diff(first, second, spec["region"])
        return diff >= spec.get("min_diff", 6.0), f"{spec['changed'][0]} -> {spec['changed'][1]} differ by {diff:.1f}"
    if "dark" in spec:
        shot = files.get(spec["dark"])
        if shot is None:
            return False, f"no screenshot {spec['dark']}"
        share = dark_fraction(shot, spec["region"])
        return share >= spec.get("min_fraction", 0.005), f"{share:.3f} of the region dark in {spec['dark']}"
    raise ValueError(f"unknown check {spec}")


def score(predicted: str, observed: str) -> str:
    if predicted == observed:
        return "confirmed"
    return "false alarm" if predicted == "fails" else "miss"


def summary(flows: list[dict[str, Any]]) -> dict[str, Any]:
    """Counts, and the precision and recall of the 'fails' predictions over flows that ran."""
    ran = [f for f in flows if f["observed"] in {"works", "fails"}]
    predicted_fail = [f for f in ran if f["predicted"] == "fails"]
    observed_fail = [f for f in ran if f["observed"] == "fails"]
    both = [f for f in predicted_fail if f["observed"] == "fails"]
    return {"flows": len(flows), "ran": len(ran),
            "confirmed": sum(f["verdict"] == "confirmed" for f in ran),
            "false_alarms": sum(f["verdict"] == "false alarm" for f in ran),
            "misses": sum(f["verdict"] == "miss" for f in ran),
            "precision": round(len(both) / len(predicted_fail), 2) if predicted_fail else None,
            "recall": round(len(both) / len(observed_fail), 2) if observed_fail else None}


# ---- device side -------------------------------------------------------------------------------

class Board(run_suite.Device):
    def __init__(self, hdc: str, serial: str):
        super().__init__(hdc, serial)
        self.hdc, self.serial = hdc, serial

    def recv(self, remote: str, local: Path, timeout: int = 120) -> bool:
        """Copy a file off the board, and wait until the copy's checksum is the board file's: hdc
        returns before its transfer ends, with the file already at full size (a recording checked
        too early, or fetched twice, read as zeros where its header belongs)."""
        import hashlib
        local.parent.mkdir(parents=True, exist_ok=True)
        want = self.shell(f"md5sum {remote} 2>/dev/null").split()[:1]
        subprocess.run([self.hdc, "-t", self.serial, "file", "recv", remote, str(local)], stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=timeout)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if want and local.exists() and hashlib.md5(local.read_bytes()).hexdigest() == want[0]:
                return True
            time.sleep(1)
        return False

    def send(self, local: Path, remote: str, timeout: int = 300) -> None:
        subprocess.run([self.hdc, "-t", self.serial, "file", "send", str(local), remote], stdin=subprocess.DEVNULL,
                       capture_output=True, timeout=timeout)

    def tap(self, command: str) -> None:
        self.shell(f"echo '{command}' > {run_suite.TAP_CHANNEL}")

    def screenshot(self, local: Path) -> bool:
        self.shell("power-shell wakeup >/dev/null; power-shell setmode 602 >/dev/null; "
                   f"snapshot_display -f {STAGE}/shot.jpeg >/dev/null", timeout=60)
        return self.recv(f"{STAGE}/shot.jpeg", local)


def launch(flow: dict[str, Any], args: argparse.Namespace, board: Board, run: Path) -> dict[str, Any]:
    """Launch the flow's app as the corpus does; the device report's child and parent pids."""
    board.shell('P=$(pidof appspawn-x); [ -n "$P" ] && kill $P; for d in /data/local/tmp/a2hlab-app-* '
                '/data/app/el2/100/base/org.westlake.imehost/files/a2hlab-source-*; do [ -e "$d" ] && rm -rf "$d"; done; '
                f'mkdir -p {STAGE}; touch {STAGE}/launch.mark', timeout=300)
    own = []
    for root in args.maps:
        gap = root / flow["app"] / "gap-map.json"
        if gap.exists():
            own = json.loads(gap.read_text()).get("launch_args", [])
            break
    shutil.rmtree(run, ignore_errors=True)
    done = subprocess.run([sys.executable, str(args.manifest / "tools" / "probe_source_app.py"),
                           "--workspace", str(args.workspace), "--westlake-source", str(args.westlake_source),
                           "--framework-report", str(args.framework_report),
                           "--app-input", str(args.app_input_root / ("prep-" + flow["app"])), "--app", flow["app"],
                           "--hdc", args.hdc, "--serial", args.serial, "--out", str(run)]
                          + own + shlex.split(args.launch_args),
                          cwd=args.manifest, capture_output=True, text=True, timeout=1200)
    report = run / "device-report.json"
    if done.returncode != 0 or not report.exists():
        raise RuntimeError("launch failed: " + (done.stdout + done.stderr).strip()[-300:])
    return json.loads(report.read_text())


def run_flow(flow: dict[str, Any], args: argparse.Namespace, board: Board) -> dict[str, Any]:
    out = args.work / flow["id"]
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    result = {"id": flow["id"], "app": flow["app"], "intent": flow["intent"], "predicted": flow["prediction"]["outcome"],
              "prediction": flow["prediction"]}
    try:
        report = launch(flow, args, board, out / "launch")
    except Exception as failure:  # the launch is not the flow: record it and go on
        return {**result, "observed": "not run", "verdict": "not run", "detail": str(failure)[:300]}
    child, parent = report["child"], report["parent"]
    package = json.loads((args.app_input_root / ("prep-" + flow["app"]) / "app-input.json").read_text())["application"]["package"]
    files: dict[str, Path] = {}
    steps_done = []
    alive, log, hilog = False, "", ""
    try:
        for step in flow["steps"]:
            if "wait" in step:
                time.sleep(step["wait"])
            elif "tap" in step:
                board.tap(" ".join(str(v) for v in step["tap"]))
            elif "drag" in step:
                board.tap(" ".join(str(v) for v in step["drag"]))
            elif "back" in step:
                board.tap("back")
            elif "push" in step:
                local = (HERE.parent / step["push"]).resolve()
                staged = f"{STAGE}/{local.name}"
                board.send(local, staged)
                dest = f"/proc/{child}/root/data/data/{package}/{step['to']}"
                board.shell(f"U=$(stat -c %u /proc/{child}); mkdir -p $(dirname {dest}); cp {staged} {dest} && "
                            f"chown $U:$U {dest} $(dirname {dest}) && chmod 644 {dest}")
            elif "mkdir" in step:
                # A folder the app makes for itself, made first so a listing does not depend on when.
                dest = f"/proc/{child}/root/data/data/{package}/{step['mkdir']}"
                board.shell(f"U=$(stat -c %u /proc/{child}); mkdir -p {dest} && chown $U:$U {dest}")
            elif "shot" in step:
                path = out / (step["shot"] + ".jpeg")
                if board.screenshot(path):
                    files[step["shot"]] = path
            elif "record" in step:
                seconds, name = step["record"]
                board.shell(f"rm -f {STAGE}/rec.wav; {args.recorder} {STAGE}/rec.wav {seconds} 2 >/dev/null 2>&1",
                            timeout=seconds + 60)
                # The recorder writes its WAV header when it closes, and after a long wait step the
                # shell has returned before it finished: wait for it to exit, and for a header.
                recorder = Path(args.recorder).name
                deadline = time.monotonic() + seconds + 30
                while time.monotonic() < deadline and board.shell(f"pidof {recorder}").strip():
                    time.sleep(1)
                path = out / (name + ".wav")
                if board.recv(f"{STAGE}/rec.wav", path):
                    files[name] = path
            else:
                raise ValueError(f"unknown step {step}")
            steps_done.append(step.get("why") or next(iter(step)))
        alive = "ALIVE" in board.shell(f"[ -d /proc/{child} ] && echo ALIVE || echo EXITED")
        log = board.shell(f"cat {run_suite.CHILD_LOG.format(pid=child)}", timeout=120)
        hilog = board.shell(f"hilog -x -P {child}", timeout=120)
        (out / "child.stderr").write_text(log)
        (out / "child.hilog").write_text(hilog)
    finally:
        board.shell(f"kill -9 {child} {parent} 2>/dev/null; rm -f {run_suite.CHILD_LOG.format(pid=child)}")
    evidence = {"files": files, "alive": alive, "log": log + "\n" + hilog}
    checks = []
    for spec in flow["checks"]:
        passed, seen = check(spec, evidence)
        checks.append({"check": spec.get("why", ""), "passed": passed, "seen": seen})
    observed = "works" if all(c["passed"] for c in checks) else "fails"
    return {**result, "observed": observed, "verdict": score(result["predicted"], observed), "checks": checks,
            "evidence": sorted(p.name for p in files.values())}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--flows", type=Path, default=HERE / "flows.json")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--westlake-source", required=True, type=Path)
    parser.add_argument("--framework-report", required=True, type=Path)
    parser.add_argument("--hdc", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--app-input-root", required=True, type=Path, help="directory holding prep-<app> app inputs")
    parser.add_argument("--maps", action="append", type=Path, default=[], help="gap-map root, for each app's launch_args")
    parser.add_argument("--work", required=True, type=Path)
    parser.add_argument("--results", required=True, type=Path)
    parser.add_argument("--only", action="append", default=[])
    parser.add_argument("--recorder", default="/data/local/tmp/oh_record",
                        help="probes/audio-capture's oh_record on the board")
    parser.add_argument("--launch-args", default="")
    args = parser.parse_args()
    flows = json.loads(args.flows.read_text())["flows"]
    for flow in flows:
        names = [s.get("shot") or s["record"][1] for s in flow["steps"] if "shot" in s or "record" in s]
        if len(names) != len(set(names)):
            raise ValueError(f"{flow['id']}: evidence names repeat: {names}")
    if args.only:
        flows = [f for f in flows if f["id"] in args.only]
    board = Board(args.hdc, args.serial)
    args.work.mkdir(parents=True, exist_ok=True)
    results = []
    for flow in flows:
        outcome = run_flow(flow, args, board)
        results.append(outcome)
        print(f"{outcome['id']:22} predicted {outcome['predicted']:5} observed {outcome['observed']:7} "
              f"-> {outcome['verdict']}", flush=True)
    document = {"date": datetime.date.today().isoformat(), "westlake_commit": run_suite.westlake_commit(args.westlake_source),
                "summary": summary(results), "flows": results}
    args.results.write_text(json.dumps(document, indent=1, default=str) + "\n")
    print(json.dumps(document["summary"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
