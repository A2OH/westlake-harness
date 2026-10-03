import unittest
from pathlib import Path


class ScreenshotDecides(unittest.TestCase):
    def test_host_screen_is_not_the_app(self) -> None:
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is required")
        import tempfile
        from westlake_gap import lifecycle
        ref = Image.open(lifecycle._HOST_SCREEN).convert("L")
        with tempfile.TemporaryDirectory() as temp:
            host = Path(temp) / "host.jpeg"
            full = Image.new("L", (60, 96), 0)
            full.paste(ref, (0, 6))
            full.resize((1200, 1920)).convert("RGB").save(host, quality=95)
            self.assertEqual(lifecycle.screen_state(host), "host")
            app = Path(temp) / "app.jpeg"
            Image.new("RGB", (1200, 1920), (20, 90, 200)).save(app)
            self.assertEqual(lifecycle.screen_state(app), "app")


class FirstBlocker(unittest.TestCase):
    def test_survived_upcall_miss_is_not_the_blocker(self) -> None:
        from westlake_gap import lifecycle
        miss = "No implementation found for boolean android.os.Process.readProcFile(java.lang.String)\n"
        self.assertEqual(lifecycle.first_blocker(miss + "sBindAppDone=true\n"), (None, None))
        self.assertEqual(lifecycle.first_blocker("sBindAppDone=true\n" + miss),
                         ("native-upcalls", "android.os.Process.readProcFile"))


    def test_trampoline_window_held_back_then_a_frame_is_drawing(self) -> None:
        from westlake_gap import lifecycle
        held = ("kRegJNI loop done\nsBindAppDone=true\nDecorView\n[OH_WSA-relayout] held back 1139x1920: "
                "no surface until its activity's window has an OH session\n[OH_WSA-relayout] x\n")
        self.assertEqual(lifecycle.score("a", held).rung_name, "view")
        self.assertEqual(lifecycle.score("a", held).blocker_category, "app-framework")
        drew = lifecycle.score("a", held + "[G214au_HWR] EglManager::swapBuffers ENTRY #1\n")
        self.assertEqual((drew.rung_name, drew.blocker), ("drawing", None))


