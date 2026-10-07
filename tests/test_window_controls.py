import json
import subprocess
import sys
import textwrap
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pop2.window_controls import is_resume_key


class ResumeKeyTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows virtual-key events")
    def test_windows_tk_media_and_navigation_events_cannot_resume(self):
        result = subprocess.run([sys.executable, "-c", textwrap.dedent("""
            import json
            import tkinter as tk
            from pop2.window_controls import is_resume_key

            root = tk.Tk()
            root.withdraw()
            seen = []
            root.bind('<KeyPress>', lambda e: seen.append([e.keycode, is_resume_key(e)]))
            root.deiconify()
            root.update()
            root.focus_force()
            root.update()
            for code in (*range(0xAD, 0xB4), 0x21, 0x22, 0x23, 0x24, 0x2D, 0x2E, 0x41):
                root.event_generate('<KeyPress>', keycode=code)
                root.event_generate('<KeyRelease>', keycode=code)
            root.destroy()
            print(json.dumps(seen))
        """)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        expected = [[code, False] for code in
                    (*range(0xAD, 0xB4), 0x21, 0x22, 0x23, 0x24, 0x2D, 0x2E)]
        self.assertEqual(json.loads(result.stdout), [*expected, [0x41, True]])

    def test_windows_media_and_browser_codes_cannot_resume_even_with_printable_text(self):
        with patch("pop2.window_controls.sys.platform", "win32"):
            for code in range(0xA6, 0xB8):
                with self.subTest(code=code):
                    event = SimpleNamespace(keysym="a", char="a", keycode=code, state=0)
                    self.assertFalse(is_resume_key(event))

    def test_navigation_keys_cannot_resume_even_with_printable_text(self):
        for key in ("Insert", "Delete", "Home", "End", "Prior", "Next",
                    "KP_Insert", "KP_Delete", "KP_Home", "KP_End", "KP_Prior", "KP_Next"):
            with self.subTest(key=key):
                event = SimpleNamespace(keysym=key, char="x", state=0)
                self.assertFalse(is_resume_key(event))
        with patch("pop2.window_controls.sys.platform", "win32"):
            for code in (0x21, 0x22, 0x23, 0x24, 0x2D, 0x2E):
                with self.subTest(code=code):
                    event = SimpleNamespace(keysym="a", char="a", keycode=code, state=0)
                    self.assertFalse(is_resume_key(event))

    def test_special_and_unknown_symbols_never_resume_via_the_character_fallback(self):
        for key in ("XF86AudioMute", "XF86AudioLowerVolume", "XF86AudioRaiseVolume",
                    "XF86AudioPlay", "F12", "Control_L", "Caps_Lock", "??", "NoSymbol"):
            with self.subTest(key=key):
                self.assertFalse(is_resume_key(SimpleNamespace(keysym=key, char="x", state=0)))

    def test_windows_text_arrows_and_keypad_still_resume(self):
        with patch("pop2.window_controls.sys.platform", "win32"):
            for key, char, code in (("a", "a", 0x41), ("A", "A", 0x41),
                                    ("ccedilla", "\u00e7", 0xBA), ("less", "<", 0xE2),
                                    ("period", ".", 0xBE), ("space", " ", 0x20),
                                    ("Left", "", 0x25), ("KP_0", "0", 0x60),
                                    ("Return", "\r", 0x0D)):
                with self.subTest(key=key):
                    self.assertTrue(is_resume_key(
                        SimpleNamespace(keysym=key, char=char, keycode=code, state=0)))

    def test_non_windows_keycodes_are_not_interpreted_as_virtual_keys(self):
        with patch("pop2.window_controls.sys.platform", "linux"):
            self.assertTrue(is_resume_key(
                SimpleNamespace(keysym="minus", char="-", keycode=0x2D, state=0)))


if __name__ == "__main__":
    unittest.main()
