"""Showing a changed cursor at once, without Tk painting the canvas again.

A Tk window with no cursor of its own shows the cursor of the window around it, so
the game's window shows its toplevel's cursor. Giving the cursor to the canvas
instead, even the cursor it already has, makes Tk paint all of the canvas again:
about 8 ms at 3440x1440, at times 30-70 ms, for each option the pointer reached or
left where the cursor changes. Changing the toplevel's costs nothing to paint.

On Windows, Tk puts a cursor on the screen when the pointer moves over its windows,
and every 250 ms while it rests there: a cursor given to the window under the
pointer shows at once, one given to the toplevel only then. refresh_pointer asks Tk
to do at once what its timer does, through Tk's own function. Elsewhere, or when
that function cannot be reached, it does nothing and the cursor shows when the
pointer next moves.
"""

import ctypes
import sys
from _tkinter import TclError

from pop2.tk_photo import tk_library

_refreshers = {}   # Tcl interpreter's address -> refresh(), or None


def _refresher(interp):
    if sys.platform != 'win32':
        return None
    library = tk_library(interp)
    if library is None:
        return None
    from ctypes import wintypes

    update = library.Tk_PointerEvent
    update.argtypes, update.restype = (ctypes.c_void_p, ctypes.c_int, ctypes.c_int), None
    where = ctypes.WinDLL('user32').GetCursorPos
    where.argtypes, where.restype = (ctypes.POINTER(wintypes.POINT),), wintypes.BOOL

    def refresh():
        point = wintypes.POINT()
        if not where(ctypes.byref(point)):
            return False
        # No window: the point is on the screen, and Tk finds the window under it,
        # as its pointer timer does. The pointer has not moved, so Tk sends no event.
        update(None, point.x, point.y)
        return True

    return refresh


def refresh_pointer(widget):
    """Have Tk set the cursor for the window under the pointer now, rather than when
    the pointer next moves. True when Tk was asked."""
    interp = widget.tk
    key = interp.interpaddr()
    if key not in _refreshers:
        try:
            _refreshers[key] = _refresher(interp)
        except (OSError, AttributeError, TypeError, ValueError, TclError):
            _refreshers[key] = None
    refresh = _refreshers[key]
    return refresh is not None and refresh()
