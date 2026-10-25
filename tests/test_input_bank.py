import unittest

from tools.reference_input_bank import InputBank


class InputBankTests(unittest.TestCase):
    def test_released_directions_remain_pending_until_consumed_or_cleared(self):
        bank = InputBank().sample(horizontal=-1)
        self.assertEqual(bank.sample(), InputBank(left=-1))
        self.assertEqual(bank.consume('left').sample(), InputBank())
        self.assertEqual(bank.clear_directions(), InputBank())

    def test_new_opposite_input_does_not_overwrite_an_old_pending_direction(self):
        bank = InputBank().sample(horizontal=-1).sample(horizontal=1)
        self.assertEqual(bank, InputBank(left=-1, right=-1))

    def test_modifier_release_cancels_a_pending_request(self):
        for modifier in (-1, -2):
            with self.subTest(modifier=modifier):
                self.assertEqual(InputBank().sample(modifier=modifier).sample(), InputBank())

    def test_clear_preserves_modifier_and_a_held_direction_rearms_after_reset(self):
        bank = InputBank(left=1, modifier=-2).clear_directions()
        self.assertEqual(bank, InputBank(modifier=-2))
        self.assertEqual(bank.sample(horizontal=-1, modifier=-2), InputBank(left=-1, modifier=-2))

    def test_consumed_held_modifier_does_not_repeat_but_switching_modifier_is_fresh(self):
        bank = InputBank().sample(modifier=-2).consume(modifier=2)
        self.assertEqual(bank.sample(modifier=-2).modifier, 2)
        self.assertEqual(bank.sample(modifier=-1).modifier, -1)

    def test_facing_restore_uses_the_old_facing_and_is_reversible(self):
        bank = InputBank(-1, 1, 0, -1, -2)
        for facing in (False, True):
            for inverted in (False, True):
                with self.subTest(facing=facing, inverted=inverted):
                    relative = bank.remap(facing_right=facing, inverted=inverted)
                    self.assertEqual(relative.remap(facing_right=facing, inverted=inverted), bank)


if __name__ == '__main__':
    unittest.main()
