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


if __name__ == "__main__":
    unittest.main()
