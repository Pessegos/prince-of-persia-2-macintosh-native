"""A widening vertical jump must not be pushed through the wall behind it."""
import unittest
import struct
from types import SimpleNamespace

from pop2.paths import ASSET_DIR
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap, RooftopPhysics, TerrainMotion
from tools.audit_temple_routes import Harness, press


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
                # Supply the response pose only; real collision, floor and
                # camera rules decide whether that response stays in place.
                runtime = SimpleNamespace(state=state,
                                          next_frame=lambda: setattr(state, 'action', 50))
                physics = RooftopPhysics(LevelMap(level), {68: record, 50: record})
                motion = TerrainMotion(0, 0)
                bounds = lambda: old if state.action == 50 else expanded
                events = physics.advance(motion, runtime, x, expanded, old_bounds=old,
                                         frame_record=record, bounds_for_state=bounds)
                self.assertEqual(state.target_x, x)
                self.assertEqual(state.source_sequence_id, 47)
                self.assertIn('wall', [event.kind for event in events])
                self.assertFalse(motion.falling)


@unittest.skipUnless(INSTALLED, 'Imported temple resources required')
class VerticalJumpWallTests(unittest.TestCase):
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
