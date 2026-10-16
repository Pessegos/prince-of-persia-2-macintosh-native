"""Sample-accurate release on SDL_mixer's existing effect channel."""

import ctypes
from pathlib import Path

import numpy as np


class PcmRelease:
    def __init__(self, mixer):
        import pygame

        rate, bits, self.channels = mixer.get_init()
        if bits != -16:
            raise RuntimeError("Gate audio release requires signed 16-bit mixer output")
        # Windows wheels bundle the DLL; POSIX resolves the dependency through
        # the mixer extension, ensuring this is pygame's already-loaded SDL.
        library = Path(pygame.__file__).parent / "SDL2_mixer.dll"
        self.library = ctypes.CDLL(str(library) if library.exists() else mixer.__file__)
        callback_type = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_void_p,
                                        ctypes.c_int, ctypes.c_void_p)
        self.callback = callback_type(self.process)
        self.library.Mix_RegisterEffect.argtypes = [ctypes.c_int, callback_type,
                                                    ctypes.c_void_p, ctypes.c_void_p]
        self.library.Mix_RegisterEffect.restype = ctypes.c_int
        self.library.Mix_UnregisterEffect.argtypes = [ctypes.c_int, callback_type]
        self.library.Mix_UnregisterEffect.restype = ctypes.c_int
        self.library.Mix_ExpireChannel.argtypes = [ctypes.c_int, ctypes.c_int]
        self.library.Mix_ExpireChannel.restype = ctypes.c_int
        self.gain = ((1 + np.cos(np.linspace(0, np.pi, rate * 12 // 1000))) / 2)[:, None]
        self.positions = {}

    def start(self, channel):
        self.cancel(channel)
        self.positions[channel] = 0
        if not self.library.Mix_RegisterEffect(channel, self.callback, None, None):
            raise RuntimeError("Cannot apply the gate audio release")
        # The channel is silent after 12 ms; retire it after several buffers.
        self.library.Mix_ExpireChannel(channel, 80)

    def cancel(self, channel):
        if channel in self.positions:
            self.library.Mix_UnregisterEffect(channel, self.callback)
            del self.positions[channel]

    def process(self, channel, stream, length, _user):
        position = self.positions[channel]
        if position >= len(self.gain):
            ctypes.memset(stream, 0, length)
            return
        pcm = (ctypes.c_int16 * (length // 2)).from_address(stream)
        samples = np.ctypeslib.as_array(pcm).reshape(-1, self.channels)
        self.positions[channel] = self.apply(samples, self.gain, position)

    @staticmethod
    def apply(samples, gain, position):
        count = max(0, min(len(samples), len(gain) - position))
        samples[:count] = np.rint(samples[:count] * gain[position:position + count])
        samples[count:] = 0
        return position + count
