"""Synthetic checks for head recovery references, not original execution."""

import struct
import unittest

from tools.probe_level7_head_recovery import peaceful_reference, recovery_reference


FRAME = struct.pack('>5h', 0, 0, 10, 0, 3)


def state(**changes):
    return dict(dict(actor=7, pose=150, facing=0, x=458, column=7,
                     sequence=170, selected=175, cursor=9, remainder=45,
                     row=1, y=333, horizontal_velocity=7, vertical_velocity=-9,
                     armed=1, alert=3, special=6), **changes)


class HeadRecoveryReferenceTests(unittest.TestCase):
    def test_peaceful_clears_motion_armed_and_alert_then_aligns(self):
        actual, reload_frame = peaceful_reference(state(), FRAME)
        self.assertTrue(reload_frame)
        self.assertEqual((actual['sequence'], actual['selected'], actual['cursor']), (139, 139, 0))
        self.assertEqual((actual['x'], actual['column'], actual['y']), (458, 4, 193))
        self.assertEqual((actual['horizontal_velocity'], actual['vertical_velocity'],
                          actual['armed'], actual['alert']), (0, 0, 0, 0))
        self.assertEqual(actual['special'], 6)

    def test_floor_alignment_applies_the_head_offset_on_each_row(self):
        for actor in (7, 8):
            for row in (0, 1, 2):
                actual, _ = peaceful_reference(state(actor=actor, row=row), FRAME)
                self.assertEqual(actual['y'], 73 + row * 120)

    def test_recovery_waits_for_cached_alive_threshold_six(self):
        for cached_alive in (-1, 0, 5):
            actual, reload_frame, requests, clear_mode = recovery_reference(state(), FRAME, cached_alive)
            self.assertEqual((requests, clear_mode, reload_frame), ([166], False, True))
            self.assertEqual((actual['x'], actual['y'], actual['special']), (446, 193, 0))
            self.assertEqual((actual['armed'], actual['horizontal_velocity'], actual['alert']), (1, 7, 3))
        actual, _, requests, clear_mode = recovery_reference(state(), FRAME, 6)
        self.assertEqual((requests, clear_mode, actual['armed']), ([139], True, 0))

    def test_already_selected_166_preserves_cursor_position_and_floor(self):
        initial = state(selected=166)
        actual, reload_frame, requests, clear_mode = recovery_reference(initial, FRAME, 5)
        self.assertEqual(actual, dict(initial, special=0))
        self.assertEqual((reload_frame, requests, clear_mode), (False, [], False))

    def test_threshold_overrides_already_selected_166(self):
        actual, _, requests, clear_mode = recovery_reference(state(selected=166), FRAME, 7)
        self.assertEqual((requests, clear_mode, actual['special']), ([139], True, 0))

    def test_recovery_clears_special_even_without_a_sequence_change(self):
        for selected in (130, 166, 175):
            self.assertEqual(recovery_reference(state(selected=selected), FRAME, -1)[0]['special'], 0)

    def test_inputs_are_not_mutated(self):
        initial = state()
        peaceful_reference(initial, FRAME)
        recovery_reference(initial, FRAME, 6)
        self.assertEqual(initial, state())


if __name__ == '__main__':
    unittest.main()
