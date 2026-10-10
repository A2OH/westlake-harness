"""The calibration flows' checks and scoring (probes/run_flows.py)."""
import importlib.util
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location("run_flows", Path(__file__).resolve().parents[1] / "probes" / "run_flows.py")
flows = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(flows)


def _wav(path: Path, samples: list[int]) -> Path:
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(48000)
        out.writeframes(struct.pack("<%dh" % len(samples), *samples))
    return path


def _image(path: Path, fill: int, box: tuple[int, int, int, int] | None = None, ink: int = 0) -> Path:
    from PIL import Image, ImageDraw
    image = Image.new("L", (120, 192), fill)
    if box:
        ImageDraw.Draw(image).rectangle(box, fill=ink)
    image.save(path, "JPEG")
    return path


class Checks(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_sound_is_any_non_zero_sample(self) -> None:
        tone = [int(3000 * math.sin(2 * math.pi * 1000 * i / 48000)) for i in range(48000)]
        silent = _wav(self.dir / "silent.wav", [0] * 48000)
        playing = _wav(self.dir / "tone.wav", tone)
        self.assertEqual(flows.audio_nonzero(silent), 0)
        self.assertGreater(flows.audio_nonzero(playing), 40000)
        evidence = {"files": {"audio": playing}, "alive": True, "log": ""}
        self.assertEqual(flows.check({"audio": "audio", "min_nonzero": 20000}, evidence)[0], True)
        evidence["files"]["audio"] = silent
        self.assertEqual(flows.check({"audio": "audio", "min_nonzero": 20000}, evidence)[0], False)
        self.assertFalse(flows.check({"audio": "missing"}, evidence)[0])

    def test_a_region_that_changed_and_one_that_did_not(self) -> None:
        before = _image(self.dir / "before.jpeg", 240)
        keyboard = _image(self.dir / "after.jpeg", 240, box=(0, 100, 119, 170), ink=40)
        same = _image(self.dir / "same.jpeg", 240)
        evidence = {"files": {"before": before, "after": keyboard, "same": same}, "alive": True, "log": ""}
        lower = [0, 100, 120, 170]
        self.assertTrue(flows.check({"changed": ["before", "after"], "region": lower}, evidence)[0])
        self.assertFalse(flows.check({"changed": ["before", "same"], "region": lower}, evidence)[0])
        self.assertFalse(flows.check({"changed": ["before", "after"], "region": [0, 0, 120, 90]}, evidence)[0],
                         "the change is outside the region")

    def test_dark_text_on_a_light_page(self) -> None:
        page = _image(self.dir / "page.jpeg", 240)
        heading = _image(self.dir / "heading.jpeg", 240, box=(10, 20, 60, 30), ink=0)
        evidence = {"files": {"page": page, "heading": heading}, "alive": True, "log": ""}
        self.assertFalse(flows.check({"dark": "page", "region": [0, 10, 120, 40]}, evidence)[0])
        self.assertTrue(flows.check({"dark": "heading", "region": [0, 10, 120, 40]}, evidence)[0])

    def test_unreadable_evidence_fails_its_check(self) -> None:
        broken = self.dir / "broken.wav"
        broken.write_bytes(b"\0" * 64)
        passed, seen = flows.check({"audio": "audio"}, {"files": {"audio": broken}, "alive": True, "log": ""})
        self.assertFalse(passed)
        self.assertIn("unreadable", seen)

    def test_alive_and_log(self) -> None:
        evidence = {"files": {}, "alive": False, "log": "No video files found"}
        self.assertFalse(flows.check({"alive": True}, evidence)[0])
        self.assertTrue(flows.check({"log": "No video files found"}, evidence)[0])
        self.assertFalse(flows.check({"log": "No video files found", "present": False}, evidence)[0])


class Scoring(unittest.TestCase):
    def test_each_verdict(self) -> None:
        self.assertEqual(flows.score("works", "works"), "confirmed")
        self.assertEqual(flows.score("fails", "fails"), "confirmed")
        self.assertEqual(flows.score("fails", "works"), "false alarm")
        self.assertEqual(flows.score("works", "fails"), "miss")

    def test_precision_and_recall_of_the_failure_predictions(self) -> None:
        def flow(predicted, observed):
            return {"predicted": predicted, "observed": observed,
                    "verdict": flows.score(predicted, observed) if observed != "not run" else "not run"}
        result = flows.summary([flow("fails", "fails"), flow("fails", "works"), flow("works", "fails"),
                                flow("works", "fails"), flow("works", "works"), flow("works", "not run")])
        self.assertEqual((result["ran"], result["confirmed"], result["false_alarms"], result["misses"]), (5, 2, 1, 2))
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 0.33)


if __name__ == "__main__":
    unittest.main()
