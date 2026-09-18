from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from westlake_gap.nativeprov import (
    attribute_unresolved_imports,
    boundary_platform_types,
    classify_symbols,
    compare_runtime_capture,
    dynamic_symbol_candidates,
    find_objdump,
    identify_components,
    jump_slot_map,
    method_surface_reach,
    resolve_native_imports,
    surface_of,
)
from westlake_gap.native import recover_jni_registration_entries
from westlake_gap.scanner import read_elf


class BoundaryTypingTest(unittest.TestCase):
    def test_platform_types_are_reported_and_java_types_are_not(self) -> None:
        self.assertEqual(
            ["android/graphics/Bitmap"],
            boundary_platform_types("(JLandroid/graphics/Bitmap;)Landroid/graphics/Bitmap;"),
        )
        self.assertEqual([], boundary_platform_types("(Ljava/lang/String;Ljava/lang/String;)J"))
        self.assertEqual([], boundary_platform_types("(JIIIZ)I"))
        self.assertEqual(
            ["android/view/Surface"],
            boundary_platform_types("(JLandroid/view/Surface;)V"),
        )

    def test_surface_costs_separate_platform_from_posix(self) -> None:
        self.assertEqual(("bitmap", "platform"), surface_of("AndroidBitmap_lockPixels"))
        self.assertEqual(("gles-egl", "platform"), surface_of("glDrawArrays"))
        self.assertEqual(("thread", "portable"), surface_of("pthread_create"))
        self.assertEqual(("dynamic-load", "blind"), surface_of("dlsym"))
        self.assertIsNone(surface_of("memcpy"))

    def test_classify_groups_and_deduplicates(self) -> None:
        grouped = classify_symbols(["glDrawArrays", "glDrawArrays", "pthread_create", "memcpy"])
        self.assertEqual({"gles-egl": ["glDrawArrays"], "thread": ["pthread_create"]}, grouped)


class ComponentProvenanceTest(unittest.TestCase):
    def test_banner_alone_proves_containment(self) -> None:
        data = b"\x00\x01padding libpng version 1.6.37 - April 14, 2019\x00more"
        found = {item["component"]: item for item in identify_components(data, [], [])}
        self.assertEqual("contains", found["libpng"]["relation"])
        self.assertEqual("1.6.37", found["libpng"]["version"])

    def test_placeholder_version_is_not_reported_as_a_version(self) -> None:
        found = {item["component"]: item for item in identify_components(b"x264 - core 0000\x00", [], [])}
        self.assertEqual("contains", found["x264"]["relation"])
        self.assertIsNone(found["x264"]["version"])

    def test_defined_symbols_contain_and_imported_symbols_only_link(self) -> None:
        names = [f"mbedtls_func_{index}" for index in range(12)]
        contains = {item["component"]: item for item in identify_components(b"", names, [])}
        self.assertEqual("contains", contains["mbedTLS"]["relation"])
        self.assertEqual(12, contains["mbedTLS"]["defined_symbol_hits"])

        links = {item["component"]: item for item in identify_components(b"", [], names)}
        self.assertEqual("links-against", links["mbedTLS"]["relation"])
        self.assertEqual(0, links["mbedTLS"]["defined_symbol_hits"])

    def test_a_few_coincidental_symbols_do_not_name_a_component(self) -> None:
        self.assertEqual([], identify_components(b"", ["png_one", "png_two"], []))

    def test_dlsym_candidates_recover_runtime_resolved_apis(self) -> None:
        data = b"\x00clCreateKernel\x00clEnqueueNDRangeKernel\x00glDrawArrays\x00memcpy\x00"
        found = dynamic_symbol_candidates(data)
        self.assertEqual(["clCreateKernel", "clEnqueueNDRangeKernel"], found["opencl"])
        self.assertEqual(["glDrawArrays"], found["gles-egl"])
        self.assertNotIn("memcpy", str(found))


