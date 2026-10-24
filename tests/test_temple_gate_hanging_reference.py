import struct
import unittest

from tools.probe_temple_gate_hanging import (
    NativeGateHanging, actor_fixture, first_in_row, hanging_cue_reference, stop_actor_reference,
)


class TempleGateHangingTests(unittest.TestCase):
    def actor(self, room=3, row=1, column=2, facing=-1, action=2):
        return actor_fixture(room, row, column, facing, action)

    def test_closed_gate_selects47_resets_cursor_and_copies_complete_actor(self):
        actor = self.actor()
        result = stop_actor_reference(actor, 2, 0)
        expected = bytearray(actor)
        for offset, value in ((36, 0), (38, 47), (40, 47)):
            struct.pack_into('>h', expected, offset, value)
        self.assertEqual(result['prince'], expected)
        self.assertEqual(result['working'], expected)
        self.assertEqual(result['events'], [('sound', 0x112), ('load_kid',), ('jump_seq', 47),
                                            ('resource', 47), ('save_kid',)])

    def test_nonzero_stop_positions_cannot_start_sequence47(self):
        for position in (56, 255):
            result = stop_actor_reference(self.actor(), 2, position)
            self.assertEqual(result['events'], [('sound', 0x112), ('load_kid',)])

    def test_exact_facing_minus1_action2_and_above_cell_are_all_required(self):
        for actor in (self.actor(facing=0), self.actor(facing=1), self.actor(action=0),
                      self.actor(action=6), self.actor(column=1), self.actor(column=3)):
            result = stop_actor_reference(actor, 2, 0)
            self.assertNotIn(('jump_seq', 47), result['events'])

    def test_stop_helper_has_no_local_room_equality_check(self):
        for room in (0, 3, 19):
            self.assertIn(('jump_seq', 47), stop_actor_reference(self.actor(room=room), 2, 0)['events'])

    def test_missing_resource_preserves_sequence_fields_but_still_reaches_copyback(self):
        actor = self.actor()
        result = stop_actor_reference(actor, 2, 0, available=False)
        self.assertEqual(result['prince'], actor)
        self.assertIn(('jump_seq', 47), result['events'])
        self.assertEqual(result['events'][-1], ('save_kid',))

    def test_cue_accepts_both_hanging_actions_and_two_adjacent_lower_cells(self):
        for action in (2, 6):
            for column in (2, 3):
                self.assertEqual(hanging_cue_reference(self.actor(column=column, action=action, facing=0), 3, 2),
                                 [('audio', 29)])

    def test_cue_requires_matching_room_and_ignores_other_actions_or_cells(self):
        for actor in (self.actor(room=0), self.actor(action=0), self.actor(column=1), self.actor(column=4)):
            self.assertEqual(hanging_cue_reference(actor, 3, 2), [])

    def test_action_not_sequence_mode_controls_hanging_admission(self):
        actor = bytearray(self.actor())
        struct.pack_into('>h', actor, 52, 0)
        self.assertIn(('jump_seq', 47), stop_actor_reference(actor, 2, 0)['events'])
        struct.pack_into('>h', actor, 16, 0)
        struct.pack_into('>h', actor, 52, 2)
        self.assertNotIn(('jump_seq', 47), stop_actor_reference(actor, 2, 0)['events'])

    def test_negative_first_row_sentinel_is_not_minus10(self):
        self.assertEqual([first_in_row(row) for row in (-1, 0, 1, 2, 3)], [-1, 0, 10, 20, 30])

    def test_nonplayer_kind_and_uncovered_indexes_are_rejected(self):
        actor = bytearray(self.actor())
        struct.pack_into('>h', actor, 8, 1)
        for data, cell in ((actor, 2), (self.actor()[:-1], 2), (self.actor(), 30)):
            with self.assertRaises(ValueError):
                stop_actor_reference(data, cell, 0)
        with self.assertRaises(ValueError):
            first_in_row(4)

    def test_jumpseq_is_native_but_resource_existence_and_audio_are_supplied(self):
        self.assertNotIn((6, 0x0006), NativeGateHanging.SUPPLIED)
        self.assertIn((17, 0x330e), NativeGateHanging.SUPPLIED)
        self.assertIn((5, 0x4d84), NativeGateHanging.SUPPLIED)


if __name__ == '__main__':
    unittest.main()
