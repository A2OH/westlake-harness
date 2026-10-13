"""The calibration flows' predictions from gap maps (scripts/predict_flows.py)."""
import importlib.util
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("predict_flows", Path(__file__).resolve().parents[1] / "scripts" / "predict_flows.py")
predict_flows = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(predict_flows)

ROWS = [{"id": "svc:clipboard", "verdict": "supplied", "measured": "conformant"},
        {"id": "jni:android.view.KeyCharacterMap", "verdict": "missing", "measured": "broken"},
        {"id": "jni:android.hardware.camera2.impl.CameraMetadataNative", "verdict": "absent"},
        {"id": "svc:alarm", "verdict": "unverified"}]


class Predict(unittest.TestCase):
    def test_a_hard_gap_on_the_path_predicts_a_failure(self) -> None:
        prediction = predict_flows.predict({"rows": ["svc:clipboard", "jni:android.view.KeyCharacterMap"]}, ROWS)
        self.assertEqual(prediction["outcome"], "fails")
        self.assertEqual(prediction["rows"], {"svc:clipboard": "supplied, measured conformant",
                                              "jni:android.view.KeyCharacterMap": "missing, measured broken"})

    def test_a_prefix_matches_every_row_under_it(self) -> None:
        prediction = predict_flows.predict({"rows": ["jni:android.hardware.camera2.*", "jni:android.view.Key"]}, ROWS)
        self.assertEqual(prediction["outcome"], "fails")
        self.assertEqual(list(prediction["rows"]), ["jni:android.hardware.camera2.impl.CameraMetadataNative"])
        self.assertEqual(prediction["no_row"], ["jni:android.view.Key"])

    def test_no_row_and_verdicts_to_verify_predict_it_works(self) -> None:
        prediction = predict_flows.predict({"rows": ["svc:alarm", "intent:*"]}, ROWS)
        self.assertEqual(prediction["outcome"], "works")
        self.assertEqual(prediction["no_row"], ["intent:*"])


if __name__ == "__main__":
    unittest.main()
