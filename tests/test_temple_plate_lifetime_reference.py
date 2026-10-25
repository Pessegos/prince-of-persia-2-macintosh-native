"""Connected pressure/release regressions with persistent mechanism banks."""

import struct
import unittest

from tests.test_temple_mixed_plate_links_reference import state as mechanism_state
from tests.test_temple_slide_rock_admission_reference import link
from tests.test_temple_slide_rock_geometry_reference import level_fixture, tile
from tools.probe_temple_plate_lifetime import lifetime_step
from tools.probe_temple_slide_rock_geometry import TempleCellReader


ROCK = (459, 356, 1, 0, -2, 6, 2, 459)
CONTEXT = (0, -1, 1, 0)


def fixture(timer=0, trobs=(), bank=()):
    level = level_fixture(11)
    tile(level, 1, 3, 2, 6)
    tile(level, 1, 9, 2, 25)
    struct.pack_into('>H', level, 0x780 + 23 * 4, 4)
    link(level, 4, 1, 29, timer=timer)
    state = dict(mechanism_state(bank, trobs), os=bytes((11, 13, 17, 19, 23, 29)), press_flag=4321)
    return state, TempleCellReader(level, 1)


def step(state, reader, operation):
    reader.requests.clear()
    return lifetime_step(dict(state, events=[], object_calls=[], rock_calls=[]), reader, operation, CONTEXT, 1, 23)


def timer(reader):
    return struct.unpack_from('>h', reader.level, 0x1680 + 4 * 10 + 4)[0]


def depressed(reader):
    return bool(struct.unpack_from('>H', reader.level, 0x780 + 23 * 4)[0] & 0x2000)


class TemplePlateLifetimeTests(unittest.TestCase):
    def test_release_then_repress_reuses_rock_and_reregisters_plate(self):
        state, reader = fixture()
        state = step(state, reader, 'press')
        self.assertEqual((state['bank'], state['trobs']), ((ROCK,), ((23, 1, 1, 6),)))
        for _ in range(5):
            state = step(state, reader, 'animate')
        self.assertEqual((timer(reader), state['trobs'], depressed(reader)), (0, (), False))
        self.assertEqual(state['bank'], (ROCK,))
        state = step(state, reader, 'press')
        self.assertEqual((timer(reader), len(state['trobs']), state['bank']), (5, 1, (ROCK,)))
        self.assertEqual(sum(event[0] == 'sound' for event in state['events']), 1)

    def test_held_refresh_keeps_timer_four_after_each_pressure_then_animation(self):
        state, reader = fixture()
        for i in range(8):
            state = step(state, reader, 'press')
            self.assertEqual(any(event[0] == 'sound' for event in state['events']), i == 0)
            state = step(state, reader, 'animate')
            self.assertEqual((timer(reader), len(state['trobs']), depressed(reader)), (4, 1, True))
        for _ in range(4):
            state = step(state, reader, 'animate')
        self.assertEqual((state['trobs'], timer(reader), depressed(reader)), ((), 0, False))

    def test_supplied_operation_order_changes_timer_without_claiming_frame_order(self):
        outcomes = []
        for operations in (('press', 'animate'), ('animate', 'press')):
            state, reader = fixture()
            for operation in operations:
                state = step(state, reader, operation)
            outcomes.append(timer(reader))
        self.assertEqual(outcomes, [4, 5])

    def test_capacity_rejection_can_leave_timer_without_registered_plate(self):
        defaults = ((9, 2, 1, 1),) * 20
        state, reader = fixture(trobs=defaults)
        state = step(state, reader, 'press')
        self.assertEqual((len(state['trobs']), timer(reader), state['bank']), (20, 5, (ROCK,)))
        state = step(state, reader, 'animate')
        self.assertEqual(state['trobs'], ())
        state = step(state, reader, 'press')
        self.assertEqual(state['trobs'], ())
        self.assertFalse(any(event[0] == 'sound' for event in state['events']))
        for _ in range(8):
            state = step(state, reader, 'animate')
        self.assertEqual((timer(reader), depressed(reader)), (5, True))

    def test_animation_before_pressure_frees_default_slots_in_time_for_source(self):
        state, reader = fixture(trobs=((9, 2, 1, 1),) * 20)
        state = step(state, reader, 'animate')
        state = step(state, reader, 'press')
        self.assertEqual(state['trobs'], ((23, 1, 1, 6),))
        for _ in range(5):
            state = step(state, reader, 'animate')
        self.assertFalse(depressed(reader))

    def test_permanent_source_has_no_animation_record_and_keeps_depressed_bit(self):
        state, reader = fixture(timer=31)
        for _ in range(3):
            state = step(state, reader, 'press')
            self.assertEqual((state['trobs'], state['press_flag']), ((), 4321))
            self.assertFalse(any(event[0] == 'sound' for event in state['events']))
            state = step(state, reader, 'animate')
        self.assertEqual((timer(reader), depressed(reader), state['bank']), (31, True, (ROCK,)))

    def test_full_mob_bank_still_allows_plate_release_and_compaction(self):
        bank = ((0, 116, 2, 0, 2, 6, 0, 0),) * 30
        state, reader = fixture(bank=bank)
        state = step(state, reader, 'press')
        self.assertEqual((state['bank'], state['mob']), (bank, ROCK))
        for _ in range(5):
            state = step(state, reader, 'animate')
        self.assertEqual((state['trobs'], depressed(reader), state['bank']), ((), False, bank))

    def test_release_does_not_change_existing_rock_control(self):
        for initial_control, expected in ((2, -2), (100, 100)):
            rock = (*ROCK[:4], initial_control, *ROCK[5:])
            state, reader = fixture(bank=(rock,))
            state = step(state, reader, 'press')
            for _ in range(5):
                state = step(state, reader, 'animate')
            self.assertEqual(state['bank'][0][4], expected)
            self.assertEqual(state['rock_calls'], [])

    def test_animation_uses_source_scratch_while_read_cache_stays_at_rock(self):
        state, reader = fixture()
        state = step(state, reader, 'press')
        cache = reader.cache
        self.assertEqual(cache[2:4], (29, 1))
        for _ in range(5):
            state = step(state, reader, 'animate')
        self.assertEqual(reader.cache, cache)
        self.assertEqual(reader.requests, [])
        self.assertIn(('release_redraw', 1, 23, 0x2004, 0), state['events'])

    def test_unknown_operation_is_rejected(self):
        state, reader = fixture()
        with self.assertRaises(ValueError):
            step(state, reader, 'frame')


if __name__ == '__main__':
    unittest.main()
