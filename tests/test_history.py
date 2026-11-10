import tempfile
import unittest
from pathlib import Path


def _round(directory, tag, ended, rows):
    lines = ["%-50s %d %-12s 100 0 %s" % ("hk-" + app, 5 if rung == "drawing" else 2, rung, blocker)
             for app, rung, blocker in rows]
    text = "\n".join(lines) + "\n" + ended + " " + tag + " done\n"
    (Path(directory) / ("round-" + tag + ".log")).write_text(text)


class HistoryTest(unittest.TestCase):
    def test_classes(self):
        """Regressions, improvements and flaky apps against the rounds before, ordered by when they ended."""
        from westlake_gap import history
        with tempfile.TemporaryDirectory() as d:
            _round(d, "r1", "Mon Nov  9 10:00:00 PST 2026", [("a", "drawing", "-"), ("b", "bound", "x"),
                                                             ("c", "drawing", "-"), ("d", "drawing", "-")])
            _round(d, "r2", "Mon Nov  9 12:00:00 PST 2026", [("a", "drawing", "-"), ("b", "bound", "x"),
                                                             ("c", "view", "y"), ("d", "drawing", "-")])
            _round(d, "r3", "Tue Nov 10 09:00:00 PST 2026", [("a", "view", "z"), ("b", "drawing", "-"),
                                                             ("c", "drawing", "-"), ("d", "drawing", "-"),
                                                             ("e", "drawing", "-")])
            # A table printed twice: the last row counts.
            _round(d, "r0play", "Mon Nov  9 09:00:00 PST 2026", [("a", "view", "-")])
            rows = {r["app"]: r for r in history.compare(Path(d), "r3")}
            self.assertEqual(rows["a"]["class"], "regression")
            self.assertEqual(rows["b"]["class"], "improvement")
            # c: drew, then not, then drew again: two changes.
            self.assertEqual(rows["c"]["class"], "flaky")
            self.assertEqual(rows["d"]["class"], "steady")
            self.assertEqual(rows["e"]["class"], "new")
            self.assertEqual([b["round"] for b in rows["a"]["before"]], ["r2", "r1"])

    def test_settled_after_one_change(self):
        """One change in an earlier round, the same since: a fix that landed, not flakiness."""
        from westlake_gap import history
        self.assertEqual(history.classify(True, [True, False, False]), ("settled", 0))
        self.assertEqual(history.classify(False, [False, False, True]), ("settled", 1))
        self.assertEqual(history.classify(True, [False, True, False])[0], "flaky")
        self.assertEqual(history.classify(True, []), ("new", None))

    def test_pass_rates(self):
        from westlake_gap import history
        with tempfile.TemporaryDirectory() as d:
            _round(d, "r1", "Mon Nov  9 10:00:00 PST 2026", [("a", "drawing", "-"), ("b", "view", "-")])
            _round(d, "r2", "Tue Nov 10 10:00:00 PST 2026", [("a", "view", "-"), ("b", "view", "-")])
            rates = {r["app"]: r for r in history.pass_rates(Path(d), 4)}
            self.assertEqual((rates["a"]["drew"], rates["a"]["runs"]), (1, 2))
            self.assertEqual(rates["a"]["rounds"], ["r2:view", "r1:drew"])
            self.assertEqual(rates["b"]["drew"], 0)
            # Apps that drew in some rounds but not all come first.
            self.assertEqual(history.pass_rates(Path(d), 4)[0]["app"], "a")

    def test_last_row_counts(self):
        from westlake_gap import history
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "round-x.log"
            p.write_text("hk-a 2 bound 10 0 -\nhk-a 5 drawing 99 0 -\nTue Nov 10 10:05:31 PST 2026 x done\n")
            ended, verdicts = history.read_round(p)
            self.assertEqual(verdicts["a"][0], "drawing")
            self.assertIsNotNone(ended)


if __name__ == "__main__":
    unittest.main()
