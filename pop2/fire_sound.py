"""The port's fire sound for a screenshot burning in the screenshots page's lava.

The screenshots page is an addition of the port, so the burn has no original
sound. The user chose a generic second of a fire catching from the internet,
cut it to 1 s and faded it out; its source and licence are unknown, so it is not
distributed. This sound is made here instead, from fresh noise, to follow a
coarse description measured from that recording (none of its samples):

- the level of thirteen frequency bands, every 10 ms in the treble and every
  60 ms in the deep rumble that carries most of it (about 93% of its energy is
  below 200 Hz), before the user's fade: ``LEVELS``;
- the 25 crackles heard over it, each a bright click of a few milliseconds,
  with its time and its loudness above 3 kHz: ``CRACKLES``;
- the user's own fade-out, constant power from 0.65 s to the end.

The noise is seeded, so the sound is the same on every run. The seed is the
one of the first forty whose 50 ms levels came closest to the recording's
(within 1 dB on average); the band levels were then refined for that noise.
"""

import numpy

RATE = 48000
SECONDS = 1.0
SEED = 22
FADE = 0.65   # the user's fade: constant power (cosine) from here to the end
# Band edges, Hz. Adjacent bands cross over smoothly (+-15% of each edge).
EDGES = (12, 30, 45, 60, 80, 110, 160, 250, 600, 1500, 3500, 7000, 12000, 24000)
# Each band's level (dB of full scale, RMS), at its step (see ``band_step``) from 0 s.
LEVELS = (
    (
        -70.3, -46, -60.9, -40.3, -49.6, -53.8, -49.8, -41.6, -49.7, -49.6, -37.4, -30, -38, -52.2,
        -31.7, -33.3, -71.1, -61.1),
    (
        -70.4, -61, -67.5, -58, -48.1, -60.8, -51.4, -64.8, -61.8, -50.7, -46.9, -45.6, -57.2,
        -54.2, -38.6, -59.5, -58.7, -53),
    (
        -75, -63.3, -79.5, -70.7, -59.8, -62.4, -48.4, -46, -46.2, -34.6, -58.4, -47.6, -51.8,
        -36.4, -62.5, -49.1, -60.1, -55.4),
    (
        -65, -82.4, -78.9, -57.7, -68.7, -40.7, -54.9, -53.7, -55.5, -63.2, -45.1, -42.6, -49.6,
        -56.2, -66.1, -53.3, -54.8, -53.4),
    (
        -79.8, -81.4, -60, -72.2, -72.9, -67.7, -50.9, -62.3, -53.4, -48.9, -63.3, -43, -51.1,
        -38.7, -46.6, -45.8, -66.5, -47.7, -42.7, -64.7, -54.7),
    (
        -83.8, -78.2, -67.1, -61.7, -58.9, -54.8, -57.6, -60.7, -46.8, -42.1, -51.4, -40.9, -42.5,
        -51.3, -54.8, -50.3, -61.9, -50.6, -38.2, -56, -47.9, -45.8, -42.6, -50.9, -42.3, -57.4,
        -49.4, -64, -38.4, -58.6, -48.6, -65.2, -72.8, -63.2, -63.2),
    (
        -84.2, -93.3, -67, -79.9, -61.4, -64.3, -73.4, -76.1, -64.9, -75, -57.5, -50.8, -72.2,
        -75.7, -72.8, -74.1, -71, -75.6, -57.8, -58.4, -73.2, -68.4, -51.5, -47.1, -72.5, -70.7,
        -64, -45.2, -42.5, -54.9, -53.9, -69, -66.8, -62.3, -68.8, -45.8, -66.5, -49, -59.4, -64.4,
        -72.4, -66, -46.2, -49.6, -73.4, -54.1, -67.9, -68.5, -56.6, -67.6, -62, -60.9, -65, -68.1,
        -57.2, -64.3, -57.2, -68.8, -66, -66, -66),
    (
        -91.9, -100, -90, -95.9, -86.2, -91.4, -89.1, -91, -77.5, -82.4, -89.2, -78.1, -73.4, -81.7,
        -79, -87, -78.9, -81.8, -79.6, -82.9, -73.4, -72.8, -70.1, -77.5, -65.9, -64.5, -73, -79.3,
        -64.3, -77.9, -64.4, -59.2, -74.9, -66.5, -69, -80.8, -64.9, -73.4, -68.5, -62.4, -61.2,
        -66.3, -72.2, -59.3, -80.8, -76.2, -61.6, -77.8, -72.9, -63.6, -75.7, -75.3, -53.4, -77.3,
        -65.5, -65.8, -59.2, -73.9, -67.9, -66.3, -68.3, -54.1, -62.9, -70.7, -65.7, -64.5, -64.7,
        -58.5, -58.5, -70.5, -75, -72, -65.1, -66.4, -62.6, -57.7, -61.7, -59, -63.3, -64.4, -64.2,
        -71.2, -60.7, -69.2, -74, -69.2, -62.9, -77.8, -69.4, -70.3, -56.9, -64.6, -73.8, -77.3,
        -81.5, -78.6, -75.4, -71.8, -71.8, -71.8, -71.8),
    (
        -96.3, -94.5, -90.4, -89.6, -78.6, -88.1, -89.2, -81.9, -90.8, -82.3, -81.3, -87.1, -78.5,
        -90.9, -91.7, -69.5, -73.5, -79, -72.9, -74.3, -75.4, -80.5, -85.7, -67.4, -84.6, -72.2,
        -82, -77.3, -76.4, -85.4, -66.8, -68.6, -64.3, -73.9, -72.1, -78.1, -68.3, -71.5, -70.9,
        -79.9, -80.4, -66.4, -74.4, -72, -64.1, -78.2, -66.6, -82.9, -63.6, -67.9, -71.1, -64.3,
        -79.8, -77.8, -71.8, -72, -69.3, -72, -72.3, -59.7, -79.3, -64.7, -80.3, -82.6, -63.4,
        -61.9, -76.6, -71.3, -79.4, -66.6, -70.7, -74.7, -70.2, -60.1, -69.8, -77.3, -79.2, -69.7,
        -81.4, -68.5, -68.5, -71.6, -75.7, -64.6, -66.1, -71.3, -74, -64.2, -84, -71.1, -76.9,
        -79.1, -66, -75.4, -74.9, -74.6, -79.6, -77.2, -77.2, -77.2, -77.2),
    (
        -92.8, -90.9, -92.7, -79.3, -73.5, -86.8, -82.2, -95.1, -80.6, -84.5, -78.6, -81.5, -83.3,
        -79.4, -84.2, -68.8, -80.7, -85.4, -76.1, -75.6, -77.6, -79.7, -73.6, -74.4, -72.3, -72.7,
        -75.9, -76.2, -76.8, -74.2, -68.9, -69.2, -68.5, -76.7, -69.8, -78.9, -67.9, -64.6, -70.8,
        -69.1, -74.5, -62.4, -70.7, -70.5, -65.3, -72.4, -67.6, -75.1, -58.4, -67.6, -63.2, -69.3,
        -57.9, -71.4, -71.8, -67.2, -65.9, -68.1, -67.8, -64.9, -72.4, -66.9, -69.2, -78.8, -55.5,
        -61.7, -66.1, -67, -70.1, -60.9, -70.9, -74.1, -65.4, -62.8, -73.9, -64.4, -67, -69.6,
        -73.3, -67.8, -69.9, -70.7, -68.2, -64.3, -73.5, -62.9, -72.2, -67.5, -68.1, -83, -74.8,
        -84.7, -66.4, -65.3, -68.2, -79.9, -75.6, -76.3, -76.3, -76.3, -76.3),
    (
        -91.4, -91.7, -100, -75.4, -70.1, -78.5, -82.5, -81, -77, -79.4, -74.2, -81.1, -77.9, -71.7,
        -88, -66.1, -62.9, -74.8, -71.1, -77, -74, -78.9, -69.4, -68.5, -68, -70, -72.6, -74.5,
        -66.3, -69.5, -68.1, -68.6, -62.9, -65.1, -71, -66.1, -65.5, -70.6, -73.5, -71, -69.1,
        -63.7, -65.1, -64.8, -62.6, -66.5, -65.8, -67.1, -58, -48.3, -64, -61.1, -62.3, -67, -67,
        -64.8, -67, -62.2, -66.1, -65.2, -66.3, -52.3, -60.5, -73.7, -56.8, -62.4, -61.2, -65.6,
        -68.1, -58.8, -70.7, -68.9, -67.8, -55.1, -63.1, -61.9, -70.7, -63.4, -67.7, -66.1, -66.4,
        -75.9, -62, -67.8, -66.2, -69.1, -62.9, -64.5, -61.1, -58.8, -60.8, -75.3, -67.6, -60.3,
        -60.1, -72.3, -75.4, -73, -73, -73, -73),
    (
        -92.8, -91.7, -87, -73.5, -65, -73.8, -74.1, -73.4, -69.1, -74.1, -66.4, -73.3, -74.3,
        -66.8, -77.2, -60.8, -59.2, -69.6, -63.6, -63.8, -69.1, -73.7, -64.7, -62.8, -58.4, -64.4,
        -64.3, -69.8, -62.6, -61.8, -63.9, -67.6, -54.3, -59, -56.3, -65.6, -55.5, -65.8, -60.1,
        -58.5, -59.5, -58.1, -55.9, -60.1, -54.9, -61.2, -59.5, -64.7, -52.4, -52.8, -52.7, -55.7,
        -50.8, -61.1, -61.7, -51.5, -62.3, -56.2, -59.3, -54.3, -62.5, -45.8, -55, -61.5, -48.1,
        -57.7, -56.6, -55.6, -56.7, -53.5, -60.9, -58, -57.8, -54, -60.2, -58, -59.6, -56.7, -67.7,
        -58.4, -61.6, -58.8, -59.8, -59.2, -58.7, -61.4, -57.5, -56.1, -55.4, -55.6, -64.1, -64.5,
        -51.5, -55.7, -51.8, -62.2, -68.9, -67.5, -67.5, -67.5, -67.5),
    (
        -88.5, -86.5, -85.5, -70.8, -65.1, -74, -79.1, -79.3, -70.1, -76.5, -66.5, -73.2, -72.7,
        -72.9, -74.7, -59.9, -63.6, -71.1, -63.2, -68.7, -71.6, -71, -65.5, -64.8, -65.2, -58.2,
        -63.6, -66.1, -67.7, -64.3, -64.8, -70.3, -52.7, -57, -56.9, -58.8, -59.7, -63.6, -61.9,
        -59.1, -60.9, -54.3, -61.5, -62.5, -56.1, -60.7, -61.5, -63, -55.8, -54.1, -54.7, -53.3,
        -56, -64.9, -67.5, -56.4, -57.4, -59.9, -58.7, -53.4, -63.4, -44, -57.4, -64.8, -50.1,
        -57.3, -65.1, -59.5, -61.4, -53.8, -67.2, -57.7, -69.4, -52.3, -63.6, -63.8, -62.1, -55.8,
        -69.3, -60.2, -59.9, -72.3, -55.3, -57.2, -60.9, -64.3, -57.7, -54.1, -53.6, -56.3, -60.6,
        -73.6, -54.6, -50.1, -57, -63.9, -67, -66.1, -66.1, -66.1, -66.1),)
