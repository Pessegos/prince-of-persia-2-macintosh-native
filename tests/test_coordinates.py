import struct
import unittest


class CoordinateConversionTests(unittest.TestCase):
    def test_actor_x_keeps_the_original_207_pixel_origin(self):
        from pop2.coordinates import column_left, native_x, scene_x

        for x in (-300, -207, -1, 0, 1, 509, 510, 1020):
            self.assertEqual(scene_x(native_x(x)), x)
        self.assertEqual((native_x(0), scene_x(374), scene_x(0)), (207, 167, -207))
        # a5-0x4b88 holds 207 + 51 * column, including negative columns.
        self.assertEqual([column_left(column) for column in (-1, 0, 1, 9, 10)], [-51, 0, 51, 459, 510])

    def test_rooms_are_one_based_natively_and_zero_means_none(self):
        from pop2.coordinates import native_room, port_room

        self.assertEqual([native_room(room) for room in (0, 31)], [1, 32])
        self.assertEqual([port_room(room) for room in (1, 32)], [0, 31])
        self.assertIsNone(port_room(0))

    def test_actor_columns_keep_the_signed_division_at_their_edges(self):
        # CODE:4 3ad6 -> 5:48b0 extends before the word subtraction.
        # Scene X-185 is raw argument0: its dividend is65532, not-4.
        from pop2.opponent_generation import character_column

        self.assertEqual([character_column(x) for x in (22, 23, 73, 74, 0, -1, -181, -185, -186)],
                         [-1, 0, 0, 1, -1, -1, -4, 1280, -5])

    def test_mixed_word_long_subtraction_keeps_offscreen_column_and_edge_in_sync(self):
        from pop2.coordinates import character_column_parts
        from pop2.ruins_ai import column_remainder
        from pop2.terrain import floor_edge_distance

        for x, column, remainder in ((-185, 1280, 48), (-184, 1280, 49),
                                     (-183, 1280, 50), (-182, 1281, 0), (-181, -4, 0)):
            self.assertEqual(character_column_parts(x), (column, remainder))
            self.assertEqual(column_remainder(x), remainder)
            self.assertEqual(floor_edge_distance(x, 0), remainder)
            self.assertEqual(floor_edge_distance(x, 1), 50 - remainder)

    def test_native_x_word_wrap_precedes_the_division(self):
        from pop2.coordinates import character_column_parts

        self.assertEqual(character_column_parts(-32768 - 207), (638, 0))
        self.assertEqual(character_column_parts(-32746 - 207), (-647, -30))

    def test_level_checkpoints_use_port_rooms(self):
        from pop2.rebirth import level_checkpoints

        level = bytearray(0x39ae)
        struct.pack_into('>4h', level, 0x39a6, 1, 20, 32, 0)
        self.assertEqual([(point.slot, point.room, point.tile) for point in level_checkpoints(bytes(level))],
                         [(1, 0, 20), (2, 31, 0)])


if __name__ == '__main__':
    unittest.main()
