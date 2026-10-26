import struct
import unittest

from tools.probe_temple_collision_sweep import sweep_reference
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import StandingCellReader


class TempleCollisionSweepTests(unittest.TestCase):
    def query(self, *, kind=4, foreground=0, first=4, last=4, row=1,
              edges=(473, 483), height=74, bars=0, left=None, actor_column=4):
        level = bytearray(0x218c)
        for offset, value in ((0x2180, 2), (0x2186, 2), (0x218a, 10),
                              (14 * 2, kind), (0x780 + 14 * 4, foreground)):
            struct.pack_into('>H', level, offset, value)
        if left is not None:
            struct.pack_into('>H', level, 0x2080, 2)
            struct.pack_into('>H', level, 60 + 19 * 2, left)
        actor = bytearray(actor_fixture(1, 1, actor_column, -1, 0))
        put_actor(actor, 8, 11)
        reader = StandingCellReader(level, 1)
        result = sweep_reference(bytes(actor), row, first, last, edges,
                                 list(range(10)), list(range(100, 110)), reader,
                                 height=height, bars=bars)
        return result, reader

    def test_low_and_high_nibbles_use_strict_opposite_edge_comparisons(self):
        for edges, expected in (((473, 483), 255), ((483, 500), 15),
                                ((450, 473), 240), ((483, 473), 0)):
            result, _ = self.query(edges=edges)
            self.assertEqual(result['masks'][4], expected)

    def test_only_visited_columns_change_and_anchor_advances_after_the_last_cell(self):
        result, reader = self.query()
        self.assertEqual(result['tags'], [0, 1, 2, 3, 1, 5, 6, 7, 8, 9])
        self.assertEqual(result['masks'], [100, 101, 102, 103, 255, 105, 106, 107, 108, 109])
        self.assertEqual(result['anchor'], 484)
        self.assertEqual(reader.requests, [(1, 4, 1), (1, 4, 1)])

    def test_open_gate_keeps_its_geometric_span_for_later_admission(self):
        self.assertEqual(self.query(foreground=184)[0]['masks'][4], 255)
        self.assertEqual(self.query(foreground=0)[0]['masks'][4], 255)

    def test_empty_span_still_initializes_anchor_without_reading_or_clearing_arrays(self):
        result, reader = self.query(first=5, last=4)
        self.assertEqual(result, dict(tags=list(range(10)), masks=list(range(100, 110)), anchor=484))
        self.assertEqual(reader.requests, [])

    def test_neighbor_read_writes_normalized_column_and_room_tag(self):
        result, _ = self.query(first=-1, last=-1, left=4, edges=(220, 230))
        self.assertEqual((result['tags'][9], result['masks'][9], result['anchor']), (2, 255, 229))

    def test_later_column_visit_overwrites_the_same_normalized_output_slot(self):
        result, _ = self.query(first=-1, last=9, left=4, edges=(220, 230))
        self.assertEqual(result['tags'][9], 1)

    def test_no_barrier_uses_real_sentinels_instead_of_forcing_zero_mask(self):
        result, _ = self.query(kind=1, edges=(-1, 1))
        self.assertEqual(result['masks'][4], 240)

    def test_crevice_height_and_bar_flag_change_the_raw_span(self):
        self.assertEqual(self.query(kind=7, edges=(430, 435), height=34)[0]['masks'][4], 255)
        self.assertEqual(self.query(kind=7, edges=(430, 435), height=35)[0]['masks'][4], 240)
        self.assertEqual(self.query(kind=2, edges=(410, 420), bars=0)[0]['masks'][4], 240)
        self.assertEqual(self.query(kind=2, edges=(410, 420), bars=1)[0]['masks'][4], 255)

    def test_sweep_does_not_replace_its_span_with_the_actor_supporting_column(self):
        self.assertEqual(self.query(actor_column=8)[0], self.query(actor_column=4)[0])
