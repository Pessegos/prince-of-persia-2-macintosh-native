"""Game controllers, read through the SDL library pygame already ships.

Tk cannot see controllers. A small thread polls SDL's game-controller layer
(no SDL window or event loop; Tk keeps the window and keyboard) and publishes
snapshots. The Tk thread turns snapshot changes into the same key presses
the keyboard produces, see `GamepadControls` in window_controls.

SDL normalises Xbox, PlayStation, Nintendo and many other pads to one button
layout named by position: 'a' is always the bottom face button.
"""

from dataclasses import dataclass, field
import ctypes
import os
import sys
import threading

from pop2.input_bindings import PAD_BUTTONS

SDL_INIT_GAMECONTROLLER = 0x2000
SDL_IGNORE = 0
AXES = ('leftx', 'lefty', 'rightx', 'righty', 'lefttrigger', 'righttrigger')
# SDL_GameControllerType: PS3/PS4/PS5, Switch Pro and Joy-Cons.
PLAYSTATION_TYPES = {3, 4, 7}
NINTENDO_TYPES = {5, 11, 12, 13}


@dataclass(frozen=True)
class PadState:
    instance: int
    name: str
    style: str
    buttons: frozenset = frozenset()
    axes: dict = field(default_factory=dict)


def pad_style(sdl_type, name=''):
    if sdl_type in PLAYSTATION_TYPES:
        return 'playstation'
    if sdl_type in NINTENDO_TYPES:
        return 'nintendo'
    lowered = name.lower()
    if any(word in lowered for word in ('playstation', 'dualshock', 'dualsense', 'ps4', 'ps5')):
        return 'playstation'
    if any(word in lowered for word in ('nintendo', 'switch', 'joy-con')):
        return 'nintendo'
    return 'xbox'


class Hysteresis:
    """A digital edge from an analog value, without chatter near the edge."""

    def __init__(self, press, release):
        self.press, self.release, self.active = press, release, False

    def update(self, value):
        self.active = value >= (self.release if self.active else self.press)
        return self.active


class PadReader:
    """Digital inputs from every connected pad: buttons, triggers, stick."""

    # Up needs a firmer push than sideways, so running never jumps by accident.
    STICK_SIDE = (0.5, 0.35)
    STICK_UP = (0.65, 0.45)
    STICK_DOWN = (0.6, 0.4)
    TRIGGER = (0.5, 0.3)

    def __init__(self):
        self.gates = {}

    def gate(self, key, levels):
        if key not in self.gates:
            self.gates[key] = Hysteresis(*levels)
        return self.gates[key]

    def inputs(self, pads):
        held = set()
        live = set()
        for pad in pads:
            held.update(pad.buttons)
            axes = pad.axes
            for name, value, levels in (
                    ('stickleft', -axes.get('leftx', 0.0), self.STICK_SIDE),
                    ('stickright', axes.get('leftx', 0.0), self.STICK_SIDE),
                    ('stickup', -axes.get('lefty', 0.0), self.STICK_UP),
                    ('stickdown', axes.get('lefty', 0.0), self.STICK_DOWN),
                    ('lefttrigger', axes.get('lefttrigger', 0.0), self.TRIGGER),
                    ('righttrigger', axes.get('righttrigger', 0.0), self.TRIGGER)):
                key = (pad.instance, name)
                live.add(key)
                if self.gate(key, levels).update(value):
                    held.add(name)
        for key in set(self.gates) - live:
            del self.gates[key]
        return frozenset(held)


def load_sdl():
    """The SDL2 library pygame has loaded (or would load) in this process."""
    os.environ.setdefault('PYGAME_HIDE_SUPPORT_PROMPT', '1')
    import pygame  # noqa: F401  (loads SDL2 next to the pygame package)

    if sys.platform == 'win32':
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel32.GetModuleHandleW.restype = ctypes.c_void_p
        kernel32.GetModuleHandleW.argtypes = (ctypes.c_wchar_p,)
        handle = kernel32.GetModuleHandleW('SDL2.dll')
        if handle:
            return ctypes.CDLL('SDL2.dll', handle=handle)
    folder = os.path.dirname(pygame.__file__)
    for name in ('SDL2.dll', 'libSDL2-2.0.so.0', 'libSDL2-2.0.0.dylib', 'libSDL2.dylib'):
        path = os.path.join(folder, name)
        if os.path.exists(path):
            return ctypes.CDLL(path)
    from ctypes.util import find_library
    found = find_library('SDL2')
    if found:
        return ctypes.CDLL(found)
    raise OSError('SDL2 library not found')


