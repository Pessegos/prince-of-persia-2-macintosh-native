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
        self.now = 10.0

    def advance(self):
        self.crush.advance(self.terrain, self.motion, self.state, self.record,
                           self.caverns.plates, now=self.now)

    def sample(self, elapsed_ms):
        self.now = 10 + elapsed_ms / 1000
        self.crush.update(self.now)

    def test_approved_pressure_slam_and_rebound_use_real_time_without_shrinking_sprites(self):
        self.advance()
        original = vars(self.state).copy()
        for elapsed, phase, pose, expected_height in (
                (0, 88, 264, 35), (299, 88, 264, 35), (300, 84, 264, 35),
                (459, 84, 264, 35), (460, 80, 264, 35), (639, 80, 264, 35),
                (640, 12, 265, 22), (719, 12, 265, 22), (720, 32, 265, 22),
                (799, 32, 265, 22), (800, 28, 265, 22), (839, 28, 265, 22),
                (840, 28, 266, 17), (1500, 28, 266, 17)):
            self.sample(elapsed)
            self.assertEqual(self.crush.gate_phase((0, 15)), phase)
            state, height = self.crush.actor(self.state)
            self.assertEqual((state.action, height), (pose, expected_height))
            self.assertEqual(vars(self.state), original)
        self.assertIsNone(self.crush.gate_phase((1, 15)))

    def test_starting_presentation_does_not_modify_native_motion_or_sequence(self):
        self.motion.dead = False
        self.state.sequence_mode = 0
        original = vars(self.state).copy()
        self.advance()
        self.assertEqual(self.crush.key, (0, 15))
        self.assertEqual(self.crush.gate_phase((0, 15)), 88)
        self.assertFalse(self.motion.dead)
        self.assertEqual(vars(self.state), original)

    def test_first_native_kneel_starts_even_when_death_is_already_registered(self):
        self.state.sequence_mode = 0
        self.advance()
        self.assertEqual(self.crush.key, (0, 15))
        self.assertEqual(self.crush.elapsed_ms, 0)
        self.sample(500)
        self.state.sequence_mode = 3
        self.advance()
        self.assertEqual(self.crush.elapsed_ms, 500)
        self.assertEqual(self.crush.gate_phase((0, 15)), 80)

    def test_subframe_deadlines_stop_after_settling_and_rendering_is_read_only(self):
        self.advance()
        self.assertEqual(self.crush.next_delay_ms(), 300)
        self.sample(640)
        before = vars(self.crush).copy()
        self.crush.gate_phase((0, 15))
        self.crush.actor(self.state)
        self.assertEqual(vars(self.crush), before)
        self.assertEqual(self.crush.next_delay_ms(), 80)
        self.sample(840)
        self.assertIsNone(self.crush.next_delay_ms())

    def test_drawing_phase_never_changes_native_foreground_or_active_gates(self):
        program = {'pressure_plates': {'rooms': {'0': [
            {'room': 0, 'cell': 15, 'kind': 4, 'foreground': 0x300 | 82}]}}}
        self.advance()
        self.sample(840)
        self.assertEqual(cavern_pressure_signature(program, 0, self.caverns), (7,))
        self.assertEqual(self.terrain.tile(0, 5, 1).foreground, 0x300 | 82)
        self.assertEqual(self.caverns.plates.foreground, {})
        self.assertEqual(self.caverns.plates.active, {})

    def test_ordinary_poses_and_hanging_hands_do_not_start_a_crush(self):
        for sequence, action, mode in ((25, 91, 3), (2, 15, 3),
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
            self.now = 10
            self.advance()
            self.sample(840)
            actor, height = self.crush.actor(self.state)
            self.assertEqual(actor.target_x, self.state.target_x + (6 if facing else -6))
            self.assertEqual((actor.current_y, actor.action, height), (-1, 266, 17))

    def test_opening_the_gate_releases_the_stone_but_keeps_the_original_death_pose(self):
        self.advance()
        self.sample(840)
        self.caverns.plates.active[0, 15] = 2
        self.advance()
        self.assertIsNone(self.crush.gate_phase((0, 15)))
        self.assertEqual(self.crush.actor(self.state)[1], 17)
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
