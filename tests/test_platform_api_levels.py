from __future__ import annotations

import unittest
from pathlib import Path

from westlake_gap.platformapi import annotate, introduced_at, load_platform_index

PLATFORMS = Path("/home/dspfac/android-sdk/platforms")


def finding(kind: str, owner: str, name: str | None = None) -> dict:
    return {"kind": kind, "dependency": {"owner": owner, "name": name}}


class VerdictTest(unittest.TestCase):
    """A gap list mixes three different things; only one of them is worth building."""

    INDEXES = {
        28: {"android/net/wifi/WifiInfo": {"methods": {"getBSSID"}, "fields": set()}},
        34: {
            "android/net/wifi/WifiInfo": {"methods": {"getBSSID", "getPasspointFqdn"}, "fields": set()},
            "android/adservices/common/AdData": {"methods": {"getMetadata"}, "fields": set()},
            "android/view/View": {"methods": {"draw"}, "fields": set()},
        },
    }

    def test_member_on_the_reference_device_is_required(self) -> None:
        findings = [finding("missing_method", "Landroid/net/wifi/WifiInfo;", "getBSSID")]
        annotate(findings, self.INDEXES, reference_api=30)
        self.assertEqual("required", findings[0]["api_verdict"])
        self.assertEqual(28, findings[0]["introduced_api"])

    def test_member_newer_than_the_reference_device_is_not(self) -> None:
        findings = [finding("missing_method", "Landroid/net/wifi/WifiInfo;", "getPasspointFqdn")]
        annotate(findings, self.INDEXES, reference_api=30)
        self.assertEqual("newer-than-reference", findings[0]["api_verdict"])
        self.assertEqual(34, findings[0]["introduced_api"])

    def test_class_newer_than_the_reference_device_is_not(self) -> None:
        findings = [finding("missing_class", "Landroid/adservices/common/AdData;")]
        annotate(findings, self.INDEXES, reference_api=30)
        self.assertEqual("newer-than-reference", findings[0]["api_verdict"])

    def test_a_class_that_was_never_android_is_its_own_verdict(self) -> None:
        findings = [finding("missing_class", "Ljavax/activation/DataHandler;")]
        annotate(findings, self.INDEXES, reference_api=30)
        self.assertEqual("absent-from-platform", findings[0]["api_verdict"])
        self.assertIsNone(findings[0]["introduced_api"])

    def test_unknown_member_of_a_known_class_is_not_claimed_absent(self) -> None:
        """Only the jars supplied are evidence; a newer member must not read as 'never Android'."""
        findings = [finding("missing_method", "Landroid/view/View;", "setFrameContentVelocity")]
        annotate(findings, self.INDEXES, reference_api=30)
        self.assertEqual("member-not-in-indexed-jars", findings[0]["api_verdict"])
        self.assertEqual(34, findings[0]["class_introduced_api"])

    def test_non_absence_findings_are_left_alone(self) -> None:
        findings = [finding("unbound_native", "Lcom/example/Foo;", "bar")]
        summary = annotate(findings, self.INDEXES, reference_api=30)
        self.assertNotIn("api_verdict", findings[0])
        self.assertEqual(0, summary["annotated"])


class PlatformJarTest(unittest.TestCase):
    def test_real_jar_parses_classes_methods_and_fields(self) -> None:
        jar = PLATFORMS / "android-28/android.jar"
        if not jar.exists():
            self.skipTest("android-28 platform jar is not installed")
        index = load_platform_index(jar)
        self.assertGreater(len(index), 3000)
        self.assertIn("getBSSID", index["android/net/wifi/WifiInfo"]["methods"])
        self.assertIn("BSSID", index["android/net/wifi/ScanResult"]["fields"])
        self.assertNotIn("android/adservices/common/AdData", index)
        self.assertEqual(28, introduced_at("Landroid/net/wifi/WifiInfo;", "getBSSID", "missing_method", {28: index}))


if __name__ == "__main__":
    unittest.main()
