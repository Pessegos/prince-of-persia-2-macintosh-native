"""Synthetic boundary checks for head routing, not the leaf AI implementations."""

import unittest

from tools.probe_level7_head_routing import head_route


class HeadRouteReferenceTests(unittest.TestCase):
    def test_idle_activation_uses_specific_poses_and_nonnegative_visibility(self):
        for pose in (150, 159, 165, 166, 173):
            for visibility in (0, 4):
                self.assertEqual(head_route(0, 1, 5, 15, pose, visibility), 'angry')
            self.assertEqual(head_route(0, 1, 5, 15, pose, -1), 'idle')
        for pose in (149, 164, 167):
            self.assertEqual(head_route(0, 1, 5, 15, pose, 4), 'idle')

    def test_target_sequence_70_pose_gate_has_exact_threshold(self):
        for pose in (0, 223, 250):
            self.assertEqual(head_route(1, 1, 70, pose, 150, 4), 'done')
        self.assertEqual(head_route(1, 1, 70, 222, 150, 4), 'attack')
        self.assertEqual(head_route(1, 1, 5, 250, 150, 4), 'attack')

    def test_attack_and_locked_modes_share_target_admission(self):
        for mode, action in ((1, 'attack'), (3, 'locked')):
            self.assertEqual(head_route(mode, 1, 5, 15, 150, -1), action)
            self.assertEqual(head_route(mode, 0, 5, 15, 150, 4), 'done')

    def test_flee_mode_does_not_require_a_target(self):
        self.assertEqual(head_route(2, 0, 70, 0, 149, -1), 'flee')

    def test_unknown_mode_has_no_leaf_request(self):
        for mode in (-1, 4):
            self.assertIsNone(head_route(mode, 1, 5, 15, 150, 4))

    def test_native_alive_and_missing_record_reject_entire_wrapper(self):
        for alive in (0, 1, 20):
            self.assertIsNone(head_route(0, 1, 5, 15, 150, 4, native_alive=alive))
        self.assertIsNone(head_route(0, 1, 5, 15, 150, 4, record_present=False))


if __name__ == '__main__':
    unittest.main()
