from pathlib import Path
import random
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

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
        self.assertEqual(menu.gallery_page, 1)
        self.assertEqual(set(menu.gallery_preview.rooms), {str(i) for i in range(6, 12)})
        self.assertEqual(menu.key('Return'), 'seek')
        menu.focus = 10
        menu.activate()
        self.assertEqual(menu.gallery_page, 2)
        self.assertEqual(menu.section_index, 12)
        menu.activate()
        self.assertEqual(menu.gallery_page, 0)
        menu.focus = 6
        menu.activate()
        self.assertEqual(menu.group_index, 1)
        self.assertEqual(menu.section_index, 16)
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
            self.assertTrue(1 < left < right < 511 and 0 < top < bottom < 365)
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

    def test_held_activation_cannot_play_accidentally_and_click_uses_original_seek_with_pause_state(self):
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
            self.assertEqual(s.paused, paused)
