"""Conservative friendly names for SDL's generic Windows XInput devices.

SDL 2.28 guesses XInput VID/PIDs, including a Microsoft Bluetooth fallback.
Do not use those guesses or the button style as evidence of the manufacturer.
Query the exact XInput slot instead; unavailable/unknown identities stay generic.
"""

import ctypes
import re
import sys


# Concrete Microsoft product IDs from SDL's usb_ids.h and Linux's xpad.c.
# Omit driver software IDs 02a1/02ff, receiver-only IDs and the frequently
# emulated Xbox 360 identity 028e. These cannot establish a physical model.
MICROSOFT_PADS = {
    0x02d1: 'Xbox One Controller',
    0x02dd: 'Xbox One Controller',
    0x02e3: 'Xbox Elite Controller',
    0x02ea: 'Xbox One Controller',
    0x02e0: 'Xbox One Controller',
    0x02fd: 'Xbox One Controller',
    0x0b20: 'Xbox One Controller',
    0x0b00: 'Xbox Elite Series 2 Controller',
    0x0b05: 'Xbox Elite Series 2 Controller',
    0x0b22: 'Xbox Elite Series 2 Controller',
    0x0b0a: 'Xbox Adaptive Controller',
    0x0b0c: 'Xbox Adaptive Controller',
    0x0b21: 'Xbox Adaptive Controller',
    0x0b12: 'Xbox Series Controller',
    0x0b13: 'Xbox Series Controller',
}


class _CapabilitiesEx(ctypes.Structure):
    # XINPUT_CAPABILITIES is 20 bytes. The remaining ABI is recorded in SDL's
    # src/core/windows/SDL_xinput.h; DWORD alignment makes the total 32 bytes.
    _fields_ = [('capabilities', ctypes.c_uint8 * 20),
                ('vendor', ctypes.c_uint16), ('product', ctypes.c_uint16),
                ('version', ctypes.c_uint16), ('reserved', ctypes.c_uint16),
                ('reserved2', ctypes.c_uint32)]


def load_capabilities():
    """Optional Windows 8+ extension, also used by current SDL. Read-only."""
    if sys.platform != 'win32':
        return None
    try:
        # Use the system DLL, never a bundled/working-directory XInput wrapper.
        dll = ctypes.WinDLL('xinput1_4.dll', winmode=0x800)
        query = dll[108]  # XInputGetCapabilitiesEx (not a named export)
        query.argtypes = (ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32,
                          ctypes.POINTER(_CapabilitiesEx))
        query.restype = ctypes.c_uint32
        return query
    except (OSError, AttributeError):
        return None


class XInputNames:
    """Resolve on connection only; identity failure must not disable input."""

    def __init__(self):
        self.query = load_capabilities()

    def name(self, reported, path):
        # Preserve specific third-party/SDL mapping names. The path identifies
        # the actual slot, unlike joystick order or an assignable player index.
        if self.query is None or not re.fullmatch(
                r'XInput Controller(?: #[1-4])?', reported, re.IGNORECASE):
            return reported
        if path not in (b'XInput#0', b'XInput#1', b'XInput#2', b'XInput#3'):
            return reported
        caps = _CapabilitiesEx()
        try:
            result = self.query(1, int(path[-1:]), 0, ctypes.byref(caps))
        except (OSError, ValueError):
            return reported
        if result != 0 or caps.capabilities[1] != 1 or caps.vendor != 0x045e:
            return reported
        return MICROSOFT_PADS.get(caps.product, reported)
