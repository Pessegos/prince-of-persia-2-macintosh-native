import struct
import unittest
from types import SimpleNamespace

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

    def test_body_height_is_clipped_to_the_native_viewport(self):
        self.assertEqual(stone_gate_blocks(64, (270, -20, 290, 25)),
                         stone_gate_blocks(64, (270, 0, 290, 25)))
        self.assertEqual(stone_gate_blocks(64, (270, 340, 290, 400)),
                         stone_gate_blocks(64, (270, 340, 290, 364)))

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
        self.assertEqual(scene.level_map.tile(16, 7, 2).foreground & 255, 52)
        self.assertTrue(scene.death.can_restart)
        self.assertEqual(scene.death.method, 0)

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

