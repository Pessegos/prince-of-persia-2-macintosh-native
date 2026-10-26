import struct
import unittest

from tools.probe_temple_ground_collision import ResponseBoundary, collision_reference
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import StandingCellReader
from tools.probe_temple_slide_rock_update import actor_word


class TempleGroundCollisionTests(unittest.TestCase):
    def query(self, *, tile=4, neighbor=0, side=-1, source=2, y=196, alive=-1,
              hp=3, pose=15, armed=0, delta=-2, facing=0, mode=0, floating=False):
        level = bytearray(0x49ca)
        for offset, value in ((0x2180, 1), (0x2186, 2), (0x218a, 10)):
            struct.pack_into('>H', level, offset, value)
        struct.pack_into('>H', level, 14 * 2, tile)
        for cell in (12, 13, 15, 16):
            struct.pack_into('>H', level, cell * 2, neighbor)
        actor = bytearray(actor_fixture(1, 1, 4, facing, mode))
        for offset, value in ((4, 460), (6, y), (10, pose), (18, 5), (26, armed),
                              (28, alive), (30, hp), (36, 0), (38, 2), (40, source)):
            put_actor(actor, offset, value)
        sequences = {2: (-7, 0, 15), 45: (-7, 5, -6, 5, -10, 229, 102), 229: (102,)}
        frames = struct.pack('>5h', 1, 0, 0, 0, 0) * 352
        reader = StandingCellReader(level, 1)
        reader.read(1, 4, 1)
        reader.requests.clear()
        result = collision_reference(bytes(actor), delta, side, reader, sequences,
                                      frames, bytes(8), floating=floating)
        return result, reader, bytes(actor)

    def test_correction_is_absolute_then_ground_backoff_is_relative_to_facing(self):
        self.assertEqual(actor_word(self.query()[0]['actor'], 4), 448)
        self.assertEqual(actor_word(self.query(facing=-1)[0]['actor'], 4), 468)

    def test_unarmed_air_entry_chooses_ground_bump_at_exactly30_pixels(self):
        result, _, _ = self.query(y=196)
        self.assertEqual(result['events'][:2], [('air_entry',), ('ground',)])
        with self.assertRaises(ResponseBoundary):
            self.query(y=197)

    def test_armed_air_response_is_an_explicit_unrecovered_boundary(self):
        with self.assertRaises(ResponseBoundary):
            self.query(armed=1)

    def test_space_neighbor_uses_empty_rock_test_then_ground_without_air_entry(self):
        result, reader, _ = self.query(tile=20, y=226)
        self.assertEqual(result['events'][0], ('ground',))
        self.assertNotIn(('air_entry',), result['events'])
        self.assertEqual(result['rock_queries'], [(1, 1)])
        self.assertEqual(reader.requests, [(1, 3, 1)])

    def test_wall_neighbor_probe_uses_side_and_selected_source75_stride(self):
        for side, source, column in ((-1, 2, 3), (0, 2, 5), (-1, 75, 2), (0, 75, 6)):
            _, reader, _ = self.query(tile=20, side=side, source=source)
            self.assertEqual(reader.requests, [(1, column, 1)])

    def test_alive_and_pose_exclusions_preserve_even_the_correction(self):
        for kwargs in ({'alive': 0}, {'pose': 242}, {'pose': 243}):
            result, reader, actor = self.query(tile=20, **kwargs)
            self.assertEqual(result['actor'], actor)
            self.assertEqual(result['events'], [])
            self.assertEqual((result['mark'], result['remainder']), (73, 79))
            self.assertEqual(reader.requests, [])

    def test_hp_zero_is_distinct_from_native_alive_exclusion(self):
        self.assertIn(('ground',), self.query(hp=0)[0]['events'])

    def test_still_wall_spacing_is_an_explicit_boundary(self):
        with self.assertRaises(ResponseBoundary):
            self.query(tile=20, neighbor=20)

    def test_delta_wraps_as_word_before_relative_backoff_and_frame_reload(self):
        self.assertEqual(actor_word(self.query(delta=32767)[0]['actor'], 4), -32319)

    def test_float_source_and_active_clip_remain_distinct_through_full_response(self):
        result, _, _ = self.query(floating=True)
        self.assertEqual([actor_word(result['actor'], o) for o in (38, 40)], [229, 45])
