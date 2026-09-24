"""Known answers for whole-NDK coverage and the package / libc-abi / weld classification.

The fixture builds a miniature NDK stub directory and miniature board directories with a C
compiler, so the test exercises real ELF export tables, not mocked sets.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from westlake_gap import gapmap, ndk


def _lib(cc: str, path: Path, symbols: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    source = path.with_suffix(".c")
    source.write_text("".join(f"int {name}(void) {{ return 0; }}\n" for name in symbols))
    subprocess.run([cc, "-shared", "-fPIC", "-o", str(path), str(source)], check=True, capture_output=True, timeout=60)
    source.unlink()


class NdkCoverage(unittest.TestCase):
    def setUp(self) -> None:
        self.cc = shutil.which("cc") or shutil.which("gcc")
        if not self.cc:
            self.skipTest("a C compiler is required")
        self.temp = tempfile.TemporaryDirectory(prefix="westlake-ndk-")
        root = Path(self.temp.name)
        _lib(self.cc, root / "ndk/libandroid.so", ["AAsset_open", "ALooper_pollAll", "ASensor_getName", "AConfiguration_new"])
        _lib(self.cc, root / "ndk/libc.so", ["strlen_fixture", "__FD_SET_chk"])
        _lib(self.cc, root / "ndk/libcamera2ndk.so", ["ACameraManager_create"])
        (root / "ndk/libc++.so").write_text("INPUT(-lc++_shared)\n")  # linker script, as in a real NDK
        _lib(self.cc, root / "oh/libc.so", ["strlen_fixture"])
        _lib(self.cc, root / "wl/liblive.so", ["ALooper_pollAll"])
        _lib(self.cc, root / "wl/libbridge.pre-fix-20260901.so", ["AAsset_open"])  # a backup copy
        manifest = root / "westlake/native/android-ndk-sources.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text(json.dumps({"sources": ["android-source/frameworks-base/native/android/asset_manager.cpp"]}))
        self.root = root

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _coverage(self) -> dict:
        root = self.root
        return ndk.coverage(ndk.ndk_surface(root / "ndk"), ndk.library_exports(root / "oh"),
                            ndk.library_exports(root / "wl"), ndk.load_model(),
                            ndk.westlake_manifest_index(root / "westlake"))

    def test_status_strategy_and_traps(self) -> None:
        cov = self._coverage()
        item = {s["symbol"]: s for s in cov["symbols"]}
        self.assertNotIn("libc++.so", cov["per_library"], "linker scripts are not libraries")
        self.assertEqual(item["strlen_fixture"]["status"], "oh")
        self.assertEqual(item["ALooper_pollAll"]["status"], "westlake")

        asset = item["AAsset_open"]
        self.assertEqual(asset["status"], "missing", "an export found only in a backup copy is not provided")
        self.assertEqual(asset["only_in_backup_copies"], ["libbridge.pre-fix-20260901.so"])
        self.assertEqual(asset["group"], "package")
        self.assertEqual(asset["westlake_manifests"], ["android-ndk-sources.json"], "built by Westlake, not deployed")

        self.assertEqual(item["AConfiguration_new"]["group"], "package")
        self.assertEqual(item["AConfiguration_new"]["westlake_manifests"], [], "no manifest compiles configuration.cpp")
        self.assertEqual((item["ASensor_getName"]["group"], item["ASensor_getName"]["weld"]), ("weld", "sensors"))
        self.assertEqual(item["ASensor_getName"]["oh"], "sensors")
        self.assertEqual(item["__FD_SET_chk"]["group"], "libc-abi")
        self.assertEqual((item["ACameraManager_create"]["group"], item["ACameraManager_create"]["weld"]), ("weld", "camera"))
        self.assertEqual(cov["summary"]["status"], {"oh": 1, "westlake": 1, "missing": 5})
        self.assertEqual(cov["summary"]["missing_only_in_backup_copies"], 1)

    def test_variant_names(self) -> None:
        for name in ["libart.pre-jit790.so", "bridge_604.so", "libart-607-known-good.so", "libart_608a.so",
                     "libandroid.choreo-forward.so", "libwl636-jit-prewarm-20260902.so"]:
            self.assertTrue(ndk.is_variant(name), name)
        for name in ["libart.so", "bridge_current.so", "libwl636.so", "libbionic_abi_shim.so", "libharfbuzz_ng.so"]:
            self.assertFalse(ndk.is_variant(name), name)

    def test_gap_map_rows(self) -> None:
        cov = self._coverage()
        scan = {"inventory": {"elfs": [
            {"soname": "libapp.so", "name": "libapp.so",
             "undefined_symbols": ["AAsset_open", "ASensor_getName", "__FD_SET_chk", "__sF"]}]}}
        missing = [{"symbol": n} for n in ["AAsset_open", "ASensor_getName", "__FD_SET_chk", "__sF"]]
        rows = {r["id"]: r for r in gapmap.ndk_symbol_rows(scan, missing, {"__sF"}, cov)}
        self.assertEqual(rows["ndk:package"]["effort"], "XS", "every symbol already has a Westlake build manifest")
        self.assertEqual((rows["ndk:weld:sensors"]["effort"], rows["ndk:weld:sensors"]["oh_touchpoint"]), ("M", "sensors"))
        libc = rows["ndk:libc-abi"]
        self.assertEqual(libc["verdict"], "missing")
        self.assertEqual(libc["covered_symbols"], ["__sF"], "a bionic-private name outside the NDK is still libc ABI")
        self.assertEqual(libc["open_symbols"], ["__FD_SET_chk"])

    def test_symbols_from_an_unshipped_library_are_not_libc(self) -> None:
        cov = self._coverage()
        scan = {"inventory": {"elfs": [
            {"soname": "libjsctooling.so", "name": "libjsctooling.so", "needed": ["libc.so", "libjsc.so"],
             "undefined_symbols": ["JSValueMakeNull", "__FD_SET_chk"]}]}}
        missing = [{"symbol": "JSValueMakeNull", "importing_libraries": ["libjsctooling.so"]},
                   {"symbol": "__FD_SET_chk", "importing_libraries": ["libjsctooling.so"]}]
        rows = {r["id"]: r for r in gapmap.ndk_symbol_rows(scan, missing, set(), cov)}
        self.assertEqual(rows["ndk:unshipped-library:libjsc.so"]["open_symbols"], ["JSValueMakeNull"])
        self.assertEqual(rows["ndk:libc-abi"]["open_symbols"], ["__FD_SET_chk"], "a known libc name stays libc")


if __name__ == "__main__":
    unittest.main()
