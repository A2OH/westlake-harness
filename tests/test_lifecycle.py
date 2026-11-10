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


class HostPages(unittest.TestCase):
    def test_any_of_the_hosts_pages_is_the_host_screen(self) -> None:
        """The host's page went from a title and a keyboard control to an empty black page: the
        records made with either are classified against the page they were made with."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is required")
        import tempfile
        from unittest import mock
        from westlake_gap import lifecycle
        with tempfile.TemporaryDirectory() as temp:
            black = Path(temp) / "host-screen-blank.png"
            Image.new("L", (60, 90), 0).save(black)
            shot = Path(temp) / "black.jpeg"
            Image.new("RGB", (1200, 1920), (0, 0, 0)).save(shot, quality=95)
            app = Path(temp) / "app.jpeg"
            Image.new("RGB", (1200, 1920), (20, 90, 200)).save(app)
            with mock.patch.object(lifecycle, "_HOST_SCREENS", [lifecycle._HOST_SCREEN, black]):
                self.assertEqual(lifecycle.screen_state(shot), "host")
                self.assertEqual(lifecycle.screen_state(app), "app")
            with mock.patch.object(lifecycle, "_HOST_SCREENS", [lifecycle._HOST_SCREEN]):
                self.assertEqual(lifecycle.screen_state(shot), "app", "the first page alone does not know it")


    def test_a_run_is_read_against_its_own_host_page(self) -> None:
        """A dark app (spacebeam) is closest to the black page, as that page with something over it.
        r87 ran over the first page, which its bare host screenshots show."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is required")
        import tempfile
        from unittest import mock
        from westlake_gap import lifecycle
        with tempfile.TemporaryDirectory() as temp:
            black = Path(temp) / "host-screen-blank.png"
            Image.new("L", (60, 90), 0).save(black)
            first = Image.new("L", (60, 96), 0)
            first.paste(Image.open(lifecycle._HOST_SCREEN).convert("L"), (0, 6))
            bare = Path(temp) / "bare.jpeg"
            first.resize((1200, 1920)).convert("RGB").save(bare, quality=95)
            dark = Path(temp) / "dark.jpeg"
            shot = Image.new("RGB", (1200, 1920), (0, 0, 0))
            shot.paste((200, 200, 200), (100, 600, 400, 660))
            shot.save(dark, quality=95)
            with mock.patch.object(lifecycle, "_HOST_SCREENS", [lifecycle._HOST_SCREEN, black]):
                self.assertEqual(lifecycle.screen_state(dark), "partial", "against every page")
                hosts = lifecycle.run_host_screens([bare, dark])
                self.assertEqual(hosts, [lifecycle._HOST_SCREEN])
                self.assertEqual(lifecycle.screen_state(dark, hosts), "app")
                over_black = Path(temp) / "black.jpeg"
                Image.new("RGB", (1200, 1920), (0, 0, 0)).save(over_black, quality=95)
                self.assertEqual(lifecycle.run_host_screens([over_black, dark]), [black])
                self.assertEqual(lifecycle.run_host_screens([dark]), [lifecycle._HOST_SCREEN, black],
                                 "no bare host: every page")


    def test_the_navigation_handle_is_left_out(self) -> None:
        """Over the black page alone the navigation bar's handle is light; over cclauncher's
        transparent window it is dark, and nothing else of cclauncher shows."""
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow is required")
        import tempfile
        from unittest import mock
        from westlake_gap import lifecycle
        with tempfile.TemporaryDirectory() as temp:
            black = Path(temp) / "host-screen-blank.png"
            page = Image.new("L", (60, 90), 0)
            page.paste(67, (24, 89, 36, 90))
            page.save(black)
            shot = Path(temp) / "cclauncher.jpeg"
            screen = Image.new("RGB", (1200, 1920), (0, 0, 0))
            screen.paste((29, 29, 29), (475, 1895, 725, 1907))
            screen.save(shot, quality=95)
            with mock.patch.object(lifecycle, "_HOST_SCREENS", [black]):
                self.assertEqual(lifecycle.screen_state(shot), "host")


