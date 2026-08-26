from __future__ import annotations

import unittest

from westlake_gap.report import aggregate


class ReportingTest(unittest.TestCase):
    def test_unresolved_is_not_a_gap(self) -> None:
        scan = {
            "runtime_lock_id": "runtime:test",
            "apk": {"package": "example", "filename": "example.apk", "sha256": "a", "bytes": 1},
            "inventory": {
                "defined_classes": 1,
                "platform_type_references": 1,
                "platform_method_references": 1,
                "platform_field_references": 0,
            },
            "summary": {"finding_count": 1, "unresolved_count": 1},
            "findings": [
                _finding("missing_method", "C1/C4", "Landroid/Test;", "run", "()V"),
                _finding("unbound_native", "CU", "Lexample/Test;", "nativeRun", "()V"),
            ],
        }
        portfolio = aggregate([scan])
        self.assertEqual(1, portfolio["metrics"]["unique_gap_count"])
        self.assertEqual(1, portfolio["metrics"]["unresolved_finding_count"])
        self.assertEqual("missing_method", portfolio["gaps"][0]["kind"])
        self.assertNotIn("CU", portfolio["gaps"][0]["classifications"])


def _finding(kind: str, classification: str, owner: str, name: str, signature: str) -> dict:
    return {
        "kind": kind,
        "classification": classification,
        "dependency": {"layer": "J", "owner": owner, "name": name, "signature": signature},
        "reference_count": 1,
    }


if __name__ == "__main__":
    unittest.main()

