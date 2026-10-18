import json
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from pop2.app_window import ICON_DIR, create_root


class ApplicationIconTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == "win32", "Windows application identity API")
    def test_windows_identity_precedes_root_and_icon_is_default_for_dialogs(self):
        with patch("ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID") as identity, \
                patch("pop2.app_window.tk.Tk") as tk_root:
            calls = Mock()
            calls.attach_mock(identity, "identity")
            calls.attach_mock(tk_root, "root")
            root = create_root()
            self.assertEqual([call[0] for call in calls.mock_calls],
                             ["identity", "root", "root().iconbitmap"])
            identity.assert_called_once_with("Pessegos.PrinceOfPersia2.MacintoshNative")
            icon = str(ICON_DIR / "prince.ico")
            root.iconbitmap.assert_called_once_with(bitmap=icon, default=icon)

    def test_windows_sizes_preserve_source_pixels_and_transparency(self):
        with Image.open(ICON_DIR / "prince.png") as source, \
                Image.open(ICON_DIR / "prince.ico") as icon:
            self.assertEqual(source.size, (512, 512))
            self.assertEqual(source.mode, "RGBA")
            self.assertEqual(source.getchannel("A").getextrema(), (0, 255))
            sizes = {(size, size) for size in (16, 24, 32, 48, 64, 128, 256)}
            self.assertEqual(icon.ico.sizes(), sizes)
            for size in sizes:
                with self.subTest(size=size):
                    expected = source.resize(size, Image.Resampling.NEAREST)
                    self.assertEqual(icon.ico.getimage(size).tobytes(), expected.tobytes())

    def test_other_platforms_apply_default_icon_and_retain_photo_references(self):
        source = Mock()
        with patch("pop2.app_window.sys.platform", "linux"), \
                patch("pop2.app_window.tk.Tk") as tk_root, \
                patch("pop2.app_window.tk.PhotoImage", return_value=source) as photo:
            root = create_root()
            self.assertIs(root, tk_root.return_value)
            photo.assert_called_once_with(master=root, file=str(ICON_DIR / "prince.png"))
            self.assertEqual(source.subsample.call_args_list, [((8,),), ((16,),)])
            root.iconphoto.assert_called_once_with(True, *root._app_icon_images)
            root.iconbitmap.assert_not_called()

    @unittest.skipUnless(sys.platform == "win32", "Windows window and taskbar icons")
    def test_real_windows_roots_and_children_use_bundled_icon(self):
        result = subprocess.run([sys.executable, "-c", textwrap.dedent("""
            import ctypes
            from ctypes import wintypes
            import tkinter as tk
            from pop2.app_window import APP_ID, create_root

            user = ctypes.windll.user32
            user.GetParent.argtypes = [wintypes.HWND]
            user.GetParent.restype = wintypes.HWND
            user.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                         wintypes.WPARAM, wintypes.LPARAM]
            user.SendMessageW.restype = ctypes.c_void_p
            user.GetClassLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
            user.GetClassLongPtrW.restype = ctypes.c_void_p
            get_id = ctypes.windll.shell32.GetCurrentProcessExplicitAppUserModelID
            get_id.argtypes = [ctypes.POINTER(ctypes.c_wchar_p)]
            get_id.restype = ctypes.c_long
            ctypes.windll.ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
            for _ in range(2):
                root = create_root()
                root.withdraw()
                try:
                    identity = ctypes.c_wchar_p()
                    assert get_id(ctypes.byref(identity)) == 0
                    assert identity.value == APP_ID
                    ctypes.windll.ole32.CoTaskMemFree(ctypes.cast(identity, ctypes.c_void_p))
                    child = tk.Toplevel(root)
                    child.withdraw()
                    root.update_idletasks()
                    for window in (root, child):
                        hwnd = user.GetParent(window.winfo_id())
                        # Tk's default icons live on the native window class.
                        for kind, index in ((0, -34), (1, -14)):
                            icon = (user.SendMessageW(hwnd, 0x7F, kind, 0)
                                    or user.GetClassLongPtrW(hwnd, index))
                            assert icon, 'missing window icon'
                finally:
                    root.destroy()
            print('true')
        """)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
