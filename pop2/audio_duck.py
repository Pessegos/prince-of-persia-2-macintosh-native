"""Sample-clock ducking of stone movement beneath a debris impact."""

import ctypes
from pathlib import Path

import numpy as np


GATE_IMPACT_GAIN = 10 ** (-3 / 20)


class DuckEnvelope:
    def __init__(self, rate):
        self.attack = max(2, round(rate * .012))
        self.release = max(2, round(rate * .120))
        self.target = self.gain = 1.0
        self.ramp = np.empty((0, 1))
        self.position = 0

    def apply(self, samples, impact):
        target = GATE_IMPACT_GAIN if impact else 1.0
        if target != self.target:
            frames = self.attack if impact else self.release
            blend = (1 - np.cos(np.linspace(0, np.pi, frames))) / 2
            self.ramp = (self.gain + (target - self.gain) * blend)[:, None]
            self.position = 0
            self.target = target
        count = min(len(samples), len(self.ramp) - self.position)
        if count:
            gains = self.ramp[self.position:self.position + count]
            samples[:count] = np.rint(samples[:count] * gains)
            self.position += count
            self.gain = float(gains[-1, 0])
        if count < len(samples):
            if target != 1:
                samples[count:] = np.rint(samples[count:] * target)
            self.gain = target


class PcmGateDuck:
    def __init__(self, mixer):
        import pygame

        self.rate, bits, self.channels = mixer.get_init()
        if bits != -16:
            raise RuntimeError("Gate impact mixing requires signed 16-bit output")
        library = Path(pygame.__file__).parent / 'SDL2_mixer.dll'
        self.library = ctypes.CDLL(str(library) if library.exists() else mixer.__file__)
        callback_type = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_void_p,
                                        ctypes.c_int, ctypes.c_void_p)
        done_type = ctypes.CFUNCTYPE(None, ctypes.c_int, ctypes.c_void_p)
        self.callback = callback_type(self.process)
        self.done_callback = done_type(self.finished)
        self.library.Mix_RegisterEffect.argtypes = [ctypes.c_int, callback_type,
                                                    ctypes.c_void_p, ctypes.c_void_p]
        self.library.Mix_RegisterEffect.restype = ctypes.c_int
        self.library.Mix_UnregisterEffect.argtypes = [ctypes.c_int, callback_type]
        self.library.Mix_UnregisterEffect.restype = ctypes.c_int
        self.roles = {}
        self.envelopes = {}

    def watch(self, channel, role):
        self.cancel(channel)
        self.roles[channel] = role
        if role == 'gate':
            self.envelopes[channel] = DuckEnvelope(self.rate)
        if not self.library.Mix_RegisterEffect(
                channel, self.callback, ctypes.cast(self.done_callback, ctypes.c_void_p), None):
            self.finished(channel, None)
            raise RuntimeError("Cannot apply the gate impact mix")

    def cancel(self, channel):
        if channel in self.roles:
            self.library.Mix_UnregisterEffect(channel, self.callback)
            self.finished(channel, None)

    def finished(self, channel, _user):
        # SDL ends the overlap on completion/stop/reuse, including while muted.
        # Pausing both channels naturally freezes the envelope's sample clock.
        self.roles.pop(channel, None)
        self.envelopes.pop(channel, None)

    def process(self, channel, stream, length, _user):
        envelope = self.envelopes.get(channel)
        if envelope is None:
            return
        pcm = (ctypes.c_int16 * (length // 2)).from_address(stream)
        samples = np.ctypeslib.as_array(pcm).reshape(-1, self.channels)
        envelope.apply(samples, 'impact' in self.roles.values())

    def close(self):
        for channel in tuple(self.roles):
            self.cancel(channel)
