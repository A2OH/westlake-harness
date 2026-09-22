"""An ART sampling trace decodes to the methods that were on a stack."""

from __future__ import annotations

import struct
import unittest

from westlake_gap import methodtrace


def build_trace(records: list[tuple[int, int]]) -> bytes:
    """A miniature ART trace: two threads, three methods, one record per sample."""
    header = (
        "*version\n3\nclock=dual\nvm=art\n"
        "*threads\n1\tmain\n12\tstartup\n"
        "*methods\n"
        "0x1234\tcom.mcdonalds.startup.AppConfigurationInitializer\tx\t(Lkotlin/coroutines/Continuation;)V\tSourceFile\n"
        "0x2000\tcom.mcdonalds.config.ConfigHelper\ti\t(Ljava/util/Map;)V\tSourceFile\n"
        "0x3000\tandroid.os.Looper\tloop\t()V\tLooper.java\n"
        "*end\n"
    ).encode()
    record_size = 4 + 4 + 4 + 4   # thread, method+action, two clocks
    body = struct.pack("<IHHqH", methodtrace.HEADER_MAGIC, 3, 18, 0, record_size)
    body = body.ljust(18, b"\0")
    for thread, method in records:
        body += struct.pack("<II", thread, method) + struct.pack("<II", 0, 0)
    return header + body


class Decode(unittest.TestCase):
    def test_methods_that_ran(self) -> None:
        blob = build_trace([(12, 0x1234), (12, 0x1234), (1, 0x3000), (12, 0x2000)])
        trace = methodtrace.parse(blob)
        self.assertEqual(trace["records"], 4)
        self.assertEqual(trace["threads"][12], "startup")

        hits = methodtrace.ran(trace, ["com.mcdonalds"])
        self.assertEqual([(h["method"], h["samples"]) for h in hits],
                         [("com.mcdonalds.startup.AppConfigurationInitializer.x", 2),
                          ("com.mcdonalds.config.ConfigHelper.i", 1)])
        self.assertEqual(hits[0]["threads"], [12], "sampled on the startup thread")
        self.assertNotIn("android.os.Looper.loop", [h["method"] for h in hits], "prefix filters the platform out")

    def test_a_method_never_sampled_is_absent(self) -> None:
        trace = methodtrace.parse(build_trace([(1, 0x3000)]))
        self.assertEqual(methodtrace.ran(trace, ["com.mcdonalds"]), [])
        report = methodtrace.markdown(trace, [], ["com.mcdonalds"])
        self.assertIn("a miss is not", report, "the report must not read as proof of absence")

    def test_rejects_other_files(self) -> None:
        with self.assertRaises(ValueError):
            methodtrace.parse(b"not a trace at all")


if __name__ == "__main__":
    unittest.main()
