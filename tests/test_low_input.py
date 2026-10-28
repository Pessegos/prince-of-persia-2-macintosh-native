"""Low/prone input-consumption rules confirmed against actual GenCtrl/JumpSeq."""

from dataclasses import replace
import unittest

from tools.reference_input_bank import InputBank
from tools.reference_low_input import LowContext, crouch_entry, low_control, sampled_low_tick


class LowInputTests(unittest.TestCase):
    def test_lower_reset_discards_a_released_tap_but_rearms_a_held_direction(self):
        for facing in (False, True):
            direction = 1 if facing else -1
            context = LowContext(pose=108, mode=5, facing_right=facing)
            lower = sampled_low_tick(InputBank(), (direction, 1, -1), context)
            self.assertEqual(lower.bank, InputBank(modifier=-1))
            idle = replace(context, pose=109, mode=1)
            released = sampled_low_tick(lower.bank, (0, 1, -1), idle)
            held = sampled_low_tick(lower.bank, (direction, 1, -1), idle)
            self.assertEqual(released.requests, ())
            self.assertEqual(held.requests, (79,))

    def test_crawl_body_reset_separates_a_tap_from_continued_hold(self):
        context = LowContext(pose=251, here_kind=7, sequence=122, selected=122)
        first = sampled_low_tick(InputBank(), (1, 0, -1), context)
        self.assertEqual(first.requests, (122,))
        body = sampled_low_tick(first.bank, (1, 0, -1), replace(context, pose=252))
        self.assertEqual(body.bank, InputBank(modifier=-1))
        self.assertEqual(sampled_low_tick(body.bank, (0, 0, -1), context).requests, ())
        self.assertEqual(sampled_low_tick(body.bank, (1, 0, -1), context).requests, (122,))

    def test_raw_gate_does_not_erase_a_pending_low_command(self):
        bank = InputBank(right=-1, down=-1, modifier=-1)
        result = sampled_low_tick(bank, (0, 0, 0), LowContext(), gate_matches=False)
        self.assertEqual(result.requests, (79,))
        self.assertEqual(result.bank, InputBank(right=1))

    def test_entry_consumes_down_and_preserves_modifier_even_if_resource_is_missing(self):
        bank = InputBank(-1, -1, -1, -1, -2)
        for missing in ((), (50,)):
            result = crouch_entry(bank, LowContext(missing_sequences=missing))
            self.assertEqual(result.bank, InputBank(down=1, modifier=-2))
            self.assertEqual(result.requests, (50,))
            self.assertEqual(result.selected, 117 if missing else 50)

    def test_ruins_scythe_crouch_entry_aligns_only_below_eight(self):
        for facing in (False, True):
            for distance in (7, 8, 9):
                result = crouch_entry(InputBank(down=-1), LowContext(
                    level=6, environment=4, ahead_kind=12, distance=distance, facing_right=facing))
                adjustment = -1 if distance == 7 else 0
                self.assertEqual(result.x, 400 + adjustment * (1 if facing else -1))

    def test_down_hold_consumes_down_and_clears_unaccepted_directions(self):
        bank = InputBank(1, -1, -1, -1, -2)
        result = low_control(bank, LowContext())
        self.assertEqual(result.bank, InputBank(down=1, modifier=-2))
        self.assertEqual(result.requests, ())

    def test_fresh_forward_under_down_consumes_forward_instead_of_down(self):
        for modifier in (-2, -1, 0, 1, 2):
            result = low_control(InputBank(-1, -1, -1, 1, modifier), LowContext())
            self.assertEqual(result.requests, (79,))
            self.assertEqual(result.bank, InputBank(left=1, modifier=modifier))

    def test_released_down_rises_before_forward_unless_clearance_blocks_it(self):
        bank = InputBank(left=-1, up=-1)
        rising = low_control(bank, LowContext())
        blocked = low_control(bank, LowContext(gate_blocked=True))
        self.assertEqual((rising.requests, rising.bank), ((49,), bank))
        self.assertEqual((blocked.requests, blocked.bank), ((79,), bank))

    def test_scythe_clearance_only_vetoes_rise_when_the_level_flag_is_enabled(self):
        bank = InputBank()
        self.assertEqual(low_control(bank, LowContext(scythe_blocked=True)).requests, (49,))
        self.assertEqual(low_control(bank, LowContext(scythe_blocked=True, scythes_enabled=True)).requests, ())

    def test_lie_down_preserves_the_column_and_aligns_around_the_real_edges(self):
        bank = InputBank(left=-1, down=1)
        for facing, x in ((True, 470), (False, 400)):
            result = low_control(bank, LowContext(facing_right=facing, x=x, ahead_kind=7))
            self.assertEqual(result.requests, (125,))
            self.assertEqual(result.x, 421 if facing else 496)
        self.assertEqual(low_control(bank, LowContext(ahead_kind=7, foreground=3)).requests, (79,))

    def test_pickup_and_sequence_111_clear_directions_and_consume_modifier(self):
        bank = InputBank(-1, -1, -1, -1, -2)
        for context in (LowContext(pickup=True), LowContext(sequence=111, selected=111)):
            result = low_control(bank, context)
            self.assertEqual(result.bank, InputBank(modifier=1))
            self.assertEqual(result.requests, ())
        self.assertFalse(low_control(bank, LowContext(sequence=111, selected=111)).pickup_checked)

    def test_carpet_branch_precedes_pickup_and_low_pose_input(self):
        bank = InputBank(left=-1, down=-1, modifier=-1)
        result = low_control(bank, LowContext(room=3, left_kind=18, pickup=True))
        self.assertTrue(result.carpet)
        self.assertFalse(result.pickup_checked)
        self.assertEqual(result.bank, bank)
        self.assertFalse(low_control(bank, LowContext(room=3, left_kind=18, selected=17)).carpet)

    def test_nonidle_prone_poses_clear_directions_but_do_not_consume_modifier(self):
        bank = InputBank(-1, -1, -1, -1, -2)
        for pose in (246, 250, 252, 261):
            result = low_control(bank, LowContext(pose=pose, here_kind=7))
            self.assertEqual(result.bank, InputBank(modifier=-2))
        for pose in (262, 263):
            result = low_control(bank, LowContext(pose=pose, here_kind=7))
            self.assertEqual(result.bank, bank)

    def test_idle_prone_requires_fresh_horizontal_and_forward_has_priority(self):
        context = LowContext(pose=251, here_kind=7, selected=122, sequence=122)
        for bank, requests in ((InputBank(left=-1, right=-1), (122,)),
                                (InputBank(left=1, right=-1), (123,)),
                                (InputBank(left=1, right=1), ())):
            result = low_control(bank, context)
            self.assertEqual(result.requests, requests)
            if requests:
                self.assertEqual(result.bank, InputBank())

    def test_stand_selection_is_seen_by_the_following_prone_dispatch(self):
        bank = InputBank(left=-1, up=1)
        result = low_control(bank, LowContext(pose=251, ahead_kind=7, warning=0))
        self.assertEqual(result.requests, (124,))
        self.assertEqual((result.sequence, result.selected, result.cursor), (124, 124, 0))
        self.assertEqual(result.bank, InputBank(up=1))
        self.assertEqual(result.warning, 1)

    def test_missing_resource_preserves_selection_but_not_already_consumed_input(self):
        context = LowContext(ahead_kind=7, missing_sequences=(125,))
        result = low_control(InputBank(left=-1, down=1), context)
        self.assertEqual(result.requests, (125,))
        self.assertEqual((result.sequence, result.selected, result.cursor), (117, 117, 4))
        self.assertEqual(result.bank, InputBank(left=1))

    def test_genctrl_protection_precedes_all_low_actions(self):
        bank = InputBank(-1, -1, -1, -1, -2)
        for mode in (4, 5, 9):
            result = low_control(bank, LowContext(mode=mode, pickup=True, ahead_kind=7))
            self.assertEqual(result.bank, InputBank(modifier=-2))
            self.assertFalse(result.pickup_checked)
            self.assertEqual(result.requests, ())
        result = low_control(bank, replace(LowContext(), selected=27))
        self.assertEqual(result.bank, InputBank(modifier=-2))


if __name__ == '__main__':
    unittest.main()