# (seconds, peak above 3 kHz as a fraction of full scale)
CRACKLES = (
    (0.0349, 0.0068), (0.0951, 0.0045), (0.1309, 0.0098), (0.151, 0.029), (0.176, 0.0097), (0.2342,
    0.0124), (0.3194, 0.0334), (0.3269, 0.0277), (0.363, 0.0347), (0.4094, 0.024), (0.4371, 0.0364),
    (0.4447, 0.0325), (0.4875, 0.0482), (0.5141, 0.0608), (0.5501, 0.0313), (0.6072, 0.0837),
    (0.6424, 0.0349), (0.7153, 0.0594), (0.7281, 0.0502), (0.7926, 0.0216), (0.8137, 0.0206),
    (0.8538, 0.0224), (0.875, 0.031), (0.9226, 0.0923), (0.9368, 0.0063),
)
# A crackle: a 0.3 ms spike of noise with a faint tail (a tenth, 1.5 ms), shaped
# by these gains (dB at these frequencies, Hz, between them in log frequency):
# brightest around 10 kHz, like the recording's.
CRACKLE_SHAPE = ((2000, -23.1), (4500, -17.0), (7500, -19.0), (10500, -3.3), (14000, -18.7), (19000, -17.5))
CRACKLE_SPIKE, CRACKLE_TAIL, CRACKLE_TAIL_TIME = 0.0003, 0.1, 0.0015
CRACKLE_LENGTH = 480   # samples (10 ms)