FIXTURE = """
#include <jni.h>
#include <android/bitmap.h>

__attribute__((noinline)) static void lock_helper(JNIEnv *env, jobject bitmap) {
    void *pixels = 0;
    AndroidBitmap_lockPixels(env, bitmap, &pixels);
    AndroidBitmap_unlockPixels(env, bitmap);
}

__attribute__((noinline)) static jint touches_platform(JNIEnv *env, jclass cls, jobject bitmap) {
    lock_helper(env, bitmap);
    return 1;
}

__attribute__((noinline)) static jint pure_compute(JNIEnv *env, jclass cls, jint value) {
    return value * 3 + 1;
}

static const JNINativeMethod kMethods[] = {
    {"touchesPlatform", "(Landroid/graphics/Bitmap;)I", (void *) touches_platform},
    {"pureCompute", "(I)I", (void *) pure_compute},
};

JNIEXPORT jint JNI_OnLoad(JavaVM *vm, void *reserved) {
    JNIEnv *env = 0;
    if ((*vm)->GetEnv(vm, (void **) &env, JNI_VERSION_1_6) != JNI_OK) {
        return JNI_ERR;
    }
    jclass cls = (*env)->FindClass(env, "fixture/Probe");
    if (cls) {
        (*env)->RegisterNatives(env, cls, kMethods, 2);
    }
    return JNI_VERSION_1_6;
}
"""


class MethodReachFixture(unittest.TestCase):
    """Known-answer fixture: one method reaches a platform surface, one provably does not."""

    def test_reach_separates_platform_coupled_from_pure_methods(self) -> None:
        clang = _find_ndk_clang()
        objdump = find_objdump()
        if not clang or not objdump:
            self.skipTest("an aarch64 NDK clang and llvm-objdump are required")

        with tempfile.TemporaryDirectory(prefix="westlake-native-prov-") as temp:
            root = Path(temp)
            source = root / "fixture.c"
            source.write_text(FIXTURE, encoding="utf-8")
            library = root / "libfixture.so"
            build = subprocess.run(
                [clang, "-O2", "-shared", "-fPIC", "-o", str(library), str(source), "-ljnigraphics"],
                capture_output=True,
                text=True,
                check=False,
            )
            if build.returncode != 0:
                self.skipTest(f"fixture did not build: {build.stderr.strip()[:200]}")

            data = library.read_bytes()
            entries, error = recover_jni_registration_entries(data)
            self.assertIsNone(error)
            by_name = {entry["name"]: entry for entry in entries}
            self.assertIn("touchesPlatform", by_name)
            self.assertIn("pureCompute", by_name)

            reach = method_surface_reach(library, entries, jump_slot_map(data))
            self.assertTrue(reach["supported"], reach.get("reason"))
            self.assertEqual("direct-bl-lower-bound", reach["basis"])
            self.assertFalse(reach["indirect_calls_followed"])
            methods = {item["name"]: item for item in reach["methods"]}

            platform = methods["touchesPlatform"]
            self.assertIn("bitmap", platform["surfaces"])
            self.assertIn("AndroidBitmap_lockPixels", platform["surfaces"]["bitmap"])
            self.assertTrue(platform["platform_coupled"])
            self.assertEqual(["android/graphics/Bitmap"], platform["boundary_platform_types"])

            pure = methods["pureCompute"]
            self.assertEqual({}, pure["surfaces"])
            self.assertFalse(pure["platform_coupled"])
            self.assertEqual([], pure["boundary_platform_types"])

            record = read_elf(path=library, abi="arm64-v8a")
            self.assertEqual("AArch64", record["machine"])
            self.assertIn("AndroidBitmap_lockPixels", record["undefined_symbols"])


def _find_ndk_clang() -> str | None:
    found = shutil.which("aarch64-linux-android21-clang")
    if found:
        return found
    for root in sorted(Path("/home/dspfac/android-sdk/ndk").glob("*/toolchains/llvm/prebuilt/*/bin"), reverse=True):
        for version in (21, 24, 26, 29):
            candidate = root / f"aarch64-linux-android{version}-clang"
            if candidate.exists():
                return str(candidate)
    return None


if __name__ == "__main__":
    unittest.main()


