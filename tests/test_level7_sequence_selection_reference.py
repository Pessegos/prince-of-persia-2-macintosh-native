"""Asset-free regression checks for the special-actor research reference."""

import struct
import unittest

from tools.probe_level7_sequence_selection import selection_reference, supporting_column


FRAME = struct.pack('>5h', 0, 0, 10, 0, 3)


def state(**changes):
    return dict(dict(actor=7, pose=150, facing=0, x=458, column=23,
                     sequence=170, selected=175, cursor=9, remainder=45), **changes)


class HeadSelectionReferenceTests(unittest.TestCase):
    def test_missing_resource_preserves_every_field(self):
        initial = state()
        self.assertEqual(selection_reference(initial, 130, False, FRAME), (initial, False))

    def test_both_head_types_turn_and_move_left_not_right(self):
        for actor in (7, 8):
            for pose in (150, 159):
                actual, reload_frame = selection_reference(state(actor=actor, pose=pose), 130, True, FRAME)
                self.assertTrue(reload_frame)
                self.assertEqual((actual['facing'], actual['x']), (-1, 446))
                self.assertEqual((actual['sequence'], actual['selected'], actual['cursor']), (130, 130, 0))
                self.assertEqual((actual['column'], actual['remainder']), supporting_column(446, -1, FRAME))

    def test_other_poses_turn_without_displacement(self):
        actual, reload_frame = selection_reference(state(pose=151), 139, True, FRAME)
        self.assertTrue(reload_frame)
        self.assertEqual((actual['facing'], actual['x']), (-1, 458))

    def test_sequence_boundaries_and_166_exception(self):
        for requested in (129, 140, 165, 167, 170):
            actual, reload_frame = selection_reference(state(), requested, True, FRAME)
            self.assertFalse(reload_frame)
            self.assertEqual((actual['facing'], actual['x'], actual['column']), (0, 458, 23))
        self.assertTrue(selection_reference(state(), 166, True, FRAME)[1])

    def test_serpent_and_already_negative_facing_do_not_realign(self):
        for initial in (state(actor=11), state(facing=-1)):
            actual, reload_frame = selection_reference(initial, 130, True, FRAME)
            self.assertFalse(reload_frame)
            self.assertEqual((actual['x'], actual['column']), (458, 23))

    def test_negative_coordinate_uses_native_truncation_and_extra_decrement(self):
        empty = bytes(10)
        self.assertEqual(supporting_column(21, 0, empty), (-5, -5))

    def test_native_extend_before_word_subtract_order_at_zero(self):
        self.assertEqual(supporting_column(22, 0, bytes(10)), (1280, 48))
        self.assertEqual(supporting_column(26, 0, bytes(10)), (-4, 0))

    def test_input_state_not_modified(self):
        initial = state()
        selection_reference(initial, 130, True, FRAME)
        self.assertEqual(initial, state())


if __name__ == '__main__':
    unittest.main()
