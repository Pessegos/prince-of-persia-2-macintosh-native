import struct
import unittest

import numpy as np

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


@unittest.skipUnless((ASSET_DIR / 'throne.json').is_file(), 'Original throne scene has not been imported')
class ThroneVisualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pop2.intro import IntroAssets

        cls.assets = IntroAssets(program_name='throne.json')

    def test_resident_kid_inks_are_relocated_but_zero_stays_transparent(self):
        from pop2.intro import indexed_shape
        from pop2.render_opening import load_resource_file

        original = np.asarray(indexed_shape(load_resource_file('Kid.rsrc')['SHAP'][25081]['data']))
        actual = np.asarray(self.assets.shapes[725081])
        expected = np.where(original == 0, 0, original + 15)
        np.testing.assert_array_equal(actual, expected)
        self.assertTrue(set(actual.ravel()) <= {0, *range(16, 32)})

    def test_both_facings_get_full_first_dissolve_and_unchanged_mother_durations(self):
        for variant in self.assets.program['variants'].values():
            self.assertEqual(variant[0]['args'], [[0, 0, 365, 512]])
            self.assertEqual([op['args'][0] for op in variant if op['op'] == 'dissolve'],
                             [240, 180, 20, 20, 20, 180])

    def test_ground_sword_is_intact_without_an_extra_floor_patch(self):
        from pop2.caverns import cavern_assets

        program, _resources, _palette, _shapes = cavern_assets(8)
        commands = [command for command in program['rooms']['8'] if command[8:10] == [5, 2]]
        self.assertTrue(any(command[1] == 1011 and command[7] == 0 for command in commands))
        self.assertFalse(any(command[1] in (1046, 3518) for command in commands))

    def test_real_scene_retains_its_hud_to_the_last_vision_frame(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(8)
        scene.peaceful = True
        scene.jump_to_room(8, 2, 267, 1)
        scene.combat.player.life = 2
        scene.render()
        expected = scene.native_viewport.crop((0, 365, 512, 384)).convert('RGBA')
        self.assertGreater(np.asarray(expected)[..., :3].max(), 0)
        self.assertTrue(scene.start_vision(lambda: None))
        self.assertEqual(scene.intro.status.tobytes(), expected.tobytes())
        scene.intro.advance(1000)
        self.assertTrue(scene.intro.done)
        self.assertEqual(scene.intro.frame().crop((0, 365, 512, 384)).tobytes(), expected.tobytes())


if __name__ == '__main__':
    unittest.main()
