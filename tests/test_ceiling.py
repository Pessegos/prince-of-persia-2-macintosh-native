import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pop2.mac_input import StepBoundary
from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import (LevelMap, RooftopPhysics, TerrainMotion, character_column,
                         floor_y, floor_contact_x)


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

    def test_barrier_bypass_uses_selected_sequence_not_the_pose_or_linked_sequence(self):
        physics = RooftopPhysics(self.terrain)
        for facing in (0, 1):
            for selected in (14, 28, 69, 70, 71, 77, 78, 79, 81):
                for action in (70, 71, 78, 79, 81):
                    state = SequenceState(14, action=action, animation_state=1,
                                          target_x=130, facing=facing, selected_sequence_id=selected)
                    with self.subTest(facing=facing, selected=selected, action=action):
                        with patch.object(self.terrain, 'wall_correction', return_value=130) as check:
                            physics.advance(TerrainMotion(0, 1), SequenceRuntime({}, state),
                                            131, (105, 102, 134, 191), frame_flags=0)
                        self.assertEqual(check.called, selected not in (70, 78))

    def test_landing_edge_reserve_matches_native_threshold_in_both_facings(self):
        for facing in (0, 1):
            self.state.facing = facing
            self.state.actor_type = 0
            direction = 1 if facing else -1
            for distance in (0, 1, 17, 30, 31, 50):
                self.state.target_x = 430 - distance if facing else 380 + distance
                column = character_column(self.state.target_x)
                self.put_tile(0, column, 1, 1)
                for kind in (0, 9, 11, 15, 26, 12, 13, 23, 24, 1, 20, 6, 34):
                    self.put_tile(0, column + direction, 1, kind)
                    expected = ((distance - 32) * direction if distance <= 30
                                and kind in (0, 9, 11, 15, 26, 12, 13, 23, 24) else 0)
                    with self.subTest(facing=facing, distance=distance, kind=kind):
                        self.assertEqual(self.terrain.landing_offset(
                            0, 1, self.state, self.record), expected)

    def test_landing_alignment_preserves_native_actor_and_special_floor_exclusions(self):
        self.state.target_x = 420
        column = character_column(420)
        self.put_tile(0, column + 1, 1, 0)
        for kind, actor in ((1, 0), (23, 0), (24, 0), (1, 7), (1, 8)):
            self.state.actor_type = actor
            self.put_tile(0, column, 1, kind)
            self.assertEqual(self.terrain.landing_offset(0, 1, self.state, self.record),
                             -22 if kind == 1 and actor == 0 else 0)

    def test_player_down_cut_waits_for_440_then_rebases_by_360(self):
        struct.pack_into('>H', self.level, 0x2086, 2)
        for y in (346, 365, 439, 440, 448, 466):
            state = SequenceState(12, target_x=200, current_y=y-floor_y(3), actor_type=0)
            motion = TerrainMotion(0, 3, falling=True)
            self.assertEqual(RooftopPhysics(self.terrain).cut_down(motion, state), y >= 440)
            self.assertEqual(motion.room, int(y >= 440))
            self.assertEqual(floor_y(motion.row) + state.current_y,
                             y - 360 if y >= 440 else y)

    def test_body_overlap_with_ceiling_is_not_a_physical_row_wall(self):
        self.put_tile(0, 1, 0, 20)
        bounds, old = (104, 102, 133, 191), (107, 121, 130, 213)
        self.assertEqual(self.terrain.wall_correction(
            0, 114, 114, bounds, old, 0, physical_row=1), 114)
        self.assertGreater(self.terrain.wall_correction(0, 114, 114, bounds, old, 0), 114)


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

    def test_left_ceiling_jump_is_not_replaced_by_a_false_ground_bump(self):
        from PIL import ImageChops

        scene = self.scene
        scene.jump_to_room(0, row=1, x=127, facing=0)
        floor = scene.native_viewport.convert('RGB').copy()
        scene.in_animation_tick = True
        scene.start_jump()
        self.assertEqual(scene.sequence_state.sequence_id, 14)
        for _ in range(12):
            self.tick()

        self.assertEqual(scene.action, 78)
        self.tick()
        self.assertEqual((scene.action, scene.sequence_state.sequence_id,
                          scene.player_x, scene.terrain_motion.row), (79, 14, 114, 1))
        self.assertFalse(scene.terrain_motion.falling)
        self.tick()
        self.assertEqual(scene.terrain_motion.row, 2)
        self.assertNotEqual(scene.sequence_state.source_sequence_id, 45)
        self.assertTrue(scene.terrain_motion.falling)
        self.assertLess(scene.sequence_state.current_y, 0)
        for _ in range(3):
            # The former ground-bump legs crossed this solid floor strip.
            region = (140, 227, 175, 241)
            self.assertIsNone(ImageChops.difference(
                scene.native_viewport.convert('RGB').crop(region),
                floor.crop(region)).getbbox())
            self.tick()

    def test_entrance_drop_lands_and_finishes_recovery_on_the_lower_platform(self):
        scene = self.scene
        scene.jump_to_room(0, row=1, x=234, facing=1)
        scene.held_directions.append(1)
        scene.start_running(1)
        landed = False
        for _ in range(45):
            self.tick()
            if scene.terrain_motion.falling:
                scene.held_directions.clear()
            elif scene.terrain_motion.row == 2:
                landed = True
            self.assertEqual(scene.room_id, 0)
        self.assertTrue(landed)
        self.assertEqual((scene.action, scene.terrain_motion.row,
                          scene.sequence_state.current_y, scene.player_x), (15, 2, 0, 379))
        self.assertFalse(scene.terrain_motion.falling)
        foot = floor_contact_x(scene.player_x, 1, scene.frames[15])
        self.assertNotEqual(scene.level_map.tile(0, character_column(foot), 2).kind, 0)

    def test_player_drop_cuts_below_entrance_at_the_native_threshold(self):
        scene = self.scene
        scene.jump_to_room(0, row=2, x=410, facing=1)
        scene.sequence_state.select(12)
        scene.sequence_runtime.next_frame()
        scene.terrain_motion.row = 3
        scene.terrain_motion.falling = True
        scene.sequence_state.current_y = 430 - floor_y(3)
        self.tick()
        self.assertEqual(scene.room_id, 0)
        self.assertEqual(floor_y(scene.terrain_motion.row) + scene.sequence_state.current_y, 436)
        self.tick()
        self.assertEqual((scene.room_id, scene.terrain_motion.row), (3, 0))
        self.assertEqual(floor_y(scene.terrain_motion.row) + scene.sequence_state.current_y, 88)
        self.assertTrue(scene.terrain_motion.falling)