IMPORT_FIXTURE = """
#include <jni.h>

extern jint westlake_fixture_present(jint value);
extern jint westlake_fixture_absent(jint value);

__attribute__((noinline)) static jint calls_absent(JNIEnv *env, jclass cls, jint value) {
    return westlake_fixture_absent(value);
}

__attribute__((noinline)) static jint calls_present(JNIEnv *env, jclass cls, jint value) {
    return westlake_fixture_present(value);
}

static const JNINativeMethod kMethods[] = {
    {"callsAbsent", "(I)I", (void *) calls_absent},
    {"callsPresent", "(I)I", (void *) calls_present},
};

JNIEXPORT jint JNI_OnLoad(JavaVM *vm, void *reserved) {
    JNIEnv *env = 0;
    if ((*vm)->GetEnv(vm, (void **) &env, JNI_VERSION_1_6) != JNI_OK) {
        return JNI_ERR;
    }
    jclass cls = (*env)->FindClass(env, "fixture/Imports");
    if (cls) {
        (*env)->RegisterNatives(env, cls, kMethods, 2);
    }
    return JNI_VERSION_1_6;
}
"""

SYSTEM_FIXTURE = """
int westlake_fixture_present(int value) { return value + 1; }
"""


class NativeImportResolutionFixture(unittest.TestCase):
    """Known answer: one import the runtime provides, one it does not."""

    def test_missing_import_becomes_one_finding_naming_its_reaching_method(self) -> None:
        clang = _find_ndk_clang()
        if not clang or not find_objdump():
            self.skipTest("an aarch64 NDK clang and llvm-objdump are required")

        with tempfile.TemporaryDirectory(prefix="westlake-native-import-") as temp:
            root = Path(temp)
            app = _build(clang, root, "libapp.so", IMPORT_FIXTURE)
            system = _build(clang, root, "libwestlakefixture.so", SYSTEM_FIXTURE)
            if not app or not system:
                self.skipTest("fixture libraries did not build")

            app_record = read_elf(path=app, abi="arm64-v8a")
            system_record = read_elf(path=system, abi="arm64-v8a")
            self.assertIn("westlake_fixture_absent", app_record["undefined_symbols"])
            self.assertIn("westlake_fixture_present", system_record["exported_symbols"])

            system_exports = {
                symbol: [{"elf": system_record["name"], "symbol": symbol}]
                for symbol in system_record["exported_symbols"]
            }
            resolved = {
                item["symbol"]: item
                for item in resolve_native_imports([app_record], {}, {}, system_exports, True)
            }

            self.assertEqual("C0", resolved["westlake_fixture_present"]["classification"])
            self.assertEqual("PLATFORM_SYSTEM", resolved["westlake_fixture_present"]["provider_scope"])

            missing = resolved["westlake_fixture_absent"]
            self.assertEqual("N-C1-candidate", missing["classification"])
            self.assertEqual("no-provider", missing["state"])
            self.assertEqual(
                ["N-C1-candidate"],
                sorted({item["classification"] for item in resolved.values() if item["classification"] != "C0"}),
            )

            attributed = attribute_unresolved_imports(app, app_record, ["westlake_fixture_absent"])
            self.assertEqual(["callsAbsent"], attributed["westlake_fixture_absent"])

    def test_absence_is_not_claimed_without_a_system_index(self) -> None:
        record = {
            "name": "lib/arm64-v8a/libapp.so",
            "sha256": "0" * 64,
            "undefined_symbols": ["AndroidBitmap_lockPixels"],
            "undefined_weak_symbols": [],
        }
        resolved = resolve_native_imports([record], {}, {}, {}, False)
        self.assertEqual("CU", resolved[0]["classification"])
        self.assertEqual("runtime-system-index-unavailable", resolved[0]["state"])

    def test_weak_undefined_symbols_are_optional_not_missing(self) -> None:
        record = {
            "name": "lib/arm64-v8a/libapp.so",
            "sha256": "0" * 64,
            "undefined_symbols": ["__cxa_thread_atexit_impl"],
            "undefined_weak_symbols": ["__cxa_thread_atexit_impl"],
        }
        resolved = resolve_native_imports([record], {}, {}, {}, True)
        self.assertEqual("N-C5-candidate", resolved[0]["classification"])
        self.assertTrue(resolved[0]["weak_only"])


