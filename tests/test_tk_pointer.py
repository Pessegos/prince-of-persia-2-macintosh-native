import ctypes
import sys
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pop2 import tk_pointer
from pop2.tk_pointer import refresh_pointer
from tests.desktop import exclusive_desktop


class PointerRefreshTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)

    @unittest.skipUnless(sys.platform == 'win32', "Tk's pointer function is Windows Tk's")
    def test_tk_is_asked_for_the_window_under_the_pointer_where_it_is_on_the_screen(self):
        calls = []

        def pointer_event(hwnd, x, y):
            calls.append((hwnd, x, y))

        library = SimpleNamespace(Tk_PointerEvent=pointer_event)
        with patch.dict(tk_pointer._refreshers, clear=True), \
                patch.object(tk_pointer, 'tk_library', return_value=library):
            self.assertTrue(refresh_pointer(self.root))
        from ctypes import wintypes
        point = wintypes.POINT()
        ctypes.WinDLL('user32').GetCursorPos(ctypes.byref(point))
        # No window: Tk finds the one under the point, as its own pointer timer does.
        self.assertEqual(calls, [(None, point.x, point.y)])

    def test_without_tks_function_nothing_is_asked(self):
        with patch.dict(tk_pointer._refreshers, clear=True), \
                patch.object(tk_pointer, 'tk_library', return_value=None):
            self.assertFalse(refresh_pointer(self.root))
            self.assertIsNone(tk_pointer._refreshers[self.root.tk.interpaddr()])

    @unittest.skipUnless(sys.platform == 'win32', "Tk's pointer function is Windows Tk's")
    def test_the_tk_in_use_is_asked_without_events_for_a_pointer_that_did_not_move(self):
        events = []
        canvas = tk.Canvas(self.root)
        canvas.pack()
        for sequence in ('<Motion>', '<Enter>', '<Leave>'):
            canvas.bind(sequence, lambda event: events.append(event.type))
        if not refresh_pointer(self.root):
            self.skipTest("Tk's own function is not reachable here")
        self.root.update()
        self.assertEqual(events, [])


@unittest.skipUnless(sys.platform == 'win32', "Windows Tk's cursor")
class ShownCursorTests(unittest.TestCase):
    """What the window's cursor relies on, in the Tk in use: a canvas with no cursor of its
    own shows its toplevel's, and Tk's pointer function puts it on the screen at once."""

    @exclusive_desktop('maps a transparent window off the screen and hands focus back')
    def test_a_canvas_without_a_cursor_shows_its_toplevels_once_tk_updates_the_pointer(self):
        user32 = ctypes.WinDLL('user32')
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        user32.SetForegroundWindow.argtypes = (ctypes.c_void_p,)
        user32.GetCursor.restype = ctypes.c_void_p
        user32.LoadCursorW.argtypes = (ctypes.c_void_p, ctypes.c_void_p)
        user32.LoadCursorW.restype = ctypes.c_void_p
        user32.SendMessageW.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)
        arrow, hand = user32.LoadCursorW(None, 32512), user32.LoadCursorW(None, 32649)
        foreground = user32.GetForegroundWindow()
        root = tk.Tk()
        self.addCleanup(root.destroy)
        root.withdraw()
        root.overrideredirect(True)
        root.attributes('-alpha', 0.0)
        root.geometry('200x100+-4000+0')
        canvas = tk.Canvas(root, width=200, height=100, highlightthickness=0)
        canvas.pack()
        root.deiconify()
        root.update()
        user32.SetForegroundWindow(foreground)
        library = tk_pointer.tk_library(root.tk)
        if library is None:
            self.skipTest("Tk's own functions are not reachable here")
        pointer_event = library.Tk_PointerEvent
        pointer_event.argtypes, pointer_event.restype = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int), None
        hwnd = canvas.winfo_id()
        user32.SendMessageW(hwnd, 0x200, 0, (50 << 16) | 50)   # the pointer over the canvas
        root.update()
        self.assertEqual(user32.GetCursor(), arrow)
        root.configure(cursor='hand2')
        self.assertEqual(user32.GetCursor(), arrow, 'not shown until Tk updates the pointer')
        # The window is off the screen, so it is named here; the game's has the pointer over it.
        pointer_event(hwnd, 50, 50)
        self.assertEqual(user32.GetCursor(), hand)
        self.assertEqual(str(canvas.cget('cursor')), '')
        root.configure(cursor='')
        pointer_event(hwnd, 50, 50)
        self.assertEqual(user32.GetCursor(), arrow)
        root.update()   # what mapping the window queued, before it is destroyed


if __name__ == '__main__':
    unittest.main()
