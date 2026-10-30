import unittest

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / 'ruins_level9.json').is_file(), 'Imported level-nine resources required')
class LevelNineHorseTests(unittest.TestCase):
    def test_the_horse_stands_on_its_pedestal_in_native_room_two(self):
        # 3:23e4-2418 / 3:4608: Prince SHAP 25360, mirrored, at (252, 40).
        from pop2.caverns import HORSE_TOP_LEFT, cavern_room, horse_sprite

        sprite = horse_sprite()
        self.assertEqual(sprite.size, (130, 154))
        room = cavern_room(1, level_number=9).background
        x, y = HORSE_TOP_LEFT
        visible = [(dx, dy) for dx in range(0, sprite.width, 3) for dy in range(0, sprite.height, 3)
                   if sprite.getpixel((dx, dy))[3]]
        self.assertTrue(visible)
        self.assertTrue(all(room.getpixel((x + dx, y + dy)) == sprite.getpixel((dx, dy))
                            for dx, dy in visible))
        # FreeShpInfo(1) in level nine: the stored shape mirrored.
        from PIL import ImageOps
        from pop2.render_opening import decode_ctbl, decode_shap, load_resource_file
        prince = load_resource_file('Prince.rsrc')
        stored = decode_shap(prince['SHAP'][25360]['data'], decode_ctbl(prince['CTBL'][25360]['data']))
        self.assertEqual(sprite.tobytes(), ImageOps.mirror(stored).tobytes())

    def test_no_other_room_draws_the_horse(self):
        from pop2.caverns import HORSE_TOP_LEFT, cavern_room, horse_sprite

        sprite = horse_sprite()
        x, y = HORSE_TOP_LEFT
        for level, room in ((9, 2), (8, 1)):
            with self.subTest(level=level, room=room):
                background = cavern_room(room, level_number=level).background
                region = background.crop((x, y, x + sprite.width, y + sprite.height))
                self.assertNotEqual(region.tobytes(), sprite.tobytes())


class LevelNineExitTests(unittest.TestCase):
    def test_leaving_level_nine_plays_the_ride_then_completes(self):
        # CheckPlayNIS(9, 10): NIS 2 first; level ten is not available, so
        # the level ends with its status message after the scene.
        from types import SimpleNamespace
        from pop2.environments import Ruins

        calls = []
        status = SimpleNamespace(set=calls.append)
        scene = SimpleNamespace(game=SimpleNamespace(level=SimpleNamespace(number=9), exit=object()),
                                status=status)
        finishes = []
        scene.start_temple_ride = lambda finish: finishes.append(finish) or True
        Ruins(scene).finish_exit()
        self.assertEqual(calls, [])
        finishes[0]()
        self.assertIsNone(scene.game.exit)
        self.assertEqual(calls, ['Level 9 complete'])
        scene.start_temple_ride = lambda finish: False
        scene.game.exit = object()
        Ruins(scene).finish_exit()
        self.assertIsNone(scene.game.exit)


if __name__ == '__main__':
    unittest.main()


class TempleSceneryNamingTests(unittest.TestCase):
    def test_temple_levels_use_temple_scenery_files(self):
        from pop2.caverns import TEMPLE_LEVELS, scenery_name, scenery_resource

        self.assertEqual(TEMPLE_LEVELS, (10, 11, 12, 13))
        self.assertEqual((scenery_name(10), scenery_resource(13)), ('temple_level10.json', 'Temple.rsrc'))
        self.assertEqual((scenery_name(9), scenery_resource(9)), ('ruins_level9.json', 'Ruins.rsrc'))
        self.assertEqual(scenery_name(3), 'caverns_entry.json')
