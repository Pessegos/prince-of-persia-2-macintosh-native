import sys
import tkinter as tk
import unittest
from unittest.mock import patch

from pop2.window_aspect import constrain_window, sizing_rect


class SizingTests(unittest.TestCase):
    def test_each_drag_edge_keeps_the_opposite_edge_and_native_ratio(self):
        for edge in range(1, 9):
            for width, height in ((1400, 768), (1020, 1050), (400, 200)):
                padding = (16, 39)
                rect = (100, 80, 100 + width + 16, 80 + height + 39)
                left, top, right, bottom = sizing_rect(rect, edge, padding, (1020, 768))
                self.assertLessEqual(abs((right - left - 16) * 384
                                         - (bottom - top - 39) * 510), 255)
                self.assertGreaterEqual(right - left - 16, 510)
                self.assertGreaterEqual(bottom - top - 39, 384)
                self.assertEqual(right if edge in (1, 4, 7) else left,
                                 rect[2] if edge in (1, 4, 7) else rect[0])
                self.assertEqual(bottom if edge in (3, 4, 5) else top,
                                 rect[3] if edge in (3, 4, 5) else rect[1])

    def test_widening_a_side_also_increases_height(self):
        self.assertEqual(sizing_rect((0, 0, 1275, 768), 2, previous_size=(1020, 768)),
                         (0, 0, 1275, 960))

    @unittest.skipUnless(sys.platform == 'win32', 'Native Windows resize message')
    def test_windows_sizing_message_accounts_for_frame_and_debug_status(self):
        import ctypes
        from ctypes import wintypes
        root = tk.Tk()
        root.attributes('-alpha', 0)
        canvas = tk.Canvas(root, highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        label = tk.Label(root, text='Debug status')
        label.pack(fill='x')
        root.geometry('1020x800')
        root.update()
        enabled = [True]
        constraint = constrain_window(root, canvas, lambda: enabled[0])
        try:
            constraint.user.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                                      wintypes.WPARAM, wintypes.LPARAM]
            constraint.user.SendMessageW.restype = ctypes.c_ssize_t
            outer, client = wintypes.RECT(), wintypes.RECT()
            constraint.user.GetWindowRect(constraint.hwnd, ctypes.byref(outer))
            constraint.user.GetClientRect(constraint.hwnd, ctypes.byref(client))
            px = outer.right - outer.left - client.right
            py = outer.bottom - outer.top - client.bottom + label.winfo_height()
            rect = wintypes.RECT(100, 100, 100 + 1275 + px, 100 + 800 + py)
            with patch.object(root, 'winfo_width', side_effect=AssertionError('Reentrant Tcl call')), \
                    patch.object(canvas, 'winfo_width', side_effect=AssertionError('Reentrant Tcl call')):
                constraint.user.SendMessageW(constraint.hwnd, 0x214, 2, ctypes.addressof(rect))
            self.assertEqual(rect.bottom - rect.top - py, 960)
            enabled[0] = False
            rect = wintypes.RECT(100, 100, 1500, 800)
            constraint.user.SendMessageW(constraint.hwnd, 0x214, 2, ctypes.addressof(rect))
            self.assertEqual((rect.left, rect.top, rect.right, rect.bottom), (100, 100, 1500, 800))
        finally:
            root.destroy()

    @unittest.skipUnless(sys.platform == 'win32', 'Native Tk wrapper lifecycle')
    def test_first_map_and_fullscreen_keep_hook_on_the_current_wrapper(self):
        import ctypes
        from ctypes import wintypes
        root = tk.Tk()
        root.withdraw()
        root.attributes('-alpha', 0)
        canvas = tk.Canvas(root, highlightthickness=0)
        canvas.pack(fill='both', expand=True)
        root.geometry('1020x768')
        constraint = constrain_window(root, canvas, lambda: True)
        self.assertIsNone(constraint.hwnd)
        try:
            root.deiconify()
            root.update()
            for fullscreen in (False, True, False):
                root.attributes('-fullscreen', fullscreen)
                root.update()
                self.assertEqual(constraint.hwnd, constraint.user.GetAncestor(root.winfo_id(), 2))
            send = constraint.user.SendMessageW
            send.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            send.restype = ctypes.c_ssize_t
            px, py = constraint.padding
            rect = wintypes.RECT(0, 0, 1275 + px, 768 + py)
            send(constraint.hwnd, 0x214, 2, ctypes.addressof(rect))
            self.assertEqual(rect.bottom - py, 960)
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
