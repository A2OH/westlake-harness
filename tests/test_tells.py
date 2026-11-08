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

    def app(self, name: str, stderr: list[str], hilog_lines: list[str] = (), died_at=1.0, died_after=None,
            screens: int = 1, crash: list[str] = ()) -> dict:
        (self.logs / f"{name}.stderr").write_text("\n".join(stderr) + "\n")
        (self.logs / f"{name}.hilog").write_text("\n".join(hilog_lines) + "\n")
        if crash:
            (self.logs / f"{name}.cppcrash").write_text("\n".join(crash) + "\n")
        explore = self.logs / f"{name}.explore"
        explore.mkdir()
        (explore / "explore.json").write_text(json.dumps(
            {"seconds": 5, "screens": screens, "died_at": died_at, "died_after": died_after}))
        return tells.one_app(self.logs, name)

    PAIRIP_START = [CHILD.format(pid="110"),
                    "[SOURCE-NATIVE-LOAD] path=/data/local/tmp/asx/lib/arm64-v8a/libpairipcore.so search=/x",
                    "[WESTLAKE-REAP] child 111 exited(0)",
                    "Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR) fault addr 0x7ef5fa2000",
                    "Backtrace:", ""]

    def test_a_crash_right_after_the_protector_loaded_names_it(self) -> None:
        # Floze, 2026-11-08: PairIP's VM crashed before the first screen, with no backtrace.
        r = self.app("hk-floze", self.PAIRIP_START, [hilog("110", "DFX_SignalHandler :: signo(11), pid(110), "
                                                                  "processName(x), threadName(<pre-initialize).")],
                     died_at=0.1, screens=0)
        self.assertEqual((r["end"]["kind"], r["end"]["protector"]), ("crash", "PairIP"))

    def test_a_later_crash_in_an_app_that_drew_is_not_the_protectors(self) -> None:
        r = self.app("hk-drew", self.PAIRIP_START, [hilog("110", "DFX_SignalHandler :: signo(11), pid(110), "
                                                                 "processName(x), threadName(RenderThread).")],
                     died_at=40.0, screens=3)
        self.assertEqual(r["end"]["kind"], "crash")
        self.assertNotIn("protector", r["end"])

    def test_a_protector_loaded_after_the_abort_is_not_named(self) -> None:
        # Youku, 2026-11-08: its APM library aborted; SecurityGuard loaded on another thread during the dump.
        r = self.app("hk-youku", [CHILD.format(pid="113"),
                                  "[SOURCE-NATIVE-LOAD] path=/data/local/tmp/asx/lib/arm64-v8a/libfulltrace.so search=/x",
                                  "terminating with uncaught exception of type std::bad_alloc: std::bad_alloc",
                                  "[WESTLAKE-WEBVIEW-BIONIC] abort message: terminating with uncaught exception",
                                  "[SOURCE-NATIVE-LOAD] path=/data/local/tmp/asx/lib/arm64-v8a/libsgmainso-6.7.so search=/x"],
                     [hilog("113", "DFX_SignalHandler :: signo(6), pid(113), processName(x), threadName(APM-FulltraceDu).")],
                     died_at=0.1, screens=0)
        self.assertEqual(r["end"]["kind"], "crash")
        self.assertNotIn("protector", r["end"])

    def test_a_fault_thread_frame_in_the_protector_names_it(self) -> None:
        # VivaVideo, 2026-11-08: a thread Baidu's hardening started faulted inside musl.
        crash = ["Reason:Signal:SIGSEGV(SEGV_MAPERR)@000000000000000000 ", "Fault thread info:",
                 "Tid:26815, Name:com.quvideo.xia",
                 "#00 pc 0000000000131388 /system/lib/ld-musl-aarch64.so.1(pthread_join+84)(a9d0)",
                 "#01 pc 0000000000130d08 /system/lib/ld-musl-aarch64.so.1(thrd_detach+48)(a9d0)",
                 "#02 pc 000000000004bda4 /data/local/tmp/asx/lib/arm64-v8a/libbaiduprotect.so",
                 "Registers:", "Other thread info:", "#00 pc 0000000000001000 /data/local/tmp/asx/lib/arm64-v8a/libpairipcore.so"]
        r = self.app("hk-viva", [CHILD.format(pid="112")], died_at=0.1, screens=3, crash=crash)
        self.assertEqual((r["end"]["kind"], r["end"]["protector"]), ("crash", "Baidu app hardening"))

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
