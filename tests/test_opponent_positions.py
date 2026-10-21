"""Asset-free persistent-NPC Cut limits, distinct from live follower cuts."""

from types import SimpleNamespace
import unittest

from pop2.opponent_generation import (
    cut_opponent_position, opponent_record_cell, opponent_record_in_bounds, opponent_row_cell,
)


class OpponentPositionTests(unittest.TestCase):
    def terrain(self, links):
        return SimpleNamespace(neighbor=lambda room, side: links.get((room, side)))

    def test_inside_record_preserves_all_fields(self):
        self.assertEqual(cut_opponent_position(None, 5, 1, 3, 200, 199),
                         (5, 1, 3, 200, 199))

    def test_saved_cell_domain_includes_only_one_row_above_the_screen(self):
        for row in range(-2, 5):
            for column in range(-1, 11):
                self.assertEqual(opponent_record_in_bounds(column, row),
                                 -1 <= row < 3 and 0 <= column < 10)

    def test_cell_and_row_offset_keep_distinct_negative_encodings(self):
        self.assertEqual([opponent_record_cell(col, -1) for col in range(10)],
                         list(range(-1, -11, -1)))
        self.assertEqual([opponent_row_cell(row) for row in range(-2, 4)],
                         [-11, -1, 0, 10, 20, 30])
        self.assertEqual(opponent_record_cell(9, 2), 29)
        self.assertEqual(opponent_record_cell(0, 3), 30)
        self.assertEqual(opponent_record_cell(-1, 1), 30)

    def test_horizontal_normalization_uses_supporting_column_not_anchor(self):
        for column, side, expected_x, expected_column in ((-1, 'left', 1010, 9),
                                                         (10, 'right', -10, 0)):
            with self.subTest(side=side):
                result = cut_opponent_position(self.terrain({(0, side): 1}), 0, 1, column, 500, 226)
                self.assertEqual(result, (1, 1, expected_column, expected_x, 226))

    def test_persistent_vertical_cut_uses365_not_live_followers360(self):
        for row, side, expected_row, expected_y in ((-1, 'up', 2, 345), (3, 'down', 0, 95)):
            with self.subTest(side=side):
                result = cut_opponent_position(self.terrain({(0, side): 1}),
                                               0, row, 3, 200, -20 if row < 0 else 460)
                self.assertEqual(result, (1, expected_row, 3, 200, expected_y))

    def test_corner_uses_vertical_link_before_horizontal(self):
        terrain = self.terrain({(0, 'up'): 1, (0, 'right'): 3, (1, 'right'): 2})
        self.assertEqual(cut_opponent_position(terrain, 0, -1, 10, 520, -20),
                         (2, 2, 0, 10, 345))

    def test_missing_vertical_link_retries_after_horizontal_cut(self):
        terrain = self.terrain({(0, 'right'): 1, (1, 'up'): 2})
        self.assertEqual(cut_opponent_position(terrain, 0, -1, 10, 520, -20),
                         (2, 2, 0, 10, 345))

    def test_missing_horizontal_link_cannot_be_replaced_by_old_room_link(self):
        terrain = self.terrain({(0, 'up'): 1, (0, 'right'): 2})
        self.assertIsNone(cut_opponent_position(terrain, 0, -1, 10, 520, -20))

    def test_repeated_cuts_keep_y_and_cached_row_in_lockstep(self):
        terrain = self.terrain({(0, 'down'): 1, (1, 'left'): 3, (3, 'down'): 2})
        self.assertEqual(cut_opponent_position(terrain, 0, 7, -1, -10, 920),
                         (2, 1, 9, 500, 190))

    def test_outside_without_a_link_or_map_has_no_persistent_room(self):
        for row, column in ((-1, 3), (3, 3), (1, -1), (1, 10), (-1, 10)):
            for terrain in (None, self.terrain({})):
                self.assertIsNone(cut_opponent_position(terrain, 0, row, column, 200, 106))


class SkeletonRecordFormatTests(unittest.TestCase):
    def test_encoded_cell_roundtrips_without_original_assets(self):
        from pop2.save_game import _pack, _unpack
        from pop2.skeleton import SkeletonRoomRecord

        for cell in (None, -10, -1, 0, 29):
            record = SkeletonRoomRecord(119, 1, 0, False, cell)
            self.assertEqual(_unpack(_pack(record), None, None), record)

    def test_older_records_without_encoded_cell_remain_readable(self):
        from pop2.save_game import _pack, _unpack
        from pop2.skeleton import SkeletonRoomRecord

        record = SkeletonRoomRecord(119, 1, 0, False)
        encoded = _pack(record)
        del encoded['fields']['cell']
        self.assertEqual(_unpack(encoded, None, None), record)

    def test_non_integer_cell_does_not_enter_a_snapshot(self):
        from pop2.save_game import SaveGameError, _pack, _unpack
        from pop2.skeleton import SkeletonRoomRecord

        for cell in ('0', True, 0.5):
            with self.assertRaises(SaveGameError):
                _unpack(_pack(SkeletonRoomRecord(119, 1, 0, False, cell)), None, None)


if __name__ == '__main__':
    unittest.main()
