import struct
import unittest

from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_kid_frames import kid_frame_reference
from tools.probe_temple_slide_rock_update import actor_word


class TempleKidFrameTests(unittest.TestCase):
    def actor(self, *, pose=0, x=258, facing=-1):
        actor = bytearray(actor_fixture(3, 7, 123, facing, 2))
        for offset, value in ((4, x), (6, 777), (10, pose)):
            put_actor(actor, offset, value)
        return bytes(actor)

    def test_full_metadata_uses_frame_attachment_index(self):
        frames = struct.pack('>10h', 3, 1, 7, -28, 7, 4, 0, 11, 0, 77)
        attachments = bytes(range(16))
        result = kid_frame_reference(self.actor(), frames, attachments)
        self.assertEqual(result['metadata'], attachments[8:16] + frames[:10])
        self.assertEqual(actor_word(result['actor'], 12), 0)

    def test_frame_flags_use_only_low_six_bits_for_supporting_foot(self):
        base = struct.pack('>5h', 1, 0, 11, 0, 13)
        high = struct.pack('>5h', 1, 0, 11, 0, 0x7fcd)
        first = kid_frame_reference(self.actor(), base, bytes(8))
        second = kid_frame_reference(self.actor(), high, bytes(8))
        self.assertEqual(first['actor'], second['actor'])
        self.assertEqual(first['remainder'], second['remainder'])
        self.assertNotEqual(first['metadata'], second['metadata'])

    def test_facing_changes_the_supporting_column_at_a_boundary(self):
        frame = struct.pack('>5h', 1, 0, 20, 0, 0)
        left = kid_frame_reference(self.actor(x=258), frame, bytes(8))
        right = kid_frame_reference(self.actor(x=258, facing=0), frame, bytes(8))
        self.assertEqual((actor_word(left['actor'], 12), actor_word(right['actor'], 12)), (0, 0))
        left = kid_frame_reference(self.actor(x=280), frame, bytes(8))
        right = kid_frame_reference(self.actor(x=280, facing=0), frame, bytes(8))
        self.assertEqual((actor_word(left['actor'], 12), actor_word(right['actor'], 12)), (0, 1))

    def test_only_column_changes_not_row_y_health_or_sequence_fields(self):
        actor = self.actor()
        result = kid_frame_reference(actor, bytes(10), bytes(8))
        self.assertEqual(result['actor'][:12] + result['actor'][14:], actor[:12] + actor[14:])
        self.assertEqual((actor_word(result['actor'], 14), actor_word(result['actor'], 6)), (7, 777))

    def test_zero_to_three_low_word_wrap_is_not_python_floor_division(self):
        result = kid_frame_reference(self.actor(x=22, facing=0), bytes(10), bytes(8))
        self.assertEqual((actor_word(result['actor'], 12), result['remainder']), (1280, 48))

    def test_two_attachment_bindings_change_metadata_without_changing_foot(self):
        first = kid_frame_reference(self.actor(), bytes(10), bytes(8))
        second = kid_frame_reference(self.actor(), bytes(10), bytes(range(8)))
        self.assertEqual(first['actor'], second['actor'])
        self.assertNotEqual(first['metadata'], second['metadata'])

    def test_out_of_bank_pose_or_attachment_is_rejected(self):
        with self.assertRaises(ValueError):
            kid_frame_reference(self.actor(pose=1), bytes(10), bytes(8))
        with self.assertRaises(ValueError):
            kid_frame_reference(self.actor(), struct.pack('>5h', 1, 2, 0, 0, 0), bytes(8))

    def test_other_actor_kind_or_facing_is_not_silently_reused(self):
        actor = bytearray(self.actor())
        put_actor(actor, 8, 7)
        with self.assertRaises(ValueError):
            kid_frame_reference(actor, bytes(10), bytes(8))
        with self.assertRaises(ValueError):
            kid_frame_reference(self.actor(facing=1), bytes(10), bytes(8))


if __name__ == '__main__':
    unittest.main()
