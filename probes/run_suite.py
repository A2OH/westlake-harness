#!/usr/bin/env python3
"""Run every white-box probe against one Westlake build and record the verdicts.

One command per build, so a regression shows up in the probes before it shows up in an app:

    probes/run_suite.py --manifest <launcher repo> --workspace <source workspace> \\
        --westlake-source <westlake tree> --framework-report <device-report.json> \\
        --hdc <hdc> --serial <device> --results <probe-results.json> --work <scratch dir>

For each probe in probes/suite.json it checks the APK against its pin in the launcher's
app-inputs.lock.json, stages it (prepare_app.py), launches it on the build under test
(probe_source_app.py), watches the probe's log for its pass and fail markers, performs its
interaction (a tap at the coordinates the probe logs), then stops it. Results are merged into the
probe-results file that `gap-map --probe-results` reads, keyed by the exact Westlake commit; a
build from a dirty tree is recorded as "dirty-<commit>", which never matches a clean commit.

--launch-args passes the provider's own launch arguments (the WebView input, the bionic shim build,
runtime-library overrides), so a probe runs on the provider the corpus runs on. Before each probe
the board is cleared of leftover launcher processes and app stages, as the corpus launches do.

A contract probe ("contracts" in suite.json) exercises several contracts in one launch and prints
one line per contract: <prefix><name> <ok|absent|fail token> <detail>. Each line becomes a result of
its own, "<probe>/<name>", and its name is the gap-map row it measures (contract probes name rows by
id), so the result lands on that row in every map that has it. The probe's own result passes when
it finished and no contract failed.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
CHILD_LOG = "/data/service/el1/public/appspawnx/adapter_child_{pid}.stderr"
TAP_CHANNEL = "/data/local/tmp/noice_tap"


# ---- pure logic (unit-tested) ------------------------------------------------------------------

def evaluate(lines: list[str], probe: dict[str, Any], hilog: list[str] | None = None) -> str:
    """'fail' if any fail marker appeared, in the probe's log or (fail_hilog) in its process's hilog,
    'pass' once every pass marker has, else 'pending'. A platform fault the app survives this time
    shows only in the hilog: gl-contracts' consumer-stall passed in-app on the old GL bindings
    while OH's buffer queue logged the failed buffer request that crashed Telegram."""
    text = "\n".join(lines)
    if any(marker in text for marker in probe.get("fail", [])):
        return "fail"
    if any(marker in line for marker in probe.get("fail_hilog", []) for line in hilog or []):
        return "fail"
    if all(marker in text for marker in probe["pass"]):
        return "pass"
    return "pending"


def tap_target(lines: list[str], probe: dict[str, Any]) -> tuple[int, int] | None:
    tap = probe.get("tap")
    if not tap:
        return None
    for line in lines:
        match = re.search(tap["pattern"], line)
        if match:
            return int(match.group(1)), int(match.group(2))
    return None


def contract_results(lines: list[str], probe: dict[str, Any]) -> list[dict[str, Any]]:
    """One result per contract line of a contract probe, the last line for a name winning."""
    spec = probe.get("contracts")
    if not spec:
        return []
    tokens = (("pass", spec.get("ok", "PASS")), ("absent", spec.get("absent", "ABSENT")),
              ("fail", spec.get("fail", "FAIL")))
    found: dict[str, dict[str, Any]] = {}
    for line in lines:
        at = line.find(spec["prefix"])
        if at < 0:
            continue
        name, _, rest = line[at + len(spec["prefix"]):].strip().partition(" ")
        outcome = next((kind for kind, token in tokens if rest.startswith(token)), None)
        if not name or outcome is None:
            continue
        found[name] = {"probe": probe["name"] + "/" + name, "row": name, "outcome": outcome,
                       "passed": outcome != "fail", "verdict": rest.strip()[:300]}
    return list(found.values())


def markers(probe: dict[str, Any]) -> list[str]:
    found = list(probe["pass"]) + list(probe.get("fail", []))
    if probe.get("tap"):
        found.append(probe["tap"]["after"])
    if probe.get("contracts"):
        found.append(probe["contracts"]["prefix"])
    return found


