import importlib.util
import re
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "score_first_blockers", Path(__file__).resolve().parents[1] / "scripts" / "score_first_blockers.py")
score = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(score)

ROWS = [{"id": "svc:usb", "verdict": "null", "aosp_contract": "Landroid/hardware/usb/UsbManager; needs binder(s) ['usb']",
         "throwing_sites": ["app.fayaz.otgmaster.MainActivity.onCreate"]},
        {"id": "svc:device_policy", "verdict": "null",
         "aosp_contract": "Landroid/app/admin/DevicePolicyManager; needs binder(s) ['device_policy']",
         "throwing_sites": ["app.clauncher.ui.HomeFragment.H"]}]


class RootCauseScoring(unittest.TestCase):
    def test_a_kotlin_cast_names_the_manager(self) -> None:
        cause = {"exception": "NullPointerException",
                 "message": "null cannot be cast to non-null type android.hardware.usb.UsbManager"}
        rows = score.candidate_rows("app-framework", "start activity: NullPointerException", ROWS, cause)
        self.assertEqual([r["id"] for r in rows], ["svc:usb"])

    def test_a_compiled_null_check_is_found_by_its_frame(self) -> None:
        cause = {"exception": "NullPointerException", "frame": "app.clauncher.ui.HomeFragment.H",
                 "message": "Attempt to invoke InvokeType(2) method 'java.lang.Class java.lang.Object.getClass()' "
                            "on a null object reference"}
        rows = score.candidate_rows("app-framework", "start activity: InflateException", ROWS, cause)
        self.assertEqual([r["id"] for r in rows], ["svc:device_policy"])
        self.assertEqual(score.candidate_rows("app-framework", "x", ROWS, dict(cause, frame="other.Class.m")), [],
                         "a null check no service row lists is not named")

    def test_other_exceptions_stay_unscorable(self) -> None:
        cause = {"exception": "ArithmeticException", "message": "divide by zero", "frame": "a.b.c"}
        self.assertIsNone(score.candidate_rows("app-framework", "start activity: ArithmeticException", ROWS, cause))


class SymptomScoring(unittest.TestCase):
    def test_an_app_exception_a_row_lists_as_its_symptom_is_named_by_it(self) -> None:
        rows = ROWS + [{"id": "perm:host:ohos.permission.MICROPHONE", "verdict": "missing",
                        "symptoms": ["uninitialized AudioRecord"]}]
        blocker = "start activity: IllegalStateException: startRecording() called on an uninitialized AudioRecord."
        named = score.candidate_rows("app-framework", blocker, rows)
        self.assertEqual([r["id"] for r in named], ["perm:host:ohos.permission.MICROPHONE"])
        self.assertEqual(score.outcome_of(named), "named")
        self.assertIsNone(score.candidate_rows("app-framework", blocker, ROWS), "no row lists it: unscorable")


class SelfFinishScoring(unittest.TestCase):
    def test_an_activity_closing_itself_needs_the_row_for_what_it_asked(self) -> None:
        rows = ROWS + [{"id": "am:task-root", "verdict": "missing"}]
        blocker = "its last activity finished itself 0 ms after resuming, and nothing replaced it"
        self.assertEqual([r["id"] for r in score.candidate_rows("self-finish", blocker, rows)], ["am:task-root"])
        self.assertEqual(score.candidate_rows("self-finish", blocker, ROWS), [], "no such row: a blind spot")

    def test_a_device_answer_counts_for_a_service_the_app_called_before_it_left(self) -> None:
        """Fossify Messages: no SMS role on a board with no telephony, a toast, and the activity closes."""
        role = {"id": "svc:role", "verdict": "supplied", "device_answer": "Roles on a board with no telephony."}
        rows = [{"id": "am:task-root", "verdict": "supplied"}, role]
        blocker = "its last activity finished itself 326 ms after resuming, and nothing replaced it"
        found = score.candidate_rows("self-finish", blocker, rows, finished={"local_services": ["role", "notification"]})
        self.assertEqual([r["id"] for r in found], ["am:task-root", "svc:role"])
        self.assertEqual(score.outcome_of(found), "device")
        found = score.candidate_rows("self-finish", blocker, rows, finished={"local_services": ["notification"]})
        self.assertEqual((score.outcome_of(found), [r["id"] for r in found]), ("supplied", ["am:task-root"]),
                         "a device answer the app never asked for is not its reason")
        own = {"id": "am:own-implicit-intents", "verdict": "missing"}
        self.assertEqual(score.outcome_of(score.candidate_rows("self-finish", blocker, rows + [own])), "named")


