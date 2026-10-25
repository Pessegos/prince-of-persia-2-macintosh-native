import json
import struct
import subprocess
import sys
import textwrap
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from pop2.app_window import ICON_DIR, create_root
from tools.build_app_icon import build_icon

from tests.desktop import exclusive_desktop


def native_icon_image(icon):
    import ctypes as C
    from ctypes import wintypes as W

    class IconInfo(C.Structure):
        _fields_ = [("is_icon", W.BOOL), ("hotspot_x", W.DWORD), ("hotspot_y", W.DWORD),
                    ("mask", W.HBITMAP), ("color", W.HBITMAP)]

    class Bitmap(C.Structure):
        _fields_ = [("type", W.LONG), ("width", W.LONG), ("height", W.LONG),
                    ("stride", W.LONG), ("planes", W.WORD), ("bits", W.WORD),
                    ("pixels", C.c_void_p)]

    user, gdi = C.windll.user32, C.windll.gdi32
    user.GetIconInfo.argtypes = [C.c_void_p, C.POINTER(IconInfo)]
    gdi.GetObjectW.argtypes = [W.HANDLE, C.c_int, C.c_void_p]
    gdi.CreateCompatibleDC.argtypes = [W.HDC]
    gdi.CreateCompatibleDC.restype = W.HDC
    gdi.GetDIBits.argtypes = [W.HDC, W.HBITMAP, W.UINT, W.UINT,
                            C.c_void_p, C.c_void_p, W.UINT]
    gdi.DeleteObject.argtypes = [W.HANDLE]
    gdi.DeleteDC.argtypes = [W.HDC]
    info = IconInfo()
    assert user.GetIconInfo(icon, C.byref(info))
    dc = gdi.CreateCompatibleDC(None)
    try:
        bitmap = Bitmap()
        assert gdi.GetObjectW(info.color, C.sizeof(bitmap), C.byref(bitmap))
        width, height = bitmap.width, bitmap.height
        pixels = C.create_string_buffer(width * height * 4)
        header = C.create_string_buffer(struct.pack(
            "<IiiHHIIiiII", 40, width, -height, 1, 32, 0, len(pixels), 0, 0, 0, 0))
        assert gdi.GetDIBits(dc, info.color, 0, height, pixels, header, 0) == height
        return Image.frombytes("RGBA", (width, height), pixels.raw, "raw", "BGRA")
    finally:
        gdi.DeleteDC(dc)
        gdi.DeleteObject(info.color)
        gdi.DeleteObject(info.mask)


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
                             ["identity", "root", "root().iconbitmap", "root().bind"])
            identity.assert_called_once_with("Pessegos.PrinceOfPersia2.MacintoshNative")
            icon = str(ICON_DIR / "prince.ico")
            self.assertEqual(root.iconbitmap.call_args_list,
                             [((), {"default": icon})])
            event, apply_icon = root.bind.call_args.args
            self.assertEqual(event, '<Map>')
            apply_icon(SimpleNamespace(widget=object()))
            self.assertEqual(root.iconbitmap.call_count, 1)
            apply_icon(SimpleNamespace(widget=root))
            self.assertEqual(root.iconbitmap.call_args.args, (icon,))
            root.unbind.assert_called_once_with('<Map>', root.bind.return_value)

    @unittest.skipUnless(sys.platform == "win32", "Windows root mapping")
    def test_icon_setup_does_not_map_a_provisional_small_window(self):
        root = create_root()
        try:
            self.assertFalse(root.winfo_ismapped())
            # Fit the CI desktop work area; Windows clamps taller windows.
            root.geometry('510x384')
            mapped = []
            root.bind('<Map>', lambda event: mapped.append(
                (root.winfo_width(), root.winfo_height())) if event.widget is root else None, add='+')
            root.update()
            self.assertTrue(mapped)
            self.assertEqual(mapped, [(510, 384)])
        finally:
            root.destroy()

    def test_windows_sizes_preserve_source_pixels_and_transparency(self):
        with Image.open(ICON_DIR / "prince.png") as source, \
                Image.open(ICON_DIR / "prince.ico") as icon:
            self.assertEqual(source.size, (512, 512))
            self.assertEqual(source.mode, "RGBA")
            self.assertEqual(source.getchannel("A").getextrema(), (0, 255))
            sizes = {(size, size) for size in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)}
            self.assertEqual(icon.ico.sizes(), sizes)
            for size in sizes:
                with self.subTest(size=size):
                    expected = source.resize(size, Image.Resampling.NEAREST)
                    self.assertEqual(icon.ico.getimage(size).tobytes(), expected.tobytes())

    def test_every_ico_frame_uses_native_bitmap_encoding(self):
        data = (ICON_DIR / "prince.ico").read_bytes()
        reserved, kind, count = struct.unpack_from("<HHH", data)
        self.assertEqual((reserved, kind, count), (0, 1, 10))
        for index in range(count):
            width, height, _colors, _reserved, _planes, bits, length, offset = (
                struct.unpack_from("<BBBBHHII", data, 6 + 16 * index))
            width, height = width or 256, height or 256
            self.assertEqual(bits, 32)
            self.assertEqual(struct.unpack_from("<Iii", data, offset), (40, width, height * 2))
            self.assertEqual(len(data[offset:offset + length]), length)

    def test_builder_reproduces_bundled_icon(self):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as temporary:
            output = build_icon(output=Path(temporary) / "prince.ico")
            self.assertEqual(output.read_bytes(), (ICON_DIR / "prince.ico").read_bytes())

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
    @exclusive_desktop('mapped native roots and their icons')
    def test_real_windows_roots_are_pixel_exact_and_children_inherit_icon(self):
        result = subprocess.run([sys.executable, "-c", textwrap.dedent("""
            import ctypes
            from ctypes import wintypes
            import tkinter as tk
            from PIL import Image
            from pop2.app_window import APP_ID, ICON_DIR, create_root
            from tests.test_app_window import native_icon_image

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
            with Image.open(ICON_DIR / 'prince.png') as source:
                source = source.convert('RGBA')
            for _ in range(2):
                root = create_root()
                root.geometry('1020x768')
                root.update()
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
                            if window is not root:
                                continue
                            actual = native_icon_image(icon)
                            size = user.GetSystemMetrics(49 if kind == 0 else 11)
                            assert actual.size == (size, size), 'wrong native icon size'
                            expected = source.resize(actual.size, Image.Resampling.NEAREST)
                            for color in ('#202020', '#eeeeee'):
                                backdrop = Image.new('RGBA', actual.size, color)
                                visible = Image.alpha_composite(backdrop, actual)
                                reference = Image.alpha_composite(backdrop, expected)
                                assert visible.tobytes() == reference.tobytes(), 'smoothed icon'
                finally:
                    root.destroy()
            print('true')
        """)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