def merge_results(document: dict[str, Any], new: list[dict[str, Any]]) -> dict[str, Any]:
    """Replace any earlier result for the same probe and commit; keep everything else in order."""
    keys = {(r["probe"], r["westlake_commit"]) for r in new}
    kept = [r for r in document.get("results", []) if (r["probe"], r["westlake_commit"]) not in keys]
    return {**document, "results": kept + new}


def dump(document: dict[str, Any]) -> str:
    """The results file's own layout: header keys indented, one result per line."""
    head = [f"  {json.dumps(k)}: {json.dumps(v)}," for k, v in document.items() if k != "results"]
    rows = ",\n".join("    " + json.dumps(r) for r in document.get("results", []))
    return "\n".join(["{", *head, '  "results": [', rows, "  ]", "}"]) + "\n"


def westlake_commit(tree: Path) -> str:
    head = subprocess.run(["git", "-C", str(tree), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(tree), "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True).stdout.strip()
    return ("dirty-" + head) if dirty else head


# ---- device side -------------------------------------------------------------------------------

class Device:
    def __init__(self, hdc: str, serial: str):
        self.transport = [hdc, "-t", serial]

    def shell(self, command: str, timeout: int = 60) -> str:
        done = subprocess.run(self.transport + ["shell", command], stdin=subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=timeout)
        return done.stdout.replace("\r", "")

    def grep(self, path: str, patterns: list[str]) -> list[str]:
        # One -F -e per marker: this board's toybox grep does not honour \\| alternation reliably.
        args = " ".join("-e " + json.dumps(p) for p in patterns)
        return [line for line in self.shell(f"grep -h -F {args} {path} 2>/dev/null").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_probe(probe: dict[str, Any], args: argparse.Namespace, device: Device, lock: dict[str, Any]) -> dict[str, Any]:
    result = {"probe": probe["name"], "passed": False}
    apk = HERE / probe["apk"]
    pin = lock["applications"].get(probe["lock_key"], {})
    if not apk.exists():
        return {**result, "verdict": "not run: APK not built (run its build.sh)"}
    if sha256(apk) != pin.get("sha256"):
        return {**result, "verdict": "not run: APK differs from its pin in app-inputs.lock.json"}
    tools = args.manifest / "tools"
    # As the corpus launches do: no leftover launcher, and no stale app stages filling /data.
    device.shell('P=$(pidof appspawn-x); [ -n "$P" ] && kill $P; for d in /data/local/tmp/a2hlab-app-* '
                 '/data/app/el2/100/base/org.westlake.imehost/files/a2hlab-source-*; do [ -e "$d" ] && rm -rf "$d"; done',
                 timeout=300)
    prep = args.work / ("prep-" + probe["name"])
    run = args.work / ("run-" + probe["name"])
    for directory in (prep, run):
        shutil.rmtree(directory, ignore_errors=True)
    subprocess.run([sys.executable, str(tools / "prepare_app.py"), "--apk", str(apk), "--app", probe["lock_key"],
                    "--out", str(prep)], cwd=args.manifest, check=True, capture_output=True, timeout=600)
    launch = subprocess.run([sys.executable, str(tools / "probe_source_app.py"), "--workspace", str(args.workspace),
                             "--westlake-source", str(args.westlake_source), "--framework-report", str(args.framework_report),
                             "--app-input", str(prep), "--app", probe["lock_key"], "--hdc", args.hdc,
                             "--serial", args.serial, "--out", str(run)] + shlex.split(args.launch_args),
                            cwd=args.manifest, capture_output=True, text=True, timeout=1200)
    report_path = run / "device-report.json"
    if launch.returncode != 0 or not report_path.exists():
        return {**result, "verdict": "not run: launch failed: " + (launch.stdout + launch.stderr).strip()[-200:]}
    report = json.loads(report_path.read_text())
    child, parent = report.get("child"), report.get("parent")
    log = CHILD_LOG.format(pid=child)
    status, lines, tapped = "pending", [], False
    deadline = time.monotonic() + args.timeout
    try:
        while time.monotonic() < deadline:
            time.sleep(3)
            lines = device.grep(log, markers(probe))
            target = tap_target(lines, probe)
            if target and not tapped:
                device.shell(f"echo '{target[0]} {target[1]}' > {TAP_CHANNEL}")
                tapped = True
                continue
            status = evaluate(lines, probe)
            if status == "pass" and probe.get("fail_hilog"):
                hilog = device.shell(f"hilog -x -P {child}", timeout=120).splitlines()
                hits = [line for line in hilog if any(m in line for m in probe["fail_hilog"])]
                status = evaluate(lines, probe, hits)
                lines += ["(hilog) " + line.strip() for line in hits[:2]]
            if status != "pending":
                break
            if "EXITED" in device.shell(f"[ -d /proc/{child} ] && echo ALIVE || echo EXITED"):
                status = "fail"
                lines.append("(probe process exited)")
                break
    finally:
        (run / "child.stderr").write_text(device.shell(f"cat {log}", timeout=120))
        device.shell(f"kill -9 {child} {parent} 2>/dev/null")
    contracts = contract_results(lines, probe)
    if contracts:
        failed = [c["row"] for c in contracts if not c["passed"]]
        absent = sum(1 for c in contracts if c["outcome"] == "absent")
        summary = (f"{len(contracts) - len(failed) - absent} pass, {absent} truthfully absent, {len(failed)} fail"
                   + (": " + ", ".join(failed) if failed else ""))
        return {**result, "passed": status == "pass" and not failed, "contracts": contracts,
                "verdict": ("timeout: " if status == "pending" else "") + summary}
    verdict_lines = [line.strip() for line in lines if not (probe.get("tap") and probe["tap"]["after"] in line)]
    return {**result, "passed": status == "pass",
            "verdict": ("timeout: " if status == "pending" else "") + " | ".join(verdict_lines)[:400]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--suite", type=Path, default=HERE / "suite.json")
    parser.add_argument("--manifest", required=True, type=Path, help="launcher repo: tools/, app-inputs.lock.json")
    parser.add_argument("--workspace", required=True, type=Path, help="source workspace passed to probe_source_app.py")
    parser.add_argument("--westlake-source", required=True, type=Path)
    parser.add_argument("--framework-report", required=True, type=Path, help="device-report.json of the build under test")
    parser.add_argument("--hdc", required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--work", required=True, type=Path, help="scratch directory for staged inputs and launch reports")
    parser.add_argument("--results", required=True, type=Path, help="probe-results.json to merge into (created if absent)")
    parser.add_argument("--only", action="append", default=[], help="run only these probes; repeat")
    parser.add_argument("--timeout", type=int, default=120, help="seconds to wait for a probe's verdict")
    parser.add_argument("--launch-args", default="",
                        help="the provider's own launch arguments, passed to probe_source_app.py as given")
    args = parser.parse_args()

    suite = json.loads(args.suite.read_text())["probes"]
    if args.only:
        suite = [p for p in suite if p["name"] in args.only]
    lock = json.loads((args.manifest / "app-inputs.lock.json").read_text())
    commit = westlake_commit(args.westlake_source)
    args.work.mkdir(parents=True, exist_ok=True)
    device = Device(args.hdc, args.serial)
    today = datetime.date.today().isoformat()
    new = []
    for probe in suite:
        outcome = run_probe(probe, args, device, lock)
        new.append({"probe": outcome["probe"], "westlake_commit": commit, "date": today,
                    "verdict": outcome["verdict"], "passed": outcome["passed"]})
        new += [{"probe": c["probe"], "row": c["row"], "outcome": c["outcome"], "westlake_commit": commit,
                 "date": today, "verdict": c["verdict"], "passed": c["passed"]} for c in outcome.get("contracts", [])]
        print(f"{'PASS' if outcome['passed'] else 'FAIL'} {probe['name']}: {outcome['verdict'][:160]}", flush=True)
    document = json.loads(args.results.read_text()) if args.results.exists() else {"results": []}
    args.results.write_text(dump(merge_results(document, new)))
    failed = [r["probe"] for r in new if not r["passed"]]
    print(f"{len(new) - len(failed)}/{len(new)} passed on westlake {commit[:16]}" + (f"; failed: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
