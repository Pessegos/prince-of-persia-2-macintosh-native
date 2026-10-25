import ctypes
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

import numpy as np

from pop2.audio import AudioEngine, MixerPlayback
from pop2.audio_duck import DuckEnvelope, GATE_IMPACT_GAIN
from pop2.audio_formats import Sample
from pop2.paths import ASSET_DIR


class DuckEnvelopeTests(unittest.TestCase):
    def test_attack_hold_and_release_are_sample_accurate_across_buffer_sizes(self):
        for channels in (1, 2):
            for block in (64, 512, 1024, 4096):
                with self.subTest(channels=channels, block=block):
                    envelope = DuckEnvelope(48000)
                    output = np.full((12000, channels), 10000, dtype=np.int16)
                    for start in range(0, 6000, block):
                        envelope.apply(output[start:min(start + block, 6000)], True)
                    for start in range(6000, len(output), block):
                        envelope.apply(output[start:start + block], False)
                    self.assertEqual(output[0, 0], 10000)
                    self.assertEqual(output[575, 0], round(10000 * GATE_IMPACT_GAIN))
                    self.assertEqual(output[5999, 0], output[575, 0])
                    self.assertEqual(output[6000, 0], output[5999, 0])
                    self.assertTrue((output[11759:] == 10000).all())
                    max_step = np.ceil(10000 * (1 - GATE_IMPACT_GAIN) * np.pi
                                       / (2 * (envelope.attack - 1))) + 1
                    self.assertLess(abs(np.diff(output[:, 0].astype(int))).max(), max_step)

    def test_isolated_gate_is_bit_identical_including_full_scale(self):
        source = np.tile(np.array([-32768, 32767], np.int16), (4096, 1))
        samples = source.copy()
        DuckEnvelope(48000).apply(samples, False)
        np.testing.assert_array_equal(samples, source)

    def test_retrigger_during_release_starts_at_current_gain_without_a_jump(self):
        envelope = DuckEnvelope(48000)
        samples = np.full((1024, 2), 10000, np.int16)
        envelope.apply(samples, True)
        samples.fill(10000)
        envelope.apply(samples, False)
        last = samples[-1, 0]
        samples.fill(10000)
        envelope.apply(samples, True)
        self.assertEqual(samples[0, 0], last)
        self.assertEqual(samples[-1, 0], round(10000 * GATE_IMPACT_GAIN))


class SdlGateDuckTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        # A constant gate and silent impact let the output measure only gain.
        Path(self.directory.name, 'gate.wav').write_bytes(Sample(b'\xa0' * 8000, 8000).wav())
        Path(self.directory.name, 'impact.wav').write_bytes(Sample(b'\x80' * 1600, 8000).wav())
        Path(self.directory.name, 'other.wav').write_bytes(Sample(b'\xa0' * 1600, 8000).wav())
        cues = {cue: {'file': 'gate.wav' if cue == 17 else
                      'impact.wav' if cue == 26 else 'other.wav'}
                for cue in (17, 18, 20, 26, 61)}
        env = patch.dict(os.environ, {'SDL_AUDIODRIVER': 'dummy'})
        env.start()
        self.addCleanup(env.stop)
        self.playback = MixerPlayback(self.directory.name, cues, mix_mechanisms=True,
                                      split_mechanisms=getattr(self, 'split_mechanisms', False))
        self.addCleanup(self.playback.close)
        self.duck = self.playback.gate_duck
        self.blocks = []
        callback_type = ctypes.CFUNCTYPE(None, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)

        def capture(_user, stream, length):
            self.blocks.append(np.frombuffer(ctypes.string_at(stream, length), np.int16).copy())

        self.capture = callback_type(capture)
        self.library = self.duck.library
        self.library.Mix_SetPostMix.argtypes = [callback_type, ctypes.c_void_p]
        self.library.Mix_SetPostMix(self.capture, None)
        self.addCleanup(lambda: self.library.Mix_SetPostMix(callback_type(), None))

    def level(self):
        first = len(self.blocks)
        time.sleep(.05)
        blocks = self.blocks[first:]
        self.assertTrue(blocks)
        return float(np.median(np.concatenate(blocks)))

    def test_actual_pcm_ducks_in_both_start_orders_then_recovers_without_restart(self):
        for gate_first in (True, False):
            with self.subTest(gate_first=gate_first):
                self.playback.stop('mechanism')
                self.playback.stop('effect')
                if gate_first:
                    self.playback.play('mechanism', 17)
                    normal = self.level()
                    self.playback.play_effect(26)
                else:
                    self.playback.play_effect(26)
                    self.playback.play('mechanism', 17)
                    normal = 8192
                door = self.playback.channels['mechanism'].get_sound()
                time.sleep(.04)
                self.assertAlmostEqual(self.level() / normal, GATE_IMPACT_GAIN, delta=.002)
                time.sleep(.27)
                self.assertAlmostEqual(self.level() / normal, 1, delta=.002)
                self.assertIs(self.playback.channels['mechanism'].get_sound(), door)
                self.assertTrue(self.playback.busy('mechanism'))
                self.assertNotIn('impact', self.duck.roles.values())

    def test_pause_mute_explicit_stop_and_reset_do_not_leave_a_stuck_duck(self):
        self.playback.play('mechanism', 17)
        self.playback.play_effect(26)
        time.sleep(.04)
        self.playback.pause(True)
        envelope = self.duck.envelopes[self.playback.effect_channel]
        position = envelope.position
        time.sleep(.25)
        self.assertEqual(envelope.position, position)
        self.assertIn('impact', self.duck.roles.values())
        self.playback.set_volume('mechanism', 0)
        self.playback.set_volume('effect', 0)
        self.playback.pause(False)
        self.playback.stop_effect(26)
        time.sleep(.16)
        self.assertEqual(self.level(), 0)
        self.playback.set_volume('mechanism', 1)
        self.assertAlmostEqual(self.level(), 8192, delta=1)
        self.playback.stop('mechanism')
        self.playback.stop('effect')
        self.assertFalse(self.duck.roles)
        self.assertFalse(self.duck.envelopes)

    def test_other_effects_and_gate_stop_or_slam_are_not_ducked(self):
        for cue in (18, 20):
            with self.subTest(cue=cue):
                self.playback.play('mechanism', 17)
                self.playback.play_effect(26)
                time.sleep(.04)
                self.playback.play('mechanism', cue)
                self.assertNotIn(self.playback.effect_channel, self.duck.envelopes)
                self.playback.stop('mechanism')
                self.playback.stop('effect')
        self.playback.play('mechanism', 17)
        self.playback.play_effect(61)
        time.sleep(.03)
        self.assertEqual(self.duck.envelopes[self.playback.effect_channel].gain, 1)
        self.assertNotIn('impact', self.duck.roles.values())

    def test_reused_effect_channel_and_repeated_gate_sustain_do_not_retrigger_duck(self):
        self.playback.play('mechanism', 17)
        self.playback.play_effect(26)
        time.sleep(.04)
        envelope = self.duck.envelopes[self.playback.effect_channel]
        self.playback.sustain_gate()
        self.assertIs(self.duck.envelopes[self.playback.effect_channel], envelope)
        self.playback.stop_effect(26)
        self.playback.play_effect(61)
        self.assertNotIn('impact', self.duck.roles.values())
        time.sleep(.16)
        self.assertEqual(envelope.gain, 1)