def band_step(index):
    """Seconds between a band's levels: 1.5 periods of its width, from 10 to 60 ms."""
    return max(0.01, min(0.06, 1.5 / (EDGES[index + 1] - EDGES[index])))


def band_weights(freqs, index):
    """A band's amplitude weights: their powers add up to one across the bands."""
    low, high = EDGES[index], EDGES[index + 1]
    f = numpy.maximum(freqs, 1.0)
    weight = ((f >= low) & (f < high)).astype(float)
    for edge, rising in ((low, True), (high, False)):
        if edge in (EDGES[0], EDGES[-1]):
            continue
        a, b = numpy.log(edge / 1.15), numpy.log(edge * 1.15)
        zone = (numpy.log(f) > a) & (numpy.log(f) < b)
        ramp = 0.5 - 0.5 * numpy.cos(numpy.pi * (numpy.log(f[zone]) - a) / (b - a))
        weight[zone] = ramp if rising else 1 - ramp
    return numpy.sqrt(weight)


def fade_curve(count, rate=RATE):
    curve = numpy.ones(count)
    start = round(FADE * rate)
    tail = count - start
    curve[start:] = numpy.cos(numpy.arange(1, tail + 1) / tail * numpy.pi / 2)
    return curve


def _background(count):
    noise = numpy.fft.rfft(numpy.random.RandomState(SEED).standard_normal(count))
    freqs = numpy.fft.rfftfreq(count, 1 / RATE)
    t = numpy.arange(count) / RATE
    out = numpy.zeros(count)
    for index, levels in enumerate(LEVELS):
        part = numpy.fft.irfft(noise * band_weights(freqs, index), count)
        part /= part.std() + 1e-12
        times = numpy.arange(len(levels)) * band_step(index)
        out += part * numpy.interp(t, times, 10 ** (numpy.array(levels) / 20))
    return out


