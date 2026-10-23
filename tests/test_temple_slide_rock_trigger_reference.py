"""Asset-free sliding-rock activation reference cases, not native execution."""

import unittest

from tools.probe_temple_slide_rock_trigger import trigger_reference


def rock(state=0, room=2, row=1, mark=0):
    return (17, 19, room, mark, state, 6, row, 23)


class TempleSlideRockTriggerTests(unittest.TestCase):
    def test_new_rock_uses_cell_anchor_and_type_six(self):
        result = trigger_reference(2, 14, 1, ())
        expected = (204, 236, 2, 0, -2, 6, 1, 204)
        self.assertEqual(result['scratch'], expected)
        self.assertEqual(result['bank'], (expected,))
        self.assertTrue(result['appended'])

    def test_other_how_values_do_not_create_a_missing_rock(self):
        for how in (-32768, -1, 0, 2, 3, 32767):
            result = trigger_reference(2, 14, how, ())
            self.assertEqual(result['bank'], ())
            self.assertIsNone(result['scratch'])

    def test_how_one_sets_nonnegative_nonterminal_states_to_minus_two(self):
        for state in (0, 1, 2, 99, 101, 32767):
            result = trigger_reference(2, 14, 1, (rock(state),))
            self.assertEqual(result['bank'], (rock(-2),))
            self.assertIsNone(result['scratch'])
            self.assertEqual(result['selected'], 0)

    def test_how_one_preserves_negative_states_and_terminal_hundred(self):
        for state in (-32768, -3, -2, -1, 100):
            bank = (rock(state),)
            self.assertEqual(trigger_reference(2, 14, 1, bank)['bank'], bank)

    def test_how_two_only_changes_minus_two_to_plus_two(self):
        for state in (-32768, -3, -2, -1, 0, 1, 2, 99, 100, 101, 32767):
            result = trigger_reference(2, 14, 2, (rock(state),))
            self.assertEqual(result['bank'], (rock(2 if state == -2 else state),))

    def test_row_lookup_ignores_x_and_chooses_first_live_matching_record(self):
        bank = (rock(7, room=3), rock(9, row=0), rock(11), rock(13))
        result = trigger_reference(2, 19, 1, bank)
        self.assertEqual(result['selected'], 2)
        self.assertEqual(result['bank'], (*bank[:2], rock(-2), bank[3]))
        self.assertFalse(result['appended'])

    def test_only_exact_deleted_mark_minus_one_is_excluded(self):
        for mark in (-2, 0, 1):
            result = trigger_reference(2, 14, 1, (rock(0, mark=mark),))
            self.assertEqual(result['selected'], 0)
            self.assertEqual(result['bank'], (rock(-2, mark=mark),))
        removed = (rock(mark=-1),)
        result = trigger_reference(2, 14, 1, removed)
        self.assertIsNone(result['selected'])
        self.assertEqual(result['bank'][0], removed[0])
        self.assertEqual(len(result['bank']), 2)

    def test_last_free_slot_is_used_and_full_bank_still_builds_scratch(self):
        filler = rock(room=3)
        result = trigger_reference(2, 14, 1, (filler,) * 29)
        self.assertEqual(len(result['bank']), 30)
        self.assertTrue(result['appended'])
        full = trigger_reference(2, 14, 1, (filler,) * 30)
        self.assertEqual(full['bank'], (filler,) * 30)
        self.assertIsNotNone(full['scratch'])
        self.assertFalse(full['appended'])

    def test_input_records_are_not_mutated(self):
        bank = [list(rock())]
        before = [record[:] for record in bank]
        trigger_reference(2, 14, 1, bank)
        self.assertEqual(bank, before)

    def test_invalid_domains_are_rejected(self):
        for room, cell, how, bank in ((0, 14, 1, ()), (33, 14, 1, ()),
                                      (2, -1, 1, ()), (2, 30, 1, ()),
                                      (2, 14, 32768, ()), (2, 14, 1, (rock(),) * 31),
                                      (2, 14, 1, ((1, 2),))):
            with self.assertRaises(ValueError):
                trigger_reference(room, cell, how, bank)


if __name__ == '__main__':
    unittest.main()
