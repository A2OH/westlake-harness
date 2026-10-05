import importlib.util
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


if __name__ == "__main__":
    unittest.main()
