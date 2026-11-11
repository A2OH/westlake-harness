import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "device"))


class FakeDevice:
    def __init__(self, screens):
        self.screens, self.taps, self.backs = screens, [], 0

    def views(self):
        return self.screens[min(len(self.taps), len(self.screens) - 1)]

    def tap(self, x, y):
        self.taps.append((x, y))

    def scroll(self):
        pass

    def back(self):
        self.backs += 1

    def screenshot(self, local):
        pass

    def alive(self):
        return True


class ChecksTest(unittest.TestCase):
    def test_consent_then_gate(self):
        """A consent notice is accepted through its accepting control, never its refusing one; a wait passes on
        the text it names; a missing view fails the step and stops the run."""
        import checks
        from explore import View
        notice = [View("TextView", "msg", 0, 100, 500, 50, False, "Read our Privacy Policy and Terms"),
                  View("Button", "decline", 0, 300, 200, 80, True, "Do not agree"),
                  View("Button", "accept", 300, 300, 200, 80, True, "Agree and continue")]
        gate = [View("TextView", "title", 0, 100, 500, 50, False, "Enter your phone number")]
        device = FakeDevice([notice, gate])
        result = checks.run(device, [{"do": "consent"}, {"do": "wait", "text": "phone number", "seconds": 1},
                                     {"do": "tap", "text": "^Next$"}, {"do": "back"}], Path("/nonexistent"), settle=0)
        self.assertEqual(device.taps, [(400, 340)])  # the accepting button's centre
        self.assertEqual([r["ok"] for r in result["steps"]], [True, True, False])
        self.assertEqual((result["passed"], result["of"]), (2, 4))

    def test_no_notice_passes_consent(self):
        import checks
        from explore import View
        device = FakeDevice([[View("TextView", "t", 0, 0, 10, 10, False, "Home")]])
        result = checks.run(device, [{"do": "consent"}], Path("/nonexistent"), settle=0)
        self.assertTrue(result["steps"][0]["ok"])
        self.assertEqual(device.taps, [])

    def test_tap_reaches_a_label_inside_a_clickable_tab(self):
        """YouTube's bottom bar: the tab is clickable and carries no text, its "Shorts" label is not clickable.
        The tap lands on the label, as a finger would."""
        import checks
        from explore import View
        bar = [View("FrameLayout", "pivot_bar_item", 300, 1820, 300, 100, True, ""),
               View("TextView", "text", 400, 1880, 100, 30, False, "Shorts")]
        device = FakeDevice([bar])
        result = checks.run(device, [{"do": "tap", "text": "^Shorts$"}], Path("/nonexistent"), settle=0)
        self.assertTrue(result["steps"][0]["ok"])
        self.assertEqual(device.taps, [(450, 1895)])

    def test_consent_prefers_the_button_to_the_sentence(self):
        """Viber: the legal sentence is clickable (its links) and says "agree"; the button is what accepts."""
        import checks
        from explore import View
        welcome = [View("TextView", "legal", 0, 1500, 1000, 60, True,
                        'By tapping "Start now" you agree to our Terms & Policies'),
                   View("Button", "start", 100, 1700, 1000, 80, True, "Agree and continue")]
        device = FakeDevice([welcome])
        checks.run(device, [{"do": "consent"}], Path("/nonexistent"), settle=0)
        self.assertEqual(device.taps, [(600, 1740)])


if __name__ == "__main__":
    unittest.main()
