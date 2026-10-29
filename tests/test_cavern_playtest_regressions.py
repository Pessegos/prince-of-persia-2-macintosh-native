"""Reported post-alpha scenarios exercised through the scene host."""

from types import SimpleNamespace
import unittest

from pop2.paths import ASSET_DIR
from pop2.story_progress import MESSAGE_FRAMES


@unittest.skipUnless((ASSET_DIR / 'ruins_level6.json').is_file(), 'Imported game required')
class PlaytestSceneTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.setUp(self)

    def test_space_displays_running_campaign_time_in_ruins_even_after_teleport(self):
        scene = self.scene
        for number in (6, 7, 8, 9):
            with self.subTest(level=number):
                scene.load_level(number)
                scene.game.story.tree_stage = 1
                scene.game.story.minutes = 65
                scene.jump_to_room(3, 2, 180, 1)
                scene.dev_key_press(SimpleNamespace(keysym='space', state=0))
                self.assertEqual(scene.time_message, '65 Minutes Left')
                self.assertEqual(scene.time_message_frames, MESSAGE_FRAMES)
                self.assertEqual(scene.game.story.minutes, 65)
                scene.dev_key_release(SimpleNamespace(keysym='space'))

    def test_space_does_not_start_the_deferred_campaign_clock(self):
        scene = self.scene
        scene.load_level(3)
        scene.dev_key_press(SimpleNamespace(keysym='space', state=0))
        self.assertIsNone(scene.time_message)
        self.assertFalse(scene.game.story.clock_started)


if __name__ == '__main__':
    unittest.main()
