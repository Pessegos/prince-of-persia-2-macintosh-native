"""A widening vertical jump must not be pushed through the wall behind it."""
import unittest
import struct
from types import SimpleNamespace

from pop2.paths import ASSET_DIR
from pop2.opponent_generation import WALL_TILES, character_column
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap, RooftopPhysics, TerrainMotion, floor_contact_x
from tools.audit_temple_routes import Harness, press, release_all


INSTALLED = all((ASSET_DIR / name).is_file() for name in
                ('temple_level10.json', 'temple_level12.json', 'Temple.rsrc'))
# Native room numbers. Standing positions are supplied; all jump/controller,
# collision, response animation, floor and room-cut work runs in the real scene.
PINCHES = ((10, 9, 0, 368), (10, 9, 2, 368), (12, 3, 0, 470),
           (12, 16, 1, 470), (12, 17, 0, 368), (12, 17, 1, 368))


class OpposedBarrierTests(unittest.TestCase):
    def test_pose_expansion_plays_a_bump_without_crossing_the_opposite_wall(self):
        for facing, wall, x, old, expanded in (
                (0, 4, 215, (211, 28, 228, 106), (198, 28, 231, 106)),
                (1, 2, 188, (174, 28, 191, 106), (171, 28, 224, 106))):
            with self.subTest(facing=facing):
                level = bytearray(0x49ca)
                struct.pack_into('>H', level, 0x2186, 2)
                for col in range(10):
                    struct.pack_into('>H', level, col * 2, 1)
                struct.pack_into('>H', level, 3 * 2, 4)
                struct.pack_into('>H', level, wall * 2, 20)
                state = SequenceState(14, action=68, animation_state=1, actor_type=0,
                                      level_kind=2, target_x=x, current_x=x, facing=facing)
                record = SimpleNamespace(offset_x=0, aux=0x40)
                # Supply SEQS47's first pose and its 16-pixel backward move;
                # real collision, floor and camera rules must contain both.
                def response():
                    state.action = 50
                    state.target_x += 16 if not facing else -16
                    state.current_x = state.target_x

                runtime = SimpleNamespace(state=state, next_frame=response)
                physics = RooftopPhysics(LevelMap(level), {68: record, 50: record})
                motion = TerrainMotion(0, 0)
                def bounds():
                    if state.action != 50:
                        return expanded
                    shift = state.target_x - x
                    return old[0] + shift, old[1], old[2] + shift, old[3]
                events = physics.advance(motion, runtime, x, expanded, old_bounds=old,
                                         frame_record=record, bounds_for_state=bounds)
                self.assertEqual(state.target_x, x)
                self.assertEqual(state.source_sequence_id, 47)
                self.assertIn('wall', [event.kind for event in events])
                self.assertFalse(motion.falling)


@unittest.skipUnless(INSTALLED, 'Imported temple resources required')
class VerticalJumpWallTests(unittest.TestCase):
    def assert_outside_wall(self, scene):
        state, motion = scene.sequence_state, scene.terrain_motion
        contact = floor_contact_x(state.target_x, state.facing, scene.frames[state.action])
        tile = scene.level_map.tile(motion.room, character_column(contact), motion.row)
        self.assertNotIn(tile.kind, WALL_TILES, (state.target_x, state.action, tile))

    def replay_step_turn_jump_and_left(self, harness):
        scene = harness.scene
        room, row = scene.room_id, scene.terrain_motion.row
        press(harness, 'shift', True)
        press(harness, 'R', True)
        harness.tick(3)
        release_all(harness)
        harness.tick(12)
        press(harness, 'L', True)
        harness.tick()
        press(harness, 'L', False)
        harness.tick(10)
        before_jump = scene.sequence_state.target_x
        press(harness, 'up', True)
        for tick in range(23):
            if tick == 3:
                press(harness, 'up', False)
            harness.tick()
            self.assertEqual(scene.room_id, room)
            self.assertEqual(scene.terrain_motion.row, row)
            self.assert_outside_wall(scene)
        after_jump = scene.sequence_state.target_x
        press(harness, 'L', True)
        for _ in range(4):
            harness.tick()
            self.assertEqual(scene.room_id, room)
            self.assertEqual(scene.terrain_motion.row, row)
            self.assert_outside_wall(scene)
        self.assertLess(scene.sequence_state.target_x, after_jump)
        self.assertTrue(scene.combat.player.alive)
        return before_jump

    def test_actual_room3_climb_step_turn_jump_then_left_cannot_teleport(self):
        harness = Harness(12, peaceful=True)
        try:
            scene = harness.scene
            # Supplied supported start below the closed upper gate. The
            # entire ascent, short step, turn, jump and movement use keys.
            scene.jump_to_room(2, row=1, x=434, facing=1, redraw=False)
            press(harness, 'up', True)
            press(harness, 'shift', True)
            harness.tick(30)
            release_all(harness)
            harness.tick(5)
            self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.player_x), (2, 0, 444))
            self.assertFalse(scene.native_ledge)
            self.assertFalse(scene.ledge_climbing)
            self.assertEqual(self.replay_step_turn_jump_and_left(harness), 453)
        finally:
            harness.close()

    def test_step_turn_jump_and_follow_up_movement_at_all_six_pinches(self):
        for level, room, row, wall_x in PINCHES:
            with self.subTest(level=level, room=room, row=row):
                harness = Harness(level, peaceful=True)
                try:
                    harness.scene.jump_to_room(room - 1, row=row, x=wall_x - 26,
                                               facing=1, redraw=False)
                    self.replay_step_turn_jump_and_left(harness)
                finally:
                    harness.close()

    def test_closed_gate_cannot_push_the_jump_through_the_rear_wall(self):
        for level, room, row, x in PINCHES:
            with self.subTest(level=level, room=room, row=row):
                harness = Harness(level, peaceful=True)
                try:
                    scene = harness.scene
                    scene.jump_to_room(room - 1, row=row, x=x, facing=0, redraw=False)
                    press(harness, 'up', True)
                    poses = []
                    for tick in range(30):
                        if tick == 8:
                            press(harness, 'up', False)
                        harness.tick()
                        poses.append(scene.action)
                        self.assertEqual(scene.room_id, room - 1)
                        self.assertEqual(scene.terrain_motion.row, row)
                        self.assertLessEqual(abs(scene.sequence_state.target_x - x), 12)
                    self.assertIn(50, poses, 'the rejected jump must still play its wall response')
                    self.assertTrue(scene.combat.player.alive)
                    self.assertFalse(scene.terrain_motion.falling)
                    self.assertEqual(scene.action, 15)
                finally:
                    harness.close()

    def test_the_same_room3_jump_with_an_open_gate_remains_a_jump(self):
        harness = Harness(12, peaceful=True)
        try:
            scene = harness.scene
            scene.jump_to_room(2, row=0, x=470, facing=0, redraw=False)
            scene.game.caverns.plates.foreground[2, 8] = 184
            press(harness, 'up', True)
            harness.tick(3)
            press(harness, 'up', False)
            poses = []
            for _ in range(20):
                harness.tick()
                poses.append(scene.action)
                self.assertEqual(scene.room_id, 2)
            self.assertNotIn(50, poses)
            self.assertIn(71, poses)
            self.assertTrue(scene.combat.player.alive)
        finally:
            harness.close()
