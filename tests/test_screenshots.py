import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from pop2.game_ui import VISIBLE_VIEWPORT
from pop2.game_menu import GameMenu
from pop2.screenshots import ScreenshotSettings, save_screenshot
from pop2.window_controls import WindowControls


class ScreenshotTests(unittest.TestCase):
    def test_native_crop_integer_scaling_and_source_pixels_are_preserved(self):
        viewport = Image.new("RGBA", (512, 384), "magenta")
        viewport.paste("blue", VISIBLE_VIEWPORT)
        viewport.putpixel((101, 100), (255, 255, 255, 255))
        original = viewport.tobytes()
        with TemporaryDirectory() as directory:
            for scale in range(1, 5):
                with self.subTest(scale=scale):
                    path = save_screenshot(viewport, ScreenshotSettings(Path(directory), scale))
                    with Image.open(path) as image:
                        self.assertEqual(image.format, "PNG")
                        self.assertEqual(image.mode, "RGB")
                        self.assertEqual(image.size, (510 * scale, 384 * scale))
                        expected = viewport.crop(VISIBLE_VIEWPORT).convert("RGB").resize(
                            image.size, Image.Resampling.NEAREST)
                        self.assertEqual(image.tobytes(), expected.tobytes())
            self.assertEqual(len(list(Path(directory).glob("*.png"))), 4)
        self.assertEqual(viewport.tobytes(), original)

    def test_default_directory_is_created_and_existing_png_is_never_overwritten(self):
        with TemporaryDirectory() as directory:
            settings = ScreenshotSettings(Path(directory) / "new folder", 1)
            viewport = Image.new("RGBA", (512, 384), "blue")
            with patch("pop2.screenshots.datetime") as clock:
                clock.now.return_value.strftime.return_value = "fixed-time"
                first = save_screenshot(viewport, settings)
                viewport.paste("red", (0, 0, 512, 384))
                second = save_screenshot(viewport, settings)
            self.assertNotEqual(first, second)
            with Image.open(first) as image:
                self.assertEqual(image.getpixel((0, 0)), (0, 0, 255))
            with Image.open(second) as image:
                self.assertEqual(image.getpixel((0, 0)), (255, 0, 0))

    def test_folder_and_size_persist_and_bad_settings_fall_back_to_defaults(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "settings" / "capture.json"
            settings = ScreenshotSettings((Path(directory) / "chosen folder").resolve(), 4)
            settings.save(path)
            self.assertEqual(ScreenshotSettings.load(path), settings)
            for value in ("broken JSON", "[]", json.dumps({"folder": 42, "scale": True}),
                          json.dumps({"folder": "relative", "scale": 99})):
                path.write_text(value, encoding="utf-8")
                self.assertEqual(ScreenshotSettings.load(path), ScreenshotSettings())
            self.assertEqual(ScreenshotSettings.load(path.with_name("missing.json")), ScreenshotSettings())

    def test_failed_png_write_does_not_leave_a_partial_file(self):
        with TemporaryDirectory() as directory:
            settings = ScreenshotSettings(Path(directory), 1)
            with patch.object(Image.Image, "save", side_effect=OSError("Disk full")):
                with self.assertRaises(OSError):
                    save_screenshot(Image.new("RGBA", (512, 384)), settings)
            self.assertEqual(list(Path(directory).iterdir()), [])


class CaptureMenuTests(unittest.TestCase):
    def test_size_folder_capture_and_back_are_keyboard_and_mouse_accessible(self):
        menu = GameMenu(page="screenshots")
        menu.key("Return")
        menu.key("Down")
        menu.key("Return")
        self.assertEqual(menu.screenshot_scale, 4)
        self.assertFalse(menu.dropdown)
        menu.key("Down")
        self.assertEqual(menu.key("Return"), "screenshot_folder")
        menu.key("Left")
        self.assertEqual(menu.focus, 1)
        self.assertEqual(menu.click(150, 267), "screenshot")
        self.assertEqual(menu.click(290, 267), "changed")
        self.assertEqual(menu.page, "menu")

    def test_capture_controls_do_not_require_developer_tools(self):
        menu = GameMenu(development=False)
        item = next(item for item in menu.items if item.action == "screenshots")
        self.assertTrue(item.enabled)
        menu.show_page("screenshots")
        menu.focus = 2
        self.assertEqual(menu.activate(), "screenshot")

    def test_escape_closes_the_size_popup_before_returning_to_the_game_menu(self):
        menu = GameMenu(page="screenshots")
        menu.key("Return")
        menu.key("Down")
        menu.key("Escape")
        self.assertEqual(menu.screenshot_scale, 3)
        self.assertEqual(menu.page, "screenshots")
        menu.key("Escape")
        self.assertEqual(menu.page, "menu")


class WindowScreenshotTests(unittest.TestCase):
    def setUp(self):
        self.host = WindowControls()
        self.host.root = Mock()
        self.host.status = Mock()
        self.host.render = Mock()
        self.host.clear_keys = Mock()
        self.host.window_keys_down = set()
        self.host.pause_resume_keys = set()
        self.host.paused = True
        self.host.dev_menu = None
        self.host.game_menu = GameMenu(page="screenshots")
        self.host.screenshot_settings = ScreenshotSettings()
        self.host.screenshot_viewport = Image.new("RGBA", (512, 384), "blue")

    def test_f8_does_not_repeat_resume_pause_or_skip_a_cutscene(self):
        host = self.host
        host.intro = object()
        with patch.object(host, "capture_screenshot") as capture:
            event = SimpleNamespace(keysym="F8", state=0)
            self.assertEqual(host.dev_key_press(event), "break")
            host.dev_key_press(event)
            capture.assert_called_once_with()
            self.assertTrue(host.paused)
            host.dev_key_release(event)
            host.dev_key_press(event)
            self.assertEqual(capture.call_count, 2)
            host.dev_key_release(event)
            host.dev_key_press(SimpleNamespace(keysym="F8", state=0x8))
            self.assertEqual(capture.call_count, 2)

    def test_capture_uses_clean_buffer_and_keeps_menu_and_pause(self):
        host = self.host
        host.native_viewport = Image.new("RGBA", (512, 384), "red")
        with TemporaryDirectory() as directory:
            host.screenshot_settings = ScreenshotSettings(Path(directory), 1)
            path = host.capture_screenshot()
            with Image.open(path) as image:
                self.assertEqual(image.getpixel((0, 0)), (0, 0, 255))
        self.assertTrue(host.paused)
        self.assertIsNotNone(host.game_menu)
        self.assertEqual(host.game_menu.screenshot_status, "PNG saved")

    def test_write_failure_keeps_menu_open_and_reports_inline_error(self):
        host = self.host
        with patch("pop2.window_controls.save_screenshot", side_effect=PermissionError()):
            self.assertIsNone(host.capture_screenshot())
        self.assertIn("Could not save", host.game_menu.error)
        self.assertTrue(host.paused)
        host.render.assert_called_once_with()

    def test_folder_dialog_cancel_and_success_preserve_pause_state(self):
        host = self.host
        host.game_was_paused = False
        host.window_keys_down.add("Return")
        original = host.screenshot_settings.folder

        def dialog(**kwargs):
            self.assertIs(kwargs["parent"], host.root)
            host.pause_if_unfocused()
            self.assertFalse(host.game_was_paused)
            return ""

        with patch("pop2.window_controls.filedialog.askdirectory", side_effect=dialog):
            host.choose_screenshot_folder()
        self.assertEqual(host.screenshot_settings.folder, original)
        self.assertFalse(host.screenshot_dialog_active)
        self.assertIn("Return", host.pause_resume_keys)
        with TemporaryDirectory() as directory:
            with patch("pop2.window_controls.filedialog.askdirectory", return_value=directory), \
                    patch.object(ScreenshotSettings, "save") as save:
                host.choose_screenshot_folder()
                save.assert_called_once_with()
            self.assertEqual(host.screenshot_settings.folder, Path(directory).resolve())
            self.assertEqual(host.game_menu.screenshot_folder, str(Path(directory).resolve()))
        self.assertTrue(host.paused)


if __name__ == "__main__":
    unittest.main()
