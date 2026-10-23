"""Asset-free geometry reference tests, independent of original game resources."""

import struct
import unittest

from tools.probe_temple_slide_rock_geometry import (
    TempleCellReader, span_reference, stop_predicate_reference,
)


def level_fixture(number=10):
    level = bytearray(0x2200)
    struct.pack_into('>H', level, 0x2180, 32)
    struct.pack_into('>H', level, 0x2186, 2)
    struct.pack_into('>H', level, 0x218a, number)
    for room in range(32):
        for cell in range(30):
            struct.pack_into('>H', level, room * 60 + cell * 2, 1)
            struct.pack_into('>H', level, 0x780 + room * 120 + cell * 4, 0x8000 + cell)
    return level


def tile(level, room, column, row, kind):
    struct.pack_into('>H', level, (room - 1) * 60 + (row * 10 + column) * 2, kind)


def link(level, room, direction, target):
    struct.pack_into('>H', level, 0x2080 + (room - 1) * 8 + direction * 2, target)


def rock(x=0, row=1, anchor=459):
    return (x, 116 + row * 120, 1, 0, 2, 6, row, anchor)


class TempleSlideRockGeometryTests(unittest.TestCase):
    def test_ordinary_cell_and_hot_cache_preserve_signed_foreground(self):
        reader = TempleCellReader(level_fixture(), 1)
        self.assertEqual(reader.read(1, 4, 1), 1)
        self.assertEqual(reader.cache, (1, -32754, 14, 1, 4, 1))
        self.assertEqual(reader.read(1, 4, 1), 1)
        self.assertEqual(reader.requests, [(1, 4, 1)] * 2)

    def test_horizontal_links_are_left_then_right_in_native_link_order(self):
        level = level_fixture()
        link(level, 1, 0, 2)
        link(level, 1, 1, 3)
        tile(level, 2, 9, 1, 12)
        tile(level, 3, 0, 1, 13)
        reader = TempleCellReader(level, 1)
        self.assertEqual(reader.read(1, -1, 1), 12)
        self.assertEqual(reader.cache[2:], (19, 2, 9, 1))
        self.assertEqual(reader.read(1, 10, 1), 13)
        self.assertEqual(reader.cache[2:], (10, 3, 0, 1))

    def test_vertical_links_normalize_rows_and_update_cache(self):
        level = level_fixture()
        link(level, 1, 2, 2)
        link(level, 1, 3, 3)
        tile(level, 2, 4, 2, 17)
        tile(level, 3, 4, 0, 19)
        reader = TempleCellReader(level, 1)
        self.assertEqual(reader.read(1, 4, -1), 17)
        self.assertEqual(reader.cache[2:], (24, 2, 4, 2))
        self.assertEqual(reader.read(1, 4, 3), 19)
        self.assertEqual(reader.cache[2:], (4, 3, 4, 0))

    def test_diagonal_can_find_vertical_then_horizontal_after_missing_horizontal(self):
        level = level_fixture()
        link(level, 1, 2, 2)
        link(level, 2, 0, 3)
        tile(level, 3, 9, 2, 43)
        reader = TempleCellReader(level, 1)
        self.assertEqual(reader.read(1, -1, -1), 43)
        self.assertEqual(reader.cache[2:], (29, 3, 9, 2))

    def test_existing_horizontal_path_is_used_before_original_vertical_path(self):
        level = level_fixture()
        link(level, 1, 0, 2)
        link(level, 2, 2, 3)
        link(level, 1, 2, 4)
        link(level, 4, 0, 5)
        tile(level, 3, 9, 2, 12)
        tile(level, 5, 9, 2, 13)
        self.assertEqual(TempleCellReader(level, 1).read(1, -1, -1), 12)

    def test_missing_link_uses_undefined_wall_and_zero_foreground(self):
        reader = TempleCellReader(level_fixture(), 1)
        self.assertEqual(reader.read(1, -1, 1), 20)
        self.assertEqual(reader.cache, (20, 0, 19, 0, 9, 1))

    def test_undefined_level_thirteen_view_rooms_four_and_thirteen_are_space(self):
        for number in (10, 11, 12, 13):
            for view in (1, 4, 13):
                reader = TempleCellReader(level_fixture(number), view)
                self.assertEqual(reader.read(1, -1, 1),
                                 0 if number == 13 and view in (4, 13) else 20)

    def test_room_zero_negative_row_uses_native_first_in_row_sentinel(self):
        reader = TempleCellReader(level_fixture(), 1)
        self.assertEqual(reader.read(0, -1, -1), 20)
        self.assertEqual(reader.cache, (20, 0, 8, 0, 9, -1))

    def test_predicate_rejects_all_is_space_kinds_and_marker_twenty_five(self):
        for kind in range(64):
            level = level_fixture()
            tile(level, 1, 0, 0, kind)
            reader = TempleCellReader(level, 1)
            result = stop_predicate_reference(rock(), reader)
            self.assertEqual(result, kind not in (0, 9, 25, 27, 47, 49))

    def test_filled_rows_pass_including_wall_tiles_not_just_floor(self):
        for kind in (1, 2, 4, 7, 20, 43):
            level = level_fixture()
            for row in (0, 1):
                for col in (0, 1):
                    tile(level, 1, col, row, kind)
            reader = TempleCellReader(level, 1)
            self.assertTrue(stop_predicate_reference(rock(), reader))
            self.assertEqual(reader.requests, [(1, 0, 0), (1, 1, 0), (1, 0, 1), (1, 1, 1)])

    def test_upper_row_rejection_short_circuits_second_row(self):
        level = level_fixture()
        tile(level, 1, 1, 0, 25)
        reader = TempleCellReader(level, 1)
        self.assertFalse(stop_predicate_reference(rock(), reader))
        self.assertEqual(reader.requests, [(1, 0, 0), (1, 1, 0)])

    def test_current_row_rejection_stops_at_first_bad_cell(self):
        level = level_fixture()
        tile(level, 1, 0, 1, 0)
        reader = TempleCellReader(level, 1)
        self.assertFalse(stop_predicate_reference(rock(), reader))
        self.assertEqual(reader.requests, [(1, 0, 0), (1, 1, 0), (1, 0, 1)])

    def test_anchor_caps_scan_and_reversed_interval_is_vacuously_true(self):
        reader = TempleCellReader(level_fixture(), 1)
        self.assertTrue(span_reference(rock(x=102, anchor=0), 0, 51, reader))
        self.assertEqual(reader.requests, [])
        self.assertTrue(span_reference(rock(x=0, anchor=1), 0, 82, reader))
        self.assertEqual(reader.requests, [(1, 0, 1)])

    def test_anchor_word_is_unsigned_in_distance_cap(self):
        reader = TempleCellReader(level_fixture(), 1)
        self.assertTrue(span_reference(rock(anchor=-1), 0, 82, reader))
        self.assertEqual(reader.requests, [(1, 0, 1), (1, 1, 1)])

    def test_start_plus_two_and_end_divisions_truncate_toward_zero(self):
        reader = TempleCellReader(level_fixture(), 1)
        self.assertTrue(span_reference(rock(x=-16), 0, 0, reader))
        self.assertEqual(reader.requests, [(1, 0, 1)])
        reader = TempleCellReader(level_fixture(), 1)
        self.assertTrue(span_reference(rock(x=49), 0, 51, reader))
        self.assertEqual(reader.requests, [(1, 1, 1)])

    def test_negative_or_zero_length_does_not_automatically_mean_no_cell_reads(self):
        for length in (-2, -1, 0):
            reader = TempleCellReader(level_fixture(), 1)
            self.assertTrue(span_reference(rock(), 0, length, reader))
            self.assertEqual(reader.requests, [(1, 0, 1)])

    def test_reference_does_not_modify_level_or_mob(self):
        level, mob = level_fixture(), list(rock())
        before_level, before_mob = bytes(level), mob[:]
        stop_predicate_reference(mob, TempleCellReader(level, 1))
        self.assertEqual(bytes(level), before_level)
        self.assertEqual(mob, before_mob)

    def test_bounded_inputs_fail_closed(self):
        level = level_fixture()
        for request in ((33, 0, 0), (1, -3, 0), (1, 13, 0), (1, 0, -2), (1, 0, 4)):
            with self.assertRaises(ValueError):
                TempleCellReader(level, 1).read(*request)
        for mob, offset, length in ((rock(x=-17), 0, 51), (rock(x=562), 0, 51),
                                     (rock(), -2, 51), (rock(), 0, 83)):
            with self.assertRaises(ValueError):
                span_reference(mob, offset, length, TempleCellReader(level, 1))
        link(level, 1, 0, 33)
        with self.assertRaises(ValueError):
            TempleCellReader(level, 1).read(1, -1, 1)


if __name__ == '__main__':
    unittest.main()
