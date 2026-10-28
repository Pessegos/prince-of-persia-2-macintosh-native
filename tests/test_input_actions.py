"""Input consumption differences verified with original ordinary action bodies."""

import unittest

from tools.reference_input_bank import InputBank
from tools.reference_input_actions import forward_jump, run, running_jump, step, turn


class InputActionTests(unittest.TestCase):
    def test_standing_jump_consumes_its_chord_without_erasing_other_directions(self):
        bank = InputBank(-1, -1, -1, -1, -2)
        result = forward_jump(bank)
        self.assertEqual(result.bank, InputBank(1, -1, 1, -1, -2))
        self.assertEqual(result.sequence, 3)
        self.assertEqual(run(bank).bank, InputBank(left=1, modifier=-2))

    def test_step_consumes_forward_and_modifier_even_when_no_animation_starts(self):
        bank = InputBank(-1, -1, -1, -1, -2)
        result = step(bank, distance=5)
        self.assertIsNone(result.sequence)
        self.assertEqual(result.x, 401)
        self.assertEqual(result.bank, InputBank(1, -1, -1, -1, 1))

    def test_warning_is_distinct_from_a_solid_barrier(self):
        bank = InputBank(left=-1, modifier=-1)
        self.assertEqual((step(bank, distance=4).sequence, step(bank, distance=4).warning), (44, 0))
        self.assertEqual(step(bank, distance=4, warning=0).sequence, 42)
        self.assertEqual(step(bank, distance=4, barrier=1).sequence, 42)
        for kind in (12, 13):
            self.assertEqual(step(bank, distance=4, barrier=1, tile_kind=kind).sequence, 44)

    def test_blocked_run_clears_other_requests_even_if_forward_was_already_consumed(self):
        bank = InputBank(1, -1, -1, -1, -2)
        result = run(bank, barrier=1, distance=4)
        self.assertIsNone(result.sequence)
        self.assertEqual(result.bank, InputBank(left=1, modifier=-2))
        # A fresh Forward instead attempts a step, which consumes the modifier.
        result = run(InputBank(-1, -1, -1, -1, -2), barrier=1, distance=5)
        self.assertEqual(result.bank, InputBank(left=1, modifier=1))

    def test_turn_consumes_backward_and_clears_other_directions(self):
        bank = InputBank(-1, -1, -1, -1, -1)
        for facing in (False, True):
            result = turn(bank, ahead_kind=4, wall=True, wall_distance=6, facing_right=facing)
            self.assertEqual(result.bank, InputBank(right=1, modifier=-1))
            self.assertEqual(result.sequence, 5)
            self.assertEqual(result.x, 395 if facing else 405)

    def test_failed_running_jump_preserves_pending_inputs_but_success_clears_and_consumes_up(self):
        bank = InputBank(-1, -1, -1, -1, -2)
        for pose, cells in ((6, (True, True)), (7, (False, False))):
            result = running_jump(bank, pose=pose, cells=cells)
            self.assertFalse(result.accepted)
            self.assertEqual(result.bank, bank)
            self.assertIsNone(result.sequence)
        result = running_jump(bank, pose=7)
        self.assertTrue(result.accepted)
        self.assertEqual(result.bank, InputBank(up=1, modifier=-2))

    def test_running_jump_alignment_has_asymmetric_rejection_and_fallback(self):
        bank = InputBank(up=-1)
        # delta = gap -48: -32 rejects, -31 through14 align,15 falls back.
        for gap, accepted, adjustment in ((16, False, 0), (17, True, -18),
                                           (62, True, 27), (63, True, 0)):
            for facing in (False, True):
                result = running_jump(bank, cells=(False, False), gap_distance=gap,
                                      facing_right=facing)
                self.assertEqual(result.accepted, accepted)
                self.assertEqual(result.x, 400 + adjustment * (1 if facing else -1))

    def test_alternate_sequence_requires_its_own_pose_gate(self):
        for pose in (6, 7, 14, 192, 196):
            result = running_jump(InputBank(up=-1), sequence=100, pose=pose,
                                  cells=(False, False))
            self.assertEqual(result.accepted, pose in (192, 196))


if __name__ == '__main__':
    unittest.main()
