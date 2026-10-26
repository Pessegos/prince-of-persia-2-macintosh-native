import struct
import unittest

from tools.probe_temple_floating_ceiling import ceiling_reference
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import StandingCellReader
from tools.probe_temple_slide_rock_update import actor_word


class TempleFloatingCeilingTests(unittest.TestCase):
    def query(self, *, tile=1, y=185, height=74, facing=0, row=1, available=True):
        level = bytearray(0x49ca)
        for offset, value in ((0x2180, 2), (0x2186, 2), (0x218a, 10)):
            struct.pack_into('>H', level, offset, value)
        if row == 0:
            struct.pack_into('>H', level, 0x2084, 2)
            cell, room = 24, 2
        else:
            cell, room = (row - 1) * 10 + 4, 1
        struct.pack_into('>H', level, (room - 1) * 60 + cell * 2, tile)
        actor = bytearray(actor_fixture(1, row, 4, facing, 4))
        for offset, value in ((4, 460), (6, y), (8, 0), (18, 5), (20, -4),
                              (28, -1), (30, 3), (36, 7), (38, 2), (40, 2)):
            put_actor(actor, offset, value)
        reader = StandingCellReader(level, 1)
        return ceiling_reference(bytes(actor), height, reader, available=available), reader, bytes(actor)

    def test_strict_head_boundary_does_not_query_at_or_below_the_ceiling(self):
        for y in (186, 187):
            result, reader, actor = self.query(y=y)
            self.assertEqual(result, dict(actor=actor, events=[]))
            self.assertEqual(reader.requests, [])
        self.assertEqual(self.query(y=185)[0]['events'], [('resource', 229)])

    def test_each_native_space_kind_permits_the_head_without_a_bump(self):
        for tile in (0, 9, 27, 47, 49):
            result, reader, actor = self.query(tile=tile)
            self.assertEqual(result, dict(actor=actor, events=[]))
            self.assertEqual(reader.requests, [(1, 4, 0)])

    def test_bump_moves_six_pixels_back_and_stops_horizontal_velocity(self):
        for facing, x in ((0, 454), (-1, 466)):
            result, _, _ = self.query(facing=facing)
            actor = result['actor']
            self.assertEqual((actor_word(actor, 4), actor_word(actor, 18)), (x, 0))
            self.assertEqual([actor_word(actor, o) for o in (36, 38, 40)], [0, 229, 229])

    def test_selection_does_not_animate_or_change_health_row_and_vertical_motion(self):
        result, _, actor = self.query()
        allowed = set(range(4, 6)) | set(range(18, 20)) | set(range(36, 42))
        self.assertTrue(all(a == b for i, (a, b) in enumerate(zip(actor, result['actor']))
                            if i not in allowed))

    def test_missing_sequence_preserves_clip_but_keeps_physical_backoff_and_stop(self):
        result, _, _ = self.query(available=False)
        actor = result['actor']
        self.assertEqual([actor_word(actor, o) for o in (4, 18, 36, 38, 40)], [454, 0, 7, 2, 2])
        self.assertEqual(result['events'], [('resource', 229)])

    def test_above_row_zero_uses_real_vertical_neighbor_traversal(self):
        result, reader, _ = self.query(row=0, y=65)
        self.assertEqual(result['events'], [('resource', 229)])
        self.assertEqual(reader.requests, [(1, 4, -1)])
        self.assertEqual(reader.cache[3:], (2, 4, 2))

    def test_word_subtraction_wraps_before_long_ceiling_comparison(self):
        result, reader, actor = self.query(y=-32760)
        self.assertEqual(result, dict(actor=actor, events=[]))
        self.assertEqual(reader.requests, [])

    def test_height_is_supplied_body_geometry_not_a_fixed_sprite_height(self):
        self.assertEqual(self.query(height=34, y=145)[0]['events'], [('resource', 229)])
        self.assertEqual(self.query(height=34, y=146)[0]['events'], [])
