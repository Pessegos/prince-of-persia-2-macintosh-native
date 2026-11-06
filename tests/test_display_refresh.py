import ctypes
import sys
import unittest
from unittest.mock import Mock, patch

from pop2.display_refresh import (DisplayMode, MonitorInfo, WindowsDisplayRefresh,
                                  valid_refresh_rate, window_refresh_rate)


class DisplayRefreshTests(unittest.TestCase):
    def test_current_mode_comes_from_the_windows_monitor_containing_the_window(self):
        user = Mock()
        user.GetAncestor.return_value = 0x123456789
        user.MonitorFromWindow.return_value = 0x234567891

        def monitor(_handle, pointer):
            self.assertEqual(pointer._obj.size, ctypes.sizeof(MonitorInfo))
            pointer._obj.device = r'\\.\DISPLAY2'
            return 1

        def settings(device, mode, pointer):
            self.assertEqual(device, r'\\.\DISPLAY2')
            self.assertEqual(mode, 0xffffffff)
            self.assertEqual(pointer._obj.size, ctypes.sizeof(DisplayMode))
            pointer._obj.frequency = 240
            return 1

        user.GetMonitorInfoW.side_effect = monitor
        user.EnumDisplaySettingsW.side_effect = settings
        query = WindowsDisplayRefresh(user)
        self.assertEqual(query.rate(0x345678912), 240)
        user.GetAncestor.assert_called_once_with(0x345678912, 2)
        user.MonitorFromWindow.assert_called_once_with(0x123456789, 2)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows ABI sizes')
    def test_native_structures_match_the_windows_unicode_display_abi(self):
        self.assertEqual(ctypes.sizeof(MonitorInfo), 104)
        self.assertEqual(ctypes.sizeof(DisplayMode), 220)
        self.assertEqual(DisplayMode.frequency.offset, 184)

    def test_missing_monitor_or_mode_uses_a_safe_rate(self):
        user = Mock()
        user.GetAncestor.return_value = 17
        user.MonitorFromWindow.return_value = 0
        self.assertEqual(WindowsDisplayRefresh(user).rate(17), 60)
        user.EnumDisplaySettingsW.assert_not_called()
        user.MonitorFromWindow.return_value = 25
        user.GetMonitorInfoW.return_value = 0
        self.assertEqual(WindowsDisplayRefresh(user).rate(17), 60)
        user.GetMonitorInfoW.return_value = 1
        user.EnumDisplaySettingsW.return_value = 0
        self.assertEqual(WindowsDisplayRefresh(user).rate(17), 60)

    def test_default_driver_values_and_invalid_rates_do_not_create_unbounded_timers(self):
        for value in (0, 1, -1, float('nan'), float('inf'), 1001):
            self.assertEqual(valid_refresh_rate(value), 60)
        for value in (59.94, 120, 144, 240, 480):
            self.assertEqual(valid_refresh_rate(value), value)

    def test_non_windows_and_api_failure_do_not_prevent_opening_the_menu(self):
        root = Mock()
        with patch('pop2.display_refresh.sys.platform', 'other'):
            self.assertEqual(window_refresh_rate(root), 60)
            root.winfo_id.assert_not_called()
        with patch('pop2.display_refresh.sys.platform', 'win32'), \
                patch('pop2.display_refresh.windows_display_refresh', side_effect=OSError):
            self.assertEqual(window_refresh_rate(root), 60)
