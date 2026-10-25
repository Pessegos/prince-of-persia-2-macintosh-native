"""Synthetic checks for temple header reference rules."""

import struct
import unittest

from tools.probe_temple_headers import customized_reference, temple_kind_reference


class TempleHeaderReferenceTests(unittest.TestCase):
    def test_bird_kind_is_not_the_working_actor_type(self):
        self.assertEqual(temple_kind_reference(7), (7, 2))

    def test_four_exceptional_kinds_are_preserved(self):
        for kind, actor in ((1, 10), (3, 6), (9, 12), (10, 0)):
            self.assertEqual(temple_kind_reference(kind), (kind, actor))

    def test_other_kinds_are_replaced_by_the_level_opponent_set(self):
        for kind in (-1, 0, 2, 4, 5, 6, 8, 11, 100):
            self.assertEqual(temple_kind_reference(kind), (7, 2))

    def test_either_high_foreground_bit_is_sufficient(self):
        for flag in (0x4000, 0x8000, 0xc000):
            data = bytearray(0x2000)
            struct.pack_into('>H', data, 0x780 + 29 * 4, flag)
            self.assertTrue(customized_reference(data, 1))
            self.assertFalse(customized_reference(data, 2))

    def test_background_and_low_foreground_bits_are_not_custom_flags(self):
        data = bytearray(0x2000)
        struct.pack_into('>2H', data, 0x780, 0x3fff, 0xc000)
        self.assertFalse(customized_reference(data, 1))

    def test_invalid_native_room_is_rejected(self):
        for room in (0, 33):
            with self.assertRaises(ValueError):
                customized_reference(bytes(0x2000), room)


if __name__ == '__main__':
    unittest.main()
