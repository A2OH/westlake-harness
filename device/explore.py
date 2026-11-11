#!/usr/bin/env python3
"""explore.py -- Level 2: use an app for a few minutes the way a curious user would, on Westlake (the
OpenHarmony board) or on an Android phone, with the same deterministic explorer on both, so the two
runs can be compared app by app.

    explore.py oh      --hdc <hdc> --serial <board> --child <pid> --out <dir> [--seconds 180]
    explore.py android --adb <adb> --serial <phone> --package <pkg> --out <dir> [--seconds 180]

The app must already be running (on Westlake: launched by launch.sh; on Android: this starts it).
Each step reads the screen's views (Westlake: the tap channel's view dump in the app's own log, and
when that shows nothing to tap, the framework's accessibility node dump, which sees Compose; Android:
uiautomator), then:

  1. taps a clickable view on this screen it has not tapped yet (text and ids first, top to bottom),
  2. else scrolls this screen (twice at most),
  3. else presses Back.

Views whose text looks like paying, deleting, signing out or uninstalling are never tapped, nor
controls that refuse a consent notice or exit the app, and text fields are not typed into. A screen is the set of (class, id) of its visible views, so a list
that scrolls stays one screen. The run stops at --seconds or when the process is gone.

Writes <out>/explore.json: each step (action, screen, views seen), screens reached, taps, whether
the process died and when, and screenshots every --shot-every steps (<out>/step-NNN.png|jpeg).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

DENY = re.compile(r"\b(buy|pay|purchase|subscribe|subscription|checkout|order now|place order|delete|remove account|"
                  r"sign ?out|log ?out|uninstall|unsubscribe|report|block|disagree|do not agree|don't agree|decline|exit|quit)\b|"
                  r"購買|购买|付款|支付|訂閱|订阅|刪除|删除|登出|退出登录|不同意|拒絕|拒绝|退出", re.I)
# Refusing a consent notice or pressing an app's own exit closes it on purpose, as on a phone: matched by
# view id too, since such buttons are often icons or text the dump leaves out.
DENY_ID = re.compile(r"not_?agree|disagree|decline|reject|exit|quit", re.I)
# On a consent notice (licence, privacy, terms) its cancel or close control refuses it too: Xiaomi Home's
# refuse button is an icon with the id appwidget_cancel and no text, and the app ended itself when it was
# tapped. Elsewhere cancel stays tappable: on an "Update / Cancel" prompt it is the way past.
CONSENT = re.compile(r"\b(agree|agreed|agreement|consent|privacy|licen[cs]e|terms)\b|协议|協議|隐私|隱私|条款|條款|同意",
                     re.I)
CONSENT_DENY = re.compile(r"\b(cancel|close)\b|取消|關閉|关闭", re.I)
CONSENT_DENY_ID = re.compile(r"cancel|close|negative", re.I)
TEXT_INPUT = re.compile(r"EditText|TextInput|SearchView|AutoComplete", re.I)


class View:
    __slots__ = ("cls", "vid", "x", "y", "w", "h", "clickable", "text")

    def __init__(self, cls, vid, x, y, w, h, clickable, text):
        self.cls, self.vid, self.x, self.y, self.w, self.h = cls, vid, x, y, w, h
        self.clickable, self.text = clickable, text

    def key(self) -> str:
        return f"{self.cls}|{self.vid}|{self.text[:40]}|{self.x // 40},{self.y // 40}"

    def centre(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2


class Board:
    """Westlake on the OpenHarmony board: the app's tap channel and its own log."""
    CHANNEL = "/data/local/tmp/noice_tap"
    # The view's text, when it has one, comes right after itm=; extras (WEB url="..." and so on) follow it.
    VT = re.compile(r'VT\s+(\S+) id=(\S+) rect=\[(-?\d+),(-?\d+) (\d+)x(\d+)\] c=(\d) en=(\d) .*?itm=\d+ (?:"(.*?)"(?= |$))?')

    # A tap this far out on both axes asks the framework for its accessibility node dump
    # (adapter.window.AccessibilityTreeDump): the nodes a screen drawn with Compose shows uiautomator on
    # Android, which the view dump does not show. Dropbox's welcome screen was 9 views, none clickable.
    A11Y_REQUEST = "1000000 1000000"
    A11Y_END = "VT ==== a11y end ===="
    DUMP_END = "VT ==== end ===="

    def __init__(self, hdc: str, serial: str, child: int):
        self.cmd = [hdc, "-t", serial]
        self.child = child
        self.log = f"/data/service/el1/public/appspawnx/adapter_child_{child}.stderr"
        self.width, self.height = 1200, 1920
        self.a11y = True   # until a request goes unanswered: a framework without the node dump
        self.a11y_retry = 0.0  # an unanswered request is retried after this time (a splash may not answer)

    def shell(self, command: str, timeout: int = 30) -> str:
        try:
            return subprocess.run(self.cmd + ["shell", command], capture_output=True, text=True,
                                  timeout=timeout, errors="replace").stdout.replace("\r", "")
        except subprocess.TimeoutExpired:
            return ""

    def send(self, command: str) -> None:
        self.shell(f"echo '{command}' > {self.CHANNEL}")

    def alive(self) -> bool:
        return self.shell(f"[ -d /proc/{self.child} ] && echo A").strip() == "A"

    def views(self) -> list[View]:
        size = self.shell(f"wc -c < {self.log}").strip()
        start = int(size) + 1 if size.isdigit() else 1
        self.send("v")
        time.sleep(1.5)
        text = self.shell(f"tail -c +{start} {self.log} | grep 'VT '", timeout=60)
        # A dump still being written is waited for, up to 3 s more: Bumble's (a Compose screen over a
        # playing video) came after the read in every step, and every step saw no view.
        for _ in range(6):
            if self.DUMP_END in text:
                break
            time.sleep(0.5)
            text = self.shell(f"tail -c +{start} {self.log} | grep 'VT '", timeout=60)
        # One block per window (root). They come in creation order, not stacking order: Excel's
        # privacy dialog was root[0] under an empty full-screen overlay view, and taking the last
        # root left the explorer blind, tapping a grid onto "Disagree and Exit". The top window is
        # taken as the last one with something to tap.
        blocks = [b for b in text.split("VT ==== root[")[1:]] or [text]
        roots = [self.parse(b) for b in blocks]
        tappable = [r for r in roots if any(v.clickable for v in r)]
        if not tappable and (self.a11y or time.time() >= self.a11y_retry):
            # The node dump's windows come after the views', so a window with nodes to tap is taken.
            roots += self.node_roots()
            tappable = [r for r in roots if any(v.clickable for v in r)]
        return tappable[-1] if tappable else (roots[-1] if roots else [])

    def node_roots(self) -> list[list[View]]:
        """The accessibility node dump's windows; none when it goes unanswered, and no more requests for 20 s."""
        size = self.shell(f"wc -c < {self.log}").strip()
        start = int(size) + 1 if size.isdigit() else 1
        self.send(self.A11Y_REQUEST)
        text = ""
        for _ in range(6):
            time.sleep(0.5)
            text = self.shell(f"tail -c +{start} {self.log} | grep 'VT '", timeout=60)
            if self.A11Y_END in text:
                break
        else:
            self.a11y = False
            self.a11y_retry = time.time() + 20
            return []
        self.a11y = True
        text = text[:text.index(self.A11Y_END)]
        return [self.parse(b) for b in text.split("VT ==== root[")[1:]]

    def parse(self, block: str) -> list[View]:
        """One window's views on screen. Rects are the window's own: a window smaller than the screen
        (a dialog) is placed centred, as Android places dialogs, which matched the board's screenshots."""
        out, dx, dy = [], 0, 0
        for line in block.splitlines():
            m = self.VT.search(line)
            if not m:
                continue
            x, y, w, h = (int(m[i]) for i in (3, 4, 5, 6))
            if not out and not (dx or dy) and x == 0 and y == 0 and w < self.width and h < self.height:
                dx, dy = (self.width - w) // 2, (self.height - h) // 2
            if m[8] != "1":
                continue
            x, y = x + dx, y + dy
            if w <= 4 or h <= 4 or x >= self.width or y >= self.height or x + w <= 0 or y + h <= 0:
                continue
            out.append(View(m[1], m[2], x, y, w, h, m[7] == "1", m[9] or ""))
        return out

    def tap(self, x: int, y: int) -> None:
        self.send(f"{x} {y}")

    def scroll(self) -> None:
        cx = self.width // 2
        self.send(f"{cx} {self.height * 3 // 4} {cx} {self.height // 4}")

    def back(self) -> None:
        self.send("b")

    def screenshot(self, local: Path) -> None:
        self.shell("power-shell wakeup >/dev/null; snapshot_display -f /data/local/tmp/ex.jpeg >/dev/null", 40)
        # A relative name from the target directory: a Windows hdc (USB under WSL) can't take a Linux path.
        target = local.with_suffix(".jpeg")
        subprocess.run(self.cmd + ["file", "recv", "/data/local/tmp/ex.jpeg", target.name], cwd=target.parent,
                       capture_output=True, timeout=60)


