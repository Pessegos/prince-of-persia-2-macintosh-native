import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pop2.mac_input import StepBoundary
from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap, character_column


class VerticalJumpTests(unittest.TestCase):
    def setUp(self):
        self.level = bytearray(0x49ca)
        struct.pack_into('>H', self.level, 0x2186, 3)
        struct.pack_into('>H', self.level, 0x2198, 1)
        struct.pack_into('>H', self.level, 0x2084, 2)
        self.terrain = LevelMap(self.level)
        self.state = SequenceState(2, action=15, target_x=405, facing=1, actor_type=0)
        self.record = SimpleNamespace(offset_x=0, aux=0x40)

    def choose(self, room=0, row=0, boundary=StepBoundary(42, 2)):
        with patch.object(self.terrain, 'step_boundary', return_value=boundary):
            return self.terrain.vertical_jump(room, row, self.state, self.record, (0, 0, 0, 0))

    def put_tile(self, room, column, row, kind):
        struct.pack_into('>H', self.level, room * 60 + (row * 10 + column) * 2, kind)

    def test_solid_ceiling_uses_the_original_low_jump_in_both_facings(self):
        for facing in (0, 1):
            self.state.facing = facing
            for kind in (1, 2, 4, 10, 11, 19, 20):
                self.put_tile(1, 7, 2, kind)
                with self.subTest(facing=facing, kind=kind):
                    self.assertEqual(self.choose(), (14, 0))

    def test_native_space_kinds_keep_the_normal_vertical_jump(self):
        for kind in (0, 9, 27, 47, 49):
            self.put_tile(1, 7, 2, kind)
            self.assertEqual(self.choose(), (28, 0))

    def test_ceiling_probe_uses_the_eight_pixel_forward_foot_position(self):
        self.state.target_x = 376
        self.put_tile(1, 6, 2, 0)
        self.put_tile(1, 7, 2, 20)
        self.assertEqual(character_column(self.state.target_x), 6)
        self.assertEqual(self.choose(), (14, 0))
        self.state.facing = 0
        self.put_tile(1, 6, 2, 20)
        self.put_tile(1, 7, 2, 0)
        self.state.target_x = 382
        self.assertEqual(character_column(self.state.target_x), 7)
        self.assertEqual(self.choose(), (14, 0))

    def test_close_barrier_correction_precedes_the_ceiling_probe(self):
        for facing, expected in ((1, -7), (0, 7)):
            self.state.facing = facing
            self.assertEqual(self.choose(boundary=StepBoundary(3, 1)), (28, expected))
            self.assertEqual(self.choose(boundary=StepBoundary(3, 2)), (28, 0))
            self.assertEqual(self.choose(boundary=StepBoundary(6, 1)), (28, 0))

    def test_rooftop_boat_exception_is_retained(self):
        struct.pack_into('>H', self.level, 0x2186, 5)
        self.put_tile(14, 7, 0, 20)
        self.assertEqual(self.choose(room=14, row=1), (28, 0))
        self.put_tile(13, 7, 0, 20)
        self.assertEqual(self.choose(room=13, row=1), (14, 0))

    def test_temple_exceptions_use_the_cached_column_before_the_forward_probe(self):
        struct.pack_into('>H', self.level, 0x2186, 6)
        for room in (6, 7):
            for column in range(10):
                self.put_tile(room, column, 1, 20)
        for room, column, expected in ((6, 2, 14), (6, 3, 28), (6, 6, 14),
                                      (7, 2, 28), (7, 6, 14)):
            self.state.target_x = (column + 5) * 51 - 182
            self.assertEqual(character_column(self.state.target_x), column)
            self.assertEqual(character_column(self.state.target_x + 8), column + 1)
            self.assertEqual(self.choose(room=room, row=2), (expected, 0))


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class OriginalCeilingTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.setUp(self)
        self.scene.load_level(3)
        self.scene.peaceful = True

    def tick(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.tick(self)

    def test_entrance_ceiling_uses_short_jump_and_returns_to_its_floor(self):
        scene = self.scene
        scene.jump_to_room(0, row=0, x=347, facing=1)
        scene.in_animation_tick = True
        scene.start_jump()
        self.assertEqual(scene.sequence_state.sequence_id, 14)
        frames = []
        for _ in range(30):
            self.tick()
            frames.append((scene.action, scene.sequence_state.current_y))
            if scene.sequence_state.sequence_id == 2:
                break
        self.assertIn((79, 0), frames)
        self.assertEqual(sum(action == 79 for action, _ in frames), 1)
        self.assertNotIn((79, -11), frames)
        self.assertEqual((scene.sequence_state.sequence_id, scene.terrain_motion.row,
                          scene.sequence_state.current_y, scene.player_x), (2, 0, 0, 363))

    def test_blocked_jump_repeats_under_another_ceiling_without_room_specific_logic(self):
        scene = self.scene
        for room, row, x in ((0, 0, 347), (3, 2, 338), (4, 1, 185)):
            scene.jump_to_room(room, row=row, x=x, facing=1)
            self.assertIsNone(scene.level_map.upper_ledge(room, row, scene.sequence_state, scene.frames[15]))
            scene.in_animation_tick = True
            scene.start_jump()
            self.assertEqual(scene.sequence_state.sequence_id, 14)
