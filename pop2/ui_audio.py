"""The port's menu sounds: a muted plucked string, independent of the game's sound resources.

The menus are an addition of the port, so they have no original sound. These
are synthesised here as a small plucked instrument, like a santur or an oud:

- ``hover``: one very short, quiet, high note (A), the string damped at
  once and the fingertip heard on it, so it is nearer a click than a tone.
  Always the same note: a run of different notes was tried and became
  tiresome within a minute.
- ``click``: the same touch a fifth lower (D) and a little firmer.
- ``reveal``: for a chapter that has just been unlocked in the Cutscene
  Viewer. A quick run up the scale the game's music leans on (D, E flat,
  F sharp, G, A), whose augmented second gives it the game's flavour, to
  the octave, struck again twice like a short tremolo. It is heard rarely,
  so it may ring; it is still quiet.

Each string is a Karplus-Strong loop: the string's shape as a finger leaves
it goes round a delay line as long as one period of the note, and is softened
a little on every turn, so the note starts clear and dies away dull like a
real string.
"""

import struct

import numpy

# D5, E flat 5, F sharp 5, G5, A5: the scale the game's music leans on.
_SCALE = (587.33, 622.25, 739.99, 783.99, 880.00)
# The notes hovering plays, in turn. One (A): the menu repeats a single quiet touch.
HOVER_NOTES = (4,)
KINDS = ('hover', 'click', 'reveal')
# Loudest sample of each sound, as a fraction of full scale. The first menu
# ticks (0.0025 and 0.0075) were too quiet to hear; a first plucked version
# (0.10 and 0.18, ringing for a quarter of a second and more) was far too much.
PEAK = {'hover': 0.012, 'click': 0.026, 'reveal': 0.09}
DURATION = {'hover': 0.05, 'click': 0.07, 'reveal': 1.30}


def _string(frequency, seconds, rate, seed, damping=0.996, pick=0.5):
    """One plucked note. ``pick`` near 0 is a soft, dull pluck; near 1 a hard, bright one."""
    period = max(2, round(rate / frequency))
    count = max(period + 1, round(seconds * rate))
    # The string pulled aside into a triangle a fifth of the way along, as a
    # finger leaves it: a clear note whose overtones fall away quickly. A
    # little noise gives each note the roughness of a real pluck.
    position = numpy.arange(period) / period
    burst = numpy.minimum(position / 0.2, (1 - position) / 0.8)
    burst += numpy.random.RandomState(seed).uniform(-1, 1, period) * 0.25 * pick
    # Soften the shape: a finger is not a point.
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
        # A high string damped at once, with the fingertip's tap: nearer a
        # click than a note.
        note = HOVER_NOTES[variant % len(HOVER_NOTES)]
        out = _mix(rate, seconds, [
            (0, _tap(0.004, rate, 0x504F40), 0.5),
            (0, _string(_SCALE[note], seconds, rate, 0x504F50 + note, damping=0.96, pick=0.35), 1)])
    elif kind == 'click':
        out = _mix(rate, seconds, [
            (0, _tap(0.006, rate, 0x504F60), 0.6),
            (0, _string(_SCALE[0], seconds, rate, 0x504F61, damping=0.955, pick=0.4), 1),
        ])
    else:
        # The game's own flavour: up the scale through its augmented second
        # (E flat to F sharp), quickly, as on a santur, to the octave, which
        # is struck again twice, softer each time, like a short tremolo.
        run = [(index * 0.065, _SCALE[index], 0.7) for index in range(5)]
        run += [(0.36, _SCALE[0] * 2, 1), (0.47, _SCALE[0] * 2, 0.55), (0.56, _SCALE[0] * 2, 0.35)]
        out = _mix(rate, seconds, [
            (start, _string(frequency, seconds, rate, 0x504F70 + index, damping=0.997, pick=0.3), gain)
            for index, (start, frequency, gain) in enumerate(run)])
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
