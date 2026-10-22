import unittest

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported level-five resources required')
class CeilingBarsSceneTests(unittest.TestCase):
    """Room 3's plate (cell 8, link 17) and ceiling bars (cell 6, tile 27)."""

    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(5)
        self.tick(16)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_export_draws_the_closed_bars_and_records_both_pressure_slots(self):
        from pop2.caverns import cavern_assets

        program = cavern_assets(5)[0]
        bars = [command for command in program['rooms']['2'] if command[1] == 4051]
        self.assertEqual(bars, [['back', 4051, 165, 50, 0, 0, [10, 165, 50, 318], 4, 6, 0]])
        records = program['pressure_plates']['rooms']['2']
        self.assertEqual([(record['cell'], record['kind']) for record in records], [(6, 27), (8, 34)])

    def test_stepping_on_the_upper_right_plate_opens_the_bars(self):
        scene = self.scene
        self.assertEqual(scene.level_map.tile(2, 6, 0).kind, 27)
        scene.jump_to_room(2, 0, 445, 1)
        self.tick(12)
        self.assertEqual(scene.level_map.tile(2, 6, 0).foreground & 7, 3)
        from pop2.caverns import cavern_pressure_signature

        program = scene.level_renderer.cavern_program
        self.assertEqual(cavern_pressure_signature(program, 2, scene.game.caverns)[0], 3)
