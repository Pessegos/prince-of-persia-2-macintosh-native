import unittest

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / 'ruins_level6.json').is_file(), 'Imported level-six resources required')
class LevelSixSceneryTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(6)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_level_six_starts_on_the_cliff_with_its_custom_palette(self):
        from pop2.caverns import room_assets

        scene = self.scene
        self.tick(4)
        state = scene.sequence_state
        self.assertEqual((scene.room_id, state.sequence_id, state.target_x), (26, 2, 167))
        self.assertIsNotNone(scene.game.caverns)
        # CUST kind 22's enter hook 7:37a6 loads CTBL 3502 over entry 64.
        _program, resources, palette, _shapes = room_assets(6, 26)
        self.assertNotEqual(palette[64], room_assets(6, 0)[2][64])
        self.assertEqual(scene.level_renderer.cavern_program['level'], 6)

    def test_the_sword_item_room_draws_from_the_sword_library(self):
        scene = self.scene
        scene.jump_to_room(16, 1, 100, 1)
        program = scene.level_renderer.cavern_program
        self.assertIn(1046, [command[1] for command in program['rooms']['16'] if command[7] == 0])
        self.tick()
        self.assertEqual(scene.room_id, 16)


if __name__ == '__main__':
    unittest.main()
