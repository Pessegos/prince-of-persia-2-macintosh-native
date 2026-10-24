"""Asset-free regression cases for pressure chains spanning two object banks."""

import struct
import unittest

from tests.test_temple_slide_rock_admission_reference import link, state as rock_state
from tests.test_temple_slide_rock_geometry_reference import level_fixture, tile
from tools.probe_temple_mixed_plate_links import add_trob, gate_reference, held_mixed_plate, mixed_chain
from tools.probe_temple_slide_rock_geometry import TempleCellReader


CONTEXT = (0, -1, 3, 0)
ROCK = (408, 236, 3, 0, -2, 6, 1, 408)
OTHER = (9, 4, 1, 6)


def state(bank=(), trobs=()):
    storage = bytearray([0xa7] * 160)
    for i, record in enumerate(trobs):
        struct.pack_into('>4h', storage, i * 8, *record)
    return dict(rock_state(bank), trobs=tuple(trobs), trob_storage=bytes(storage),
                trob_scratch=(41, 43, 47, 53), events=[])


def fixture(mode=6, timer=2, position=180):
    level = level_fixture(11)
    source = 15 if mode == 6 else 16
    tile(level, 3, source % 10, 1, mode)
    tile(level, 3, 2, 0, 4)
    tile(level, 3, 8, 1, 25)
    struct.pack_into('>H', level, 0x780 + 2 * 120 + 2 * 4, 0xa500 | position)
    struct.pack_into('>H', level, 0x780 + 2 * 120 + source * 4, 0)
    first, second = (2, 18) if mode == 6 else (18, 2)
    link(level, 0, 3, first, 1, timer)
    link(level, 1, 3, second)
    return TempleCellReader(level, 3), source


