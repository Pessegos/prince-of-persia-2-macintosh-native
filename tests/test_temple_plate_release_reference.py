"""Asset-free regressions for native plate lifetime and stable TROB removal."""

import struct
import unittest

from tests.test_temple_slide_rock_geometry_reference import level_fixture, tile
from tools.probe_temple_plate_release import animate_bank, animate_record, initial_state


def fixture(timer=5, records=((14, 1, 1, 6),), shared=False):
    level = level_fixture(11)
    for i, (cell, room, _phase, _kind) in enumerate(records):
        index = 240 if shared else 220 + i
        tile(level, room, cell % 10, cell // 10, 6)
        struct.pack_into('>2H', level, 0x780 + (room - 1) * 120 + cell * 4, 0xa000 | index, 0x5a00 + i)
        struct.pack_into('>h', level, 0x1680 + index * 10 + 4, timer)
    return initial_state(level, records)


def timer_of(state, index=220):
    return struct.unpack_from('>h', state['level'], 0x1680 + index * 10 + 4)[0]


def foreground(state, room=1, cell=14):
    return struct.unpack_from('>H', state['level'], 0x780 + (room - 1) * 120 + cell * 4)[0]


class TemplePlateReleaseTests(unittest.TestCase):
    def test_five_updates_release_refreshed_plate_on_old_timer_one(self):
        state = fixture()
        for expected in (4, 3, 2, 1):
            state = animate_bank(dict(state, events=[]))
            self.assertEqual(timer_of(state), expected)
            self.assertEqual(len(state['trobs']), 1)
            self.assertTrue(foreground(state) & 0x2000)
            self.assertFalse(any(event[0] == 'redraw' for event in state['events']))
        state = animate_bank(dict(state, events=[]))
        self.assertEqual((timer_of(state), state['trobs']), (0, ()))
        self.assertFalse(foreground(state) & 0x2000)

    def test_redraw_sees_updated_timer_but_old_depressed_foreground(self):
        state = fixture(timer=1)
        old_foreground = foreground(state)
        state = animate_bank(state)
        self.assertEqual(state['events'][-1], ('redraw', 1, 14, old_foreground, 0))
        self.assertEqual(foreground(state), old_foreground & ~0x2000)
        self.assertEqual(struct.unpack_from('>H', state['level'], 0x780 + 14 * 4 + 2)[0], 0x5a00)

    def test_permanent_and_larger_signed_timers_remove_record_without_lifting(self):
        for timer in (31, 32, 32767):
            state = fixture(timer)
            before = foreground(state)
            result = animate_bank(state)
            self.assertEqual((timer_of(result), result['trobs']), (timer, ()))
            self.assertEqual(foreground(result), before)
            self.assertFalse(any(event[0] == 'redraw' for event in result['events']))

    def test_negative_phase_skips_timer_and_lift_before_compaction(self):
        state = fixture(timer=1, records=((14, 1, -2, 6),))
        result = animate_bank(state)
        self.assertEqual((timer_of(result), result['trobs']), (1, ()))
        self.assertEqual(foreground(result), foreground(state))
        self.assertEqual(result['scratch'], (14, 1, -2, 6))

    def test_zero_and_negative_timers_lift_and_use_signed_word_wrap(self):
        for before, after in ((0, -1), (-1, -2), (-32768, 32767)):
            result = animate_bank(fixture(before))
            self.assertEqual(timer_of(result), after)
            self.assertEqual(result['trobs'], ())
            self.assertFalse(foreground(result) & 0x2000)

    def test_nonnegative_phase_is_preserved_while_timer_is_active(self):
        for phase in (0, 1, 9, 32767):
            result = animate_bank(fixture(5, ((14, 1, phase, 6),)))
            self.assertEqual(result['trobs'], ((14, 1, phase, 6),))

    def test_stored_kind_dispatch_is_independent_of_raw_tile_kind(self):
        for kind in (5, 6, 34):
            state = fixture(1, ((14, 1, 1, kind),))
            result = animate_bank(state)
            self.assertEqual((timer_of(result), result['trobs']), (0, ()))
            self.assertEqual(struct.unpack('>3H', result['os'])[2], 6)
        state = fixture(1, ((14, 1, 1, 1),))
        result = animate_bank(state)
        self.assertEqual((timer_of(result), result['trobs']), (1, ()))
        self.assertEqual(foreground(result), foreground(state))

    def test_survivors_keep_original_order_after_middle_and_end_removal(self):
        records = ((14, 1, 1, 6), (15, 1, -1, 5), (16, 1, 7, 34), (17, 1, -1, 6))
        result = animate_bank(fixture(5, records))
        self.assertEqual(result['trobs'], (records[0], records[2]))
        self.assertEqual([event[1] for event in result['events'] if event[0] == 'visit'], [0, 1, 2, 3])
        self.assertEqual(result['scratch'], records[-1])

    def test_compaction_retains_unused_bank_bytes_instead_of_zeroing_tail(self):
        records = ((14, 1, -1, 6), (15, 1, 1, 5), (16, 1, 1, 34))
        state = fixture(5, records)
        result = animate_bank(state)
        self.assertEqual(result['trob_storage'][24:], state['trob_storage'][24:])
        self.assertEqual(struct.unpack_from('>4h', result['trob_storage'], 16), records[-1])

    def test_empty_pass_retains_scratch_os_and_storage(self):
        state = fixture(records=())
        self.assertEqual(animate_bank(state), state)

    def test_shared_timer_is_decremented_per_record_in_visit_order(self):
        records = ((14, 1, 1, 6), (15, 1, 1, 5))
        state = fixture(2, records, shared=True)
        result = animate_bank(state)
        self.assertEqual(timer_of(result, 240), 0)
        self.assertEqual(result['trobs'], (records[0],))
        self.assertTrue(foreground(result, cell=14) & 0x2000)
        self.assertFalse(foreground(result, cell=15) & 0x2000)
        result = animate_bank(dict(result, events=[]))
        self.assertEqual((timer_of(result, 240), result['trobs']), (-1, ()))

    def test_direct_dispatch_does_not_write_back_or_compact_bank(self):
        state = fixture(1)
        result = animate_record(state['level'], state['trobs'][0], 7)
        self.assertEqual(result['scratch'], (14, 1, -1, 6))
        self.assertEqual(state['trobs'], ((14, 1, 1, 6),))
        self.assertEqual(result['events'][0], ('visit', 7, 14, 1, 1, 6))

    def test_out_of_scope_kind_and_capacity_fail_explicitly(self):
        state = fixture()
        with self.assertRaises(ValueError):
            animate_record(state['level'], (14, 1, 1, 4), 0)
        with self.assertRaises(ValueError):
            initial_state(state['level'], ((14, 1, 1, 6),) * 21)


if __name__ == '__main__':
    unittest.main()
