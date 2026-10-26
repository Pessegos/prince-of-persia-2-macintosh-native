import struct
import unittest

from tools.probe_temple_collision_banks import banks_reference
from tools.probe_temple_collision_history import TABLES
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import StandingCellReader


class TempleCollisionBanksTests(unittest.TestCase):
    def query(self, *, gates=(), pattern=0, previous=1, facing=0, velocity=1,
              mode=0, source=2, rocks=False, old_room=1, edges=(430, 475)):
        level = bytearray(0x49ca)
        for offset, value in ((0x2180, 1), (0x2186, 2), (0x218a, 10)):
            struct.pack_into('>H', level, offset, value)
        level[0x2191] = int(rocks)
        for cell in range(30):
            struct.pack_into('>H', level, cell * 2, 1)
        for column in gates:
            struct.pack_into('>H', level, (10 + column) * 2, 4)
        tables = {name: [old_room] * 10 if name.endswith('tags') else [pattern] * 10 for name in TABLES}
        actor = bytearray(actor_fixture(1, 1, 4, facing, mode))
        for offset, value in ((4, 460), (8, 0), (18, velocity), (28, -1), (30, 3),
                              (40, source), (52, 4)):
            put_actor(actor, offset, value)
        reader = StandingCellReader(level, 1)
        result = banks_reference(bytes(actor), edges, tables, reader, previous)
        return result, reader, tables

    def test_limits_history_three_rows_and_remainder_are_generated(self):
        result, reader, _ = self.query(previous=0)
        self.assertEqual([result[k] for k in ('first', 'last', 'current', 'previous', 'remainder')],
                         [1, 8, 1, 1, 47])
        self.assertEqual(result['anchor'], 688)
        self.assertEqual(len(reader.requests), 48)
        self.assertEqual([reader.requests[i][2] for i in (0, 16, 32)], [1, 2, 0])
        self.assertEqual(result['tables']['current_tags'], [65535] + [1] * 8 + [65535])

    def test_new_nibbles_are_detected_only_for_matching_non_sentinel_tags(self):
        result, _, _ = self.query(gates=(4,))
        self.assertEqual((result['hit_low'], result['hit_high']), (4, 4))
        result, _, _ = self.query(gates=(4,), old_room=2)
        self.assertEqual((result['hit_low'], result['hit_high']), (-1, -1))
        result, _, _ = self.query(gates=(4,), old_room=65535)
        self.assertEqual((result['hit_low'], result['hit_high']), (-1, -1))

    def test_descending_scan_leaves_the_smallest_qualifying_column(self):
        result, _, _ = self.query(gates=(3, 4))
        self.assertEqual((result['hit_low'], result['hit_high']), (3, 3))

    def test_row_change_nibble_adjustment_precedes_the_new_overlap_comparison(self):
        result, _, _ = self.query(gates=(4,), pattern=255)
        self.assertEqual((result['hit_low'], result['hit_high']), (-1, -1))
        result, _, _ = self.query(gates=(4,), pattern=255, previous=0)
        self.assertEqual((result['hit_low'], result['hit_high']), (4, -1))
        result, _, _ = self.query(gates=(4,), pattern=255, previous=0, velocity=-1)
        self.assertEqual((result['hit_low'], result['hit_high']), (-1, 4))

    def test_early_paths_clear_collision_flags_without_rebuilding_history(self):
        for kwargs in ({'mode': 7}, {'source': 70}, {'source': 78}):
            result, reader, tables = self.query(previous=0, **kwargs)
            self.assertEqual(result['tables'], tables)
            self.assertEqual((result['current'], result['previous'], result['first'], result['last']),
                             (71, 0, 7, 8))
            self.assertEqual((result['hit_low'], result['hit_high']), (-1, -1))
            self.assertEqual(reader.requests, [])

    def test_empty_rock_bank_does_not_turn_special4_into_a_collision(self):
        result, _, _ = self.query(rocks=True)
        self.assertEqual(result['rock_queries'], [(1, 1), (1, 1), (1, 2), (1, 0)])
        result, _, _ = self.query(mode=7, rocks=True)
        self.assertEqual(result['rock_queries'], [(1, 1)])
        result, _, _ = self.query(source=70, rocks=True)
        self.assertEqual(result['rock_queries'], [])

    def test_generated_empty_interval_clears_tags_but_does_not_read_cells(self):
        result, reader, _ = self.query(edges=(680, 260))
        self.assertEqual((result['first'], result['last']), (6, 4))
        self.assertEqual(result['tables']['current_tags'], [65535] * 10)
        self.assertEqual((result['hit_low'], result['hit_high']), (-1, -1))
        self.assertEqual(reader.requests, [])

    def test_far_offscreen_anchor_alias_is_outside_this_bounded_caller_model(self):
        with self.assertRaises(ValueError):
            self.query(edges=(22, 50))
