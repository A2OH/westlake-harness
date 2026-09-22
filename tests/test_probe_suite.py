"""Known answers for the probe-suite runner's pure logic: verdicts, taps, result merging."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("run_suite", Path(__file__).parents[1] / "probes" / "run_suite.py")
run_suite = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(run_suite)

SUITE = {p["name"]: p for p in json.loads((Path(__file__).parents[1] / "probes" / "suite.json").read_text())["probes"]}


class ProbeSuite(unittest.TestCase):
    def test_every_probe_has_an_apk_and_markers(self) -> None:
        for name, probe in SUITE.items():
            self.assertTrue(probe["pass"], name)
            self.assertTrue(probe["apk"].startswith(name + "/"), name)

    def test_verdicts(self) -> None:
        procs = SUITE["running-app-processes"]
        one_phase = ["[WL-RUNNING-PROCS] phase=application verdict=PASS_SELF_VISIBLE count=1"]
        self.assertEqual(run_suite.evaluate(one_phase, procs), "pending", "both phases must pass")
        both = one_phase + ["[WL-RUNNING-PROCS] phase=activity verdict=PASS_SELF_VISIBLE count=1"]
        self.assertEqual(run_suite.evaluate(both, procs), "pass")
        self.assertEqual(run_suite.evaluate(["[WL-RUNNING-PROCS] phase=application verdict=FAIL_NULL"], procs), "fail")

    def test_tap_comes_from_the_probe(self) -> None:
        dialog = SUITE["dialog-before-window"]
        lines = ["[WL-DIALOG-ORDER] placement=CENTRED at 280,634 size=640x651",
                 "[WL-DIALOG-ORDER] width=FITS right=920 screenWidth=1200",
                 "[WL-DIALOG-ORDER] button center=600,1075"]
        self.assertEqual(run_suite.tap_target(lines, dialog), (600, 1075))
        self.assertEqual(run_suite.evaluate(lines, dialog), "pending", "centred but not yet clicked")
        self.assertEqual(run_suite.evaluate(lines + ["[WL-DIALOG-ORDER] dialog button clicked"], dialog), "pass")
        # McDonald's upgrade dialog was centred and still unreachable: it ran off the right edge.
        overflow = [lines[0], "[WL-DIALOG-ORDER] width=OVERFLOWS right=1290 screenWidth=1200", lines[2]]
        self.assertEqual(run_suite.evaluate(overflow, dialog), "fail", "a window wider than the display")
        self.assertIn("button center=", run_suite.markers(dialog))

    def test_merge_replaces_only_the_same_probe_and_commit(self) -> None:
        document = {"board": "b", "results": [
            {"probe": "a", "westlake_commit": "c1", "passed": False},
            {"probe": "a", "westlake_commit": "c2", "passed": False}]}
        merged = run_suite.merge_results(document, [{"probe": "a", "westlake_commit": "c2", "passed": True}])
        self.assertEqual([(r["westlake_commit"], r["passed"]) for r in merged["results"]], [("c1", False), ("c2", True)])
        text = run_suite.dump(merged)
        self.assertEqual(json.loads(text), merged)
        self.assertEqual(text.count("\n    {"), 2, "one result per line")

    def test_dirty_builds_never_match_a_commit(self) -> None:
        self.assertFalse(("dirty-" + "f6dc6150").startswith("f6dc6150"))


if __name__ == "__main__":
    unittest.main()
