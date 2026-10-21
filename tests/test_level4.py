import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image

from pop2.cavern_state import CavernState
from pop2.caverns import _cavern_assets, cavern_assets, cavern_room
from pop2.level_data import LevelDefinition
from pop2.level_rendering import LevelRenderer
from pop2.paths import ASSET_DIR
from pop2.render_opening import load_resource_file


class CavernLevelIsolationTests(unittest.TestCase):
    def test_program_and_decoded_sprite_caches_are_separate_and_default_means_level_three(self):
        _cavern_assets.cache_clear()
        self.addCleanup(_cavern_assets.cache_clear)
        with TemporaryDirectory() as directory:
            directory = Path(directory)
            for number, name in ((3, 'caverns_entry.json'), (4, 'caverns_level4.json')):
                (directory / name).write_text(json.dumps({'level': number}), encoding='ascii')
            with (patch('pop2.caverns.ASSET_DIR', directory),
                  patch('pop2.caverns.load_resource_file', return_value={'CTBL': {3500: {'data': b''}}}),
                  patch('pop2.caverns.decode_ctbl', return_value={})):
                three, four = cavern_assets(), cavern_assets(4)
                self.assertIs(cavern_assets(3), three)
                self.assertIs(cavern_assets(4), four)
                three[3]['sentinel'] = object()
                self.assertNotIn('sentinel', four[3])
                self.assertEqual((three[0]['level'], four[0]['level']), (3, 4))

    def test_export_identity_is_checked_before_drawing(self):
        _cavern_assets.cache_clear()
        self.addCleanup(_cavern_assets.cache_clear)
        with TemporaryDirectory() as directory:
            directory = Path(directory)
            (directory / 'caverns_level4.json').write_text('{"level": 3}', encoding='ascii')
            with (patch('pop2.caverns.ASSET_DIR', directory),
                  self.assertRaisesRegex(ValueError, 'different level')):
                cavern_assets(4)
        for number in (True, 2, 5, '4'):
            with self.subTest(number=number), self.assertRaisesRegex(ValueError, 'Unsupported cavern'):
                cavern_assets(number)

    def test_level_three_artwork_retouch_is_never_applied_to_level_four(self):
        program = {'version': 14, 'level': 4, 'rooms': {'0': [['back', 3501, 0, 1, 16, 0]]}}
        sprite = Image.new('RGBA', (1, 1), 'red')
        with (patch('pop2.caverns.cavern_assets', return_value=(program, {}, {}, {3501: sprite})),
              patch('pop2.caverns.retouched_sprite', side_effect=AssertionError('Level-three artwork'))):
            room = cavern_room(0, retouched=True, level_number=4)
        self.assertEqual(room.background.getpixel((0, 0)), (255, 0, 0, 255))

    def test_renderer_routes_static_and_animated_drawing_to_the_selected_level(self):
        program = {'torches': {}}
        level = SimpleNamespace(number=4, kind=3, start_room=0, data=b'')
        with patch('pop2.caverns.cavern_assets', return_value=(program, None, None, None)) as assets:
            renderer = LevelRenderer(level, preload_room=False)
            assets.assert_called_once_with(4)
        room = object()
        with patch('pop2.caverns.cavern_room', return_value=room) as draw:
            self.assertIs(renderer.room(0), room)
            self.assertEqual(draw.call_args.kwargs['level_number'], 4)
        renderer.cavern_map = object()
        frame = Image.new('RGBA', (1, 1))
        with (patch('pop2.caverns.draw_cavern_flasks', return_value=frame) as flasks,
              patch('pop2.caverns.draw_cavern_spikes', return_value=frame) as spikes):
            renderer.animated_layer(frame, 0, None, front=True, caverns=CavernState())
            self.assertEqual(flasks.call_args.kwargs['level_number'], 4)
            self.assertEqual(spikes.call_args.kwargs['level_number'], 4)


@unittest.skipUnless((ASSET_DIR / 'caverns_level4.json').is_file(), 'Imported level-four resources required')
class LevelFourSceneryTests(unittest.TestCase):
    def test_level_four_export_has_its_own_start_and_all_room_layers(self):
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 4)
        program = cavern_assets(4)[0]
        self.assertEqual((level.kind, level.start_room, level.start_tile, level.start_x, level.facing),
                         (3, 0, 25, 277, 0))
        self.assertEqual((program['version'], program['level']), (15, 4))
        rooms = {str(room) for room in range(32)}
        for key in ('rooms', 'torches', 'climb_redraw', 'floor_redraw'):
            self.assertEqual(set(program[key]), rooms)
        self.assertEqual(program['entry_exit']['room'], level.start_room)
        self.assertEqual(program['entry_exit']['cell'], 25)
        self.assertNotEqual(program['rooms'], cavern_assets(3)[0]['rooms'])

    def test_room_nineteen_keeps_the_native_decoration_beneath_an_upper_room_loose_floor(self):
        # DrawCaveFloorCommon 8:1998 reads the upper room from room setup.
        commands = cavern_assets(4)[0]['rooms']['18']
        self.assertIn(['front', 3604, 306, 23, 16, 0, [5, 306, 23, 356], 4, 6, 0], commands)

    def test_all_rooms_and_animated_layers_render_without_reusing_level_three(self):
        level = LevelDefinition.read(load_resource_file('Prince.rsrc'), 4)
        renderer = LevelRenderer(level, preload_room=False)
        world = CavernState()
        world.configure_entry(renderer.cavern_program.get('entry_exit'))
        world.configure_torches(renderer.cavern_program.get('torches', {}))
        world.configure_lava(renderer.cavern_program.get('lava'))
        self.assertEqual(renderer.supported_rooms(), list(range(32)))
        self.assertEqual(len(renderer.screen_entries()), 32)
        for room_id in range(32):
            with self.subTest(room=room_id):
                room = renderer.enter_room(room_id, world)
                frame = renderer.animated_layer(room.background.copy(), room_id, None, caverns=world)
                frame = Image.alpha_composite(frame, room.foreground)
                frame = renderer.animated_layer(frame, room_id, None, front=True, caverns=world)
                self.assertEqual(frame.size, (510, 365))
                self.assertEqual(frame.getchannel('A').getextrema(), (255, 255))


if __name__ == '__main__':
    unittest.main()
