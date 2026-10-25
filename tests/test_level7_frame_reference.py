"""Asset-free bounds and remapping checks for the special-actor research codec."""

import unittest

from tools.probe_level7_frames import head_frame_index


class HeadFrameReferenceTests(unittest.TestCase):
    def test_base_types_use_the_same_pose_offset(self):
        for actor in (7, 11):
            for pose in (149, 150, 181, 182, 289):
                self.assertEqual(head_frame_index(actor, pose), pose - 149)

    def test_type_eight_remap_ends_at_181_inclusive(self):
        self.assertEqual(head_frame_index(8, 149), 43)
        self.assertEqual(head_frame_index(8, 150), 44)
        self.assertEqual(head_frame_index(8, 181), 75)
        self.assertEqual(head_frame_index(8, 182), 33)
        self.assertEqual(head_frame_index(8, 289), 140)

    def test_other_families_and_out_of_domain_poses_are_rejected(self):
        for actor, pose in ((0, 150), (2, 150), (7, 148), (8, 290), (11, 150.0)):
            with self.subTest(actor=actor, pose=pose), self.assertRaises(ValueError):
                head_frame_index(actor, pose)


if __name__ == '__main__':
    unittest.main()
