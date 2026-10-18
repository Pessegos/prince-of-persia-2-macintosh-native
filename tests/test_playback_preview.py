from pathlib import Path
import random
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from PIL import Image, ImageStat, ImageTk

from pop2.game_ui import DevelopmentMenu
from pop2.paths import ASSET_DIR
from pop2.playback_navigation import PlaybackGroup


def part_point(menu, index):
    x1, y1, x2, y2 = menu.gallery_preview.rooms[str(index)]
    left, top, _right, _bottom = menu.control_rect(4)
    return left + (x1 + x2) / 2, top + (y1 + y2) / 2


class GalleryModelTests(unittest.TestCase):
    def menu(self):
        frames = {i: Image.new('RGB', (510, 384), (i * 13 % 256, 64, 150)) for i in range(20)}
        provider = Mock(side_effect=lambda indices: {i: frames[i] for i in indices})
        menu = DevelopmentMenu(('Room 1',), 0, False,
            sections=tuple(f'Story {i + 1}' for i in range(20)),
            section_groups=(PlaybackGroup('Prologue', tuple(range(16))),
                            PlaybackGroup('Credits', tuple(range(16, 20)))),
            playback_provider=provider, level_available=False)
        return menu, provider

    def test_gallery_is_lazy_paginated_and_keyboard_selection_tracks_visible_page(self):
        menu, provider = self.menu()
        menu.activate()
        self.assertTrue(menu.gallery_enabled)
        self.assertEqual(menu.focus, 4)
        provider.assert_not_called()
        menu.key('Down')
        menu.key('Down')
        self.assertEqual(menu.section_index, 6)
        self.assertTrue(menu.preview_keyboard_selection)
        self.assertEqual(menu.gallery_page, 1)
        self.assertEqual(set(menu.gallery_preview.rooms), {str(i) for i in range(6, 12)})
        self.assertEqual(menu.key('Return'), 'seek')
        menu.focus = 10
        menu.activate()
        self.assertEqual(menu.gallery_page, 2)
        self.assertEqual(menu.section_index, 12)
        self.assertFalse(menu.preview_keyboard_selection)
        menu.activate()
        self.assertEqual(menu.gallery_page, 0)
        menu.focus = 6
        menu.activate()
        self.assertEqual(menu.group_index, 1)
        self.assertEqual(menu.section_index, 16)
        self.assertFalse(menu.preview_keyboard_selection)
        self.assertNotIn(9, menu.controls)
        self.assertNotIn(10, menu.controls)

    def test_hover_never_seeks_but_clicking_a_thumbnail_does_and_gaps_do_not(self):
        menu, _provider = self.menu()
        menu.activate()
        point = part_point(menu, 2)
        self.assertTrue(menu.hover(*point))
        self.assertEqual(menu.hovered_part, 2)
        self.assertEqual(menu.section_index, 0)
        self.assertFalse(menu.hover(*point))
        self.assertEqual(menu.click(172, 60), 'changed')
        self.assertEqual(menu.section_index, 0)
        self.assertEqual(menu.click(*point), 'seek')
        self.assertEqual(menu.section_index, 2)
        self.assertTrue(menu.hover(-1, -1))
        self.assertIsNone(menu.hovered_part)

    def test_only_visible_frames_load_and_recent_pages_reuse_their_hd_images(self):
        menu, provider = self.menu()
        menu.activate()
        first = menu.gallery_preview
        provider.assert_called_once_with(tuple(range(6)))
        hd = first.detail((976, 556))
        menu.turn_gallery_page(1)
        menu.gallery_preview
        self.assertEqual(provider.call_args_list, [call(tuple(range(6))), call(tuple(range(6, 12)))])
        menu.turn_gallery_page(-1)
        self.assertIs(menu.gallery_preview, first)
        self.assertIs(menu.gallery_preview.detail((976, 556)), hd)
        self.assertEqual(provider.call_count, 2)

    def test_page_cache_is_bounded_and_keeps_the_most_recently_used_page(self):
        menu, provider = self.menu()
        menu.sections += tuple(f'Extra {i}' for i in range(6))
        menu.section_groups += (PlaybackGroup('More', tuple(range(20, 26))),)
        provider.side_effect = lambda indices: {i: Image.new('RGB', (510, 384)) for i in indices}
        menu.activate()
        first = menu.gallery_preview
        for page in (1, 2):
            menu.turn_gallery_page(page - menu.gallery_page)
            menu.gallery_preview
        menu.focus = 0
        menu.select(1)
        menu.gallery_preview
        menu.focus = 0
        menu.select(0)
        self.assertIs(menu.gallery_preview, first)
        menu.focus = 0
        menu.select(2)
        menu.gallery_preview
        self.assertEqual(len(menu.gallery_pages), 4)
        self.assertNotIn(tuple(range(6, 12)), menu.gallery_pages)
        menu.focus = 0
        menu.select(0)
        self.assertIs(menu.gallery_preview, first)
        self.assertEqual(provider.call_count, 5)

    def test_popup_back_escape_and_all_controls_fit_and_keep_selection(self):
        menu, _provider = self.menu()
        menu.activate()
        menu.focus = 0
        menu.open_dropdown()
        menu.key('Down')
        self.assertEqual(menu.group_index, 0)
        menu.key('Return')
        self.assertEqual(menu.group_index, 1)
        for _ in range(len(menu.controls) * 2):
            menu.key('Tab')
            self.assertIn(menu.focus, menu.controls)
            left, top, right, bottom = menu.control_rect(menu.focus)
            self.assertTrue(1 < left < right < 511 and 0 < top < bottom < 384)
        menu.focus = 0
        menu.open_dropdown()
        self.assertEqual(menu.key('Escape'), 'changed')
        self.assertTrue(menu.gallery_enabled)
        self.assertEqual(menu.key('Escape'), 'changed')
        self.assertEqual(menu.page, 'tools')
        self.assertEqual(menu.focus, 8)
        menu.activate()
        self.assertEqual(menu.group_index, 1)
        self.assertEqual(menu.key('Escape'), 'changed')
        self.assertEqual(menu.key('Escape'), 'resume')

    def test_caption_regions_stay_inside_the_gallery_and_separate_from_every_image(self):
        from pop2.playback_preview import GALLERY_SIZE, gallery_caption_rect, gallery_preview

        frames = {i: Image.new('RGB', (510, 384)) for i in range(6)}
        for count in range(1, 7):
            atlas = gallery_preview(frames, tuple(range(count)))
            for index, rect in atlas.rooms.items():
                caption = gallery_caption_rect(rect, count == 1)
                if count > 1:
                    self.assertEqual((rect[2] - rect[0], rect[3] - rect[1]), (152, 114))
                self.assertEqual(caption[1] - rect[3], 2)
                self.assertTrue(0 <= caption[0] < caption[2] <= GALLERY_SIZE[0])
                self.assertTrue(rect[3] < caption[1] < caption[3] <= GALLERY_SIZE[1])
                for other in atlas.rooms.values():
                    self.assertFalse(caption[0] < other[2] and caption[2] > other[0]
                                     and caption[1] < other[3] and caption[3] > other[1], (index, other))

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
class ImportedGalleryTests(unittest.TestCase):
    def setUp(self):
        from tests.test_attract_scene import AttractSceneTests

        AttractSceneTests.setUp(self)

    def open_gallery(self):
        s = self.scene
        s.open_dev_mode()
        s.dev_menu.focus = 8
        s.apply_dev_action(s.dev_menu.activate())
        return s.dev_menu

    def test_compact_captions_fit_without_clipping_the_scaled_bitmap(self):
        from pop2.playback_preview import gallery_caption

        font = self.scene.ui_font
        for density in (1, 3):
            for label in ('Treachery Revealed', 'Credits - Page 4', 'The Sultan Leaves'):
                with self.subTest(label=label, density=density):
                    scale = 0.75 * density
                    caption = gallery_caption(font, label, (160 * density, 20 * density),
                                              '#eeeeee', scale=scale)
                    glyph = font.text(label, '#eeeeee')
                    glyph = glyph.crop(glyph.getbbox())
                    glyph = glyph.resize((round(glyph.width * scale), round(glyph.height * scale)),
                                         Image.Resampling.NEAREST)
                    alpha = caption.getchannel('A')
                    expected = glyph.getchannel('A')
                    self.assertEqual(alpha.crop(alpha.getbbox()).tobytes(),
                                     expected.crop(expected.getbbox()).tobytes())
                    self.assertGreater(caption.getbbox()[0], 0)
                    self.assertLess(caption.getbbox()[2], caption.width)
                    self.assertLess(caption.getbbox()[3] - caption.getbbox()[1], font.height * density)

    def test_cyan_indicates_only_the_actual_part_not_the_browsed_group_or_keyboard_choice(self):
        menu, _provider = GalleryModelTests().menu()
        menu.current_section = 0
        menu.activate()
        menu.key('Down')
        menu.key('Right')
        menu.key('Right')
        layer = menu.gallery_layer(self.scene.ui_font)
        first = menu.gallery_preview.rooms['0']
        selected = menu.gallery_preview.rooms['5']
        self.assertEqual(layer.getpixel(first[:2])[:3], (99, 200, 229))
        self.assertEqual(layer.getpixel(selected[:2])[:3], (238, 238, 238))
        menu.focus = 6
        menu.activate()
        layer = menu.gallery_layer(self.scene.ui_font)
        self.assertNotIn((99, 200, 229, 255),
                         {color for _count, color in layer.getcolors(layer.width * layer.height)})
        menu.focus = 5
        menu.activate()
        layer = menu.gallery_layer(self.scene.ui_font)
        self.assertEqual(layer.getpixel(menu.gallery_preview.rooms['0'][:2])[:3], (99, 200, 229))

    def test_no_white_default_marker_on_open_group_page_or_mouse_hover(self):
        menu, _provider = GalleryModelTests().menu()
        menu.activate()

        def no_white_marker():
            menu.focus = 4
            layer = menu.gallery_layer(self.scene.ui_font)
            for index, rect in menu.gallery_preview.rooms.items():
                self.assertNotEqual(layer.getpixel(rect[:2])[:3], (238, 238, 238), index)

        no_white_marker()
        menu.key('Right')
        self.assertTrue(menu.preview_keyboard_selection)
        menu.hover(*part_point(menu, 2))
        self.assertFalse(menu.preview_keyboard_selection)
        no_white_marker()
        menu.key('Right')
        menu.turn_gallery_page(1)
        no_white_marker()
        menu.key('Right')
        menu.focus = 0
        menu.select(1)
        no_white_marker()

    def test_gallery_covers_the_entire_original_hud_even_when_browsing_credits(self):
        menu = self.open_gallery()
        native = Image.new('RGBA', (512, 384), '#ff00ff')
        menu.focus = 0
        menu.select(0)
        menu.turn_gallery_page(menu.gallery_count - 1)
        result = menu.draw(native, self.scene.ui_font)
        self.assertEqual(menu.panel_rect, (1, 0, 511, 384))
        hud, footer = result.crop((1, 365, 511, 384)), result.crop((1, 373, 511, 384))
        self.assertNotIn((255, 0, 255, 255), {color for _count, color in hud.getcolors(10000)})
        self.assertEqual(footer.getcolors(), [(footer.width * footer.height, (16, 16, 16, 255))])

    def test_gameplay_has_no_fake_current_cutscene(self):
        s = self.scene
        s.finish_intro()
        s.load_level(3)
        menu = self.open_gallery()
        self.assertIsNone(menu.current_section)

    def test_reopening_gallery_reuses_prepared_pages_without_reloading_or_rescaling(self):
        menu = self.open_gallery()
        first = menu.gallery_preview
        hd = first.detail((976, 556))
        self.scene.close_dev_mode()
        with patch.object(self.scene, 'development_playback_preview',
                          side_effect=AssertionError('Reopening reloaded preview sources')):
            reopened = self.open_gallery()
            self.assertIs(reopened.gallery_preview, first)
            self.assertIs(reopened.gallery_preview.detail((976, 556)), hd)

    def test_every_part_has_native_visible_art_and_disk_cache_is_lossless_without_live_state_changes(self):
        from pop2.playback_preview import PlaybackPreviews

        s = self.scene
        parts = s.development_parts()
        before = (s.game, s.room_id, s.player_x, s.combat.world_frame,
                  s.intro, s.intro.time, s.intro.position, random.getstate())
        groups = self.open_gallery().groups
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
        for group in self.open_gallery().groups:
            players = {}
            for index in group.part_indices:
                with self.subTest(part=parts[index].label):
                    self.assertEqual(provider.snapshot(index, players).tobytes(),
                                     provider.snapshot(index).tobytes())

    def test_real_hover_updates_match_full_redraw_at_multiple_sizes_and_mouse_wheel_paginates(self):
        s = self.scene
        menu = self.open_gallery()
        for width, height in ((1020, 768), (1920, 1080), (2560, 1440), (800, 602)):
            with self.subTest(size=(width, height)), \
                    patch.object(s.canvas, 'winfo_width', return_value=width), \
                    patch.object(s.canvas, 'winfo_height', return_value=height):
                s.present_viewport()
                photo = s.image_ref
                points = [part_point(menu, i) for i in (0, 5, 2)] + [(20, 20), (20, 340), (-1, -1)]
                with patch.object(s, 'render', side_effect=AssertionError('Hover rendered live game')):
                    for point in points:
                        with patch.object(s, 'dev_pointer', return_value=point):
                            s.dev_hover(SimpleNamespace())
                        self.assertIs(s.image_ref, photo)
                        actual = ImageTk.getimage(photo).convert('RGB')
                        native = menu.draw(s.screenshot_viewport, s.ui_font)
                        low = native.crop((1, 0, 511, 384)).resize(actual.size, Image.Resampling.NEAREST)
                        self.assertEqual(actual.tobytes(), menu.present_map(low, s.ui_font).convert('RGB').tobytes())
        with patch.object(s, 'dev_pointer', return_value=part_point(menu, 0)):
            s.dev_scroll(SimpleNamespace(delta=-120))
        self.assertEqual(menu.gallery_page, 1)
        menu.focus = 0
        menu.open_dropdown()
        s.redraw_dev_menu()
        self.assertTrue(menu.dropdown)
        menu.key('Escape')
        s.redraw_dev_menu()
        self.assertFalse(menu.dropdown)

    def test_held_activation_cannot_play_accidentally_and_click_starts_playback(self):
        s = self.scene
        for paused in (False, True):
            s.set_paused(paused)
            s.open_dev_mode()
            s.dev_menu.focus = 8
            enter = SimpleNamespace(keysym='Return', state=0)
            s.dev_key_press(enter)
            s.dev_key_press(enter)
            menu = s.dev_menu
            self.assertIsNotNone(menu)
            self.assertTrue(menu.gallery_enabled)
            s.dev_key_release(enter)
            selected = s.development_parts()[1]
            with patch.object(s, 'seek_playback_part', wraps=s.seek_playback_part) as seek:
                s.apply_dev_action(menu.click(*part_point(menu, 1)))
            seek.assert_called_once_with(selected)
            self.assertIsNone(s.dev_menu)
            self.assertFalse(s.paused)

    def test_play_button_autoplays_but_resume_without_seeking_preserves_pause(self):
        s = self.scene
        s.set_paused(True)
        menu = self.open_gallery()
        s.apply_dev_action('resume')
        self.assertTrue(s.paused)
        menu = self.open_gallery()
        menu.focus = 2
        s.apply_dev_action(menu.activate())
        self.assertIsNone(s.dev_menu)
        self.assertFalse(s.paused)
