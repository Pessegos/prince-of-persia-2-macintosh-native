import json
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from pathlib import Path

from PIL import Image

from pop2.caverns import cavern_room
from pop2.level_data import LevelDefinition
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file
from pop2.terrain import LevelMap
from tools.render_cavern_map import room_positions


class CavernDrawingTests(unittest.TestCase):
    def test_native_clip_bounds_apply_to_pixels_and_foreground_masks(self):
        sprite = Image.new('RGBA', (8, 6), (200, 100, 30, 255))
        commands = [['front', 3501, 10, 20, 16, 1, [16, 12, 19, 16]]]
        program = {'version': 2, 'level': 3, 'rooms': {'4': commands}}
        with patch('pop2.caverns.cavern_assets', return_value=(program, {}, {}, {3501: sprite})):
            art = cavern_room(4)
        self.assertEqual((art.room_id, art.level_kind), (4, 3))
        self.assertEqual(art.foreground.getbbox(), (12, 16, 16, 19))
        self.assertEqual(art.actor_occlusion[1].getbbox(), (12, 16, 16, 19))
        self.assertIsNone(art.actor_occlusion[0].getbbox())
        self.assertEqual(art.foreground.getpixel((12, 16)), (200, 100, 30, 255))

    def test_empty_clip_does_not_draw(self):
        program = {'version': 2, 'level': 3, 'rooms': {
            '0': [['front', 3501, 10, 20, 16, 1, [100, 100, 110, 110]]]}}
        sprite = Image.new('RGBA', (8, 6), (200, 100, 30, 255))
        with patch('pop2.caverns.cavern_assets', return_value=(program, {}, {}, {3501: sprite})):
            art = cavern_room()
        self.assertIsNone(art.foreground.getbbox())


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class OriginalCavernTests(unittest.TestCase):
    def test_all_native_rooms_render_with_recorded_clip_rectangles(self):
        program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
        self.assertEqual(program['version'], 2)
        self.assertEqual(set(program['rooms']), {str(room) for room in range(32)})
        for room in range(32):
            with self.subTest(room=room):
                commands = program['rooms'][str(room)]
                self.assertTrue(commands)
                self.assertTrue(all(len(command) == 7 and len(command[6]) == 4 for command in commands))
                art = cavern_room(room)
                self.assertEqual(art.background.size, (510, 365))
                self.assertGreater(len(art.background.getcolors(510 * 365)), 20)
                self.assertIsNotNone(art.foreground.getbbox())

    def test_map_covers_all_original_rooms_and_matches_every_link(self):
        terrain = LevelMap(LevelDefinition.read(load_resource_file('Prince.rsrc'), 3).data)
        positions = room_positions(terrain)
        self.assertEqual(set(positions), set(range(32)))
        self.assertEqual(len(set(positions.values())), 32)
        offsets = {'left': (-1, 0), 'right': (1, 0), 'up': (0, -1), 'down': (0, 1)}
        for room, (x, y) in positions.items():
            for direction, (dx, dy) in offsets.items():
                neighbor = terrain.neighbor(room, direction)
                if neighbor is not None:
                    self.assertEqual(positions[neighbor], (x + dx, y + dy))

    def test_map_tool_writes_a_nonblank_native_map(self):
        from tools.render_cavern_map import render_map

        with TemporaryDirectory() as directory:
            output = render_map(Path(directory) / 'map.png')
            with Image.open(output) as image:
                self.assertEqual(image.size, (5610, 2304))
                self.assertIsNotNone(image.getbbox())

    def test_f2_can_load_every_room_and_place_on_original_standing_floor(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        self.assertEqual(scene.level_renderer.supported_rooms(), list(range(32)))
        entries = scene.level_renderer.screen_entries()
        self.assertEqual(len(entries), 32)
        for label, room in entries.items():
            with self.subTest(room=room):
                scene.jump_to_screen(label)
                self.assertEqual(scene.room_id, room)
                self.assertEqual(scene.room_cache[room].room_id, room)
                if room != scene.game.level.start_room:
                    column = (scene.player_x - 30) // 51
                    self.assertEqual(scene.level_map.tile(room, column, scene.terrain_motion.row).kind, 1)
                self.assertGreater(len(scene.native_viewport.getcolors(512 * 384)), 20)
                self.assertFalse(scene.terrain_motion.dead)

    def test_gameplay_crosses_the_original_link_outside_the_entrance(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        scene.jump_to_room(0, row=2, x=22, facing=0)
        scene.horizontal_key(None, -1, True)
        for _ in range(12):
            RooftopSceneTests.tick(self)
            if scene.room_id != 0:
                break
        self.assertEqual(scene.room_id, scene.level_map.neighbor(0, 'left'))
        self.assertEqual(scene.background, scene.room_cache[scene.room_id].background)
        self.assertFalse(scene.terrain_motion.dead)


if __name__ == '__main__':
    unittest.main()
