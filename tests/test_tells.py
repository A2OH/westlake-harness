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
            screens: int = 1, crash: list[str] = (), maps: list[str] = ()) -> dict:
        (self.logs / f"{name}.stderr").write_text("\n".join(stderr) + "\n")
        (self.logs / f"{name}.hilog").write_text("\n".join(hilog_lines) + "\n")
        if crash:
            (self.logs / f"{name}.cppcrash").write_text("\n".join(crash) + "\n")
        if maps:
            (self.logs / f"{name}.maps").write_text("\n".join(maps) + "\n")
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

    def test_bangcle_and_fairguard_are_named(self) -> None:
        # China Railway, 2026-11-08: Bangcle's libDexHelper.so aborted at start.
        crash = ["Reason:Signal:SIGABRT(SI_TKILL)@0x0131544600000fdc ", "Fault thread info:", "Tid:4060, Name:main",
                 "#00 pc 0000000000111344 /system/lib/ld-musl-aarch64.so.1(raise+384)(a9d0)",
                 "#01 pc 00000000000bd55c /system/lib/ld-musl-aarch64.so.1(abort+20)(a9d0)",
                 "#02 pc 0000000000070318 /data/local/tmp/asx/lib/arm64-v8a/libDexHelper.so", "Registers:"]
        r = self.app("hk-rail", [CHILD.format(pid="113")], died_at=0.1, crash=crash)
        self.assertEqual(r["end"]["protector"], "Bangcle")
        crash[-2] = "#02 pc 000000000001e1d0 /data/local/tmp/asx/lib/arm64-v8a/libFairGuard.so"
        r = self.app("hk-game", [CHILD.format(pid="114")], died_at=0.1, crash=crash)
        self.assertEqual(r["end"]["protector"], "FairGuard")

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

    LIB = "/data/local/tmp/asx/lib/arm64-v8a/"
    HANDLED = ("11-08 23:19:03.207 31065 31353 W C03f07/MUSL-SIGCHAIN: signal_chain_handler call usr sigaction "
               "for signal: 4 sig_action.sa_sigaction={}")

    def test_the_handler_that_took_the_signal_is_named_from_the_memory_map(self) -> None:
        r = self.app("hk-game", [CHILD.format(pid="31065")], [self.HANDLED.format("7eba092d38")],
                     maps=[f"7eba080000-7eba0a0000 r-xp 00000000 103:3e 1234 {self.LIB}libCrashSight.so",
                           f"7eba0a0000-7eba0b0000 r--p 00020000 103:3e 1234 {self.LIB}libCrashSight.so"])
        self.assertEqual(r["end"]["kind"], "silent")
        self.assertEqual(r["end"]["detail"], "after the app's own handler took signal 4 (in libCrashSight.so)")

    def test_the_shims_forwarder_names_the_handler_installed_through_it(self) -> None:
        stderr = [CHILD.format(pid="31065"),
                  "[WESTLAKE-SIGNAL-INSTALL] android signal=4 flags=0x8000004 handler=0x7eb451545c caller=0x7eb4513750",
                  "[WESTLAKE-SIGNAL-INSTALL] android signal=11 flags=0x8000004 handler=0x7eba092d38 caller=0x7eb4513750"]
        maps = [f"7eb4500000-7eb4520000 r-xp 00000000 103:3e 77 {self.LIB}libBugly_Native.so",
                "7f03880000-7f038a0000 r-xp 00000000 103:3e 88 /data/local/tmp/asx/webview-t-lib/libwebview_bionic_shim.so"]
        r = self.app("hk-reader", stderr, [self.HANDLED.format("7f0388a4dc")], maps=maps)
        self.assertEqual(r["end"]["detail"], "after the app's own handler took signal 4 (in libBugly_Native.so)")

    def test_without_a_memory_map_the_handler_is_not_named(self) -> None:
        r = self.app("hk-gone", [CHILD.format(pid="31065")], [self.HANDLED.format("7eba092d38")])
        self.assertEqual(r["end"]["detail"], "after the app's own handler took signal 4")

    def test_the_witness_names_a_protector_a_silent_end_faulted_in(self) -> None:
        stderr = [CHILD.format(pid="20616"),
                  "[WESTLAKE-SIGNAL-WITNESS] signal=0x4 code=0x1 tid=0x5088 thread=com.asw.moneyba pc=0x7ef9f202e8 "
                  "x30=0x7f9d0a52ec at /data/local/tmp/asx/lib/arm64-v8a/libakamaibap.so+0x2202e8 insn=0xa5aada00 "
                  "next=0x44c66935 from /system/lib/ld-musl-aarch64.so.1+0x7f2ec x0=0xfffffffffffff216"]
        r = self.app("hk-loyalty", stderr, screens=0)
        self.assertEqual(r["end"]["kind"], "silent")
        self.assertEqual(r["end"]["protector"], "Akamai Bot Manager")

    def test_a_witness_in_an_ordinary_library_names_no_protector(self) -> None:
        stderr = [CHILD.format(pid="20616"),
                  "[WESTLAKE-SIGNAL-WITNESS] signal=0xb code=0x1 tid=0x6006 thread=main pc=0x7f943b6f14 x30=0x7f943b6ea4 "
                  "at /system/lib/ld-musl-aarch64.so.1+0x84f14 insn=0xf86d79cf next=0xeb0b01ff from "
                  "/system/lib/ld-musl-aarch64.so.1+0x84ea4 x0=0x0"]
        r = self.app("hk-meetings", stderr, screens=0)
        self.assertNotIn("protector", r["end"])

    def test_a_silent_end_right_after_a_protector_loads_names_it(self) -> None:
        """Limbus Company: AppSealing's library loads, installs two handlers, and the log stops."""
        stderr = [CHILD.format(pid="2601"),
                  "[SOURCE-NATIVE-LOAD] path=/data/local/tmp/asx/lib/arm64-v8a/libcovault-appsec.so search=/x",
                  "[SOURCE-NATIVE-LOADER] path=/data/local/tmp/asx/lib/arm64-v8a/libcovault-appsec.so class_paths=/x",
                  "[WESTLAKE-SIGNAL-INSTALL] oh signal=4 flags=0x18000004 handler=0x7f7fbc7f98 caller=0x7f810e1310",
                  "[WESTLAKE-SIGNAL-INSTALL] oh signal=31 flags=0x1c000004 handler=0x7f7fbc7f98 caller=0x7f810e1334"]
        r = self.app("hk-limbus", stderr, screens=0)
        self.assertEqual(r["end"]["protector"], "AppSealing")
        later = self.app("hk-later", stderr + ["[OHServiceManager] getService(\"isub\") → null (stub)"] * 10, screens=0)
        self.assertNotIn("protector", later["end"], "a load long before the log stops is not the end's cause")

    def test_netease_yidun_is_named_from_the_fault_thread(self) -> None:
        """Farlight's game: its first frame is a call through an unrelocated pointer, from libnesec.so."""
        crash = ["Reason:Signal:SIGSEGV(SEGV_ACCERR)@0x00000000000d3eb0 ", "Fault thread info:",
                 "Tid:2514, Name:com.farlightgam", "#00 pc 00000000000c3eb0 [Unknown]",
                 "#01 pc 00000000000a5720 /data/local/tmp/asx/lib/arm64-v8a/libnesec.so",
                 "#02 pc 0000000000212154 /data/local/tmp/asx/boot/boot.oat", "Registers:"]
        r = self.app("hk-shooter", [CHILD.format(pid="2495")], screens=0, crash=crash)
        self.assertEqual((r["end"]["kind"], r["end"]["protector"]), ("crash", "NetEase Yidun"))

    def test_the_loader_reason_is_a_failed_tell_and_a_cause_candidate(self) -> None:
        r = self.app("hk-amap", [CHILD.format(pid="106"),
                                 "[WESTLAKE-LOADER] libamaptbt.so by name failed (Error relocating x: "
                                 "__system_property_set: symbol not found); opening the path",
                                 "[UNCAUGHT] thread='launch_async' java.lang.UnsatisfiedLinkError: x"])
        self.assertEqual(r["end"]["kind"], "uncaught")
        load = [t for t in r["tells"] if t["contract"] == "load:libamaptbt.so"]
        self.assertEqual(load[0]["answer"], "failed")
        self.assertIn("__system_property_set", tells.cause_candidate(r, set()))

    def test_the_gpu_driver_ending_the_context_is_the_cause_candidate(self) -> None:
        r = self.app("hk-flutter", [CHILD.format(pid="16923"),
                                    "[SOURCE-NATIVE-LOAD] path=/data/local/tmp/asx/lib/arm64-v8a/libflutter.so search=/x",
                                    "==>[ERROR] (mali-cmar-backe) BASE: In file: ../../vendor/gpu/usr/base/src/"
                                    "mali_base_kbase.c  line: 361 base_jd_event_term",
                                    "Could not notify message handler of driver termination.",
                                    "[WESTLAKE-REAP] child 17024 exited(0)",
                                    "Fatal signal 6 (SIGABRT), code -6 (SI_TKILL)", "Backtrace:", ""],
                     [hilog("16923", "DFX_SignalHandler :: signo(6), pid(16923), processName(x), "
                                     "threadName(mali-cmar-backe).", tid="17016")],
                     died_at=0.1, screens=0)
        self.assertEqual(r["end"]["kind"], "crash")
        gpu = [t for t in r["tells"] if t["contract"] == "gpu:mali-context"]
        self.assertEqual((gpu[0]["answer"], gpu[0]["detail"]),
                         ("failed", "the GPU driver ended the context (base_jd_event_term, thread mali-cmar-backe)"))
        self.assertIn("base_jd_event_term", tells.cause_candidate(r, set()))

    def test_keep_screen_on_is_a_tell_and_never_the_cause(self) -> None:
        """YouTube Music asked for FLAG_KEEP_SCREEN_ON; the window policy's native did not load."""
        r = self.app("hk-music", [CHILD.format(pid="5903"),
                                  "[OH_WINDOW_POLICY] update failed java.lang.ExceptionInInitializerError",
                                  "[OH_WINDOW_POLICY] session=4237 keepScreenOn=true rc=0",
                                  "[UNCAUGHT] thread='main' java.lang.IllegalStateException: x"])
        answers = [(t["contract"], t["answer"], t["fidelity"], t["detail"]) for t in r["tells"]
                   if t["contract"] == "window:keep-screen-on"]
        self.assertEqual(answers, [
            ("window:keep-screen-on", "not applied", "stand-in", "java.lang.ExceptionInInitializerError"),
            ("window:keep-screen-on", "applied", "android", "keepScreenOn=true rc=0")])
        self.assertNotIn("keep-screen-on", tells.cause_candidate(r, set()))

    def test_surfaceview_order_is_a_tell(self) -> None:
        r = self.app("hk-casino", [CHILD.format(pid="12682"),
                                   "[OH_WSA] SurfaceView 'SurfaceView[a/a.Boot]' 1200x1920 at 0,0 -> own sessionId=4244",
                                   "[OH_WSA] SurfaceView 'SurfaceView[a/a.Boot]' 1280x1920 at -40,0 -> own "
                                   "sessionId=4245, below its window (z-level -2, rc=0)",
                                   "[OH_WSA] SurfaceView 'SurfaceView[a/a.Boot]' 1200x1920 at 0,0 -> own "
                                   "sessionId=4246, on top",
                                   "[OH_WSA] SurfaceView 'SurfaceView[a/a.Boot]' 1200x1920 at 0,0 -> own "
                                   "sessionId=4247, below its window (z-level -1, rc=-2)"],
                     died_at=None)
        answers = [(t["answer"], t["fidelity"], t["detail"]) for t in r["tells"]
                   if t["contract"] == "window:surfaceview-order"]
        self.assertEqual(answers, [
            ("on top", "unknown", "above its activity's window (a build before z-levels)"),
            ("below", "android", "z-level -2"),
            ("on top", "android", "the app put it on top (setZOrderOnTop), or the runtime was told to"),
            ("failed", "unknown", "below its window (z-level -1, rc=-2)")])

    def test_libandroid_lookups_by_handle_are_tells(self) -> None:
        r = self.app("hk-browser", [CHILD.format(pid="109"),
                                    "[WESTLAKE-LOADER] libandroid.so by handle: ASharedMemory_create from the bionic shim",
                                    "[WESTLAKE-LOADER] libandroid.so by handle: ASurfaceControl_createFromWindow from "
                                    "the bionic shim"],
                     died_at=None)
        answers = {(t["contract"], t["answer"], t["fidelity"]) for t in r["tells"]}
        self.assertIn(("dlsym:libandroid.so#ASharedMemory_create", "shim", "unknown"), answers)
        self.assertIn(("dlsym:libandroid.so#ASurfaceControl_createFromWindow", "shim", "stand-in"), answers)

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
