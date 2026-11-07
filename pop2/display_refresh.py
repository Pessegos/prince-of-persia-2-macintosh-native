"""Read the current Windows display mode without changing display settings."""

import ctypes
from ctypes import wintypes
from functools import lru_cache
import math
import sys
from tkinter import TclError


class MonitorInfo(ctypes.Structure):
    _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT), ('work', wintypes.RECT),
                ('flags', wintypes.DWORD), ('device', wintypes.WCHAR * 32)]


class DisplayMode(ctypes.Structure):
    # DEVMODEW's printer/display union occupies 16 bytes. Only the current
    # display frequency is consumed; preserve the complete public structure.
    _fields_ = [('device', wintypes.WCHAR * 32), ('spec', wintypes.WORD),
                ('driver', wintypes.WORD), ('size', wintypes.WORD), ('extra', wintypes.WORD),
                ('fields', wintypes.DWORD), ('display', wintypes.BYTE * 16),
                ('color', ctypes.c_short), ('duplex', ctypes.c_short),
                ('resolution', ctypes.c_short), ('tt', ctypes.c_short), ('collate', ctypes.c_short),
                ('form', wintypes.WCHAR * 32), ('dpi', wintypes.WORD),
                ('bits', wintypes.DWORD), ('width', wintypes.DWORD), ('height', wintypes.DWORD),
                ('flags', wintypes.DWORD), ('frequency', wintypes.DWORD),
                ('icm_method', wintypes.DWORD), ('icm_intent', wintypes.DWORD),
                ('media', wintypes.DWORD), ('dither', wintypes.DWORD),
                ('reserved1', wintypes.DWORD), ('reserved2', wintypes.DWORD),
                ('panning_width', wintypes.DWORD), ('panning_height', wintypes.DWORD)]


def valid_refresh_rate(value):
    return float(value) if math.isfinite(value) and 20 <= value <= 1000 else 60.0


class WindowsDisplayRefresh:
    def __init__(self, user=None):
        self.user = user if user is not None else ctypes.WinDLL('user32', use_last_error=True)
        self.user.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        self.user.GetAncestor.restype = wintypes.HWND
        self.user.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        self.user.MonitorFromWindow.restype = wintypes.HMONITOR
        self.user.GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(MonitorInfo)]
        self.user.GetMonitorInfoW.restype = wintypes.BOOL
        self.user.EnumDisplaySettingsW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD,
                                                 ctypes.POINTER(DisplayMode)]
        self.user.EnumDisplaySettingsW.restype = wintypes.BOOL

    def rate(self, hwnd):
        outer = self.user.GetAncestor(hwnd, 2) or hwnd  # GA_ROOT: Tk's wrapper HWND.
        monitor = self.user.MonitorFromWindow(outer, 2)  # MONITOR_DEFAULTTONEAREST.
        info = MonitorInfo(size=ctypes.sizeof(MonitorInfo))
        mode = DisplayMode(size=ctypes.sizeof(DisplayMode))
        if (monitor and self.user.GetMonitorInfoW(monitor, ctypes.byref(info))
                and self.user.EnumDisplaySettingsW(info.device, 0xffffffff, ctypes.byref(mode))):
            return valid_refresh_rate(mode.frequency)
        return 60.0


@lru_cache(maxsize=1)
def windows_display_refresh():
    return WindowsDisplayRefresh()


def window_refresh_rate(root):
    if sys.platform != 'win32':
        return 60.0
    try:
        return windows_display_refresh().rate(root.winfo_id())
    except (OSError, RuntimeError, TclError):
        return 60.0
