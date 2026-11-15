from pathlib import Path
import random
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from PIL import Image, ImageStat

from pop2.paths import ASSET_DIR
from pop2.playback_navigation import playback_groups


class SnapshotTests(unittest.TestCase):
    def test_snapshot_finishes_the_reveal_without_running_the_following_clear(self):
        from pop2.playback_navigation import PlaybackPart
        from pop2.playback_preview import PlaybackPreviews
        from tests.test_intro import player

        rect = (62, 64, 292, 448)
        source = player(('palette', 1, 66, 0), ('shape', 1, 64, 62, 0),
                        ('copy', rect), ('wait', 60), ('shape', 2, 64, 62, 0),
                        ('dissolve', 60), ('fill', 3, rect), ('copy', rect), ('wait', 60))
        source.assets.palettes[1] = {1: (180, 20, 20), 2: (20, 80, 180), 3: (240, 240, 240)}
        source.assets.shapes = {
            1: Image.frombytes('L', (384, 230), bytes((1, 3)) * (384 * 230 // 2)),
            2: Image.frombytes('L', (384, 230), bytes((2, 3)) * (384 * 230 // 2)),
        }
        parts = (PlaybackPart('Reveal', 'intro', 5), PlaybackPart('Next', 'intro', 8))
        previews = PlaybackPreviews(None, parts, None, 'test')
        previews.assets['intro'] = source.assets
        frame = previews.snapshot(0)
        self.assertEqual(frame.getpixel((64, 62)), (20, 80, 180))
        self.assertEqual(frame.getpixel((65, 62)), (240, 240, 240))


@unittest.skipUnless((ASSET_DIR / 'attract.json').is_file(), 'Imported scene resources required')
class ImportedSnapshotTests(unittest.TestCase):
    def setUp(self):
        from tests.test_attract_scene import AttractSceneTests

        AttractSceneTests.setUp(self)

    def test_every_part_has_native_visible_art_and_disk_cache_is_lossless_without_live_state_changes(self):
        from pop2.playback_preview import PlaybackPreviews

        s = self.scene
        parts = s.development_parts()
        before = (s.game, s.room_id, s.player_x, s.combat.world_frame,
                  s.intro, s.intro.time, s.intro.position, random.getstate())
        groups = playback_groups(parts)
        seen = set()
        with TemporaryDirectory() as directory:
            # The directory controls only the disposable cache; artwork stays in ASSET_DIR.
            provider = PlaybackPreviews(s.resources, parts, s.attract_data, 'test')
            for group in groups:
                with self.subTest(group=group.label), \
                        patch('pop2.playback_preview.read_preview', return_value=None), \
                        patch('pop2.playback_preview.write_preview'):
                    frames = provider.group(group.part_indices)
                for index, frame in frames.items():
                    self.assertEqual(frame.size, (510, 384))
                    stats = ImageStat.Stat(frame.crop((64, 62, 448, 292)).convert('L'))
                    self.assertGreater(stats.stddev[0], 4, parts[index])
                    seen.add(index)
            indices = groups[0].part_indices
            from pop2.preview_cache import write_preview
            identity = [[parts[i].label, parts[i].stage, parts[i].index] for i in indices]
            cache_path = Path(directory) / '.developer-cache' / f'playback-{indices[0]}.zip'
            write_preview(cache_path, 'test', identity, {str(i): frame for i, frame in provider.frames[indices].items()})
            warm = PlaybackPreviews(s.resources, parts, s.attract_data, 'test', Path(directory))
            with patch.object(warm, 'snapshot', side_effect=AssertionError('Warm cache rendered scene')):
                frames = warm.group(indices)
            self.assertEqual(frames[0].tobytes(), provider.frames[indices][0].tobytes())
        self.assertEqual(seen, set(range(len(parts))))
        self.assertEqual(before, (s.game, s.room_id, s.player_x, s.combat.world_frame,
                                  s.intro, s.intro.time, s.intro.position, random.getstate()))

    def test_palace_thumbnails_preserve_each_current_picture_and_caption_after_the_titles(self):
        from pop2.intro import IntroPlayer
        from pop2.playback_preview import PlaybackPreviews

        s = self.scene
        parts = s.development_parts()
        previews = PlaybackPreviews(s.resources, parts, s.attract_data, 'test')
        for index, part in enumerate(parts):
            if part.stage != 'intro':
                continue
            operation = s.intro_assets.program['operations'][part.index]
            if operation['op'] != 'text' or operation['args'][1] < 17:
                continue
            with self.subTest(scene=part.label):
                actual = previews.snapshot(index)
                player = IntroPlayer(previews.assets['intro'])
                player.seek_operation(part.index)
                while player.transition is not None:
                    player.advance(player.wait_until - player.time, stop_position=player.position)
                expected = player.frame().crop((0, 0, 510, 384)).convert('RGB')
                self.assertEqual(actual.tobytes(), expected.tobytes())

    def test_shared_private_replay_matches_independent_snapshots_for_every_scene(self):
        from pop2.playback_preview import PlaybackPreviews

        s = self.scene
        parts = s.development_parts()
        provider = PlaybackPreviews(s.resources, parts, s.attract_data, 'test')
        for group in playback_groups(parts):
            players = {}
            for index in group.part_indices:
                with self.subTest(part=parts[index].label):
                    self.assertEqual(provider.snapshot(index, players).tobytes(),
                                     provider.snapshot(index).tobytes())

    def test_held_activation_cannot_play_accidentally_after_opening_the_chapter_viewer(self):
        s = self.scene
        for paused in (False, True):
            s.set_paused(paused)
            s.open_dev_mode()
            s.dev_menu.focus = 8
            enter = SimpleNamespace(keysym='Return', state=0)
            s.dev_key_press(enter)
            s.dev_key_press(enter)
            menu = s.game_menu
            self.assertIsNotNone(menu)
            self.assertEqual(menu.page, 'cutscenes')
            self.assertIsNone(s.cutscene_replay)
            s.dev_key_release(enter)
            with patch.object(s, 'seek_playback_part', wraps=s.seek_playback_part) as seek:
                rect = menu.cutscene_viewer.card_rect(0)
                point = (rect[0] + rect[2]) / 2, (rect[1] + rect[3]) / 2
                with patch.object(s, 'dev_pointer', return_value=point):
                    s.dev_click(SimpleNamespace(num=1))
                    self.assertIsNone(s.cutscene_replay)
                    s.dev_release(SimpleNamespace(num=1))      # one deliberate click plays the card
                    replay = s.cutscene_replay
                    s.dev_double_click(SimpleNamespace(num=1))
                    self.assertIs(s.cutscene_replay, replay)
                    self.assertFalse(replay.paused)
            seek.assert_not_called()
            self.assertIsNone(s.dev_menu)
            self.assertIsNotNone(s.cutscene_replay)
            self.assertTrue(s.paused)
            s.stop_cutscene_replay()
            s.close_game_menu()
