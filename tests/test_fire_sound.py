import unittest
import wave
from pathlib import Path

import numpy

from pop2 import fire_sound


class FireSoundTests(unittest.TestCase):
    def setUp(self):
        self.sound = fire_sound.fire_samples()

    def test_one_second_that_is_the_same_on_every_run(self):
        self.assertEqual(len(self.sound), fire_sound.RATE)
        numpy.testing.assert_array_equal(self.sound, fire_sound.fire_samples())
        self.assertEqual(len(fire_sound.fire_pcm(44100, 2)), 44100 * 2 * 2)

    def test_every_band_has_levels_for_the_whole_second(self):
        self.assertEqual(len(fire_sound.LEVELS), len(fire_sound.EDGES) - 1)
        for index, levels in enumerate(fire_sound.LEVELS):
            self.assertGreaterEqual((len(levels) - 1) * fire_sound.band_step(index), fire_sound.SECONDS - 1e-9)

    def test_it_swells_to_about_two_thirds_and_fades_to_silence_as_the_users_edit(self):
        loudness = [numpy.sqrt((self.sound[i:i + 2400] ** 2).mean()) for i in range(0, len(self.sound), 2400)]
        loudest = int(numpy.argmax(loudness))
        self.assertIn(loudest, range(11, 15))                  # 0.55-0.75 s
        self.assertLess(loudness[0], loudness[loudest] / 5)    # it catches quietly
        self.assertLess(abs(self.sound[-1]), 1e-4)            # no click at the end
        self.assertLess(abs(self.sound).max(), 0.2)            # the recording peaks at 11% of full scale
        # Most of it is a deep rumble, as the recording (about 93% below 200 Hz).
        power = abs(numpy.fft.rfft(self.sound)) ** 2
        freqs = numpy.fft.rfftfreq(len(self.sound), 1 / fire_sound.RATE)
        self.assertGreater(power[freqs < 200].sum() / power.sum(), 0.85)

    def test_its_hiss_is_many_tiny_crackles_not_static(self):
        # Between the crackles, the 6-12 kHz hiss is spiky like the recording's
        # (kurtosis about 7); the first version's static was 3, heard as thin and cold.
        freqs = numpy.fft.rfftfreq(len(self.sound), 1 / fire_sound.RATE)
        treble = numpy.fft.irfft(numpy.fft.rfft(self.sound) * ((freqs >= 6000) & (freqs < 12000)), len(self.sound))
        crackles = [round(when * fire_sound.RATE) for when, _peak in fire_sound.CRACKLES]
        kurtosis = []
        for start in range(2400, 45000, 960):
            if any(start - 240 <= crackle < start + 1200 for crackle in crackles):
                continue
            piece = treble[start:start + 960] - treble[start:start + 960].mean()
            kurtosis.append((piece ** 4).mean() / (piece ** 2).mean() ** 2)
        self.assertGreater(numpy.median(kurtosis), 5)

    def test_it_follows_the_users_recording_when_it_is_installed(self):
        recording = Path(__file__).resolve().parents[1] / 'assets' / 'audio' / 'menu-burn.wav'
        if not recording.is_file():
            self.skipTest("The user's own fire recording is not installed")
        with wave.open(str(recording)) as handle:
            data = numpy.frombuffer(handle.readframes(handle.getnframes()), '<i2')
            original = data.reshape(-1, handle.getnchannels())[:, 0] / 32768
        made = self.sound[:len(original)]

        def levels(x):
            return numpy.array([10 * numpy.log10((x[i:i + 2400] ** 2).mean() + 1e-12) for i in range(0, 45600, 2400)])

        # Every 50 ms until the last, within about 1 dB on average and 4 dB at most.
        difference = abs(levels(made) - levels(original))
        self.assertLess(difference.mean(), 1.5)
        self.assertLess(difference.max(), 4.5)


if __name__ == '__main__':
    unittest.main()
