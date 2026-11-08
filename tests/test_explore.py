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
