"""The port's menu sounds: a plucked string, independent of the game's sound resources.

The menus are an addition of the port, so they have no original sound. These
are synthesised here as a small plucked instrument, like a santur or an oud,
in the scale the game's music leans on (D, E flat, F sharp, G, A):

- ``hover``: one soft note. There are several, and the menu plays them in
  turn, up the scale and back down, so moving through a menu runs along the
  strings instead of repeating one tick.
- ``click``: a firmer strum of the low D and its fifth, with a light tap.
- ``reveal``: a rising run that ends an octave up, for a chapter that has
  just been unlocked in the Cutscene Viewer.

Each string is a Karplus-Strong loop: a short burst of noise goes round a
delay line as long as one period of the note, and is softened a little on
every turn, so the note starts bright and dies away dull like a real string.
"""

import struct

import numpy

# D5, E flat 5, F sharp 5, G5, A5, then back down: the order hover notes are played in.
_SCALE = (587.33, 622.25, 739.99, 783.99, 880.00)
HOVER_NOTES = (0, 1, 2, 3, 4, 3, 2, 1)
KINDS = ('hover', 'click', 'reveal')
# Loudest sample of each sound, as a fraction of full scale.
PEAK = {'hover': 0.10, 'click': 0.18, 'reveal': 0.20}
DURATION = {'hover': 0.26, 'click': 0.42, 'reveal': 1.10}


def _string(frequency, seconds, rate, seed, damping=0.996, pick=0.5):
    """One plucked note. ``pick`` near 0 is a soft, dull pluck; near 1 a hard, bright one."""
    period = max(2, round(rate / frequency))
    count = max(period + 1, round(seconds * rate))
    burst = numpy.random.RandomState(seed).uniform(-1, 1, period)
    # Soften the burst: a finger is not a point.
    for _ in range(max(1, round((1 - pick) * 6))):
        burst = (burst + numpy.roll(burst, 1)) / 2
    burst -= burst.mean()
    turns = [burst]
    for _ in range(count // period + 2):
        previous = turns[-1]
        turns.append((previous + numpy.roll(previous, 1)) * (damping / 2))
    note = numpy.concatenate(turns)
    # A whole number of samples per turn is slightly out of tune, and the
    # averaging adds half a sample more: read the note at the speed that
    # puts it on pitch.
    speed = frequency * (period + 0.5) / rate
    return numpy.interp(numpy.arange(count) * speed, numpy.arange(len(note)), note)


def _tap(seconds, rate, seed):
    """A fingertip on the instrument's body: a few milliseconds of dull noise."""
    count = max(2, round(seconds * rate))
    noise = numpy.random.RandomState(seed).uniform(-1, 1, count)
    for _ in range(4):
        noise = (noise + numpy.roll(noise, 1)) / 2
    return noise * numpy.exp(-numpy.arange(count) / (count / 5))


def _mix(rate, seconds, parts):
    """Lay ``(start seconds, samples, gain)`` parts over one another."""
    out = numpy.zeros(round(seconds * rate))
    for start, samples, gain in parts:
        first = round(start * rate)
        samples = samples[:max(0, len(out) - first)]
        out[first:first + len(samples)] += samples * gain
    return out


def menu_samples(kind, rate, variant=0):
    """The sound as floating-point samples between -1 and 1, before its level is set."""
    if kind not in KINDS:
        raise ValueError('Unknown menu sound')
    seconds = DURATION[kind]
    if kind == 'hover':
        note = HOVER_NOTES[variant % len(HOVER_NOTES)]
        out = _mix(rate, seconds, [(0, _string(_SCALE[note], seconds, rate, 0x504F50 + note, pick=0.35), 1)])
    elif kind == 'click':
        out = _mix(rate, seconds, [
            (0, _tap(0.012, rate, 0x504F60), 0.5),
            (0, _string(_SCALE[0] / 2, seconds, rate, 0x504F61, pick=0.6), 1),
            (0.012, _string(_SCALE[4] / 2, seconds, rate, 0x504F62, pick=0.6), 0.7),
        ])
    else:
        run = (_SCALE[0], _SCALE[2], _SCALE[4], _SCALE[0] * 2)
        out = _mix(rate, seconds, [
            (index * 0.085, _string(frequency, seconds, rate, 0x504F70 + index, damping=0.9975, pick=0.55),
             0.8 if index < 3 else 1)
            for index, frequency in enumerate(run)])
    # Die away to silence at the end, and start from silence without a click.
    fade = min(len(out), round(0.35 * seconds * rate))
    out[-fade:] *= numpy.linspace(1, 0, fade) ** 2
    attack = min(len(out), max(2, round(0.002 * rate)))
    out[:attack] *= numpy.linspace(0, 1, attack)
    return out / max(1e-9, numpy.abs(out).max())


def menu_pcm(kind, rate, channels, variant=0):
    """The sound as signed 16-bit samples for the mixer, the same in every channel."""
    samples = numpy.round(menu_samples(kind, rate, variant) * PEAK[kind] * 32767).astype('<i2')
    samples[0] = samples[-1] = 0
    return struct.pack('<' + 'h' * (len(samples) * channels),
                       *(int(sample) for sample in samples for _ in range(channels)))
