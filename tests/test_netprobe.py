"""netprobe.py's verdicts: what from the board's answer makes a name usable or not."""
import importlib.util
import pathlib
import unittest

_SPEC = importlib.util.spec_from_file_location(
    "netprobe", pathlib.Path(__file__).resolve().parents[1] / "device" / "netprobe" / "netprobe.py")
netprobe = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(netprobe)


def row(name, **fields):
    base = {"name": name, "gai": 0, "v4": ["198.51.100.7"], "v6": 0, "connect": "ok", "tls": "handshake"}
    base.update(fields)
    return base


class ClassifyTest(unittest.TestCase):
    def classify(self, rows, answers):
        return netprobe.classify(rows, lambda name: answers.get(name))

    def test_a_tls_record_back_is_usable_whatever_the_address(self):
        rows = [row("cdn.example", v4=["203.0.113.9"]), row("alert.example", tls="alert")]
        summary = self.classify(rows, {"cdn.example": ["198.51.100.7"], "alert.example": ["198.51.100.7"]})
        self.assertEqual(summary["ok"], 2)
        self.assertEqual(rows[0]["answer"], "different")
        self.assertEqual(summary["different_answers_ok"], ["cdn.example"])

    def test_failures_say_which_step_failed(self):
        rows = [row("gone.example", gai=-2, v4=[]), row("v6only.example", v4=[], v6=2),
                row("dropped.example", connect="timeout", tls="none"), row("reset.example", tls="reset")]
        summary = self.classify(rows, {"reset.example": ["192.0.2.1"]})
        self.assertEqual(summary["ok"], 0)
        self.assertEqual(summary["failed"], {
            "gone.example": "lookup-failed", "v6only.example": "no-ipv4",
            "dropped.example": "connect-timeout", "reset.example": "tls-reset/different"})

    def test_same_network_answer(self):
        rows = [row("near.example", v4=["198.51.100.8"])]
        self.classify(rows, {"near.example": ["198.51.100.7"]})
        self.assertEqual(rows[0]["answer"], "same-24")

    def test_no_reference_leaves_the_answer_unjudged(self):
        rows = [row("offline.example")]
        self.classify(rows, {})
        self.assertNotIn("answer", rows[0])
        self.assertEqual(rows[0]["verdict"], "ok")


if __name__ == "__main__":
    unittest.main()
