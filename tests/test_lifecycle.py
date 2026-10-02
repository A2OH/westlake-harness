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


if __name__ == "__main__":
    unittest.main()
