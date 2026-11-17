"""The port's fire sound for a screenshot burning in the screenshots page's lava.

The screenshots page is an addition of the port, so the burn has no original
sound. The user chose a generic second of a fire catching from the internet,
cut it to 1 s and faded it out; its source and licence are unknown, so it is not
distributed. This sound is made here instead, from fresh noise, to follow a
coarse description measured from that recording (none of its samples):

- the level of thirteen frequency bands, every 10 ms in the treble and every
  60 ms in the deep rumble that carries most of it (about 93% of its energy is
  below 200 Hz), before the user's fade: ``LEVELS``;
- the 25 crackles heard over it, each a bright click of a few milliseconds
  with a soft low pop, at its time and its loudness above 3 kHz: ``CRACKLES``;
- the grain of its hiss: between those crackles the treble is many tiny
  crackles, not even static (``HISS_*``); a first version made of static was
  heard as thinner and colder than the recording;
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
        -96.7, -90.9, -94.3, -77.7, -74.8, -89, -79.5, -97.2, -80.4, -83, -78.4, -81.1, -88.1,
        -75.6, -86.5, -68.3, -84.1, -82.2, -76, -75.1, -80, -76.3, -70.8, -72.8, -71.2, -73.8,
        -74.4, -77.1, -75.1, -71.5, -70, -67.8, -69.8, -74.6, -69.4, -77.3, -67.9, -64.6, -67.5,
        -68.8, -72, -61.9, -73.1, -65.3, -66.6, -72.2, -67, -75.2, -57.3, -66, -62.8, -69.4, -58.5,
        -72.2, -70, -66, -70.5, -66.8, -69.3, -62.7, -77, -67.9, -68.2, -78, -56.4, -65.9, -63.5,
        -68.1, -71.4, -58.3, -75.4, -70.3, -64.5, -62.6, -69.7, -62, -67.6, -70.7, -68.9, -70.7,
        -70.3, -69.9, -68.2, -61.9, -70, -64.9, -70.5, -66.2, -71.2, -79.7, -72.9, -84.7, -65.1,
        -71.3, -68.4, -80.8, -73.2, -76.3, -76.3, -76.3, -76.3),
    (
        -100, -91.7, -100, -73.6, -70.8, -76.7, -84.1, -78.1, -75.1, -74.7, -72.9, -77.9, -76.9,
        -72.3, -88, -63.8, -63.3, -73.5, -71.6, -71.9, -72.2, -84.8, -65.2, -65.7, -66.2, -69.7,
        -66.7, -72.4, -63.5, -70.5, -66.6, -65.9, -65.2, -59.2, -68.3, -61.6, -65.8, -63.9, -74.7,
        -67.6, -65.4, -64.1, -67.2, -61.6, -63.5, -66.3, -65, -65.8, -58.8, -45.1, -68.8, -60.4,
        -60.6, -63.6, -64.6, -72.3, -67, -61.2, -68.9, -63.2, -70.2, -48.4, -61.6, -73.4, -54.5,
        -62, -61.3, -65, -66.4, -55.9, -75.5, -68.1, -64.3, -57, -67.6, -58.9, -76.6, -63.5, -64.3,
        -64.8, -63.4, -78.2, -61.9, -66.1, -63.4, -69.7, -63.8, -67.2, -59, -54.7, -61.8, -75.1,
        -61.2, -65.7, -58.9, -77.2, -70.8, -73, -73, -73, -73),
    (
        -100, -91.7, -83.9, -72.8, -63.5, -73, -70, -70.1, -70, -69.2, -67.1, -69.5, -72.5, -65.7,
        -72.6, -59.5, -56.4, -67.2, -66.4, -60.8, -68.1, -72.2, -60.1, -63.8, -55.8, -59.9, -61.5,
        -67.8, -62.3, -58, -59.6, -70, -53.8, -54.6, -58.1, -59.9, -54.1, -71.7, -56.2, -62.5,
        -55.5, -60.3, -55.8, -56.2, -52.7, -59.5, -57.7, -62.8, -50.9, -52.5, -50.1, -54.1, -51.3,
        -58.2, -60.9, -50.2, -64.3, -53.3, -59.5, -49.5, -67.5, -44.5, -50.2, -63.9, -45.3, -58.7,
        -56.9, -55.4, -56.3, -48.8, -62.8, -53.5, -55.8, -56.1, -58.4, -55.4, -56.5, -59.3, -59.9,
        -61.2, -57.1, -59, -57, -55.1, -54.7, -65.2, -56.3, -51.5, -56.6, -51, -60, -65.1, -50.1,
        -61.7, -50.9, -69.1, -61.8, -67.5, -67.5, -67.5, -67.5),
    (
        -91.1, -84.4, -85.7, -69.9, -64.2, -77.3, -77.1, -81.8, -67.6, -80.8, -67.6, -73.3, -72.9,
        -72.2, -72.5, -59.6, -62.5, -73, -63.3, -66.7, -70.6, -71.1, -64.8, -63.7, -62.9, -57.6,
        -62.2, -64.4, -66.1, -65.2, -62.5, -76.8, -52.5, -55.5, -58.1, -58.2, -59.8, -61.3, -62.5,
        -57.5, -60.3, -54.5, -60.4, -61.8, -54.4, -62.2, -59.9, -65.1, -54.4, -55, -52.9, -55,
        -54.9, -63.4, -66.2, -56.2, -58.2, -58.8, -58.4, -54.6, -64.9, -43.6, -57.5, -65.1, -50.8,
        -56.5, -63.2, -60.1, -59.6, -52.6, -66.8, -56.3, -72.2, -52.8, -63.9, -63.5, -60.6, -56.8,
        -65.2, -60.9, -59.8, -73.7, -55, -55.6, -58.9, -65.7, -58, -52.3, -54, -54.9, -60.7, -75.4,
        -52.1, -53.1, -55.6, -65, -65, -66.1, -66.1, -66.1, -66.1),
)
# (seconds, peak above 3 kHz as a fraction of full scale)
CRACKLES = (
    (0.0349, 0.0068), (0.0951, 0.0045), (0.1309, 0.0098), (0.151, 0.029), (0.176, 0.0097), (0.2342,
    0.0124), (0.3194, 0.0334), (0.3269, 0.0277), (0.363, 0.0347), (0.4094, 0.024), (0.4371, 0.0364),
    (0.4447, 0.0325), (0.4875, 0.0482), (0.5141, 0.0608), (0.5501, 0.0313), (0.6072, 0.0837),
    (0.6424, 0.0349), (0.7153, 0.0594), (0.7281, 0.0502), (0.7926, 0.0216), (0.8137, 0.0206),
    (0.8538, 0.0224), (0.875, 0.031), (0.9226, 0.0923), (0.9368, 0.0063),
)
# A crackle: noise rising over 0.1 ms, dying away over 1 ms with a tail
# half as loud lasting 2 ms, coloured by these gains (dB at these
# frequencies, Hz, between them in log frequency): brightest around 10 kHz,
# with a soft low pop (300-700 Hz), like the recording's crackles.
CRACKLE_SHAPE = ((458, -8.5), (1025, -28.4), (2121, -10.3), (3873, -10.0), (6325, -8.3),
                 (9381, 0.0), (12410, -1.6), (15875, -7.0), (20785, -13.8))
CRACKLE_ATTACK, CRACKLE_DECAY, CRACKLE_TAIL, CRACKLE_TAIL_TIME = 0.0001, 0.001, 0.5, 0.002
CRACKLE_LENGTH = 960   # samples (20 ms)
# Between the crackles, the recording's treble is not even static but many tiny
# crackles of its own: about 1200 a second, of varied sizes (log-normal, spread
# HISS_SPREAD), mixed with smooth noise in each treble band in these shares.
HISS_CLICKS = 1200
HISS_SPREAD = 0.8
HISS_LARGEST = 3.0   # times the median tiny crackle
HISS_MIX = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0.66, 0.74, 0.81, 0.55)


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


def _click_train(count):
    rng = numpy.random.RandomState(SEED + 2000)
    number = rng.poisson(HISS_CLICKS * count / RATE)
    where = rng.randint(0, count, number)
    # The largest are held to the size of the smaller crackles heard over it.
    size = numpy.minimum(rng.lognormal(0, HISS_SPREAD, number), HISS_LARGEST) * rng.choice((-1, 1), number)
    out = numpy.zeros(count)
    numpy.add.at(out, where, size)
    return out


def _background(count, levels=None):
    levels = LEVELS if levels is None else levels
    noise = numpy.fft.rfft(numpy.random.RandomState(SEED).standard_normal(count))
    clicks = numpy.fft.rfft(_click_train(count))
    freqs = numpy.fft.rfftfreq(count, 1 / RATE)
    t = numpy.arange(count) / RATE
    out = numpy.zeros(count)
    for index, band in enumerate(levels):
        weights = band_weights(freqs, index)
        part = numpy.fft.irfft(noise * weights, count)
        part /= part.std() + 1e-12
        share = HISS_MIX[index]
        if share:
            tiny = numpy.fft.irfft(clicks * weights, count)
            part = share * tiny / (tiny.std() + 1e-12) + numpy.sqrt(1 - share * share) * part
        times = numpy.arange(len(band)) * band_step(index)
        out += part * numpy.interp(t, times, 10 ** (numpy.array(band) / 20))
    return out


def _crackles(count):
    rng = numpy.random.RandomState(SEED + 1000)
    n = CRACKLE_LENGTH
    t = numpy.arange(n) / RATE
    envelope = numpy.where(t < CRACKLE_ATTACK, 0.5 - 0.5 * numpy.cos(numpy.pi * t / CRACKLE_ATTACK), 1.0)
    after = numpy.maximum(0, t - CRACKLE_ATTACK)
    envelope *= numpy.exp(-after / CRACKLE_DECAY) + CRACKLE_TAIL * numpy.exp(-after / CRACKLE_TAIL_TIME)
    # The colour is given to a longer run of noise, and the crackle cut from its
    # middle: it starts cleanly, with no ringing before it.
    long = 4096
    freqs = numpy.fft.rfftfreq(long, 1 / RATE)
    centres, gains = zip(*CRACKLE_SHAPE)
    colour = 10 ** (numpy.interp(numpy.log(numpy.maximum(freqs, 1)), numpy.log(centres), gains) / 20)
    colour *= numpy.clip((freqs - 150) / 150, 0, 1)
    pad = numpy.fft.rfftfreq(2 * n, 1 / RATE) > 3000
    out = numpy.zeros(count)
    for when, peak in CRACKLES:
        coloured = numpy.fft.irfft(numpy.fft.rfft(rng.standard_normal(long)) * colour, long)
        burst = coloured[1024:1024 + n] * envelope
        bright = numpy.fft.irfft(numpy.fft.rfft(numpy.concatenate([burst, numpy.zeros(n)])) * pad, 2 * n)[:n]
        top = int(numpy.argmax(abs(bright[:round((CRACKLE_ATTACK + 0.001) * RATE)])))
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


def fire_pcm(rate, channels):
    """The mixer's interleaved 16-bit samples of the sound."""
    samples = numpy.clip(numpy.round(fire_samples(rate) * 32767), -32768, 32767).astype('<i2')
    return numpy.repeat(samples[:, None], channels, 1).tobytes()
