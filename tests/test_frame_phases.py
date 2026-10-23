import unittest

from pop2.paths import ASSET_DIR


class WorldPhaseTableTests(unittest.TestCase):
    def test_each_tick_mode_keeps_the_existing_phase_order(self):
        # docs/research/frame-phase-order.md records the port's order before
        # the orchestrator; changes need original evidence.
        from pop2.frame_phases import WORLD_PHASES

        full = ('terrain', 'combat', 'harbor', 'level_events', 'rebirth', 'audio', 'render')
        self.assertEqual(WORLD_PHASES, {
            'potion': ('terrain', 'combat', 'level_events', 'rebirth', 'audio', 'render'),
            'falling': full, 'locked': full, 'opening': ('combat', 'audio', 'render'),
            'ordinary': full})


@unittest.skipUnless((ASSET_DIR / 'caverns_level5.json').is_file(), 'Imported resources required')
class WorldPhaseTraceTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(5)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def modes(self):
        return [mode for mode, phase in self.scene.frame_trace if phase == 'terrain'
                or mode == 'opening' and phase == 'combat']

    def test_standing_runs_the_ordinary_phases_once_per_tick(self):
        scene = self.scene
        self.tick(20)
        scene.frame_trace = []
        self.tick(3)
        self.assertEqual(self.modes(), ['ordinary'] * 3)
        self.assertEqual([phase for _mode, phase in scene.frame_trace[:7]],
                         ['terrain', 'combat', 'harbor', 'level_events', 'rebirth', 'audio', 'render'])

    def test_a_falling_prince_runs_the_falling_phases(self):
        scene = self.scene
        self.tick(20)
        scene.terrain_motion.falling = True
        scene.frame_trace = []
        self.tick()
        self.assertEqual(self.modes()[0], 'falling')


if __name__ == '__main__':
    unittest.main()
