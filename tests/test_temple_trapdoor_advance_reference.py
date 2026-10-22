"""Synthetic phase/audio rules, distinct from original execution."""

import unittest

from tools.probe_temple_trapdoor_advance import advance_reference


def mob(phase=1, deleted=0):
    return (204, 245, 1, deleted, 0, 10, 1, phase)


class TrapDoorAdvanceReferenceTests(unittest.TestCase):
    def test_only_low_five_bits_control_advancement(self):
        for phase, expected in ((1, 2), (16, 17), (17, 17), (75, 76), (80, 81), (81, 81)):
            self.assertEqual(advance_reference(mob(phase), True, False)[0][7], expected)

    def test_deleted_minus_one_rejects_everything_but_other_states_do_not(self):
        initial = mob(1, -1)
        self.assertEqual(advance_reference(initial, False, False), (initial, [], []))
        self.assertEqual(advance_reference(mob(1, 2), True, True)[0][7], 2)

    def test_active_initial_sound_short_circuits_second_query(self):
        self.assertEqual(advance_reference(mob(), True, False)[1:], ([197], []))

    def test_active_loop_sound_suppresses_another_request(self):
        self.assertEqual(advance_reference(mob(), False, True)[1:], ([197, 198], []))

    def test_no_sound_requests_loop_cue_even_at_terminal_phase(self):
        self.assertEqual(advance_reference(mob(17), False, False)[1:], ([197, 198], [198]))

    def test_advancement_does_not_delete_or_change_geometry(self):
        initial = mob(16)
        result, _, _ = advance_reference(initial, True, True)
        self.assertEqual(result[:7], initial[:7])

    def test_both_initial_states_reach_low17_in_different_update_counts(self):
        for start, steps, final in ((1, 16, 17), (75, 6, 81)):
            current = mob(start)
            for _ in range(steps):
                current, _, _ = advance_reference(current, True, True)
            self.assertEqual(current[7], final)
            self.assertEqual(advance_reference(current, True, True)[0], current)


if __name__ == '__main__':
    unittest.main()