class Phone:
    """The Android reference phone over adb; uiautomator for the views."""
    BOUNDS = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")

    def __init__(self, adb: str, serial: str, package: str):
        self.cmd = [adb, "-s", serial]
        self.package = package
        size = self.shell("wm size").split()[-1] if self.shell("wm size") else "1080x2340"
        self.width, self.height = (int(v) for v in size.split("x"))

    def shell(self, command: str, timeout: int = 30) -> str:
        try:
            return subprocess.run(self.cmd + ["shell", command], capture_output=True, text=True,
                                  timeout=timeout, errors="replace").stdout.replace("\r", "")
        except subprocess.TimeoutExpired:
            return ""

    def start(self) -> None:
        self.shell(f"am force-stop {self.package}; monkey -p {self.package} -c android.intent.category.LAUNCHER 1")

    def alive(self) -> bool:
        return bool(self.shell(f"pidof {self.package}").strip())

    def views(self) -> list[View]:
        xml = self.shell("uiautomator dump /sdcard/wl-ex.xml >/dev/null 2>&1; cat /sdcard/wl-ex.xml", timeout=40)
        try:
            root = ET.fromstring(xml[xml.find("<?xml"):] if "<?xml" in xml else xml)
        except ET.ParseError:
            return []
        out = []
        for node in root.iter("node"):
            if node.get("package") not in (self.package, None):
                continue
            m = self.BOUNDS.match(node.get("bounds", ""))
            if not m:
                continue
            x1, y1, x2, y2 = (int(v) for v in m.groups())
            if x2 - x1 <= 4 or y2 - y1 <= 4:
                continue
            cls = node.get("class", "?").rsplit(".", 1)[-1]
            vid = (node.get("resource-id") or "-").rsplit("/", 1)[-1]
            out.append(View(cls, vid, x1, y1, x2 - x1, y2 - y1, node.get("clickable") == "true",
                            node.get("text") or node.get("content-desc") or ""))
        return out

    def tap(self, x: int, y: int) -> None:
        self.shell(f"input tap {x} {y}")

    def scroll(self) -> None:
        cx = self.width // 2
        self.shell(f"input swipe {cx} {self.height * 3 // 4} {cx} {self.height // 4} 300")

    def back(self) -> None:
        self.shell("input keyevent 4")

    def screenshot(self, local: Path) -> None:
        png = subprocess.run(self.cmd + ["exec-out", "screencap", "-p"], capture_output=True, timeout=60).stdout
        local.with_suffix(".png").write_bytes(png)