def _build(clang: str, root: Path, name: str, source_text: str) -> Path | None:
    source = root / f"{name}.c"
    source.write_text(source_text, encoding="utf-8")
    target = root / name
    build = subprocess.run(
        [clang, "-O2", "-shared", "-fPIC", "-nostdlib", "-Wl,--no-undefined-version",
         "-o", str(target), str(source)],
        capture_output=True,
        text=True,
        check=False,
    )
    return target if build.returncode == 0 and target.exists() else None


class RuntimeCaptureComparisonTest(unittest.TestCase):
    """The capture's value is the difference, so both directions are asserted."""

    SURFACE = {
        "libraries": [
            {"library": "libknown.so", "method_reach": {"methods": [
                {"name": "exercised", "signature": "(I)I"},
                {"name": "neverRun", "signature": "(J)V"},
            ]}},
            {"library": "libopaque.so"},
        ]
    }
    CAPTURE = [
        {"type": "registerNatives", "clazz": "com/example/Known", "methods": [
            {"name": "exercised", "signature": "(I)I", "lib": "/data/app/x/lib/arm64/libknown.so"},
        ]},
        {"type": "registerNatives", "clazz": "?", "methods": [
            {"name": "hidden", "signature": "()V", "lib": "libopaque.so"},
        ]},
        {"type": "registerNatives", "clazz": "?", "methods": [
            {"name": "downloaded", "signature": "()V", "lib": "libnotinapk.so"},
        ]},
        {"type": "dlopen", "path": "/data/data/pkg/files/hotfix-root/install/1/oat/arm64/patch.odex", "ok": True},
        {"type": "dlopen", "path": "libc.so", "ok": True},
        {"type": "dlsym", "symbol": "Java_com_example_Known_missing", "resolved": False},
        {"type": "dlsym", "symbol": "dl_iterate_phdr", "resolved": True},
    ]

    def test_both_directions_of_the_difference(self) -> None:
        diff = compare_runtime_capture(self.CAPTURE, self.SURFACE)
        self.assertEqual(2, diff["static"]["methods"])
        self.assertEqual(3, diff["runtime"]["methods"])
        self.assertEqual(3, diff["runtime"]["registration_tables"])
        self.assertEqual(2, diff["runtime_only_methods"])    # hidden + downloaded
        self.assertEqual(1, diff["static_only_methods"])     # neverRun
        self.assertEqual(4, diff["union_methods"])

    def test_library_origin_is_separated(self) -> None:
        diff = compare_runtime_capture(self.CAPTURE, self.SURFACE)
        self.assertEqual([{"library": "libnotinapk.so", "methods": 1}], diff["libraries_absent_from_apk"])
        self.assertEqual([{"library": "libopaque.so", "methods": 1}], diff["libraries_opaque_to_static"])

    def test_dlsym_failures_and_runtime_code_objects_are_kept(self) -> None:
        diff = compare_runtime_capture(self.CAPTURE, self.SURFACE)
        self.assertEqual(["Java_com_example_Known_missing"], diff["dlsym_unresolved"])
        self.assertEqual(1, diff["dlsym_resolved_count"])
        self.assertEqual(1, len(diff["runtime_loaded_code_objects"]))
        self.assertIn("patch.odex", diff["runtime_loaded_code_objects"][0])

    def test_real_capture_matches_the_published_report(self) -> None:
        root = Path(__file__).resolve().parent.parent
        surface = root / "benchmark/2026-08-23-toutiao/native-analysis/native-surface.json"
        captures = sorted((root / "benchmark/2026-08-23-toutiao/runtime-evidence/android-baseline").glob("capture-*.jsonl"))
        if not surface.exists() or not captures:
            self.skipTest("Toutiao native-analysis evidence is not present")
        rows = []
        for path in captures:
            with path.open(encoding="utf-8") as stream:
                rows.extend(json.loads(line) for line in stream if line.strip())
        diff = compare_runtime_capture(rows, json.loads(surface.read_text(encoding="utf-8")))
        self.assertEqual(1340, diff["static"]["methods"])
        self.assertEqual(1157, diff["runtime"]["methods"])
        self.assertEqual(280, diff["runtime_only_methods"])
        self.assertEqual(463, diff["static_only_methods"])
        self.assertEqual(5, len(diff["libraries_absent_from_apk"]))
        self.assertEqual(3, len(diff["libraries_opaque_to_static"]))
