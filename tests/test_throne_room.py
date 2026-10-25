import struct
import unittest

from pop2.sequence_runtime import SequenceState
from pop2.paths import ASSET_DIR
from pop2.terrain import LevelMap
from tests import test_audio


class ThroneGateTests(unittest.TestCase):
    def setUp(self):
        self.level = bytearray(0x49ca)
        struct.pack_into('>H', self.level, 0x2186, 4)
        struct.pack_into('>H', self.level, 0x218a, 8)
        struct.pack_into('>H', self.level, 0x2198, 1)
        struct.pack_into('>H', self.level, 8 * 60 + 15 * 2, 4)
        self.terrain = LevelMap(self.level)

    def test_type_eight_planes_block_both_directions_regardless_of_opening_phase(self):
        # GetBarrCode 4:532e; DATA c9e0/c9f2[8] = 16/24.
        for phase in (0, 104, 184, 237, 255):
            struct.pack_into('>H', self.level, 0x780 + 8 * 120 + 15 * 4, phase)
            with self.subTest(phase=phase):
                self.assertEqual(self.terrain.wall_correction(
                    8, 280, 300, (285, 155, 310, 226), (265, 155, 290, 226), 1, 1), 282)
                self.assertEqual(self.terrain.wall_correction(
                    8, 350, 310, (295, 155, 320, 226), (335, 155, 360, 226), 0, 1), 318)

    def test_cautious_step_sees_the_same_solid_plane(self):
        record = type('Frame', (), {'offset_x': 0, 'aux': 0})()
        state = SequenceState(2, target_x=250, facing=1, actor_type=0)
        boundary = self.terrain.step_boundary(8, 1, state, record, (255, 155, 280, 226), cautious=True)
        self.assertEqual((boundary.clearance, boundary.tile_kind), (12, 4))

    def test_only_the_level_eight_throne_room_gets_the_special_barrier(self):
        tile = self.terrain.tile(8, 5, 1)
        for number, environment, room, blocked in (
                (8, 4, 8, True), (8, 4, 7, False), (7, 4, 8, False), (8, 3, 8, False)):
            struct.pack_into('>H', self.level, 0x218a, number)
            struct.pack_into('>H', self.level, 0x2186, environment)
            with self.subTest(number=number, environment=environment, room=room):
                self.assertEqual(self.terrain.throne_gate(room, tile), blocked)


class ThroneMusicTests(unittest.TestCase):
    def setUp(self):
        test_audio.CueTests.setUp(self)
        self.audio.cues[180] = {'mode': 1, 'priority': 0, 'file': 'throne.wav'}

    def test_throne_repeats_when_idle_without_interrupting_foreground_music(self):
        audio = self.audio
        audio.ambient(8, 2, 5, special=180, special_when_idle=True)
        self.assertEqual(audio.pending_song, 180)
        audio.flush()
        self.busy['music'] = True
        self.playback.play.reset_mock()
        audio.ambient(8, 2, 5, special=180, special_when_idle=True)
        self.assertIsNone(audio.pending_song)
        self.playback.play.assert_not_called()
        self.busy['music'] = False
        audio.ambient(8, 2, 5, special=180, special_when_idle=True)
        self.assertEqual(audio.pending_song, 180)
        audio.flush()
        audio.add_song(38)
        audio.flush()
        self.busy['music'] = True
        audio.ambient(8, 2, 5, special=180, special_when_idle=True)
        self.assertIsNone(audio.pending_song)

    def test_combat_only_specials_do_not_replace_peaceful_music(self):
        self.audio.ambient(8, 2, 5, special=180)
        self.assertNotEqual(self.audio.pending_song, 180)


@unittest.skipUnless((ASSET_DIR / 'ruins_level8.json').is_file(), 'Original ruins have not been imported')
class ThroneSceneMusicTests(unittest.TestCase):
    def test_idle_throne_theme_repeats_then_normal_ambience_returns_after_vision(self):
        from pop2.audio import AudioEngine
        from tests.test_audio import TimedPlayback
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(8)
        scene.peaceful = True
        scene.jump_to_room(8, 2, 180, 1)
        scene.audio = AudioEngine(playback=object())
        scene.audio.playback = TimedPlayback(scene.audio.cues)
        scene.audio.configure_level(scene.game.level.data)
        scene.advance_audio()
        self.assertEqual(scene.audio.current_music, 180)
        scene.audio.playback.advance(10000)
        scene.advance_audio()
        self.assertEqual(scene.audio.current_music, 180)
        self.assertTrue(scene.audio.music_busy)
        scene.game.sword_type = 1
        scene.game.caverns.throne_done = True
        scene.audio.playback.advance(10000)
        scene.advance_audio()
        self.assertNotEqual(scene.audio.current_music, 180)
        self.assertTrue(139 <= scene.audio.current_music <= 174)


if __name__ == '__main__':
    unittest.main()
