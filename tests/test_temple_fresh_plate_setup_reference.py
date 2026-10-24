"""First-press ordering and suppression, without original resources or graphics."""

import struct
import unittest

from tests.test_temple_mixed_plate_links_reference import CONTEXT, OTHER, ROCK, fixture, state
from tools.probe_temple_fresh_plate_setup import plate_reference
from tools.probe_temple_slide_rock_geometry import TempleCellReader


def prepared(mode=6, timer=0, depressed=False):
    reader, source = fixture(mode, timer)
    if depressed:
        struct.pack_into('>H', reader.level, 0x780 + 2 * 120 + source * 4, 0x2000)
    reader.read(3, source % 10, 1)
    return reader, source


class TempleFreshPlateSetupTests(unittest.TestCase):
    def test_first_press_orders_source_sound_redraw_then_gate_and_rock(self):
        reader, source = prepared()
        result = plate_reference(dict(state(), press_flag=4321), reader, CONTEXT)
        self.assertEqual(result['events'], [('trob', 3, source, 1, 6), ('sound', 27),
                                            ('redraw', 3, source, 0), ('object', 4, 3, 2, 6),
                                            ('trob', 3, 2, 4, 4), ('object', 25, 3, 18, 6),
                                            ('rock', 3, 18, 1)])
        self.assertEqual(result['trobs'], ((source, 3, 1, 6), (2, 3, 4, 4)))
        self.assertEqual(result['bank'], (ROCK,))
        self.assertEqual(result['press_flag'], 1)

    def test_last_trob_slot_goes_to_plate_not_gate_and_rock_still_runs(self):
        reader, source = prepared()
        result = plate_reference(dict(state(trobs=(OTHER,) * 19), press_flag=0), reader, CONTEXT)
        self.assertEqual(result['trobs'][-1], (source, 3, 1, 6))
        self.assertEqual(len(result['trobs']), 20)
        self.assertFalse(any(record[:2] == (2, 3) for record in result['trobs']))
        self.assertEqual(result['bank'], (ROCK,))

    def test_full_trob_bank_does_not_cancel_sound_redraw_flag_or_links(self):
        reader, source = prepared()
        initial = dict(state(trobs=(OTHER,) * 20), press_flag=4321)
        result = plate_reference(initial, reader, CONTEXT)
        self.assertEqual(result['trobs'], initial['trobs'])
        self.assertEqual(result['trob_scratch'], initial['trob_scratch'])
        self.assertIn(('sound', 27), result['events'])
        self.assertIn(('redraw', 3, source, 0), result['events'])
        self.assertEqual((result['press_flag'], result['bank']), (1, (ROCK,)))

    def test_existing_source_trob_reuses_slot_even_with_different_kind(self):
        reader, source = prepared()
        initial = dict(state(trobs=((source, 3, -1, 99),) + (OTHER,) * 18), press_flag=0)
        result = plate_reference(initial, reader, CONTEXT)
        self.assertEqual(result['trobs'][0], (source, 3, 1, 99))
        self.assertEqual(result['trobs'][-1], (2, 3, 4, 4))
        self.assertEqual(len(result['trobs']), 20)

    def test_failed_gate_append_does_not_roll_back_gate_foreground(self):
        reader, _ = prepared(mode=5)
        initial = dict(state(trobs=(OTHER,) * 19), press_flag=0)
        result = plate_reference(initial, reader, CONTEXT)
        self.assertEqual(len(result['trobs']), 20)
        self.assertEqual(struct.unpack_from('>H', reader.level, 0x780 + 2 * 120 + 2 * 4)[0], 0xa5b4)
        # Position180 is already aligned; use183 to prove a mutation survives rejection.
        reader, _ = prepared(mode=5)
        struct.pack_into('>H', reader.level, 0x780 + 2 * 120 + 2 * 4, 0xa5b7)
        result = plate_reference(initial, reader, CONTEXT)
        self.assertEqual(struct.unpack_from('>H', reader.level, 0x780 + 2 * 120 + 2 * 4)[0], 0xa5b8)
        self.assertFalse(any(record[:2] == (2, 3) for record in result['trobs']))

    def test_depressed_bit_does_not_suppress_first_press_when_timer_is_fresh(self):
        reader, source = prepared(depressed=True)
        result = plate_reference(dict(state(), press_flag=0), reader, CONTEXT)
        self.assertIn(('sound', 27), result['events'])
        self.assertIn(('redraw', 3, source, 0x2000), result['events'])

    def test_pose185_suppresses_sound_only(self):
        reader, source = prepared()
        result = plate_reference(dict(state(), press_flag=0), reader, (185, -1, 3, 0))
        self.assertFalse(any(event[0] == 'sound' for event in result['events']))
        self.assertIn(('redraw', 3, source, 0), result['events'])
        self.assertEqual((result['press_flag'], result['bank']), (1, (ROCK,)))

    def test_sound_room_exception_requires_both_level13_and_room4(self):
        for number, room, expected in ((13, 4, False), (12, 4, True), (13, 3, True)):
            reader, source = prepared()
            level = bytearray(reader.level)
            struct.pack_into('>h', level, 0x218a, number)
            struct.pack_into('>h', level, (room - 1) * 60 + source * 2, 6)
            struct.pack_into('>h', level, 0x780 + (room - 1) * 120 + source * 4, 0)
            reader = TempleCellReader(level, room)
            reader.read(room, source % 10, 1)
            result = plate_reference(dict(state(), press_flag=0), reader, (0, -1, room, 0))
            self.assertEqual(('sound', 27) in result['events'], expected)
            self.assertIn(('redraw', room, source, 0), result['events'])

    def test_timer_not_depression_controls_transition_to_held_path(self):
        for timer in (-1, 0, 1, 2, 31):
            reader, source = prepared(timer=timer)
            result = plate_reference(dict(state(), press_flag=4321), reader, CONTEXT)
            self.assertEqual(('sound', 27) in result['events'], timer < 2)
            self.assertEqual(result['press_flag'], 1 if timer < 2 else 4321)
            self.assertEqual(struct.unpack_from('>h', reader.level, 0x1684)[0], 31 if timer == 31 else 5)
            reader.read(3, source % 10, 1)
            result = plate_reference(dict(result, events=[]), reader, CONTEXT)
            self.assertFalse(any(event[0] in ('sound', 'redraw') for event in result['events']))

    def test_wrong_cached_kind_is_rejected(self):
        reader, _ = prepared()
        reader.cache = (25, *reader.cache[1:])
        with self.assertRaises(ValueError):
            plate_reference(dict(state(), press_flag=0), reader, CONTEXT)


if __name__ == '__main__':
    unittest.main()
