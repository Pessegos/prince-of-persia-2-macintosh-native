"""Controller labels must not turn XInput compatibility into a brand claim."""

import ctypes
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from pop2.controller_identity import XInputNames, _CapabilitiesEx, load_capabilities
from pop2.gamepad import SdlGamepads


def capabilities(devices):
    """Supply Windows per-slot responses, independently of SDL's guesses."""
    def query(reserved, slot, flags, output):
        assert (reserved, flags) == (1, 0)
        result, vendor, product = devices.get(slot, (1167, 0, 0))
        caps = ctypes.cast(output, ctypes.POINTER(_CapabilitiesEx)).contents
        caps.capabilities[1] = 1  # XINPUT_DEVSUBTYPE_GAMEPAD
        caps.vendor, caps.product = vendor, product
        return result
    return Mock(side_effect=query)


class ControllerIdentityTests(unittest.TestCase):
    def names(self, devices):
        query = capabilities(devices)
        with patch('pop2.controller_identity.load_capabilities', return_value=query):
            return XInputNames(), query

    def test_exact_slot_distinguishes_microsoft_from_third_party(self):
        names, query = self.names({0: (0, 0x045e, 0x02ea), 2: (0, 0x2dc8, 0x02ea)})
        self.assertEqual(names.name('XInput Controller', b'XInput#2'), 'XInput Controller')
        self.assertEqual(names.name('XInput Controller', b'XInput#0'), 'Xbox One Controller')
        self.assertEqual([call.args[1] for call in query.call_args_list], [2, 0])

    def test_unknown_and_driver_software_ids_stay_generic(self):
        for vendor, product in ((0, 0), (0x045e, 0), (0x045e, 0xffff),
                                (0x045e, 0x02ff), (0x045e, 0x02a1),
                                (0x045e, 0x028e), (0x045e, 0x0719), (0x24c6, 0x0b12)):
            with self.subTest(vendor=vendor, product=product):
                names, _ = self.names({0: (0, vendor, product)})
                self.assertEqual(names.name('XInput Controller', b'XInput#0'),
                                 'XInput Controller')

    def test_known_models_do_not_all_become_xbox_one(self):
        names, _ = self.names({0: (0, 0x045e, 0x0b13), 1: (0, 0x045e, 0x0b05),
                               2: (0, 0x045e, 0x0b0a)})
        self.assertEqual(names.name('XInput Controller #1', b'XInput#0'),
                         'Xbox Series Controller')
        self.assertEqual(names.name('XInput Controller', b'XInput#1'),
                         'Xbox Elite Series 2 Controller')
        self.assertEqual(names.name('XInput Controller', b'XInput#2'),
                         'Xbox Adaptive Controller')

    def test_reported_specific_names_and_non_xinput_paths_are_preserved(self):
        names, query = self.names({0: (0, 0x045e, 0x02ea)})
        for reported, path in (('8BitDo Pro 2', b'XInput#0'),
                               ('Wireless Controller', b'XInput#0'),
                               ('XInput Wheel #1', b'XInput#0'),
                               ('XInput Controller', None),
                               ('XInput Controller', b'XInput#4'),
                               ('XInput Controller', b'USB#0'),
                               ('XInput Controller', b'XInput#0extra')):
            with self.subTest(reported=reported, path=path):
                self.assertEqual(names.name(reported, path), reported)
        query.assert_not_called()

    def test_failure_never_promotes_even_supplied_microsoft_ids(self):
        names, query = self.names({0: (1167, 0x045e, 0x02ea)})
        self.assertEqual(names.name('XInput Controller', b'XInput#0'), 'XInput Controller')
        query.side_effect = OSError('query unavailable')
        self.assertEqual(names.name('XInput Controller', b'XInput#0'), 'XInput Controller')
        with patch('pop2.controller_identity.load_capabilities', return_value=None):
            self.assertEqual(XInputNames().name('XInput Controller', b'XInput#0'),
                             'XInput Controller')

    def test_optional_system_extension_binding_and_abi(self):
        self.assertEqual(ctypes.sizeof(_CapabilitiesEx), 32)
        self.assertEqual(_CapabilitiesEx.vendor.offset, 20)
        self.assertEqual(_CapabilitiesEx.product.offset, 22)
        dll = Mock()
        dll.__getitem__ = Mock(return_value=Mock())
        with patch('pop2.controller_identity.sys.platform', 'win32'), \
                patch('pop2.controller_identity.ctypes.WinDLL', create=True,
                      return_value=dll) as load:
            query = load_capabilities()
        load.assert_called_once_with('xinput1_4.dll', winmode=0x800)
        dll.__getitem__.assert_called_once_with(108)
        self.assertIs(query.restype, ctypes.c_uint32)
        with patch('pop2.controller_identity.sys.platform', 'linux'), \
                patch('pop2.controller_identity.ctypes.WinDLL', create=True) as load:
            self.assertIsNone(load_capabilities())
        load.assert_not_called()
        with patch('pop2.controller_identity.sys.platform', 'win32'), \
                patch('pop2.controller_identity.ctypes.WinDLL', create=True,
                      side_effect=OSError('not installed')):
            self.assertIsNone(load_capabilities())

    def test_unplug_and_replacement_use_fresh_identity_and_keep_input(self):
        # SDL still calls both pads XInput, and can report guessed Microsoft
        # VID/PIDs for either. Those APIs must never be consulted for naming.
        sdl = Mock()
        sdl.SDL_InitSubSystem.return_value = 0
        sdl.SDL_NumJoysticks.return_value = 1
        sdl.SDL_JoystickGetDeviceInstanceID.return_value = 41
        sdl.SDL_IsGameController.return_value = 1
        sdl.SDL_GameControllerOpen.return_value = 100
        sdl.SDL_GameControllerName.return_value = b'XInput Controller'
        sdl.SDL_GameControllerPath.return_value = b'XInput#2'
        sdl.SDL_GameControllerGetType.return_value = 2
        sdl.SDL_GameControllerGetAttached.return_value = 1
        sdl.SDL_GameControllerGetButton.side_effect = lambda handle, button: button == 0
        sdl.SDL_GameControllerGetAxis.return_value = 0
        devices = {2: (0, 0x045e, 0x02ea)}
        snapshots = []
        with patch('pop2.gamepad.threading.Thread'), \
                patch('pop2.controller_identity.load_capabilities',
                      return_value=capabilities(devices)):
            reader = SdlGamepads(loader=lambda: sdl)

            def wait(interval):
                snapshots.append(reader.snapshot)
                phase = len(snapshots)
                if phase == 2:
                    sdl.SDL_GameControllerGetAttached.return_value = 0
                elif phase == 3:
                    devices[2] = (0, 0x2dc8, 0x6001)
                    sdl.SDL_JoystickGetDeviceInstanceID.return_value = 42
                    sdl.SDL_GameControllerGetAttached.return_value = 1
                return phase == 4

            reader._stop = SimpleNamespace(wait=wait)
            reader._run()
        self.assertIsNone(reader.error)
        self.assertEqual(snapshots[1][0].name, 'Xbox One Controller')
        self.assertEqual(snapshots[2], ())
        self.assertEqual(snapshots[3][0].name, 'XInput Controller')
        self.assertEqual(snapshots[3][0].style, 'xbox')
        self.assertEqual(snapshots[3][0].buttons, {'a'})
        sdl.SDL_GameControllerGetVendor.assert_not_called()
        sdl.SDL_GameControllerGetProduct.assert_not_called()
        self.assertEqual(sdl.SDL_GameControllerClose.call_count, 2)
