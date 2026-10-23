import struct
import unittest
from types import SimpleNamespace
from PIL import Image, ImageChops, ImageOps

from pop2.caverns import CavernRoom
from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import LevelMap, RooftopPhysics, TerrainMotion, stone_gate_blocks


class StoneGateTests(unittest.TestCase):
    def setUp(self):
        self.level = bytearray(0x49ca)
        struct.pack_into('>H', self.level, 0x2186, 3)
        struct.pack_into('>H', self.level, 0x2198, 1)
        for cell in range(30):
            struct.pack_into('>H', self.level, cell * 2, 1)
        struct.pack_into('>H', self.level, 15 * 2, 4)
        self.terrain = LevelMap(self.level)

    def phase(self, value):
        struct.pack_into('>H', self.level, 0x780 + 15 * 4, 0x300 | value)

    def test_quantized_opening_matches_native_body_height_threshold(self):
        for height in (20, 34, 72, 76):
            bounds = (270, 227-height, 290, 226)
            threshold = ((height + 3) // 2) * 4
            for phase in range(256):
                with self.subTest(height=height, phase=phase):
                    self.assertEqual(stone_gate_blocks(0x300 | phase, bounds), phase < threshold)

    def test_actor_and_selected_sequence_exceptions_do_not_use_linked_sequence(self):
        bounds = (270, 155, 290, 226)
        for actor, blocked in ((0, True), (1, False), (2, True)):
            state = SequenceState(2, actor_type=actor, selected_sequence_id=68)
            self.assertFalse(stone_gate_blocks(0, bounds, state))
            state.selected_sequence_id = 2
            self.assertEqual(stone_gate_blocks(0, bounds, state), blocked)
        for actor, threshold in ((7, 240), (8, 216)):
            state = SequenceState(2, actor_type=actor)
            self.assertTrue(stone_gate_blocks(threshold-1, bounds, state))
            self.assertFalse(stone_gate_blocks(threshold, bounds, state))

    def test_closed_gate_stops_both_facings_at_original_type_five_planes(self):
        self.phase(0)
        self.assertEqual(self.terrain.wall_correction(
            0, 280, 300, (285, 155, 310, 226), (265, 155, 290, 226), 1, 1), 284)
        self.assertEqual(self.terrain.wall_correction(
            0, 350, 330, (320, 155, 345, 226), (340, 155, 365, 226), 0, 1), 337)
        self.assertEqual(self.terrain.wall_correction(
            0, 300, 305, (295, 155, 310, 226), (290, 155, 305, 226), 0, 1), 305)

    def test_partial_gate_allows_low_body_but_not_standing_body(self):
        self.phase(104)
        for top, expected in ((155, 284), (193, 300)):
            self.assertEqual(self.terrain.wall_correction(
                0, 280, 300, (285, top, 310, 226), (265, top, 290, 226), 1, 1), expected)
        self.phase(255)
        self.assertEqual(self.terrain.wall_correction(
            0, 280, 300, (285, 155, 310, 226), (265, 155, 290, 226), 1, 1), 300)

    def test_closing_gate_does_not_side_bump_a_body_already_underneath(self):
        self.phase(104)
        for facing, old_x, new_x, previous, current in (
                (1, 310, 315, (290, 155, 310, 226), (290, 155, 320, 226)),
                (0, 310, 305, (315, 155, 340, 226), (300, 155, 340, 226))):
            self.assertEqual(self.terrain.wall_correction(
                0, old_x, new_x, current, previous, facing, 1), new_x)

    def test_gate_contact_uses_pre_collision_masks_but_current_body_height(self):
        self.phase(104)
        record = SimpleNamespace(offset_x=0, aux=0)
        state = SequenceState(47, action=50, target_x=280, facing=1, level_kind=3, actor_type=0)
        motion = TerrainMotion(0, 1)
        contact = (298, 155, 323, 226)
        corrected = (260, 155, 285, 226)
        event = RooftopPhysics(self.terrain).check_gate(
            motion, SequenceRuntime({}, state), corrected, corrected, record, True, False,
            contact_bounds=(contact, contact))
        self.assertEqual((event.kind, state.source_sequence_id), ('gate', 50))
        self.assertEqual(motion.gate_contact_bounds, (0, 1, contact, contact))

    def test_moving_low_body_under_closing_gate_is_crushed_not_pushed_out(self):
        self.phase(64)
        record = SimpleNamespace(offset_x=0, aux=64)
        physics = RooftopPhysics(self.terrain)
        for facing, old_x, x, previous, current in (
                (1, 310, 315, (298, 193, 323, 226), (303, 193, 328, 226)),
                (0, 310, 305, (315, 193, 340, 226), (310, 193, 335, 226))):
            state = SequenceState(117, action=109, target_x=x, current_x=x,
                                  facing=facing, level_kind=3, actor_type=0)
            motion = TerrainMotion(0, 1)
            events = physics.advance(motion, SequenceRuntime({47: (50, -1, 47)}, state),
                                     old_x, current, old_bounds=previous, frame_record=record)
            self.assertEqual([event.kind for event in events], ['death'])
            self.assertEqual((state.source_sequence_id, state.target_x), (118, x))
            self.assertTrue(motion.dead)

    def test_sweep_preserves_native_actor_and_selected_sequence_bypasses(self):
        for actor, selected in ((1, 2), (11, 2), (0, 68)):
            state = SequenceState(2, actor_type=actor, selected_sequence_id=selected)
            self.assertEqual(self.terrain.wall_correction(
                0, 280, 300, (285, 155, 310, 226), (265, 155, 290, 226),
                1, 1, state=state), 300)

    def test_cautious_step_uses_same_gate_planes_and_opening(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        for facing, x, bounds, distance in (
                (1, 280, (270, 155, 290, 226), 4),
                (0, 335, (333, 155, 353, 226), 6)):
            state = SequenceState(2, target_x=x, facing=facing, actor_type=0)
            self.phase(0)
            boundary = self.terrain.step_boundary(0, 1, state, record, bounds)
            self.assertEqual((boundary.clearance, boundary.barrier_type), (distance, 1))
            self.phase(255)
            boundary = self.terrain.step_boundary(0, 1, state, record, bounds)
            self.assertEqual((boundary.clearance, boundary.barrier_type), (42, 2))

    def test_other_environments_keep_their_existing_gate_behavior(self):
        for environment in (1, 4, 5, 6):
            struct.pack_into('>H', self.level, 0x2186, environment)
            self.assertEqual(self.terrain.wall_correction(
                0, 280, 300, (285, 155, 310, 226), (265, 155, 290, 226), 1, 1), 300)

    def test_closed_gate_cannot_be_caught_from_its_right_side(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        for facing in (0, 1):
            column = 6 if not facing else 4
            struct.pack_into('>H', self.level, (10 + column) * 2, 0)
            for phase in (0, 1, 47, 48, 119, 120, 184, 255):
                self.phase(phase)
                state = SequenceState(12, action=106, actor_type=0, level_kind=3,
                                      target_x=column * 51 + 35 + (17 if facing else -17),
                                      facing=facing, current_y=-20, vertical_velocity=30)
                with self.subTest(facing=facing, phase=phase):
                    before = vars(state).copy()
                    caught = self.terrain.catch_ledge(0, 2, state, record)
                    self.assertEqual(caught, bool(facing or phase))
                    if not caught:
                        self.assertEqual(vars(state), before)

    def test_up_approach_keeps_native_closed_gate_exception(self):
        # DoJumpUp 6:1620-162a supplies phase 184 to CanGrab; this is
        # deliberately different from catching a gate during a free fall.
        struct.pack_into('>H', self.level, 16 * 2, 0)
        self.phase(0)
        record = SimpleNamespace(offset_x=0, aux=0)
        state = SequenceState(2, action=15, target_x=6 * 51 + 35, facing=0)
        self.assertIsNotNone(self.terrain.upper_ledge(0, 2, state, record))

    def test_gate_climb_selects_original_failed_climb_below_directional_clearance(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        for environment in (1, 3, 5, 6):
            struct.pack_into('>H', self.level, 0x2186, environment)
            for facing in (0, 1):
                for actor in (0, 1, 2):
                    for phase in range(256):
                        self.phase(phase)
                        state = SequenceState(9, action=91, actor_type=actor,
                                              level_kind=environment, facing=facing,
                                              target_x=5 * 51 + 35)
                        threshold = 120 if environment == 3 and not facing else 48
                        blocked = (actor != 1 and phase < threshold
                                   and (not facing or environment == 3))
                        self.assertEqual(self.terrain.climb_sequence(0, 2, state, record),
                                         73 if blocked else 10)

    def test_gate_foreground_uses_native_actor_column_row_and_hanging_exclusions(self):
        blank = Image.new('RGBA', (510, 365))
        cover = Image.new('L', (20, 30), 255)
        room = CavernRoom(blank, blank, {row: Image.new('L', blank.size) for row in range(-1, 5)},
                          (), (), 0, 3, gate_occlusion={(1, 0): (cover, (102, 20))})
        record = SimpleNamespace(offset_x=0, aux=0)
        for column in range(4):
            for row in (0, 1):
                for mode in range(10):
                    state = SequenceState(2, action=15, target_x=column * 51 + 35,
                                          facing=0, actor_type=0, animation_state=mode)
                    mask = room.actor_mask(row, state=state, record=record,
                                           bounds=(100, 10, 130, 106))
                    expected = column in (0, 1) and row == 0 and mode not in (2, 6)
                    self.assertEqual(mask.getpixel((110, 25)), 255 if expected else 0)
        self.assertIsNone(room.actor_occlusion[0].getbbox())

    def test_body_height_is_clipped_to_the_native_viewport(self):
        self.assertEqual(stone_gate_blocks(64, (270, -20, 290, 25)),
                         stone_gate_blocks(64, (270, 0, 290, 25)))
        self.assertEqual(stone_gate_blocks(64, (270, 340, 290, 400)),
                         stone_gate_blocks(64, (270, 340, 290, 364)))

    def test_standing_turn_reserves_native_eleven_pixel_foot_clearance_at_cavern_gate(self):
        record = SimpleNamespace(offset_x=4, aux=70)
        for facing, x, expected in ((0, 333, 5), (0, 338, 0), (1, 279, -11),
                                    (1, 268, 0)):
            state = SequenceState(2, action=15, target_x=x, facing=facing,
                                  level_kind=3, actor_type=0)
            for phase in (0, 104, 184):
                self.phase(phase)
                self.assertEqual(self.terrain.standing_turn_offset(
                    0, 1, state, record, (x - 4, 148, x + 13, 226)),
                    expected if phase < 168 else 0)
        state.level_kind = 5
        self.assertEqual(self.terrain.standing_turn_offset(
            0, 1, state, record, (280, 148, 300, 226)), 0)

    def test_rise_veto_uses_native_phase_and_directional_anchor_band(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        for facing, minimum, maximum in ((0, 286, 324), (1, 306, 344)):
            for phase in (0, 1, 104, 183, 184, 237, 255):
                self.phase(phase)
                for x in range(275, 351):
                    state = SequenceState(117, action=109, target_x=x, facing=facing, level_kind=3)
                    self.assertEqual(self.terrain.gate_blocks_rise(0, 1, state, record),
                                     0 < phase < 184 and minimum <= x <= maximum)

    def test_contact_crouches_first_then_crushes_when_low_pose_no_longer_fits(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        physics = RooftopPhysics(self.terrain)
        for facing in (0, 1):
            state = SequenceState(2, action=15, target_x=310, facing=facing, level_kind=3, actor_type=0)
            runtime, motion = SequenceRuntime({}, state), TerrainMotion(0, 1)
            self.phase(104)
            standing = (298, 155, 323, 226)
            event = physics.check_gate(motion, runtime, standing, standing, record, True, False)
            self.assertEqual((event.kind, state.sequence_id, state.action, state.target_x),
                             ('gate', 50, 15, 310))
            state.action = 109
            crouched = (298, 193, 323, 226)
            self.assertIsNone(physics.check_gate(motion, runtime, crouched, crouched, record, True, False))
            self.phase(64)
            event = physics.check_gate(motion, runtime, crouched, crouched, record, True, False)
            self.assertEqual((event.kind, event.death_method, state.sequence_id), ('death', 0, 118))
            self.assertTrue(motion.dead)

    def test_god_mode_ejects_instead_of_crushing_without_changing_the_gate(self):
        self.phase(64)
        record = SimpleNamespace(offset_x=0, aux=0)
        state = SequenceState(117, action=109, target_x=310, facing=1, level_kind=3, actor_type=0)
        motion = TerrainMotion(0, 1)
        body = (298, 193, 323, 226)
        before = bytes(self.level)
        event = RooftopPhysics(self.terrain).check_gate(
            motion, SequenceRuntime({}, state), body, body, record, True, False, invulnerable=True)
        self.assertEqual(event.kind, 'gate')
        self.assertFalse(motion.dead)
        self.assertNotEqual(state.source_sequence_id, 118)
        self.assertNotEqual(state.target_x, 310)
        self.assertEqual(bytes(self.level), before)

    def test_gate_contact_requires_previous_overlap_and_ignores_dead_or_descent(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        physics = RooftopPhysics(self.terrain)
        self.phase(64)
        body = (298, 193, 323, 226)
        for alive, selected, previous in ((True, 117, (275, 193, 294, 226)),
                                          (False, 117, body), (True, 68, body), (True, 118, body)):
            state = SequenceState(selected, action=109, target_x=310, facing=1, level_kind=3, actor_type=0)
            motion = TerrainMotion(0, 1)
            self.assertIsNone(physics.check_gate(motion, SequenceRuntime({}, state), body,
                                                previous, record, alive, False))
            self.assertFalse(motion.dead)

    def test_turn_keeps_pre_turn_gate_contact_instead_of_testing_each_arm_pose(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        physics = RooftopPhysics(self.terrain)
        body = (298, 155, 323, 226)
        for facing in (0, 1):
            for previous, standing in (
                    ((270, 155, 294, 226), (270, 155, 294, 226)),
                    ((328, 155, 352, 226), (328, 155, 352, 226)),
                    ((270, 155, 294, 226), body)):
                with self.subTest(facing=facing, standing=standing, previous=previous):
                    self.phase(184)
                    state = SequenceState(2, action=15, target_x=310, facing=facing,
                                          level_kind=3, actor_type=0)
                    motion = TerrainMotion(0, 1)
                    runtime = SequenceRuntime({}, state)
                    self.assertIsNone(physics.check_gate(
                        motion, runtime, standing, previous, record, True, False))
                    cached = motion.gate_contact_bounds
                    self.phase(104)
                    state.select(5)
                    state.animation_state = 7
                    for action in range(45, 53):
                        state.action = action
                        self.assertIsNone(physics.check_gate(
                            motion, runtime, body, body, record, True, False))
                        self.assertEqual(motion.gate_contact_bounds, cached)
                        self.assertEqual(state.source_sequence_id, 5)
                    state.animation_state = 0
                    self.assertEqual(physics.check_gate(
                        motion, runtime, body, body, record, True, False).kind, 'gate')
                    self.assertEqual(state.source_sequence_id, 50)

    def test_gate_closing_on_an_already_overlapping_turn_still_forces_crouch(self):
        record = SimpleNamespace(offset_x=0, aux=0)
        physics = RooftopPhysics(self.terrain)
        body = (298, 155, 323, 226)
        for facing in (0, 1):
            self.phase(184)
            state = SequenceState(2, action=15, target_x=310, facing=facing,
                                  level_kind=3, actor_type=0)
            runtime, motion = SequenceRuntime({}, state), TerrainMotion(0, 1)
            self.assertIsNone(physics.check_gate(motion, runtime, body, body, record, True, False))
            state.select(5)
            state.action, state.animation_state = 49, 7
            self.phase(104)
            event = physics.check_gate(motion, runtime, body, body, record, True, False)
            self.assertEqual((event.kind, state.source_sequence_id), ('gate', 50))

    def test_turn_contact_seed_and_room_or_row_change_do_not_reuse_stale_bounds(self):
        physics = RooftopPhysics(self.terrain)
        record = SimpleNamespace(offset_x=0, aux=0)
        body = (298, 155, 323, 226)
        outside = (270, 155, 294, 226)
        self.phase(104)
        for cached in (None, (1, 1, body, body), (0, 0, body, body)):
            state = SequenceState(5, action=49, animation_state=7, target_x=310,
                                  facing=1, level_kind=3, actor_type=0)
            motion = TerrainMotion(0, 1, gate_contact_bounds=cached)
            self.assertIsNone(physics.check_gate(
                motion, SequenceRuntime({}, state), body, outside, record, True, False))
            self.assertEqual(motion.gate_contact_bounds, (0, 1, outside, outside))

    def test_closed_gate_and_drawn_sword_eject_instead_of_crushing(self):
        physics = RooftopPhysics(self.terrain)
        record = SimpleNamespace(offset_x=0, aux=0)
        body = (298, 193, 323, 226)
        for phase, sword in ((0, False), (64, True)):
            self.phase(phase)
            for facing in (0, 1):
                state = SequenceState(117, action=109, target_x=310, facing=facing, level_kind=3, actor_type=0)
                motion = TerrainMotion(0, 1)
                event = physics.check_gate(motion, SequenceRuntime({}, state), body, body, record, True, sword)
                self.assertEqual(event.kind, 'gate')
                self.assertEqual(state.target_x, 339 if facing else 281)
                self.assertFalse(motion.dead)


@unittest.skipUnless((ASSET_DIR / 'Prince.rsrc').is_file(), 'Imported game resources required')
class ImportedStoneGateTests(unittest.TestCase):
    def test_room_four_repeated_turns_next_to_neighbor_gate_do_not_crouch_or_drift(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.jump_to_room(3, row=2, x=29, facing=0)
        scene.in_animation_tick = True
        for _ in range(3):
            for direction, expected_x, expected_facing in ((1, 41, 1), (-1, 32, 0)):
                scene.horizontal_key(None, direction, True)
                scene.horizontal_key(None, direction, False)
                for _ in range(14):
                    self.assertEqual(scene.sequence_state.source_sequence_id, 5)
                    self.assertNotIn(scene.action, (107, 108, 109))
                    self.assertFalse(scene.terrain_motion.falling or scene.terrain_motion.dead)
                    self.tick()
                self.assertEqual((scene.player_x, scene.sequence_state.facing, scene.action),
                                 (expected_x, expected_facing, 15))
        self.assertEqual(scene.combat.player.life, 3)

    def scene_at_gate(self, phase=104):
        from tests.test_terrain import RooftopSceneTests
        from unittest.mock import Mock

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.peaceful = True
        scene.jump_to_room(16, row=2, x=412, facing=1)
        scene.in_animation_tick = True
        scene.game.caverns.plates.foreground[16, 27] = 0x300 | phase
        scene.render = Mock()
        return scene

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.tick(self, count)

    def test_releasing_run_through_room_10_gate_does_not_pull_prince_back_from_room_14(self):
        scene = self.scene_at_gate()
        for x in (477, 480, 489, 495):
            with self.subTest(x=x):
                plates = scene.game.caverns.plates
                plates.foreground.clear()
                plates.active.clear()
                plates.timers.clear()
                scene.jump_to_room(9, row=1, x=x, facing=1)
                scene.in_animation_tick = True
                plates.foreground[9, 19] = 0x300 | 237
                plates.active[9, 19] = 2
                scene.start_sequence(202)
                scene.sequence_runtime.next_frame()
                scene.player_x, scene.action = scene.sequence_state.target_x, scene.sequence_state.action
                scene.held_directions = [1]
                scene.sample_keyboard()
                scene.run_active, scene.run_direction = True, 1
                scene.horizontal_key(None, 1, False)
                entered = False
                poses = []
                for _ in range(28):
                    self.tick()
                    entered |= scene.room_id == 13
                    if entered:
                        self.assertEqual(scene.room_id, 13)
                    poses.append(scene.action)
                    self.assertFalse(scene.terrain_motion.dead or scene.terrain_motion.falling)
                    self.assertNotEqual(scene.sequence_state.source_sequence_id, 47)
                self.assertTrue(entered)
                self.assertIn(109, poses)
                self.assertEqual((scene.action, scene.sequence_state.facing), (15, 1))
                self.assertEqual(plates.foreground[9, 19] & 255, 0)

    def run_jump_at_room_23_gate(self, phase):
        scene = self.scene_at_gate()
        scene.jump_to_room(22, row=0, x=410, facing=0)
        scene.game.caverns.plates.foreground[22, 1] = 0x200 | phase
        scene.horizontal_key(None, -1, True)
        self.tick(6)
        scene.up_key(None)
        scene.shift_held = True
        return scene

    def test_room_23_closed_gate_rejects_running_jump_grab(self):
        scene = self.run_jump_at_room_23_gate(0)
        for _ in range(60):
            self.tick()
            self.assertFalse(scene.native_ledge or scene.ledge_hanging or scene.ledge_climbing)
        self.assertTrue(scene.terrain_motion.dead)

    def assert_failed_room_23_climb(self, phase):
        scene = self.run_jump_at_room_23_gate(184)
        for _ in range(25):
            self.tick()
            if scene.native_ledge:
                break
        self.assertTrue(scene.native_ledge)
        scene.set_key_state('up', False)
        scene.horizontal_key(None, -1, False)
        self.tick(14)
        self.assertEqual(scene.action, 91)
        scene.game.caverns.plates.foreground[22, 1] = 0x200 | phase
        scene.up_key(None)
        self.tick()
        self.assertEqual(scene.sequence_state.source_sequence_id, 73)
        scene.set_key_state('up', False)
        poses = [scene.action]
        for _ in range(11):
            self.tick()
            poses.append(scene.action)
            self.assertEqual(scene.terrain_motion.row, 1 if not scene.terrain_motion.falling else 2)
            self.assertGreater(scene.player_x, 110)
        self.assertEqual(poses[:11], [135, 136, 137, 137, 138, 138, 138, 138, 137, 136, 135])
        self.tick(10)
        self.assertFalse(scene.native_ledge or scene.ledge_hanging or scene.ledge_climbing)
        self.assertTrue(scene.terrain_motion.falling or scene.terrain_motion.dead)

    def test_room_23_low_gate_uses_complete_failed_climb_without_crossing_it(self):
        self.assert_failed_room_23_climb(119)

    def test_room_23_gate_closing_after_a_valid_grab_still_blocks_climbing(self):
        self.assert_failed_room_23_climb(0)

    def test_room_23_moving_stone_stays_in_front_of_overlapping_head_and_body(self):
        from pop2.scene_prototype import ROOM_ORIGIN_X

        scene = self.scene_at_gate()
        scene.game.caverns.plates.foreground[22, 1] = 0x200 | 156
        for facing in (0, 1):
            with self.subTest(facing=facing):
                scene.jump_to_room(22, row=0, x=120, facing=facing)
                room = scene.room_cache[22]
                cover, position = room.gate_occlusion[1, 0]
                mask = Image.new('L', scene.background.size)
                mask.paste(cover, position)
                self.assertIsNotNone(mask.crop(scene.player_bounds()).getbbox())
                scenery = Image.alpha_composite(scene.background, scene.foreground)
                type(scene).render(scene)
                actual = scene.screenshot_viewport.crop((ROOM_ORIGIN_X, 0, ROOM_ORIGIN_X + 510, 365))
                difference = ImageChops.difference(actual.convert('RGB'), scenery.convert('RGB'))
                self.assertIsNone(ImageChops.multiply(difference, mask.convert('RGB')).getbbox())

    def test_room_23_sufficiently_open_gate_still_allows_full_climb(self):
        scene = self.run_jump_at_room_23_gate(184)
        for _ in range(25):
            self.tick()
            if scene.native_ledge:
                break
        self.assertTrue(scene.native_ledge)
        scene.set_key_state('up', False)
        scene.horizontal_key(None, -1, False)
        self.tick(14)
        scene.up_key(None)
        self.tick()
        scene.set_key_state('up', False)
        self.assertEqual(scene.sequence_state.source_sequence_id, 10)
        poses = []
        for _ in range(19):
            self.tick()
            poses.append(scene.action)
        self.assertIn(141, poses)
        self.assertIn(149, poses)
        self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.action), (22, 0, 15))
        self.assertFalse(scene.native_ledge or scene.ledge_hanging or scene.ledge_climbing)

    def test_low_gate_keeps_crouched_prince_down_until_there_is_clearance(self):
        scene = self.scene_at_gate()
        scene.start_sequence(117)
        scene.sequence_runtime.next_frame()
        scene.action = scene.sequence_state.action
        self.tick(20)
        self.assertEqual(scene.action, 109)
        self.assertEqual(scene.combat.player.life, 3)
        scene.game.caverns.plates.foreground[16, 27] = 0x300 | 184
        self.tick()
        self.assertEqual(scene.sequence_state.source_sequence_id, 49)
        self.tick(12)
        self.assertEqual(scene.action, 15)

    def test_closing_gate_uses_full_native_crush_and_stops_on_the_body(self):
        scene = self.scene_at_gate(144)
        scene.game.caverns.plates.active[16, 27] = 0
        trace = []
        for _ in range(40):
            self.tick()
            trace.append(scene.action)
        self.assertTrue(scene.terrain_motion.dead)
        self.assertEqual(scene.combat.player.life, 0)
        self.assertEqual(scene.sequence_state.source_sequence_id, 118)
        self.assertEqual([pose for pose in trace if pose in (264, 265, 266)][:8],
                         [264] * 6 + [265, 266])
        self.assertNotIn((16, 27), scene.game.caverns.plates.active)
        self.assertEqual(scene.level_map.tile(16, 7, 2).foreground & 255, 48)
        self.assertTrue(scene.death.can_restart)
        self.assertEqual(scene.death.method, 0)

    def test_room_23_final_gate_slam_tracks_flattening_in_both_facings(self):
        scene = self.scene_at_gate()
        for facing, x in ((0, 121), (1, 106)):
            with self.subTest(facing=facing):
                scene.jump_to_room(22, row=0, x=x, facing=facing)
                plates = scene.game.caverns.plates
                plates.foreground[22, 1] = 0x200 | 144
                plates.active[22, 1] = 0
                trace = []
                for _ in range(40):
                    self.tick()
                    trace.append((scene.action, scene.sequence_state.sequence_mode,
                                  plates.foreground[22, 1] & 255))
                signal = next(i for i, (_, mode, _) in enumerate(trace) if mode == 3)
                self.assertEqual(trace[signal][0], 264)
                self.assertGreater(trace[signal][2], 48)
                self.assertEqual(trace[signal + 1], (265, 0, 48))
                self.assertEqual(trace[signal + 2], (266, 0, 48))
                self.assertEqual(trace[-1], (266, 0, 48))
                self.assertNotIn((22, 1), plates.active)
                self.assertEqual(scene.combat.player.life, 0)
                self.assertTrue(scene.death.can_restart)

    def test_crush_stone_overlaps_full_size_native_body_in_both_facings(self):
        from pop2.render_opening import character_sprite_top
        from pop2.scene_prototype import ROOM_ORIGIN_X, ScenePrototype

        scene = self.scene_at_gate()
        for facing, x in ((0, 121), (1, 106)):
            with self.subTest(facing=facing):
                scene.jump_to_room(22, row=0, x=x, facing=facing)
                plates = scene.game.caverns.plates
                plates.foreground[22, 1] = 0x200 | 144
                plates.active[22, 1] = 0
                self.tick(40)
                crush = scene.game.caverns.crush
                actor, height = crush.actor(scene.sequence_state)
                self.assertGreaterEqual(crush.elapsed_ms, 840)
                self.assertEqual((actor.action, height), (266, 17))
                self.assertEqual(plates.foreground[22, 1] & 255, 48)
                self.assertEqual(crush.gate_phase((22, 1)), 28)
                record = scene.frames[actor.action]
                sprite = scene.player_sprite(actor.action).resize(
                    (scene.player_sprite(actor.action).width, height), Image.Resampling.NEAREST)
                anchor = record.offset_x
                if facing:
                    sprite = ImageOps.mirror(sprite)
                    anchor = sprite.width - anchor
                body = Image.new('L', scene.background.size)
                y = character_sprite_top(scene.player_floor_y() + record.offset_y + actor.current_y, height)
                body.paste(sprite.getchannel('A'), (actor.target_x - anchor, y))
                room = scene.room_cache[22]
                cover, position = room.gate_occlusion[1, 0]
                stone = Image.new('L', body.size)
                stone.paste(cover, position)
                overlap = ImageChops.multiply(stone, body)
                self.assertIsNotNone(overlap.getbbox())
                ScenePrototype.render(scene)
                actual = scene.screenshot_viewport.crop((ROOM_ORIGIN_X, 0, ROOM_ORIGIN_X + 510, 365))
                scenery = Image.alpha_composite(scene.background, scene.foreground)
                difference = ImageChops.difference(actual.convert('RGB'), scenery.convert('RGB'))
                self.assertIsNone(ImageChops.multiply(difference, overlap.convert('RGB')).getbbox())

    def test_crush_presentation_freezes_on_pause_and_clears_on_f3_and_restart(self):
        from unittest.mock import patch
        from pop2.scene_prototype import ScenePrototype

        scene = self.scene_at_gate(144)
        scene.game.caverns.plates.active[16, 27] = 0
        for _ in range(35):
            self.tick()
            crush = scene.game.caverns.crush
            if crush.key is not None and 640 <= crush.elapsed_ms < 720:
                break
        self.assertGreaterEqual(crush.elapsed_ms, 640)
        self.assertLess(crush.elapsed_ms, 720)
        before = vars(crush).copy()
        ScenePrototype.render(scene)
        ScenePrototype.render(scene)
        self.assertEqual(vars(crush), before)
        with patch('pop2.window_controls.time.perf_counter', return_value=self.now):
            scene.set_paused(True)
        self.tick(10)
        self.assertEqual(vars(crush), before)
        with patch('pop2.window_controls.time.perf_counter', return_value=self.now):
            scene.set_paused(False)
        self.tick()
        self.assertAlmostEqual(crush.elapsed_ms, before['elapsed_ms'] + 101)
        scene.jump_to_room(16, row=2, x=450, facing=1)
        self.assertIsNone(scene.game.caverns.crush.key)
        self.assertEqual(scene.level_map.tile(16, 7, 2).foreground & 255, 48)
        scene.restart_level()
        self.assertIsNone(scene.game.caverns.crush.key)

    def test_gate_subframe_callback_draws_without_advancing_gameplay(self):
        from unittest.mock import patch

        scene = self.scene_at_gate(144)
        plates = scene.game.caverns.plates
        plates.active[16, 27] = 0
        while scene.game.caverns.crush.key is None:
            self.tick()
        state = vars(scene.sequence_state).copy()
        foreground, active = plates.foreground.copy(), plates.active.copy()
        world_frame, life = scene.combat.world_frame, scene.combat.player.life
        self.now += 0.640
        with patch('pop2.scene_prototype.time.perf_counter', return_value=self.now):
            scene.advance_gate_presentation()
        self.assertEqual(vars(scene.sequence_state), state)
        self.assertEqual((plates.foreground, plates.active), (foreground, active))
        self.assertEqual((scene.combat.world_frame, scene.combat.player.life), (world_frame, life))
        crush = scene.game.caverns.crush
        self.assertEqual(crush.gate_phase((16, 27)), 12)
        self.assertEqual(crush.actor(scene.sequence_state)[0].action, 265)
        scene.cancel_gate_presentation()

    def test_health_bottles_empty_on_the_presented_slam_in_both_facings(self):
        from unittest.mock import patch
        from pop2.gate_crush import SLAM_AT_MS
        from pop2.scene_prototype import ScenePrototype

        scene = self.scene_at_gate()
        for facing, x, life in ((0, 121, 3), (1, 106, 6)):
            with self.subTest(facing=facing, life=life):
                scene.jump_to_room(22, row=0, x=x, facing=facing)
                scene.combat.player.life = scene.combat.player.max_life = life
                plates = scene.game.caverns.plates
                plates.foreground[22, 1] = 0x200 | 144
                plates.active[22, 1] = 0
                for _ in range(40):
                    self.tick()
                    if scene.terrain_motion.dead:
                        break
                crush = scene.game.caverns.crush
                self.assertTrue(scene.terrain_motion.dead)
                self.assertEqual(scene.combat.player.life, 0)
                self.assertEqual(crush.life_before_crush, life)
                self.assertEqual(crush.display_life(scene.sequence_state, 0), life)
                self.assertIsNone(crush.key)
                self.tick()
                self.assertEqual(crush.elapsed_ms, 0)
                started = self.now
                native_life, world_frame = scene.combat.player.life, scene.combat.world_frame
                for elapsed, displayed, gate_phase in ((SLAM_AT_MS - .001, life, 80),
                                                        (SLAM_AT_MS, 0, 12)):
                    self.now = started + elapsed / 1000
                    with patch('pop2.scene_prototype.time.perf_counter', return_value=self.now):
                        scene.advance_gate_presentation()
                    self.assertEqual(crush.display_life(scene.sequence_state, 0), displayed)
                    self.assertEqual(crush.gate_phase((22, 1)), gate_phase)
                    self.assertEqual((scene.combat.player.life, scene.combat.world_frame),
                                     (native_life, world_frame))
                    self.assertFalse(scene.death.prompt_visible)
                    ScenePrototype.render(scene)
                    expected = Image.new('RGBA', scene.native_viewport.size, (0, 0, 0, 255))
                    scene.health_art.draw(expected, scene.combat, show_opponent=False, player_life=displayed)
                    hud = (0, 368, 512, 384)
                    self.assertIsNone(ImageChops.difference(
                        scene.native_viewport.crop(hud).convert('RGB'),
                        expected.crop(hud).convert('RGB')).getbbox())
                scene.jump_to_room(16, row=2, x=450, facing=1)
                self.assertIsNone(scene.game.caverns.crush.life_before_crush)

    def test_crouched_prince_can_crawl_out_without_holding_down(self):
        scene = self.scene_at_gate()
        scene.start_sequence(117)
        scene.sequence_runtime.next_frame()
        scene.action = scene.sequence_state.action
        scene.horizontal_key(None, 1, True)
        positions = []
        for _ in range(30):
            self.tick()
            positions.append((scene.room_id, scene.player_x))
        self.assertTrue(any(room != 16 or x > 450 for room, x in positions))
        self.assertEqual(scene.combat.player.life, 3)
        self.assertFalse(scene.terrain_motion.dead)

    def test_jump_under_partial_gate_is_interrupted_by_contact(self):
        scene = self.scene_at_gate(168)
        scene.start_jump()
        sources = []
        for _ in range(25):
            self.tick()
            sources.append(scene.sequence_state.source_sequence_id)
        self.assertIn(50, sources)
        self.assertFalse(scene.terrain_motion.dead)

    def test_every_native_level_three_gate_uses_the_same_collision_planes(self):
        from pop2.render_opening import load_resource_file

        terrain = LevelMap(load_resource_file('Prince.rsrc')['LEVL'][2002]['data'])
        count = 0
        for room in range(32):
            for cell in range(30):
                row, column = divmod(cell, 10)
                if terrain.tile(room, column, row).kind != 4:
                    continue
                count += 1
                left, right = column*51+40, column*51+72
                bottom = row*120+106
                with self.subTest(room=room, cell=cell):
                    self.assertEqual(terrain.wall_correction(
                        room, left-10, left-8, (left-9, bottom-70, left+1, bottom),
                        (left-11, bottom-70, left-1, bottom), 1, row), left-10)
                    self.assertEqual(terrain.wall_correction(
                        room, right+10, right+8, (right-1, bottom-70, right+9, bottom),
                        (right+1, bottom-70, right+11, bottom), 0, row), right+9)
        self.assertEqual(count, 9)

    def test_closed_room_seventeen_gate_blocks_run_and_shift_walk_from_both_sides(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        for facing, x in ((0, 460), (1, 360)):
            for shift in (False, True):
                with self.subTest(facing=facing, shift=shift):
                    scene.jump_to_room(16, row=2, x=x, facing=facing)
                    scene.set_key_state('shift', shift)
                    scene.horizontal_key(None, 1 if facing else -1, True)
                    for _ in range(30):
                        scene.advance_animation()
                        bounds = scene.player_collision_bounds()
                        self.assertEqual(scene.room_id, 16)
                        self.assertFalse(scene.terrain_motion.falling)
                        if facing:
                            self.assertLess(bounds[2], 397)
                        else:
                            self.assertGreaterEqual(bounds[0], 429)

