import struct
import unittest

from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_soft_distance import soft_distance_reference
from tools.probe_temple_gate_standing import StandingCellReader


class TempleSoftDistanceTests(unittest.TestCase):
    def query(self, *, here=1, ahead=1, foreground=0, facing=-1, x=460,
              edges=(445, 475), metadata=(0, 0), height=74, bars=0,
              view=1, neighbors=(0,) * 6):
        level = bytearray(0x218c)
        for offset, value in ((0x2180, 1), (0x2186, 2), (0x218a, 10)):
            struct.pack_into('>H', level, offset, value)
        front = 3 if facing == -1 else 5
        for column, kind in ((4, here), (front, ahead)):
            struct.pack_into('>H', level, (10 + column) * 2, kind)
            struct.pack_into('>H', level, 0x780 + (10 + column) * 4, foreground)
        actor = bytearray(actor_fixture(1, 1, 4, facing, 0))
        for offset, value in ((4, x), (40, 9), (42, 20), (46, 94)):
            put_actor(actor, offset, value)
        reader = StandingCellReader(level, view)
        result = soft_distance_reference(bytes(actor), reader, edges, metadata, view, neighbors,
                                         height=height, bars=bars)
        return result, reader

    def test_clear_forward_floor_returns_the_safe_sentinel_without_computing_a_foot(self):
        result, reader = self.query()
        self.assertEqual(result, dict(distance=42, reason=2, anchor=73, remainder=79))
        self.assertEqual(reader.requests, [(1, 4, 1), (1, 3, 1)])

    def test_a_forward_gap_measures_the_supporting_foot_edge(self):
        for facing, expected in ((-1, 26), (0, 24)):
            result, _ = self.query(ahead=0, facing=facing)
            self.assertEqual((result['distance'], result['reason'], result['remainder']),
                             (expected, 0, 26))

    def test_current_barrier_wins_and_the_51_boundary_selects_the_sentinel(self):
        for left, distance, reason in ((500, 17, 1), (533, 50, 1), (534, 42, 2)):
            result, reader = self.query(here=4, edges=(left, left + 30))
            self.assertEqual((result['distance'], result['reason'], result['anchor']),
                             (distance, reason, 433))
            self.assertEqual(reader.requests, [(1, 4, 1)])

    def test_passable_gate_preserves_anchor_before_the_gap_measurement(self):
        result, _ = self.query(here=4, ahead=0, foreground=184)
        self.assertEqual(result, dict(distance=26, reason=0, anchor=73, remainder=26))

    def test_frame_low_six_bits_shift_the_foot_in_each_facing(self):
        self.assertEqual(self.query(ahead=0, metadata=(8, 0x7f))[0]['distance'], 30)
        self.assertEqual(self.query(ahead=0, metadata=(8, 0x7f), facing=0)[0]['distance'], 28)

    def test_forward_button_subtracts_one_but_zero_edge_uses_the_safe_sentinel(self):
        self.assertEqual(self.query(ahead=6)[0]['distance'], 25)
        self.assertEqual(self.query(ahead=6, x=434)[0],
                         dict(distance=42, reason=2, anchor=73, remainder=0))

    def test_lava_slope_depends_on_facing_and_current_vs_forward_cell(self):
        self.assertEqual(self.query(here=24)[0]['distance'], 9)
        self.assertEqual(self.query(ahead=24)[0]['distance'], 60)
        self.assertEqual(self.query(here=24, facing=0)[0]['reason'], 2)
        self.assertEqual(self.query(here=23, facing=0)[0]['distance'], -9)
        self.assertEqual(self.query(ahead=23, facing=0)[0],
                         dict(distance=42, reason=71, anchor=73, remainder=26))

    def test_small_crevice_barrier_uses_the_collision_height_fixture(self):
        self.assertEqual(self.query(here=7, height=34)[0]['distance'], 12)
        self.assertEqual(self.query(here=7, height=35)[0]['reason'], 2)

    def test_bar_state_changes_a_low_phase_type_two_barrier(self):
        self.assertEqual(self.query(here=2, edges=(500, 530))[0]['distance'], 17)
        self.assertEqual(self.query(here=2, edges=(500, 530), bars=1)[0]['reason'], 2)

    def test_signed_word_wrapping_precedes_column_division(self):
        self.assertEqual(self.query(ahead=0, x=-32768)[0]['remainder'], 0)
        self.assertEqual(self.query(ahead=0, x=32767)[0]['remainder'], 50)

    def test_extending_before_word_subtraction_preserves_the_original_edge_quirk(self):
        for x, remainder in ((22, 48), (23, 49), (24, 50), (25, 0), (-32746, -30)):
            self.assertEqual(self.query(ahead=0, x=x)[0]['remainder'], remainder)

    def test_soft_selector_uses_only_the_four_adjustroom_slots(self):
        for slot, anchor in enumerate((-77, -77, 433, 943, 943, 433)):
            neighbors = tuple(1 if i == slot else 0 for i in range(6))
            result, _ = self.query(here=4, edges=(500, 530), view=2, neighbors=neighbors)
            self.assertEqual(result['anchor'], anchor)
