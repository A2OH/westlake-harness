"""Known answers for resolving an APK's native imports against a library index."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from westlake_gap import ohresolve


class Resolve(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
