import ctypes
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
import wave

import numpy as np

from pop2.audio import MixerPlayback
from pop2.audio_loop import PcmSustain, gate_loop_bounds
from pop2.paths import ASSET_DIR


def write_pcm(path, samples, rate=48000):
    with wave.open(str(path), 'wb') as writer:
        writer.setparams((2, 2, rate, 0, 'NONE', ''))
        writer.writeframes(samples.astype('<i2').tobytes())


class SustainPcmTests(unittest.TestCase):
    def test_intro_plays_once_across_arbitrary_buffers_and_multiple_loop_wraps(self):
        source = np.repeat(np.arange(37, dtype=np.int16)[:, None], 2, axis=1)
        sustain = PcmSustain(None, source.tobytes(), 2, 11, 32)
        expected = np.r_[source[:11], np.tile(source[11:32], (100, 1))][:1000]
        for size in (1, 7, 31, 512, 2048):
            with self.subTest(buffer=size):
                out = np.zeros_like(expected)
                position = 0
                for start in range(0, len(out), size):
                    position = sustain.fill(out[start:start + size], position)
                np.testing.assert_array_equal(out, expected)
                np.testing.assert_array_equal(sustain.samples, source)

    def test_metadata_is_in_source_frames_and_invalid_regions_fail_explicitly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'gate.wav')
            write_pcm(path, np.ones((3000, 2), np.int16), 24000)
            info = {'loop': dict(rate=24000, start=1200, end=2900, count=65535)}
            self.assertEqual(gate_loop_bounds(path, info, 48000), (2400, 5800))
            self.assertIsNone(gate_loop_bounds(path, {}, 48000))
            for overrides in ({'end': 3001}, {'start': 2900}, {'rate': 44100}, {'count': 0}):
                with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                    gate_loop_bounds(path, {'loop': info['loop'] | overrides}, 48000)

    def test_legacy_recognition_does_not_apply_original_offsets_by_duration_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, 'gate.wav')
            with wave.open(str(path), 'wb') as writer:
                writer.setparams((1, 2, 11025, 0, 'NONE', ''))
                writer.writeframes(bytes(11524 * 2))
            self.assertIsNone(gate_loop_bounds(path, {}, 48000))

    @unittest.skipUnless((ASSET_DIR / 'audio/cue-17.wav').is_file(),
                         'Requires locally imported original cue17')
    def test_existing_original_import_gets_its_native_loop_without_reimport(self):
        self.assertEqual(gate_loop_bounds(ASSET_DIR / 'audio/cue-17.wav', {}, 48000),
                         (round(5025 * 48000 / 11025), round(11520 * 48000 / 11025)))


class SustainSdlTests(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {'SDL_AUDIODRIVER': 'dummy'})
        env.start()
        self.addCleanup(env.stop)
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name)
        # Distinct intro, sustain and unused outro reject whole-file repeats,
        # skipped intros, repeated intros, cursor resets and wrap-boundary gaps.
        values = np.r_[np.arange(1300) + 2000, np.arange(1600) - 6000,
                       np.full(100, 12000)].astype(np.int16)
        self.source = np.repeat(values[:, None], 2, axis=1)
        write_pcm(path / 'gate.wav', self.source)
        write_pcm(path / 'stop.wav', np.zeros((4800, 2), np.int16))
        cues = {17: {'file': 'gate.wav', 'loop': dict(rate=48000, start=1300, end=2900, count=65535)},
                18: {'file': 'stop.wav'}, 26: {'file': 'stop.wav'}}
        self.playback = MixerPlayback(path, cues, mix_mechanisms=True, split_mechanisms=True)
        self.addCleanup(self.playback.close)
        self.playback.gate_lifetime = 1000
        self.sustain = self.playback.gate_sustain
        self.blocks = []
        callback_type = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)

        def capture(_user, stream, length):
            self.blocks.append(np.frombuffer(ctypes.string_at(stream, length), np.int16).reshape(-1, 2).copy())

        self.capture = callback_type(capture)
        self.library = self.playback.gate_release.library
        self.library.Mix_SetPostMix.argtypes = [callback_type, ctypes.c_void_p]
        self.library.Mix_SetPostMix(self.capture, None)
        self.addCleanup(lambda: self.library.Mix_SetPostMix(callback_type(), None))

    def wait_blocks(self, count):
        deadline = time.monotonic() + 2
        while len(self.blocks) < count and time.monotonic() < deadline:
            time.sleep(.002)
        self.assertGreaterEqual(len(self.blocks), count)

    def test_actual_sdl_output_follows_intro_then_tail_even_across_carrier_wraps(self):
        original = self.playback.sounds[17].get_raw()
        self.playback.play('mechanism', 17)
        self.wait_blocks(22)
        self.playback.stop('mechanism')
        recorded = np.concatenate(self.blocks)
        first = np.flatnonzero(recorded[:, 0])[0]
        actual = recorded[first:first + 9500]
        expected = np.r_[self.source[:1300], np.tile(self.source[1300:2900], (8, 1))][:len(actual)]
        np.testing.assert_array_equal(actual, expected)
        self.assertEqual(self.playback.sounds[17].get_raw(), original)
        self.assertFalse(self.sustain.positions)

    def test_two_direction_cursors_pause_release_and_channel_reuse_are_independent(self):
        self.playback.play('mechanism', 17)
        self.wait_blocks(5)
        opening_channel = self.playback.effect_channel
        self.playback.play('closing', 17)
        self.wait_blocks(len(self.blocks) + 2)
        closing_channel = self.playback.closing_voice.effect_channel
        self.assertIn(opening_channel, self.sustain.positions)
        self.assertIn(closing_channel, self.sustain.positions)
        self.assertNotEqual(self.sustain.positions[opening_channel], self.sustain.positions[closing_channel])
        self.playback.pause(True)
        positions = self.sustain.positions.copy()
        time.sleep(.04)
        self.assertEqual(self.sustain.positions, positions)
        self.playback.pause(False)
        self.playback.play('closing', 18)
        time.sleep(.10)
        self.assertIn(opening_channel, self.sustain.positions)
        self.assertNotIn(closing_channel, self.sustain.positions)
        self.playback.play('closing', 17)
        new_channel = self.playback.closing_voice.effect_channel
        self.assertIn(new_channel, self.sustain.positions)
        self.playback.stop('closing')
        self.assertNotIn(new_channel, self.sustain.positions)
        self.assertIn(opening_channel, self.sustain.positions)
        self.playback.stop('mechanism')
        self.assertFalse(self.sustain.positions)

    def test_duck_and_release_process_the_generated_sustain_not_the_carrier(self):
        self.playback.play('mechanism', 17)
        self.wait_blocks(5)
        self.playback.play_effect(26)
        self.wait_blocks(len(self.blocks) + 4)
        # Both callbacks coexist; the envelope follows the generated tail.
        ducked = np.concatenate(self.blocks[-2:])
        self.assertTrue(np.all(ducked[:, 0] < 0))
        self.assertLess(np.max(np.abs(ducked.astype(int))), 2200)
        self.playback.play('mechanism', 18)
        self.wait_blocks(len(self.blocks) + 11)
        self.assertFalse(np.concatenate(self.blocks[-2:]).any())
        self.assertFalse(self.sustain.positions)


if __name__ == '__main__':
    unittest.main()
