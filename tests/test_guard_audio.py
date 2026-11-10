"""Guard landing and kill music in the real hidden scene, with timed audio."""

import unittest
from dataclasses import replace
from unittest.mock import Mock

from pop2.audio import AudioEngine
from pop2.combat import select_sequence
from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceRuntime
from pop2.terrain import TerrainMotion
from tests.test_audio import TimedPlayback
from tools.audit_temple_routes import Harness


INSTALLED = all((ASSET_DIR / name).is_file() for name in (
    *(f'temple_level{level}.json' for level in range(10, 14)),
    'Birdhead.rsrc', 'audio/manifest.json'))


@unittest.skipUnless(INSTALLED, 'Imported temple and audio resources required')
class GuardAudioTests(unittest.TestCase):
    def harness(self, level=12, room=8, row=0, x=100):
        # Parameterized cases must close the preceding hidden Tcl interpreter.
        self.doCleanups()
        harness = Harness(level, peaceful=False, draw=True)
        self.addCleanup(harness.close)
        scene = harness.scene
        scene.jump_to_room(room, row=row, x=x, facing=1)
        audio = AudioEngine(playback=object(), mix_effects=True)
        backend = TimedPlayback(audio.cues)
        audio.playback = Mock(wraps=backend)
        audio.configure_level(scene.game.level.data)
        scene.audio = audio
        self.addCleanup(audio.close)
        return harness, backend

    @staticmethod
    def tick(harness, backend, count=1):
        for _ in range(count):
            backend.advance(.101)
            harness.tick()

    @staticmethod
    def kill_songs(scene):
        return [call for call in scene.audio.playback.play.call_args_list
                if call.args[:2] == ('music', 189)]

    def falling_room9_guard(self):
        harness, backend = self.harness()
        scene = harness.scene
        guard = scene.combat.active_guards()[0]
        guard.sword_drawn = True
        select_sequence(guard, 90)
        guard.runtime.next_frame()
        guard.state.target_x = guard.state.current_x = 195
        guard.state.facing = 0
        # Supply the successful nonfatal strike; AI, fall, plate and audio run.
        scene.combat._hurt('guard', guard, scene.combat.player)
        for _ in range(20):
            self.tick(harness, backend)
            if not guard.alive:
                break
        self.assertFalse(guard.alive)
        self.assertEqual((guard.room, guard.row), (8, 2))
        self.assertFalse(guard.terrain_motion.falling)
        return harness, backend, guard

    def test_room9_guard_scream_is_stopped_before_impact_frame_audio_is_drained(self):
        harness, _backend, _guard = self.falling_room9_guard()
        audio = harness.scene.audio
        self.assertFalse(audio.sound_playing(30), 'the fall scream started over the impact')
        audio.playback.stop_effect.assert_any_call(30)
        self.assertIn(7, [call.args[0] for call in audio.playback.play_effect.call_args_list])

    def test_room9_guard_death_plays_one_victory_song_after_the_native_count(self):
        harness, backend, _guard = self.falling_room9_guard()
        for _ in range(7):
            self.tick(harness, backend)
            self.assertFalse(self.kill_songs(harness.scene))
        self.tick(harness, backend)
        self.assertEqual(len(self.kill_songs(harness.scene)), 1)
        self.tick(harness, backend, 20)
        self.assertEqual(len(self.kill_songs(harness.scene)), 1)

    def test_already_playing_scream_stops_on_surviving_and_fatal_landings(self):
        for velocity, fatal in ((20, False), (63, True)):
            with self.subTest(velocity=velocity):
                harness, backend = self.harness()
                scene = harness.scene
                guard = scene.combat.active_guards()[0]
                guard.row = 2
                guard.terrain_motion = TerrainMotion(8, 2, falling=True, scream_played=True)
                select_sequence(guard, 82)
                for _ in range(5):
                    guard.runtime.next_frame()  # Actual mode-4 free-fall loop, pose 106.
                guard.state.target_x = guard.state.current_x = 260
                guard.state.current_y, guard.state.vertical_velocity = -1, velocity
                scene.audio.add_sound(30)
                scene.audio.flush()
                self.assertTrue(scene.audio.sound_playing(30))
                self.tick(harness, backend)
                self.assertEqual(not guard.alive, fatal)
                self.assertFalse(scene.audio.sound_playing(30))

    def test_inflight_guard_scream_keeps_playing_until_a_real_impact(self):
        harness, backend = self.harness()
        scene = harness.scene
        guard = scene.combat.active_guards()[0]
        guard.row = 2
        guard.terrain_motion = TerrainMotion(8, 2, falling=True)
        select_sequence(guard, 82)
        for _ in range(5):
            guard.runtime.next_frame()
        guard.state.target_x = guard.state.current_x = 260
        guard.state.current_y, guard.state.vertical_velocity = -200, 59
        self.tick(harness, backend)
        self.assertTrue(guard.terrain_motion.falling)
        self.assertTrue(scene.audio.sound_playing(30))

    def test_sword_victory_music_is_wired_for_all_four_temple_levels(self):
        # Each real room has one ordinary birdhead and no reinforcement point.
        for level, room, row, x in ((10, 12, 1, 302), (11, 25, 1, 353),
                                     (12, 5, 2, 251), (13, 3, 1, 353)):
            with self.subTest(level=level):
                harness, backend = self.harness(level, room, row, x - 80)
                scene = harness.scene
                guard = scene.combat.active_guards()[0]
                guard.life = 1
                guard.state.facing = 0
                scene.combat._hurt('guard', guard, scene.combat.player)
                self.tick(harness, backend, 10)
                self.assertEqual(len(self.kill_songs(scene)), 1)

    def test_trap_death_endpoints_do_not_require_a_sword_hit_for_music(self):
        for sequence in (22, 188, 189, 190):  # impact/debris, both spike deaths, scythe
            with self.subTest(sequence=sequence):
                harness, backend = self.harness()
                scene = harness.scene
                guard = scene.combat.active_guards()[0]
                self.tick(harness, backend)  # A living NPC control arms the pending cue.
                guard.life = 0
                guard.terrain_motion.dead = True
                select_sequence(guard, sequence)
                guard.runtime.next_frame()
                self.tick(harness, backend, 9)
                self.assertEqual(len(self.kill_songs(scene)), 1)

    def test_pending_native_alive_opponent_suppresses_and_consumes_the_song(self):
        harness, backend = self.harness()
        scene = harness.scene
        guard = scene.combat.active_guards()[0]
        self.tick(harness, backend)
        guard.life = 0
        other = replace(guard, runtime=SequenceRuntime(scene.combat.sequences,
                        replace(guard.state)), native_alive=True, alert_mode=3, bank_slot=1)
        scene.combat.guards.append(other)
        # Do not register the second NPC yet: HP zero is still native ALIVE=-1.
        for _ in range(8):
            scene.combat.choose_guard_action(guard)
        self.assertFalse(scene.combat.songs)
        self.assertFalse(guard.death_song_pending)
        scene.combat.guards.remove(other)
        for _ in range(10):
            scene.combat.choose_guard_action(guard)
        self.assertFalse(scene.combat.songs)

    def test_reinforcements_on_the_deaths_row_suppress_the_song_until_exhausted(self):
        for remaining, player_x, expected in ((2, 300, False), (0, 300, True), (2, 485, True)):
            with self.subTest(remaining=remaining, player_x=player_x):
                harness, backend = self.harness(10, 28, 2, 300)
                scene = harness.scene
                self.tick(harness, backend, 25)
                guard = scene.combat.active_guards()[0]
                point = scene.combat.generation_points[0]
                point.remaining = remaining
                scene.sequence_state.target_x = player_x
                guard.life = 0
                for _ in range(8):
                    scene.combat.choose_guard_action(guard)
                self.assertEqual(189 in scene.combat.songs, expected)
                self.assertFalse(guard.death_song_pending)

    def test_rooftop_guards_keep_the_native_no_victory_song_rule(self):
        harness, backend = self.harness(1, 1, 1, 400)
        scene = harness.scene
        guard = scene.combat.active_guards()[0]
        scene.combat._hurt('guard', guard, scene.combat.player)
        self.tick(harness, backend, 10)
        self.assertFalse(guard.alive)
        self.assertFalse(self.kill_songs(scene))

    def test_reentering_a_corpse_room_does_not_replay_its_victory_song(self):
        harness, backend, guard = self.falling_room9_guard()
        self.tick(harness, backend, 10)
        self.assertEqual(len(self.kill_songs(harness.scene)), 1)
        harness.scene.jump_to_room(5, row=2, x=100, facing=1, reset_guards=False)
        harness.scene.jump_to_room(8, row=0, x=100, facing=1, reset_guards=False)
        self.tick(harness, backend, 15)
        self.assertFalse(guard.death_song_pending)
        self.assertEqual(len(self.kill_songs(harness.scene)), 1)
