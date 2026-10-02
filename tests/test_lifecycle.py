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


if __name__ == "__main__":
    unittest.main()
