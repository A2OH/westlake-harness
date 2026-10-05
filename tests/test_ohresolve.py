"""Known answers for resolving an APK's native imports against a library index."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from westlake_gap import ohresolve


class Resolve(unittest.TestCase):
    def test_a_versioned_import_needs_the_same_version_or_an_unversioned_definition(self) -> None:
        """Messenger: libcore.so asks for __system_property_read_callback@LIBC_O; the shim had it under LIBC."""
        scan = {"inventory": {"elfs": [{"name": "libcore.so", "undefined_symbols": [
            "__system_property_read_callback", "getrandom", "__system_property_get"],
            "import_versions": {"__system_property_read_callback": "LIBC_O", "getrandom": "LIBC_P",
                                "__system_property_get": "LIBC"}}]}}
        provided = {"__system_property_read_callback", "getrandom", "__system_property_get"}
        versions = {"__system_property_read_callback": {"LIBC"}, "getrandom": {None}, "__system_property_get": {"LIBC"}}
        result = ohresolve.resolve(scan, provided, {}, versions)
        self.assertEqual([m["symbol"] for m in result["missing"]], ["__system_property_read_callback"])
        self.assertEqual(result["missing"][0]["version_mismatch"], {"wanted": ["LIBC_O"], "defined": ["LIBC"]})
        versions["__system_property_read_callback"] = {"LIBC_O"}
        self.assertEqual(ohresolve.resolve(scan, provided, {}, versions)["missing"], [])
        self.assertEqual(ohresolve.resolve(scan, provided, {})["missing"], [], "no versions known: names only")

    def test_an_import_versioned_against_a_sibling_clashes_with_an_unversioned_board_copy(self) -> None:
        """Fennec: libxul imports free@libmozglue.so; musl's unversioned free took the binding."""
        scan = {"inventory": {"elfs": [
            {"name": "lib/arm64-v8a/libxul.so", "soname": "libxul.so",
             "undefined_symbols": ["free", "CERT_Dup", "memcpy"],
             "import_versions": {"free": "libmozglue", "CERT_Dup": "libnss3", "memcpy": "LIBC"}},
            {"name": "lib/arm64-v8a/libmozglue.so", "soname": "libmozglue.so", "exported_symbols": ["free"]},
            {"name": "lib/arm64-v8a/libnss3.so", "soname": "libnss3.so", "exported_symbols": ["CERT_Dup"]}]}}
        versions = {"free": {None}, "memcpy": {None}}
        result = ohresolve.resolve(scan, {"free", "memcpy"}, {}, versions)
        self.assertEqual(result["versioned_clash"],
                         [{"symbol": "free", "version": "libmozglue", "importing_libraries": ["libxul.so"]}])
        self.assertEqual(ohresolve.versioned_clashes(scan["inventory"]["elfs"], {"free": {"LIBC"}}), [],
                         "a board copy under a version of its own does not match another version")
        self.assertEqual(ohresolve.resolve(scan, {"free", "memcpy"}, {})["versioned_clash"], [], "no versions known")

    def test_weak_ndk_imports_nothing_defines(self) -> None:
        """Fennec: libxul imports ASystemFontIterator_open (API 29) weakly; a call jumped to 0."""
        scan = {"inventory": {"elfs": [{"soname": "libxul.so", "exported_symbols": [],
                                        "undefined_symbols": ["ASystemFontIterator_open", "AFont_close", "__cxa_finalize"],
                                        "undefined_weak_symbols": ["ASystemFontIterator_open", "AFont_close",
                                                                   "__cxa_finalize"]}]}}
        declared = {"ASystemFontIterator_open": "libandroid", "AFont_close": "libandroid"}
        result = ohresolve.resolve(scan, {"AFont_close"}, declared)
        self.assertEqual(result["weak_missing"], [{"symbol": "ASystemFontIterator_open",
                                                   "importing_libraries": ["libxul.so"], "surface": "libandroid"}])
        self.assertEqual(result["missing"], [], "weak imports are never missing to the loader")

    def test_own_exports_index_and_weak_imports(self) -> None:
        cc = shutil.which("cc") or shutil.which("gcc")
        if not cc:
            self.skipTest("a C compiler is required")
        with tempfile.TemporaryDirectory(prefix="westlake-resolve-") as temp:
            index = Path(temp) / "index"
            index.mkdir()
            source = index / "board.c"
            source.write_text("int provided_by_board(void) { return 0; }\n")
            subprocess.run([cc, "-shared", "-fPIC", "-o", str(index / "libboard.so"), str(source)], check=True)
            source.unlink()
            provided, libraries = ohresolve.index_exports([index])
            self.assertEqual(libraries, ["index/libboard.so"])
            scan = {"inventory": {"elfs": [
                {"soname": "liba.so", "exported_symbols": ["shared_inside_apk"],
                 "undefined_symbols": ["provided_by_board", "nowhere", "optional_hook"],
                 "undefined_weak_symbols": ["optional_hook"]},
                {"soname": "libb.so", "exported_symbols": [],
                 "undefined_symbols": ["shared_inside_apk", "nowhere"], "undefined_weak_symbols": []}]}}
            result = ohresolve.resolve(scan, provided, {"nowhere": "libandroid"})
            self.assertEqual((result["symbols"], result["resolved"]), (3, 2), "weak imports are optional, not counted")
            self.assertEqual(result["missing"], [{"symbol": "nowhere", "importers": 2,
                                                  "importing_libraries": ["liba.so", "libb.so"], "surface": "libandroid"}])

    def test_only_the_target_abi_is_resolved(self) -> None:
        scan = {"apk": {"target_abi": "arm64-v8a"}, "inventory": {"elfs": [
            {"soname": "libx.so", "abi": "arm64-v8a", "exported_symbols": [],
             "undefined_symbols": ["memcpy"], "undefined_weak_symbols": []},
            {"soname": "libx.so", "abi": "armeabi-v7a", "exported_symbols": [],
             "undefined_symbols": ["memcpy", "__aeabi_memcpy"], "undefined_weak_symbols": []}]}}
        result = ohresolve.resolve(scan, {"memcpy"}, {})
        self.assertEqual((result["symbols"], result["resolved"], result["missing"]), (1, 1, []),
                         "a fat APK's other-ABI copies are never loaded")


if __name__ == "__main__":
    unittest.main()
