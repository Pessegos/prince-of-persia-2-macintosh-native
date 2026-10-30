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


if __name__ == '__main__':
    unittest.main()
