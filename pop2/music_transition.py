"""PCM envelopes for the approved horse-to-temple music transition."""

import numpy as np


HORSE_FADE_OUT = 1.25
TEMPLE_FADE_IN = 1.0


def fade_pcm(raw, rate, channels, *, into=0, out=0):
    samples = np.frombuffer(raw, dtype='<i2').reshape(-1, channels).copy()
    for seconds, entering in ((into, True), (out, False)):
        count = min(len(samples), round(seconds * rate))
        if count < 2:
            continue
        gain = (1 - np.cos(np.linspace(0, np.pi, count))) / 2
        if not entering:
            gain = 1 - gain
        region = samples[:count] if entering else samples[-count:]
        region[:] = np.rint(region * gain[:, None])
    return samples.tobytes()


def horse_music_ending(raw, rate, channels):
    """Remove ToTempl2's silent renderer padding and soften its final phrase.

    A -60dBFS peak threshold plus100ms of release padding retains the quiet
    ending. Source files and all samples before the final fade are preserved.
    """
    samples = np.frombuffer(raw, dtype='<i2').reshape(-1, channels)
    if not len(samples):
        return raw
    peak = np.abs(samples.astype(np.int32)).max(axis=1)
    active = np.flatnonzero(peak > 33)
    if not len(active):
        return raw
    end = min(len(samples), int(active[-1]) + 1 + round(.1 * rate))
    return fade_pcm(samples[:end].tobytes(), rate, channels, out=HORSE_FADE_OUT)