def prepare(sdl):
    sdl.SDL_SetHint.argtypes = (ctypes.c_char_p, ctypes.c_char_p)
    for hint, value in (
            # The Tk window, not an SDL one, has the focus.
            (b'SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS', b'1'),
            # Polled drivers only: these two need window messages or focus.
            (b'SDL_JOYSTICK_RAWINPUT', b'0'), (b'SDL_JOYSTICK_WGI', b'0'),
            # Name buttons by position on Nintendo pads too.
            (b'SDL_GAMECONTROLLER_USE_BUTTON_LABELS', b'0')):
        sdl.SDL_SetHint(hint, value)
    sdl.SDL_InitSubSystem.argtypes = (ctypes.c_uint32,)
    sdl.SDL_QuitSubSystem.argtypes = (ctypes.c_uint32,)
    sdl.SDL_GameControllerUpdate.restype = None
    sdl.SDL_NumJoysticks.restype = ctypes.c_int
    sdl.SDL_IsGameController.argtypes = (ctypes.c_int,)
    sdl.SDL_JoystickGetDeviceInstanceID.argtypes = (ctypes.c_int,)
    sdl.SDL_JoystickGetDeviceInstanceID.restype = ctypes.c_int32
    sdl.SDL_GameControllerOpen.argtypes = (ctypes.c_int,)
    sdl.SDL_GameControllerOpen.restype = ctypes.c_void_p
    for name in ('SDL_GameControllerClose', 'SDL_GameControllerGetAttached',
                 'SDL_GameControllerName', 'SDL_GameControllerGetType'):
        getattr(sdl, name).argtypes = (ctypes.c_void_p,)
    sdl.SDL_GameControllerName.restype = ctypes.c_char_p
    sdl.SDL_GameControllerGetButton.argtypes = (ctypes.c_void_p, ctypes.c_int)
    sdl.SDL_GameControllerGetButton.restype = ctypes.c_uint8
    sdl.SDL_GameControllerGetAxis.argtypes = (ctypes.c_void_p, ctypes.c_int)
    sdl.SDL_GameControllerGetAxis.restype = ctypes.c_int16
    sdl.SDL_GameControllerRumble.argtypes = (ctypes.c_void_p, ctypes.c_uint16,
                                             ctypes.c_uint16, ctypes.c_uint32)
    sdl.SDL_GetError.restype = ctypes.c_char_p
    if sdl.SDL_InitSubSystem(SDL_INIT_GAMECONTROLLER) != 0:
        raise OSError(sdl.SDL_GetError().decode('utf-8', 'replace'))
    # Without an event loop, read state directly; queued events would pile up.
    sdl.SDL_GameControllerEventState(SDL_IGNORE)
    sdl.SDL_JoystickEventState(SDL_IGNORE)


class SdlGamepads:
    """Background polling thread; `snapshot` is always a complete tuple."""

    INTERVAL = 0.008

    def __init__(self, loader=load_sdl):
        self.loader = loader
        self.snapshot = ()
        self.error = None
        self.ready = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name='pop2-gamepads', daemon=True)
        self._thread.start()

    def close(self):
        self._stop.set()
        if self._thread is not threading.current_thread():
            self._thread.join(timeout=1)

    def _run(self):
        try:
            sdl = self.loader()
            prepare(sdl)
        except Exception as error:  # noqa: BLE001 - controllers are optional
            self.error = f'{type(error).__name__}: {error}'
            return
        self.ready = True
        open_pads = {}
        try:
            while not self._stop.wait(self.INTERVAL):
                sdl.SDL_GameControllerUpdate()
                for index in range(max(0, sdl.SDL_NumJoysticks())):
                    instance = sdl.SDL_JoystickGetDeviceInstanceID(index)
                    if instance < 0 or instance in open_pads or not sdl.SDL_IsGameController(index):
                        continue
                    handle = sdl.SDL_GameControllerOpen(index)
                    if handle:
                        raw = sdl.SDL_GameControllerName(handle) or b'Controller'
                        name = raw.decode('utf-8', 'replace')
                        open_pads[instance] = (handle, name, pad_style(
                            sdl.SDL_GameControllerGetType(handle), name))
                states = []
                for instance, (handle, name, style) in list(open_pads.items()):
                    if not sdl.SDL_GameControllerGetAttached(handle):
                        sdl.SDL_GameControllerClose(handle)
                        del open_pads[instance]
                        continue
                    buttons = frozenset(button for index, button in enumerate(PAD_BUTTONS)
                                        if sdl.SDL_GameControllerGetButton(handle, index))
                    axes = {axis: max(-1.0, sdl.SDL_GameControllerGetAxis(handle, index) / 32767)
                            for index, axis in enumerate(AXES)}
                    states.append(PadState(instance, name, style, buttons, axes))
                self.snapshot = tuple(states)
        finally:
            for handle, _name, _style in open_pads.values():
                sdl.SDL_GameControllerClose(handle)
            sdl.SDL_QuitSubSystem(SDL_INIT_GAMECONTROLLER)
            self.snapshot = ()


def gamepads_disabled():
    """Tests and headless runs must not read the player's real controller."""
    return bool(os.environ.get('POP2_NO_GAMEPAD'))
