import struct
import unittest

from pop2.crevices import crevice_group, front_crevice_group, hide_crevices
from pop2.terrain import LevelMap


def ruins_level():
    level = bytearray(0x49ca)
    struct.pack_into('>H', level, 0x2186, 4)
    # Room 1's right neighbour is room 2; a crevice run crosses the join.
    struct.pack_into('>H', level, 0x2080 + 0 * 8 + 2, 2)
    struct.pack_into('>H', level, 0x2080 + 1 * 8 + 0, 1)
    for room, cell, foreground in ((0, 18, 0x82), (0, 19, 0x81), (1, 10, 0x80), (1, 13, 0x83)):
        struct.pack_into('>H', level, room * 60 + cell * 2, 7)
        struct.pack_into('>H', level, 0x780 + room * 120 + cell * 4, foreground)
    return bytes(level)


class CreviceTests(unittest.TestCase):
    def test_init_state_covers_every_crevice(self):
        # InitState 3:5dce-5e04 clears bit 0x80 of tile 7 only.
        level = hide_crevices(ruins_level())
        values = [struct.unpack_from('>H', level, 0x780 + room * 120 + cell * 4)[0]
                  for room, cell in ((0, 18), (0, 19), (1, 10), (1, 13))]
        self.assertEqual(values, [0x02, 0x01, 0x00, 0x03])

    def test_the_scan_takes_the_first_run_of_the_row_across_room_links(self):
        terrain = LevelMap(hide_crevices(ruins_level()))
        self.assertEqual(crevice_group(terrain, 0, 3, 1), ((0, 18), (0, 19), (1, 10)))
        self.assertEqual(crevice_group(terrain, 1, 5, 1), ((0, 18), (0, 19), (1, 10)))
        self.assertEqual(crevice_group(terrain, 0, 3, 0), ())

    def test_only_a_crouching_prince_facing_a_crevice_reveals_it(self):
        terrain = LevelMap(hide_crevices(ruins_level()))
        group = ((0, 18), (0, 19), (1, 10))
        self.assertEqual(front_crevice_group(terrain, 0, 7, 1, 1, 117), group)
        self.assertEqual(front_crevice_group(terrain, 0, 7, 1, 0, 117), ())
        # 7:3404 rejects selected SEQS 17 and a front crevice with low bits 3.
        self.assertEqual(front_crevice_group(terrain, 0, 7, 1, 1, 17), ())
        self.assertEqual(front_crevice_group(terrain, 1, 2, 1, 1, 117), ())


if __name__ == '__main__':
    unittest.main()
