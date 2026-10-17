import struct
import unittest
from types import SimpleNamespace

from pop2.cavern_state import CavernState
from pop2.caverns import cavern_pressure_signature
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap, TerrainMotion


class GateCrushTests(unittest.TestCase):
    def setUp(self):
        level = bytearray(0x49ca)
        struct.pack_into('>H', level, 0x2186, 3)
        struct.pack_into('>H', level, 15 * 2, 4)
        struct.pack_into('>H', level, 0x780 + 15 * 4, 0x300 | 82)
        self.terrain = LevelMap(level)
        self.caverns = self.terrain.caverns = CavernState()
        self.crush = self.caverns.crush
        self.state = SequenceState(118, action=264, animation_state=1,
                                   target_x=5 * 51 + 35, facing=0, sequence_mode=3)
        self.motion = TerrainMotion(0, 1, dead=True)
        self.record = SimpleNamespace(offset_x=0, aux=0)

    def advance(self):
        self.crush.advance(self.terrain, self.motion, self.state, self.record,
                           self.caverns.plates)

    def test_pressure_profile_has_intermediate_poses_and_one_short_rebound(self):
        phases, poses = [], []
        original = vars(self.state).copy()
        for _ in range(10):
            self.advance()
            phases.append(self.crush.gate_phase((0, 15)))
            state, height = self.crush.actor(self.state)
            poses.append((state.action, height))
            self.assertEqual(vars(self.state), original)
        self.assertEqual(phases, [80, 68, 52, 40, 28, 32, 28, 28, 28, 28])
        self.assertEqual(poses[:7], [(264, 35), (264, 29), (265, 22), (265, 18),
                                     (266, 12), (266, 14), (266, 12)])
        self.assertIsNone(self.crush.gate_phase((1, 15)))

    def test_drawing_phase_never_changes_native_foreground_or_active_gates(self):
        program = {'pressure_plates': {'rooms': {'0': [
            {'room': 0, 'cell': 15, 'kind': 4, 'foreground': 0x300 | 82}]}}}
        for _ in range(7):
            self.advance()
        self.assertEqual(cavern_pressure_signature(program, 0, self.caverns), (7,))
        self.assertEqual(self.terrain.tile(0, 5, 1).foreground, 0x300 | 82)
        self.assertEqual(self.caverns.plates.foreground, {})
        self.assertEqual(self.caverns.plates.active, {})

    def test_ordinary_poses_and_hanging_hands_do_not_start_a_crush(self):
        for sequence, action, mode in ((25, 91, 3), (2, 15, 3), (118, 264, 0),
                                        (118, 265, 0), (118, 266, 0)):
            self.state.select(sequence)
            self.state.action, self.state.sequence_mode = action, mode
            self.advance()
            self.assertIsNone(self.crush.key)
            self.assertEqual(self.crush.actor(self.state), (self.state, None))

    def test_actor_offsets_follow_facing_without_moving_the_physics_state(self):
        for facing in (0, 1):
            self.crush.reset()
            self.state.facing = facing
            for _ in range(7):
                self.advance()
            actor, height = self.crush.actor(self.state)
            self.assertEqual(actor.target_x, self.state.target_x + (6 if facing else -6))
            self.assertEqual((actor.current_y, actor.action, height), (-1, 266, 12))

    def test_opening_the_gate_releases_the_stone_but_keeps_the_flattened_body(self):
        for _ in range(7):
            self.advance()
        self.caverns.plates.active[0, 15] = 2
        self.advance()
        self.assertIsNone(self.crush.gate_phase((0, 15)))
        self.assertEqual(self.crush.actor(self.state)[1], 12)
        self.caverns.plates.active.clear()
        self.advance()
        self.assertIsNone(self.crush.gate_phase((0, 15)))

    def test_replacement_actor_or_room_clears_the_effect(self):
        self.advance()
        self.motion.room = 1
        self.advance()
        self.assertIsNone(self.crush.key)
        self.motion.room = 0
        self.advance()
        self.state.select(2)
        self.advance()
        self.assertIsNone(self.crush.key)
        self.assertEqual(self.crush.actor(self.state)[1], None)


if __name__ == '__main__':
    unittest.main()
