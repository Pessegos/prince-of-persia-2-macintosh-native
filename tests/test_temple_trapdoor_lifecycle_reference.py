"""Reference orchestration tests, not native or complete game-frame proofs."""

import struct
import unittest

from tools.probe_temple_trapdoor_lifecycle import cycle_reference
from tools.probe_temple_trapdoor_presentation import view_for


MAPPING = (66, *([0] * 17))
FRAMES = ((51, 11, 8, 74, 49),)
CLIP = (-1000, -1000, 2000, 2000)


def active_level():
    data = bytearray(0x2000)
    struct.pack_into('>H', data, 0x780 + 120 + 14 * 4, 0x81)
    return data


def cycle(level, mobs, visible=False, pending=198):
    return cycle_reference(level, mobs, view_for(2, 'current'), visible, pending, MAPPING, FRAMES, CLIP)


class TrapDoorLifecycleReferenceTests(unittest.TestCase):
    def test_terminal_marks_deleted_then_next_update_compacts(self):
        initial = (204, 245, 2, 0, 0, 10, 1, 16)
        first = cycle(active_level(), [initial])
        self.assertEqual(first['mobs'][0][3], -1)
        self.assertEqual(first['mobs'][0][7], 17)
        second = cycle(first['level'], first['mobs'], pending=first['pending_cue'])
        self.assertEqual((second['mobs'], second['queries'], second['sounds']), ([], [], []))

    def test_shorter_initial_state_restores_in_six_supplied_cycles(self):
        mobs = [(204, 245, 2, 0, 0, 10, 1, 75)]
        level = active_level()
        for step in range(1, 7):
            result = cycle(level, mobs)
            level, mobs = result['level'], result['mobs']
            self.assertEqual(mobs[0][3], -1 if step == 6 else 0)
        self.assertEqual(mobs[0][7], 81)

    def test_visibility_does_not_change_restored_level_or_object(self):
        initial = (204, 245, 2, 0, 0, 10, 1, 16)
        visible, invisible = cycle(active_level(), [initial], True), cycle(active_level(), [initial], False)
        self.assertEqual((visible['level'], visible['mobs']), (invisible['level'], invisible['mobs']))
        self.assertEqual(struct.unpack_from('>H', invisible['level'], 60 + 14 * 2)[0], 26)

    def test_audio_and_pending_state_pass_between_the_two_phases(self):
        result = cycle(active_level(), [(204, 245, 2, 0, 0, 10, 1, 16)])
        self.assertEqual((result['queries'], result['resets'], result['sounds'], result['pending_cue']),
                         ([197], [198], [27], -1))

    def test_empty_bank_has_no_requests_or_level_changes(self):
        level = active_level()
        result = cycle(level, [])
        self.assertEqual((result['level'], result['mobs'], result['queries'], result['visibility']),
                         (level, [], [], []))

    def test_inputs_are_not_mutated(self):
        level, mobs = active_level(), [(204, 245, 2, 0, 0, 10, 1, 16)]
        before = bytes(level), list(mobs)
        cycle(level, mobs)
        self.assertEqual((level, mobs), before)


if __name__ == '__main__':
    unittest.main()
