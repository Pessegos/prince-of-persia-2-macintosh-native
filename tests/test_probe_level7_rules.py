"""Synthetic checks for the independent crevice reference, not native parity."""

import struct
import unittest

from tools.probe_level7_rules import read_cell, reference_front, reference_scan


def level_fixture():
    return bytearray(0x49ca)


def set_cell(data, room, column, row, kind=7, foreground=0):
    cell = row * 10 + column
    struct.pack_into('>H', data, (room - 1) * 60 + cell * 2, kind)
    struct.pack_into('>H', data, 0x780 + (room - 1) * 120 + cell * 4, foreground)


def foreground(data, room, column, row):
    return struct.unpack_from('>H', data, 0x780 + (room - 1) * 120 + (row * 10 + column) * 4)[0]


class ReferenceTests(unittest.TestCase):
    def test_absent_crevice_does_not_change_level(self):
        data = level_fixture()
        self.assertEqual(reference_scan(data, 1, 5, 0, 1), data)

    def test_scans_whole_row_not_only_actor_neighborhood(self):
        data = level_fixture()
        set_cell(data, 1, 0, 0, foreground=0x4201)
        result = reference_scan(data, 1, 8, 0, 1)
        self.assertEqual(foreground(result, 1, 0, 0), 0x4281)
        self.assertEqual(foreground(data, 1, 0, 0), 0x4201)

    def test_only_first_contiguous_group_changes(self):
        data = level_fixture()
        for col in (2, 3, 6):
            set_cell(data, 1, col, 1, foreground=1)
        result = reference_scan(data, 1, 4, 1, 1)
        self.assertEqual([foreground(result, 1, col, 1) for col in (2, 3, 6)], [0x81, 0x81, 1])

    def test_reveal_and_hide_preserve_other_foreground_bits(self):
        data = level_fixture()
        set_cell(data, 1, 2, 2, foreground=0x1282)
        hidden = reference_scan(data, 1, 2, 2, 0)
        self.assertEqual(foreground(hidden, 1, 2, 2), 0x1202)
        shown = reference_scan(hidden, 1, 2, 2, 1)
        self.assertEqual(shown, data)
        self.assertEqual(reference_scan(shown, 1, 2, 2, 1), shown)

    def test_horizontal_group_crosses_native_room_link(self):
        data = level_fixture()
        struct.pack_into('>H', data, 0x2080 + 2, 2)
        struct.pack_into('>H', data, 0x2080 + 8, 1)
        set_cell(data, 1, 9, 1, foreground=1)
        set_cell(data, 2, 0, 1, foreground=0)
        result = reference_scan(data, 2, 0, 1, 1)
        self.assertEqual(foreground(result, 1, 9, 1), 0x81)
        self.assertEqual(foreground(result, 2, 0, 1), 0x80)
        self.assertIsNone(read_cell(data, 1, -1, 1))

    def test_front_facing_selected_id_and_hidden_type_gate(self):
        data = level_fixture()
        set_cell(data, 1, 4, 0, foreground=1)
        for col, facing in ((3, 0), (5, -1)):
            with self.subTest(column=col, facing=facing):
                result = reference_front(data, 1, col, 0, facing, 5)
                self.assertEqual(foreground(result, 1, 4, 0), 0x81)
                self.assertEqual(reference_front(data, 1, col, 0, facing, 17), data)
        self.assertEqual(reference_front(data, 1, 5, 0, 0, 5), data)
        set_cell(data, 1, 4, 0, foreground=3)
        self.assertEqual(reference_front(data, 1, 3, 0, 0, 5), data)

    def test_reference_deliberately_rejects_vertical_out_of_scope_input(self):
        with self.assertRaisesRegex(ValueError, 'vertical'):
            read_cell(level_fixture(), 1, 0, 3)


if __name__ == '__main__':
    unittest.main()