def screen_of(views: list[View]) -> str:
    keys = sorted({f"{v.cls}|{v.vid}" for v in views})
    return hashlib.sha1("\n".join(keys).encode()).hexdigest()[:12]


def refuses_consent(view: View, consent: bool) -> bool:
    return consent and bool(CONSENT_DENY.search(view.text) or CONSENT_DENY_ID.search(view.vid))


def choose(views: list[View], tried: set[str]) -> View | None:
    consent = any(CONSENT.search(v.text) for v in views)
    candidates = [v for v in views if v.clickable and v.key() not in tried
                  and not TEXT_INPUT.search(v.cls) and not DENY.search(v.text) and not DENY_ID.search(v.vid)
                  and not refuses_consent(v, consent)]
    # Labelled views first (a user reads before tapping), then top to bottom, left to right.
    candidates.sort(key=lambda v: (not (v.text or v.vid != "-"), v.y, v.x))
    return candidates[0] if candidates else None


def grid_points(w: int, h: int) -> list[tuple[str, int, int]]:
    """Where to tap blind: the bottom action band first, at 91% of the height (centre, left, right),
    then five rows from 15% to 85%, top to bottom. Welcome and sign-in screens drawn with Compose
    show no clickable view, and keep their buttons at 88-96%: LINE's "Log in", SofaScore's "Get
    started", HelloTalk's "Join", Dropbox's "Sign up". The rows alone stopped at 85%, and a
    60-second run spent its 14 taps above them."""
    cols = [w * (2 * col + 1) // 6 for col in range(3)]
    points = [(f"b,{col}", cols[col], h * 91 // 100) for col in (1, 0, 2)]
    points += [(f"{row},{col}", cols[col], h * (15 + 70 * row // 4) // 100) for row in range(5) for col in range(3)]
    return points


def grid(device, screen: str, tried: set[str]) -> View | None:
    for vid, x, y in grid_points(device.width, device.height):
        v = View("grid", vid, x - 1, y - 1, 2, 2, True, screen)   # one grid per screen
        if v.key() not in tried:
            return v
    return None


def explore(device, seconds: int, out: Path, shot_every: int, settle: float) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    steps, screens, tried, scrolled = [], {}, set(), {}
    died_at = None
    n = 0
    backs_here, last_screen = 0, None
    while time.monotonic() - t0 < seconds:
        if not device.alive():
            died_at = round(time.monotonic() - t0, 1)
            break
        views = device.views()
        screen = screen_of(views)
        screens[screen] = screens.get(screen, 0) + 1
        if n % shot_every == 0:
            device.screenshot(out / f"step-{n:03d}")
        target = choose(views, tried)
        if target is None and scrolled.get(screen, 0) >= 2 and backs_here < 2:
            # Nothing labelled left (or a WebView, Compose, Flutter or game surface the view list
            # can't see into): tap a grid of points, the bottom action band first (grid_points).
            target = grid(device, screen, tried)
        if target is not None:
            tried.add(target.key())
            x, y = target.centre()
            device.tap(x, y)
            action = {"tap": [x, y], "view": target.cls, "id": target.vid,
                      "text": "" if target.cls == "grid" else target.text[:60]}
        elif scrolled.get(screen, 0) < 2:
            scrolled[screen] = scrolled.get(screen, 0) + 1
            device.scroll()
            action = {"scroll": True}
        else:
            device.back()
            action = {"back": True}
        backs_here = backs_here + 1 if "back" in action and screen == last_screen else 0
        last_screen = screen
        if backs_here >= 3 and hasattr(device, "start"):
            device.start()   # Back left the app on the phone: bring it back, as a user would
            backs_here = 0
        steps.append({"t": round(time.monotonic() - t0, 1), "screen": screen, "views": len(views),
                      "clickable": sum(v.clickable for v in views), **action})
        n += 1
        time.sleep(settle)
    if died_at is None and not device.alive():
        died_at = round(time.monotonic() - t0, 1)
    device.screenshot(out / "final")
    result = {"seconds": round(time.monotonic() - t0, 1), "steps": len(steps), "screens": len(screens),
              "taps": sum("tap" in s for s in steps), "scrolls": sum("scroll" in s for s in steps),
              "backs": sum("back" in s for s in steps), "empty_dumps": sum(s["views"] == 0 for s in steps),
              "died_at": died_at, "steps_detail": steps,
              # What the process ended after: "back" (Back closed the app's last screen, which on
              # Westlake ends the process and on Android leaves it cached) or the last tap's view.
              "died_after": None if died_at is None or not steps else
                            "back" if "back" in steps[-1] else f"{steps[-1].get('view')}:{steps[-1].get('id')}"}
    (out / "explore.json").write_text(json.dumps(result, indent=1) + "\n")
    return result


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("platform", choices=["oh", "android"])
    p.add_argument("--serial", required=True)
    p.add_argument("--hdc")
    p.add_argument("--child", type=int)
    p.add_argument("--adb")
    p.add_argument("--package")
    p.add_argument("--out", required=True, type=Path)
    p.add_argument("--seconds", type=int, default=180)
    p.add_argument("--shot-every", type=int, default=10)
    p.add_argument("--settle", type=float, default=1.5, help="seconds to let a screen respond to an action")
    a = p.parse_args()
    if a.platform == "oh":
        if not (a.hdc and a.child):
            p.error("oh needs --hdc and --child")
        device = Board(a.hdc, a.serial, a.child)
    else:
        if not (a.adb and a.package):
            p.error("android needs --adb and --package")
        device = Phone(a.adb, a.serial, a.package)
        device.start()
        time.sleep(8)
    r = explore(device, a.seconds, a.out, a.shot_every, a.settle)
    print(json.dumps({k: v for k, v in r.items() if k != "steps_detail"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
