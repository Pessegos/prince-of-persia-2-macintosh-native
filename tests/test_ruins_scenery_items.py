"""Ruins shape IDs overlap the cave torch bank; preserve their native art."""

import unittest
from unittest.mock import patch

from PIL import Image

from pop2.caverns import cavern_assets, cavern_room, cavern_scene_signature
from pop2.cavern_state import CavernState
from pop2.paths import ASSET_DIR


class SharedSceneryNumberTests(unittest.TestCase):
    def test_torch_numbers_are_decoration_in_ruins_and_animation_in_caverns(self):
        for level in (3, 4, 5, 6, 7, 8, 9):
            for shape in range(3581, 3590):
                with self.subTest(level=level, shape=shape):
                    command = ['front', shape, 10, 10, 16, 0, [0, 0, 365, 510], 4, 0, 0]
                    program = {'version': 16, 'level': level, 'rooms': {'0': [command]}}
                    shapes = {shape: Image.new('RGBA', (2, 2), 'red')}
                    with patch('pop2.caverns.room_assets', return_value=(program, {}, {}, shapes)):
                        result = cavern_room(0, animated=True, level_number=level).flattened()
                    self.assertEqual(result.getpixel((10, 8)),
                                     (255, 0, 0, 255) if level >= 6 else (0, 0, 0, 255))


@unittest.skipUnless((ASSET_DIR / 'ruins_level6.json').is_file(), 'Imported ruins required')
class RuinsSceneryArtTests(unittest.TestCase):
    def test_room18_includes_the_complete_native_floor_crack(self):
        expected = cavern_room(17, level_number=6).flattened()
        actual = cavern_room(17, animated=True, level_number=6).flattened()
        self.assertTrue(actual.tobytes() == expected.tobytes())

    def test_all_item_free_ruins_rooms_preserve_the_static_scenery_in_live_mode(self):
        checked = 0
        for level in (6, 7, 8, 9):
            program, *_ = cavern_assets(level)
            for room, commands in program['rooms'].items():
                # Pickups have separate runtime drawing; every library4 piece
                # in these rooms must stay in the live scenery exactly.
                if any(command[7] in (0, 1) for command in commands):
                    continue
                with self.subTest(level=level, room=int(room) + 1):
                    expected = cavern_room(int(room), level_number=level).flattened()
                    actual = cavern_room(int(room), animated=True, level_number=level).flattened()
                    self.assertTrue(actual.tobytes() == expected.tobytes())
                    checked += 1
        self.assertGreaterEqual(checked, 100)

    def test_revealed_tunnel_ceilings_and_floor_edges_match_the_complete_drawing(self):
        state = CavernState()
        program, *_ = cavern_assets(6)
        # The actual cross-room tunnel in the supplied recording.
        for room, cell, foreground in ((16, 18, 130), (16, 19, 129), (17, 10, 128)):
            state.loose.tiles[room, cell] = 7, foreground
            state.loose.redrawn.add((room, cell))
        for room, rect in ((16, (380, 120, 510, 250)), (17, (0, 120, 100, 250))):
            with self.subTest(room=room + 1):
                signature = cavern_scene_signature(program, room, state)
                options = dict(loose_key=signature, redrawn=frozenset(state.loose.redrawn), level_number=6)
                expected = cavern_room(room, **options).flattened().crop(rect)
                actual = cavern_room(room, animated=True, **options).flattened().crop(rect)
                self.assertTrue(actual.tobytes() == expected.tobytes())
