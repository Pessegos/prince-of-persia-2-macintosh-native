import unittest

from pop2.paths import ASSET_DIR


class CarpetExportTests(unittest.TestCase):
    def test_flag_eight_animations_restore_the_background_under_moved_layers(self):
        # PlayTheAnimation 16:121c and 16:1378-13bc.
        import struct
        from tools.extract_intro import expand_animations

        body = (bytes((5, 6)) + struct.pack('>2h', 1, 1) + bytes((1, 2))
                + bytes((6, 8)) + struct.pack('>3h', 1, 3, 0) + bytes((1, 2)) + bytes((0, 2)))
        script = struct.pack('>I', len(body)) + body
        resources = {'ANI ': {100001: {'data': struct.pack('>9h', 0, 0, 10, 10, 1, 7, 0, 0, 0)}},
                     'SCRP': {100007: {'data': script}},
                     'SHAP': {100001: {'data': struct.pack('>HhhH', 0, 0, 4, 3)}}}
        operations = [{'op': 'animation', 'args': [100000, 1, 5, 6], 'pc': 0, 'flags': 0x1c}]
        result = expand_animations(operations, resources)
        self.assertEqual([(item['op'], item['args']) for item in result], [
            ('save_background', []),
            ('shape', [100001, 5, 6, 16]), ('copy', [[6, 5, 9, 9]]), ('wait', [3]),
            ('restore', [[6, 5, 9, 9]]), ('shape', [100001, 8, 6, 16]),
            ('copy', [[6, 5, 9, 9]]), ('copy', [[6, 8, 9, 12]]), ('wait', [3])])


@unittest.skipUnless((ASSET_DIR / 'carpet.json').is_file(), 'Imported carpet scene required')
class CarpetSceneTests(unittest.TestCase):
    def test_the_scene_flies_over_the_sea_and_lands_on_the_cliff(self):
        from pop2.intro import IntroAssets, IntroPlayer

        assets = IntroAssets(program_name='carpet.json')
        self.assertEqual(set(assets.program['resource_files']),
                         {'TNIS1.rsrc', 'TNIS2.rsrc', 'TNIS3.rsrc', 'Ruins.rsrc', 'Caverns.rsrc'})
        player = IntroPlayer(assets)
        player.advance(60)
        self.assertTrue(player.done)
        self.assertGreater(player.time, 20)
        ops = [item['op'] for item in assets.program['operations']]
        self.assertIn('palette_at', ops)
        self.assertEqual(ops.count('save_background'), 3)

    def test_finishing_level_five_plays_the_carpet_scene_then_loads_level_six(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(5)
        scene.finish_level_via_story(5, 6)
        self.assertEqual((scene.attract_stage, scene.next_level_after_tree), ('tree', 6))
        self.assertIs(scene.intro.assets, scene.carpet_assets)
        scene.finish_tree()
        self.assertEqual(scene.game.level.number, 6)
        self.assertIsNone(scene.intro)


if __name__ == '__main__':
    unittest.main()
