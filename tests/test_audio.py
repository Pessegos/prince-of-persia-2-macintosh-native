import io
import json
import os
from pathlib import Path
import random
import struct
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch
import wave

from pop2.audio import AudioEngine, GATE_SLAM_DELAY, MixerPlayback
from pop2.audio_formats import Sample, digitized_sound, mohawk_resources, standard_sound
from pop2.rebirth import DeathState


class TimedPlayback:
    """Deterministic cue clock; SDL integration tests cover actual PCM mixing."""

    def __init__(self, cues):
        self.cues = cues
        self.remaining = {"effect": 0, "mechanism": 0, "closing": 0, "music": 0}
        self.effects = {}
        self.paused = False

    def play(self, bus, cue):
        self.remaining[bus] = self.cues[cue]["duration"]

    def busy(self, bus):
        return self.remaining[bus] > 1e-9

    def play_effect(self, cue):
        if cue not in self.effects:
            self.effects[cue] = self.cues[cue]['duration']

    def playing_effects(self):
        return tuple(self.effects)

    def stop_effect(self, cue):
        self.effects.pop(cue, None)

    def advance(self, interval):
        if not self.paused:
            for bus in self.remaining:
                self.remaining[bus] = max(0, self.remaining[bus] - interval)
            self.effects = {cue: duration - interval for cue, duration in self.effects.items()
                            if duration - interval > 1e-9}

    def stop(self, bus):
        self.remaining[bus] = 0
        if bus == 'effect':
            self.effects.clear()

    def pause(self, paused):
        self.paused = paused

    def close(self):
        pass