class NoFrameScoring(unittest.TestCase):
    def test_an_activity_that_never_drew_needs_what_holds_its_draws(self) -> None:
        """Linphone: its own onPostCreate releases its draws, and the provider never called it."""
        blocker = "the activity resumed 1.5 s after start and drew no frame"
        rows = ROWS + [{"id": "am:post-create", "verdict": "missing"}]
        found = score.candidate_rows("no-frame", blocker, rows)
        self.assertEqual(([r["id"] for r in found], score.outcome_of(found)), (["am:post-create"], "named"))
        self.assertEqual(score.outcome_of(score.candidate_rows("no-frame", blocker, ROWS)), "not-named")


class WindowBuffersScoring(unittest.TestCase):
    def test_a_window_with_no_buffers_needs_the_geometry_row(self) -> None:
        """anarchre, diesimu: SDL's geometry reached OH as a 0x0 buffer size."""
        blocker = "13915 buffer requests on one of its windows failed (ret 50002000)"
        rows = ROWS + [{"id": "window:buffers-geometry", "verdict": "missing"}]
        found = score.candidate_rows("window-buffers", blocker, rows)
        self.assertEqual(([r["id"] for r in found], score.outcome_of(found)), (["window:buffers-geometry"], "named"))
        self.assertEqual(score.outcome_of(score.candidate_rows("window-buffers", blocker, ROWS)), "not-named")


class RefusalScoring(unittest.TestCase):
    def test_a_stall_after_a_service_refused_a_call_is_named_by_its_row(self) -> None:
        rows = ROWS + [{"id": "svc:user-unanswered", "verdict": "missing", "symptoms": ["OH user service does not implement"]}]
        refusals = ["OH user service does not implement getProfileIds"]
        named = score.candidate_rows("stall", "main thread idle in its message loop at x", rows, refusals=refusals)
        self.assertEqual([r["id"] for r in named], ["svc:user-unanswered"])
        self.assertIsNone(score.candidate_rows("stall", "main thread idle in its message loop at x", rows),
                          "no refusal logged: a stall names nothing")


class DlsymScoring(unittest.TestCase):
    def test_a_name_a_lookup_by_handle_missed_is_named_by_the_row_listing_it(self) -> None:
        rows = ROWS + [{"id": "gl:gles3-by-handle", "verdict": "missing",
                        "symbols": ["glBindVertexArray", "glGenVertexArrays"]}]
        blocker = "dlsym found no glGenVertexArrays in /system/lib64/ndk/libGLESv2.so"
        self.assertEqual(score.platform_key("native-symbols", blocker), ("symbol", "glGenVertexArrays"))
        self.assertEqual([r["id"] for r in score.candidate_rows("native-symbols", blocker, rows)],
                         ["gl:gles3-by-handle"])
        self.assertEqual(score.platform_key("native-loading", "Error relocating /x/libgojni.so: AInputEvent_getDeviceId: "
                                            "symbol not found"), ("symbol", "AInputEvent_getDeviceId"))


class NullServiceScoring(unittest.TestCase):
    def test_a_null_platform_service_names_its_row(self) -> None:
        """wormhole2 never drew after Build.getSerial's NPE; the launchers stalled on LauncherApps."""
        rows = ROWS + [{"id": "svc:device_identifiers", "verdict": "null",
                        "aosp_contract": "Landroid/os/Build;.getSerial needs binder(s) ['device_identifiers'] "
                                         "(IDeviceIdentifiersPolicyService)"},
                       {"id": "svc:launcherapps", "verdict": "null"}]
        found = score.candidate_rows("no-frame", "the activity resumed 0.9 s after start and drew no frame", rows,
                                     null_services=["android.os.IDeviceIdentifiersPolicyService"])
        self.assertEqual(([r["id"] for r in found], score.outcome_of(found)), (["svc:device_identifiers"], "named"))
        found = score.candidate_rows("stall", "main thread idle", rows, null_services=["android.content.pm.ILauncherApps"])
        self.assertEqual([r["id"] for r in found], ["svc:launcherapps"])
        self.assertIsNone(score.candidate_rows("stall", "main thread idle", rows), "no evidence: unscorable as before")


