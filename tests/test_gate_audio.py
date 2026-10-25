import json
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from pop2.audio import AudioEngine
from pop2.audio_duck import GATE_IMPACT_GAIN
from pop2.mechanism_audio import GateSound
from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceState
from pop2.terrain import TerrainMotion
from tests.test_audio import TimedPlayback
from tests import test_audio_duck, test_pressure_plates, test_terrain


class GateControllerAudioTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_pressure_plates.PressurePlateTests()
        self.fixture.setUp()
        self.plates = self.fixture.plates
        self.terrain = self.fixture.terrain

    def test_native_ids_keep_direction_and_source_before_coalescing(self):
        self.fixture.set_tile(0, 16, 4, 100)
        self.plates.active.update({(0, 15): 2, (0, 16): 1})
        self.assertEqual(self.plates.advance(self.terrain), (17, 17))
        self.assertEqual(self.plates.gate_sounds,
                         [GateSound(17, True, (0, 15)), GateSound(17, False, (0, 16))])

    def test_finishing_gate_is_attributed_without_changing_the_other_gate(self):
        self.fixture.set_tile(0, 15, 4, 180)
        self.fixture.set_tile(0, 16, 4, 20)
        self.plates.active.update({(0, 15): 2, (0, 16): 2})
        self.assertEqual(self.plates.advance(self.terrain), (18, 17))
        self.assertEqual(self.plates.gate_sounds,
                         [GateSound(18, True, (0, 15)), GateSound(17, True, (0, 16))])

    def test_exit_is_opening_and_notifications_are_per_frame(self):
        self.fixture.set_tile(0, 15, 17, 77)
        self.plates.active[0, 15] = 1
        for cue in (17, 18):
            self.assertEqual(self.plates.advance(self.terrain), (cue,))
            self.assertEqual(self.plates.gate_sounds, [GateSound(cue, True, (0, 15))])
        self.assertEqual(self.plates.advance(self.terrain), ())
        self.assertEqual(self.plates.gate_sounds, [])

    def test_crush_stop_and_final_slam_keep_closing_attribution(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        state = SequenceState(118, action=264, target_x=310, facing=1, sequence_mode=3)
        motion = TerrainMotion(0, 1, dead=True)
        self.plates.foreground[0, 15] = 0x300 | 82
        self.plates.active[0, 15] = 1
        self.assertEqual(self.plates.advance(self.terrain, state, motion, record), (17, 20, 18))
        self.assertEqual(self.plates.gate_sounds,
                         [GateSound(cue, False, (0, 15)) for cue in (17, 20, 18)])
        state.action, state.sequence_mode = 266, 0
        self.plates.foreground[0, 15] = 0x300 | 56
        self.plates.active[0, 15] = 1
        self.plates.advance(self.terrain, state, motion, record)
        self.assertEqual(self.plates.gate_sounds[-1], GateSound(None, False, (0, 15)))


class GateEngineAudioTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = directory.name
        cues = {str(cue): {'file': 'sample.wav', 'mode': 1, 'priority': priority, 'duration': 1}
                for cue, priority in ((17, 110), (18, 110), (20, 80), (26, 8))}
        Path(directory.name, 'manifest.json').write_text(json.dumps({'schema': 1, 'cues': cues}))
        self.audio = AudioEngine(directory.name, playback=object())
        self.backend = TimedPlayback(self.audio.cues)
        self.audio.playback = Mock(wraps=self.backend)
        self.audio.playback.sustain_gate = Mock()

    def frame(self, *events):
        state = SimpleNamespace(actor_type=0, sound_events=[event.cue for event in events
                                                          if event.cue is not None])
        self.audio.drain(state, gate_events=events)
        self.audio.flush()

    def test_opposite_motions_mix_but_same_direction_requests_coalesce(self):
        events = (GateSound(17, True, (0, 1)), GateSound(17, True, (0, 2)),
                  GateSound(17, False, (0, 3)), GateSound(17, False, (0, 4)))
        for _ in range(5):
            self.frame(*events)
        self.assertTrue(self.backend.busy('mechanism'))
        self.assertTrue(self.backend.busy('closing'))
        self.assertEqual(self.audio.playback.play.call_count, 2)
        self.assertEqual(self.audio.playback.sustain_gate.call_count, 8)

    def test_each_direction_can_stop_without_cutting_the_opposite_motion(self):
        for opening, bus, other in ((True, 'mechanism', 'closing'), (False, 'closing', 'mechanism')):
            with self.subTest(opening=opening):
                self.audio.reset()
                self.frame(GateSound(17, opening, (0, 1)), GateSound(17, not opening, (0, 2)))
                self.frame(GateSound(18, opening, (0, 1)), GateSound(17, not opening, (0, 2)))
                self.assertEqual(getattr(self.audio, f'current_{bus}'), 18)
                self.assertEqual(getattr(self.audio, f'current_{other}'), 17)
                self.assertTrue(self.backend.busy(other))

    def test_one_gate_finishing_does_not_stop_others_in_the_same_direction(self):
        for events in ((GateSound(18, True, (0, 1)), GateSound(17, True, (0, 2))),
                       (GateSound(17, True, (0, 2)), GateSound(18, True, (0, 1)))):
            with self.subTest(events=events):
                self.audio.reset()
                self.frame(*events)
                self.assertEqual(self.audio.current_mechanism, 17)

    def test_reversal_releases_old_direction_unless_another_gate_still_needs_it(self):
        self.frame(GateSound(17, True, (0, 1)))
        self.frame(GateSound(17, False, (0, 1)))
        self.assertIsNone(self.audio.current_mechanism)
        self.assertFalse(self.backend.busy('mechanism'))
        self.assertEqual(self.audio.current_closing, 17)
        self.frame(GateSound(17, True, (0, 2)), GateSound(17, False, (0, 1)))
        self.assertTrue(self.backend.busy('mechanism'))
        self.assertTrue(self.backend.busy('closing'))

    def test_fast_close_and_crush_slam_do_not_lose_to_its_own_stop_cue(self):
        self.frame(GateSound(17, True, (0, 2)),
                   *(GateSound(cue, False, (0, 1)) for cue in (17, 20, 18)))
        self.assertEqual((self.audio.current_mechanism, self.audio.current_closing), (17, 20))

    def test_crush_silence_does_not_suppress_another_opening_or_closing_gate(self):
        for opening in (True, False):
            self.audio.reset()
            self.frame(GateSound(17, opening, (0, 2)), GateSound(17, False, (0, 1)))
            self.frame(GateSound(17, opening, (0, 2)), GateSound(17, False, (0, 1)),
                       GateSound(None, False, (0, 1)))
            bus = 'mechanism' if opening else 'closing'
            self.assertEqual(getattr(self.audio, f'current_{bus}'), 17)
            self.assertTrue(self.backend.busy(bus))

    def test_empty_controller_frame_releases_only_continuous_motion(self):
        self.frame(GateSound(17, True, (0, 1)), GateSound(20, False, (0, 2)))
        self.frame()
        self.assertIsNone(self.audio.current_mechanism)
        self.assertFalse(self.backend.busy('mechanism'))
        self.assertEqual(self.audio.current_closing, 20)
        self.assertTrue(self.backend.busy('closing'))

    def test_pause_and_reset_cancel_unflushed_attribution(self):
        self.audio.pause(True)
        self.frame(GateSound(17, True, (0, 1)), GateSound(17, False, (0, 2)))
        self.audio.playback.play.assert_not_called()
        self.assertTrue(self.audio.effect_busy)
        self.audio.reset()
        self.audio.pause(False)
        self.audio.flush()
        self.audio.playback.play.assert_not_called()
        self.assertFalse(self.audio.effect_busy)

    def test_native_comparison_ignores_direction_and_untagged_calls_keep_arbitration(self):
        for mixed in (True, False):
            audio = AudioEngine(self.directory, playback=Mock(wraps=self.backend), mix_mechanisms=mixed)
            events = (GateSound(17, True, (0, 1)), GateSound(20, False, (0, 2)))
            state = SimpleNamespace(actor_type=0, sound_events=[17, 20])
            if mixed:
                audio.drain(state)
            else:
                audio.drain(state, gate_events=events)
            audio.flush()
            audio.playback.play.assert_called_once_with('mechanism' if mixed else 'effect', 20)


class OppositeGateSdlTests(test_audio_duck.SdlGateDuckTests):
    split_mechanisms = True

    def test_actual_sdl_output_contains_both_motions_with_independent_stops(self):
        self.playback.play('mechanism', 17)
        normal = self.level()
        self.playback.play('closing', 17)
        self.assertAlmostEqual(self.level() / normal, 2, delta=.002)
        opening = self.playback.channels['mechanism'].get_sound()
        self.playback.play('closing', 18)
        self.assertIs(self.playback.channels['mechanism'].get_sound(), opening)
        self.assertTrue(self.playback.busy('mechanism'))
        self.playback.stop('closing')
        time.sleep(.03)
        self.assertAlmostEqual(self.level(), normal, delta=1)

    def test_approved_impact_duck_applies_to_both_motions(self):
        self.playback.play('mechanism', 17)
        self.playback.play('closing', 17)
        normal = self.level()
        self.playback.play_effect(26)
        time.sleep(.03)
        self.assertAlmostEqual(self.level() / normal, GATE_IMPACT_GAIN, delta=.002)
        time.sleep(.28)
        self.assertAlmostEqual(self.level() / normal, 1, delta=.002)

    def test_delayed_closing_slam_preserves_opening_and_its_sample_clock(self):
        self.playback.play('mechanism', 17)
        self.playback.play('closing', 17)
        self.playback.play('closing', 20)
        self.assertTrue(self.playback.busy('mechanism'))
        self.assertIs(self.playback.channels['mechanism'].get_sound(), self.playback.sounds[17])
        time.sleep(.03)
        self.assertAlmostEqual(self.level(), 8192, delta=1)
        voice = self.playback.closing_voice
        self.assertEqual((voice.effect_channel, voice.tail_channel), (7, 6))
        self.playback.pause(True)
        time.sleep(.21)
        self.assertTrue(self.playback.busy('closing'))
        self.playback.pause(False)
        self.playback.stop('closing')
        self.assertTrue(self.playback.busy('mechanism'))

    def test_secondary_channels_follow_mute_reset_and_never_enter_the_effect_pool(self):
        self.playback.play('mechanism', 17)
        self.playback.play('closing', 17)
        self.playback.play_effect(26)
        self.assertGreaterEqual(min(self.playback.effect_channel_ids.values()), 8)
        for bus in ('mechanism', 'closing', 'effect'):
            self.playback.set_volume(bus, 0)
        self.assertEqual(self.level(), 0)
        for bus in ('mechanism', 'closing', 'effect'):
            self.playback.stop(bus)
        self.assertFalse(self.duck.roles)
        self.assertFalse(self.playback.gate_release.positions)


@unittest.skipUnless((ASSET_DIR / 'caverns_level4.json').is_file(),
                     'Original cavern assets have not been imported')
class GateSceneAudioTests(unittest.TestCase):
    def setUp(self):
        test_terrain.RooftopSceneTests.setUp(self)
        self.scene.load_level(4)
        self.scene.peaceful = self.scene.god_mode = True
        self.scene.audio = AudioEngine(playback=object())
        self.backend = TimedPlayback(self.scene.audio.cues)
        self.scene.audio.playback = Mock(wraps=self.backend)
        plates = self.scene.game.caverns.plates
        self.gates = [(room, cell) for room in range(32) for cell in range(30)
                      if self.scene.level_map.tile(room, cell % 10, cell // 10).kind == 4][:2]
        self.assertEqual(len(self.gates), 2)
        plates.active.clear()
        plates.foreground[self.gates[0]] = 0
        plates.active[self.gates[0]] = 2

    def test_real_frame_routes_opposite_motion_to_two_voices(self):
        plates = self.scene.game.caverns.plates
        plates.foreground[self.gates[1]] = 100
        plates.active[self.gates[1]] = 1
        test_terrain.RooftopSceneTests.tick(self)
        self.assertEqual((self.scene.audio.current_mechanism, self.scene.audio.current_closing), (17, 17))
        self.assertTrue(self.backend.busy('mechanism'))
        self.assertTrue(self.backend.busy('closing'))
        self.assertEqual(plates.gate_sounds, [])

    def test_real_frame_keeps_opening_under_another_gates_fast_slam(self):
        plates = self.scene.game.caverns.plates
        plates.foreground[self.gates[1]] = 40
        plates.active[self.gates[1]] = 4
        test_terrain.RooftopSceneTests.tick(self)
        self.assertEqual((self.scene.audio.current_mechanism, self.scene.audio.current_closing), (17, 20))
        self.assertEqual(plates.foreground[self.gates[0]], 4)
        self.assertEqual(plates.foreground[self.gates[1]], 0)


if __name__ == '__main__':
    unittest.main()
