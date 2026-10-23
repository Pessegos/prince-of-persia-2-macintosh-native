"""Synthetic trap-door trigger/constructor references; no game resource bytes."""

import struct
import unittest

from tools.probe_temple_trapdoors import trigger_reference


def fixture(foreground=0, room=2, cell=14):
    data = bytearray(0x2000)
    struct.pack_into('>H', data, (room - 1) * 60 + cell * 2, 26)
    struct.pack_into('>2H', data, 0x780 + (room - 1) * 120 + cell * 4, foreground, 0x1234)
    return data


class TempleTrapDoorReferenceTests(unittest.TestCase):
    def test_same_column_creates_counter_one_and_removes_floor(self):
        data = fixture()
        result = trigger_reference(data, 2, 14, 4, 0)
        self.assertEqual(result['scratch_mob'], (204, 245, 2, 0, 0, 10, 1, 1))
        self.assertEqual((result['count'], result['cached_foreground']), (1, 0))
        self.assertEqual(struct.unpack_from('>H', result['level'], 60 + 14 * 2)[0], 0)
        self.assertEqual(struct.unpack_from('>2H', result['level'], 0x780 + 120 + 14 * 4), (0x81, 0x1234))
        self.assertEqual((result['sounds'], result['redraw']), ([197], [0]))

    def test_different_column_caches_bit_40_and_creates_counter_75(self):
        for column in (3, 5):
            result = trigger_reference(fixture(), 2, 14, column, 0)
            self.assertEqual(result['cached_foreground'], 0x40)
            self.assertEqual(result['scratch_mob'][-1], 75)

    def test_existing_bit_40_rejects_without_sound_or_mutation(self):
        data = fixture(0x8041)
        result = trigger_reference(data, 2, 14, 4, 3)
        self.assertEqual(result['level'], data)
        self.assertEqual((result['count'], result['scratch_mob'], result['appended']), (3, None, False))
        self.assertEqual((result['sounds'], result['redraw']), ([], []))

    def test_last_free_slot_is_used_but_a_full_bank_does_not_append(self):
        result = trigger_reference(fixture(), 2, 14, 4, 29)
        self.assertEqual((result['count'], result['appended']), (30, True))
        full = trigger_reference(fixture(), 2, 14, 4, 30)
        self.assertEqual((full['count'], full['appended']), (30, False))
        self.assertIsNotNone(full['scratch_mob'])
        self.assertEqual(full['sounds'], [197])
        self.assertNotEqual(full['level'], fixture())

    def test_unrelated_foreground_bits_are_not_preserved_in_level_word(self):
        result = trigger_reference(fixture(0x8001), 2, 14, 4, 0)
        self.assertEqual(result['cached_foreground'], 0x8001)
        self.assertEqual(struct.unpack_from('>H', result['level'], 0x780 + 120 + 14 * 4)[0], 0x81)

    def test_input_level_is_not_modified(self):
        data = fixture()
        before = bytes(data)
        trigger_reference(data, 2, 14, 4, 0)
        self.assertEqual(data, before)

    def test_invalid_inputs_and_non_trap_cells_are_rejected(self):
        for room, cell, count in ((0, 14, 0), (33, 14, 0), (2, 30, 0), (2, 14, -1), (2, 14, 31)):
            with self.assertRaises(ValueError):
                trigger_reference(fixture(), room, cell, 4, count)
        with self.assertRaises(ValueError):
            trigger_reference(bytes(0x2000), 2, 14, 4, 0)


if __name__ == '__main__':
    unittest.main()
