"""Known answers for Java APIs that native code calls back into through JNIEnv.

The fixture library names, as strings, exactly what FindClass/GetMethodID/GetStaticFieldID would be
passed. Every state must come out right, and so must the four false-positive traps the first
runs fell into: an inherited constructor (constructors are not inherited), an SDK stub's
package-private placeholder constructor, an empty body in an upstream library jar, and a constant
body in AOSP-compiled framework.jar.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from test_known_answers import _run, _write
from westlake_gap.nativeupcall import library_upcalls, resolve_upcalls
from westlake_gap.platformapi import load_platform_members
from westlake_gap.scanner import RuntimeResolver

FIXTURE_C = r"""
const char *const upcalls[] = {
    "android/os/Handler", "post", "(Ljava/lang/Runnable;)Z",
    "android/net/TrafficStats", "setThreadStatsTag", "(I)V", "getTotalRxBytes", "()J",
    "android/net/wifi/WifiInfo", "getSSID", "()Ljava/lang/String;",
    "android/app/ActivityThread", "currentApplication", "()Landroid/app/Application;",
    "android/os/Build$VERSION", "SDK_INT",
    "android/os/Derived", "<init>", "()V",
    "android/os/Stubby",
    "android/os/Streamy", "close",
    "android/os/Framed", "getMax", "()F",
};
"""

REFERENCE = {
    "android/os/Handler.java": "package android.os; public class Handler { public final boolean post(Runnable r) { return false; } }",
    "android/net/TrafficStats.java": """package android.net; public class TrafficStats {
        public static void setThreadStatsTag(int t) {} public static long getTotalRxBytes() { return 0; } }""",
    "android/net/wifi/WifiInfo.java": "package android.net.wifi; public class WifiInfo { public String getSSID() { return null; } }",
    "android/os/Build.java": "package android.os; public class Build { public static class VERSION { public static final int SDK_INT = 0; } }",
    "android/os/Base.java": "package android.os; public class Base { public Base() {} }",
    "android/os/Derived.java": "package android.os; public class Derived extends Base { public Derived(int x) {} }",
    "android/os/Stubby.java": "package android.os; public class Stubby { Stubby() {} }",
    "android/os/Streamy.java": "package android.os; public class Streamy { public void close() {} }",
    "android/os/Framed.java": "package android.os; public class Framed { public static float getMax() { return 1f; } }",
}


def _runtime() -> dict:
    def cls(artifact, methods=(), fields=(), hollow=(), sup="Ljava/lang/Object;"):
        return {"artifact": artifact, "super": sup, "interfaces": [], "methods": list(methods),
                "fields": list(fields), "hollow_methods": list(hollow)}
    return {"runtime_lock_id": "fixture", "classes": {
        "Landroid/os/Handler;": cls("framework.jar", ["post(Ljava/lang/Runnable;)Z"]),
        "Landroid/net/TrafficStats;": cls("adapter-mainline-stubs.jar", ["setThreadStatsTag(I)V"], hollow=["setThreadStatsTag(I)V"]),
        "Landroid/app/ActivityThread;": cls("framework.jar", ["currentApplication()Landroid/app/Application;"]),
        "Landroid/os/Build$VERSION;": cls("framework.jar", fields=["SDK_INT:I"]),
        "Landroid/os/Base;": cls("framework.jar", ["<init>()V"]),
        "Landroid/os/Derived;": cls("framework.jar", ["<init>(I)V"], sup="Landroid/os/Base;"),
        "Landroid/os/Stubby;": cls("framework.jar"),
        # An empty body in an upstream library jar is upstream behaviour, not a placeholder.
        "Landroid/os/Streamy;": cls("core-oj.jar", ["close()V"], hollow=["close()V"]),
        # A constant body in framework.jar may be AOSP's own: a candidate, not evidence.
        "Landroid/os/Framed;": cls("framework.jar", ["getMax()F"], hollow=["getMax()F"]),
    }}


class NativeUpcalls(unittest.TestCase):
    def test_states_and_false_positive_traps(self) -> None:
        cc, javac = shutil.which("cc") or shutil.which("gcc"), shutil.which("javac")
        if not cc or not javac:
            self.skipTest("a C compiler and javac are required")
        with tempfile.TemporaryDirectory(prefix="westlake-upcalls-") as temp:
            root = Path(temp)
            _write(root / "fixture.c", FIXTURE_C)
            library = root / "libfixture.so"
            subprocess.run([cc, "-shared", "-fPIC", "-O0", "-o", str(library), str(root / "fixture.c")],
                           check=True, capture_output=True, timeout=60)
            for name, text in REFERENCE.items():
                _write(root / "ref" / name, text)
            classes = root / "classes"
            classes.mkdir()
            _run(javac, "--release", "8", "-d", str(classes), *map(str, (root / "ref").rglob("*.java")))
            jar = root / "android.jar"
            with zipfile.ZipFile(jar, "w") as archive:
                for path in classes.rglob("*.class"):
                    archive.write(path, str(path.relative_to(classes)))

            reference = load_platform_members(jar)
            runtime = _runtime()
            result = resolve_upcalls(library_upcalls(library.read_bytes(), reference, runtime),
                                     RuntimeResolver(runtime), reference)
            state = {(m["owner"], m["name"], m["descriptor"]): m["state"] for m in result["members"]}

            self.assertEqual(state[("android/os/Handler", "post", "(Ljava/lang/Runnable;)Z")], "present")
            self.assertEqual(state[("android/net/TrafficStats", "setThreadStatsTag", "(I)V")], "hollow",
                             "an empty body in a Westlake stub jar is a placeholder")
            self.assertEqual(state[("android/net/TrafficStats", "getTotalRxBytes", "()J")], "missing")
            self.assertEqual(result["class_states"]["android/net/wifi/WifiInfo"], "missing")
            self.assertEqual(state[("android/net/wifi/WifiInfo", "getSSID", "()Ljava/lang/String;")], "class-missing")
            self.assertEqual(state[("android/app/ActivityThread", "currentApplication", "()Landroid/app/Application;")],
                             "present", "hidden APIs are enumerated from the runtime, not the public SDK")
            self.assertEqual(state[("android/os/Build$VERSION", "SDK_INT", "I")], "present")
            self.assertEqual(state[("android/os/Streamy", "close", "()V")], "present",
                             "an empty body in an upstream library jar is not a gap")
            self.assertEqual(state[("android/os/Framed", "getMax", "()F")], "hollow-candidate",
                             "a constant body in AOSP-compiled framework.jar is only a candidate")
            self.assertNotIn(("android/os/Derived", "<init>", "()V"), state, "constructors are not inherited")
            self.assertFalse([k for k in state if k[0] == "android/os/Stubby"],
                             "an SDK stub's package-private placeholder constructor is not API")
            self.assertIn("android/app/Application", result["boundary_types"])


if __name__ == "__main__":
    unittest.main()
