"""Recovered dispatch and modifier semantics, independent of local assets."""

import unittest

from pop2.mac_input import sample_modifier
from tools.reference_input_bank import InputBank
from tools.reference_input_routes import sampled_route, unarmed_route


class InputRouteTests(unittest.TestCase):
    def test_runtime_modifier_matches_the_recovered_bank_for_every_modifier_state(self):
        for previous in (-2, -1, 0, 1, 2):
            for shift in (False, True):
                for ctrl in (False, True):
                    raw = -1 if shift else (-2 if ctrl else 0)
                    self.assertEqual(sample_modifier(previous, shift, ctrl),
                                     InputBank(modifier=previous).sample(modifier=raw).modifier)

    def test_ctrl_does_not_change_running_or_override_fresh_down(self):
        for modifier in (-2, -1, 0, 1, 2):
            for pose in range(4, 15):
                bank = InputBank(left=1, modifier=modifier)
                self.assertEqual(unarmed_route(bank, pose), (bank, ()))
                bank = InputBank(left=1, down=-1, modifier=modifier)
                result, events = unarmed_route(bank, pose)
                self.assertEqual((result, events),
                                 (InputBank(down=1, modifier=modifier), (('sequence', 26),)))

    def test_only_released_horizontal_brakes_on_supporting_poses(self):
        for pose in range(4, 15):
            result, events = unarmed_route(InputBank(modifier=-2), pose)
            self.assertEqual(events, (('sequence', 13),) if pose in (7, 11) else ())
            self.assertEqual(result.modifier, -2)

    def test_standing_draw_requires_fresh_ctrl_all_directions_zero_and_a_sword(self):
        for pose in (15, 50, 51, 52):
            bank, events = unarmed_route(InputBank(modifier=-2), pose)
            self.assertEqual((bank, events), (InputBank(modifier=2), (('draw',), ('target',))))
            for field in ('left', 'right', 'up', 'down'):
                for value in (-1, 1):
                    _, events = unarmed_route(InputBank(**{field: value}, modifier=-2), pose)
                    self.assertNotIn(('draw',), events)
            for modifier in (-1, 0, 1, 2):
                self.assertNotIn(('draw',), unarmed_route(InputBank(modifier=modifier), pose)[1])
            self.assertNotIn(('draw',), unarmed_route(InputBank(modifier=-2), pose, sword=-1)[1])

    def test_reset_discards_directions_but_preserves_the_modifier(self):
        for pose in (26, 44):
            bank = InputBank(-1, -1, -1, -1, -2)
            self.assertEqual(unarmed_route(bank, pose), (InputBank(modifier=-2), ()))
        for mode in (4, 5, 9):
            self.assertEqual(unarmed_route(InputBank(up=-1, modifier=-2), 15, mode=mode),
                             (InputBank(modifier=-2), ()))

    def test_running_priorities_keep_active_backward_and_consumed_up_distinct(self):
        bank, events = unarmed_route(InputBank(left=-1, right=1, up=-1, down=-1), 8)
        self.assertEqual((bank, events), (InputBank(right=1), (('sequence', 6),)))
        bank, events = unarmed_route(InputBank(left=-1, up=1, down=-1), 8)
        self.assertEqual((bank, events), (InputBank(left=1, up=1, down=-1), ()))

    def test_released_ctrl_does_not_survive_braking_but_held_ctrl_can_draw(self):
        for facing in (False, True):
            direction = 1 if facing else -1
            for held in (False, True):
                bank = InputBank(right=1) if facing else InputBank(left=1)
                bank, events = sampled_route(bank, (direction, 0, -2), 8, facing_right=facing)
                self.assertEqual(events, ())
                bank, events = sampled_route(bank, (0, 0, -2 if held else 0), 11, facing_right=facing)
                self.assertEqual(events, (('sequence', 13),))
                bank, events = sampled_route(bank, (0, 0, -2 if held else 0), 50, facing_right=facing)
                self.assertEqual(events, (('draw',), ('target',)) if held else ())
                bank, events = sampled_route(bank, (0, 0, -2 if held else 0), 15, facing_right=facing)
                self.assertEqual(events, ())


if __name__ == '__main__':
    unittest.main()
