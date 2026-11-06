import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw, ImageFont

from pop2.cutscenes import CHAPTERS, CHAPTER_KEYS, CutsceneCollection
from pop2.cutscene_gallery import CutsceneGallery
from pop2.cutscene_viewer import ReplayAudio
from pop2.game_menu import GameMenu
from pop2.paths import ASSET_DIR


class CollectionTests(unittest.TestCase):
    def test_whole_story_catalog_includes_recent_films_and_excludes_tree_and_gameplay(self):
        self.assertEqual([chapter.program for chapter in CHAPTERS],
                         ['intro.json', 'ending.json', 'discovery.json', 'carpet.json',
                          'throne.json', 'temple.json', 'tower.json'])
        self.assertEqual(len(CHAPTER_KEYS), len(CHAPTERS))
        self.assertEqual(len({chapter.program for chapter in CHAPTERS}), len(CHAPTERS))

    def test_collection_persists_and_preserves_other_instance_unlocks(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'collection.json'
            first, second = CutsceneCollection.load(path), CutsceneCollection.load(path)
            self.assertEqual(first.seen, {'opening'})
            first.unlock('voyage', 'unknown')
            second.unlock('carpet')
            self.assertEqual(CutsceneCollection.load(path).seen, {'opening', 'voyage', 'carpet'})
            self.assertEqual(json.loads(path.read_text())['version'], 1)

    def test_bad_profile_and_write_error_do_not_interrupt_the_game(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'collection.json'
            for data in ('[]', '{bad', '{"version":1,"seen":[4]}',
                         '{"version":8,"seen":["tower"]}'):
                path.write_text(data)
                self.assertEqual(CutsceneCollection.load(path).seen, {'opening'})
            collection = CutsceneCollection(path)
            with patch('pop2.cutscenes.tempfile.NamedTemporaryFile', side_effect=OSError):
                collection.unlock('voyage')
            self.assertIn('voyage', collection.seen)
            self.assertTrue(collection.error)

    def test_legacy_saves_admit_only_preceding_mandatory_chapters(self):
        with TemporaryDirectory() as directory:
            collection = CutsceneCollection(Path(directory) / 'collection.json')
            game = SimpleNamespace(level=SimpleNamespace(number=8),
                                   caverns=SimpleNamespace(throne_seen=False, throne_done=False))
            collection.admit_saved_progress(game)
            self.assertEqual(collection.seen, {'opening', 'voyage', 'discovery', 'carpet'})
            game.caverns.throne_seen = True
            collection.admit_saved_progress(game)
            self.assertIn('vision', collection.seen)
            game.level.number = 13
            collection.admit_saved_progress(game)
            self.assertIn('horse', collection.seen)
            self.assertNotIn('tower', collection.seen)


class CaptionFont:
    height = 12

    def __init__(self):
        self.values = []

    def text(self, value, color='white'):
        self.values.append(value)
        image = Image.new('RGBA', (max(1, len(value) * 7), 14))
        ImageDraw.Draw(image).text((0, 0), value, font=ImageFont.load_default(), fill=color)
        return image


class GalleryTests(unittest.TestCase):
    def gallery(self):
        return CutsceneGallery(CutsceneCollection(Path('unused-test-profile.json')),
                               Mock(return_value=Image.new('RGB', (510, 384), '#773311')))

    def test_horizontal_navigation_and_explicit_activation(self):
        gallery = self.gallery()
        self.assertEqual(list(gallery.visible), [0, 1, 2])
        self.assertEqual(gallery.key('Return'), 'cutscene_play')
        gallery.key('Right')
        self.assertEqual(gallery.key('Return'), 'changed')
        gallery.key('End')
        self.assertEqual(gallery.index, 6)
        self.assertEqual(list(gallery.visible), [4, 5, 6])
        gallery.key('Right')
        self.assertEqual(gallery.index, 6)
        gallery.key('Home')
        gallery.key('Tab', backwards=True)
        self.assertEqual(gallery.key('Return'), 'cutscene_back')
        self.assertEqual(gallery.key('Escape'), 'cutscene_back')

    def test_locked_chapters_leak_neither_previews_nor_story_titles(self):
        gallery = self.gallery()
        font = CaptionFont()
        with patch('pop2.cutscene_gallery.chapter_available', return_value=True):
            gallery.draw(Image.new('RGBA', (512, 384)), font)
        gallery.preview.assert_called_once_with(0)
        self.assertNotIn(CHAPTERS[1].title, font.values)
        self.assertNotIn(CHAPTERS[2].title, font.values)
        self.assertEqual(gallery.index, 0)


class ReplayAudioTests(unittest.TestCase):
    def test_replay_uses_private_channels_and_never_resets_the_game_engine(self):
        count = [8]
        mixer = Mock()
        mixer.get_num_channels.side_effect = lambda: count[0]
        mixer.set_num_channels.side_effect = lambda value: count.__setitem__(0, value)
        mixer.get_init.return_value = (48000, -16, 2)
        channels = {8: Mock(), 9: Mock()}
        mixer.Channel.side_effect = channels.__getitem__
        sound = Mock()
        engine = Mock(playback=SimpleNamespace(mixer=mixer, sounds={'scene-0-25006': sound}))
        replay = ReplayAudio(engine)
        self.assertEqual(count[0], 10)
        replay.play_intro(25006, 0)
        channels[8].play.assert_called_once_with(sound)
        replay.pause(True)
        channels[8].pause.assert_called_once_with()
        channels[9].pause.assert_called_once_with()
        replay.close()
        self.assertEqual(count[0], 8)
        engine.reset.assert_not_called()
        engine.pause.assert_not_called()
        self.assertEqual([call.args[0] for call in mixer.Channel.call_args_list], [8, 9])

    def test_real_sdl_channels_leave_the_paused_music_and_effects_in_place(self):
        from pop2.audio import MixerPlayback

        with TemporaryDirectory() as directory, patch.dict('os.environ', {'SDL_AUDIODRIVER': 'dummy'}):
            backend = MixerPlayback(directory, {})
            replay = None
            try:
                sound = backend.mixer.Sound(buffer=bytes(48000 * 4 * 2))
                backend.sounds['scene-0-25006'] = sound
                backend.channels['music'].play(sound)
                backend.channels['effect'].play(sound)
                backend.pause(True)
                count = backend.mixer.get_num_channels()
                replay = ReplayAudio(SimpleNamespace(playback=backend))
                replay.play_intro(25006, 0)
                self.assertIs(backend.channels['music'].get_sound(), sound)
                self.assertIs(backend.channels['effect'].get_sound(), sound)
                self.assertTrue(backend.channels['music'].get_busy())
                self.assertTrue(replay.channels['music'].get_busy())
                replay.pause(True)
                replay.pause(False)
                replay.close()
                self.assertEqual(backend.mixer.get_num_channels(), count)
                self.assertIs(backend.channels['music'].get_sound(), sound)
            finally:
                if replay is not None:
                    replay.close()
                backend.close()


@unittest.skipUnless(all((ASSET_DIR / c.program).is_file() for c in CHAPTERS), 'Imported story programs required')
class ViewerSceneTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.scene.cutscene_collection = CutsceneCollection(Path(self.directory.name) / 'cutscenes.json')

    def snapshot(self):
        from pop2.save_game import capture_snapshot

        return capture_snapshot(self.scene.game)

    def open_viewer(self):
        self.scene.open_game_menu()
        self.scene.apply_game_action('cutscenes')
        return self.scene.game_menu.cutscene_viewer

    def test_f1_and_f3_offer_the_same_chapter_viewer_without_a_screen_selector(self):
        scene = self.scene
        self.assertIn('cutscenes', {item.action for item in GameMenu().items})
        gallery = self.open_viewer()
        self.assertEqual(gallery.chapters, CHAPTERS)
        scene.close_game_menu()
        scene.open_dev_mode()
        scene.dev_menu.focus = 8
        scene.apply_dev_action(scene.dev_menu.activate())
        self.assertIsNone(scene.dev_menu)
        self.assertEqual(scene.game_menu.page, 'cutscenes')

    def test_alt_c_opens_the_same_viewer_and_is_listed_in_f1(self):
        scene = self.scene
        self.assertEqual(next(item.shortcut for item in GameMenu().items if item.action == 'cutscenes'), 'Alt+C')
        event = SimpleNamespace(keysym='c', state=0x20000)
        scene.dev_key_press(event)
        gallery = scene.game_menu.cutscene_viewer
        scene.dev_key_press(event)
        self.assertIs(scene.game_menu.cutscene_viewer, gallery)
        self.assertTrue(scene.paused)
        self.assertEqual(scene.game_menu.page, 'cutscenes')
        scene.dev_key_release(event)


    def test_every_chapter_finishes_in_the_gallery_without_touching_the_live_world(self):
        scene = self.scene
        scene.cutscene_collection.seen.update(CHAPTER_KEYS)
        before, game, combat = self.snapshot(), scene.game, scene.combat
        gallery = self.open_viewer()
        self.assertEqual(self.snapshot(), before)
        for index, chapter in enumerate(CHAPTERS):
            with self.subTest(chapter=chapter.key):
                gallery.index = index
                scene.start_cutscene_replay()
                self.assertIsNotNone(scene.cutscene_replay, gallery.error)
                player = scene.cutscene_replay.player
                player.advance(1200)
                self.assertTrue(player.done)
                scene.advance_cutscene_replay()
                self.assertIsNone(scene.cutscene_replay)
                self.assertEqual(scene.game_menu.page, 'cutscenes')
                self.assertTrue(scene.paused)
                self.assertIs(scene.game, game)
                self.assertIs(scene.combat, combat)
                self.assertEqual(self.snapshot(), before)

    def test_escape_focus_loss_and_stop_preserve_an_interrupted_campaign_cutscene(self):
        scene = self.scene
        scene.start_intro()
        original = scene.intro
        original.advance(3)
        position = original.position, original.time
        gallery = self.open_viewer()
        scene.start_cutscene_replay()
        self.assertIsNot(scene.cutscene_replay.player, original)
        scene.cutscene_replay.player.advance(2)
        scene.pause_cutscene_replay(True)
        self.assertTrue(scene.cutscene_replay.paused)
        self.assertIsNone(scene.cutscene_after_id)
        scene.pause_cutscene_replay(False)
        self.assertIsNotNone(scene.cutscene_after_id)
        scene.pause_if_unfocused()
        self.assertTrue(scene.cutscene_replay.paused)
        scene.stop_cutscene_replay()
        self.assertEqual((original.position, original.time), position)
        self.assertIs(scene.intro, original)
        self.assertEqual(gallery.index, 0)
        scene.close_game_menu()
        self.assertIs(scene.intro, original)

    def test_locked_play_and_replay_navigation_never_unlock_future_scenes(self):
        scene = self.scene
        gallery = self.open_viewer()
        gallery.index = 5
        scene.start_cutscene_replay()
        self.assertIsNone(scene.cutscene_replay)
        self.assertEqual(scene.cutscene_collection.seen, {'opening'})

        scene.close_game_menu()
        scene.with_intro = True
        scene.seek_playback_part(next(part for part in scene.development_parts() if part.stage == 'temple'))
        self.assertEqual(scene.cutscene_collection.seen, {'opening'})

    def test_replay_input_blocks_game_commands_and_mouse_back_does_not_start_another_film(self):
        scene = self.scene
        self.open_viewer()
        scene.start_cutscene_replay()
        original = scene.cutscene_replay
        before = self.snapshot()
        for key in ('Left', 'Down', 'F3', 'F2'):
            event = SimpleNamespace(keysym=key, state=0)
            scene.dev_key_press(event)
            scene.dev_key_release(event)
        with patch.object(scene, 'new_game') as new_game:
            event = SimpleNamespace(keysym='n', state=0x20000)
            scene.dev_key_press(event)
            scene.dev_key_release(event)
            new_game.assert_not_called()
        self.assertIs(scene.cutscene_replay, original)
        self.assertEqual(self.snapshot(), before)
        event = SimpleNamespace(keysym='Escape', state=0)
        scene.dev_key_press(event)
        self.assertTrue(original.paused)
        scene.dev_key_press(event)
        self.assertTrue(original.paused)
        scene.dev_key_release(event)
        scene.dev_key_press(event)
        self.assertFalse(original.paused)
        scene.dev_key_release(event)
        with patch.object(scene, 'dev_pointer', return_value=(400, 375)):
            scene.dev_click(SimpleNamespace(num=1))
        self.assertIsNone(scene.cutscene_replay)
        self.assertEqual(scene.game_menu.page, 'cutscenes')
        self.assertEqual(self.snapshot(), before)

    def test_failed_film_open_is_reported_without_destroying_the_live_session(self):
        scene = self.scene
        self.open_viewer()
        before = self.snapshot()
        provider = scene.cutscene_preview_provider()
        provider.assets.clear()
        with patch('pop2.intro.IntroAssets', side_effect=ValueError('Missing import')), \
                self.assertLogs('pop2.cutscene_viewer', level='ERROR') as logs:
            scene.start_cutscene_replay()
        self.assertIsNone(scene.cutscene_replay)
        self.assertIn('importing the game again', scene.game_menu.cutscene_viewer.error)
        self.assertIn('Missing import', '\n'.join(logs.output))
        self.assertEqual(self.snapshot(), before)

    def test_error_during_playback_returns_safely_and_cancels_the_viewer_tick(self):
        scene = self.scene
        self.open_viewer()
        before = self.snapshot()
        scene.start_cutscene_replay()
        with patch.object(scene.cutscene_replay.player, 'advance', side_effect=ValueError('Broken scene')), \
                self.assertLogs('pop2.cutscene_viewer', level='ERROR'):
            scene.advance_cutscene_replay()
        self.assertIsNone(scene.cutscene_replay)
        self.assertIsNone(scene.cutscene_after_id)
        self.assertTrue(scene.game_menu.cutscene_viewer.error)
        self.assertTrue(scene.paused)
        self.assertEqual(self.snapshot(), before)

    def test_loading_an_older_save_backfills_chapters_but_warping_and_saving_do_not(self):
        from pop2.save_game import capture, write_save

        scene = self.scene
        scene.load_level(6)
        self.assertEqual(scene.cutscene_collection.seen, {'opening'})
        path = Path(self.directory.name) / 'old-save.pop2save'
        write_save(path, capture(scene.game))
        self.assertEqual(scene.cutscene_collection.seen, {'opening'})
        scene.load_game_from(path)
        self.assertEqual(scene.cutscene_collection.seen, {'opening', 'voyage', 'discovery', 'carpet'})

    def test_viewer_over_a_copy_challenge_pauses_on_focus_loss_and_resets_its_clock_on_return(self):
        scene = self.scene
        from pop2.copy_protection import CopyProtection

        scene.copy_challenge = CopyProtection(scene.resources.prince)
        scene.last_copy_at = 1.0
        self.open_viewer()
        scene.start_cutscene_replay()
        scene.pause_if_unfocused()
        self.assertTrue(scene.cutscene_replay.paused)
        scene.stop_cutscene_replay()
        with patch('pop2.window_controls.time.perf_counter', return_value=1000.0):
            scene.close_game_menu(resume=True)
        self.assertEqual(scene.last_copy_at, 1000.0)

    def test_natural_story_starts_unlock_each_chapter_and_new_game_keeps_the_collection(self):
        scene = self.scene
        for start, expected in ((scene.start_ending, 'voyage'), (scene.start_discovery, 'discovery'),
                                (scene.start_carpet, 'carpet'), (lambda: scene.start_vision(lambda: None), 'vision'),
                                (lambda: scene.start_temple_ride(lambda: None), 'horse'),
                                (lambda: scene.start_tower_flight(lambda: None), 'tower')):
            start()
            self.assertIn(expected, scene.cutscene_collection.seen)
        scene.new_game()
        self.assertEqual(scene.cutscene_collection.seen, CHAPTER_KEYS)
        self.assertEqual(CutsceneCollection.load(scene.cutscene_collection.path).seen, CHAPTER_KEYS)


if __name__ == '__main__':
    unittest.main()
