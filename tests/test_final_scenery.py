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

    def test_shared_views_keep_distinct_native_room_links_and_terrain(self):
        from pop2.game_session import GameResources
        from pop2.terrain import LevelMap

        level = LevelMap(GameResources.load().level(14).data)
        # 3/9 and 8/10 are two camera views, but each number has its own
        # LEVL links and collision grid. Native numbers are one-based here.
        self.assertEqual(level.neighbor(2, 'right'), 8)
        self.assertEqual(level.neighbor(8, 'left'), 2)
        self.assertEqual(level.neighbor(7, 'up'), 9)
        self.assertEqual(level.neighbor(9, 'down'), 7)
        self.assertEqual([level.tile(8, column, 2).kind for column in range(10)],
                         [20, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        self.assertEqual([level.tile(9, column, 2).kind for column in range(10)],
                         [0] * 10)
        self.assertTrue(any(level.tile(2, column, 2).kind == 1 for column in range(10)))
        self.assertTrue(any(level.tile(7, column, 2).kind == 1 for column in range(10)))
