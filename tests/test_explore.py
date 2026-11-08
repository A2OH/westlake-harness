import importlib.util
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "explore", Path(__file__).resolve().parents[1] / "device" / "explore.py")
explore = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(explore)


def view(vid: str, text: str = "", x: int = 0, y: int = 0, cls: str = "Button") -> "explore.View":
    return explore.View(cls, vid, x, y, 100, 60, True, text)


class WhatTheExplorerTaps(unittest.TestCase):
    def test_a_consent_notice_cancel_icon_is_not_tapped(self) -> None:
        # Xiaomi Home's licence screen: the refuse button is an icon, id appwidget_cancel, no text.
        views = [view("smarthome_protocol_text", "I've read and agreed to the Software License and Service Agreement",
                      y=1680, cls="TextView"),
                 view("appwidget_cancel", x=0, y=1800), view("appwidget_confirm", x=600, y=1800)]
        tried = {views[0].key()}
        self.assertEqual(explore.choose(views, tried).vid, "appwidget_confirm")

    def test_a_consent_notice_cancel_text_is_not_tapped(self) -> None:
        views = [view("-", "We value your privacy", y=100, cls="TextView"),
                 view("btn_left", "Cancel", x=0, y=900), view("btn_right", "Continue", x=600, y=900)]
        self.assertEqual(explore.choose(views, {views[0].key()}).vid, "btn_right")

    def test_cancel_elsewhere_is_still_tapped(self) -> None:
        # An update prompt: Cancel is the way past it, and the only control left.
        views = [view("update", "Update", y=900), view("cancel", "Cancel", y=1000)]
        self.assertEqual(explore.choose(views, {views[0].key()}).vid, "cancel")

    def test_refusals_are_never_tapped(self) -> None:
        views = [view("btn_disagree", "Disagree and exit"), view("-", "Exit", y=100)]
        self.assertIsNone(explore.choose(views, set()))


class FakeBoard(explore.Board):
    """The board's app log, which grows by what each tap-channel command makes the app write."""

    def __init__(self, answers: dict[str, str]) -> None:
        super().__init__("hdc", "serial", 7)
        self.answers, self.logtext, self.sent = answers, "", []

    def shell(self, command: str, timeout: int = 30) -> str:
        if command.startswith("wc -c"):
            return str(len(self.logtext.encode()))
        if command.startswith("tail -c +"):
            start = int(command.split("+", 1)[1].split()[0]) - 1
            return "".join(l + "\n" for l in self.logtext.encode()[start:].decode().splitlines() if "VT " in l)
        return ""

    def send(self, command: str) -> None:
        self.sent.append(command)
        self.logtext += self.answers.get(command, "")


COMPOSE_VIEWS = ("VT ==== root[0] ====\n"
                 "VT DecorView id=- rect=[0,0 1200x1920] c=0 en=1 f=0 ftm=0 itm=1 \n"
                 "VT  AndroidComposeView id=- rect=[0,0 1200x1920] c=0 en=1 f=0 ftm=1 itm=1 \n"
                 "VT ==== end ====\n")
COMPOSE_NODES = ("VT ==== root[a0] ====\n"
                 "VT DecorView id=- rect=[0,0 1200x1920] c=0 en=1 f=0 ftm=0 itm=1 \n"
                 "VT  View id=- rect=[0,0 1200x1920] c=0 en=1 f=0 ftm=0 itm=1 \n"
                 'VT   Button id=- rect=[152,1745 432x110] c=1 en=1 f=0 ftm=0 itm=1 "Sign up"\n'
                 'VT   Button id=- rect=[616,1745 432x110] c=1 en=1 f=0 ftm=0 itm=1 "Log in"\n'
                 "VT ==== a11y end ====\n")


class WhatTheExplorerSeesOfCompose(unittest.TestCase):
    def setUp(self) -> None:
        self.sleep, explore.time.sleep = explore.time.sleep, lambda s: None

    def tearDown(self) -> None:
        explore.time.sleep = self.sleep

    def test_a_screen_with_nothing_to_tap_asks_for_the_node_dump(self) -> None:
        board = FakeBoard({"v": COMPOSE_VIEWS, board_request(): COMPOSE_NODES})
        views = board.views()
        self.assertEqual(board.sent, ["v", board_request()])
        self.assertEqual(explore.choose(views, set()).text, "Sign up")

    def test_an_unanswered_request_is_not_repeated(self) -> None:
        board = FakeBoard({"v": COMPOSE_VIEWS})   # a framework without the node dump
        self.assertFalse(any(v.clickable for v in board.views()))
        board.views()
        self.assertEqual(board.sent, ["v", board_request(), "v"])

    def test_a_dump_written_late_is_waited_for(self) -> None:
        # Bumble's dumps came after the first read: the explorer saw no view in any step.
        board = FakeBoard({"v": "VT ==== root[0] ====\n"
                                'VT Button id=ok rect=[0,0 100x60] c=1 en=1 f=0 ftm=0 itm=1 "OK"\nVT ==== end ====\n'})
        reads = []
        shell = board.shell

        def slow(command: str, timeout: int = 30) -> str:
            if command.startswith("tail -c +"):
                reads.append(command)
                if len(reads) < 3:
                    return ""
            return shell(command, timeout)

        board.shell = slow
        self.assertEqual([v.text for v in board.views()], ["OK"])
        self.assertEqual(len(reads), 3)

    def test_a_screen_with_views_to_tap_does_not_ask(self) -> None:
        board = FakeBoard({"v": "VT ==== root[0] ====\n"
                                'VT Button id=ok rect=[0,0 100x60] c=1 en=1 f=0 ftm=0 itm=1 "OK"\nVT ==== end ====\n'})
        board.views()
        self.assertEqual(board.sent, ["v"])


def board_request() -> str:
    return explore.Board.A11Y_REQUEST


class WhereTheExplorerTapsBlind(unittest.TestCase):
    class Board:
        width, height = 1200, 1920

    def test_the_bottom_action_band_comes_first(self) -> None:
        # Dropbox's welcome screen (Compose: no clickable view): Sign up and Log in sit at y 1745-1855.
        points = explore.grid_points(1200, 1920)
        self.assertEqual([(x, y) for _, x, y in points[:3]], [(600, 1747), (200, 1747), (1000, 1747)])
        self.assertEqual(explore.grid(self.Board, "s", set()).centre(), (600, 1747))

    def test_every_point_is_tapped_once_per_screen(self) -> None:
        tried: set[str] = set()
        taps = []
        while (v := explore.grid(self.Board, "s", tried)) is not None:
            tried.add(v.key())
            taps.append(v.centre())
        self.assertEqual(len(taps), 18)
        self.assertEqual(len(set(taps)), 18)
        self.assertEqual(taps[3], (200, 288), "then the rows, top to bottom")


if __name__ == "__main__":
    unittest.main()
