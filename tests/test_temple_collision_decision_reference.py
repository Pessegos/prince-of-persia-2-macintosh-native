import struct
import unittest

from tools.probe_temple_collision_decision import decision_reference
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import StandingCellReader


class TempleCollisionDecisionTests(unittest.TestCase):
    def query(self, *, tile=4, foreground=0, facing=0, armed=0, kind=0, height=74,
              flags=(4, 4), mode=0, pose=15, row=1, tag=1, source=2, rocks=False,
              view=1, neighbors=(0,) * 6):
        level = bytearray(0x49ca)
        for offset, value in ((0x2180, 2), (0x2186, 2), (0x218a, 10)):
            struct.pack_into('>H', level, offset, value)
        level[0x2191] = int(rocks)
        normalized_row = row % 3
        cell = normalized_row * 10 + 4
        struct.pack_into('>H', level, (tag - 1) * 60 + cell * 2, tile)
        struct.pack_into('>H', level, 0x780 + (tag - 1) * 120 + cell * 4, foreground)
        actor = bytearray(actor_fixture(1, row, 4, facing, mode))
        for offset, value in ((8, kind), (10, pose), (26, armed), (40, source),
                              (42, 20), (46, 20 + height)):
            put_actor(actor, offset, value)
        reader = StandingCellReader(level, view)
        result = decision_reference(bytes(actor), (430, 475), [tag] * 10, *flags, reader,
                                    height=height, neighbors=neighbors)
        return result, reader

    def test_low_candidate_has_priority_and_does_not_retry_the_high_candidate(self):
        self.assertEqual(self.query()[0]['events'], [('collide', -2, -1)])
        result, reader = self.query(facing=-1)
        self.assertEqual(result['events'], [])
        self.assertEqual(reader.requests, [])
        self.assertEqual(self.query(facing=-1, flags=(-1, 4))[0]['events'], [('collide', 53, 0)])

    def test_only_armed_value_one_enables_the_rear_side(self):
        self.assertEqual(self.query(facing=-1, armed=1)[0]['events'], [('collide', -2, -1)])
        self.assertEqual(self.query(facing=-1, armed=2)[0]['events'], [])

    def test_hanging_modes_and_unsigned_pose135_to144_bypass_cell_queries(self):
        for kwargs in ({'mode': 2}, {'mode': 6}, {'pose': 135}, {'pose': 144}):
            result, reader = self.query(**kwargs)
            self.assertEqual(result, dict(events=[], rock_queries=[], anchor=73))
            self.assertEqual(reader.requests, [])
        for pose in (134, 145, -1):
            self.assertTrue(self.query(pose=pose)[0]['events'])

    def test_no_candidate_does_not_query_or_change_anchor(self):
        result, reader = self.query(flags=(-1, -1))
        self.assertEqual((result['events'], result['anchor'], reader.requests), ([], 73, []))

    def test_open_gate_and_source68_preserve_anchor_and_do_not_retry(self):
        for kwargs in ({'foreground': 184}, {'source': 68}):
            result, reader = self.query(**kwargs)
            self.assertEqual((result['events'], result['anchor']), ([], 73))
            self.assertEqual(reader.requests, [(1, 4, 1)])

    def test_serpent_is_exempt_even_when_the_tile_predicate_blocks(self):
        result, reader = self.query(tile=20, kind=11)
        self.assertEqual((result['events'], result['anchor']), ([], 73))
        self.assertEqual(reader.requests, [(1, 4, 1)])

    def test_crevice_height_phase_and_actor_kind_are_separate_admission_rules(self):
        self.assertEqual(self.query(tile=7, height=34)[0]['events'], [])
        for kwargs in ({'height': 35}, {'height': 34, 'foreground': 3}, {'height': 34, 'kind': 7}):
            self.assertTrue(self.query(tile=7, **kwargs)[0]['events'])

    def test_scythe_requires_tall_body_and_low_five_bit_phase3_to15(self):
        for phase in (2, 16, 31):
            self.assertEqual(self.query(tile=12, foreground=phase)[0]['events'], [])
        for phase in (3, 15, 0x8103):
            self.assertTrue(self.query(tile=12, foreground=phase)[0]['events'])
        for kwargs in ({'height': 48}, {'kind': 1}, {'kind': 7}, {'kind': 8}, {'kind': 11}):
            self.assertEqual(self.query(tile=12, foreground=3, **kwargs)[0]['events'], [])

    def test_candidate_tag_supplies_room_and_physical_row_is_folded_once(self):
        for row, normalized in ((-1, 2), (3, 0)):
            _, reader = self.query(row=row, tag=2)
            self.assertEqual(reader.requests, [(2, 4, normalized), (2, 4, normalized)])

    def test_only_read_neighbor_slots_shift_the_anchor(self):
        for slot, anchor in enumerate((-77, -77, 433, 943, 943, 433)):
            neighbors = tuple(2 if i == slot else 0 for i in range(6))
            self.assertEqual(self.query(tag=2, neighbors=neighbors)[0]['anchor'], anchor)

    def test_empty_rock_fallback_is_queried_only_for_sentinel_span_edges(self):
        result, _ = self.query(tile=1, rocks=True)
        self.assertEqual(result['events'], [('collide', 446, -1)])
        self.assertEqual(result['rock_queries'], [(1, 1)])
        self.assertEqual(self.query(rocks=True)[0]['rock_queries'], [])

    def test_tile10_rejects_without_span_geometry(self):
        result, reader = self.query(tile=10)
        self.assertEqual((result['events'], result['anchor']), ([], 73))
        self.assertEqual(reader.requests, [(1, 4, 1)])