class Evidence(unittest.TestCase):
    CRASH = ("Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR) fault addr 0x40\nThread: 9911 \"EGLThread\"\n"
             "Registers:\n    x30: 0x0000007f90ace7a0\n     sp: 0x0000007e9774ed20     pc: 0x0000007f90acde28\n")
    MAPS = ("7f90780000-7f90b00000 r-xp 00000000 fd:00 123 /vendor/lib64/chipsetsdk/libGLES_mali.z.so\n"
            "7f90b00000-7f90b10000 r--p 00380000 fd:00 123 /vendor/lib64/chipsetsdk/libGLES_mali.z.so\n")

    def test_native_crash_is_placed_in_its_library(self) -> None:
        from westlake_gap import evidence, lifecycle
        site = evidence.crash_site(self.CRASH, self.MAPS)
        self.assertEqual((site["thread"], site["pc"]["library"], site["pc"]["offset"]),
                         ("EGLThread", "libGLES_mali.z.so", "0x34de28"))
        s = lifecycle.score("app", "kRegJNI loop done\n" + self.CRASH)
        lifecycle.add_evidence(s, "kRegJNI loop done\n" + self.CRASH, self.MAPS)
        self.assertEqual(s.blocker, "SIGSEGV on thread EGLThread in libGLES_mali.z.so+0x34de28")

    def test_stalled_main_thread_becomes_the_blocker(self) -> None:
        from westlake_gap import lifecycle
        dump = ('DALVIK THREADS (2):\n"Thread-2" prio=5 tid=1 Blocked\n  | state=S schedstat=( 1 2 3 )\n'
                "  at java.lang.Object.wait(Native method)\n  at com.example.Init.await(Init.java:3)\n"
                '"HeapTaskDaemon" prio=5 tid=2 Waiting\n  at java.lang.Object.wait(Native method)\n')
        text = "kRegJNI loop done\nsBindAppDone=true\n" + dump
        s = lifecycle.score("app", text)
        lifecycle.add_evidence(s, text, None)
        self.assertEqual((s.blocker_category, s.blocker),
                         ("stall", "main thread waiting on a monitor at com.example.Init.await(Init.java:3)"))

    DUMP = ("Build info:OpenHarmony 6.1.0.31\nPid:6719\nReason:Signal:SIGSEGV(SEGV_MAPERR)@000000000000000000 \n"
            "Fault thread info:\nTid:6808, Name:acceleratePlayH\n#00 pc 0000000000000000 Not mapped\n"
            "#01 pc 00000000000802e8 /system/lib/ld-musl-aarch64.so.1(do_init_fini+444)(a9d018197b852b7e)\n"
            "#02 pc 0000000000ed6bf8 /data/local/tmp/asx/libart.so(vixl::aarch64::Assembler::pacib()+40)\n\n"
            "Registers:\n")

    def test_crash_dump_names_what_the_log_never_saw(self) -> None:
        from westlake_gap import evidence, lifecycle
        dump = evidence.cppcrash(self.DUMP)
        self.assertEqual((dump["signal"], dump["thread"], dump["kind"]), ("SIGSEGV", "acceleratePlayH", "null-constructor"))
        # Westlake's runtime libraries get no symbol: the dumper names the nearest exported one.
        self.assertNotIn("symbol", dump["frames"][2])
        text = "kRegJNI loop done\n"
        s = lifecycle.score("tiktok", text)
        lifecycle.add_evidence(s, text, None, self.DUMP)
        self.assertEqual((s.blocker_category, s.fatal), ("native-crash", 1))
        self.assertIn("acceleratePlayH: a library constructor (INIT_ARRAY entry) is null", s.blocker)

    def test_crash_dump_shapes(self) -> None:
        from westlake_gap import evidence
        head = "Reason:Signal:%s@0000000000000000\nFault thread info:\nTid:1, Name:t\n"
        heap = evidence.cppcrash(head % "SIGSEGV(SEGV_MAPERR)"
                                 + "#00 pc 00000000000d6e20 /system/lib/ld-musl-aarch64.so.1(__libc_malloc_impl+1332)(ab)\n"
                                 + "#01 pc 000000000003928c /data/local/tmp/asx/lib/arm64-v8a/libsyscall.so\n")
        self.assertEqual((heap["kind"], heap["first_app_frame"]), ("heap", "libsyscall.so+0x3928c"))
        abort = evidence.cppcrash(head % "SIGABRT(SI_TKILL)"
                                  + "#00 pc 0000000000111344 /system/lib/ld-musl-aarch64.so.1(raise+384)(ab)\n"
                                  + "#01 pc 00000000000bd55c /system/lib/ld-musl-aarch64.so.1(abort+20)(ab)\n"
                                  + "#02 pc 0000000006229238 /data/local/tmp/asx/lib/arm64-v8a/.libwaze.so.westlake-init.1986.0 (deleted)\n")
        self.assertEqual(abort["summary"], "aborted from libwaze.so")
        call = evidence.cppcrash(head % "SIGSEGV(SEGV_MAPERR)" + "#00 pc 0000000000000000 Not mapped\n"
                                 + "#01 pc 0000000000499ba4 /data/local/tmp/asx/lib/arm64-v8a/libpython3.11.so\n")
        self.assertEqual(call["summary"], "a null function pointer called from libpython3.11.so+0x499ba4")
        init = evidence.cppcrash(head % "SIGSEGV(SEGV_ACCERR)" + "#00 pc 00000000000482a0 [Unknown]\n"
                                 + "#01 pc 00000000000802e8 /system/lib/ld-musl-aarch64.so.1(do_init_fini+444)(ab)\n")
        self.assertEqual(init["kind"], "unrelocated-constructor")

    def test_crash_dump_completes_a_crash_the_log_saw(self) -> None:
        from westlake_gap import lifecycle
        text = "kRegJNI loop done\nFatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR) fault addr 0x0\nThread: 1 \"acceleratePlayH\"\n"
        s = lifecycle.score("tiktok", text)
        lifecycle.add_evidence(s, text, None, self.DUMP)
        self.assertTrue(s.blocker.endswith(": a library constructor (INIT_ARRAY entry) is null: musl calls it, bionic skips it"))

    def test_a_signal_only_the_hilog_saw(self) -> None:
        from westlake_gap import evidence, lifecycle
        hilog = ("10-03 10:19:36.586  7402  7402 I C00f00/AppSpawnX: Child process started\n"
                 "10-03 10:19:46.745  7402  7471 W C03f07/MUSL-SIGCHAIN: signal_chain_handler call 0 rd sigchain action for signal: 11\n"
                 "10-03 10:19:46.745  7402  7471 W C03f07/MUSL-SIGCHAIN: signal_chain_handler call 0 rd sigchain action for signal: 11 directly return\n"
                 "10-03 10:19:54.969  7402  7545 W C03f07/MUSL: flag is AI_NUMERICHOST but host is Illegal\n"
                 "10-03 10:19:54.973  7402  7545 W C03f07/MUSL-SIGCHAIN: signal_chain_handler call usr sigaction for signal: 4 sig_action.sa_sigaction=7ed1a28d64\n")
        self.assertEqual(evidence.hilog_signal(hilog), {"signal": "SIGILL", "tid": 7545,
                                                        "after": "flag is AI_NUMERICHOST but host is Illegal"})
        # A signal the app's handler took and the process lived on past is not a crash.
        later = hilog + "10-03 10:20:30.000  7402  7402 I C00f00/App: still running\n"
        self.assertIsNone(evidence.hilog_signal(later))
        s = lifecycle.score("instagram", "kRegJNI loop done\n")
        lifecycle.add_evidence(s, "kRegJNI loop done\n", None, None, hilog)
        self.assertEqual(s.blocker, "SIGILL on tid 7545 (hilog only, no crash dump), right after: "
                                    "flag is AI_NUMERICHOST but host is Illegal")


if __name__ == "__main__":
    unittest.main()
