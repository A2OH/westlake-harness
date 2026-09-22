"""Known answers for the deployment check: missing libraries and binaries older than their source."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from westlake_gap import deploy


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class DeploymentCheck(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="westlake-deploy-")
        root = Path(self.temp.name)
        tree = root / "westlake"
        _write(tree / "framework/window/java/Keyboard.java",
               'class Keyboard { static { System.loadLibrary("helper"); } }')
        _write(tree / "framework/core/jni/helper.cpp", "\n".join([
            'void a() { dlopen("libsys.so", RTLD_NOW); dlopen("libgone.so", RTLD_NOW); }',
            'void b() { log("[WESTLAKE-OLD] original behaviour line %d\\n", 1); }',
            'void c() { log("[WESTLAKE-NEW] behaviour added after the build %s\\n", x); }',
            '// log("[WESTLAKE-CMT] quoted in a comment, never compiled");',
        ]))
        # Listed for the same library, compiled into another one: none of its strings is present.
        _write(tree / "framework/core/jni/elsewhere.cpp",
               'void d() { log("[WESTLAKE-ELSE] compiled into a different library\\n"); }')
        _write(tree / "framework/tests/Only.java", 'class Only { static { System.loadLibrary("testonly"); } }')
        _write(tree / "tools/build_native.py", "entries = [\n"
               "    ('libhelper.so', ROOT / 'framework/core/jni/helper.cpp', []),\n]\n")
        _write(tree / "native/libraries.json", json.dumps({"libraries": {"libhelper.so": {"sources": [
            "westlake/framework/core/jni/helper.cpp", "westlake/framework/core/jni/elsewhere.cpp"]}}}))
        binary = b"\x7fELF...[WESTLAKE-OLD] original behaviour line %d\n..."
        staged = root / "staged"
        _write(staged / "libhelper.so", "")
        (staged / "libhelper.so").write_bytes(binary)
        self.report = {"files": {"libhelper.so": {"sha256": hashlib.sha256(binary).hexdigest()}}}
        _write(root / "board.txt", "/system/lib64/ndk/libsys.so\n")
        self.root, self.tree, self.staged = root, tree, staged

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_missing_and_older_than_source(self) -> None:
        # build_native.py maps libhelper.so to helper.cpp alone; the index adds elsewhere.cpp.
        mapping = deploy.artifact_sources(self.tree, {"artifacts": {}})
        self.assertEqual(mapping["libhelper.so"], ["framework/core/jni/helper.cpp"])

        result = deploy.check(self.tree, [self.report], [self.staged], self.root / "board.txt")
        status = {row["name"]: row["status"] for row in result["loads"]}
        self.assertEqual(status["libhelper.so"], "staged", "System.loadLibrary(\"helper\") is libhelper.so")
        self.assertEqual(status["libsys.so"], "board")
        self.assertEqual(result["summary"]["missing"], ["libgone.so"])
        self.assertNotIn("libtestonly.so", status, "tests do not count")

        fresh = {row["artifact"]: row for row in result["freshness"]}["libhelper.so"]
        self.assertEqual(fresh["verdict"], "older than source")
        self.assertEqual([a["string"] for a in fresh["absent_examples"]],
                         ["[WESTLAKE-NEW] behaviour added after the build"])
        self.assertNotIn("[WESTLAKE-CMT]", json.dumps(fresh), "a string in a comment is not source")

    def test_file_compiled_elsewhere_is_not_stale(self) -> None:
        mapping = {"libhelper.so": ["framework/core/jni/elsewhere.cpp"]}
        rows = deploy.freshness(self.tree, {"libhelper.so": self.report["files"]["libhelper.so"]["sha256"]},
                                [self.staged], mapping)
        self.assertEqual(rows[0]["verdict"], "unverified", "none of its strings: not compiled into this binary")


if __name__ == "__main__":
    unittest.main()
