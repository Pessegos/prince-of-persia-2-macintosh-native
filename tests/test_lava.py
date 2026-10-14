from types import SimpleNamespace
import struct
import unittest
from unittest.mock import patch

from pop2.animation_data import FrameRecord
from pop2.lava import Lava, LavaPool
from pop2.paths import ASSET_DIR
from pop2.terrain import LevelMap, TerrainMotion
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.rebirth import DeathState
from tools.extract_lava import lava_tables


def synthetic_tables():
    return {'limits': [4, 5, 4], 'piece_offsets': [0, 0],
            'characters': [[(150, 45, -18)] * 5, [(148, 45, -18)] * 22,
                           [(168, 18, -15)] * 5],
            'splashes': [(146, 43, -16)] * 3,
            'events': [(0, 0, -11, 58, 0), (4, 1, -15, 64, 1)],
            'bubbles': [[0, 1, -2, 2, -1], [3, 4, 5, -1]]}


class LavaRuleTests(unittest.TestCase):
    def setUp(self):
        self.pool = LavaPool(synthetic_tables())

    def test_cell_seed_and_initial_bubbles(self):
        for cell, phase, active in ((27, 0, 0), (22, 5, 1), (23, 10, 0)):
            pool = LavaPool(synthetic_tables())
            pool.initialize(cell)
            self.assertEqual(pool.flags, phase)
            self.assertEqual(sum(b[0] for b in pool.bubbles), active)

    def test_normal_cycle_uses_previous_phase_and_retains_bubbles_at_reset(self):
        self.assertEqual(self.pool.advance(), ())
        self.assertEqual(self.pool.bubbles[0], [1, 0, 0, -11, 58, 0])
        self.pool.advance()
        self.assertEqual(self.pool.bubbles[0][1], 1)
        self.pool.advance()
        self.assertEqual(self.pool.bubbles[0][1], 3)
        self.assertEqual(self.pool.bubbles[0][5], 1)
        self.pool.advance()
        self.assertEqual(self.pool.bubbles[0][0], 0)
        self.pool.flags = 22
        self.pool.bubbles[2] = [1, 1, 0, -11, 58, 1]
        self.pool.advance()
        self.assertEqual(self.pool.flags, 0)
        self.assertEqual(self.pool.bubbles[2], [1, 1, 0, -11, 58, 1])

    def test_death_selection_and_inclusive_random_branch(self):
        for mode, roll, expected in ((3, 0, 0x8000), (4, 0, 0x8000),
                                     (0, 1, 0xa000), (0, 2, 0xa000),
                                     (1, 3, 0xa000), (0, 0, 0xb000)):
            self.assertEqual(self.pool.begin_death(mode, 1, random_value=roll), (116, 70))
            self.assertEqual(self.pool.flags, expected)
        with patch('pop2.lava.random.randint', return_value=0) as draw:
            self.pool.begin_death(0, 1)
            draw.assert_called_once_with(0, 3)
        self.pool.begin_death(0, 0, random_value=1)
        self.assertEqual(self.pool.flags, 0xa800)
        self.assertEqual(self.pool.character_sequence, 1)
        self.assertEqual(self.pool.begin_death(0, 1, actor_type=2), (115, 69))
        self.assertEqual(self.pool.character_sequence, 2)

    def test_death_duration_and_sound_use_old_phase(self):
        for mode, roll, last in ((3, 0, 4), (0, 1, 5), (0, 0, 21)):
            pool = LavaPool(synthetic_tables())
            pool.begin_death(mode, 1, random_value=roll)
            sounds = []
            for tick in range(1, last + 2):
                sounds.extend((tick, cue) for cue in pool.advance())
                self.assertEqual(pool.character_sequence >= 0, tick <= last)
            self.assertEqual(sounds, [(5 if mode == 3 else 6, 68)])

    def test_death_reset_at_three_preserves_flags_but_does_not_advance_bubbles(self):
        self.pool.begin_death(0, 0, random_value=0)
        self.pool.flags |= 3
        self.pool.bubbles[0] = [1, 1, 0, -11, 58, 1]
        self.pool.advance()
        self.assertEqual(self.pool.flags, 0xb804)
        self.assertEqual(self.pool.bubbles[0][1], 1)

    def test_native_cover_is_between_rear_and_front_bubbles(self):
        self.pool.bubbles[0] = [1, 0, 0, -11, 58, 0]
        self.pool.bubbles[1] = [1, 1, 0, -11, 42, 1]
        self.assertEqual(self.pool.drawings(), [(3617, 42, -11, False),
                                              (3615, 0, 0, False),
                                              (3616, 58, -11, False)])
        self.pool.begin_death(3, 0)
        self.assertEqual(self.pool.drawings(), [(3615, 0, 0, False),
                                              (3650, 45, -18, True)])

    def test_room_changes_reinitialize_but_rendering_same_room_does_not(self):
        lava = Lava(synthetic_tables())
        records = [{'room': 5, 'cell': 27}] * 2
        lava.enter_room(5, records)
        self.assertEqual(len(lava.pools), 1)
        lava.advance()
        lava.enter_room(5, records)
        self.assertEqual(lava.pools[5, 27].flags, 1)
        lava.enter_room(12, records)
        self.assertEqual(lava.pools[5, 27].flags, 0)
        lava.enter_room(0, [])
        self.assertEqual(lava.pools, {})

    def contact(self, foot, y=346, flags=0x40, offset=0, facing=1, dead=False):
        data = bytearray(0x4200)
        import struct
        struct.pack_into('>H', data, 27 * 2, 23)
        struct.pack_into('>H', data, 28 * 2, 24)
        terrain = LevelMap(bytes(data))
        lava = Lava(synthetic_tables())
        lava.enter_room(0, [{'room': 0, 'cell': 27}])
        frame = FrameRecord(15, 0, 0, offset, 0, flags)
        state = SimpleNamespace(target_x=foot - offset * (1 if facing else -1),
                                facing=facing, current_y=y - 346)
        return lava.contact(terrain, TerrainMotion(0, 2, dead=dead), state, frame)

    def test_native_contact_limits_and_surface_y(self):
        for foot in range(380, 470):
            with self.subTest(foot=foot):
                self.assertEqual(self.contact(foot) is not None, 400 <= foot <= 444)
        self.assertIsNone(self.contact(420, y=316))
        self.assertIsNotNone(self.contact(420, y=317))
        self.assertIsNone(self.contact(420, flags=0))
        self.assertIsNone(self.contact(420, dead=True))

    def test_column_is_derived_from_supporting_foot_not_anchor(self):
        for facing in (0, 1):
            for offset in (-30, 0, 30):
                self.assertIsNotNone(self.contact(420, offset=offset, facing=facing))
                self.assertIsNone(self.contact(399, offset=offset, facing=facing))

    def test_sequence_death_music_selector_does_not_replace_lava_cause(self):
        state = SequenceState(116, actor_type=0)
        runtime = SequenceRuntime({116: (-7, 1, -11, 1, 15, 185, -23)}, state)
        self.assertEqual(runtime.next_frame().action, 15)
        self.assertEqual(state.death_song_method, 1)
        death = DeathState(counter=6, method=5, music_method=state.death_song_method)
        from unittest.mock import Mock
        audio = Mock()
        audio.death_ready.return_value = True
        death.advance(185, 0.1, audio)
        audio.death_song.assert_called_once_with(1)
        self.assertEqual(death.method, 5)
        other = SequenceState(115, actor_type=2)
        SequenceRuntime({115: (-11, 1, 185)}, other).next_frame()
        self.assertIsNone(other.death_song_method)


