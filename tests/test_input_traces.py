"""Composed sampled controller traces, with action boundaries checked natively."""

import unittest

from tools.reference_input_bank import InputBank
from tools.reference_input_traces import composed_route, sampled_tick


class InputTraceTests(unittest.TestCase):
    def test_run_and_standing_jump_have_different_effects_on_pending_down(self):
        running = composed_route(InputBank(left=-1, down=-1), 50)
        jumping = composed_route(InputBank(left=-1, up=-1, down=-1), 50)
        self.assertEqual((running.sequence, running.bank), (1, InputBank(left=1)))
        self.assertEqual((jumping.sequence, jumping.bank), (3, InputBank(1, 0, 1, -1)))

    def test_released_up_retries_a_rejected_running_jump_then_is_consumed(self):
        for facing in (False, True):
            direction = 1 if facing else -1
            bank = InputBank(right=1) if facing else InputBank(left=1)
            first = sampled_tick(bank, (direction, -1, 0), 6, facing_right=facing)
            self.assertIsNone(first.sequence)
            self.assertEqual(first.bank.up, -1)
            second = sampled_tick(first.bank, (direction, 0, 0), 7, facing_right=facing,
                                  cells=(False, False))
            self.assertIsNone(second.sequence)
            self.assertEqual(second.bank.up, -1)
            third = sampled_tick(second.bank, (direction, 0, 0), 8, facing_right=facing)
            self.assertEqual((third.sequence, third.bank), (4, InputBank(up=1)))
            fourth = sampled_tick(third.bank, (0, 0, 0), 44, facing_right=facing)
            self.assertEqual(fourth.bank, InputBank())

    def test_running_reversal_discards_simultaneously_pending_up(self):
        for facing in (False, True):
            direction = 1 if facing else -1
            bank = InputBank(right=1) if facing else InputBank(left=1)
            result = sampled_tick(bank, (-direction, -1, 0), 8, facing_right=facing)
            self.assertEqual(result.sequence, 6)
            self.assertEqual(result.bank.up, 0)
            released = sampled_tick(result.bank, (0, 0, 0), 50, facing_right=facing)
            self.assertIsNone(released.sequence)

    def test_jump_reset_distinguishes_taps_before_and_after_pose_26(self):
        early = sampled_tick(InputBank(), (-1, -1, 0), 20, facing_right=False)
        cleared = sampled_tick(early.bank, (0, 0, 0), 26, facing_right=False)
        idle = sampled_tick(cleared.bank, (0, 0, 0), 50, facing_right=False)
        self.assertEqual((idle.bank, idle.sequence), (InputBank(), None))
        late = sampled_tick(cleared.bank, (-1, -1, 0), 27, facing_right=False)
        idle = sampled_tick(late.bank, (0, 0, 0), 50, facing_right=False)
        self.assertEqual((idle.bank, idle.sequence), (InputBank(1, 0, 1), 3))

    def test_mode_reset_drops_released_input_and_rearms_a_still_held_input(self):
        first = sampled_tick(InputBank(), (0, -1, 0), 110, mode=5)
        self.assertEqual(first.bank.up, 0)
        released = sampled_tick(first.bank, (0, 0, 0), 117, mode=1)
        held = sampled_tick(first.bank, (0, -1, 0), 117, mode=1)
        self.assertEqual((released.bank.up, held.bank.up), (0, -1))

    def test_direction_is_reinterpreted_after_facing_changes(self):
        # Physical Left was Backward during a right-facing turn. After the
        # animation flips facing, the same pending latch means Forward.
        first = sampled_tick(InputBank(), (-1, 0, 0), 45, facing_right=True)
        self.assertIsNone(first.sequence)
        second = sampled_tick(first.bank, (0, 0, 0), 48, facing_right=False)
        self.assertEqual(second.sequence, 43)
        third = sampled_tick(second.bank, (0, 0, 0), 50, facing_right=False)
        self.assertEqual((third.sequence, third.bank), (1, InputBank(left=1)))

    def test_pending_tap_has_no_elapsed_time_expiry_but_a_reset_still_discards_it(self):
        bank = InputBank(up=-1)
        for _ in range(1000):
            bank = sampled_tick(bank, (0, 0, 0), 20).bank
        self.assertEqual(bank.up, -1)
        self.assertEqual(sampled_tick(bank, (0, 0, 0), 26).bank.up, 0)

    def test_unrecovered_action_calls_are_explicitly_outside_composed_model(self):
        for bank in (InputBank(up=-1), InputBank(down=-1), InputBank(modifier=-2)):
            with self.assertRaises(NotImplementedError):
                composed_route(bank, 50)


if __name__ == '__main__':
    unittest.main()
