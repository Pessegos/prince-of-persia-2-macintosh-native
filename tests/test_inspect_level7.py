"""Asset-free tests for the standalone later-level research inventory."""

import struct
import unittest

from tools.inspect_level7 import inventory_level, resource_filename


def fixture():
    data = bytearray(0x49ca)
    struct.pack_into('>H', data, 0x2186, 4)
    struct.pack_into('>H', data, 0x218a, 7)
    struct.pack_into('>3H', data, 0x2198, 32, 24, 0)
    struct.pack_into('>h', data, 0x21a4, 5)
    return data


class InventoryTests(unittest.TestCase):
    def test_identity_and_default_facing_are_decoded_without_scene_loading(self):
        result = inventory_level(fixture())
        self.assertEqual(result['resource_id'], 2006)
        self.assertEqual(result['environment'], 4)
        self.assertEqual(result['opponent_set'], 5)
        self.assertEqual(result['start'], dict(room=32, cell=24, port_facing=0, port_x=226))
        self.assertEqual(result['tile_counts'], {'0': 960})

    def test_links_follow_native_room_numbers_and_stop_at_missing_links(self):
        data = fixture()
        struct.pack_into('>H', data, 0x2080 + 31 * 8, 3)
        struct.pack_into('>H', data, 0x2080 + 2 * 8 + 2, 32)
        result = inventory_level(data)
        self.assertEqual(result['reachable_rooms'], [3, 32])
        self.assertEqual(result['rooms'][31]['links']['left'], 3)
        self.assertIsNone(result['rooms'][31]['links']['right'])

    def test_custom_flags_use_foreground_not_background(self):
        data = fixture()
        struct.pack_into('>2H', data, 0x780 + 31 * 120, 0x4000, 0)
        struct.pack_into('>2H', data, 0x780, 0, 0xc000)
        rooms = inventory_level(data)['rooms']
        self.assertEqual(rooms[31]['custom_resource'], 4775)
        self.assertIsNone(rooms[0]['custom_resource'])

    def test_raw_special_records_do_not_use_ordinary_guard_decoder(self):
        data = fixture()
        offset = 0x20e6 + 32 * 0xc0
        words = tuple(range(-9, 10))
        struct.pack_into('>H19h', data, offset, 1, *words)
        self.assertEqual(inventory_level(data)['rooms'][31]['generator_records'], [list(words)])

    def test_checkpoint_and_identity_validation(self):
        data = fixture()
        struct.pack_into('>4h', data, 0x39a6, 3, 0, 0, 0)
        self.assertEqual(inventory_level(data)['checkpoints'], [dict(slot=1, room=3, cell=0)])
        with self.assertRaisesRegex(ValueError, 'not 6'):
            inventory_level(data, 6)

    def test_rejects_generator_overflow_and_truncated_levels(self):
        data = fixture()
        struct.pack_into('>H', data, 0x20e6 + 32 * 0xc0, 6)
        with self.assertRaisesRegex(ValueError, 'generator'):
            inventory_level(data)
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            inventory_level(data[:100])


class FilenameTests(unittest.TestCase):
    def test_pascal_filename_and_six_byte_stride(self):
        data = bytearray(120)
        name = b':Data:Ruins.rsrc'
        data[8:9 + len(name)] = bytes([len(name)]) + name
        struct.pack_into('>hi', data, 70 + 4 * 6, 0, 8 - len(data))
        self.assertEqual(resource_filename(data, -50, 4), 'Ruins.rsrc')

    def test_invalid_pointer_and_index_are_not_silently_decoded(self):
        data = bytearray(120)
        for index in (-1, 25):
            with self.assertRaises(ValueError):
                resource_filename(data, -50, index)
        for pointer in (0, -121):
            struct.pack_into('>i', data, 72, pointer)
            with self.assertRaises(ValueError):
                resource_filename(data, -50, 0)

    def test_truncated_pascal_string_is_rejected(self):
        data = bytearray(120)
        struct.pack_into('>i', data, 72, -2)
        data[118] = 5
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            resource_filename(data, -50, 0)


if __name__ == '__main__':
    unittest.main()
