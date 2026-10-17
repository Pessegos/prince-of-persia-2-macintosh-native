import struct
import unittest

from pop2.development_entry import STANDING_TILES, cavern_entry
from pop2.paths import ASSET_DIR
from pop2.terrain import LevelMap


class DevelopmentEntryTests(unittest.TestCase):
    def setUp(self):
        self.level = bytearray(0x49ca)
        struct.pack_into('>H', self.level, 0x2186, 3)
        for room in range(2):
            for row in range(3):
                for column in range(10):
                    self.tile(room, row, column, 20)
        struct.pack_into('>H', self.level, 0x2082, 2)
        struct.pack_into('>H', self.level, 0x2088, 1)
        for column in range(6, 10):
            self.tile(0, 2, column, 1)
        self.tile(1, 2, 0, 1)
        self.terrain = LevelMap(self.level)

    def tile(self, room, row, column, kind, foreground=0):
        cell = row * 10 + column
        struct.pack_into('>H', self.level, room * 60 + cell * 2, kind)
        struct.pack_into('>H', self.level, 0x780 + room * 120 + cell * 4, foreground)

    def test_centered_floor_inside_sealed_rock_is_not_an_entry(self):
        self.tile(0, 0, 4, 1)
        self.tile(0, 0, 5, 1)
        self.assertEqual(cavern_entry(self.terrain, 0), (2, 6))

    def test_floor_does_not_connect_through_its_solid_bottom(self):
        self.tile(0, 1, 5, 1)
        self.tile(0, 2, 5, 0)
        self.assertEqual(cavern_entry(self.terrain, 0, preferred_row=1), (2, 6))

    def test_loose_floor_opening_can_connect_an_upper_potion_platform(self):
        self.tile(0, 1, 5, 1)
        self.tile(0, 1, 6, 11)
        self.assertEqual(cavern_entry(self.terrain, 0, preferred_row=1), (1, 5))

    def test_room_link_into_solid_rock_is_not_an_exit(self):
        self.tile(1, 2, 0, 20)
        with self.assertRaisesRegex(ValueError, 'accessible standing floor'):
            cavern_entry(self.terrain, 0)

    def test_closed_gate_separates_pockets_but_live_opening_reconnects_them(self):
        self.tile(0, 2, 4, 1)
        self.tile(0, 2, 5, 1)
        self.tile(0, 2, 6, 4)
        for column in range(7, 10):
            self.tile(0, 2, column, 3)
        self.assertEqual(cavern_entry(self.terrain, 0), (2, 7))
        self.tile(0, 2, 6, 4, 184)
        self.assertEqual(cavern_entry(self.terrain, 0), (2, 5))

    def test_stable_decorated_floor_is_available_when_plain_floor_is_sealed(self):
        self.tile(0, 0, 5, 1)
        for column, kind in ((6, 19), (7, 10), (8, 11), (9, 34)):
            self.tile(0, 2, column, kind)
        self.assertEqual(cavern_entry(self.terrain, 0), (2, 6))
        self.assertTrue(STANDING_TILES.isdisjoint((2, 4, 11, 12, 13, 23, 24, 33, 34)))

    def test_selection_is_deterministic_and_does_not_modify_the_map(self):
        before = bytes(self.level)
        self.assertEqual([cavern_entry(self.terrain, 0) for _ in range(4)], [(2, 6)] * 4)
        self.assertEqual(bytes(self.level), before)

    def test_live_gate_and_removed_floor_state_is_read_without_resetting_it(self):
        from pop2.cavern_state import CavernState

        caverns = self.terrain.caverns = CavernState()
        self.tile(0, 1, 5, 1)
        self.tile(0, 1, 6, 11)
        self.tile(0, 2, 6, 4)
        caverns.loose.tiles[0, 16] = (0, 3)
        self.assertEqual(cavern_entry(self.terrain, 0, preferred_row=1), (2, 7))
        caverns.plates.foreground[0, 26] = 184
        caverns.plates.active[0, 26] = 2
        before = (caverns.loose.tiles.copy(), caverns.plates.foreground.copy(),
                  caverns.plates.active.copy())
        self.assertEqual(cavern_entry(self.terrain, 0, preferred_row=1), (1, 5))
        self.assertEqual((caverns.loose.tiles, caverns.plates.foreground,
                          caverns.plates.active), before)


@unittest.skipUnless((ASSET_DIR / 'Prince.rsrc').is_file(), 'Imported game resources required')
class ImportedDevelopmentEntryTests(unittest.TestCase):
    def test_original_sealed_pockets_are_rejected_in_all_affected_rooms(self):
        from pop2.render_opening import load_resource_file

        terrain = LevelMap(load_resource_file('Prince.rsrc')['LEVL'][2002]['data'])
        expected = {3: (0, 2), 12: (2, 2), 15: (2, 5), 19: (2, 2),
                    21: (2, 7), 28: (2, 7), 31: (1, 2), 32: (2, 6)}
        for room, cell in expected.items():
            with self.subTest(room=room):
                self.assertEqual(cavern_entry(terrain, room - 1,
                                 preferred_row=2 if room == 21 else None), cell)
        for room in range(32):
            row, column = cavern_entry(terrain, room, preferred_row=2 if room == 20 else None)
            self.assertIn(terrain.tile(room, column, row).kind, STANDING_TILES)

    def test_every_non_entry_room_can_idle_and_start_a_cautious_step_after_f3(self):
        from unittest.mock import patch
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        with patch.object(scene, 'render'):
            for room in range(1, 32):
                with self.subTest(room=room + 1):
                    scene.load_level(3)
                    scene.peaceful = True
                    scene.jump_to_screen(f'Room {room + 1}')
                    origin = scene.player_x
                    row = scene.terrain_motion.row
                    for _ in range(4):
                        RooftopSceneTests.tick(self)
                    self.assertEqual((scene.room_id, scene.player_x, scene.terrain_motion.row),
                                     (room, origin, row))
                    self.assertFalse(scene.terrain_motion.dead or scene.terrain_motion.falling)
                    # Try each direction from a fresh warp; a sealed pocket
                    # cannot make progress in either direction.
                    moved = False
                    for direction in (-1, 1):
                        scene.jump_to_screen(f'Room {room + 1}')
                        scene.shift_held = True
                        # Shift-turn and the ledge warning each deliberately
                        # consume a press; re-press before testing the step.
                        for _ in range(3):
                            scene.horizontal_key(None, direction, True)
                            for _ in range(18):
                                RooftopSceneTests.tick(self)
                                if (scene.room_id != room or scene.terrain_motion.row != row
                                        or abs(scene.player_x - origin) >= 18):
                                    moved = True
                                    break
                            scene.horizontal_key(None, direction, False)
                            if moved:
                                break
                        if moved:
                            break
                    self.assertTrue(moved)
                    self.assertFalse(scene.terrain_motion.dead)


if __name__ == '__main__':
    unittest.main()
