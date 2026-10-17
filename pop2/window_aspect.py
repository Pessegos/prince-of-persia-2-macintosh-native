"""Keep interactive window resizing proportional without stretching pixels."""

import sys

from pop2.game_ui import VISIBLE_SIZE


def sizing_rect(rect, edge, padding=(0, 0), previous_size=VISIBLE_SIZE):
    left, top, right, bottom = rect
    width = max(VISIBLE_SIZE[0], right - left - padding[0])
    height = max(VISIBLE_SIZE[1], bottom - top - padding[1])
    use_width = edge in (1, 2)
    if edge in (4, 5, 7, 8):
        use_width = (abs(width - previous_size[0]) / VISIBLE_SIZE[0]
                     >= abs(height - previous_size[1]) / VISIBLE_SIZE[1])
    if use_width:
        height = round(width * VISIBLE_SIZE[1] / VISIBLE_SIZE[0])
    else:
        width = round(height * VISIBLE_SIZE[0] / VISIBLE_SIZE[1])
    width += padding[0]
    height += padding[1]
    if edge in (1, 4, 7):
        left = right - width
    else:
        right = left + width
    if edge in (3, 4, 5):
        top = bottom - height
    else:
        bottom = top + height
    return left, top, right, bottom


class WindowAspect:
    """WM_SIZING handles side drags; Tk's wm aspect is ignored on Windows."""

    def __init__(self, root, canvas, enabled):
        import ctypes
        from ctypes import wintypes

        self.root, self.canvas, self.enabled = root, canvas, enabled
        self.user = ctypes.WinDLL('user32', use_last_error=True)
        self.controls = ctypes.WinDLL('comctl32', use_last_error=True)
        self.user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user.GetAncestor.restype = wintypes.HWND
        self.user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.user.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        self.hwnd = None
        self.padding = (0, 0)
        self.previous_size = VISIBLE_SIZE
        callback_type = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND,
                                          wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
                                          ctypes.c_size_t, ctypes.c_size_t)
        self.controls.SetWindowSubclass.argtypes = [wintypes.HWND, callback_type,
                                                   ctypes.c_size_t, ctypes.c_size_t]
        self.controls.SetWindowSubclass.restype = wintypes.BOOL
        self.controls.RemoveWindowSubclass.argtypes = [wintypes.HWND, callback_type, ctypes.c_size_t]
        self.controls.DefSubclassProc.argtypes = [wintypes.HWND, wintypes.UINT,
                                                 wintypes.WPARAM, wintypes.LPARAM]
        self.controls.DefSubclassProc.restype = ctypes.c_ssize_t

        @callback_type
        def callback(hwnd, message, edge, address, subclass_id, data):
            if message == 0x214 and self.enabled():  # WM_SIZING
                rect = ctypes.cast(address, ctypes.POINTER(wintypes.RECT)).contents
                adjusted = sizing_rect((rect.left, rect.top, rect.right, rect.bottom), edge,
                                       self.padding, self.previous_size)
                rect.left, rect.top, rect.right, rect.bottom = adjusted
                return 1
            if message == 0x82:  # WM_NCDESTROY
                self.controls.RemoveWindowSubclass(hwnd, self.callback, subclass_id)
                if self.hwnd == hwnd:
                    self.hwnd = None
            return self.controls.DefSubclassProc(hwnd, message, edge, address)

        self.callback = callback
        root.bind('<Map>', self.mapped, add='+')
        canvas.bind('<Configure>', self.refresh_metrics, add='+')
        if root.winfo_ismapped():
            self.install()

    def mapped(self, event):
        if event.widget is self.root:
            self.install()

    def install(self):
        import ctypes
        hwnd = self.user.GetAncestor(self.root.winfo_id(), 2)
        if hwnd == self.hwnd:
            return
        if self.hwnd is not None:
            self.controls.RemoveWindowSubclass(self.hwnd, self.callback, id(self))
        # Tk can replace its outer HWND when first mapped or changing window
        # attributes. Hook the mapped wrapper, not the provisional hidden one.
        self.hwnd = hwnd
        if not self.controls.SetWindowSubclass(hwnd, self.callback, id(self), 0):
            raise ctypes.WinError(ctypes.get_last_error())
        self.refresh_metrics()

    def refresh_metrics(self, event=None):
        import ctypes
        from ctypes import wintypes
        if self.hwnd is None:
            return
        outer, client = wintypes.RECT(), wintypes.RECT()
        self.user.GetWindowRect(self.hwnd, ctypes.byref(outer))
        self.user.GetClientRect(self.hwnd, ctypes.byref(client))
        width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
        # Never enter Tcl inside the native subclass callback. Reentrant Tk
        # calls there invalidate _tkinter's thread-state bookkeeping.
        self.padding = (outer.right - outer.left - client.right + self.root.winfo_width() - width,
                        outer.bottom - outer.top - client.bottom + self.root.winfo_height() - height)
        self.previous_size = (width, height)


def constrain_window(root, canvas, enabled):
    root.aspect(*VISIBLE_SIZE, *VISIBLE_SIZE)
    if sys.platform == 'win32':
        return WindowAspect(root, canvas, enabled)
    return None