class LavaExtractionTests(unittest.TestCase):
    def setUp(self):
        self.data = bytearray(0x6000)
        self.pieces = bytearray(0x220)
        struct.pack_into('>3h', self.data, len(self.data) - 0x2e54, 4, 5, 4)
        for index, count in enumerate((5, 22, 5)):
            displacement = -0x4000 + index * 200
            struct.pack_into('>i', self.data, len(self.data) - 0x2f4a + index * 4, displacement)
            for frame in range(count):
                struct.pack_into('>3h', self.data, len(self.data) + displacement + frame * 6,
                                 150 + frame, 40 + index, -18)
        for index in range(6):
            displacement = -0x3800 + index * 100
            struct.pack_into('>i', self.data, len(self.data) - 0x2cfa + index * 4, displacement)
            struct.pack_into('>5h', self.data, len(self.data) + displacement, 0, 1, -2, 2, -1)
        struct.pack_into('>5h', self.data, len(self.data) - 0x2e4e, 0, 2, -11, 58, 1)
        struct.pack_into('>2h', self.pieces, 0x1d6, -3, -4)

    def extract(self):
        with (patch('tools.extract_lava.expand_a5_data', return_value=bytes(self.data)),
              patch('tools.extract_lava.parse_resource_fork',
                    side_effect=[{}, {'PIEC': {3500: {'data': bytes(self.pieces)}}}])):
            return lava_tables(b'program', b'artwork')

    def test_signed_offsets_markers_and_full_rare_continuation_are_imported(self):
        tables = self.extract()
        self.assertEqual(tables['schema'], 1)
        self.assertEqual([len(seq) for seq in tables['characters']], [5, 22, 5])
        self.assertEqual(tables['characters'][1][21], [171, 41, -18])
        self.assertEqual(tables['piece_offsets'], [-3, -4])
        self.assertEqual(tables['events'][0], [0, 2, -11, 58, 1])
        self.assertEqual(tables['bubbles'][4], [0, 1, -2, 2, -1])

    def test_unsupported_death_limits_are_rejected(self):
        struct.pack_into('>h', self.data, len(self.data) - 0x2e54, 20)
        with self.assertRaisesRegex(ValueError, 'death tables'):
            self.extract()

    def test_unterminated_bubble_table_is_rejected(self):
        start = len(self.data) - 0x3800
        self.data[start:start + 80] = bytes(80)
        with self.assertRaisesRegex(ValueError, 'Unterminated'):
            self.extract()


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class ImportedLavaTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.setUp(self)
        self.scene.load_level(3)
        self.scene.peaceful = True

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.tick(self, count)

    def test_all_native_pools_and_visible_border_copies_are_recovered(self):
        tables = self.scene.level_renderer.cavern_program['lava']
        pools = {(item['room'], item['cell']) for records in tables['rooms'].values() for item in records}
        self.assertEqual(pools, {(5, 27), (9, 23), (14, 22), (25, 23), (30, 23)})
        self.assertEqual(tables['limits'], [4, 5, 4])
        self.assertEqual([len(t) for t in tables['characters']], [5, 22, 5])

    def test_pool_boils_without_player_input_and_does_not_change_static_art(self):
        scene = self.scene
        scene.jump_to_room(5, row=2, x=350, facing=1)
        scene.render()
        initial = scene.native_viewport.crop((375, 325, 470, 365)).tobytes()
        base = scene.background.tobytes()
        self.tick(8)
        self.assertNotEqual(scene.native_viewport.crop((375, 325, 470, 365)).tobytes(), initial)
        self.assertEqual(scene.background.tobytes(), base)
        self.assertTrue(scene.combat.player.alive)

    def test_walk_into_lava_dies_with_original_sequence_and_retry(self):
        scene = self.scene
        scene.jump_to_room(5, row=2, x=420, facing=1)
        with patch('pop2.lava.random.randint', return_value=1):
            self.tick()
        self.assertEqual(scene.death.method, 5)
        self.assertEqual(scene.death.music_method, 1)
        self.assertEqual(scene.sequence_state.selected_sequence_id, 116)
        self.assertEqual(scene.game.caverns.lava.pools[5, 27].flags, 0xa000)
        self.assertTrue(scene.terrain_motion.dead)
        self.assertFalse(scene.combat.player.alive)
        self.assertIsNone(scene.player_sprite())
        self.tick(40)
        self.assertTrue(scene.death.can_restart)
        scene.restart_after_death()
        self.assertTrue(scene.combat.player.alive)
        self.assertNotEqual(scene.death.method, 5)
        self.assertEqual(scene.game.caverns.lava.pools, {})

    def test_airborne_contact_uses_other_sequence_and_jump_clears_surface(self):
        scene = self.scene
        scene.jump_to_room(5, row=2, x=420, facing=1)
        state = scene.sequence_state
        state.animation_state, state.current_y = 3, -31
        scene.advance_level_events()
        self.assertTrue(scene.combat.player.alive)
        state.current_y = -29
        scene.advance_level_events()
        self.assertFalse(scene.combat.player.alive)
        self.assertEqual(scene.game.caverns.lava.pools[5, 27].flags, 0x8000)


if __name__ == '__main__':
    unittest.main()
