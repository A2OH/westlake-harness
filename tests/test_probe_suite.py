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

    def test_a_hilog_marker_fails_a_probe_that_passed_in_app(self) -> None:
        gl = SUITE["gl-contracts"]
        passed = ["[WL-GL-PROBE] verdict=ALL_PASS"]
        self.assertEqual(run_suite.evaluate(passed, gl, []), "pass")
        starved = ["10-03 10:30:33.706 10221 10286 E C01401/Bufferqueue: <native_window.cpp:229-NativeWindowRequestBuffer>: "
                   "RequestBuffer ret:40601000, uniqueId: 43898860732416."]
        self.assertEqual(run_suite.evaluate(passed, gl, starved), "fail")

    def test_tap_comes_from_the_probe(self) -> None:
        dialog = SUITE["dialog-before-window"]
        lines = ["[WL-DIALOG-ORDER] placement=CENTRED at 280,634 size=640x651",
                 "[WL-DIALOG-ORDER] width=FITS right=920 screenWidth=1200",
                 "[WL-DIALOG-ORDER] alertWidth=FITS at 58 right=1141 screenWidth=1200",
                 "[WL-CONTRACT] wm:window-placement PASS dialog at 280,634 size 640x651",
                 "[WL-DIALOG-ORDER] button center=600,1075"]
        self.assertEqual(run_suite.tap_target(lines, dialog), (600, 1075))
        self.assertEqual(run_suite.evaluate(lines, dialog), "pending", "placed, and the tap not yet in")
        clicked = lines + ["[WL-DIALOG-ORDER] dialog button clicked",
                           "[WL-CONTRACT] wm:dialog-stacking PASS the tap reached the dialog's button",
                           "[WL-CONTRACT] done"]
        self.assertEqual(run_suite.evaluate(clicked, dialog), "pass")
        # Placement and stacking are rows of their own: a misplaced dialog (McDonald's upgrade dialog
        # ran off the right edge) no longer ends the run before the tap that measures stacking.
        misplaced = [line.replace(" PASS ", " FAIL ") if "window-placement" in line else line for line in clicked]
        outcomes = {r["row"]: r["outcome"] for r in run_suite.contract_results(misplaced, dialog)}
        self.assertEqual(outcomes, {"wm:window-placement": "fail", "wm:dialog-stacking": "pass"})
        self.assertIn("button center=", run_suite.markers(dialog))

    def test_a_contract_probe_gives_a_result_per_row(self) -> None:
        probe = {"name": "media-contracts", "pass": ["[WL-CONTRACT] done"],
                 "contracts": {"prefix": "[WL-CONTRACT] "}}
        lines = ["[WL-CONTRACT] jni:android.media.MediaCodec PASS decoded 30 frames",
                 "[WL-CONTRACT] svc:vibrator ABSENT hasVibrator=false, vibrate() returned",
                 "[WL-CONTRACT] jni:android.media.MediaMetadataRetriever FAIL UnsatisfiedLinkError native_init",
                 "[WL-CONTRACT] not-a-result", "[WL-CONTRACT] done"]
        results = {r["row"]: r for r in run_suite.contract_results(lines, probe)}
        self.assertEqual(sorted(results), ["jni:android.media.MediaCodec", "jni:android.media.MediaMetadataRetriever",
                                           "svc:vibrator"])
        self.assertEqual((results["svc:vibrator"]["outcome"], results["svc:vibrator"]["passed"]), ("absent", True))
        failed = results["jni:android.media.MediaMetadataRetriever"]
        self.assertEqual((failed["outcome"], failed["passed"], failed["probe"]),
                         ("fail", False, "media-contracts/jni:android.media.MediaMetadataRetriever"))
        self.assertIn("[WL-CONTRACT] ", run_suite.markers(probe))
        self.assertEqual(run_suite.evaluate(lines, probe), "pass", "the probe finished")
        icu = {"name": "icu-data", "pass": ["[WL-ICU] done"], "contracts": {"prefix": "[WL-ICU] ", "ok": "ok=",
                                                                              "fail": "FAILED"}}
        icu_lines = ["[WL-ICU] zone.default ok=America/Los_Angeles", "[WL-ICU] locale.display FAILED NullPointerException"]
        self.assertEqual([r["outcome"] for r in run_suite.contract_results(icu_lines, icu)], ["pass", "fail"])

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
