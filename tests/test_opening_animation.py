import unittest

from pop2.animation_data import sequence_words
from pop2.opening_animation import GLASS_POSITIONS, OpeningEscape
from pop2.render_opening import OPENING_FLOOR_Y, load_resource_file
from pop2.sequence_runtime import SequenceRuntime, SequenceState


class OpeningEscapeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prince = load_resource_file("Prince.rsrc")
        cls.sequences = {
            key: sequence_words(value["data"])
            for key, value in prince["SEQS"].items()
        }

    def opening(self):
        state = SequenceState(2, actor_type=0, level_kind=5)
        runtime = SequenceRuntime(self.sequences, state)
        return OpeningEscape(runtime, start_tile=2)

    def test_native_pose_and_position_timeline(self):
        # Original SEQS/physics; checked against first screen.mp4 at 12 fps.
        expected = (
            (43, 324, 127), (103, 355, 148), (104, 355, 160),
            (105, 359, 176), (106, 373, 197), (106, 381, 224),
            (107, 391, 226), (108, 397, 226), (109, 404, 226),
            (110, 407, 226), (111, 409, 226), (112, 411, 226),
            (113, 416, 226), (114, 416, 226), (115, 419, 226),
            (116, 411, 226), (117, 411, 226), (118, 411, 226),
            (119, 411, 226), (15, 411, 226),
        )
        opening = self.opening()
        for tick, pose in enumerate(expected):
            with self.subTest(tick=tick):
                state = opening.state
                self.assertEqual(
                    (state.action, state.target_x, OPENING_FLOOR_Y + state.current_y),
                    pose,
                )
                self.assertEqual(state.current_x, state.target_x)
                self.assertEqual(state.facing, 1)
            opening.advance()
        self.assertFalse(opening.active)
        self.assertEqual(opening.state.sequence_id, 2)

    def test_fall_velocity_and_landing_reset(self):
        opening = self.opening()
        for _ in range(4):
            opening.advance()
        self.assertEqual(opening.state.horizontal_velocity, 8)
        self.assertEqual(opening.state.vertical_velocity, 21)
        opening.advance()
        self.assertEqual(opening.state.vertical_velocity, 27)
        opening.advance()
        self.assertEqual(opening.state.vertical_velocity, 0)
        self.assertEqual(opening.state.horizontal_velocity, 0)
        self.assertEqual(opening.state.sequence_id, 17)
        self.assertEqual(opening.state.current_y, 0)

    def test_curtain_settles_after_original_fourteen_stage_table(self):
        opening = self.opening()
        frames = []
        for _ in range(15):
            frames.append(opening.curtain_frame)
            opening.advance()
        self.assertEqual(frames, [4, 3, 2, 1, 5, 6, 7, 6, 5, 0, 1, 2, 3, 8, 8])

    def test_glass_uses_source_positions_and_expires(self):
        self.assertEqual(GLASS_POSITIONS[0], (263, 107))
        self.assertEqual(GLASS_POSITIONS[-1], (445, 231))
        opening = self.opening()
        for index in range(1, 12):
            self.assertEqual(opening.glass_frame, index)
            opening.advance()
        self.assertIsNone(opening.glass_frame)
        while opening.active:
            opening.advance()
        self.assertIsNone(opening.glass_frame)

    def test_completed_opening_does_not_advance_idle(self):
        opening = self.opening()
        while opening.active:
            opening.advance()
        snapshot = vars(opening.state).copy()
        tick = opening.tick
        for _ in range(100):
            opening.advance()
        self.assertEqual(vars(opening.state), snapshot)
        self.assertEqual(opening.tick, tick)

    def test_restart_reuses_same_runtime_without_old_velocity_or_facing(self):
        opening = self.opening()
        for _ in range(5):
            opening.advance()
        opening.state.facing = 0
        opening.state.sequence_mode = 11
        opening = OpeningEscape(opening.runtime, 2)
        reference = self.opening()
        self.assertEqual(vars(opening.state), vars(reference.state))

    def test_velocity_opcode_assigns_without_moving_actor(self):
        state = SequenceState(1, horizontal_velocity=23, vertical_velocity=62)
        runtime = SequenceRuntime({1: (-8, 6, 15, 106, -23)}, state)
        runtime.next_frame()
        self.assertEqual((state.horizontal_velocity, state.vertical_velocity), (6, 15))
        self.assertEqual((state.target_x, state.current_y), (0, 0))
        self.assertEqual(state.sequence_events, [(-8, (6, 15))])

    def test_velocity_assignment_can_replace_terminal_fall_speed(self):
        state = SequenceState(1, horizontal_velocity=8, vertical_velocity=63)
        runtime = SequenceRuntime({1: (-8, 6, 15, 106, -23)}, state)
        runtime.next_frame()
        self.assertEqual((state.horizontal_velocity, state.vertical_velocity), (6, 15))


if __name__ == "__main__":
    unittest.main()
