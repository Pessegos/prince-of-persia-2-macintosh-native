import json
import struct
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from pathlib import Path

from PIL import Image

from pop2.caverns import cavern_room, flask_shape, flask_assets
from pop2.cavern_state import CavernState
from pop2.level_data import LevelDefinition
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file
from pop2.terrain import LevelMap
from tools.render_cavern_map import room_positions
from tools.extract_caverns import exit_closing_frames


class CavernDrawingTests(unittest.TestCase):
    def test_dock_waterline_does_not_clip_cavern_actors_in_same_numbered_rooms(self):
        from pop2.scene_prototype import ScenePrototype

        scene = ScenePrototype.__new__(ScenePrototype)
        scene.game = SimpleNamespace(room_id=0, level=SimpleNamespace(kind=3))
        scene.foreground = Image.new('RGBA', (510, 365))
        background = Image.new('RGBA', (510, 365), 'black')
        for room in (15, 18):
            scene.room_id = room
            for kind, animation, visible in ((3, 0, True), (3, 9, True),
                                             (5, 0, False), (5, 9, True)):
                with self.subTest(room=room, kind=kind, animation=animation):
                    layer = Image.new('RGBA', background.size, 'magenta')
                    state = SimpleNamespace(level_kind=kind, animation_state=animation)
                    frame = scene.composite_actor(background, layer, state=state)
                    self.assertEqual(frame.getpixel((250, 340)),
                                     (255, 0, 255, 255) if visible else (0, 0, 0, 255))
                    self.assertEqual(frame.getpixel((250, 360)),
                                     (255, 0, 255, 255) if kind == 3 else (0, 0, 0, 255))

    def test_monochrome_flask_uses_native_whole_bitmap_rle_and_ink_color(self):
        data = struct.pack('>HhhH2H', 0x9200, 2, 9, 2, 0, 0) + bytes([1, 128, 128, 0])
        colors = {233: (25, 112, 217, 255)}
        image = flask_shape(data, colors, 233)
        self.assertEqual(image.size, (9, 2))
        self.assertEqual(image.getpixel((0, 0)), colors[233])
        self.assertEqual(image.getpixel((1, 0)), (0, 0, 0, 0))
        self.assertEqual(image.getpixel((0, 1)), (0, 0, 0, 0))

    def test_monochrome_flask_rejects_truncation_and_run_overflow(self):
        header = struct.pack('>HhhH2H', 0x9200, 2, 9, 2, 0, 0)
        for body in (b'', bytes([128]), bytes([130, 0]), bytes([0])):
            with self.subTest(body=body), self.assertRaises(ValueError):
                flask_shape(header + body, {233: (1, 2, 3, 255)}, 233)

    def test_flask_library_is_not_decoded_with_the_cavern_palette(self):
        commands = [['front', 3001, 10, 20, 16, 1, [0, 0, 365, 510], 1]]
        program = {'version': 3, 'level': 3, 'rooms': {'0': commands}}
        data = b'flask'
        colors = {225: (250, 250, 198, 255)}
        sprite = Image.new('RGBA', (12, 16), colors[225])
        with (patch('pop2.caverns.cavern_assets', return_value=(program, {}, {}, {})),
              patch('pop2.caverns.flask_assets', return_value=({'SHAP': {3001: {'data': data}}}, colors)),
              patch('pop2.caverns.flask_shape', return_value=sprite) as decode):
            art = cavern_room()
        decode.assert_called_once_with(data, colors, 16)
        self.assertEqual(art.foreground.getbbox(), (10, 4, 22, 20))

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


class CavernEntryTests(unittest.TestCase):
    def test_closing_frames_are_extracted_from_the_native_table(self):
        data = bytearray(0x5000)
        struct.pack_into('>2h', data, len(data) - 0x45fc + 10, 32, 200)
        with patch('tools.extract_caverns.expand_a5_data', return_value=bytes(data)):
            frames = exit_closing_frames({})
        self.assertEqual(frames, [{'phase': 79, 'sounds': []},
                                  {'phase': 47, 'sounds': []},
                                  {'phase': 0, 'sounds': [20]}])

    def test_entry_advances_phases_preserves_upper_flags_and_sounds_once(self):
        state = CavernState()
        state.configure_entry({'room': 4, 'cell': 16, 'frames': [
            {'phase': 79, 'sounds': []}, {'phase': 47, 'sounds': []},
            {'phase': 0, 'sounds': [20]}]})
        self.assertEqual(state.foreground(4, 16, 0x7f4f), 0x7f4f)
        self.assertEqual(state.advance(), ())
        self.assertEqual(state.foreground(4, 16, 0x7f4f), 0x7f2f)
        self.assertEqual(state.foreground(4, 17, 0x7f4f), 0x7f4f)
        self.assertEqual(state.advance(), (20,))
        self.assertEqual(state.foreground(4, 16, 0x7f4f), 0x7f00)
        for _ in range(5):
            self.assertEqual(state.advance(), ())


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class OriginalCavernTests(unittest.TestCase):
    def test_all_native_rooms_render_with_recorded_clip_rectangles(self):
        program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
        self.assertEqual(program['version'], 3)
        self.assertEqual(set(program['rooms']), {str(room) for room in range(32)})
        for room in range(32):
            with self.subTest(room=room):
                commands = program['rooms'][str(room)]
                self.assertTrue(commands)
                self.assertTrue(all(len(command) == 8 and len(command[6]) == 4 for command in commands))
                self.assertTrue(all(command[7] in (1, 4) for command in commands))
                art = cavern_room(room)
                self.assertEqual(art.background.size, (510, 365))
                self.assertGreater(len(art.background.getcolors(510 * 365)), 20)
                self.assertIsNotNone(art.foreground.getbbox())

    def test_original_flasks_use_prince_shapes_and_small_colored_masks(self):
        program = json.loads((ASSET_DIR / 'caverns_entry.json').read_text(encoding='ascii'))
        source, colors = flask_assets()
        requests = [command for commands in program['rooms'].values() for command in commands if command[7] == 1]
        self.assertTrue(requests)
        for command in requests:
            self.assertTrue(3001 <= command[1] <= 3033)
            image = flask_shape(source['SHAP'][command[1]]['data'], colors, command[4])
            self.assertLessEqual(image.width, 30)
            self.assertLessEqual(image.height, 64)
            self.assertIsNotNone(image.getbbox())

    def test_entry_closes_updates_scenery_and_resets_on_restart(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(3)
        original = scene.background.copy()
        self.assertEqual(scene.level_map.tile(0, 4, 1).foreground & 255, 79)
        scene.advance_level_events()
        self.assertEqual(scene.level_map.tile(0, 4, 1).foreground & 255, 47)
        scene.advance_level_events()
        self.assertEqual(scene.level_map.tile(0, 4, 1).foreground & 255, 0)
        self.assertIn(20, scene.sequence_state.sound_events)
        self.assertNotEqual(scene.background.tobytes(), original.tobytes())
        scene.sequence_state.sound_events.clear()
        scene.advance_level_events()
        self.assertNotIn(20, scene.sequence_state.sound_events)
        scene.restart_opening(play_sound=False)
        self.assertEqual(scene.level_map.tile(0, 4, 1).foreground & 255, 79)
        self.assertEqual(scene.background.tobytes(), original.tobytes())

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
