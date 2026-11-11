"""Final tower palette and retained scenery from Macintosh room references."""

import unittest

from pop2.paths import ASSET_DIR


@unittest.skipUnless(all((ASSET_DIR / name).is_file()
                         for name in ('Final.rsrc', 'final_level14.json')),
                     'Imported final scenery required')
class FinalSceneryTests(unittest.TestCase):
    def test_final_room_colours_follow_original_palette_changes(self):
        from pop2.caverns import cavern_room

        # Fixed pixels in the Macintosh CUST backgrounds: the tree, chess
        # floor, crystals and palace have different colour-table banks.
        self.assertEqual(cavern_room(2, level_number=14).background.getpixel((255, 180)),
                         (50, 33, 20, 255))
        self.assertEqual(cavern_room(3, level_number=14).background.getpixel((100, 100)),
                         (34, 17, 39, 255))
        self.assertEqual(cavern_room(5, level_number=14).background.getpixel((100, 100)),
                         (144, 104, 64, 255))
        self.assertEqual(cavern_room(6, level_number=14).background.getpixel((255, 180)),
                         (144, 104, 64, 255))

    def test_rooms_nine_and_ten_retain_the_previous_scene(self):
        from PIL import ImageChops

        from pop2.caverns import cavern_room

        tree = cavern_room(2, level_number=14)
        tree_return = cavern_room(8, level_number=14)
        palace = cavern_room(7, level_number=14)
        palace_return = cavern_room(9, level_number=14)
        self.assertIsNone(ImageChops.difference(tree.background, tree_return.background).getbbox())
        self.assertIsNone(ImageChops.difference(palace.background, palace_return.background).getbbox())
        self.assertIsNotNone(palace_return.foreground.getbbox())
