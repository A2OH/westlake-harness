import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "tells", Path(__file__).resolve().parents[1] / "device" / "tells.py")
tells = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(tells)

CHILD = "[AppSpawnX] [CHILD] native stderr redirected to /data/service/el1/public/appspawnx/adapter_child_{pid}.stderr"


def hilog(pid: str, message: str, tid: str = "200") -> str:
    return f"11-07 13:50:36.186  {pid}  {tid} I C02d11/DfxSignalHandler: {message}"


class HowAppsEnded(unittest.TestCase):
    """Known answers for the ends of 2026-11-07, as their logs showed them."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.logs = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def app(self, name: str, stderr: list[str], hilog_lines: list[str] = (), died_at=1.0, died_after=None) -> dict:
        (self.logs / f"{name}.stderr").write_text("\n".join(stderr) + "\n")
        (self.logs / f"{name}.hilog").write_text("\n".join(hilog_lines) + "\n")
        explore = self.logs / f"{name}.explore"
        explore.mkdir()
        (explore / "explore.json").write_text(json.dumps(
            {"seconds": 5, "screens": 1, "died_at": died_at, "died_after": died_after}))
        return tells.one_app(self.logs, name)

    def test_a_system_exit_names_the_app_frame_that_called_it(self) -> None:
        r = self.app("hk-outlook", [CHILD.format(pid="100"),
                                    '[WESTLAKE-EXIT] the process is exiting (System.exit or the last thread); '
                                    'called on thread "main"',
                                    "\tat java.lang.Runtime.exit(Runtime.java:1)",
                                    "\tat java.lang.System.exit(System.java:1)",
                                    "\tat com.example.util.OSUtil.kill(OSUtil.java:9)"])
        self.assertEqual(r["end"]["kind"], "java-exit")
        self.assertIn("com.example.util.OSUtil.kill", r["end"]["detail"])

    def test_a_self_signal_is_not_a_crash(self) -> None:
        r = self.app("hk-excel", [CHILD.format(pid="101"),
                                  "java.lang.Throwable: [WESTLAKE-KILL] the process sends itself signal 9",
                                  "\tat android.os.Process.sendSignal(Native Method)",
                                  "\tat android.os.Process.killProcess(Unknown Source:2)",
                                  "\tat com.example.office.Host$r.run(Host.java:3)"])
        self.assertEqual(r["end"]["kind"], "self-signal")
        self.assertIn("com.example.office.Host$r.run", r["end"]["detail"])

    def test_back_on_the_last_screen_notes_a_signal_during_the_exit(self) -> None:
        r = self.app("hk-tutor", [CHILD.format(pid="102")],
                     [hilog("102", "DFX_SignalHandler :: signo(6), pid(102), processName(x), threadName(mali-cmar-backe).")],
                     died_after="back")
        self.assertEqual(r["end"]["kind"], "explorer-back")
        self.assertIn("signal 6 on thread mali-cmar-backe", r["end"]["detail"])

    def test_a_signal_whose_dump_timed_out(self) -> None:
        r = self.app("hk-wechat", [CHILD.format(pid="103")],
                     [hilog("103", "DFX_SignalHandler :: signo(11), pid(103), processName(x), threadName(wc_srvinit_0)."),
                      hilog("103", "waitpid 999 timeout")])
        self.assertEqual(r["end"]["kind"], "dump-timeout")

    def test_another_process_signal_is_not_this_apps(self) -> None:
        r = self.app("hk-quiet", [CHILD.format(pid="104")],
                     [hilog("555", "DFX_SignalHandler :: signo(11), pid(555), processName(y), threadName(t).")])
        self.assertEqual(r["end"]["kind"], "silent")

    def test_a_protector_trap_is_still_silent_but_says_so(self) -> None:
        r = self.app("hk-scanner", [CHILD.format(pid="105")],
                     ["11-08 01:11:52.507 105 106 W C03f07/MUSL-SIGCHAIN: signal_chain_handler call usr sigaction "
                      "for signal: 4 sig_action.sa_sigaction=7dd7999190"])
        self.assertEqual(r["end"]["kind"], "silent")
        self.assertIn("own handler took signal 4", r["end"]["detail"])

    def test_the_loader_reason_is_a_failed_tell_and_a_cause_candidate(self) -> None:
        r = self.app("hk-amap", [CHILD.format(pid="106"),
                                 "[WESTLAKE-LOADER] libamaptbt.so by name failed (Error relocating x: "
                                 "__system_property_set: symbol not found); opening the path",
                                 "[UNCAUGHT] thread='launch_async' java.lang.UnsatisfiedLinkError: x"])
        self.assertEqual(r["end"]["kind"], "uncaught")
        load = [t for t in r["tells"] if t["contract"] == "load:libamaptbt.so"]
        self.assertEqual(load[0]["answer"], "failed")
        self.assertIn("__system_property_set", tells.cause_candidate(r, set()))

    def test_window_session_stubs_and_stand_ins_are_tells(self) -> None:
        r = self.app("hk-video", [CHILD.format(pid="108")],
                     ["11-08 08:39:21.753 108 120 I C00f00/OH_WSAdapter: [STUB] getWindowId - OH accessibility "
                      "window ID not mapped",
                      "11-08 09:39:21.753 108 120 I C00f00/OH_WSAdapter: [STAND-IN] getWindowId - the window's id, "
                      "held until the window is removed"],
                     died_at=None)
        answers = {(t["contract"], t["answer"], t["fidelity"]) for t in r["tells"]}
        self.assertIn(("binder:IWindowSession.getWindowId", "stub", "unknown"), answers)
        self.assertIn(("binder:IWindowSession.getWindowId", "fixed", "stand-in"), answers)

    def test_a_running_app_has_no_end(self) -> None:
        r = self.app("hk-alive", [CHILD.format(pid="107"), '[OHServiceManager] getService("isub") → null (stub)'],
                     died_at=None)
        self.assertFalse(r["ended"])
        self.assertEqual(r["tells"][0]["contract"], "svc:isub")


if __name__ == "__main__":
    unittest.main()
