"""Isolated reproductions of the November ruins playtest reports."""

import unittest

from pop2.paths import ASSET_DIR


@unittest.skipUnless((ASSET_DIR / 'ruins_level9.json').is_file(), 'Imported ruins required')
class RuinsBugReportTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def test_falling_tile_on_scythe_survives_every_animation_phase(self):
        from pop2.caverns import cavern_scythe_signature
        from pop2.environments import environment_for
        from pop2.loose_floors import FallingFloor
        from pop2.scythes import SCYTHE_STATES

        scene = self.scene
        scene.load_level(7)
        scene.jump_to_room(7, 2, 250, 0)
        scene.peaceful = True
        caverns = scene.game.caverns
        traps = [(c, r) for r in range(3) for c in range(10)
                 if scene.level_map.tile(7, c, r).kind == 13]
        self.assertTrue(traps)
        column, row = traps[0]
        caverns.loose.falling.append(FallingFloor(7, column, row, row * 120 + 115, 8, 3))
        environment_for(scene).frame_start()
        self.assertTrue(scene.level_map.tile(7, column, row).foreground & 0x20)
        key = (7, row * 10 + column)
        caverns.scythes.active.add(key)
        phases = []
        for _ in range(22):
            caverns.scythes.advance(scene.level_map)
            phases.append(scene.level_map.tile(7, column, row).foreground & 0x1f)
            signature = cavern_scythe_signature(scene.level_renderer.cavern_program, 7, caverns)
            self.assertTrue(all(0 <= index < len(SCYTHE_STATES) for index in signature[1]))
            scene.render()
        self.assertEqual(phases[:20], list(range(1, 20)) + [0])
        self.assertNotIn(key, caverns.scythes.active)
