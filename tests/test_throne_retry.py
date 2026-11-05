"""Playtest regressions for throne pickup, checkpoints and Alt+R."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pop2.environments import environment_for
from pop2.paths import ASSET_DIR
from pop2.rebirth import RebirthSnapshot


@unittest.skipUnless((ASSET_DIR / 'ruins_level8.json').is_file(), 'Imported ruins required')
class ThroneRetryTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.load_level(8)
        self.scene.peaceful = True
        self.scene.game.story.tree_stage = 7

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests

        with patch.object(self.scene, 'render'), patch.object(self.scene, 'advance_audio'):
            RooftopSceneTests.tick(self, count)

    def reach_throne_after_earlier_checkpoint(self):
        scene = self.scene
        scene.jump_to_room(11, 1, 281, 1)  # Facing-right supporting foot at column5.
        scene.advance_rebirth()
        self.assertEqual(scene.checkpoint.checkpoint.room, 11)
        scene.jump_to_room(8, 2, 267, 1, reset_guards=False, preserve_checkpoint=True)
        environment_for(scene).wake_from_vision()
        self.tick(40)

    def take_floor_sword(self):
        scene = self.scene
        scene.jump_to_room(8, 2, 267, 1, reset_guards=False, preserve_checkpoint=True)
        scene.set_key_state('shift', True)
        self.tick(20)
        scene.set_key_state('shift', False)
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 1)

    def test_retry_after_vision_without_pickup_returns_to_room_twelve_with_old_sword(self):
        self.reach_throne_after_earlier_checkpoint()
        scene = self.scene
        self.assertEqual(scene.checkpoint.checkpoint.room, 11)
        scene.restart_level()
        self.assertEqual(scene.room_id, 11)
        self.assertEqual((scene.game.sword_type, scene.sword_set()), (2, 2))
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 22)

    def test_pickup_captures_consumed_item_and_retry_and_saved_retry_keep_it_consumed(self):
        from pop2.save_game import capture, write_save

        self.reach_throne_after_earlier_checkpoint()
        self.take_floor_sword()
        scene = self.scene
        self.assertEqual(scene.checkpoint.checkpoint.room, 8)
        self.assertEqual(scene.checkpoint.caverns.potions.tiles[8, 25][0], 1)
        scene.restart_level()
        self.assertEqual(scene.room_id, 8)
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 1)
        self.assertEqual(scene.sword_set(), 1)
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'throne.pop2save'
            write_save(path, capture(scene.game))
            scene.load_game_from(path)
        self.assertEqual(scene.room_id, 8)
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 1)

    def test_room_eleven_warp_uses_the_earlier_checkpoint_before_sword_pickup(self):
        scene = self.scene
        for after_vision in (False, True):
            with self.subTest(after_vision=after_vision):
                scene.load_level(8)
                if after_vision:
                    scene.jump_to_room(8, 2, 267, 1)
                    environment_for(scene).wake_from_vision()
                scene.jump_to_screen('Room 11')
                self.assertEqual(scene.checkpoint.checkpoint.room, 11)
                scene.restart_level_now(redraw=False)
                self.assertEqual(scene.room_id, 11)
                self.assertEqual(scene.sword_set(), 2)

    def test_premature_old_throne_snapshot_is_repaired_before_retry(self):
        scene = self.scene
        scene.jump_to_room(8, 2, 267, 1)
        environment_for(scene).wake_from_vision()
        premature = RebirthSnapshot.capture(scene.checkpoints[0], scene.combat)
        scene.checkpoint = premature
        scene.restart_level_now(redraw=False)
        self.assertEqual(scene.room_id, 11)
        self.assertEqual(scene.sword_set(), 2)

        scene.jump_to_room(8, 2, 267, 1)
        environment_for(scene).wake_from_vision()
        self.take_floor_sword()
        scene.checkpoint = premature  # Old snapshot still has the floor sword.
        scene.restart_level_now(redraw=False)
        self.assertEqual(scene.room_id, 8)
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 1)

    def test_throne_retry_restarts_its_post_vision_theme_instead_of_common_ruins_music(self):
        from pop2.audio import AudioEngine
        from tests.test_audio import TimedPlayback

        self.reach_throne_after_earlier_checkpoint()
        self.take_floor_sword()
        scene = self.scene
        scene.audio = AudioEngine(playback=object())
        scene.audio.playback = TimedPlayback(scene.audio.cues)
        scene.audio.configure_level(scene.game.level.data)
        scene.advance_audio()
        self.assertEqual(scene.audio.current_music, 182)
        scene.audio.playback.advance(10000)
        scene.advance_audio()
        self.assertNotEqual(scene.audio.current_music, 182)
        scene.restart_level()
        self.assertEqual(scene.room_id, 8)
        self.assertEqual(scene.audio.current_music, 182)
        self.assertTrue(scene.audio.music_busy)

    def test_throne_theme_returns_when_retry_first_shows_a_tree_scene(self):
        from pop2.audio import AudioEngine
        from tests.test_audio import TimedPlayback

        self.reach_throne_after_earlier_checkpoint()
        self.take_floor_sword()
        scene = self.scene
        scene.audio = AudioEngine(playback=object())
        scene.audio.playback = TimedPlayback({**scene.audio.cues, **scene.audio.scene_cues})
        scene.audio.configure_level(scene.game.level.data)
        scene.advance_audio()
        self.assertEqual(scene.audio.current_music, 182)
        scene.game.story.tree_stage = -1  # RestartGame owes the first tree scene.
        scene.restart_level()
        self.assertIsNotNone(scene.intro)
        self.assertNotEqual(scene.audio.current_music, 182)
        scene.finish_tree(skipped=True)
        self.assertEqual(scene.room_id, 8)
        self.assertEqual(scene.level_map.tile(8, 5, 2).kind, 1)
        self.assertEqual(scene.audio.current_music, 182)
