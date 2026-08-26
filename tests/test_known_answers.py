from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
import zipfile
import os
from pathlib import Path

from westlake_gap.scanner import build_runtime_index, scan_apk


class KnownAnswerFixture(unittest.TestCase):
    """Executable Milestone-0 scope and detector calibration."""

    def test_c8_c9_and_unbound_native(self) -> None:
        javac = shutil.which("javac")
        d8 = _find_android_d8()
        if not javac or not d8:
            self.skipTest("javac and d8 are required for the executable fixture")

        with tempfile.TemporaryDirectory(prefix="westlake-known-answer-") as temp:
            root = Path(temp)
            compile_api = root / "compile-api"
            platform_src = root / "platform-src"
            app_src = root / "app-src"
            _write(
                compile_api / "android/graphics/ColorMatrix.java",
                """package android.graphics;
                public class ColorMatrix {
                    public ColorMatrix() {}
                    public void set(float[] values) {}
                }
                """,
            )
            _write(
                platform_src / "android/graphics/ColorMatrix.java",
                """package android.graphics;
                public class ColorMatrix { public ColorMatrix() {} }
                """,
            )
            _write(
                app_src / "fixture/ProbeApp.java",
                """package fixture;
                import android.graphics.ColorMatrix;
                public class ProbeApp {
                    public static boolean probe() {
                        try {
                            Class.forName("com.android.org.conscrypt.SSLParametersImpl");
                            return true;
                        } catch (ClassNotFoundException expected) { return false; }
                    }
                    public static void use() { new ColorMatrix().set(new float[20]); }
                    public static native void vendorProfilerStart();
                }
                """,
            )

            api_classes = root / "api-classes"
            platform_classes = root / "platform-classes"
            app_classes = root / "app-classes"
            for output in (api_classes, platform_classes, app_classes):
                output.mkdir()
            _run(javac, "--release", "8", "-d", str(api_classes), str(compile_api / "android/graphics/ColorMatrix.java"))
            _run(javac, "--release", "8", "-d", str(platform_classes), str(platform_src / "android/graphics/ColorMatrix.java"))
            _run(
                javac,
                "--release",
                "8",
                "-cp",
                str(api_classes),
                "-d",
                str(app_classes),
                str(app_src / "fixture/ProbeApp.java"),
            )

            platform_dex = root / "platform-dex"
            app_dex = root / "app-dex"
            platform_dex.mkdir()
            app_dex.mkdir()
            _run(d8, "--min-api", "21", "--output", str(platform_dex), str(platform_classes / "android/graphics/ColorMatrix.class"))
            _run(d8, "--min-api", "21", "--output", str(app_dex), str(app_classes / "fixture/ProbeApp.class"))
            platform_jar = root / "adapter-mainline-stubs.jar"
            with zipfile.ZipFile(platform_jar, "w") as archive:
                archive.write(platform_dex / "classes.dex", "classes.dex")

            runtime = build_runtime_index([platform_jar])
            result = scan_apk(app_dex / "classes.dex", runtime)
            findings = result["findings"]

            self.assertTrue(
                any(
                    item["kind"] == "missing_method"
                    and item["classification"] == "C9-candidate"
                    and item["dependency"]["owner"] == "Landroid/graphics/ColorMatrix;"
                    and item["dependency"]["name"] == "set"
                    and item["dependency"]["signature"] == "([F)V"
                    for item in findings
                ),
                "must rediscover the hollow ColorMatrix.set contract",
            )
            self.assertTrue(
                any(
                    item["kind"] == "existence_probe"
                    and item["classification"] == "C8-candidate"
                    and item["dependency"]["owner"] == "Lcom/android/org/conscrypt/SSLParametersImpl;"
                    and item["probe_only"]
                    for item in findings
                ),
                "must retain a proving Class.forName flow as a C8 candidate",
            )
            self.assertTrue(
                any(
                    item["kind"] == "unbound_native"
                    and item["classification"] == "V-C1-candidate"
                    and item["dependency"]["name"] == "vendorProfilerStart"
                    for item in findings
                ),
                "must report a native declaration with no export/registration evidence",
            )
            serialized = str(findings)
            self.assertNotIn("iftable", serialized)
            self.assertNotIn("Surface vtable", serialized)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _run(*command: str) -> None:
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)


def _find_android_d8() -> str | None:
    candidates: list[Path] = []
    if os.environ.get("WESTLAKE_D8"):
        candidates.append(Path(os.environ["WESTLAKE_D8"]))
    for root_name in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        if os.environ.get(root_name):
            candidates.extend(sorted((Path(os.environ[root_name]) / "build-tools").glob("*/d8"), reverse=True))
    candidates.extend(sorted((Path.home() / "android-sdk/build-tools").glob("*/d8"), reverse=True))
    command_d8 = shutil.which("d8")
    if command_d8:
        candidates.append(Path(command_d8))
    for candidate in candidates:
        try:
            result = subprocess.run(
                [str(candidate), "--version"], capture_output=True, text=True, timeout=10
            )
        except OSError:
            continue
        if result.returncode == 0 and "D8" in (result.stdout + result.stderr):
            return str(candidate)
    return None


if __name__ == "__main__":
    unittest.main()
