import unittest

from tools.probe_temple_collision_history import TABLES, history_reference
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture


class TempleCollisionHistoryTests(unittest.TestCase):
    def query(self, current, previous, *, facing=0, velocity=1, column=4):
        tables = {name: [(i + 1) * 257 + c for c in range(10)] for i, name in enumerate(TABLES)}
        tables['lower_masks'] = [0xafff] * 10
        actor = bytearray(actor_fixture(1, 1, column, facing, 0))
        put_actor(actor, 18, velocity)
        return history_reference(bytes(actor), current, previous, tables), tables

    def test_same_row_and_plus_or_minus_three_select_current(self):
        for previous in (1, -2, 4):
            result, tables = self.query(1, previous)
            self.assertEqual(result['selected'], 'current')
            self.assertEqual(result['tables']['history_tags'], tables['current_tags'])
            self.assertEqual(result['tables']['history_masks'], tables['current_masks'])

    def test_plus_one_and_minus_two_select_upper(self):
        for previous in (2, -1):
            result, tables = self.query(1, previous)
            self.assertEqual(result['selected'], 'upper')
            self.assertEqual(result['tables']['history_tags'], tables['upper_tags'])

    def test_other_rows_select_lower_and_adjust_it_before_copying(self):
        result, tables = self.query(1, 0)
        self.assertEqual(result['selected'], 'lower')
        self.assertEqual(result['tables']['lower_masks'][4], 0xf0)
        self.assertEqual(result['tables']['history_masks'][4], 0xf0)
        self.assertEqual(result['tables']['history_tags'], tables['lower_tags'])
        self.assertEqual(tables['lower_masks'][4], 0xafff)

    def test_facing_and_velocity_choose_the_retained_nibble(self):
        for facing, velocity, expected in ((0, 1, 0xf0), (-1, -1, 0xf0),
                                            (0, -1, 0x0f), (-1, 1, 0x0f), (0, 0, 0xafff)):
            result, _ = self.query(1, 0, facing=facing, velocity=velocity)
            self.assertEqual(result['tables']['history_masks'][4], expected)

    def test_an_offscreen_column_is_not_used_as_an_array_index(self):
        for column in (-1, 10, 1280):
            result, _ = self.query(1, 0, column=column)
            self.assertEqual(result['tables']['history_masks'], [0xafff] * 10)

    def test_three_tag_banks_are_cleared_but_the_other_masks_are_not(self):
        result, tables = self.query(1, 1)
        for name in ('upper_tags', 'lower_tags', 'current_tags'):
            self.assertEqual(result['tables'][name], [65535] * 10)
        for name in ('upper_masks', 'lower_masks', 'current_masks'):
            self.assertEqual(result['tables'][name], tables[name])

    def test_neighbor_row_comparison_is_extended_not_wrapped(self):
        result, _ = self.query(32767, -32766)
        self.assertEqual(result['selected'], 'lower')
        result, _ = self.query(-32768, 32766)
        self.assertEqual(result['selected'], 'lower')

    def test_helper_uses_supplied_physical_rows_not_the_actor_fixture_row(self):
        result, _ = self.query(5, 6)
        self.assertEqual(result['selected'], 'upper')

    def test_incomplete_banks_are_outside_the_reference_domain(self):
        with self.assertRaises(ValueError):
            history_reference(actor_fixture(1, 1, 4, 0, 0), 1, 1, {})
