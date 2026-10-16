import ctypes
import unittest
from unittest.mock import Mock

import numpy as np

from pop2.audio_release import PcmRelease


class PcmReleaseTests(unittest.TestCase):
    def setUp(self):
        self.release = PcmRelease.__new__(PcmRelease)
        self.release.gain = ((1 + np.cos(np.linspace(0, np.pi, 576))) / 2)[:, None]
        self.release.positions = {0: 0, 2: 0}
        self.release.channels = 2

    def test_release_has_no_per_buffer_volume_steps(self):
        for block in (64, 512, 1024, 2048):
            for channels in (1, 2):
                with self.subTest(block=block, channels=channels):
                    output = np.full((4096, channels), 10000, dtype=np.int16)
                    position = 0
                    for start in range(0, len(output), block):
                        position = self.release.apply(output[start:start + block],
                                                      self.release.gain, position)
                    self.assertEqual(position, 576)
                    np.testing.assert_array_equal(output[0], 10000)
                    self.assertFalse(output[575:].any())
                    steps = np.diff(output[:576], axis=0)
                    self.assertTrue((steps <= 0).all())
                    self.assertLess(abs(steps).max(), 30)

    def test_callback_processes_only_the_registered_channel_and_leaves_silence(self):
        buffer = (ctypes.c_int16 * 1024)(*[10000] * 1024)
        self.release.process(0, ctypes.addressof(buffer), ctypes.sizeof(buffer), None)
        self.assertEqual(self.release.positions, {0: 512, 2: 0})
        self.assertEqual(buffer[0], 10000)
        self.assertGreater(buffer[-1], 0)
        self.release.process(0, ctypes.addressof(buffer), ctypes.sizeof(buffer), None)
        self.assertEqual(self.release.positions, {0: 576, 2: 0})
        self.assertFalse(any(buffer[128:]))
        self.release.process(0, ctypes.addressof(buffer), ctypes.sizeof(buffer), None)
        self.assertFalse(any(buffer))

    def test_signed_full_scale_stereo_is_attenuated_without_overflow(self):
        samples = np.tile(np.array([-32768, 32767], dtype=np.int16), (1024, 1))
        self.release.apply(samples, self.release.gain, 0)
        expected = np.rint(np.array([-32768, 32767]) * self.release.gain).astype(np.int16)
        np.testing.assert_array_equal(samples[:576], expected)
        self.assertFalse(samples[576:].any())

    def test_start_resets_the_sample_cursor_and_expires_only_the_silent_tail(self):
        self.release.library = Mock()
        self.release.callback = Mock()
        self.release.positions[2] = 576
        self.release.start(2)
        self.assertEqual(self.release.positions[2], 0)
        self.release.library.Mix_RegisterEffect.assert_called_once_with(
            2, self.release.callback, None, None)
        self.release.library.Mix_ExpireChannel.assert_called_once_with(2, 80)

    def test_registration_errors_are_not_silent(self):
        self.release.library = Mock()
        self.release.callback = Mock()
        self.release.library.Mix_RegisterEffect.return_value = 0
        with self.assertRaisesRegex(RuntimeError, 'gate audio release'):
            self.release.start(0)
        self.release.library.Mix_ExpireChannel.assert_not_called()

    def test_cancellation_removes_even_an_effect_registered_after_a_sample_finished(self):
        self.release.library = Mock()
        self.release.callback = Mock()
        self.release.cancel(0)
        self.release.library.Mix_UnregisterEffect.assert_called_once_with(0, self.release.callback)
        self.assertNotIn(0, self.release.positions)
        self.release.cancel(0)
        self.assertEqual(self.release.library.Mix_UnregisterEffect.call_count, 1)


if __name__ == '__main__':
    unittest.main()
