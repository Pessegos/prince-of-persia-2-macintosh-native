"""Synthetic coverage for the head movement-admission research reference."""

import struct
import unittest

from tools.probe_level7_head_movement import gate_blocks, middle_of_cell, movement_reference


def level():
    return bytearray(0x4000)


def tile(data, column, row, kind, foreground=0):
    cell = row * 10 + column
    struct.pack_into('>H', data, cell * 2, kind)
    struct.pack_into('>H', data, 0x780 + cell * 4, foreground)


def state(**changes):
    return dict(dict(room=1, row=1, column=4, actor=7, facing=-1, x=458,
                     y=193, selected=130, body_top=18, body_bottom=50), **changes)


class HeadMovementReferenceTests(unittest.TestCase):
    def test_middle_window_is_inclusive_and_uses_native_origin(self):
        self.assertTrue(middle_of_cell(254 - 12))
        self.assertTrue(middle_of_cell(254 + 12))
        self.assertFalse(middle_of_cell(254 - 13))
        self.assertFalse(middle_of_cell(254 + 13))
        self.assertFalse(middle_of_cell(0))

    def test_vertical_moves_require_space_and_stay_in_same_room_rows(self):
        data = level()
        self.assertTrue(movement_reference(data, state(), 2))
        self.assertTrue(movement_reference(data, state(), 3))
        self.assertFalse(movement_reference(data, state(row=2, y=313), 2))
        self.assertFalse(movement_reference(data, state(row=0, y=73), 3))
        tile(data, 4, 1, 1)
        self.assertFalse(movement_reference(data, state(), 2))
        self.assertTrue(movement_reference(data, state(), 3))

    def test_horizontal_moves_reject_vertical_overshoot_only_in_143_144(self):
        for selected, y in ((143, 192), (144, 194)):
            for direction in (0, 1):
                self.assertFalse(movement_reference(level(), state(selected=selected, y=y), direction))
                self.assertTrue(movement_reference(level(), state(selected=selected, y=193), direction))
        self.assertTrue(movement_reference(level(), state(selected=130, y=100), 0))

    def test_wall_neighbor_rejection_when_relative_probe_crosses_cell(self):
        data = level()
        for kind in (2, 7, 20, 25, 43):
            tile(data, 3, 1, kind)
            self.assertFalse(movement_reference(data, state(), 0))
        # The same X probe with facing zero remains in the cached cell.
        self.assertTrue(movement_reference(data, state(facing=0), 0))

    def test_current_gate_is_checked_only_by_direction_one(self):
        data = level()
        tile(data, 4, 1, 4)
        self.assertTrue(movement_reference(data, state(), 0))
        self.assertFalse(movement_reference(data, state(), 1))

    def test_gate_threshold_differs_between_head_variants(self):
        self.assertTrue(gate_blocks(7, 148, 18, 50))
        self.assertFalse(gate_blocks(8, 148, 18, 50))
        self.assertEqual(gate_blocks(7, 148, 18, 50), gate_blocks(7, 0x8000 + 148, 18, 50))
        self.assertFalse(gate_blocks(7, 160, 18, 50))

    def test_invalid_direction_does_not_admit_a_move(self):
        for direction in (-1, 4, 100):
            self.assertFalse(movement_reference(level(), state(), direction))


if __name__ == '__main__':
    unittest.main()
