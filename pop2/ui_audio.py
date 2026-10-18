"""Quiet host-menu ticks, independent of the original game's sound resources."""

import math
import random
import struct


def menu_pcm(kind, rate, channels):
    if kind not in ('hover', 'click'):
        raise ValueError('Unknown menu sound')
    duration, peak, smoothing = ((0.022, 0.035, 0.35) if kind == 'hover'
                                 else (0.038, 0.085, 0.18))
    count = max(2, round(duration * rate))
    rng = random.Random(0x504F50 + (kind == 'click'))
    filtered, samples = 0.0, []
    for index in range(count):
        phase = index / (count - 1)
        filtered += smoothing * (rng.uniform(-1, 1) - filtered)
        envelope = math.sin(math.pi * phase) ** 2 * math.exp(-5 * phase)
        samples.append(filtered * envelope)
    gain = peak * 32767 / max(abs(sample) for sample in samples)
    pcm = [round(sample * gain) for sample in samples]
    pcm[0] = pcm[-1] = 0
    return struct.pack('<' + 'h' * count * channels,
                       *(sample for sample in pcm for _ in range(channels)))
