from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from westlake_gap.scanner import build_runtime_index, read_elf, scan_apk


class NativeVisibilityFixture(unittest.TestCase):
    def test_registration_table_runtime_export_and_abi_gate(self) -> None:
        javac = shutil.which("javac")
        d8 = _find_android_d8()
        cc = shutil.which("cc") or shutil.which("gcc")
        if not javac or not d8 or not cc:
            self.skipTest("javac, d8, and a C compiler are required")

        with tempfile.TemporaryDirectory(prefix="westlake-native-visibility-") as temp:
            root = Path(temp)
            source = root / "Probe.java"
            _write(
                source,
                """package fixture;
                public class Probe { public static native void registeredOnly(); }
                """,
            )
            classes = root / "classes"
            dex = root / "dex"
            classes.mkdir()
            dex.mkdir()
            _run(javac, "--release", "8", "-d", str(classes), str(source))
            _run(d8, "--min-api", "21", "--output", str(dex), str(classes / "fixture/Probe.class"))

            registration_c = root / "registration.c"
            _write(
                registration_c,
                """typedef struct { const char *name; const char *sig; void *fn; } Method;
                static void implementation(void) {}
                __attribute__((used)) static Method methods[] = {
                    {"registeredOnly", "()V", (void *)&implementation},
                };
                __attribute__((visibility("default"))) int JNI_OnLoad(void *vm, void *reserved) {
                    return methods != 0 ? 0x00010006 : 0;
                }
                """,
            )
            registration_so = root / "libregistration.so"
            _run(cc, "-shared", "-fPIC", "-Wl,--build-id", "-o", str(registration_so), str(registration_c))
            record = read_elf(path=registration_so)
            self.assertTrue(record["has_jni_onload"])
            self.assertTrue(record["build_id"])
            self.assertTrue(
                any(
                    entry["name"] == "registeredOnly" and entry["signature"] == "()V"
                    for entry in record["jni_registration_entries"]
                )
            )

            app = root / "fixture.apk"
            with zipfile.ZipFile(app, "w") as archive:
                archive.write(dex / "classes.dex", "classes.dex")
                archive.write(registration_so, "lib/x86_64/libregistration.so")
            runtime = build_runtime_index([], target_abi="x86_64")
            scanned = scan_apk(app, runtime)
            native = scanned["inventory"]["declared_native_methods"][0]
            self.assertEqual("static-registration-table-candidate", native["state"])
            self.assertEqual("classes.dex", native["dex"])
            self.assertTrue(native["dex_sha256"])
            self.assertEqual("target-abi-available", scanned["inventory"]["native_resolution"]["abi_status"])

            wrong_abi = scan_apk(app, build_runtime_index([], target_abi="arm64-v8a"))
            self.assertEqual(
                "target-abi-unavailable",
                wrong_abi["inventory"]["declared_native_methods"][0]["state"],
            )

            export_c = root / "export.c"
            _write(
                export_c,
                """__attribute__((visibility("default")))
                void Java_fixture_Probe_registeredOnly(void) {}
                """,
            )
            bridge = root / "libbridge.so"
            _run(cc, "-shared", "-fPIC", "-Wl,--build-id", "-o", str(bridge), str(export_c))
            bridge_runtime = build_runtime_index([], [bridge], target_abi="x86_64")
            runtime_resolved = scan_apk(dex / "classes.dex", bridge_runtime)
            native = runtime_resolved["inventory"]["declared_native_methods"][0]
            self.assertEqual("runtime-export-resolved", native["state"])
            self.assertEqual("PLATFORM_FRAMEWORK", native["provider_scope"])


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


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
    command = shutil.which("d8")
    if command:
        candidates.append(Path(command))
    for candidate in candidates:
        try:
            result = subprocess.run([str(candidate), "--version"], capture_output=True, text=True, timeout=10)
        except OSError:
            continue
        if result.returncode == 0 and "D8" in result.stdout + result.stderr:
            return str(candidate)
    return None


if __name__ == "__main__":
    unittest.main()
