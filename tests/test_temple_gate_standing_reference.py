import struct
import unittest

from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import COLD_CACHE, StandingCellReader, standing_reference
from tools.probe_temple_slide_rock_geometry import TempleCellReader


class TempleGateStandingTests(unittest.TestCase):
    def fixture(self, gates=(), *, facing=-1, x=442, column=4, row=1, room=1, number=10):
        level = bytearray(0x218c)
        struct.pack_into('>H', level, 0x2180, 32)
        struct.pack_into('>H', level, 0x2186, 2)
        struct.pack_into('>H', level, 0x218a, number)
        for gate_room, gate_col, position in gates:
            cell = 10 + gate_col
            struct.pack_into('>H', level, (gate_room - 1) * 60 + cell * 2, 4)
            struct.pack_into('>H', level, 0x780 + (gate_room - 1) * 120 + cell * 4, position)
        actor = bytearray(actor_fixture(room, row, column, facing, 2))
        put_actor(actor, 4, x)
        return bytes(actor), TempleCellReader(level, room)

    def query(self, *args, **kwargs):
        actor, reader = self.fixture(*args, **kwargs)
        return standing_reference(actor, reader), reader

    def test_position_zero_and184_do_not_block_this_predicate(self):
        for position, expected in ((0, 0), (1, 1), (183, 1), (184, 0), (255, 0), (0x8101, 1)):
            self.assertEqual(self.query(((1, 4, position),))[0], expected)

    def test_inclusive_band_and_facing_relative_anchor(self):
        for facing, left, right in ((-1, 442, 480), (0, 462, 500)):
            for x, expected in ((left - 1, 0), (left, 1), (right, 1), (right + 1, 0)):
                self.assertEqual(self.query(((1, 4, 1),), facing=facing, x=x)[0], expected)

    def test_current_gate_stops_lookup_even_when_fully_open(self):
        result, reader = self.query(((1, 4, 184), (1, 3, 1)), x=442)
        self.assertEqual(result, 0)
        self.assertEqual(reader.requests, [(1, 4, 1)])

    def test_lookup_tables_are_opposite_and_first_neighbor_wins(self):
        for facing, first, second in ((-1, 3, 5), (0, 5, 3)):
            result, reader = self.query(((1, first, 0), (1, second, 1)), facing=facing)
            self.assertEqual(result, 0)
            self.assertEqual(reader.requests, [(1, 4, 1), (1, first, 1)])

    def test_no_gate_reads_both_neighbors_and_retains_last_cache(self):
        result, reader = self.query()
        self.assertEqual(result, 0)
        self.assertEqual(reader.requests, [(1, 4, 1), (1, 3, 1), (1, 5, 1)])
        self.assertEqual(reader.cache, (0, 0, 15, 1, 5, 1))

    def test_cross_room_uses_normalized_gate_column_not_actor_column(self):
        actor, reader = self.fixture(((2, 9, 1),), column=0, x=9 * 51 + 238)
        struct.pack_into('>H', reader.level, 0x2080, 2)
        self.assertEqual(standing_reference(actor, reader), 1)
        self.assertEqual(reader.cache[3:], (2, 9, 1))

    def test_level8_room9_exemption_performs_no_reads(self):
        result, reader = self.query(((9, 4, 1),), room=9, number=8)
        self.assertEqual(result, 0)
        self.assertEqual(reader.requests, [])
        self.assertEqual(reader.cache, COLD_CACHE)
        self.assertEqual(self.query(((9, 4, 1),), room=9, number=10)[0], 1)

    def test_vertical_query_preserves_original_requested_row_in_trace(self):
        actor, reader = self.fixture(row=-1)
        self.assertEqual(standing_reference(actor, reader), 0)
        self.assertEqual(reader.requests, [(1, 4, -1), (1, 3, -1), (1, 5, -1)])
        self.assertEqual(reader.cache[3:], (0, 5, 2))

    def test_word_wrap_does_not_make_far_anchor_overlap_gate(self):
        for x in (-32768, 32767):
            self.assertEqual(self.query(((1, 4, 1),), x=x)[0], 0)

    def test_undefined_read_retains_last_valid_room_base(self):
        _actor, reader = self.fixture()
        reader = StandingCellReader(reader.level, 1)
        reader.read(1, 4, 1)
        self.assertEqual(reader.pointer_room, 1)
        reader.read(1, -1, 1)
        self.assertEqual(reader.cache[3], 0)
        self.assertEqual(reader.pointer_room, 1)

    def test_warm_read_keeps_same_logical_state(self):
        actor, reader = self.fixture(((1, 4, 1),))
        reader.read(1, 4, 1)
        reader.requests.clear()
        self.assertEqual(standing_reference(actor, reader), 1)
        self.assertEqual(reader.requests, [(1, 4, 1)])
        self.assertEqual(reader.cache, (4, 1, 14, 1, 4, 1))


if __name__ == '__main__':
    unittest.main()