class CueTests(unittest.TestCase):
    """Native foreground arbitration remains available as a comparison mode."""
    def test_cavern_banks_switch_for_combat_without_interrupting_foreground_songs(self):
        audio = self.audio
        audio.manifest['ambient'] = [{'starts': [40, 41, 42], 'counts': [0, 0, 1],
                                     'combat_group': 2}]
        level = bytearray(0x49ca)
        struct.pack_into('>h', level, 0x424a + (3 * 30 + 10 + 8) * 2, 1)
        audio.configure_level(level)
        audio.ambient(3, 1, 8)
        audio.flush()
        self.assertEqual((audio.current_music, audio.current_music_group), (41, 1))
        self.busy['music'] = True
        audio.ambient(3, 1, 8, fighting=True)
        self.assertIn(audio.pending_song, (42, 43))
        audio.flush()
        self.assertEqual(audio.current_music_group, 2)
        audio.ambient(3, 1, 8)
        self.assertEqual(audio.pending_song, 41)
        audio.flush()
        audio.add_song(38)
        audio.flush()
        audio.ambient(3, 1, 8, fighting=True)
        self.assertIsNone(audio.pending_song)

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.playback = Mock()
        self.busy = {"effect": False, "mechanism": False, "music": False}
        self.playback.busy.side_effect = self.busy.__getitem__
        cues = {str(i): {"mode": 1, "priority": i, "file": f"{i}.wav"}
                for i in (7, 11, 12, 17, 18, 20, 31, 38, 40, 41, 42, 43, 51, 60,
                          61, 119, 294, 295, 300)}
        for cue, priority in ((17, 110), (18, 110), (20, 80), (60, 125), (61, 90)):
            cues[str(cue)]['priority'] = priority
        manifest = {"schema": 1, "cues": cues, "death_cues": [38] * 16,
                    "level_one": {"bank": 0, "groups": [0] * 960},
                    "ambient": [{"starts": [40], "counts": [3], "combat_group": -1}]}
        Path(self.directory.name, "manifest.json").write_text(json.dumps(manifest))
        self.audio = AudioEngine(self.directory.name, self.playback, random.Random(1),
                                 mix_effects=False)

    def test_room_song_departure_cancels_a_still_pending_entry_request(self):
        self.audio.room_song((5, 2), 40)
        self.assertEqual(self.audio.pending_song, 40)
        self.audio.room_song((5, 3))
        self.audio.flush()
        self.playback.play.assert_not_called()

    def test_room_song_is_once_per_visit_and_reset_allows_a_new_entry(self):
        self.audio.room_song((5, 2), 40)
        self.audio.flush()
        self.playback.play.reset_mock()
        self.audio.room_song((5, 2), 40)
        self.audio.flush()
        self.playback.play.assert_not_called()
        self.audio.reset()
        self.audio.room_song((5, 2), 40)
        self.audio.flush()
        self.playback.play.assert_called_once_with('music', 40)

    def test_room_song_can_start_once_when_entered_with_ambient_disabled(self):
        self.audio.set_music_enabled(False)
        self.audio.room_song((5, 2), 40)
        self.assertIsNone(self.audio.pending_song)
        self.audio.set_music_enabled(True)
        self.audio.room_song((5, 2), 40)
        self.assertEqual(self.audio.pending_song, 40)

    def test_intro_audio_bypasses_game_effect_priority_and_preserves_pause(self):
        self.audio.add_sound(7)
        self.audio.play_intro(11, 1)
        self.assertIsNone(self.audio.pending_effect)
        self.playback.play.assert_called_with("effect", 11)
        self.audio.pause(True)
        self.audio.play_intro(40, 0)
        self.assertEqual(self.audio.current_music, 40)
        self.assertFalse(self.audio.current_music_ambient)
        self.playback.play.assert_called_with("music", 40)
        self.playback.pause.assert_called_with(True)

    def test_missing_intro_audio_requires_reimport(self):
        with self.assertRaisesRegex(ValueError, "import the game again"):
            self.audio.play_intro(25010, 0)

    def test_repeated_gate_requests_extend_playback_without_restarting_the_sample(self):
        self.audio.cues[17] = {"mode": 1, "priority": 110, "file": "17.wav"}
        self.audio.add_sound(17)
        self.audio.flush()
        self.busy['mechanism'] = True
        for _ in range(3):
            self.audio.add_sound(17)
            self.audio.flush()
        self.playback.play.assert_called_once_with('mechanism', 17)
        self.assertEqual(self.playback.sustain_gate.call_count, 3)

    def test_gate_repeat_respects_pause_but_is_independent_of_foreground_effects(self):
        self.audio.cues[17] = {"mode": 1, "priority": 110, "file": "17.wav"}
        self.audio.add_sound(17)
        self.audio.flush()
        self.busy['mechanism'] = True
        self.audio.add_sound(17)
        self.audio.pause(True)
        self.audio.flush()
        self.playback.sustain_gate.assert_not_called()
        self.audio.pause(False)
        self.audio.add_sound(7)
        self.audio.flush()
        self.playback.play.assert_any_call('effect', 7)
        self.playback.sustain_gate.assert_called_once()

    def test_door_and_bones_requested_in_the_same_tick_both_play(self):
        for cues in ((17, 61), (61, 17), (17, 60), (60, 17)):
            with self.subTest(cues=cues):
                self.audio.reset()
                self.playback.reset_mock()
                for cue in cues:
                    self.audio.add_sound(cue)
                self.assertTrue(self.audio.sound_playing(17))
                bones = next(cue for cue in cues if cue != 17)
                self.assertTrue(self.audio.sound_playing(bones))
                self.audio.flush()
                self.assertEqual(self.playback.play.call_args_list,
                                 [call('effect', bones), call('mechanism', 17)])

    def test_repeated_bones_do_not_cut_or_restart_the_moving_door(self):
        self.audio.add_sound(17)
        self.audio.flush()
        self.busy['mechanism'] = True
        for _ in range(8):
            self.audio.add_sound(17)
            self.audio.add_sound(61)
            self.audio.flush()
            self.busy['effect'] = True
        self.assertEqual(self.playback.play.call_args_list,
                         [call('mechanism', 17), call('effect', 61)])
        self.assertEqual(self.playback.sustain_gate.call_count, 8)
        self.assertTrue(self.audio.sound_playing(17))
        self.assertTrue(self.audio.sound_playing(61))

    def test_door_stop_replaces_movement_without_cutting_bones(self):
        self.audio.add_sound(17)
        self.audio.add_sound(61)
        self.audio.flush()
        self.busy.update(effect=True, mechanism=True)
        self.audio.add_sound(18)
        self.audio.flush()
        self.playback.play.assert_called_with('mechanism', 18)
        self.assertEqual(self.audio.current_effect, 61)
        self.assertFalse(self.audio.sound_playing(17))
        self.assertTrue(self.audio.sound_playing(18))
        self.assertTrue(self.audio.sound_playing(61))

    def test_stopping_bones_does_not_stop_the_door_and_vice_versa(self):
        self.audio.add_sound(17)
        self.audio.add_sound(61)
        self.audio.flush()
        self.busy.update(effect=True, mechanism=True)
        self.audio.stop_sound(61)
        self.playback.stop.assert_called_once_with('effect')
        self.assertTrue(self.audio.sound_playing(17))
        self.audio.stop_sound(17)
        self.assertEqual(self.playback.stop.call_args_list,
                         [call('effect'), call('mechanism')])

    def test_pending_mechanisms_are_cancelled_by_reset_and_not_flushed_while_paused(self):
        self.audio.pause(True)
        self.audio.add_sound(17)
        self.audio.add_sound(61)
        self.audio.flush()
        self.playback.play.assert_not_called()
        self.assertTrue(self.audio.effect_busy)
        self.audio.reset()
        self.audio.pause(False)
        self.audio.flush()
        self.playback.play.assert_not_called()
        self.assertIsNone(self.audio.pending_mechanism)
        self.assertIsNone(self.audio.current_mechanism)
        self.playback.stop.assert_any_call('mechanism')

    def test_mechanism_volume_follows_master_mute_without_stopping_its_clock(self):
        self.audio.add_sound(17)
        self.audio.flush()
        self.busy['mechanism'] = True
        self.audio.set_sound_enabled(False)
        self.playback.set_volume.assert_any_call('mechanism', 0.0)
        self.playback.stop.assert_not_called()
        self.assertTrue(self.audio.effect_busy)
        self.audio.set_sound_enabled(True)
        self.playback.set_volume.assert_any_call('mechanism', 1.0)

    def test_death_can_ignore_door_movement_but_not_a_foreground_impact(self):
        self.audio.add_sound(17)
        self.audio.flush()
        self.busy['mechanism'] = True
        self.assertTrue(self.audio.death_ready())
        self.audio.add_sound(7)
        self.assertFalse(self.audio.death_ready())
        self.audio.flush()
        self.busy['effect'] = True
        self.assertFalse(self.audio.death_ready())
        self.busy['effect'] = False
        self.assertTrue(self.audio.death_ready())

    def test_native_single_effect_arbitration_remains_available_for_comparison(self):
        audio = AudioEngine(self.directory.name, self.playback, mix_mechanisms=False)
        audio.cues[17]['priority'] = 110
        audio.add_sound(17)
        audio.flush()
        self.busy['effect'] = True
        audio.add_sound(61)
        audio.flush()
        self.assertEqual(self.playback.play.call_args_list,
                         [call('effect', 17), call('effect', 61)])
        self.assertFalse(audio.sound_playing(17))

    def test_song_playing_checks_pending_and_live_music_not_the_effect_channel(self):
        audio = self.audio
        self.assertFalse(audio.song_playing(40))
        audio.add_song(40)
        self.assertTrue(audio.song_playing(40))
        self.assertFalse(audio.song_playing(41))
        audio.flush()
        self.assertFalse(audio.song_playing(40))
        self.busy['music'] = True
        self.assertTrue(audio.song_playing(40))
        self.assertFalse(audio.sound_playing(40))

    def test_seek_offset_is_forwarded_without_losing_pause(self):
        self.audio.pause(True)
        self.audio.play_intro(40, 0, offset=2.5)
        self.playback.play.assert_called_with("music", 40, offset=2.5)
        self.playback.pause.assert_called_with(True)

    def test_pending_effect_uses_priority_and_current_effect_rejects_lower_priority(self):
        audio = self.audio
        audio.add_sound(294)
        audio.add_sound(12)
        audio.add_sound(31)
        audio.flush()
        self.playback.play.assert_called_once_with("effect", 12)
        self.busy["effect"] = True
        audio.add_sound(294)
        audio.flush()
        self.assertEqual(self.playback.play.call_count, 1)
        self.assertIsNone(audio.pending_effect)

    def test_sound_playing_checks_the_requested_cue_not_any_effect(self):
        self.audio.current_effect = 12
        self.busy["effect"] = True
        self.assertTrue(self.audio.sound_playing(12))
        self.assertFalse(self.audio.sound_playing(51))
        self.audio.pending_effect = 51
        self.assertTrue(self.audio.sound_playing(51))
        self.busy["effect"] = False
        self.audio.pending_effect = None
        self.assertFalse(self.audio.sound_playing(12))

    def test_mode_one_does_not_restart_itself_but_mode_two_can(self):
        audio = self.audio
        audio.add_sound(12)
        audio.flush()
        self.busy["effect"] = True
        audio.add_sound(12)
        audio.flush()
        self.assertEqual(self.playback.play.call_count, 1)
        audio.cues[12]["mode"] = 2
        audio.add_sound(12)
        audio.flush()
        self.assertEqual(self.playback.play.call_count, 2)

    def test_music_keeps_first_pending_request_and_has_a_separate_bus(self):
        self.audio.add_song(40)
        self.audio.add_song(41)
        self.audio.add_sound(12)
        self.audio.flush()
        self.assertEqual(self.audio.current_music, 40)
        self.assertEqual(self.audio.current_effect, 12)
        self.assertEqual(self.playback.play.call_count, 2)

    def test_drain_clears_offscreen_events_without_playing_them_later(self):
        state = SimpleNamespace(sound_events=[294, 12], actor_type=2)
        self.audio.drain(state, audible=False)
        self.audio.flush()
        self.assertEqual(state.sound_events, [])
        self.playback.play.assert_not_called()
        state.sound_events = [294]
        self.audio.drain(state)
        self.audio.flush()
        self.playback.play.assert_called_once_with("effect", 294)

    def test_suppressed_actor_footsteps_do_not_suppress_the_guards(self):
        self.audio.add_sound(294, actor_type=1)
        self.assertIsNone(self.audio.pending_effect)
        self.audio.add_sound(294, actor_type=2)
        self.assertEqual(self.audio.pending_effect, 294)

    def test_bridge_fight_plays_its_special_song_instead_of_the_combat_group(self):
        # SpecialMusic 5:5398-53bc: BrgFight (119) in level five's bridge rooms.
        audio = self.audio
        audio.manifest['ambient'] = [{'starts': [40, 41, 42], 'counts': [0, 0, 1],
                                     'combat_group': 2}]
        level = bytearray(0x49ca)
        struct.pack_into('>h', level, 0x424a + (3 * 30 + 10 + 8) * 2, 1)
        audio.configure_level(level)
        audio.ambient(3, 1, 8)
        audio.flush()
        self.busy['music'] = True
        audio.ambient(3, 1, 8, fighting=True, special=119)
        self.assertEqual(audio.pending_song, 119)
        audio.flush()
        self.assertEqual((audio.current_music, audio.current_music_group), (119, 2))
        audio.ambient(3, 1, 8, fighting=True, special=119)
        self.assertIsNone(audio.pending_song)
        audio.ambient(3, 1, 8, special=119)
        self.assertEqual(audio.pending_song, 41)

    def test_ambient_avoids_repeating_and_waits_for_current_song(self):
        audio = self.audio
        audio.current_music = 40
        audio.ambient(3, 1, 8)
        self.assertIn(audio.pending_song, (41, 42, 43))
        audio.flush()
        self.busy["music"] = True
        audio.ambient(6, 1, 5, fighting=True)
        self.assertIsNone(audio.pending_song)
        self.busy["music"] = False
        audio.ambient(6, 1, 5, fighting=True)
        self.assertIn(audio.pending_song, (40, 41, 42, 43))

    def test_ambient_includes_last_song_and_wraps_repeats(self):
        self.audio.rng = Mock()
        self.audio.rng.randrange.return_value = 3
        self.audio.ambient(3, 1, 8)
        self.assertEqual(self.audio.pending_song, 43)
        self.audio.flush()
        self.audio.ambient(3, 1, 8)
        self.assertEqual(self.audio.pending_song, 40)

    def test_dead_player_does_not_restart_ambient_music(self):
        self.audio.ambient(3, 1, 8, alive=False)
        self.assertIsNone(self.audio.pending_song)

    def test_pause_freezes_playback_and_does_not_flush_a_new_cue(self):
        self.audio.add_sound(12)
        self.audio.pause(True)
        self.audio.flush()
        self.playback.play.assert_not_called()
        self.audio.pause(False)
        self.audio.flush()
        self.playback.play.assert_called_once_with("effect", 12)

    def test_reset_cancels_both_current_and_pending_audio(self):
        self.audio.add_sound(12)
        self.audio.add_song(40)
        self.audio.reset()
        self.audio.flush()
        self.playback.play.assert_not_called()
        self.assertIsNone(self.audio.current_music)
        self.assertIsNone(self.audio.current_effect)

    def test_master_mute_changes_both_volumes_without_stopping_the_cue_clock(self):
        self.audio.add_song(38)
        self.audio.flush()
        self.busy["music"] = True
        self.audio.set_sound_enabled(False)
        self.assertFalse(self.audio.sound_enabled)
        self.playback.set_volume.assert_any_call("music", 0.0)
        self.playback.set_volume.assert_any_call("effect", 0.0)
        self.playback.stop.assert_not_called()
        self.assertTrue(self.audio.music_busy)
        self.audio.reset()
        self.assertFalse(self.audio.sound_enabled)
        self.audio.set_sound_enabled(True)
        self.playback.set_volume.assert_any_call("music", 1.0)
        self.playback.set_volume.assert_any_call("effect", 1.0)

    def test_music_toggle_cancels_only_ambient_and_preserves_effects(self):
        self.audio.ambient(3, 1, 8)
        self.audio.add_sound(12)
        self.audio.set_music_enabled(False)
        self.assertIsNone(self.audio.pending_song)
        self.audio.flush()
        self.playback.play.assert_called_once_with("effect", 12)
        self.audio.ambient(3, 1, 8)
        self.assertIsNone(self.audio.pending_song)
        self.audio.reset()
        self.assertFalse(self.audio.music_enabled)
        self.audio.set_music_enabled(True)
        self.audio.ambient(3, 1, 8)
        self.audio.flush()
        self.audio.set_music_enabled(False)
        self.playback.stop.assert_called_with("music")
        self.assertIsNone(self.audio.current_music)

    def test_disabling_ambient_preserves_death_music_current_or_pending(self):
        self.audio.death_song(14)
        self.audio.set_music_enabled(False)
        self.assertEqual(self.audio.pending_song, 38)
        self.audio.flush()
        self.audio.set_music_enabled(False)
        self.playback.stop.assert_not_called()
        self.assertEqual(self.audio.current_music, 38)

    def test_stop_sound_cancels_only_the_matching_current_or_pending_effect(self):
        self.audio.add_sound(12)
        self.audio.flush()
        self.busy["effect"] = True
        self.audio.add_sound(31)
        self.audio.stop_sound(31)
        self.assertIsNone(self.audio.pending_effect)
        self.assertEqual(self.audio.current_effect, 12)
        self.playback.stop.assert_not_called()
        self.audio.stop_sound(12)
        self.playback.stop.assert_called_once_with("effect")
        self.assertIsNone(self.audio.current_effect)

    def test_death_waits_for_real_audio_not_a_literal_duration(self):
        death = DeathState()
        death.begin(14)
        self.busy["effect"] = True
        death.advance(185, 100, self.audio)
        self.assertEqual(death.counter, 0)
        self.busy["effect"] = False
        for _ in range(7):
            death.advance(185, 0, self.audio)
        self.assertTrue(death.can_restart)
        self.assertEqual(self.audio.pending_song, 38)
        death.advance(185, 1000, self.audio)
        self.assertFalse(death.prompt_visible)
        self.audio.flush()
        self.busy["music"] = True
        death.advance(185, 1000, self.audio)
        self.assertFalse(death.prompt_visible)
        self.busy["music"] = False
        death.advance(185, 0, self.audio)
        self.assertTrue(death.prompt_visible)


    def test_music_elapsed_counts_playing_time_without_pauses(self):
        clock = [100.0]
        with patch('pop2.audio.time.monotonic', side_effect=lambda: clock[0]):
            self.assertIsNone(self.audio.music_elapsed())
            self.audio.add_song(119)
            self.audio.flush()
            self.busy['music'] = True
            clock[0] = 103.0
            self.assertAlmostEqual(self.audio.music_elapsed(), 3.0)
            self.audio.pause(True)
            clock[0] = 110.0
            self.assertAlmostEqual(self.audio.music_elapsed(), 3.0)
            self.audio.pause(False)
            clock[0] = 111.5
            self.assertAlmostEqual(self.audio.music_elapsed(), 4.5)
            self.busy['music'] = False
            self.assertIsNone(self.audio.music_elapsed())


class PolyphonicCueTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        Path(self.directory.name, 'sample.wav').write_bytes(
            Sample(b'\x90\x70' * 4000, 8000).wav())
        cues = {str(cue): {'mode': 1, 'priority': cue, 'file': 'sample.wav'}
                for cue in (7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18, 20, 27, 31,
                            38, 40, 51, 60, 61, 69, 71, 192, 272, 294, 295, 296, 300)}
        cues['17']['priority'] = cues['18']['priority'] = 110
        Path(self.directory.name, 'manifest.json').write_text(json.dumps({
            'schema': 1, 'cues': cues, 'death_cues': [38] * 16}))
        env = patch.dict(os.environ, {'SDL_AUDIODRIVER': 'dummy'})
        env.start()
        self.addCleanup(env.stop)
        self.audio = AudioEngine(self.directory.name)
        self.addCleanup(self.audio.close)
        self.playback = self.audio.playback
        time.sleep(.02)

    def test_distinct_effects_mix_regardless_of_priority_or_request_order(self):
        for cues in ((61, 294, 7), (7, 294, 61)):
            with self.subTest(cues=cues):
                self.audio.reset()
                for cue in cues:
                    self.audio.add_sound(cue)
                    self.assertTrue(self.audio.sound_playing(cue))
                self.audio.flush()
                self.assertEqual(set(self.playback.playing_effects()), set(cues))
                self.assertEqual(len({id(channel) for channel in self.playback.effects.values()}), 3)
                self.assertTrue(all(self.audio.sound_playing(cue) for cue in cues))

    def test_new_effect_does_not_cut_an_already_playing_effect(self):
        self.audio.add_sound(61)
        self.audio.flush()
        bones = self.playback.effects[61]
        self.audio.add_sound(7)
        self.audio.flush()
        self.assertIs(self.playback.effects[61], bones)
        self.assertTrue(bones.get_busy())
        self.assertTrue(self.audio.sound_playing(7))

    def test_pool_grows_past_default_sdl_channel_count_without_stealing(self):
        cues = (7, 8, 9, 13, 14, 15, 27, 31, 51, 60, 61, 69, 71, 294, 295, 296)
        for cue in cues:
            self.audio.add_sound(cue)
        self.audio.flush()
        self.assertEqual(set(self.playback.playing_effects()), set(cues))
        self.assertEqual(len(self.playback.effect_channels), len(cues))
        self.assertTrue(all(channel.get_busy() for channel in self.playback.effects.values()))

    def test_same_cue_is_coalesced_and_never_restarted_even_for_mode_two(self):
        self.audio.cues[61]['mode'] = 2
        for _ in range(20):
            self.audio.add_sound(61)
        self.audio.flush()
        self.assertEqual(len(self.playback.effect_channels), 1)
        time.sleep(.6)
        for _ in range(20):
            self.audio.add_sound(61)
            self.audio.flush()
        self.assertEqual(len(self.playback.effect_channels), 1)
        time.sleep(.55)
        self.assertFalse(self.audio.sound_playing(61))
        self.audio.add_sound(61)
        self.audio.flush()
        self.assertTrue(self.audio.sound_playing(61))
        self.assertEqual(len(self.playback.effect_channels), 1)

    def test_stop_sound_is_selective_and_idle_channels_are_reused(self):
        for cue in (61, 294, 17):
            self.audio.add_sound(cue)
        self.audio.flush()
        first = self.playback.effects[61]
        self.audio.stop_sound(61)
        self.assertFalse(self.audio.sound_playing(61))
        self.assertTrue(self.audio.sound_playing(294))
        self.assertTrue(self.audio.sound_playing(17))
        self.audio.add_sound(7)
        self.audio.flush()
        self.assertIs(self.playback.effects[7], first)
        self.assertEqual(len(self.playback.effect_channels), 2)

    def test_doors_keep_one_shared_channel_while_distinct_effects_mix(self):
        for _ in range(10):
            self.audio.add_sound(17)
        for cue in (61, 294):
            self.audio.add_sound(cue)
        self.audio.flush()
        self.assertNotIn(17, self.playback.effects)
        self.assertEqual(set(self.playback.playing_effects()), {61, 294})
        self.audio.add_sound(18)
        self.audio.flush()
        self.assertIs(self.playback.channels['mechanism'].get_sound(), self.playback.sounds[18])
        self.assertEqual(set(self.playback.playing_effects()), {61, 294})

    def test_pause_mute_and_reset_apply_to_all_active_and_future_effects(self):
        for cue in (61, 294):
            self.audio.add_sound(cue)
        self.audio.flush()
        self.audio.pause(True)
        time.sleep(1.05)
        self.assertEqual(set(self.playback.playing_effects()), {61, 294})
        self.audio.add_sound(7)
        self.audio.flush()
        self.assertNotIn(7, self.playback.playing_effects())
        self.assertTrue(self.audio.sound_playing(7))
        self.audio.set_sound_enabled(False)
        self.assertTrue(all(channel.get_volume() == 0 for channel in self.playback.effect_channels))
        self.audio.pause(False)
        self.audio.flush()
        self.assertTrue(self.audio.sound_playing(7))
        self.assertEqual(self.playback.effects[7].get_volume(), 0)
        self.assertTrue(self.audio.effect_busy)
        self.audio.set_sound_enabled(True)
        self.assertTrue(all(channel.get_volume() == 1 for channel in self.playback.effect_channels))
        self.audio.add_sound(8)
        self.audio.reset()
        self.audio.flush()
        self.assertFalse(self.audio.effect_busy)
        self.assertFalse(self.playback.playing_effects())
        self.assertFalse(self.audio.pending_effects)

    def test_effect_pool_never_steals_music_menu_or_mechanism_channels(self):
        self.audio.add_song(40)
        self.audio.add_sound(17)
        self.audio.flush()
        self.playback.play_ui('click')
        music = self.playback.channels['music'].get_sound()
        door = self.playback.channels['mechanism'].get_sound()
        menu = self.playback.ui_channels['click'].get_sound()
        for cue in (7, 8, 9, 13, 14, 15, 27, 31, 51, 60, 61, 69, 71, 294, 295):
            self.audio.add_sound(cue)
        self.audio.flush()
        self.assertIs(self.playback.channels['music'].get_sound(), music)
        self.assertIs(self.playback.channels['mechanism'].get_sound(), door)
        self.assertIs(self.playback.ui_channels['click'].get_sound(), menu)
        self.assertTrue(self.audio.song_playing(40))
        self.assertTrue(self.audio.sound_playing(17))

    def test_death_waits_for_all_relevant_effects_not_only_the_latest(self):
        self.audio.add_sound(7)
        self.audio.add_sound(272)
        self.audio.flush()
        self.assertFalse(self.audio.death_ready())
        self.audio.stop_sound(7)
        self.assertTrue(self.audio.death_ready())
        self.assertTrue(self.audio.effect_busy)
        self.audio.stop_sound(272)
        self.assertFalse(self.audio.effect_busy)

    def test_contact_still_suppresses_the_same_ticks_redundant_empty_swing(self):
        for contact in (10, 12, 31):
            with self.subTest(contact=contact):
                self.audio.reset()
                for cue in (11, 294, contact):
                    self.audio.add_sound(cue)
                self.audio.flush()
                self.assertEqual(set(self.playback.playing_effects()), {294, contact})

    def test_intro_effect_clears_game_effects_and_pending_requests(self):
        self.audio.add_sound(61)
        self.audio.flush()
        self.audio.add_sound(294)
        self.audio.play_intro(7, 1)
        self.audio.flush()
        self.assertFalse(self.playback.playing_effects())
        self.assertTrue(self.audio.sound_playing(7))
        self.assertFalse(self.audio.sound_playing(294))

    def test_stop_discards_stale_frame_events_without_blocking_later_frames(self):
        self.audio.add_sound(8)
        self.audio.flush()
        self.audio.stop_sound(8)
        state = SimpleNamespace(sound_events=[8, 7], actor_type=0)
        self.audio.drain(state)
        self.audio.flush()
        self.assertEqual(set(self.playback.playing_effects()), {7})
        self.assertFalse(state.sound_events)
        state.sound_events = [8]
        self.audio.drain(state)
        self.audio.flush()
        self.assertTrue(self.audio.sound_playing(8))

    def test_active_effect_is_not_resubmitted_to_playback(self):
        with patch.object(self.playback, 'play_effect', wraps=self.playback.play_effect) as play:
            for _ in range(5):
                self.audio.add_sound(61)
                self.audio.flush()
            play.assert_called_once_with(61)