@unittest.skipUnless((ASSET_DIR / 'Prince.rsrc').is_file()
                     and (ASSET_DIR / 'audio' / 'manifest.json').is_file(),
                     'Original level/audio data has not been imported')
class ImportedGateImpactTests(unittest.TestCase):
    def test_overlapping_gate_adds_less_than_one_db_to_the_debris_burst(self):
        with patch.dict(os.environ, {'SDL_AUDIODRIVER': 'dummy'}):
            audio = AudioEngine()
            self.addCleanup(audio.close)
            samples = {}
            for cue in (17, 26):
                samples[cue] = np.frombuffer(audio.playback.sounds[cue].get_raw(),
                                             np.int16).reshape(-1, 2).copy()
            gate = samples[17]
            DuckEnvelope(48000).apply(gate, True)
            for milliseconds in (100, 250, 500, 950):
                with self.subTest(milliseconds=milliseconds):
                    count = milliseconds * 48
                    impact = samples[26][:count].astype(float)
                    mixed = impact + gate[:count]
                    excess = 10 * np.log10(np.sum(mixed ** 2) / np.sum(impact ** 2))
                    # The user's recording retained a 2.5 dB double impact
                    # with the earlier -3 dB gate duck. Keep this near unity.
                    self.assertLessEqual(excess, 1.0)
                    self.assertGreater(excess, 0)

    def test_room_nine_only_the_right_impact_has_a_gate_to_duck(self):
        from pop2.game_session import GameResources
        from pop2.pressure_plates import PressurePlates
        from pop2.terrain import LevelMap

        terrain = LevelMap(GameResources.load().level(5).data)
        with patch.dict(os.environ, {'SDL_AUDIODRIVER': 'dummy'}):
            audio = AudioEngine()
            self.addCleanup(audio.close)
            for cell, expected in ((22, [26, 65, 65]), (26, [26, 65, 17])):
                with self.subTest(cell=cell):
                    audio.reset()
                    plates = PressurePlates()
                    tile = terrain.tile(8, cell % 10, cell // 10)
                    cues = [26, *plates.impact(terrain, 8, cell, tile.kind),
                            *plates.advance(terrain)]
                    self.assertEqual(cues, expected)
                    for cue in cues:
                        audio.add_sound(cue)
                    audio.flush()
                    self.assertEqual(audio.playback.playing_effects(), (26,))
                    time.sleep(.04)
                    duck = audio.playback.gate_duck
                    if cell == 26:
                        envelope = duck.envelopes[audio.playback.effect_channel]
                        self.assertAlmostEqual(envelope.gain, GATE_IMPACT_GAIN)
                        self.assertTrue(audio.playback.busy('mechanism'))
                        self.assertEqual(plates.active[(21, 29)], 3)
                    else:
                        self.assertFalse(duck.envelopes)
                        self.assertFalse(audio.playback.busy('mechanism'))


if __name__ == '__main__':
    unittest.main()