def _crackles(count):
    rng = numpy.random.RandomState(SEED + 1000)
    n = CRACKLE_LENGTH
    t = numpy.arange(n) / RATE
    freqs = numpy.fft.rfftfreq(n, 1 / RATE)
    centres, gains = zip(*CRACKLE_SHAPE)
    shape = 10 ** (numpy.interp(numpy.log(numpy.maximum(freqs, 1)), numpy.log(centres), gains) / 20) * (freqs > 1500)
    out = numpy.zeros(count)
    for when, peak in CRACKLES:
        burst = rng.standard_normal(n) * (numpy.exp(-t / CRACKLE_SPIKE)
                                          + CRACKLE_TAIL * numpy.exp(-t / CRACKLE_TAIL_TIME))
        burst = numpy.fft.irfft(numpy.fft.rfft(burst) * shape, n)
        bright = numpy.fft.irfft(numpy.fft.rfft(burst) * (freqs > 3000), n)
        top = int(numpy.argmax(abs(bright[:48])))
        burst *= peak / (abs(bright[top]) + 1e-12)
        first = round(when * RATE) - top
        piece = burst[:count - first]
        out[first:first + len(piece)] += piece
    return out


def fire_samples(rate=RATE):
    """The sound as floats (full scale 1), mono, at ``rate`` samples a second."""
    count = round(SECONDS * RATE)
    sound = _background(count) * fade_curve(count) + _crackles(count)
    if rate != RATE:
        sound = numpy.interp(numpy.arange(round(SECONDS * rate)) * (RATE / rate), numpy.arange(count), sound)
    return sound


def fire_pcm(rate, channels, volume=1.0):
    """The mixer's interleaved 16-bit samples of the sound, made at ``volume`` (1 as
    measured; louder is the same sound made bigger, rounded once, never cut off: it
    peaks near 9% of full scale)."""
    samples = numpy.clip(numpy.round(fire_samples(rate) * (32767 * volume)), -32768, 32767).astype('<i2')
    return numpy.repeat(samples[:, None], channels, 1).tobytes()
