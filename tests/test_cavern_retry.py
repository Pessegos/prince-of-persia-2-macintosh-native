"""Presentation regressions for cavern retries, without desktop input."""

from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from pop2.paths import ASSET_DIR
from pop2.screenshots import ScreenshotSettings


@unittest.skipUnless((ASSET_DIR / 'tree-1.json').is_file(), 'Imported tree scenes required')
class CavernRetryPresentationTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        stack = ExitStack()
        self.addCleanup(stack.close)
        directory = stack.enter_context(TemporaryDirectory())
        stack.enter_context(patch('pop2.window_controls.ScreenshotSettings.load',
                                  return_value=ScreenshotSettings(Path(directory))))
        RooftopSceneTests.setUp(self)
        self.scene.load_level(4)
        RooftopSceneTests.tick(self, 16)

    def retry_renders(self, *, checkpoint=False, death=False):
        scene = self.scene
        scene.combat.player.life = scene.combat.player.max_life = 5
        if checkpoint:
            from pop2.rebirth import Checkpoint, RebirthSnapshot

            # Synthetic checkpoint exercises the host path; level four has none.
            scene.checkpoint = RebirthSnapshot.capture(Checkpoint(1, 0, 24), scene.combat)
        if death:
            scene.combat.player.life = 0
            scene.death.counter, scene.death.prompt_visible = 8, True
        stages = []
        with patch.object(scene, 'render', side_effect=lambda: stages.append(scene.attract_stage)):
            if death:
                scene.dev_key_press(SimpleNamespace(keysym='a', state=0, char='a'))
            else:
                scene.restart_level()
        return stages

    def test_keyboard_death_retry_presents_tree_without_a_level_frame(self):
        self.assertEqual(self.retry_renders(death=True), ['tree'])
        self.assertEqual((self.scene.tree_variant, self.scene.combat.player.life), (1, 5))

    def test_manual_restart_presents_tree_without_a_level_frame(self):
        self.assertEqual(self.retry_renders(), ['tree'])

    def test_checkpoint_retry_also_suppresses_the_intermediate_room(self):
        self.assertEqual(self.retry_renders(checkpoint=True, death=True), ['tree'])
        point = self.scene.checkpoint.checkpoint
        self.assertEqual((self.scene.room_id, self.scene.terrain_motion.row), (point.room, point.row))

    def test_restart_without_a_due_tree_still_presents_gameplay(self):
        self.scene.game.story.tree_stage = 0
        stages = self.retry_renders(death=True)
        self.assertTrue(stages)
        self.assertEqual(set(stages), {None})
        self.assertIsNone(self.scene.intro)


@unittest.skipUnless((ASSET_DIR / 'caverns_level4.json').is_file(), 'Imported cavern resources required')
class CavernGateClearanceTests(unittest.TestCase):
    def test_short_left_tap_finishes_normally_when_the_gate_only_clips_the_rear_edge(self):
        from pop2.pressure_plates import PressurePlates
        from tests.test_terrain import RooftopSceneTests

        stack = ExitStack()
        self.addCleanup(stack.close)
        directory = stack.enter_context(TemporaryDirectory())
        stack.enter_context(patch('pop2.window_controls.ScreenshotSettings.load',
                                  return_value=ScreenshotSettings(Path(directory))))
        RooftopSceneTests.setUp(self)
        scene = self.scene
        scene.load_level(4)
        scene.peaceful = True
        scene.in_animation_tick = True
        with patch.object(scene, 'render'):
            for start in (130, 132):
                with self.subTest(start=start):
                    scene.jump_to_room(10, 2, start, 0)
                    plates = scene.game.caverns.plates = PressurePlates()
                    plates.foreground[10, 22] = 0x200 | 237
                    plates.active[10, 22] = 4
                    scene.game.caverns.entry_frame = len(scene.game.caverns.entry_frames) - 1
                    scene.horizontal_key(None, -1, True)
                    scene.horizontal_key(None, -1, False)
                    phases = []
                    for _ in range(24):
                        RooftopSceneTests.tick(self)
                        phases.append(plates.foreground[10, 22] & 255)
                        self.assertNotIn(scene.sequence_state.source_sequence_id, (50, 118))
                        self.assertFalse(scene.terrain_motion.dead or scene.terrain_motion.falling)
                    self.assertEqual((scene.action, scene.combat.player.life), (15, 3))
                    self.assertLess(scene.player_x, start)
                    # It still slams; the next reversible plate may reopen it.
                    self.assertIn(0, phases)
