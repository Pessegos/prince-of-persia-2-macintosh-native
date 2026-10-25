"""Asset-free idle-choice reference checks; no native executable dependency."""

import struct
import unittest

from tools.probe_level7_head_idle import idle_reference


FRAME = struct.pack('>5h', 0, 0, 10, 0, 3)


def state(**changes):
    return dict(dict(room=1, row=1, column=4, actor=7, facing=-1, x=458,
                     y=193, selected=130, body_top=18, body_bottom=50, pose=150,
                     sequence=170, cursor=9, remainder=45), **changes)


class HeadIdleReferenceTests(unittest.TestCase):
    def test_other_poses_do_not_draw_random_or_query_movement(self):
        for pose in (149, 159):
            initial = state(pose=pose)
            self.assertEqual(idle_reference(bytearray(0x4000), initial, FRAME, ()),
                             (initial, [], [], [], False))

    def test_two_horizontal_sequence_families(self):
        for direction, base in ((0, 131), (1, 134)):
            for variant in range(3):
                actual, draws, directions, requests, reload_frame = idle_reference(
                    bytearray(0x4000), state(), FRAME, (direction, variant))
                self.assertEqual((requests, directions, draws),
                                 ([base + variant], [direction], [(3, direction), (2, variant)]))
                self.assertEqual(actual['cursor'], 0)
                self.assertFalse(reload_frame)

    def test_vertical_choice_uses_a_second_binary_draw(self):
        for second, requested in ((0, 138), (1, 137)):
            _, draws, directions, requests, _ = idle_reference(
                bytearray(0x4000), state(), FRAME, (2, second))
            self.assertEqual((draws, directions, requests), ([(3, 2), (1, second)], [2 + second], [requested]))

    def test_three_continues_only_a_horizontal_family(self):
        for selected, direction, base in ((131, 0, 131), (133, 0, 131), (134, 1, 134), (136, 1, 134)):
            _, draws, directions, requests, _ = idle_reference(
                bytearray(0x4000), state(selected=selected), FRAME, (3, 1))
            self.assertEqual((draws, directions, requests), ([(3, 3), (2, 1)], [direction], [base + 1]))
        _, draws, directions, requests, _ = idle_reference(bytearray(0x4000), state(), FRAME, (3,))
        self.assertEqual((draws, directions, requests), ([(3, 3)], [], []))

    def test_blocked_direction_does_not_draw_a_variant(self):
        data = bytearray(0x4000)
        struct.pack_into('>H', data, (10 + 3) * 2, 20)
        actual, draws, directions, requests, _ = idle_reference(data, state(), FRAME, (0,))
        self.assertEqual((draws, directions, requests), ([(3, 0)], [0], []))
        self.assertEqual((actual['sequence'], actual['cursor']), (170, 9))
        self.assertNotEqual(actual['remainder'], 45)

    def test_successful_selection_keeps_the_original_normalization(self):
        actual, _, _, _, reload_frame = idle_reference(bytearray(0x4000), state(facing=0), FRAME, (0, 0))
        self.assertTrue(reload_frame)
        self.assertEqual((actual['facing'], actual['x']), (-1, 446))

    def test_supplied_random_draws_are_bounded_and_must_exist(self):
        for tape in ((), (4,), (2, 2), (0, 3)):
            with self.assertRaises(ValueError):
                idle_reference(bytearray(0x4000), state(), FRAME, tape)

    def test_inputs_remain_unchanged(self):
        initial = state()
        idle_reference(bytearray(0x4000), initial, FRAME, (0, 1))
        self.assertEqual(initial, state())


if __name__ == '__main__':
    unittest.main()
