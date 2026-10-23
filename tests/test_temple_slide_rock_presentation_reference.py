"""Asset-free slide-rock queue/restoration checks using synthetic map and DATA tables."""

import struct
import unittest

from tests.test_temple_slide_rock_geometry_reference import level_fixture, tile
from tools.probe_temple_slide_rock_geometry import TempleCellReader
from tools.probe_temple_slide_rock_presentation import (
    CAPACITY, STORAGE_SIZE, first_in_row, mob_rect_reference, presentation_reference, view_for,
)


def rock(x=0, y=236, mark=0, control=2, anchor=153):
    return (x, y, 1, mark, control, 6, 1, anchor)


class TempleSlideRockPresentationTests(unittest.TestCase):
    def setUp(self):
        self.level = level_fixture()
        self.heights = list(range(50, 64))
        self.heights[6:8] = (80, 83)
        self.widths = list(range(20, 34))
        self.widths[6] = 82
        self.decorations = ((7, -10), (12, -20), (17, -30))
        self.storage = bytes((i * 11 + 3) % 256 for i in range(STORAGE_SIZE))
        self.view = view_for(1, 'current')
        self.reader = None

    def present(self, mob=None, **kwargs):
        self.reader = TempleCellReader(self.level, self.view['current'])
        args = dict(view=self.view, visible=True, heights=self.heights, widths=self.widths,
                    decorations=self.decorations, clip=(-1000, -1000, 2000, 2000),
                    storage=self.storage, count=2)
        args.update(kwargs)
        return presentation_reference(rock() if mob is None else mob, self.reader, **args)

    @staticmethod
    def objects(result):
        return [event for event in result['events'] if event[0] == 'object']

    @staticmethod
    def record(result, index):
        return struct.unpack_from('>14h', result['storage'], 16 + index * 28)

    def test_deleted_record_returns_without_even_visibility_or_dimension_changes(self):
        mob = rock(mark=-1)
        result = self.present(mob)
        self.assertEqual(result['mob'], mob)
        self.assertEqual(result['events'], [])
        self.assertEqual(result['storage'], self.storage)
        self.assertEqual(result['heights'], tuple(self.heights))
        self.assertEqual((result['count'], result['screen_cell']), (2, -1234))
        self.assertEqual(self.reader.requests, [])

    def test_invisible_record_only_queries_visibility_and_sets_screen_cell(self):
        result = self.present(visible=False)
        self.assertEqual(result['events'], [('visibility', 1, 10)])
        self.assertEqual(result['screen_cell'], 10)
        self.assertEqual(result['storage'], self.storage)
        self.assertEqual(result['heights'], tuple(self.heights))
        self.assertEqual(self.reader.requests, [])

    def test_visible_filled_band_uses_temporary_dimensions_then_canonicalizes_heights(self):
        mob = rock()
        result = self.present(mob)
        objects = self.objects(result)
        self.assertFalse(any(event[0] == 'redraw' for event in result['events']))
        self.assertEqual(objects[0][3][5], 7)
        self.assertEqual(objects[0][5], 111)
        self.assertEqual(objects[1][3][5], 6)
        self.assertEqual(objects[1][5], 109)
        self.assertEqual(result['mob'], mob)
        expected = list(self.heights)
        expected[6] = expected[7]
        self.assertEqual(result['heights'], tuple(expected))
        self.assertEqual(result['widths'], tuple(self.widths))

    def test_gap_redraw_shifts_up_and_right_caps_width_then_restores(self):
        tile(self.level, 1, 0, 0, 0)
        mob = rock(anchor=30)
        result = self.present(mob)
        redraw = next(event for event in result['events'] if event[0] == 'redraw')
        self.assertEqual(redraw, ('redraw', 2, (8, 124, 1, 0, 2, 6, 1, 30), 10, 19, 30))
        self.assertIn(('redraw_sink', 0x3ba, (105, 8, 125, 38), -1), result['events'])
        self.assertEqual(self.objects(result)[0][5], 83)
        self.assertEqual(result['mob'], mob)
        self.assertEqual(result['widths'], tuple(self.widths))

    def test_trailing_body_uses_x_plus_51_y_minus_two_and_type_six(self):
        result = self.present(rock(x=5))
        trailing = self.objects(result)[1]
        self.assertEqual(trailing[2:5], (234, (56, 234, 1, 0, 2, 6, 1, 153), 11))
        # The strict outer comparison does not admit X+51 equal to the anchor.
        result = self.present(rock(x=102))
        self.assertEqual([event[3][5] for event in self.objects(result)], [7, 8, 8, 8, 8, 9])

    def test_strips_keep_initial_phase_while_x_increments_by_36(self):
        result = self.present()
        objects = self.objects(result)
        for kind, (dx, dy) in zip((8, 8, 9), self.decorations):
            strip = [event for event in objects if event[3][5] == kind and event[2] == 236 + dy]
            self.assertEqual([event[3][0] for event in strip], list(range(dx, 153, 36)))
            self.assertTrue(strip)
            for event in strip:
                self.assertEqual(self.record(result, event[1])[12], (dx & 7) >> 1)

    def test_decoration_cell_uses_stored_row_with_type_eight_extra_column(self):
        result = self.present(rock(y=6))
        objects = self.objects(result)
        self.assertEqual(objects[0][4], 0)  # Main body's row is recomputed from Y.
        for event in objects[2:]:
            mob = event[3]
            self.assertEqual(event[4], 10 + mob[0] // 51 + int(mob[5] == 8))

    def test_queue_fields_padding_existing_prefix_and_unwritten_tail(self):
        result = self.present()
        self.assertEqual(result['storage'][:16 + 2 * 28], self.storage[:16 + 2 * 28])
        tail = 16 + result['count'] * 28
        self.assertEqual(result['storage'][tail:], self.storage[tail:])
        for event in self.objects(result):
            index, y, mob = event[1:4]
            record = self.record(result, index)
            self.assertEqual(record[:5], (mob[0], y, 4, mob[7], 0))
            self.assertEqual(record[6], mob[5] | 0x80)
            self.assertEqual(record[11], 0)
            self.assertEqual(record[13], -1)
            offset = 16 + index * 28 + 10
            self.assertEqual(result['storage'][offset:offset + 2], self.storage[offset:offset + 2])

    def test_empty_clips_still_append_objects_but_with_zero_rectangles(self):
        full = self.present()
        outside = self.present(clip=(1000, 1000, 1100, 1100))
        self.assertEqual(full['count'], outside['count'])
        for event in self.objects(outside):
            self.assertEqual(self.record(outside, event[1])[7:11], (0, 0, 0, 0))

    def test_both_horizontal_relations_translate_minus_510_not_opposite_directions(self):
        mob = rock(x=51)
        base = (156, 51, 237, 133)
        self.assertEqual(mob_rect_reference(mob, self.heights, self.widths, self.view), (base, None))
        for relation in ('right', 'left'):
            rect, event = mob_rect_reference(mob, self.heights, self.widths, view_for(1, relation))
            self.assertEqual(rect, (156, -459, 237, -377))
            self.assertEqual(event, ('offset', 0, -510, base, rect))

    def test_vertical_and_diagonal_projection_uses_365_and_unrelated_is_empty(self):
        for relation, dy, dx in (('below', -365, 0), ('above', 365, 0),
                                 ('below_left', -365, -510), ('above_right', 365, -510)):
            rect, event = mob_rect_reference(rock(), self.heights, self.widths, view_for(1, relation))
            self.assertEqual(rect, (156 + dy, dx, 237 + dy, 82 + dx))
            self.assertEqual(event[1:3], (dy, dx))
        self.assertEqual(mob_rect_reference(rock(), self.heights, self.widths,
                                           view_for(1, 'unrelated')), ((0, 0, 0, 0), None))

    def test_get_row_boundary_and_index_cell_sentinel(self):
        for y, cell in ((5, 30), (6, 0), (125, 10), (236, 10)):
            self.assertEqual(self.present(rock(y=y), visible=False)['screen_cell'], cell)
        self.assertEqual(self.present(rock(x=510), visible=False)['screen_cell'], 30)
        self.assertEqual([first_in_row(row) for row in (-2, -1, 0, 1, 2)], [-11, -1, 0, 10, 20])

    def test_control_word_does_not_suppress_terminal_or_stopped_rock_presentation(self):
        baseline = self.present(rock(control=-2))
        for control in (0, 2, 100):
            result = self.present(rock(control=control))
            self.assertEqual(result['storage'], baseline['storage'])
            self.assertEqual(result['heights'], baseline['heights'])
            self.assertEqual(result['mob'], rock(control=control))

    def test_negative_anchor_uses_unsigned_outer_test_but_signed_inner_strip_test(self):
        tile(self.level, 1, 0, 0, 0)
        result = self.present(rock(anchor=-1))
        redraw = next(event for event in result['events'] if event[0] == 'redraw')
        self.assertEqual(redraw[-1], -1)
        self.assertEqual([event[3][5] for event in self.objects(result)], [7, 6])

    def test_invalid_domains_and_supplied_queue_budget_fail_closed(self):
        for mob in ((0, 1), rock(x=562), rock(control=32768)):
            with self.assertRaises(ValueError):
                self.present(mob)
        for overrides in (dict(count=-1), dict(count=CAPACITY), dict(count=CAPACITY - 1),
                          dict(storage=bytes(16)), dict(heights=[1] * 13), dict(decorations=())):
            with self.assertRaises(ValueError):
                self.present(**overrides)
        with self.assertRaises(ValueError):
            view_for(1, 'not-a-relation')


if __name__ == '__main__':
    unittest.main()
