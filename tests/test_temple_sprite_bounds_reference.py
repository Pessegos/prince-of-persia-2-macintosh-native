import struct
import unittest

from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_slide_rock_update import actor_word
from tools.probe_temple_sprite_bounds import DEFAULT_RECT, bounds_reference, drawing_reference, row_reference


class TempleSpriteBoundsTests(unittest.TestCase):
    def actor(self, *, facing=-1, armed=0, pose=1, x=400, y=110):
        actor = bytearray(actor_fixture(3, 1, 2, facing, 2))
        for offset, value in ((4, x), (6, y), (10, pose), (26, armed), (54, 83)):
            put_actor(actor, offset, value)
        return bytes(actor)

    def metadata(self, *, shape=0, attachment_shape=1, length=10, attachment=1, dx=0, dy=0):
        return struct.pack('>9h', attachment, attachment_shape, length, 0, shape, 0, dx, dy, 0)

    def query(self, actor=None, metadata=None, **kwargs):
        actor = self.actor() if actor is None else actor
        metadata = self.metadata() if metadata is None else metadata
        drawing = drawing_reference(actor, metadata, bytes(20))
        return bounds_reference(actor, metadata, drawing, {0: (20, 40)}, (1, 2, 3, 4, 5, 6, 7),
                                (11, 13, 17, 19), 23, **kwargs)

    def test_collision_width_includes_one_but_visual_rectangle_does_not(self):
        result = self.query()
        self.assertEqual(result['bounds'], (71, 421, 400, 421, 400, 21, 40))
        self.assertEqual(struct.unpack_from('>4h', result['actor'], 42), (71, 193, 111, 213))
        self.assertEqual(result['cells'], (3, 4, 0, 0))
        self.assertEqual(result['remainder'], 9)

    def test_draw_point_uses_relative_frame_offsets_and_native_origin(self):
        for facing, x in ((-1, 186), (0, 200)):
            drawn = drawing_reference(self.actor(facing=facing), self.metadata(dx=7, dy=-20), bytes(20))
            self.assertEqual(struct.unpack('>5h', drawn[:10]), (facing, x, 90, 0, 2))
            self.assertEqual(struct.unpack_from('>h', drawn, 18)[0], 83)

    def test_sword_extension_changes_body_edges_but_not_visual_rectangle(self):
        for facing, expected in ((-1, (393, 421)), (0, (379, 407))):
            actor = self.actor(facing=facing, armed=1)
            result = self.query(actor)
            self.assertEqual((result['bounds'][2], result['bounds'][1]), expected)
            self.assertEqual(result['bounds'][5], 28)
            unarmed = self.query(self.actor(facing=facing))
            self.assertEqual(result['actor'][42:50], unarmed['actor'][42:50])

    def test_sword_requires_armed_exactly_one_and_nonzero_attachment(self):
        for armed, attachment, length in ((0, 1, 10), (2, 1, 10), (1, 0, 10), (1, 1, 2)):
            with self.subTest(armed=armed, attachment=attachment, length=length):
                self.assertEqual(self.query(self.actor(armed=armed),
                                           self.metadata(attachment=attachment, length=length))['bounds'][5], 21)

    def test_shape_failure_keeps_old_edges_but_resets_actor_rectangle(self):
        result = self.query(available=False)
        self.assertEqual(result['bounds'], (1, 2, 3, 4, 5, 6, 7))
        self.assertEqual(result['cells'], (11, 13, 17, 19))
        self.assertEqual(result['remainder'], 23)
        self.assertEqual(struct.unpack_from('>4h', result['actor'], 42), DEFAULT_RECT)
        self.assertEqual(result['services'], [('shape_size', 0)])

    def test_imageless_frame_never_calls_size_or_intersection_service(self):
        result = self.query(metadata=self.metadata(shape=-1))
        self.assertEqual(result['services'], [])
        self.assertEqual(result['bounds'], (1, 2, 3, 4, 5, 6, 7))

    def test_pose_zero_or_two_imageless_sources_keep_previous_drawing(self):
        drawing = bytes(range(20))
        for actor, metadata in ((self.actor(pose=0), self.metadata()),
                                (self.actor(), self.metadata(shape=-1, attachment_shape=-1))):
            self.assertEqual(drawing_reference(actor, metadata, drawing), drawing)

    def test_screen_intersection_does_not_clamp_collision_left_edge(self):
        result = self.query(self.actor(x=180))
        self.assertEqual(result['bounds'][2], 180)
        self.assertEqual(struct.unpack_from('>4h', result['actor'], 42), DEFAULT_RECT)
        # Partial overlap: drawing X-7 with width20 ends at13.
        result = self.query(self.actor(x=200), screen=(0, 0, 365, 510))
        self.assertEqual(struct.unpack_from('>4h', result['actor'], 42), (71, 0, 111, 13))

    def test_bottom_row_minus_one_is_special_three_and_top_row_is_not(self):
        result = self.query(self.actor(y=0))
        self.assertEqual(result['cells'][2:], (-1, 3))
        self.assertEqual(row_reference(5), -1)
        self.assertEqual(row_reference(6), 0)
        self.assertEqual(row_reference(-120), -2)

    def test_body_top_is_capped_at365_without_changing_actor_row_or_y(self):
        actor = self.actor(y=500)
        result = self.query(actor)
        self.assertEqual(result['bounds'][0], 365)
        self.assertEqual((actor_word(result['actor'], 6), actor_word(result['actor'], 14)), (500, 1))
        self.assertEqual(result['actor'][:42] + result['actor'][50:], actor[:42] + actor[50:])


if __name__ == '__main__':
    unittest.main()