class FormatTests(unittest.TestCase):
    def test_pcm_wav_preserves_samples_rate_and_channel_count(self):
        sample = Sample(bytes((0, 64, 128, 255)), 11127)
        with wave.open(io.BytesIO(sample.wav())) as reader:
            self.assertEqual((reader.getframerate(), reader.getnchannels()), (11127, 1))
            self.assertEqual(reader.readframes(4), sample.pcm)

    def test_sustain_metadata_is_opt_in_and_does_not_modify_pcm(self):
        sample = Sample(b"\x80" * 8, 22050, loop_start=2, loop_end=7)
        self.assertNotIn(b"smpl", sample.wav())
        self.assertIn(b"smpl", sample.wav(sustain=True))
        with wave.open(io.BytesIO(sample.wav(sustain=True))) as reader:
            self.assertEqual(reader.readframes(8), sample.pcm)

    def test_mohawk_pcm_data_and_truncation(self):
        header = struct.pack(">IHBB", 11025 << 16, 4, 8, 1) + bytes(12)
        chunk = b"Data" + struct.pack(">I", len(header) + 4) + header + b"abcd"
        sample = digitized_sound(chunk)
        self.assertEqual((sample.pcm, sample.rate), (b"abcd", 11025))
        with self.assertRaises(ValueError):
            digitized_sound(chunk[:-1])

    def test_standard_sound_header_and_truncation(self):
        data = struct.pack(">HHHHHI", 2, 0, 1, 0x8051, 0, 14)
        data += struct.pack(">5IBB", 0, 4, 22050 << 16, 0, 0, 0, 67) + b"abcd"
        sample = standard_sound(data)
        self.assertEqual((sample.pcm, sample.base_note), (b"abcd", 67))
        with self.assertRaises(ValueError):
            standard_sound(data[:-1])

    def test_invalid_mohawk_header_and_tables_are_rejected(self):
        for data in (b"", b"MHWK" + bytes(4) + b"RSRC" + bytes(16)):
            with self.assertRaises(ValueError):
                mohawk_resources(data)


