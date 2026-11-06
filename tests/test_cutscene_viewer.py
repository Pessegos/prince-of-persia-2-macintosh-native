import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw, ImageFont

from pop2.cutscenes import CHAPTERS, CHAPTER_KEYS, OPENING_KEYS, CutsceneCollection
from pop2.cutscene_gallery import CutsceneGallery
from pop2.cutscene_viewer import ReplayAudio
from pop2.game_menu import GameMenu
from pop2.paths import ASSET_DIR


class CollectionTests(unittest.TestCase):
    def test_whole_story_catalog_includes_recent_films_and_excludes_tree_and_gameplay(self):
        self.assertEqual([chapter.program for chapter in CHAPTERS],
                         ['intro.json', 'intro.json', 'intro.json', 'ending.json', 'discovery.json', 'carpet.json',
                          'throne.json', 'temple.json', 'tower.json'])
        self.assertEqual(len(CHAPTER_KEYS), len(CHAPTERS))
        self.assertEqual(len({chapter.program for chapter in CHAPTERS}), 7)

    def test_collection_persists_and_preserves_other_instance_unlocks(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'collection.json'
            first, second = CutsceneCollection.load(path), CutsceneCollection.load(path)
            self.assertEqual(first.seen, set(OPENING_KEYS))
            first.unlock('voyage', 'unknown')
            second.unlock('carpet')
            self.assertEqual(CutsceneCollection.load(path).seen, OPENING_KEYS | {'voyage', 'carpet'})
            self.assertEqual(json.loads(path.read_text())['version'], 1)

    def test_bad_profile_and_write_error_do_not_interrupt_the_game(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'collection.json'
            for data in ('[]', '{bad', '{"version":1,"seen":[4]}',
                         '{"version":8,"seen":["tower"]}'):
                path.write_text(data)
                self.assertEqual(CutsceneCollection.load(path).seen, set(OPENING_KEYS))
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
            self.assertEqual(collection.seen, OPENING_KEYS | {'voyage', 'discovery', 'carpet'})
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
        return CutsceneGallery(CutsceneCollection(Path('unused-test-profile.json'), seen={'opening'}),
                               Mock(return_value=Image.new('RGB', (510, 384), '#773311')))

    def test_horizontal_navigation_and_explicit_activation(self):
        gallery = self.gallery()
        self.assertEqual(list(gallery.visible), [0, 1, 2, 3, 4, 5])
        self.assertEqual(gallery.key('Return'), 'cutscene_play')
        gallery.key('Right')
        self.assertEqual(gallery.key('Return'), 'changed')
        gallery.key('End')
        self.assertEqual(gallery.index, 8)
        gallery.advance(1)
        self.assertEqual(list(gallery.visible), [4, 5, 6, 7, 8])
        gallery.key('Right')
        self.assertEqual(gallery.index, 8)
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

    def test_wheel_is_continuous_eased_and_independent_of_selection(self):
        gallery = self.gallery()
        gallery.wheel(.25)
        self.assertEqual(gallery.scroll, 0)
        self.assertGreater(gallery.scroll_target, 0)
        self.assertLess(gallery.scroll_target, gallery.PITCH)
        self.assertTrue(gallery.advance(1 / 60))
        self.assertGreater(gallery.scroll, 0)
        self.assertLess(gallery.scroll, gallery.scroll_target)
        self.assertEqual(gallery.index, 0)
        gallery.wheel(100)
        gallery.advance(1)
        self.assertEqual(gallery.scroll, gallery.max_scroll)
        gallery.wheel(-100)
        gallery.advance(1)
        self.assertEqual(gallery.scroll, 0)

    def test_drag_browses_without_selecting_and_click_selects_on_release(self):
        gallery = self.gallery()
        self.assertTrue(gallery.begin_drag(200, 150))
        gallery.move_drag(164.5)
        gallery.end_drag(164.5, 150)
        self.assertEqual(gallery.scroll, 35.5)
        self.assertEqual(gallery.index, 0)
        rect = gallery.card_rect(2)
        x, y = (rect[0] + rect[2]) / 2, 150
        gallery.begin_drag(x, y)
        gallery.end_drag(x, y)
        self.assertEqual(gallery.index, 2)

    def test_hd_thumbnail_uses_source_pixels_instead_of_a_small_upscaled_card(self):
        from PIL import ImageChops

        gallery = self.gallery()
        source = Image.effect_noise((510, 384), 100).convert('RGB')
        gallery.preview.return_value = source
        image = gallery.draw(Image.new('RGBA', (2048, 1536)), CaptionFont())
        rect = gallery.card_rect(0)
        thumb = tuple(round(v * 4) for v in (rect[0] + 2, rect[1] + 2, rect[2] - 2, rect[1] + 112))
        expected = source.resize((thumb[2] - thumb[0], thumb[3] - thumb[1]), Image.Resampling.NEAREST)
        self.assertIsNone(ImageChops.difference(image.crop(thumb).convert('RGB'), expected).getbbox())


    def test_two_rows_stay_dense_and_arrow_keys_follow_the_grid(self):
        gallery = self.gallery()
        first = [gallery.card_rect(i) for i in range(6)]
        self.assertEqual([rect[1] for rect in first], [63, 201, 63, 201, 63, 201])
        self.assertEqual([rect[0] for rect in first], [21, 21, 181, 181, 341, 341])
        self.assertGreater(first[0][2] - first[0][0], 140)
        gallery.key('Down')
        self.assertEqual(gallery.index, 1)
        gallery.key('Up')
        self.assertEqual(gallery.index, 0)
        for _ in range(3):
            gallery.key('Right')
        self.assertEqual(gallery.index, 6)
        self.assertGreater(gallery.scroll_target, 0)
        gallery.key('Left')
        self.assertEqual(gallery.index, 4)

    def test_scroll_frames_do_not_load_redraw_fonts_or_resample_images(self):
        gallery, font = self.gallery(), CaptionFont()
        viewport = Image.new('RGBA', (1530, 1152))
        gallery.draw(viewport, font)
        grid = gallery.grid_cache[1]
        with patch.object(gallery, 'preview', side_effect=AssertionError('Loaded during scroll')), \
                patch.object(font, 'text', side_effect=AssertionError('Drew text during scroll')), \
                patch.object(Image.Image, 'resize', side_effect=AssertionError('Resized during scroll')):
            gallery.wheel(.5)
            for _ in range(20):
                gallery.advance(1 / 60)
                gallery.draw(viewport, font)
                self.assertIs(gallery.grid_cache[1], grid)



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
        # Exercise the portable Tk renderer here; the native-surface test below
        # also verifies the Windows path without mapping or focusing a window.
        self.scene.native_cutscene_presentation = lambda: False

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

    def test_intro_parts_reconstruct_silently_and_stop_at_their_own_boundaries(self):
        from pop2.cutscenes import chapter_range
        from pop2.cutscene_viewer import chapter_player
        from pop2.intro import IntroAssets

        assets = IntroAssets()
        operations = assets.program['operations']
        bounds = [chapter_range(chapter, assets.program) for chapter in CHAPTERS[:3]]
        self.assertEqual(bounds[0][0], 0)
        self.assertEqual(bounds[0][1], bounds[1][0])
        handoff = operations[bounds[1][1]:bounds[2][0]]
        self.assertFalse(any(op['op'] == 'text' and op['args'][1] for op in handoff))
        self.assertIsNone(bounds[2][1])
        for chapter, (_start, end) in zip(CHAPTERS[:3], bounds):
            with self.subTest(chapter=chapter.key):
                audio = Mock()
                player = chapter_player(chapter, assets, audio)
                # Seeking never dispatches prior narration to the audio adapter.
                self.assertLessEqual(audio.play_intro.call_count, 2)
                player.advance(1200)
                self.assertTrue(player.done)
                self.assertEqual(player.position, end or len(operations))
                self.assertEqual(assets.program['operations'], operations)

    def test_device_presentation_reuses_the_photo_and_keeps_the_world_paused_while_scrolling(self):
        from PIL import ImageChops, ImageTk
        from pop2.game_ui import fit_viewport

        scene = self.scene
        gallery = self.open_viewer()
        before = self.snapshot()
        with patch.object(scene.canvas, 'winfo_width', return_value=1920), \
                patch.object(scene.canvas, 'winfo_height', return_value=1080):
            scene.present_viewport()
            size, _position = fit_viewport(1920, 1080)
            source = scene.screenshot_viewport.crop((1, 0, 511, 384)).resize(size, Image.Resampling.NEAREST)
            expected = gallery.draw(source, scene.ui_font, visible=True).convert('RGB')
            actual = ImageTk.getimage(scene.image_ref).convert('RGB')
            self.assertIsNone(ImageChops.difference(actual, expected).getbbox())
            low = gallery.draw(scene.screenshot_viewport, scene.ui_font).crop((1, 0, 511, 384))
            self.assertIsNotNone(ImageChops.difference(actual, low.convert('RGB').resize(size)).getbbox())
            photo = scene.image_ref
            scene.dev_scroll(SimpleNamespace(delta=-60, num=None))
            self.assertGreater(gallery.scroll_target, 0)
            self.assertEqual(gallery.index, 0)
            gallery.advance(1 / 60)
            scene.present_viewport()
            self.assertIs(scene.image_ref, photo)
        self.assertTrue(scene.paused)
        self.assertEqual(self.snapshot(), before)

    def test_incremental_scroll_pixels_match_full_render_in_both_directions_and_after_toast(self):
        from PIL import ImageChops, ImageTk

        scene = self.scene
        gallery = self.open_viewer()
        with patch.object(scene.canvas, 'winfo_width', return_value=1280), \
                patch.object(scene.canvas, 'winfo_height', return_value=960):
            scene.present_viewport()
            photo = scene.image_ref
            for step in (1, 1, -1, -1, 20, -20):
                gallery.wheel(step)
                for _ in range(3):
                    gallery.advance(1 / 60)
                    with patch('PIL.ImageChops.difference', side_effect=AssertionError('Compared full frame during scroll')):
                        scene.present_viewport()
                    source = scene._cutscene_gallery_source[2]
                    expected = gallery.draw(source, scene.ui_font, visible=True,
                                            background_key=id(scene.screenshot_viewport)).convert('RGB')
                    actual = ImageTk.getimage(photo).convert('RGB')
                    self.assertIsNone(ImageChops.difference(actual, expected).getbbox())
                    self.assertIs(scene.image_ref, photo)
            scene.screenshot_toast = 'Saved screenshot'
            scene.present_viewport()
            gallery.wheel(1)
            gallery.advance(1 / 60)
            scene.present_viewport()
            expected = scene.draw_screenshot_notice(gallery.draw(source, scene.ui_font, visible=True,
                background_key=id(scene.screenshot_viewport)), visible=True).convert('RGB')
            self.assertIsNone(ImageChops.difference(ImageTk.getimage(photo).convert('RGB'), expected).getbbox())

    def test_native_surface_matches_pixels_in_both_window_modes_and_returns_to_tk(self):
        import sys
        from PIL import ImageChops, ImageTk

        if sys.platform != 'win32':
            self.skipTest('Windows bitmap surface required')
        scene = self.scene
        gallery = self.open_viewer()
        # Set the renderer flag on the hidden fixture; never map/focus a window.
        scene.native_cutscene_presentation = lambda: True
        scene.fullscreen = False
        with patch.object(scene.canvas, 'winfo_width', return_value=1920), \
                patch.object(scene.canvas, 'winfo_height', return_value=1080):
            bitmap = None
            for fullscreen in (False, True, True, False):
                scene.fullscreen = fullscreen
                gallery.wheel(.25)
                gallery.advance(1 / 60)
                scene.present_viewport()
                presenter = scene.bitmap_presenter
                if bitmap is None:
                    bitmap = presenter.bitmap
                self.assertIs(presenter.bitmap, bitmap)
                self.assertIsNone(scene.image_ref)
                raw = bitmap.tobytes()
                width, height = bitmap.size
                stride = (width * 3 + 3) // 4 * 4
                actual = Image.frombytes('RGB', (width, height), raw, 'raw', 'BGR', stride, -1)
                expected = gallery.draw(scene._cutscene_gallery_source[2], scene.ui_font, visible=True,
                    background_key=id(scene.screenshot_viewport)).convert('RGB')
                self.assertIsNone(ImageChops.difference(actual, expected).getbbox())
                scene.root.update_idletasks()  # Flush the hidden surface's idle paint.
            scene.apply_game_action('cutscene_back')
            self.assertIsNone(scene.bitmap_presenter)
            self.assertIsNotNone(scene.image_ref)
            expected_menu = scene.native_viewport.crop((1, 0, 511, 384)).convert('RGB').resize(expected.size, Image.Resampling.NEAREST)
            self.assertIsNone(ImageChops.difference(ImageTk.getimage(scene.image_ref).convert('RGB'), expected_menu).getbbox())

    def test_pointer_drag_does_not_play_or_select_and_leave_cancels_the_drag(self):
        scene = self.scene
        gallery = self.open_viewer()
        with patch.object(scene, 'dev_pointer', return_value=(220, 150)):
            scene.dev_click(SimpleNamespace(num=1))
        with patch.object(scene, 'dev_pointer', return_value=(180, 150)):
            scene.dev_hover(SimpleNamespace())
            scene.dev_release(SimpleNamespace(num=1))
        self.assertEqual(gallery.scroll, 40)
        self.assertEqual(gallery.index, 0)
        self.assertIsNone(scene.cutscene_replay)
        with patch.object(scene, 'dev_pointer', return_value=(220, 150)):
            scene.dev_click(SimpleNamespace(num=1))
        scene.pause_if_unfocused()
        self.assertIsNone(gallery.drag)
        with patch.object(scene, 'dev_pointer', return_value=(220, 150)):
            scene.dev_click(SimpleNamespace(num=1))
        scene.dev_pointer_leave(SimpleNamespace())
        self.assertIsNone(gallery.drag)

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
        self.assertEqual(scene.cutscene_collection.seen, set(OPENING_KEYS))

        scene.close_game_menu()
        scene.with_intro = True
        scene.seek_playback_part(next(part for part in scene.development_parts() if part.stage == 'temple'))
        self.assertEqual(scene.cutscene_collection.seen, set(OPENING_KEYS))

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
        self.assertEqual(scene.cutscene_collection.seen, set(OPENING_KEYS))
        path = Path(self.directory.name) / 'old-save.pop2save'
        write_save(path, capture(scene.game))
        self.assertEqual(scene.cutscene_collection.seen, set(OPENING_KEYS))
        scene.load_game_from(path)
        self.assertEqual(scene.cutscene_collection.seen, OPENING_KEYS | {'voyage', 'discovery', 'carpet'})

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
