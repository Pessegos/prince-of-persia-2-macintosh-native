"""Quiet host-menu ticks, independent of the original game's sound resources."""

import math
import random
import struct


def menu_pcm(kind, rate, channels):
    if kind not in ('hover', 'click'):
        raise ValueError('Unknown menu sound')
    duration, peak, cutoff = ((0.012, 0.0025, 1600) if kind == 'hover'
                              else (0.018, 0.0075, 2200))
    count = max(2, round(duration * rate))
    rng = random.Random(0x504F50 + (kind == 'click'))
    smoothing = 1 - math.exp(-2 * math.pi * cutoff / rate)
    dc_smoothing = 1 - math.exp(-2 * math.pi * 500 / rate)
    filtered, rounded, dc = 0.0, 0.0, 0.0
    samples = []
    for index in range(count):
        phase = index / (count - 1)
        filtered += smoothing * (rng.uniform(-1, 1) - filtered)
        # Two low-pass stages soften the scratchy top without a pitched beep.
        rounded += smoothing * (filtered - rounded)
        dc += dc_smoothing * (rounded - dc)
        envelope = math.sin(math.pi * phase) ** 2 * math.exp(-7 * phase)
        samples.append((rounded - dc) * envelope)
    gain = peak * 32767 / max(abs(sample) for sample in samples)
    pcm = [round(sample * gain) for sample in samples]
    pcm[0] = pcm[-1] = 0
    return struct.pack('<' + 'h' * count * channels,
                       *(sample for sample in pcm for _ in range(channels)))
