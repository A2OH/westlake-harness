#!/usr/bin/env python3
"""checks.py -- scripted functional checks: a short script per app (accept its consent notice, reach its
first screen, see one piece of content load, make one interaction), run on Westlake (the board) or on an
Android phone through explore.py's device layer, each step passed or failed with a screenshot.

    checks.py oh      --hdc <hdc> --serial <board> --child <pid> --app <package> --out <dir> [--spec <json>]
    checks.py android --adb <adb> --serial <phone> --package <package> --out <dir> [--spec <json>]

The app must already be running (Westlake: launched by launch.sh; Android: this starts it). A spec maps
each package to its steps (default: checks.json beside this file):

    {"com.whatsapp": [{"do": "consent"}, {"do": "wait", "text": "phone number", "seconds": 20}]}

    consent  when a consent notice is on screen, tap the control that accepts it (passes when none is)
    tap      tap the first clickable view, top to bottom, whose text or id matches "text" / "id", or
             else the first such view at all (a label whose clickable parent carries no text)
             (case-insensitive regular expressions)
    wait     wait up to "seconds" (default 20) for a view whose text or id matches
    scroll   scroll the screen once
    back     press Back

Every step records pass or fail, the seconds it took, the view it matched and a screenshot
(<out>/check-NN.png|jpeg); the run stops at the first failed step, so an account or login gate is a fine
last step (a "wait" for its text). Writes <out>/checks.json. Views that pay, delete, sign out or refuse
a consent notice are never tapped (explore.py's DENY).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explore import CONSENT, DENY, Board, Phone, View  # noqa: E402

#: A control that accepts a consent notice (its text), checked after DENY, so "do not agree" never matches.
ACCEPT = re.compile(r"\b(agree|accept|allow|continue|got it|ok|okay|i understand|start)\b|"
                    r"同意|接受|允許|允许|繼續|继续|確定|确定|好的|知道了", re.I)


def matches(view: View, text: str | None, vid: str | None) -> bool:
    if text and not re.search(text, view.text or "", re.I):
        return False
    if vid and not re.search(vid, view.vid or "", re.I):
        return False
    return bool(text or vid)


def with_nodes(device, views: list[View], text: str | None, vid: str | None) -> list[View]:
    """The views, and the accessibility nodes too when no view matches: a Compose screen (Uber's login) shows its
    text only as nodes, and its root view is clickable, so the view dump alone never names its Continue button."""
    if find(views, text, vid, clickable=False) is not None or not hasattr(device, "node_roots"):
        return views
    return views + [node for root in device.node_roots() for node in root]


def find(views: list[View], text: str | None, vid: str | None, clickable: bool) -> View | None:
    for view in sorted(views, key=lambda v: (v.y, v.x)):
        if clickable and not view.clickable:
            continue
        if matches(view, text, vid) and not DENY.search(view.text or ""):
            return view
    return None


def consent_control(views: list[View]) -> View | None:
    """The control that accepts a consent notice on this screen, or None when there is no notice."""
    if not any(CONSENT.search(v.text or "") for v in views):
        return None
    # A button's short label before a sentence: Viber's "By tapping "Start now" you agree to our Terms" is
    # clickable (its links) and says "agree", and was tapped instead of the button.
    for view in sorted(views, key=lambda v: (len(v.text or "") > 40, v.y, v.x)):
        text = view.text or ""
        if view.clickable and ACCEPT.search(text) and not DENY.search(text):
            return view
    # A short accepting label inside a clickable parent that carries no text (Instagram's terms screen: its
    # "Continue" node is not clickable, its button is): a finger on the label reaches the button.
    for view in sorted(views, key=lambda v: (v.y, v.x)):
        text = view.text or ""
        if 0 < len(text) <= 40 and ACCEPT.search(text) and not DENY.search(text):
            return view
    return None


def run(device, steps: list[dict], out: Path, settle: float = 1.5) -> dict:
    results = []
    for index, step in enumerate(steps):
        action, started, ok, matched = step.get("do"), time.time(), False, None
        if action == "consent":
            views = device.views()
            control = consent_control(views)
            # Instagram's terms screen names its notice and its Continue button only as accessibility nodes.
            if control is None and hasattr(device, "node_roots"):
                control = consent_control(views + [node for root in device.node_roots() for node in root])
            if control is not None:
                device.tap(*control.centre())
                matched = control.text
            ok = True
        elif action == "tap":
            views = with_nodes(device, device.views(), step.get("text"), step.get("id"))
            view = find(views, step.get("text"), step.get("id"), clickable=True)
            # A label inside a clickable parent (YouTube's bottom bar: the tab is clickable, its
            # "Shorts" text is not): a finger on the label reaches the tab, so tap the label.
            if view is None:
                view = find(views, step.get("text"), step.get("id"), clickable=False)
            if view is not None:
                device.tap(*view.centre())
                ok, matched = True, view.text or view.vid
        elif action == "wait":
            deadline = started + float(step.get("seconds", 20))
            while time.time() < deadline and device.alive():
                view = find(with_nodes(device, device.views(), step.get("text"), step.get("id")),
                            step.get("text"), step.get("id"), clickable=False)
                if view is not None:
                    ok, matched = True, view.text or view.vid
                    break
                time.sleep(1)
        elif action == "scroll":
            device.scroll()
            ok = True
        elif action == "back":
            device.back()
            ok = True
        else:
            raise ValueError("unknown step: " + str(action))
        time.sleep(settle)
        shot = out / ("check-%02d" % index)
        try:
            device.screenshot(shot)
        except Exception:  # a screenshot is evidence, not a step
            pass
        ok = ok and device.alive()
        results.append({"do": action, "ok": ok, "seconds": round(time.time() - started, 1), "matched": matched,
                        **{k: v for k, v in step.items() if k != "do"}})
        if not ok:
            break
    return {"steps": results, "passed": sum(r["ok"] for r in results), "of": len(steps)}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("platform", choices=["oh", "android"])
    p.add_argument("--serial", required=True)
    p.add_argument("--hdc")
    p.add_argument("--child", type=int)
    p.add_argument("--adb")
    p.add_argument("--package")
    p.add_argument("--app", help="the package whose steps to run (default --package)")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--spec", type=Path, default=Path(__file__).resolve().parent / "checks.json")
    p.add_argument("--settle", type=float, default=1.5)
    a = p.parse_args()
    app = a.app or a.package
    steps = json.loads(a.spec.read_text()).get(app)
    if not steps:
        print("no checks for " + str(app), file=sys.stderr)
        return 2
    a.out.mkdir(parents=True, exist_ok=True)
    if a.platform == "oh":
        device = Board(a.hdc, a.serial, a.child)
    else:
        device = Phone(a.adb, a.serial, a.package)
        device.start()
    result = {"app": app, "platform": a.platform, **run(device, steps, a.out, a.settle)}
    (a.out / "checks.json").write_text(json.dumps(result, indent=1))
    print("%s: %d of %d steps" % (app, result["passed"], result["of"]))
    return 0 if result["passed"] == result["of"] else 1


if __name__ == "__main__":
    sys.exit(main())