class ScreenshotConfirms(unittest.TestCase):
    def test_an_app_on_screen_whose_logs_fell_short_drew(self) -> None:
        """aaaaxy (r88): its log stops at bind, Go's output goes to hilog, and its hilog carried no
        first frame; the screenshot shows its game."""
        import tempfile
        from unittest import mock
        from westlake_gap import lifecycle
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "aaaaxy.stderr"
            log.write_text("kRegJNI loop done\n[DIRECT-LAUNCH] bind done sBindAppDone=true\n")
            with mock.patch.object(lifecycle, "run_host_screens", return_value=[]), \
                    mock.patch.object(lifecycle, "screen_state", return_value="app"):
                s = lifecycle.score_paths([log])[0]
            self.assertEqual((s.rung_name, s.blocking), ("drawing", False))
            self.assertIn("the screenshot shows the app", s.anomaly)
            with mock.patch.object(lifecycle, "run_host_screens", return_value=[]), \
                    mock.patch.object(lifecycle, "screen_state", return_value="host"):
                self.assertEqual(lifecycle.score_paths([log])[0].rung_name, "bound", "the host screen: nothing drew")


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

    def test_a_name_ending_in_abort_is_not_an_abort(self) -> None:
        """Boehm GC's GC_LOOP_ON_ABORT, in the shim's log of the environment variables an app asked for."""
        from westlake_gap import lifecycle
        asked = ("[WESTLAKE-WEBVIEW-BIONIC] getenv GC_LOOP_ON_ABORT: unset, asked by "
                 "/data/local/tmp/asx/lib/arm64-v8a/libil2cpp.so\n")
        self.assertEqual(lifecycle.first_blocker(asked), (None, None))
        self.assertEqual(lifecycle.first_blocker("F libc: ABORT: something went wrong\n"),
                         ("native-crash", "abort: something went wrong"))

    def test_the_abort_message_is_the_blocker_and_its_frames_say_where(self) -> None:
        """Friday Night Funkin': libc++abi's uncaught std::invalid_argument on SDLThread. ART's report of
        the SIGABRT came after it, with no frames; the shim's frames climb past libc++abi."""
        from westlake_gap import evidence, lifecycle
        asx = "/data/local/tmp/asx/lib/arm64-v8a/"
        text = ("kRegJNI loop done\n"
                "[WESTLAKE-WEBVIEW-BIONIC] abort message: terminating due to uncaught exception of type "
                "St16invalid_argument\n"
                "[WESTLAKE-ABORT-FRAMES] tid=0x4886 #0x1 %slibc++_shared.so+0xc5f40 #0x2 %slibc++_shared.so+0xc5e10"
                " #0x3 %slibc++_shared.so+0xc4f1c #0x4 %slibc++_shared.so+0x8a01c #0x5 %slibvlc.so+0x1005e88"
                " #0x6 %slibvlc.so+0xf00a10\n" % ((asx,) * 6)
                + "Fatal signal 6 (SIGABRT), code -6 (SI_TKILL)\nThread: 18554 \"SDLThread\"\n"
                "Registers:\n    x30: 0x0000007fa6969560\n     sp: 0x0000007ed368a4a0     pc: 0x0000007fa69bd344\n")
        self.assertEqual(lifecycle.first_blocker(text),
                         ("native-crash", "abort: terminating due to uncaught exception of type St16invalid_argument"))
        frames = evidence.abort_frames(text)
        self.assertEqual([(f["depth"], f["library"]) for f in frames][3:5], [(4, "libc++_shared.so"), (5, "libvlc.so")])
        self.assertEqual(evidence.abort_origin(frames)["offset"], "0x1005e88")
        maps = "7fa6800000-7fa6b00000 r-xp 00000000 fd:00 1 /system/lib/ld-musl-aarch64.so.1\n"
        s = lifecycle.score("fnf", text)
        lifecycle.add_evidence(s, text, maps)
        self.assertEqual(s.blocker, "abort: terminating due to uncaught exception of type St16invalid_argument "
                                    "(from libvlc.so+0x1005e88)")
        self.assertEqual(len(s.abort_frames), 6)
        # A terminate handler or a C++ runtime inside an app library starts the chain: the origin is past it.
        midland = [{"library": n, "offset": o} for n, o in (("libbugsnag-ndk.so", "0xf5fd0"), ("libbugsnag-ndk.so", "0xf5e94"),
                                                            ("libc++.so", "0xae114"), ("libhermes.so", "0x173450"))]
        self.assertEqual(evidence.abort_origin(midland)["library"], "libhermes.so")
        pairip = [{"library": "libpairipcore.so", "offset": o} for o in ("0x1ccc8", "0x2ad2c")]
        self.assertEqual(evidence.abort_origin(pairip)["offset"], "0x1ccc8")
        # Without the frames (an older shim), the abort is still placed where its signal landed.
        bare = text.replace(text[text.index("[WESTLAKE-ABORT-FRAMES]"):text.index("Fatal signal")], "")
        s = lifecycle.score("fnf", bare)
        lifecycle.add_evidence(s, bare, maps)
        self.assertTrue(s.blocker.endswith("St16invalid_argument in ld-musl-aarch64.so.1+0x1bd344"), s.blocker)

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

    def test_a_fault_in_the_runtime_is_named_by_its_caller(self) -> None:
        """A SIGSEGV in musl's strlen says only that a pointer was bad. The shim's frame walk for the
        same thread names the game library that passed it; ART and Java frames are passed over."""
        from westlake_gap import evidence, lifecycle
        asx = "/data/local/tmp/asx/"
        witness = ("[WESTLAKE-SIGNAL-WITNESS] signal=0xb code=0x1 tid=0x72a0 thread=GameThread pc=0x7fab8d6c10 "
                   "x30=0x7fab8d1850 at /system/lib/ld-musl-aarch64.so.1+0x97c10 insn=0xa9400c02 next=0xb200c3e8 "
                   "from /system/lib/ld-musl-aarch64.so.1+0x92850 x0=0x1\n"
                   "[WESTLAKE-SIGNAL-FRAMES] tid=0x72a0 #0x1 /system/lib/ld-musl-aarch64.so.1+0x8f3cc"
                   " #0x2 %slibart.so+0xed49e4 #0x3 %sboot/boot.oat+0x212158 #0x4 %slib/arm64-v8a/libgame.so+0x1234\n"
                   % (asx, asx, asx))
        crash = ('Fatal signal 11 (SIGSEGV), code 1 (SEGV_MAPERR) fault addr 0x0\nThread: 29344 "GameThread"\n'
                 "Registers:\n    x30: 0x0000007fab8d1850\n     sp: 0x0000007e9774ed20     pc: 0x0000007fab8d6c10\n")
        maps = "7fab83f000-7fab900000 r-xp 00000000 fd:00 1 /system/lib/ld-musl-aarch64.so.1\n"
        text = "kRegJNI loop done\n" + witness + crash
        event = evidence.signal_witnesses(text, maps)[0]
        self.assertEqual([f["library"] for f in event["frames"]],
                         ["ld-musl-aarch64.so.1", "libart.so", "boot.oat", "libgame.so"])
        self.assertEqual(evidence.first_app_frame(event["frames"])["offset"], "0x1234")
        s = lifecycle.score("game", text)
        lifecycle.add_evidence(s, text, maps)
        self.assertEqual(s.blocker, "SIGSEGV on thread GameThread in ld-musl-aarch64.so.1+0x97c10 (from libgame.so+0x1234)")
        # Nothing but the runtime and Java under it (a library load from Java): the blocker stays as it was.
        java_only = text.replace(" #0x4 %slib/arm64-v8a/libgame.so+0x1234" % asx, "")
        s = lifecycle.score("game", java_only)
        lifecycle.add_evidence(s, java_only, maps)
        self.assertEqual(s.blocker, "SIGSEGV on thread GameThread in ld-musl-aarch64.so.1+0x97c10")

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
        # Material Files: musl's realloc under getgrgid, two threads sharing its static line buffer.
        grown = evidence.cppcrash(head % "SIGSEGV(SEGV_MAPERR)"
                                  + "#00 pc 00000000000d7e80 /system/lib/ld-musl-aarch64.so.1(__libc_realloc+552)(ab)\n"
                                  + "#01 pc 000000000011a164 /system/lib/ld-musl-aarch64.so.1(getdelim+268)(ab)\n"
                                  + "#02 pc 000000000003928c /data/local/tmp/asx/lib/arm64-v8a/libsyscall.so\n")
        self.assertEqual(grown["kind"], "heap")
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

    def test_a_dump_older_than_the_process_is_another_processs(self) -> None:
        """r87: TikTok's launch (pid 9865) picked up the dump that PPSSPP's process, with the same
        pid, had left 2 h 22 min earlier."""
        from westlake_gap import lifecycle
        dump = self.DUMP.replace("Pid:6719\n", "Timestamp:2026-10-07 05:07:01.719\nPid:9865\n")
        hilog = "10-07 07:29:35.406  9865  9865 I C00f00/AppSpawnX: Child process started, pid=<private>\n"
        text = "kRegJNI loop done\n"
        s = lifecycle.score("tiktok", text)
        lifecycle.add_evidence(s, text, None, dump, hilog)
        self.assertEqual((s.crash_dump, s.fatal), (None, 0))
        # The process's own dump comes after its first line.
        s = lifecycle.score("ppsspp", text)
        lifecycle.add_evidence(s, text, None, dump, hilog.replace("07:29:35.406", "05:06:59.900"))
        self.assertEqual((s.blocker_category, s.fatal), ("native-crash", 1))

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
        left = hilog + ("10-05 08:30:22.500   942   967 I C00f00/OH_ACCAdapter: finishActivity: no OH ability; "
                        "local destroy scheduled for android.os.Binder@1\n")
        s = lifecycle.score("fmessages", text)
        s.screen = "host"
        lifecycle.add_evidence(s, text, None, None, left.replace("activityResumed: OnDrawListener attached",
                                                                 "activityResumed: OnDrawListener attached (token=android.os.Binder@1)"))
        self.assertEqual(s.blocker_category, "self-finish", "it left; the timeout follows from that")
        drawn = hilog.replace("(first-frame timeout)", "(first-frame)")
        s = lifecycle.score("linphone", text)
        s.screen = "host"
        lifecycle.add_evidence(s, text, None, None, drawn)
        self.assertNotEqual(s.blocker_category, "no-frame", "a frame was drawn")

    def test_a_window_whose_buffer_requests_failed(self) -> None:
        """anarchre: SDL's EGL surface asked OH for a buffer 13,915 times and got none, its window
        sized 0x0 by SDL's (0, 0, visual) geometry; the host screen showed."""
        from westlake_gap import evidence, lifecycle
        line = ("10-06 03:10:57.%03d  9162  9229 E C01401/Bufferqueue: <native_window.cpp:229-NativeWindowRequestBuffer>: "
                "RequestBuffer ret:50002000, uniqueId: 3758096388240.\n")
        hilog = "".join(line % i for i in range(5)) + line.replace("3758096388240", "3758096388238") % 9
        self.assertEqual(evidence.buffer_request_failures(hilog),
                         {"count": 5, "ret": 50002000, "window": 3758096388240, "windows": 2})
        self.assertIsNone(evidence.buffer_request_failures("10-06 03:10:57.100 1 1 I C00f00/SDL: onResume()\n"))
        text = "kRegJNI loop done\n[DIRECT-LAUNCH] bind done sBindAppDone=true\n"
        s = lifecycle.score("anarchre", text)
        s.screen = "host"
        lifecycle.add_evidence(s, text, None, None, hilog)
        self.assertEqual((s.blocker_category, s.blocker),
                         ("window-buffers", "5 buffer requests on one of its windows failed (ret 50002000)"))
        s = lifecycle.score("anarchre", text)
        s.screen = "app"
        lifecycle.add_evidence(s, text, None, None, hilog)
        self.assertNotEqual(s.blocker_category, "window-buffers", "on screen: the failures did not keep it off")

    def test_a_lookup_by_handle_that_found_nothing(self) -> None:
        """aaaaxy: Ebiten logged dlsym's error for glGenVertexArrays, looked up in OH's NDK
        libGLESv2.so, and the host screen showed."""
        from westlake_gap import evidence, lifecycle
        hilog = ("10-06 21:03:16.594 30377 30398 E C00f00/Go: go.Universe$proxyerror: gl: glGenVertexArrays is "
                 "missing: do_dlsym failed: Symbol not found: glGenVertexArrays, version: null "
                 "so=/system/lib64/ndk/libGLESv2.so\n")
        found = [{"symbol": "glGenVertexArrays", "library": "/system/lib64/ndk/libGLESv2.so"}]
        hal = ("10-06 18:36:48.754 14462 14574 W C02510/load_hdi: OpenHdiServiceImpl failed to get symbol of "
               "'MapperImplRelease', do_dlsym failed: Symbol not found: MapperImplRelease, version: null "
               "so=/vendor/lib64/passthrough/libmapper_service_1.0.z.so\n")
        self.assertEqual(evidence.dlsym_failures(None, hal + hilog + hilog), found, "OH's HAL probes are not the app's")
        text = "kRegJNI loop done\n[DIRECT-LAUNCH] bind done sBindAppDone=true\n"
        s = lifecycle.score("aaaaxy", text)
        s.screen = "host"
        lifecycle.add_evidence(s, text, None, None, hilog)
        self.assertEqual((s.blocker_category, s.blocker),
                         ("native-symbols", "dlsym found no glGenVertexArrays in /system/lib64/ndk/libGLESv2.so"))
        self.assertEqual(s.dlsym_failures, found)
        s = lifecycle.score("aaaaxy", text)
        s.screen = "app"
        lifecycle.add_evidence(s, text, None, None, hilog)
        self.assertNotEqual(s.blocker_category, "native-symbols", "on screen: the app went on without it")

    def test_service_refusals_in_the_log(self) -> None:
        """clauncher: the user service threw for getProfileIds, from UserManager.getUserProfiles."""
        from westlake_gap import evidence
        line = ("java.lang.UnsupportedOperationException: OH user service does not implement getProfileIds\n"
                "\tat adapter.packagemanager.OHUserManager.lambda$install$0(Unknown Source:410)\n")
        self.assertEqual(evidence.service_refusals(line, line), ["OH user service does not implement getProfileIds"])
        self.assertEqual(evidence.service_refusals("UnsupportedOperationException: not supported\n", None), [])

    def test_null_platform_services_in_the_log(self) -> None:
        """wormhole2: Build.getSerial dereferenced a null IDeviceIdentifiersPolicyService, caught by
        its plugin's channel and logged; the app never drew."""
        from westlake_gap import evidence
        line = ("10-06 18:09:41.446  4506  4527 E C00f00/MethodChannel#x: java.lang.NullPointerException: Attempt to "
                "invoke InvokeType(4) method 'java.lang.String android.os.IDeviceIdentifiersPolicyService."
                "getSerialForPackage(java.lang.String, java.lang.String)' on a null object reference\n")
        other = ("NullPointerException: Attempt to invoke virtual method 'int java.lang.String.length()' on a null "
                 "object reference\n")
        self.assertEqual(evidence.null_service_interfaces(line + other, None),
                         ["android.os.IDeviceIdentifiersPolicyService"])
        self.assertEqual(evidence.null_service_interfaces(other), [])

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


    def test_a_witness_that_is_the_logs_last_word_names_the_death(self) -> None:
        """1688 (com.alibaba.wireless): the log ends on the shim's witness of a SIGSEGV in musl's
        loader, then its frame walk; no crash dump, no hilog report. NBA 2K: its audio thread's
        witness, then other threads' lines, then that thread's frame walk as the last line."""
        from westlake_gap import evidence, lifecycle
        asx = "/data/local/tmp/asx/"
        witness = ("[WESTLAKE-SIGNAL-WITNESS] signal=0xb code=0x1 tid=0x4cad thread=launcher-0 pc=0x7fa8758c10 "
                   "x30=0x7fa8753850 at /system/lib/ld-musl-aarch64.so.1+0x97c10 insn=0xa9400c02 next=0xb200c3e8 "
                   "from /system/lib/ld-musl-aarch64.so.1+0x92850 x0=0x768\n")
        frames = ("[WESTLAKE-SIGNAL-FRAMES] tid=0x4cad #0x1 /system/lib/ld-musl-aarch64.so.1+0x8f3cc"
                  " #0x2 %swebview-t-lib/libwebview_bionic_shim.so+0x14ad4 #0x3 %slibart.so+0xed49e4\n" % (asx, asx))
        text = "kRegJNI loop done\n[SOURCE-NATIVE-LOAD] path=%slib/arm64-v8a/libx.so\n" % asx + witness + frames
        self.assertEqual(evidence.final_witness(text)["thread"], "launcher-0")
        s = lifecycle.score("wireless", text)
        lifecycle.add_evidence(s, text, None)
        self.assertEqual((s.blocker_category, s.blocker),
                         ("native-crash", "SIGSEGV on thread launcher-0 at ld-musl-aarch64.so.1+0x97c10 "
                                          "(from ld-musl-aarch64.so.1+0x92850) (the log's last words: no crash dump, "
                                          "no hilog report)"))
        # Other threads' lines between the witness and its frame walk: still the last word.
        between = "".join("[WL-VULKAN] vkGetInstanceProcAddr(vkFn%d): no function\n" % i for i in range(20))
        late = "kRegJNI loop done\n" + witness.replace("launcher-0", "VCAUDIO3") + between + frames
        self.assertEqual(evidence.final_witness(late)["thread"], "VCAUDIO3")
        # Survived: the app went on logging (a library probing the CPU catches its own SIGILL).
        survived = text + "".join("[WESTLAKE-VSYNC] dispatchVsync #%d\n" % i for i in range(4))
        self.assertIsNone(evidence.final_witness(survived))
        s = lifecycle.score("wireless", survived)
        lifecycle.add_evidence(s, survived, None)
        self.assertNotEqual(s.blocker_category, "native-crash")
        # A frame walk for another thread does not extend the witness.
        other = text.replace("tid=0x4cad #0x1", "tid=0x1234 #0x1") + "a\nb\nc\n"
        self.assertIsNone(evidence.final_witness(other))

    def test_a_process_that_killed_itself(self) -> None:
        """Didi: its privacy module's timer called Process.killProcess(myPid()); Westlake logs the
        Java stack before the SIGKILL, and nothing else reports the death."""
        from westlake_gap import evidence, lifecycle
        stack = ("java.lang.Throwable: [WESTLAKE-KILL] the process sends itself signal 9\n"
                 "\tat android.os.Process.sendSignal(Native Method)\n"
                 "[WESTLAKE-WEBVIEW-BIONIC] property ro.product.model=X\n"
                 "\tat android.os.Process.killProcess(Unknown Source:2)\n"
                 "\tat com.didi.sdk.privacy.e.run(src:5)\n"
                 "\tat java.util.TimerThread.mainLoop(Unknown Source:116)\n")
        self.assertEqual(evidence.self_kill(stack),
                         {"frames": ["android.os.Process.sendSignal(Native Method)",
                                     "android.os.Process.killProcess(Unknown Source:2)",
                                     "com.didi.sdk.privacy.e.run(src:5)",
                                     "java.util.TimerThread.mainLoop(Unknown Source:116)"],
                          "first_app_frame": "com.didi.sdk.privacy.e.run(src:5)"})
        text = "kRegJNI loop done\n" + stack
        s = lifecycle.score("didi", text)
        lifecycle.add_evidence(s, text, None)
        self.assertEqual((s.blocker_category, s.blocker),
                         ("self-kill", "it killed its own process from com.didi.sdk.privacy.e.run(src:5)"))
        # SIGQUIT to itself asks for a thread dump; the process lives on.
        self.assertIsNone(evidence.self_kill(stack.replace("signal 9", "signal 3")))
        # An activity that finished itself first is the better account (Unity kills in onDestroy).
        hilog = ("10-05 08:30:20.900   942   942 I C00f00/AppSpawnX: Child process started, pid=1\n"
                 "10-05 08:30:22.380   942   967 I C00f00/OH_ACCAdapter: activityResumed: OnDrawListener attached "
                 "(token=android.os.Binder@1)\n"
                 "10-05 08:30:22.500   942   967 I C00f00/OH_ACCAdapter: finishActivity: no OH ability; "
                 "local destroy scheduled for android.os.Binder@1\n"
                 "10-05 08:30:23.191   942   967 W C00f00/OH_ACCAdapter: activityResumed (first-frame timeout): no OH token mapping\n")
        s = lifecycle.score("pokemon", text)
        s.screen = "host"
        lifecycle.add_evidence(s, text, None, None, hilog)
        self.assertEqual(s.blocker_category, "self-finish")
        self.assertIsNotNone(s.self_kill)


    def test_self_exit_names_the_last_library(self):
        """A process that calls exit() runs OH's static destructors: the IPC skeleton stops its threads
        and the window manager goes away, in the app's own hilog. Nothing else reports it."""
        from westlake_gap import evidence, lifecycle
        text = ("kRegJNI loop done\n"
                "[SOURCE-NATIVE-LOAD] path=/data/local/tmp/asx/lib/arm64-v8a/libc++_shared.so search=x\n"
                "[SOURCE-NATIVE-LOAD] path=/data/local/tmp/asx/lib/arm64-v8a/libgame.so search=x\n"
                "[WESTLAKE-SIGNAL-INSTALL] oh signal=31 flags=0x1c000004 handler=0x1 caller=0x2\n")
        hilog = ("11-11 01:41:45.827 25621 25621 I C00f00/AppSpawnX: Child process started, pid=25621\n"
                 "11-11 01:41:46.365 25621 25641 I C04204/WMSScb: window_manager.cpp ~WindowManager: destroyed, "
                 "userId: -1\n"
                 "11-11 01:41:46.426 25621 25641 I C057c1/ProcessSkeleton: NotifyChildThreadStop: waiting 3 child "
                 "threads to exit\n")
        self.assertEqual(evidence.self_exit(hilog, text), {"after_s": 0.5, "last_library": "libgame.so"})
        s = lifecycle.score("game", text)
        lifecycle.add_evidence(s, text, None, None, hilog)
        self.assertEqual((s.blocker_category, s.blocker),
                         ("self-exit", "it exited by itself 0.5 s after starting, with no crash; "
                                       "the last library it loaded was libgame.so"))
        # A process the harness ends at the close of its window logs no clean-up.
        quiet = hilog.split("\n")[0] + "\n11-11 01:42:20.000 25621 25621 I C00f00/X: still here\n"
        self.assertIsNone(evidence.self_exit(quiet, text))
        # Clean-up long before the log ends is not how the process ended.
        later = hilog + "11-11 01:41:50.000 25621 25621 I C00f00/X: still here\n"
        self.assertIsNone(evidence.self_exit(later, text))
        # Across midnight.
        wrapped = hilog.replace("01:41:45.827", "23:59:59.827").replace("01:41:46", "00:00:00")
        self.assertEqual(evidence.self_exit(wrapped, text)["after_s"], 0.5)

    def test_touch_before_finish_is_not_the_app(self):
        """The board forwards real touches: a release just before the last activity finished means a tap
        closed it, and the row is marked disturbed instead of the app finishing itself."""
        from westlake_gap import evidence, lifecycle
        text = "kRegJNI loop done\n"
        hilog = ("11-10 15:08:07.000   942   942 I C00f00/AppSpawnX: Child process started, pid=1\n"
                 "11-10 15:08:26.339   942   967 I C00f00/OH_ACCAdapter: activityResumed: OnDrawListener attached "
                 "(token=adapter.core.ActivityToken@2)\n"
                 "11-10 15:08:38.202   942   967 I C00f00/MotionEvent-aosp: [DIAG] nativeGetAction -> 1 (ptrs=1)\n"
                 "11-10 15:08:38.204   942   967 I C00f00/OH_ACCAdapter: finishActivity: no OH ability; "
                 "local destroy scheduled for adapter.core.ActivityToken@2\n")
        finished = evidence.self_finish(hilog)
        self.assertEqual(finished["touched_ms_before"], 2)
        s = lifecycle.score("keeta", text)
        s.screen = "host"
        lifecycle.add_evidence(s, text, None, None, hilog)
        self.assertEqual(s.blocker_category, "touched")
        self.assertFalse(s.blocking)
        # A touch long before the finish is not what closed it.
        early = hilog.replace("15:08:38.202", "15:08:30.000")
        self.assertNotIn("touched_ms_before", evidence.self_finish(early))
        s = lifecycle.score("keeta", text)
        s.screen = "host"
        lifecycle.add_evidence(s, text, None, None, early)
        self.assertEqual(s.blocker_category, "self-finish")

if __name__ == "__main__":
    unittest.main()
