from dataclasses import replace
import struct
import unittest

from tests.test_temple_mixed_lifetime_reference import CLOSE, OPEN, fixture
from tools.probe_temple_mixed_rock_motion import NativeMixedRockMotion, mixed_rock_step
from tools.probe_temple_pressure_admission import actor_bytes
from tools.probe_temple_slide_rock_lifecycle import store_bank
from tools.probe_temple_slide_rock_update import make_prince


def prepare(bank=(), position=80):
    state, reader = fixture(position=position, bank=bank)
    state.update(prince=make_prince(room=0, row=0, frame=0), working=actor_bytes(CLOSE),
                 pending=192, phases=[], actor_inputs=[])
    return state, reader


def step(state, reader, operation, actor=CLOSE):
    reader.requests.clear()
    state = dict(state, working=actor_bytes(actor), events=[], object_calls=[], rock_calls=[],
                 pressure_requests=[], phases=[], actor_inputs=[])
    return mixed_rock_step(state, reader, operation, actor)


class TempleMixedRockMotionTests(unittest.TestCase):
    def test_already_closed_gate_does_not_prevent_rock_creation_or_movement(self):
        state, reader = prepare(position=0)
        state = step(state, reader, 'check')
        self.assertFalse(any(record[3] == 4 for record in state['trobs']))
        state = step(state, reader, 'rocks')
        self.assertEqual(state['bank'][0][0], 406)

    def test_closing_plate_creates_rock_then_real_geometry_moves_it_two_units(self):
        state, reader = prepare()
        state = step(state, reader, 'check')
        original = state['bank'][0]
        self.assertEqual(original, (408, 236, 3, 0, -2, 6, 1, 408))
        state = step(state, reader, 'rocks')
        self.assertEqual(state['bank'][0], (406, 236, 3, 0, -2, 6, 1, 408))
        self.assertEqual(state['phases'], [('motion', original), ('crush', state['bank'][0])])
        self.assertEqual(state['events'], [('cell', 3, 7, 1), ('sound', 192)])
        self.assertEqual(state['actor_inputs'], [])

    def test_opening_plate_repopulates_cache_after_motion_and_releases_existing_rock(self):
        state, reader = prepare()
        state = step(state, reader, 'check')
        state = step(state, reader, 'rocks')
        self.assertEqual(reader.cache[2:], (17, 3, 7, 1))
        state = step(state, reader, 'check', OPEN)
        self.assertEqual(reader.cache[2:], (16, 3, 6, 1))
        self.assertEqual(state['bank'][0][4], 2)
        self.assertIn((2, 3, 2, 4), state['trobs'])

    def test_plate_release_does_not_cancel_independent_rock_motion(self):
        state, reader = prepare()
        state = step(state, reader, 'check')
        for _ in range(5):
            state = step(state, reader, 'animate')
            state = step(state, reader, 'rocks')
        self.assertEqual(state['trobs'], ())
        self.assertEqual(state['bank'][0][0], 398)
        self.assertEqual(state['bank'][0][4], -2)

    def test_released_rock_eventually_stops_on_filled_bands_and_clears_matching_cue(self):
        state, reader = prepare()
        state = step(state, reader, 'check')
        state = step(state, reader, 'check', OPEN)
        for _ in range(80):
            state = step(state, reader, 'rocks', OPEN)
        self.assertEqual(state['bank'][0][4], 0)
        self.assertEqual(state['pending'], -1)

    def test_terminal_control100_cannot_be_reactivated_by_closing_plate(self):
        rock = (408, 236, 3, 0, 100, 6, 1, 408)
        state, reader = prepare((rock,))
        state = step(state, reader, 'check')
        state = step(state, reader, 'rocks')
        self.assertEqual(state['bank'], (rock,))
        self.assertEqual(state['events'], [])

    def test_full_removed_bank_can_free_slots_then_held_pressure_creates_rock(self):
        filler = (0, 116, 4, -1, 100, 6, 0, 0)
        state, reader = prepare((filler,) * 30)
        state = step(state, reader, 'check')
        self.assertEqual(len(state['bank']), 30)
        state = step(state, reader, 'rocks')
        self.assertEqual(state['bank'], ())
        state = step(state, reader, 'check')
        self.assertEqual(state['bank'], ((408, 236, 3, 0, -2, 6, 1, 408),))

    def test_retained_full_bank_blocks_new_rock_but_not_gate_animation(self):
        filler = (0, 116, 4, 0, 100, 6, 0, 0)
        state, reader = prepare((filler,) * 30)
        state = step(state, reader, 'check')
        state = step(state, reader, 'animate')
        state = step(state, reader, 'rocks')
        self.assertEqual(state['bank'], (filler,) * 30)
        self.assertEqual(struct.unpack_from('>H', reader.level, 0x780 + 2 * 120 + 2 * 4)[0] & 255, 20)

    def test_compaction_keeps_updated_survivor_and_preserves_old_tail_bytes(self):
        removed = (0, 116, 4, -1, 100, 6, 0, 0)
        rock = (408, 236, 3, 0, -2, 6, 1, 408)
        state, reader = prepare((removed, rock))
        storage = state['bank_storage']
        state = step(state, reader, 'rocks')
        moved = (406, 236, 3, 0, -2, 6, 1, 408)
        self.assertEqual(state['bank'], (moved,))
        self.assertEqual(state['bank_storage'], store_bank(store_bank(storage, (removed, moved)), (moved,)))

    def test_ordinary_gate_stop_copies_full_saved_prince_without_mutating_it(self):
        state, reader = prepare(position=3)
        state['trobs'] = ((2, 3, 1, 4),)
        state['trob_storage'] = struct.pack('>4h', *state['trobs'][0]) + state['trob_storage'][8:]
        prince = state['prince']
        state = step(state, reader, 'animate')
        self.assertEqual(state['working'], prince)
        self.assertEqual(state['prince'], prince)
        self.assertIn(('load_kid',), state['events'])

    def test_out_of_scope_saved_actor_or_non_type6_bank_is_rejected(self):
        for prince in (make_prince(room=3, frame=0), make_prince(room=0, frame=87)):
            state, reader = prepare()
            with self.assertRaises(ValueError):
                step(dict(state, prince=prince), reader, 'rocks')
        state, reader = prepare(((408, 236, 3, 0, 2, 1, 1, 408),))
        with self.assertRaises(ValueError):
            step(state, reader, 'rocks')

    def test_pressure_rejection_does_not_stop_already_forced_motion(self):
        state, reader = prepare()
        state = step(state, reader, 'check')
        state = step(state, reader, 'check', replace(CLOSE, aux=0))
        self.assertEqual(state['pressure_requests'], [])
        state = step(state, reader, 'rocks')
        self.assertEqual(state['bank'][0][0], 406)

    def test_native_motion_and_geometry_are_not_supplied_endpoints(self):
        for target in ((10, 0x1656), (4, 0x27ee), (10, 0x1d5c), (10, 0x16f6), (5, 0x29e8)):
            self.assertNotIn(target, NativeMixedRockMotion.SUPPLIED)
            self.assertTrue(any(low <= target[1] <= high for low, high in NativeMixedRockMotion.RANGES[target[0]]))


if __name__ == '__main__':
    unittest.main()
