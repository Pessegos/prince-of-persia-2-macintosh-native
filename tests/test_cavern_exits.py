import json
import struct
from types import SimpleNamespace
import unittest

from pop2.cavern_state import CavernState
from pop2.caverns import cavern_exit_clip, pressure_drawing_commands
from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap
from pop2.environments import environment_for


class CavernExitTests(unittest.TestCase):
    def setUp(self):
        self.level = bytearray(0x49ca)
        struct.pack_into('>H', self.level, 0x2186, 3)
        struct.pack_into('>H', self.level, 0x218a, 3)
        struct.pack_into('>H', self.level, 0x2198, 1)
        self.terrain = LevelMap(self.level)
        self.terrain.caverns = CavernState()
        self.plates = self.terrain.caverns.plates
        self.set_tile(0, 14, 34, 1)
        self.set_tile(1, 15, 17, 0x300)
        struct.pack_into('>5h', self.level, 0x1680 + 10, 2, 15, 0, -3, -3)

    def set_tile(self, room, cell, kind, foreground):
        struct.pack_into('>H', self.level, room * 60 + cell * 2, kind)
        struct.pack_into('>H', self.level, 0x780 + room * 120 + cell * 4, foreground)

    def push(self):
        return self.plates.push(self.terrain, self.terrain.tile(0, 4, 1))

    def test_exit_opens_one_pixel_per_update_then_stays_open(self):
        self.assertEqual(self.push(), (27,))
        self.assertEqual(self.plates.songs, [297])
        for phase in range(1, 80):
            self.assertEqual(self.plates.advance(self.terrain), (18 if phase == 79 else 17,))
            self.assertEqual(self.terrain.tile(1, 5, 1).foreground, 0x300 | phase)
        self.assertNotIn((1, 15), self.plates.active)
        for _ in range(100):
            self.assertEqual(self.plates.advance(self.terrain), ())
        self.assertEqual(self.terrain.tile(1, 5, 1).foreground, 0x34f)

    def test_held_and_rearmed_button_never_reverses_or_restarts_the_exit(self):
        self.push()
        self.plates.songs.clear()
        for _ in range(100):
            self.plates.advance(self.terrain)
            self.push()
        self.assertEqual(self.plates.songs, [])
        for _ in range(5):
            self.plates.advance(self.terrain)
        self.assertEqual(self.push(), (27,))
        self.assertEqual(self.plates.songs, [])
        self.assertNotIn((1, 15), self.plates.active)

    def test_up_uses_open_exit_in_current_behind_or_forward_cell(self):
        self.set_tile(1, 15, 17, 79)
        record = SimpleNamespace(offset_x=0, aux=0)
        for facing in (0, 1):
            for x in (230, 280, 330):
                state = SequenceState(2, actor_type=0, target_x=x, facing=facing)
                self.assertEqual(self.terrain.exit_door(1, 1, state, record).column, 5)
                for phase in (0, 1, 78):
                    self.set_tile(1, 15, 17, phase)
                    self.assertIsNone(self.terrain.exit_door(1, 1, state, record))
                self.set_tile(1, 15, 17, 79)
        state.actor_type = 2
        self.assertIsNone(self.terrain.exit_door(1, 1, state, record))
        self.set_tile(0, 15, 17, 79)
        state.actor_type = 0
        self.assertIsNone(self.terrain.exit_door(0, 1, state, record))

    def test_exit_shape_moves_in_pixels_not_stone_gate_quarter_phases(self):
        command = ['back', 3566, 280, 335, 16, 2, [243, 280, 335, 329], 4, 5, 2]
        records = [{'kind': 17, 'foreground': 0, 'commands': [('back', 3566, 4, 5, 2)]}]
        resources = {'SHAP': {3566: {'data': struct.pack('>4H', 0, 0, 49, 92)}}}
        for phase in (0, 1, 40, 78, 79):
            expected = [*command[:3], 335 - phase, *command[4:6],
                        [max(241, 243 - phase), 280, 335 - phase, 329], *command[7:]]
            self.assertEqual(pressure_drawing_commands([command], records, (phase,), resources), [expected])
        self.assertEqual(command[3], 335)

    def test_exit_actor_clip_begins_only_after_native_stair_height(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        state = SequenceState(70, action=224, target_x=280, facing=0,
                              actor_type=0, current_y=-24)
        self.assertIsNone(cavern_exit_clip(self.terrain, 1, 1, state, record))
        state.current_y = -25
        self.assertEqual(cavern_exit_clip(self.terrain, 1, 1, state, record), (137, 326))
        state.target_x = 230
        self.set_tile(1, 14, 16, 0)
        self.assertEqual(cavern_exit_clip(self.terrain, 1, 1, state, record), (137, 326))
        state.action = 216
        self.assertIsNone(cavern_exit_clip(self.terrain, 1, 1, state, record))


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class ImportedCavernExitTests(unittest.TestCase):
    def test_button_song_pause_room_persistence_and_entry_completion(self):
        from tests.test_terrain import RooftopSceneTests
        from pop2.audio import AudioEngine
        from tests.test_audio import TimedPlayback

        RooftopSceneTests.setUp(self)
        scene = self.scene
        manifest = json.loads((ASSET_DIR / 'audio/manifest.json').read_text(encoding='ascii'))
        cues = {int(k): v for k, v in manifest['cues'].items()}
        scene.audio = AudioEngine(playback=TimedPlayback({**cues, **manifest.get('scene_cues', {})}))
        scene.load_level(3)
        scene.jump_to_room(29, row=0, x=455, facing=1)
        record = scene.frames[scene.sequence_state.action]
        scene.sequence_state.target_x += (record.aux & 63) - record.offset_x
        scene.advance_level_events()
        plates = scene.game.caverns.plates
        self.assertEqual(plates.active[(29, 25)], 1)
        self.assertEqual(plates.songs, [297])
        scene.advance_audio()
        self.assertEqual(plates.songs, [])
        self.assertEqual(scene.audio.current_music, 297)
        self.assertTrue(scene.audio.song_playing(297))
        self.assertNotEqual(scene.audio.current_effect, 297)
        scene.set_paused(True)
        RooftopSceneTests.tick(self, 10)
        self.assertEqual(scene.level_map.tile(29, 5, 2).foreground & 255, 0)
        scene.set_paused(False)
        for _ in range(79):
            environment_for(scene).frame_start()
        scene.jump_to_room(28, row=1, x=250, facing=1)
        self.assertEqual(scene.level_map.tile(29, 5, 2).foreground & 255, 79)
        scene.jump_to_room(29, row=2, x=280, facing=1)
        scene.start_jump()
        self.assertEqual(scene.sequence_state.source_sequence_id, 70)
        self.assertEqual(scene.sequence_state.facing, 0)
        self.assertTrue(scene._combat_controls_locked())
        RooftopSceneTests.tick(self, 35)
        # The native completion waits for end song 32 before entering NIS 10.
        self.assertTrue(scene.level_complete)
        self.assertEqual(scene.game.exit.song, 32)
        self.assertIsNone(scene.intro)
        self.assertEqual(scene.game.level.number, 3)
        scene.restart_level()
        self.assertFalse(scene.level_complete)
        self.assertEqual(scene.level_map.tile(29, 5, 2).foreground & 255, 0)

    def test_import_contains_both_exits_but_keeps_entrance_closure_separate(self):
        data = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
        exits = {(r['room'], r['cell']) for room in data['pressure_plates']['rooms'].values()
                 for r in room if r['kind'] == 17}
        self.assertEqual(exits, {(12, 16), (29, 25)})


if __name__ == '__main__':
    unittest.main()
