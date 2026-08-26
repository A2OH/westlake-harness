from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from westlake_gap.trace import (
    build_evidence_ledger,
    build_watchlist,
    markdown_evidence_report,
    parse_trace_files,
)


class TraceEvidenceTest(unittest.TestCase):
    def test_legacy_fallback_hit_is_not_a_terminal_miss(self) -> None:
        scan = _scan()
        with tempfile.TemporaryDirectory(prefix="westlake-trace-") as temp:
            trace = Path(temp) / "stderr.log"
            trace.write_text(
                "[WESTLAKE-JNIMISS] void fixture.Probe.registeredOnly() declaring_class=0x1\n"
                "[WESTLAKE-JNIDLSYM] resolved Java_fixture_Probe_registeredOnly via RTLD_DEFAULT\n",
                encoding="utf-8",
            )
            ledger = build_evidence_ledger(
                [scan], parse_trace_files([trace]), "run-1", "cold-launch"
            )
        self.assertEqual(
            "runtime-dlsym-resolved",
            ledger["native_evidence"][0]["runtime_state"],
        )
        self.assertEqual(0, ledger["metrics"]["unmatched_event_count"])

    def test_structured_terminal_miss_and_caller_keyed_reflection_watch(self) -> None:
        scan = _scan()
        watchlist = build_watchlist([scan])
        self.assertEqual(1, len(watchlist["reflective_loads"]))
        self.assertEqual("Lfixture/Caller;", watchlist["reflective_loads"][0]["caller_class"])
        event = {
            "event_type": "JNI_LOOKUP_MISS",
            "class_descriptor": "Lfixture/Probe;",
            "method_name": "registeredOnly",
            "method_signature": "()V",
            "terminal": True,
        }
        ledger = build_evidence_ledger([scan], [event], "run-2", "feature")
        self.assertEqual("runtime-confirmed-miss", ledger["native_evidence"][0]["runtime_state"])
        self.assertIn("runtime-confirmed-miss", markdown_evidence_report(ledger))

        class_event = {
            "event_type": "CLASS_LOAD_FAILURE",
            "package": "fixture",
            "apk_sha256": "apk:test",
            "requested_class": "Lmissing/Feature;",
            "caller_class": "Lfixture/Caller;",
            "caller_method": "probe",
            "caller_signature": "()V",
        }
        ledger = build_evidence_ledger([scan], [class_event], "run-3", "feature")
        self.assertEqual(
            "runtime-load-failure",
            ledger["reflection_evidence"][0]["runtime_state"],
        )

    def test_multi_apk_legacy_event_is_not_cross_attributed(self) -> None:
        first = _scan()
        second = _scan()
        second["apk"] = {"package": "fixture.two", "sha256": "apk:two"}
        event = {
            "event_type": "JNI_DLSYM_HIT",
            "symbol": "Java_fixture_Probe_registeredOnly",
            "legacy_text": True,
        }
        ledger = build_evidence_ledger([first, second], [event], "run-4", "portfolio")
        self.assertEqual(
            {"not-observed": 2},
            ledger["metrics"]["native_runtime_states"],
        )
        self.assertEqual(
            "ambiguous-artifact-provenance",
            ledger["unmatched_events"][0]["join_status"],
        )

    def test_wrong_abi_native_is_excluded_from_runtime_watchlist(self) -> None:
        scan = _scan()
        scan["inventory"]["declared_native_methods"][0]["state"] = "target-abi-unavailable"
        watchlist = build_watchlist([scan])
        self.assertEqual([], watchlist["native_methods"])
        self.assertEqual(
            {"target-abi-unavailable": 1},
            watchlist["excluded_native_state_counts"],
        )


def _scan() -> dict:
    return {
        "runtime_lock_id": "runtime:test",
        "apk": {"package": "fixture", "sha256": "apk:test"},
        "inventory": {
            "declared_native_methods": [
                {
                    "owner": "Lfixture/Probe;",
                    "name": "registeredOnly",
                    "descriptor": "()V",
                    "dex": "classes.dex",
                    "dex_sha256": "dex:test",
                    "jni_short": "Java_fixture_Probe_registeredOnly",
                    "jni_long": "Java_fixture_Probe_registeredOnly__",
                    "classification": "CU",
                    "state": "registration-source-unattributed",
                }
            ]
        },
        "findings": [
            {
                "kind": "existence_probe",
                "classification": "CU",
                "dependency": {"owner": "Lmissing/Feature;"},
                "evidence": [
                    {
                        "owner": "Lfixture/Caller;",
                        "method": "probe",
                        "descriptor": "()V",
                        "dex": "classes.dex",
                        "api": "Class.forName",
                    }
                ],
            }
        ],
    }


if __name__ == "__main__":
    unittest.main()