class TempleMixedPlateLinksTests(unittest.TestCase):
    def test_gate_first_chain_runs_both_mechanisms_in_link_order(self):
        reader, _ = fixture()
        result = mixed_chain(state(), reader, 0, 6, CONTEXT)
        self.assertEqual(result['events'], [('object', 4, 3, 2, 6), ('trob', 3, 2, 4, 4),
                                            ('object', 25, 3, 18, 6), ('rock', 3, 18, 1)])
        self.assertEqual(result['trobs'], ((2, 3, 4, 4),))
        self.assertEqual(result['bank'], (ROCK,))

    def test_rock_first_chain_releases_existing_rock_then_opens_gate(self):
        reader, _ = fixture(mode=5)
        result = mixed_chain(state((ROCK,)), reader, 0, 5, CONTEXT)
        self.assertEqual(result['events'], [('object', 25, 3, 18, 5), ('rock', 3, 18, 2),
                                            ('object', 4, 3, 2, 5), ('trob', 3, 2, 2, 4)])
        self.assertEqual(result['bank'][0][4], 2)

    def test_missing_rock_in_mode_five_does_not_cancel_gate(self):
        reader, _ = fixture(mode=5)
        result = mixed_chain(state(), reader, 0, 5, CONTEXT)
        self.assertEqual(result['bank'], ())
        self.assertEqual(result['trobs'], ((2, 3, 2, 4),))

    def test_no_gate_request_does_not_cancel_rock_creation(self):
        reader, _ = fixture(position=0)
        result = mixed_chain(state(), reader, 0, 6, CONTEXT)
        self.assertEqual(result['trobs'], ())
        self.assertEqual(result['bank'], (ROCK,))

    def test_full_trob_bank_does_not_block_rock_bank(self):
        reader, _ = fixture()
        initial = state(trobs=(OTHER,) * 20)
        result = mixed_chain(initial, reader, 0, 6, CONTEXT)
        self.assertEqual(result['bank'], (ROCK,))
        for key in ('trobs', 'trob_storage', 'trob_scratch'):
            self.assertEqual(result[key], initial[key])

    def test_full_rock_bank_does_not_block_trob_bank(self):
        reader, _ = fixture()
        bank = ((0, 116, 4, 0, 2, 6, 0, 0),) * 30
        result = mixed_chain(state(bank), reader, 0, 6, CONTEXT)
        self.assertEqual(result['bank'], bank)
        self.assertEqual(result['mob'], ROCK)
        self.assertEqual(result['trobs'], ((2, 3, 4, 4),))

    def test_full_trob_bank_still_updates_existing_last_record(self):
        initial = state(trobs=(OTHER,) * 19 + ((2, 3, 2, 4),))
        result = add_trob(initial, 3, 2, 4, 4)
        self.assertEqual(len(result['trobs']), 20)
        self.assertEqual(result['trobs'][-1], (2, 3, 4, 4))
        self.assertEqual(result['trob_scratch'], initial['trob_scratch'])

    def test_first_coordinate_match_ignores_kind_and_negative_phase(self):
        initial = state(trobs=((2, 3, -1, 99), (2, 3, 4, 4)))
        result = add_trob(initial, 3, 2, 2, 4)
        self.assertEqual(result['trobs'], ((2, 3, 2, 99), (2, 3, 4, 4)))
        self.assertEqual(result['trob_storage'][16:], initial['trob_storage'][16:])
        self.assertEqual(result['trob_scratch'], initial['trob_scratch'])

    def test_append_at_last_slot_writes_scratch_and_only_that_record(self):
        initial = state(trobs=(OTHER,) * 19)
        result = add_trob(initial, 3, 2, 2, 4)
        self.assertEqual(result['trob_scratch'], (2, 3, 2, 4))
        self.assertEqual(result['trob_storage'][:152], initial['trob_storage'][:152])
        self.assertEqual(result['trobs'][-1], (2, 3, 2, 4))

    def test_gate_threshold_preserves_decoration_and_actor_context(self):
        self.assertEqual(gate_reference(0xa5b7, 5, (), 3, 2, CONTEXT), (0xa5b8, 2))
        self.assertEqual(gate_reference(0xa5b8, 5, (), 3, 2, CONTEXT), (0xa5ed, -1))
        self.assertEqual(gate_reference(0xa5b8, 5, (), 3, 2, (0, 0, 3, 0)), (0xa5ff, 3))
        self.assertEqual(gate_reference(0xa5b8, 5, (), 3, 2, (0, -1, 3, 3)), (0xa5ed, -1))
        self.assertEqual(gate_reference(0xa5b8, 5, (), 3, 2, (0, -1, 3, 4)), (0xa5ff, 3))
        self.assertEqual(gate_reference(0xa5ff, 5, (), 3, 2, CONTEXT), (0xa5ff, -1))

    def test_closing_gate_admission_depends_on_pose_and_alive_together(self):
        for pose in (185, 242, 243, 266, 271):
            self.assertEqual(gate_reference(180, 6, (), 3, 2, (pose, 2, 3, 0)), (180, -1))
            self.assertEqual(gate_reference(180, 6, (), 3, 2, (pose, 1, 3, 0)), (180, 4))
        self.assertEqual(gate_reference(180, 6, (), 3, 2, (0, 2, 3, 0)), (180, 4))

    def test_mode_six_uses_existing_phase_even_with_zero_position(self):
        self.assertEqual(gate_reference(0, 6, (), 3, 2, CONTEXT), (0, -1))
        self.assertEqual(gate_reference(0, 6, ((2, 3, 2, 4),), 3, 2, CONTEXT), (0, 4))
        self.assertEqual(gate_reference(180, 6, ((2, 3, 4, 4),), 3, 2, CONTEXT), (180, -1))

    def test_held_plate_marks_saved_source_despite_rock_read_changing_cache(self):
        reader, source = fixture(timer=2)
        reader.read(3, source % 10, 1)
        result = held_mixed_plate(state(), reader, 3, source, CONTEXT)
        self.assertEqual(reader.cache[2:4], (18, 3))
        self.assertEqual(struct.unpack_from('>H', reader.level, 0x780 + 2 * 120 + source * 4)[0], 0x2000)
        self.assertEqual(struct.unpack_from('>h', reader.level, 0x1684)[0], 5)
        self.assertEqual((len(result['trobs']), len(result['bank'])), (1, 1))

    def test_permanent_held_plate_reuses_both_banks(self):
        reader, source = fixture(timer=31)
        result = state()
        for _ in range(3):
            reader.read(3, source % 10, 1)
            result = held_mixed_plate(result, reader, 3, source, CONTEXT)
            self.assertEqual((len(result['trobs']), len(result['bank'])), (1, 1))
            self.assertEqual(struct.unpack_from('>h', reader.level, 0x1684)[0], 31)

    def test_out_of_scope_modes_fresh_timers_and_level_five_fail_closed(self):
        with self.assertRaises(ValueError):
            gate_reference(180, 34, (), 3, 2, CONTEXT)
        reader, source = fixture(timer=0)
        reader.read(3, source % 10, 1)
        with self.assertRaises(ValueError):
            held_mixed_plate(state(), reader, 3, source, CONTEXT)
        struct.pack_into('>h', reader.level, 0x218a, 5)
        with self.assertRaises(ValueError):
            mixed_chain(state(), reader, 0, 6, CONTEXT)


if __name__ == '__main__':
    unittest.main()
