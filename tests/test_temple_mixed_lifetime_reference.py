from dataclasses import replace
import struct
import unittest

from tests.test_temple_mixed_plate_links_reference import fixture as mixed_fixture, state as mechanism_state
from tests.test_temple_slide_rock_admission_reference import link
from tests.test_temple_slide_rock_geometry_reference import tile
from tools.probe_temple_mixed_lifetime import mixed_lifetime_step
from tools.probe_temple_pressure_admission import PressureActor


OPEN = PressureActor(3, 6, 1, 236)
CLOSE = replace(OPEN, column=5)
FILLER = (9, 4, 1, 1)


def fixture(position=0, trobs=(), bank=()):
    reader, _ = mixed_fixture(mode=5, timer=0, position=position)
    level = bytearray(reader.level)
    tile(level, 3, 5, 1, 6)
    struct.pack_into('>H', level, 0x780 + 2 * 120 + 15 * 4, 2)
    link(level, 2, 3, 2, following=3)
    link(level, 3, 3, 18)
    reader.level = level
    state = dict(mechanism_state(bank, trobs), os=bytes((11, 13, 17, 19, 23, 29)),
                 press_flag=4321, pressure_requests=[], relief_countdown=1234)
    return state, reader


def step(state, reader, operation='check', actor=OPEN):
    reader.requests.clear()
    return mixed_lifetime_step(dict(state, events=[], object_calls=[], rock_calls=[]), reader, operation, actor)


def position(reader):
    return struct.unpack_from('>H', reader.level, 0x780 + 2 * 120 + 2 * 4)[0] & 255


class TempleMixedLifetimeTests(unittest.TestCase):
    def test_contact_registers_source_before_target_and_missing_rock_does_not_cancel_gate(self):
        state, reader = fixture()
        state = step(state, reader)
        self.assertEqual(state['trobs'], ((16, 3, 1, 5), (2, 3, 2, 4)))
        self.assertEqual(state['bank'], ())
        self.assertEqual(state['pressure_requests'], [('push', (0, -1))])

    def test_source_release_compacts_without_removing_the_still_opening_gate(self):
        state, reader = fixture()
        state = step(state, reader)
        for _ in range(5):
            state = step(state, reader, 'animate')
        self.assertEqual((state['trobs'], position(reader)), (((2, 3, 2, 4),), 20))
        self.assertEqual(struct.unpack_from('>H', reader.level, 0x780 + 2 * 120 + 16 * 4)[0], 0)

    def test_other_plate_reverses_gate_and_creates_forced_rock_record(self):
        state, reader = fixture()
        state = step(state, reader)
        for _ in range(12):
            state = step(state, reader, 'animate')
        self.assertEqual(position(reader), 48)
        state = step(state, reader, actor=CLOSE)
        self.assertEqual(state['trobs'], ((2, 3, 4, 4), (15, 3, 1, 6)))
        self.assertEqual(state['bank'], ((408, 236, 3, 0, -2, 6, 1, 408),))
        cache = reader.cache
        state = step(state, reader, 'animate', CLOSE)
        self.assertEqual((position(reader), state['trobs']), (0, ((15, 3, 1, 6),)))
        self.assertEqual(reader.cache, cache)
        self.assertIn(('relief_check',), state['events'])
        self.assertEqual(state['relief_countdown'], 1234)

    def test_permanent_actor_opens_to255_without_source_trob_or_later_close(self):
        state, reader = fixture()
        state = step(state, reader, actor=replace(OPEN, alive=0, pose=185))
        self.assertEqual(state['trobs'], ((2, 3, 3, 4),))
        for _ in range(80):
            state = step(state, reader, 'animate')
        self.assertEqual((position(reader), state['trobs']), (255, ()))
        self.assertEqual(struct.unpack_from('>h', reader.level, 0x1680 + 4)[0], 31)

    def test_source_can_take_last_slot_leaving_gate_at80_without_a_trob(self):
        state, reader = fixture(position=80, trobs=(FILLER,) * 19)
        state = step(state, reader)
        self.assertEqual(len(state['trobs']), 20)
        self.assertFalse(any(record[3] == 4 for record in state['trobs']))
        for _ in range(160):
            state = step(state, reader, 'animate')
        self.assertEqual((position(reader), state['trobs']), (80, ()))

    def test_later_held_pressure_can_register_gate_without_reregistering_missing_source(self):
        state, reader = fixture(position=80, trobs=(FILLER,) * 20)
        state = step(state, reader)
        state = step(state, reader, 'animate')
        self.assertEqual(state['trobs'], ())
        state = step(state, reader)
        self.assertEqual(state['trobs'], ((2, 3, 2, 4),))
        self.assertEqual(struct.unpack_from('>h', reader.level, 0x1680 + 4)[0], 5)

    def test_rejected_contact_does_not_refresh_source_or_remove_gate(self):
        state, reader = fixture()
        state = step(state, reader)
        state = step(state, reader, 'animate')
        state = step(state, reader, actor=replace(OPEN, aux=0))
        self.assertEqual(state['pressure_requests'], [])
        self.assertEqual(struct.unpack_from('>h', reader.level, 0x1680 + 4)[0], 4)
        self.assertEqual(len(state['trobs']), 2)

    def test_normal_gate_finishes_even_with_no_actor_contact_after_initial_press(self):
        state, reader = fixture()
        state = step(state, reader)
        for _ in range(160):
            state = step(state, reader, 'animate')
        self.assertEqual((position(reader), state['trobs'], state['bank']), (0, (), ()))

    def test_full_mob_bank_does_not_prevent_gate_registration(self):
        bank = ((0, 116, 4, 0, 2, 6, 0, 0),) * 30
        state, reader = fixture(bank=bank)
        state = step(state, reader)
        self.assertEqual(state['bank'], bank)
        self.assertEqual(state['trobs'], ((16, 3, 1, 5), (2, 3, 2, 4)))

    def test_other_actor_or_hanging_modes_are_explicitly_outside_this_model(self):
        for actor in (replace(OPEN, kind=4), replace(OPEN, mode=2)):
            state, reader = fixture()
            with self.assertRaises(ValueError):
                step(state, reader, actor=actor)


if __name__ == '__main__':
    unittest.main()
