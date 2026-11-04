import random
import unittest
from unittest.mock import Mock, patch

from PIL import ImageStat

from pop2.paths import ASSET_DIR
from pop2.playback_navigation import playback_groups
from pop2.playback_preview import PlaybackPreviews


INSTALLED = all((ASSET_DIR / name).is_file() for name in (
    'temple.json', 'temple_level10.json', 'ruins_level9.json', 'attract.json'))


@unittest.skipUnless(INSTALLED, 'Imported horse scene and playback resources required')
class HorsePlaybackTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.scene.with_intro = True
        self.scene.start_intro()

    def test_after_level_nine_gallery_has_six_visible_isolated_thumbnails(self):
        scene = self.scene
        parts = scene.development_parts()
        group = next((g for g in playback_groups(parts) if g.label == 'After Level 9'), None)
        self.assertIsNotNone(group)
        self.assertEqual(len(group.part_indices), 6)
        before = (scene.game, scene.intro, scene.intro.time, scene.intro.position,
                  scene.combat.world_frame, random.getstate())
        scene.audio = Mock()
        previews = PlaybackPreviews(scene.resources, parts, scene.attract_data, 'horse-test')
        with patch('pop2.playback_preview.read_preview', return_value=None), \
                patch('pop2.playback_preview.write_preview'):
            frames = previews.group(group.part_indices)
        for index, frame in frames.items():
            with self.subTest(part=parts[index].label):
                self.assertEqual(frame.size, (510, 384))
                self.assertGreater(ImageStat.Stat(frame.convert('L')).stddev[0], 4)
        scene.audio.play_intro.assert_not_called()
        self.assertEqual(before, (scene.game, scene.intro, scene.intro.time, scene.intro.position,
                                  scene.combat.world_frame, random.getstate()))

    def test_every_horse_part_seeks_the_real_scene_and_finishes_with_the_music_handoff(self):
        scene = self.scene
        parts = scene.development_parts()
        horse = [(index, p) for index, p in enumerate(parts) if p.stage == 'temple']
        self.assertEqual(len(horse), 5)
        scene.audio = Mock()
        scene.audio.carry_story_music.return_value = True
        for index, part in horse:
            with self.subTest(part=part.label):
                scene.seek_playback_part(part)
                self.assertEqual(scene.game.level.number, 9)
                self.assertEqual(scene.intro.program_kind, 'temple')
                self.assertEqual(scene.attract_stage, 'tree')
                self.assertEqual(scene.current_playback_part(), index)
        scene.audio.reset.reset_mock()
        scene.intro.advance(60)
        scene.finish_attract_stage()
        self.assertEqual((scene.game.level.number, scene.room_id), (10, 21))
        self.assertEqual(parts[scene.current_playback_part()].index, 10)
        self.assertIsNone(scene.intro)
        scene.audio.reset.assert_called_once_with(keep_music=True)
        scene.open_dev_mode()
        self.assertEqual(scene.dev_menu.current_section, scene.current_playback_part())

    def test_seeking_away_discards_the_unfinished_horse_callback(self):
        scene = self.scene
        parts = scene.development_parts()
        scene.seek_playback_part(next(p for p in parts if p.stage == 'temple'))
        self.assertIsNotNone(scene.after_vision)
        scene.seek_playback_part(next(p for p in parts if p.stage == 'level' and p.index == 10))
        self.assertIsNone(scene.after_vision)
        self.assertIsNone(scene.next_level_after_tree)
        self.assertIsNone(scene.intro)
        self.assertEqual((scene.game.level.number, scene.room_id), (10, 21))

    def test_developer_play_button_starts_the_horse_scene_unpaused(self):
        scene = self.scene
        parts = scene.development_parts()
        index = next(i for i, p in enumerate(parts) if p.stage == 'temple')
        scene.open_dev_mode()
        menu = scene.dev_menu
        menu.section_index = index
        menu.show_page('playback')
        self.assertIn('After Level 9', [group.label for group in menu.groups])
        menu.focus = 2
        scene.apply_dev_action(menu.activate())
        self.assertIsNone(scene.dev_menu)
        self.assertFalse(scene.paused)
        self.assertEqual(scene.intro.program_kind, 'temple')
