"""Synthetic temple inventories, without original game data."""

import struct
import unittest

from tests.test_inspect_level7 import fixture
from tools.inspect_level7 import inventory_level
from tools.inspect_temple import inventory_temple_level, summarize


def temple(number=10):
    data = fixture()
    struct.pack_into('>H', data, 0x2186, 2)
    struct.pack_into('>H', data, 0x218a, number)
    struct.pack_into('>h', data, 0x21a4, 7)
    return data


class TempleInventoryTests(unittest.TestCase):
    def test_all_four_level_identities_are_supported(self):
        for number in (10, 11, 12, 13):
            report = inventory_temple_level(temple(number), number)
            self.assertEqual((report['level'], report['resource_id']), (number, 1999 + number))

    def test_other_environments_sets_and_levels_are_rejected(self):
        for offset, value in ((0x2186, 4), (0x21a4, 5)):
            data = temple()
            struct.pack_into('>H', data, offset, value)
            with self.assertRaisesRegex(ValueError, 'temple'):
                inventory_temple_level(data, 10)
        data = temple(7)
        with self.assertRaisesRegex(ValueError, 'temple'):
            inventory_temple_level(data, 7)

    def test_mixed_raw_kinds_and_sequences_are_preserved(self):
        data = temple(12)
        offset = 0x20e6 + 6 * 0xc0
        struct.pack_into('>H', data, offset, 2)
        for index, kind, sequence in ((0, 7, 77), (1, 1, 105)):
            struct.pack_into('>h', data, offset + 2 + index * 38 + 0x18, kind)
            struct.pack_into('>h', data, offset + 2 + index * 38 + 8, sequence)
        report = inventory_temple_level(data, 12)
        self.assertEqual(report['generator_count'], 2)
        self.assertEqual(report['generator_kinds_and_sequences'], [
            dict(raw_kind=1, sequence=105, count=1), dict(raw_kind=7, sequence=77, count=1)])

    def test_candidate_locations_keep_native_room_and_cell_numbers(self):
        data = temple()
        struct.pack_into('>H', data, 31 * 60 + 29 * 2, 26)
        report = inventory_temple_level(data, 10)
        self.assertEqual(report['mechanism_cells']['26'], [
            dict(room=32, cell=29, foreground=0, reachable=True)])

    def test_absent_custom_resource_is_retained_as_a_candidate(self):
        data = temple(13)
        struct.pack_into('>H', data, 0x780 + 25 * 120, 0x8000)
        report = inventory_level(data, 13)
        report['missing_custom_resources'] = [4625]
        self.assertEqual(summarize(report)['custom_candidates'], [
            dict(room=26, resource=4625, reachable=False, present_in_scenery=False)])

    def test_surviving_checkpoint_slot_is_not_renumbered(self):
        data = temple(11)
        struct.pack_into('>4h', data, 0x39a6, 0, 0, 6, 17)
        self.assertEqual(inventory_temple_level(data, 11)['checkpoints'], [dict(slot=2, room=6, cell=17)])

    def test_raw_inventory_does_not_claim_resource_presence(self):
        data = temple(13)
        struct.pack_into('>H', data, 0x780, 0x8000)
        self.assertIsNone(inventory_temple_level(data, 13)['custom_candidates'][0]['present_in_scenery'])


if __name__ == '__main__':
    unittest.main()
