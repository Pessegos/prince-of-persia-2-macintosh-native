from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from pop2.game_session import GameResources, GameSession
from pop2.paths import ASSET_DIR
from pop2.story_progress import FRAMES_PER_MINUTE, StoryProgress

TREES = all((ASSET_DIR / f'tree-{n}.json').is_file() for n in range(1, 10))


@unittest.skipUnless((ASSET_DIR / 'Prince.rsrc').is_file(), 'Imported game resources required')
class StorySaveTests(unittest.TestCase):
    def roundtrip(self, story):
        from pop2.save_game import capture, read_save, write_save

        resources = GameResources.load()
        game = GameSession.load(resources, 4)
        game.story = story
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'story.pop2save'
            document = capture(game)
            write_save(path, document)
            restored, _saved = read_save(path, resources)
        return document, restored.story

    def test_started_clock_and_tree_stage_survive_a_progress_save(self):
        document, story = self.roundtrip(StoryProgress(minutes=58, frames_remaining=300, tree_stage=1))
        self.assertEqual(document['story'], {'minutes': 58, 'frames_remaining': 300, 'tree_stage': 1})
        self.assertEqual(story, StoryProgress(58, 300, 1))

    def test_untouched_campaign_omits_the_optional_story_field(self):
        document, story = self.roundtrip(StoryProgress())
        self.assertNotIn('story', document)
        self.assertEqual(story, StoryProgress())

    def test_invalid_story_clock_is_rejected(self):
        from pop2.save_game import SaveGameError, capture, read_save

        resources = GameResources.load()
        game = GameSession.load(resources, 4)
        game.story = StoryProgress(tree_stage=0)
        document = capture(game)
        for story in ({'minutes': 76, 'frames_remaining': 1, 'tree_stage': 0},
                      {'minutes': 5, 'frames_remaining': 0, 'tree_stage': 0},
                      {'minutes': 5, 'frames_remaining': 1, 'tree_stage': 8},
                      {'minutes': 5, 'frames_remaining': 1}):
            with self.subTest(story=story), TemporaryDirectory() as directory:
                path = Path(directory) / 'bad.pop2save'
                path.write_text(json.dumps({**document, 'story': story}), encoding='ascii')
                with self.assertRaises(SaveGameError):
                    read_save(path, resources)


@unittest.skipUnless(TREES, 'Imported tree scenes required')
class StoryHostTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(4)
        self.tick(16)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.tick(self, count)

    def finish_tree(self):
        scene = self.scene
        while scene.intro is not None and not scene.intro.done:
            scene.intro.advance(1.0)
        scene.finish_attract_stage()

    def test_first_level_four_restart_plays_tree_one_once_and_starts_the_clock(self):
        scene = self.scene
        self.assertFalse(scene.game.story.clock_started)
        scene.restart_level()
        self.assertEqual((scene.attract_stage, scene.tree_variant), ('tree', 1))
        self.assertEqual(scene.game.story.tree_stage, 0)
        self.finish_tree()
        self.assertIsNone(scene.intro)
        self.assertEqual((scene.game.level.number, scene.room_id), (4, 0))
        scene.restart_level()
        self.assertIsNone(scene.intro)

    def test_clock_counts_gameplay_frames_only_after_the_tree_starts_it(self):
        scene = self.scene
        self.tick(30)
        self.assertEqual(scene.game.story.frames_remaining, FRAMES_PER_MINUTE)
        scene.game.story.tree_stage = 0
        self.tick(30)
        self.assertEqual(scene.game.story.frames_remaining, FRAMES_PER_MINUTE - 30)
        scene.combat.player.life = 0
        before = scene.game.story.frames_remaining
        self.tick(5)
        self.assertEqual(scene.game.story.frames_remaining, before)

    def test_time_message_appears_in_the_hud_for_twenty_four_steps(self):
        scene = self.scene
        scene.game.story = StoryProgress(minutes=11, frames_remaining=1, tree_stage=0)
        self.tick()
        self.assertEqual((scene.time_message, scene.time_message_frames), ('10 Minutes Left', 24))
        self.tick(21)
        self.assertEqual(scene.time_message, '10 Minutes Left')
        self.tick(2)
        self.assertIsNone(scene.time_message)
        scene.game.story = StoryProgress(minutes=11, frames_remaining=1, tree_stage=0)
        self.tick()
        scene.restart_level()
        self.assertIsNone(scene.time_message)

    def test_time_threshold_selects_the_next_tree_variant_on_restart(self):
        scene = self.scene
        scene.game.story = StoryProgress(minutes=63, tree_stage=0)
        scene.restart_level()
        self.assertEqual(scene.tree_variant, 2)

    def test_expiry_plays_the_last_tree_and_ends_the_campaign(self):
        scene = self.scene
        scene.game.story = StoryProgress(minutes=1, frames_remaining=1, tree_stage=3)
        self.tick()
        self.assertEqual((scene.attract_stage, scene.tree_variant), ('tree', 9))
        self.finish_tree()
        self.assertEqual(scene.game.level.number, 1)
        self.assertEqual(scene.game.story, StoryProgress())

    def test_level_changes_keep_the_story_and_new_game_resets_it(self):
        scene = self.scene
        scene.game.story = StoryProgress(minutes=40, tree_stage=4)
        scene.load_level(3)
        self.assertEqual(scene.game.story, StoryProgress(minutes=40, tree_stage=4))
        scene.new_game()
        self.assertEqual(scene.game.story, StoryProgress())


if __name__ == '__main__':
    unittest.main()