class SdlPlaybackTests(unittest.TestCase):
    def test_mechanism_loop_survives_foreground_playback_and_stop(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'sample.wav').write_bytes(Sample(b'\x90\x70' * 4000, 8000).wav())
            cues = {cue: {'file': 'sample.wav'} for cue in (17, 18, 61)}
            with patch.dict(os.environ, {'SDL_AUDIODRIVER': 'dummy'}):
                playback = MixerPlayback(directory, cues, mix_mechanisms=True)
                try:
                    playback.play('mechanism', 17)
                    movement = playback.channels['mechanism']
                    playback.play('effect', 61)
                    self.assertTrue(movement.get_busy())
                    self.assertIs(movement.get_sound(), playback.sounds[17])
                    self.assertTrue(playback.busy('effect'))
                    self.assertEqual(playback.effect_channel, 5)
                    playback.stop('effect')
                    self.assertTrue(movement.get_busy())
                    self.assertFalse(playback.busy('effect'))
                    playback.play('effect', 61)
                    playback.play('mechanism', 18)
                    self.assertIs(playback.gate_tail, movement)
                    self.assertIs(playback.channels['mechanism'].get_sound(), playback.sounds[18])
                    self.assertIs(playback.channels['effect'].get_sound(), playback.sounds[61])
                    playback.play('effect', 61)
                    self.assertTrue(playback.gate_tail.get_busy())
                    self.assertEqual(playback.gate_release.positions[5], 0)
                    playback.stop('mechanism')
                    self.assertFalse(playback.gate_tail.get_busy())
                    self.assertFalse(playback.busy('mechanism'))
                    self.assertTrue(playback.busy('effect'))
                finally:
                    playback.close()

    def test_mixed_mechanism_pause_mute_and_close_include_both_gate_channels(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'sample.wav').write_bytes(Sample(b'\x90\x70' * 8000, 8000).wav())
            cues = {cue: {'file': 'sample.wav'} for cue in (17, 18, 61)}
            with patch.dict(os.environ, {'SDL_AUDIODRIVER': 'dummy'}):
                playback = MixerPlayback(directory, cues, mix_mechanisms=True)
                try:
                    time.sleep(.02)
                    playback.play('mechanism', 17)
                    playback.play('effect', 61)
                    playback.pause(True)
                    time.sleep(.04)
                    for bus in ('effect', 'mechanism'):
                        self.assertTrue(playback.busy(bus))
                    playback.pause(False)
                    playback.play('mechanism', 18)
                    playback.pause(True)
                    position = playback.gate_release.positions[5]
                    time.sleep(.04)
                    self.assertEqual(playback.gate_release.positions[5], position)
                    playback.set_volume('effect', .5)
                    self.assertEqual(playback.channels['effect'].get_volume(), .5)
                    self.assertEqual(playback.channels['mechanism'].get_volume(), 1)
                    playback.set_volume('mechanism', 0)
                    self.assertFalse(playback.gate_tail.get_busy())
                    self.assertTrue(playback.busy('mechanism'))
                    self.assertEqual(playback.channels['mechanism'].get_volume(), 0)
                    playback.pause(False)
                finally:
                    playback.close()
                self.assertFalse(playback.gate_release.positions)
                self.assertIsNone(playback.mixer.get_init())

    def test_gate_slam_has_exact_eleven_frame_lead_in_without_changing_the_sample(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'sample.wav').write_bytes(Sample(b'\x90\x70' * 1000, 8000).wav())
            cues = {20: {'file': 'sample.wav'}, 27: {'file': 'sample.wav'}}
            with patch.dict(os.environ, {'SDL_AUDIODRIVER': 'dummy'}):
                from pygame import mixer
                make_sound = mixer.Sound
                loaded = []

                def load_sound(*args, **kwargs):
                    sound = make_sound(*args, **kwargs)
                    if args:
                        loaded.append(sound.get_raw())
                    return sound

                with patch.object(mixer, 'Sound', side_effect=load_sound):
                    playback = MixerPlayback(directory, cues)
                try:
                    delayed = playback.sounds[20].get_raw()
                    self.assertEqual(GATE_SLAM_DELAY, 11 / 60)
                    self.assertEqual(delayed, bytes(8800 * 4) + loaded[0])
                    self.assertEqual(playback.sounds[27].get_raw(), loaded[1])
                    playback.play('effect', 20)
                    playback.pause(True)
                    time.sleep(.2)
                    self.assertTrue(playback.busy('effect'))
                    self.assertIs(playback.channels['effect'].get_sound(), playback.sounds[20])
                    playback.pause(False)
                    playback.stop('effect')
                    self.assertFalse(playback.busy('effect'))
                finally:
                    playback.close()

    def test_gate_sustain_crosses_multiple_repeats_but_is_not_an_infinite_orphan(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'sample.wav').write_bytes(
                Sample(bytes((128, 140, 160, 140, 128, 116, 96, 116)) * 80, 8000).wav())
            cues = {17: {'file': 'sample.wav'}, 18: {'file': 'sample.wav'}}
            with patch.dict(os.environ, {'SDL_AUDIODRIVER': 'dummy'}):
                playback = MixerPlayback(directory, cues)
                try:
                    playback.play('effect', 17)
                    sound = playback.channels['effect'].get_sound()
                    for _ in range(12):
                        time.sleep(.02)
                        self.assertTrue(playback.busy('effect'))
                        playback.sustain_gate()
                        self.assertIs(playback.channels['effect'].get_sound(), sound)
                    playback.pause(True)
                    time.sleep(.12)
                    playback.pause(False)
                    self.assertTrue(playback.busy('effect'))
                    playback.sustain_gate()
                    time.sleep(.12)
                    self.assertFalse(playback.busy('effect'))
                finally:
                    playback.close()

    def test_clean_stop_release_also_crosses_a_loop_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'sample.wav').write_bytes(Sample(b'\x90' * 40, 8000).wav())
            cues = {17: {'file': 'sample.wav'}, 18: {'file': 'sample.wav'}}
            with patch.dict(os.environ, {'SDL_AUDIODRIVER': 'dummy'}):
                playback = MixerPlayback(directory, cues)
                try:
                    playback.gate_lifetime = 1000
                    playback.play('effect', 17)
                    playback.play('effect', 18)
                    time.sleep(.04)
                    self.assertEqual(playback.gate_release.positions[0], 576)
                finally:
                    playback.close()

    def test_mixer_can_close_while_a_gate_release_is_active(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "sample.wav").write_bytes(Sample(b"\x90" * 1600, 8000).wav())
            cues = {17: {"file": "sample.wav"}, 18: {"file": "sample.wav"}}
            with patch.dict(os.environ, {"SDL_AUDIODRIVER": "dummy"}):
                playback = MixerPlayback(directory, cues)
                try:
                    playback.play("effect", 17)
                    playback.play("effect", 18)
                finally:
                    playback.close()
                self.assertIsNone(playback.mixer.get_init())

    def test_gate_stop_starts_immediately_with_a_short_independent_movement_tail(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "sample.wav").write_bytes(Sample(b"\x90" * 1600, 8000).wav())
            cues = {17: {"file": "sample.wav"}, 18: {"file": "sample.wav"}}
            with patch.dict(os.environ, {"SDL_AUDIODRIVER": "dummy"}):
                playback = MixerPlayback(directory, cues)
                try:
                    time.sleep(0.02)
                    playback.set_volume("effect", 0.5)
                    playback.play("effect", 17)
                    movement = playback.channels["effect"]
                    movement_sound = movement.get_sound()
                    original = playback.sounds[17].get_raw()
                    playback.play("effect", 18)
                    self.assertIs(playback.gate_tail, movement)
                    self.assertIs(playback.channels["effect"].get_sound(), playback.sounds[18])
                    self.assertIs(playback.gate_tail.get_sound(), movement_sound)
                    self.assertIs(movement_sound, playback.sounds[17])
                    self.assertEqual(playback.sounds[17].get_raw(), original)
                    self.assertEqual(playback.channels["effect"].get_volume(), 0.5)
                    playback.pause(True)
                    position = playback.gate_release.positions[0]
                    time.sleep(0.04)
                    self.assertEqual(playback.gate_release.positions[0], position)
                    self.assertTrue(playback.busy("effect"))
                    playback.pause(False)
                    time.sleep(0.10)
                    self.assertFalse(playback.gate_tail.get_busy())
                    self.assertEqual(playback.gate_release.positions[0], 576)
                    self.assertEqual(playback.sounds[17].get_raw(), original)
                    self.assertTrue(playback.busy("effect"))
                    playback.stop("effect")
                    self.assertFalse(playback.busy("effect"))
                    playback.play("effect", 17)
                    playback.play("effect", 18)
                    playback.set_volume("effect", 0)
                    self.assertFalse(playback.gate_tail.get_busy())
                    self.assertEqual(playback.channels["effect"].get_volume(), 0)
                    self.assertTrue(playback.busy("effect"))
                finally:
                    playback.close()

    def test_real_sdl_channels_pause_resume_and_stop_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "sample.wav").write_bytes(Sample(b"\x90" * 800, 8000).wav())
            cues = {1: {"file": "sample.wav"}}
            with patch.dict(os.environ, {"SDL_AUDIODRIVER": "dummy"}):
                playback = MixerPlayback(directory, cues)
                try:
                    # SDL_mixer uses tick zero as its unpaused sentinel.
                    time.sleep(0.02)
                    playback.play("music", 1)
                    playback.play("effect", 1)
                    playback.set_volume("music", 0.0)
                    playback.play("music", 1)
                    self.assertEqual(playback.channels["music"].get_volume(), 0.0)
                    self.assertTrue(playback.busy("music"))
                    self.assertTrue(playback.busy("effect"))
                    playback.pause(True)
                    time.sleep(0.16)
                    self.assertTrue(playback.busy("music"))
                    playback.stop("effect")
                    self.assertFalse(playback.busy("effect"))
                    playback.pause(False)
                    time.sleep(0.16)
                    self.assertFalse(playback.busy("music"))
                finally:
                    playback.close()