class NativeCrashScoring(unittest.TestCase):
    def test_a_row_about_a_library_in_the_crash_names_it(self) -> None:
        """Waze aborted in libwaze.so (loaded from the shim's init copy); its constructors were dropped."""
        dump = {"frames": [
            {"path": "/system/lib/ld-musl-aarch64.so.1", "library": "ld-musl-aarch64.so.1", "symbol": "abort+20"},
            {"path": "/data/local/tmp/asx/lib/arm64-v8a/.libwaze.so.westlake-init.24312.0", "library": "libwaze.so"}]}
        rows = [{"id": "load:packed-init-array", "verdict": "missing", "libraries": ["libwaze.so"]},
                {"id": "egl:by-handle", "verdict": "missing", "libraries": ["lib/arm64-v8a/libSDL2.so"]}]
        found = score.candidate_rows("native-crash", "SIGABRT on thread Native Thread: aborted from libwaze.so",
                                     rows, dump=dump)
        self.assertEqual([r["id"] for r in found], ["load:packed-init-array"])
        sdl = {"frames": [{"path": "/data/local/tmp/asx/lib/arm64-v8a/libSDL2.so", "library": "libSDL2.so"}]}
        self.assertEqual([r["id"] for r in score.crash_rows(sdl, rows)], ["egl:by-handle"])
        mali = {"frames": [{"path": "/vendor/lib64/chipsetsdk/libGLES_mali.z.so", "library": "libGLES_mali.z.so"}]}
        self.assertIsNone(score.crash_rows(mali, rows), "no app frame: unscorable")

    def test_a_row_about_one_call_needs_that_call_in_the_crash(self) -> None:
        handle = {"id": "abi:thread-handle-order", "verdict": "missing", "libraries": ["libvcbasekit.so", "libppsspp_jni.so"],
                  "crash_symbols": "^pthread_"}
        tiktok = {"frames": [{"path": "/system/lib/ld-musl-aarch64.so.1", "library": "ld-musl-aarch64.so.1",
                              "symbol": "pthread_setname_np+92"},
                             {"path": "/data/local/tmp/asx/lib/arm64-v8a/libvcbasekit.so", "library": "libvcbasekit.so"}]}
        ppsspp = {"frames": [{"path": "/data/local/tmp/asx/libhwui.so", "library": "libhwui.so"},
                             {"path": "/data/local/tmp/asx/lib/arm64-v8a/libppsspp_jni.so", "library": "libppsspp_jni.so"}]}
        self.assertEqual([r["id"] for r in score.crash_rows(tiktok, [handle])], ["abi:thread-handle-order"])
        self.assertIsNone(score.crash_rows(ppsspp, [handle]))
        # PPSSPP's crash runs in libhwui's copy of its own symbols: the interposition row names it.
        interposed = {"id": "load:interposed-by-runtime", "verdict": "missing", "libraries": ["libppsspp_jni.so"],
                      "crash_libraries": ["libhwui.so", "libpng.so"]}
        self.assertEqual([r["id"] for r in score.crash_rows(ppsspp, [handle, interposed])], ["load:interposed-by-runtime"])
        own = {"frames": [{"path": "/data/local/tmp/asx/lib/arm64-v8a/libppsspp_jni.so", "library": "libppsspp_jni.so"}]}
        self.assertIsNone(score.crash_rows(own, [interposed]), "a crash in its own code is not interposition")

    def test_a_weak_import_names_only_a_call_through_null(self) -> None:
        weak = {"id": "ndk:weak-api", "verdict": "missing", "libraries": ["libxul.so"], "crash_kinds": ["null-call"]}
        frames = [{"path": "/data/local/tmp/asx/lib/arm64-v8a/libxul.so", "library": "libxul.so"}]
        self.assertEqual([r["id"] for r in score.crash_rows({"kind": "null-call", "frames": frames}, [weak])],
                         ["ndk:weak-api"])
        self.assertIsNone(score.crash_rows({"kind": "heap", "frames": frames}, [weak]))


if __name__ == "__main__":
    unittest.main()
