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
            # An overlay toolbar over the host screen (Draw Anywhere): a band, the rest the host.
            over = Path(temp) / "overlay.jpeg"
            shot = full.resize((1200, 1920)).convert("RGB")
            shot.paste((150, 150, 150), (40, 140, 560, 200))
            shot.save(over, quality=95)
            self.assertEqual(lifecycle.screen_state(over), "partial")


class FirstBlocker(unittest.TestCase):
    def test_survived_upcall_miss_is_not_the_blocker(self) -> None:
        from westlake_gap import lifecycle
        miss = "No implementation found for boolean android.os.Process.readProcFile(java.lang.String)\n"
        self.assertEqual(lifecycle.first_blocker(miss + "sBindAppDone=true\n"), (None, None))
        self.assertEqual(lifecycle.first_blocker("sBindAppDone=true\n" + miss),
                         ("native-upcalls", "android.os.Process.readProcFile"))


    def test_uncaught_plain_exceptions_and_library_loads_are_blockers(self) -> None:
        from westlake_gap import lifecycle
        gecko = ("[UNCAUGHT] thread='Gecko' java.lang.Exception: Error loading Gecko libraries: Error loading "
                 "shared library libmediandk.so: (needed by /data/local/tmp/asx/lib/arm64-v8a/libxul.so)\n")
        self.assertEqual(lifecycle.first_blocker(gecko),
                         ("native-loading", "uncaught on Gecko: library libmediandk.so not loaded"))
        self.assertEqual(lifecycle.first_blocker("[UNCAUGHT] thread='main' java.lang.Error: boom\n"),
                         ("app-framework", "uncaught on main: Error: boom"))
        self.assertEqual(lifecycle.first_blocker(
            "[UNCAUGHT] thread='main' java.lang.IllegalStateException: Required value was null.\n"),
            ("app-framework", "uncaught on main: IllegalStateException: Required value was null."))

    def test_an_activity_that_closed_itself_off_screen(self) -> None:
        from westlake_gap import evidence
        resumed = ("10-04 04:24:13.864 1 2 I C00f00/OH_ACCAdapter: activityResumed: OnDrawListener attached, FG "
                   "deferred to first frame (token=android.os.Binder@%s)\n")
        finished = ("10-04 04:24:13.%s 1 2 I C00f00/OH_ACCAdapter: finishActivity: no OH ability; local destroy "
                    "scheduled for android.os.Binder@%s\n")
        self.assertEqual(evidence.self_finish(resumed % "bad9da3" + finished % ("900", "bad9da3")),
                         {"token": "android.os.Binder@bad9da3", "after_ms": 36})
        # A trampoline: the first activity finished after another one resumed.
        self.assertIsNone(evidence.self_finish(resumed % "a1" + resumed % "b2" + finished % ("950", "a1")))
        self.assertIsNone(evidence.self_finish(resumed % "a1"))

    def test_the_in_process_services_an_app_called(self) -> None:
        from westlake_gap import evidence
        stderr = ("[WESTLAKE-LOCAL-SERVICE] role bound in process\n[WESTLAKE-LOCAL-SERVICE] role.isRoleAvailableAsUser\n"
                  "[WESTLAKE-LOCAL-SERVICE] notification.enqueueTextToast\n[WESTLAKE-LOCAL-SERVICE] role.isRoleHeld\n"
                  "[WESTLAKE-LOCAL-SERVICE] telephony.registry.listenWithEventList\n")
        self.assertEqual(evidence.local_service_calls(stderr), ["role", "notification", "telephony.registry"])

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

    def test_the_main_thread_is_the_one_running_activity_thread_main(self) -> None:
        """cclauncher: tid 1 was a WorkManager pool thread parked in its queue; the main looper ran as
        "Thread-2" (appspawn-x starts the VM on a worker pthread) and was idle."""
        from westlake_gap import evidence
        dump = ('DALVIK THREADS (2):\n"Thread-2" prio=5 tid=9 Native\n  | state=S schedstat=( 1 2 3 )\n'
                "  at android.os.MessageQueue.nativePollOnce(Native method)\n  at android.os.Looper.loop(Looper.java:1)\n"
                "  at android.app.ActivityThread.main(ActivityThread.java:1)\n"
                '"WM.task-1" prio=5 tid=1 Waiting\n  | state=S\n  at jdk.internal.misc.Unsafe.park(Native method)\n'
                "  at java.util.concurrent.locks.LockSupport.park(LockSupport.java:1)\n")
        thread = evidence.main_thread(dump)
        self.assertEqual((thread["name"], thread["waiting"]), ("Thread-2", "idle in its message loop"))

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
        # Fennec: libxul freed with musl's free what mozjemalloc allocated; mallocng faults checking it.
        foreign = evidence.cppcrash(head % "SIGSEGV(SEGV_MAPERR)"
                                    + "#00 pc 00000000000d5e1c /system/lib/ld-musl-aarch64.so.1(get_meta+92)(ab)\n"
                                    + "#01 pc 00000000000d5b40 /system/lib/ld-musl-aarch64.so.1(__libc_free+24)(ab)\n"
                                    + "#02 pc 0000000002906cb0 /data/local/tmp/asx/lib/arm64-v8a/libxul.so\n")
        self.assertEqual(foreign["kind"], "heap")
        self.assertIn("handed memory its heap never allocated", foreign["summary"])
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

    def test_a_frame_past_its_files_mappings(self) -> None:
        """CapCut: the dump placed its fault at libmetasec_ov.so+0x215d6ec, past the 1.9 MB library."""
        from westlake_gap import evidence
        lib = "/data/local/tmp/asx/lib/arm64-v8a/libmetasec_ov.so"
        text = ("Reason:Signal:SIGSEGV(SEGV_MAPERR)@0x0000000000000013 \nFault thread info:\nTid:17197, Name:Thread-13\n"
                f"#00 pc 000000000215d6ec {lib}\n#01 pc 00000000000210a0 {lib}\nRegisters:\n\nMaps:\n"
                f"7ea1680000-7ea183e000 r-xp 00000000 {lib}\n7ea183e000-7ea1842000 r--p 001be000 {lib}\n"
                f"7ea1858000-7ea185c000 rw-p 001d4000 {lib}\n")
        dump = evidence.cppcrash(text)
        self.assertTrue(dump["frames"][0]["beyond_mapping"])
        self.assertNotIn("beyond_mapping", dump["frames"][1])
        self.assertTrue(dump["summary"].startswith("in code past libmetasec_ov.so's mappings"))
        self.assertEqual(dump["first_app_frame"], "libmetasec_ov.so+0x215d6ec (past its mappings)")
        self.assertEqual(evidence.cppcrash(text.split("Maps:")[0])["summary"], "in libmetasec_ov.so+0x215d6ec",
                         "no maps, no judgement")

    def test_the_pc_register_places_an_app_librarys_fault(self) -> None:
        """CapCut: the dump printed libmetasec_ov.so+0x1756ec (in .rodata); pc is a store at 0x15b6ec."""
        from westlake_gap import evidence
        lib = "/data/local/tmp/asx/lib/arm64-v8a/libmetasec_ov.so"
        musl = "/system/lib/ld-musl-aarch64.so.1"
        text = ("Reason:Signal:SIGSEGV(SEGV_MAPERR)@0x0000000000000013 \nFault thread info:\nTid:1, Name:Thread-13\n"
                f"#00 pc 00000000001756ec {lib}\n#01 pc 000000000017588c {lib}\nRegisters:\n"
                "lr:0000007ed0b9b890 sp:0000007eb2d7c030 pc:0000007ed0b9b6ec\n\nMaps:\n"
                f"7ed0a40000-7ed0bfe000 r-xp 00000000 {lib}\n7fb2b13000-7fb2bec000 r-xp 0007e000 {musl}\n")
        dump = evidence.cppcrash(text)
        self.assertEqual((dump["frames"][0]["pc"], dump["frames"][0]["dump_pc"]), (0x15b6ec, 0x1756ec))
        self.assertEqual(dump["summary"], "in libmetasec_ov.so+0x15b6ec")
        # OH's own libraries keep the dump's address: their text does not lie at its file offset.
        musl_text = (text.replace(f"#00 pc 00000000001756ec {lib}", f"#00 pc 000000000013331c {musl}(pthread_setname_np+92)(ab)")
                     .replace("pc:0000007ed0b9b6ec", "pc:0000007fb2bc731c"))
        self.assertEqual(evidence.cppcrash(musl_text)["frames"][0]["pc"], 0x13331c)

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

    def test_startup_times_come_from_the_hilog(self) -> None:
        from westlake_gap import evidence
        hilog = ("10-03 11:25:25.346 22245 22245 I C00f00/AppSpawnX: Child process started, pid=<private>\n"
                 "10-03 11:25:27.601 22245 22262 I C00f00/OH_ACCAdapter: activityResumed: OnDrawListener attached, FG deferred\n"
                 "10-03 11:25:28.131 22245 22262 W C00f00/OH_ACCAdapter: activityResumed (first-frame): no OH token mapping\n")
        self.assertEqual(evidence.startup_times(hilog), {"resumed": 2.26, "first_frame": 2.79})
        self.assertIsNone(evidence.startup_times("10-03 11:25:25.346 1 1 I C00f00/X: other\n"))

    def test_a_resumed_activity_that_drew_no_frame(self) -> None:
        """Since build 88 the adapter's 800 ms timeout says so. Linphone resumed, its pre-draw
        listener cancelled every draw, and only the timeout reported: the host screen showed."""
        from westlake_gap import evidence, lifecycle
        hilog = ("10-05 08:30:20.900   942   942 I C00f00/AppSpawnX: Child process started, pid=1\n"
                 "10-05 08:30:22.380   942   967 I C00f00/OH_ACCAdapter: activityResumed: OnDrawListener attached\n"
                 "10-05 08:30:23.191   942   967 W C00f00/OH_ACCAdapter: activityResumed (first-frame timeout): no OH token mapping\n")
        self.assertEqual(evidence.startup_times(hilog), {"resumed": 1.48, "first_frame_timeout": 2.29})
        text = "kRegJNI loop done\n[DIRECT-LAUNCH] bind done sBindAppDone=true\n"
        s = lifecycle.score("linphone", text)
        s.screen = "host"
        lifecycle.add_evidence(s, text, None, None, hilog)
        self.assertEqual((s.blocker_category, s.blocker),
                         ("no-frame", "the activity resumed 1.5 s after start and drew no frame"))
        s = lifecycle.score("linphone", text)
        s.screen = "app"
        lifecycle.add_evidence(s, text, None, None, hilog)
        self.assertNotEqual(s.blocker_category, "no-frame", "on screen: something drew")
        drawn = hilog.replace("(first-frame timeout)", "(first-frame)")
        s = lifecycle.score("linphone", text)
        s.screen = "host"
        lifecycle.add_evidence(s, text, None, None, drawn)
        self.assertNotEqual(s.blocker_category, "no-frame", "a frame was drawn")

    def test_root_cause_is_the_deepest_cause_with_its_app_frame(self) -> None:
        """otgmaster's blocker read "start activity: NullPointerException"; its cause named the
        manager, and the first app frame where the null was used."""
        from westlake_gap import lifecycle
        log = ("[CHILD_CK] J_invokeStaticMain_main_threw: java.lang.RuntimeException: Unable to start activity x\n"
               "java.lang.RuntimeException: Unable to start activity x\n"
               "\tat android.app.ActivityThread.performLaunchActivity(Unknown Source:629)\n"
               "Caused by: java.lang.NullPointerException: null cannot be cast to non-null type android.hardware.usb.UsbManager\n"
               "\tat android.app.Activity.getSystemService(Unknown Source:1)\n"
               "\tat app.fayaz.otgmaster.MainActivity.onCreate(MainActivity.kt:270)\n"
               "[INITCHILD-FAIL] java.lang.reflect.InvocationTargetException: null\n"
               "[INITCHILD-FAIL]   caused by: java.lang.RuntimeException: later\n")
        self.assertEqual(lifecycle.root_cause(log), {
            "exception": "NullPointerException",
            "message": "null cannot be cast to non-null type android.hardware.usb.UsbManager",
            "frame": "app.fayaz.otgmaster.MainActivity.onCreate"})
        bind = ("x ensureBindApplication FAILED phase=handleBindApplication cause[1]=java.lang.RuntimeException: Unable to create\n"
                "x ensureBindApplication FAILED phase=handleBindApplication cause[2]=java.lang.IllegalArgumentException: maxSize <= 0\n"
                "x ensureBindApplication FAILED phase=handleBindApplication at cha.a(r8:3)\n"
                "x [DIRECT-LAUNCH] FAILED cause[0]=java.lang.IllegalStateException: Application binding failed\n")
        self.assertEqual(lifecycle.root_cause(bind),
                         {"exception": "IllegalArgumentException", "message": "maxSize <= 0", "frame": "cha.a"},
                         "the launch failure that follows the bind's is not its cause")
        self.assertIsNone(lifecycle.root_cause("kRegJNI loop done\n"))

    def test_a_first_frame_the_log_never_reached(self) -> None:
        """Rethink: the Go runtime sends stderr to hilog, so the child log stopped at "bound" while
        the hilog showed the first frame and the screenshot the app's welcome screen."""
        from westlake_gap import lifecycle
        hilog = ("10-03 11:25:25.346 22245 22245 I C00f00/AppSpawnX: Child process started, pid=1\n"
                 "10-03 11:25:27.606 22245 22262 I C00f00/OH_ACCAdapter: activityResumed: OnDrawListener attached\n"
                 "10-03 11:25:28.131 22245 22262 W C00f00/OH_ACCAdapter: activityResumed (first-frame): no OH token mapping\n")
        text = "kRegJNI loop done\n[DIRECT-LAUNCH] bind done sBindAppDone=true\n"
        for screen, rung in (("app", "drawing"), ("host", "view"), (None, "view")):
            s = lifecycle.score("rethink", text)
            s.screen = screen
            lifecycle.add_evidence(s, text, None, None, hilog)
            self.assertEqual(s.rung_name, rung, screen)
        s = lifecycle.score("rethink", text)
        s.screen = "app"
        lifecycle.add_evidence(s, text, None, None, "10-03 11:25:25.346 1 1 I C00f00/X: other\n")
        self.assertEqual(s.rung_name, "bound", "no first-frame marker: the log decides")

    def test_the_shim_witness_places_a_signal_without_a_dump(self) -> None:
        from westlake_gap import evidence, lifecycle
        log = ("kRegJNI loop done\n[WESTLAKE-SIGNAL-WITNESS] signal=0x4 code=0x1 tid=0x1d79 thread=MnsNetworking "
               "pc=0x7f00001234 x30=0x7f00002000\n")
        maps = "7f00000000-7f00010000 r-xp 00000000 fd:00 1 /data/data/pkg/lib-compressed/libstartup.so\n"
        witness = evidence.signal_witnesses(log, maps)[0]
        self.assertEqual((witness["signal"], witness["tid"], witness["pc"]["library"], witness["pc"]["offset"]),
                         ("SIGILL", 7545, "libstartup.so", "0x1234"))
        hilog = ("10-03 10:19:36.586  7402  7402 I C00f00/AppSpawnX: Child process started\n"
                 "10-03 10:19:54.969  7402  7545 W C03f07/MUSL: flag is AI_NUMERICHOST but host is Illegal\n"
                 "10-03 10:19:54.973  7402  7545 W C03f07/MUSL-SIGCHAIN: signal_chain_handler call usr sigaction for signal: 4 x\n")
        s = lifecycle.score("instagram", log)
        lifecycle.add_evidence(s, log, maps, None, hilog)
        self.assertEqual(s.blocker, "SIGILL on thread MnsNetworking at libstartup.so+0x1234 (from libstartup.so+0x2000) "
                                    "(hilog only, no crash dump), right after: flag is AI_NUMERICHOST but host is Illegal")

    def test_the_witness_places_its_own_addresses(self) -> None:
        from westlake_gap import evidence
        log = ("[WESTLAKE-SIGNAL-WITNESS] signal=0x4 code=0x1 tid=0x5788 thread=MNSEventLoop1 pc=0x7f98dd8548 "
               "x30=0x7ecd8dc3e0 at /system/lib/ld-musl-aarch64.so.1+0xbc548 insn=0xf4ccffcc next=0xa9037bfd "
               "from /data/local/tmp/asx/lib/arm64-v8a/libstartup.so+0x71c3e0 x0=0x1\n")
        witness = evidence.signal_witnesses(log)[0]
        self.assertEqual((witness["pc"]["library"], witness["pc"]["offset"], witness["insn"]),
                         ("ld-musl-aarch64.so.1", "0xbc548", "0xf4ccffcc"))
        self.assertEqual(witness["caller"]["library"], "libstartup.so")


if __name__ == "__main__":
    unittest.main()