class MixerSeekTests(unittest.TestCase):
    def test_pcm_offset_is_aligned_to_whole_sample_frames(self):
        playback = MixerPlayback.__new__(MixerPlayback)
        playback.mixer = Mock()
        playback.mixer.get_init.return_value = (48000, -16, 2)
        original = Mock()
        pcm = bytes(range(256)) * 1000
        original.get_raw.return_value = pcm
        playback.sounds = {40: original}
        channel = Mock()
        playback.channels = {"music": channel}
        playback.play("music", 40, offset=.25)
        playback.mixer.Sound.assert_called_once_with(buffer=pcm[48000:])
        channel.play.assert_called_once_with(playback.mixer.Sound.return_value)
        playback.play("music", 40, offset=100)
        channel.stop.assert_called_once()


class MixerGateTransitionTests(unittest.TestCase):
    def setUp(self):
        self.playback = MixerPlayback.__new__(MixerPlayback)
        self.playback.sounds = {cue: Mock() for cue in (7, 17, 18, 20)}
        self.effect, self.music, self.tail = Mock(), Mock(), Mock()
        self.playback.channels = {"effect": self.effect, "music": self.music}
        self.playback.gate_tail = self.tail
        self.playback.effects = {}
        self.playback.effect_channels = []
        self.playback.effect_channel, self.playback.tail_channel = 0, 2
        self.playback.gate_release = Mock()
        self.playback.gate_duck = None
        self.playback.gate_lifetime = 1045
        self.effect.get_sound.return_value = self.playback.sounds[17]
        self.effect.get_busy.return_value = True
        self.effect.get_volume.return_value = 0.5

    def test_gate_movement_loops_in_the_mixer_without_a_queued_restart(self):
        self.playback.play('effect', 17)
        self.effect.play.assert_called_once_with(self.playback.sounds[17], loops=-1)
        self.effect.queue.assert_not_called()
        self.playback.gate_release.expire.assert_called_once_with(0, 1045)

    def test_only_an_active_movement_sample_can_have_its_deadline_renewed(self):
        self.effect.get_sound.return_value = self.playback.sounds[20]
        self.playback.sustain_gate()
        self.effect.get_sound.return_value = self.playback.sounds[17]
        self.effect.get_busy.return_value = False
        self.playback.sustain_gate()
        self.playback.gate_release.expire.assert_not_called()

    def test_music_playback_of_the_same_resource_is_not_looped(self):
        self.playback.play('music', 17)
        self.music.play.assert_called_once_with(self.playback.sounds[17])
        self.playback.gate_release.expire.assert_not_called()

    def test_only_a_playing_gate_movement_to_stop_transition_gets_a_fading_tail(self):
        self.playback.play("effect", 18)
        self.assertIs(self.playback.channels["effect"], self.tail)
        self.assertIs(self.playback.gate_tail, self.effect)
        self.playback.gate_release.start.assert_called_once_with(0)
        self.assertEqual((self.playback.effect_channel, self.playback.tail_channel), (2, 0))
        self.effect.fadeout.assert_not_called()
        self.tail.set_volume.assert_called_once_with(0.5)
        self.tail.play.assert_called_once_with(self.playback.sounds[18])
        self.tail.queue.assert_not_called()
        self.effect.stop.assert_not_called()
        self.effect.play.assert_not_called()

    def test_unrelated_cue_replacement_is_unchanged(self):
        self.playback.play("effect", 7)
        self.effect.play.assert_called_once_with(self.playback.sounds[7])
        self.effect.fadeout.assert_not_called()
        self.tail.play.assert_not_called()
        self.playback.gate_release.start.assert_not_called()

    def test_delayed_slam_releases_movement_smoothly_without_cutting_its_attack(self):
        self.playback.play('effect', 20)
        self.assertIs(self.playback.channels['effect'], self.tail)
        self.playback.gate_release.start.assert_called_once_with(0)
        self.effect.stop.assert_not_called()
        self.tail.play.assert_called_once_with(self.playback.sounds[20])
        self.playback.gate_release.cancel.assert_called_once_with(2)

    def test_consecutive_stops_release_the_correct_alternating_channel(self):
        self.playback.play("effect", 18)
        self.playback.play("effect", 17)
        self.tail.get_sound.return_value = self.playback.sounds[17]
        self.tail.get_busy.return_value = True
        self.playback.play("effect", 18)
        self.assertEqual(self.playback.gate_release.start.call_args_list, [call(0), call(2)])
        self.assertEqual((self.playback.effect_channel, self.playback.tail_channel), (0, 2))
        self.assertIs(self.playback.channels["effect"], self.effect)

    def test_new_effect_clears_the_previous_release_tail(self):
        self.playback.play("effect", 18)
        self.playback.play("effect", 20)
        self.effect.stop.assert_called_once_with()
        self.tail.play.assert_called_with(self.playback.sounds[20])

    def test_finished_movement_does_not_leave_a_tail(self):
        self.effect.get_busy.return_value = False
        self.playback.play("effect", 18)
        self.effect.play.assert_called_once_with(self.playback.sounds[18])
        self.effect.fadeout.assert_not_called()
        self.playback.gate_release.start.assert_not_called()

    def test_stop_after_another_cue_does_not_leave_a_tail(self):
        self.effect.get_sound.return_value = self.playback.sounds[20]
        self.playback.play("effect", 18)
        self.effect.play.assert_called_once_with(self.playback.sounds[18])
        self.effect.fadeout.assert_not_called()
        self.playback.gate_release.start.assert_not_called()

    def test_pause_mute_and_reset_include_the_tail(self):
        self.playback.play("effect", 18)
        self.playback.pause(True)
        for channel in (self.effect, self.music, self.tail):
            channel.pause.assert_called_once()
        self.playback.pause(False)
        for channel in (self.effect, self.music, self.tail):
            channel.unpause.assert_called_once()
        self.playback.set_volume("effect", 0)
        self.effect.set_volume.assert_called_once_with(0)
        self.tail.set_volume.assert_called_with(0)
        self.effect.stop.assert_called_once()
        self.playback.stop("effect")
        self.tail.stop.assert_called_with()
        self.assertEqual(self.effect.stop.call_count, 2)
        self.music.stop.assert_not_called()


if __name__ == "__main__":
    unittest.main()
