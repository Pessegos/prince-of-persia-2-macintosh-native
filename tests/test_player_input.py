"""Saved player-bank and raw-control gating rules recovered from 4:3cae."""

import unittest

from tools.reference_input_bank import InputBank
from tools.reference_player_input import player_input_tick


class PlayerInputTests(unittest.TestCase):
    def test_raw_direction_gate_prevents_new_input_without_clearing_old_pending_input(self):
        result = player_input_tick(InputBank(up=-1), (1, 0, -2), 20, gate_matches=False)
        self.assertEqual(result.action.bank, InputBank(up=-1, modifier=-2))

    def test_room_zero_and_sequence_59_also_gate_raw_directions(self):
        for context in ({'room': 0}, {'sequence': 59}, {'gate_matches': False}):
            result = player_input_tick(InputBank(), (-1, -1, -1), 20, **context)
            self.assertEqual(result.action.bank, InputBank(modifier=-1))
        allowed = player_input_tick(InputBank(), (-1, -1, -1), 20)
        self.assertEqual(allowed.action.bank, InputBank(left=-1, up=-1, modifier=-1))

    def test_releasing_modifier_cancels_it_even_when_raw_directions_are_gated(self):
        result = player_input_tick(InputBank(up=-1, modifier=-2), (0, 0, 0), 20,
                                   gate_matches=False)
        self.assertEqual(result.action.bank, InputBank(up=-1))

    def test_pending_direction_can_still_be_accepted_while_new_raw_input_is_gated(self):
        result = player_input_tick(InputBank(left=-1), (0, 0, 0), 50,
                                   facing_right=False, gate_matches=False)
        self.assertEqual((result.action.sequence, result.action.bank), (1, InputBank(left=1)))

    def test_auxiliary_countdown_is_not_a_pending_command_expiry(self):
        bank = InputBank(up=-1)
        for before, after in ((0, 0), (1, 0), (-1, -2), (-32768, 32767), (32767, 32766)):
            result = player_input_tick(bank, (0, 0, 0), 20, countdown=before)
            self.assertEqual((result.action.bank, result.countdown), (bank, after))

    def test_mode_reset_still_discards_pending_directions_after_the_raw_gate(self):
        result = player_input_tick(InputBank(up=-1), (0, -1, -1), 110,
                                   mode=5, gate_matches=False)
        self.assertEqual(result.action.bank, InputBank(modifier=-1))

    def test_consumed_saved_output_does_not_repeat_when_the_direction_is_released(self):
        first = player_input_tick(InputBank(left=-1), (0, 0, 0), 50, facing_right=False)
        second = player_input_tick(first.action.bank, (0, 0, 0), 50, facing_right=False)
        self.assertEqual((first.action.sequence, second.action.sequence), (1, None))
        self.assertEqual(second.action.bank, InputBank())

    def test_recording_endpoint_result_is_returned_as_a_word_without_reclassifying_input(self):
        bank = InputBank(up=-1)
        result = player_input_tick(bank, (0, 0, 0), 20, record_status=0xbeef)
        self.assertEqual((result.record_status, result.action.bank), (0xbeef, bank))


if __name__ == '__main__':
    unittest.main()
