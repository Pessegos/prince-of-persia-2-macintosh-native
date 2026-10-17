import random
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image, ImageChops

from pop2.development_map import DevelopmentMap, MAP_SIZE, build_development_map, room_positions
from pop2.game_ui import DevelopmentMenu
from pop2.paths import ASSET_DIR


def preview():
    return DevelopmentMap(Image.new('RGB', MAP_SIZE, '#101010'),
                          {'Room 1': (0, 0, 50, 40), 'Room 2': (50, 0, 100, 40),
                           'Room 3': (50, 40, 100, 80)},
                          {'Room 1': (0, 0), 'Room 2': (1, 0), 'Room 3': (1, 1)})


class DevelopmentMapModelTests(unittest.TestCase):
    def menu(self):
        atlas = preview()
        return DevelopmentMenu(tuple(atlas.rooms), 0, False,
                               level_options=((3, 'Level 3', tuple(atlas.rooms)),),
                               map_provider=lambda _number: atlas, focus=4)

    def test_map_hits_are_half_open_and_do_not_select_gaps(self):
        atlas = preview()
        for point, expected in (((0, 0), 'Room 1'), ((49.9, 39.9), 'Room 1'),
                                ((50, 0), 'Room 2'), ((50, 40), 'Room 3'),
                                ((0, 40), None), ((100, 20), None), ((-1, 0), None)):
            self.assertEqual(atlas.hit(*point), expected)

    def test_spatial_keys_and_enter_select_without_numeric_room_order(self):
        menu = self.menu()
        self.assertEqual(menu.key('Right'), 'changed')
        self.assertEqual(menu.screen, 'Room 2')
        menu.key('Down')
        self.assertEqual(menu.screen, 'Room 3')
        self.assertEqual(menu.key('Return'), 'go')
        menu.key('Down')
        self.assertEqual(menu.screen, 'Room 3')
        menu.key('Up')
        self.assertEqual(menu.screen, 'Room 2')
        menu.key('Tab')
        self.assertEqual(menu.focus, 1)

    def test_hover_is_transient_and_click_is_direct_teleport(self):
        menu = self.menu()
        self.assertTrue(menu.hover(84, 120))
        self.assertEqual(menu.hovered_screen, 'Room 2')
        self.assertEqual(menu.screen, 'Room 1')
        self.assertFalse(menu.hover(84, 120))
        self.assertTrue(menu.hover(200, 250))
        self.assertIsNone(menu.hovered_screen)
        self.assertEqual(menu.click(200, 250), 'changed')
        self.assertEqual(menu.screen, 'Room 1')
        self.assertEqual(menu.click(84, 120), 'go')
        self.assertEqual(menu.screen, 'Room 2')
        self.assertTrue(menu.hover(-1, -1))
        self.assertIsNone(menu.hovered_screen)

    def test_only_level_field_opens_dropdown_and_popup_has_hit_priority(self):
        menu = self.menu()
        menu.open_dropdown()
        self.assertFalse(menu.dropdown)
        menu.focus = 0
        menu.open_dropdown()
        self.assertTrue(menu.dropdown)
        self.assertEqual(menu.click(220, 99), 'changed')
        self.assertFalse(menu.dropdown)
        self.assertEqual(menu.screen, 'Room 1')

    def test_level_changes_clear_hover_without_loading_or_teleporting_game(self):
        menu = self.menu()
        menu.level_options += ((4, 'Level 4', ('Other',)),)
        menu.hover(84, 120)
        menu.focus = 0
        menu.select(1)
        self.assertEqual((menu.level_number, menu.screen), (4, 'Other'))
        self.assertIsNone(menu.hovered_screen)
        menu.change_tab(1)
        self.assertFalse(menu.map_enabled)

    def test_map_panel_and_controls_remain_inside_playfield(self):
        menu = self.menu()
        left, top, right, bottom = menu.panel_rect
        self.assertEqual(left + right, 512)
        self.assertLessEqual(abs(top - (365 - bottom)), 1)
        for control in menu.controls:
            x1, y1, x2, y2 = menu.control_rect(control)
            self.assertTrue(left < x1 < x2 < right)
            self.assertTrue(top < y1 < y2 < bottom)

    def test_invalid_flat_map_links_are_rejected(self):
        links = {(0, 'right'): 1, (1, 'down'): 0}
        terrain = SimpleNamespace(start_room=0, neighbor=lambda room, side: links.get((room, side)))
        with self.assertRaisesRegex(ValueError, 'flat map'):
            room_positions(terrain)


@unittest.skipUnless((ASSET_DIR / 'caverns_entry.json').is_file(), 'Imported game resources required')
class ImportedDevelopmentMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pop2.game_session import GameResources
        cls.resources = GameResources.load()

    def test_all_supported_levels_have_real_scenery_and_selectable_rooms(self):
        from pop2.level_rendering import LevelRenderer
        from pop2.terrain import LevelMap

        for number in (1, 2, 3):
            with self.subTest(level=number):
                level = self.resources.level(number)
                atlas = build_development_map(level)
                self.assertEqual(atlas.image.size, MAP_SIZE)
                self.assertEqual(set(atlas.rooms), set(LevelRenderer(level).screen_entries()))
                positions = room_positions(LevelMap(level.data))
                self.assertTrue(set(atlas.positions.values()).issubset(set(positions.values())))
                self.assertGreater(len(atlas.image.getcolors(100000)), 200)
                for label, (left, top, right, bottom) in atlas.rooms.items():
                    self.assertEqual(atlas.hit((left + right) / 2, (top + bottom) / 2), label)
                    self.assertEqual(atlas.source_frames[label].size, (510, 360))

    def test_cavern_preview_includes_original_bones_without_touching_rng(self):
        level = self.resources.level(3)
        before = random.getstate()
        atlas = build_development_map(level)
        self.assertEqual(random.getstate(), before)
        clean = build_development_map(level, include_enemies=False)
        self.assertEqual(len(atlas.rooms), 32)
        self.assertEqual(atlas.enemy_rooms,
                         {'Room 4', 'Room 6', 'Room 11', 'Room 15', 'Room 20', 'Room 25', 'Room 29'})
        changed = {label for label in atlas.rooms if ImageChops.difference(
            atlas.source_frames[label], clean.source_frames[label]).getbbox() is not None}
        self.assertEqual(changed, atlas.enemy_rooms)
        from pop2.development_map import map_enemies
        _art, actors = map_enemies(level, range(32))
        self.assertTrue(all(actor.state.action in range(206, 210)
                            for entries in actors.values() for actor in entries))

    def test_high_resolution_uses_native_sources_and_reuses_bounded_cache(self):
        atlas = build_development_map(self.resources.level(3))
        high = atlas.detail((1856, 776))
        self.assertIs(atlas.detail(high.size), high)
        enlarged = atlas.image.resize(high.size, Image.Resampling.NEAREST)
        self.assertIsNotNone(ImageChops.difference(high, enlarged).getbbox())
        atlas.detail((928, 388))
        self.assertEqual(len(atlas.scaled_images), 1)

    def test_labels_only_render_on_hover_and_popup_survives_high_resolution(self):
        from pop2.game_ui import MacintoshFont

        atlas = build_development_map(self.resources.level(3))
        font = MacintoshFont(self.resources.prince['NFNT'][23331]['data'])
        menu = DevelopmentMenu(tuple(atlas.rooms), 0, False,
                               level_options=((3, 'Level 3', tuple(atlas.rooms)),),
                               map_provider=lambda _number: atlas)
        native = Image.new('RGBA', (512, 384))
        with patch.object(font, 'text', wraps=font.text) as text:
            menu.draw(native, font)
        self.assertFalse(any(call.args[0].startswith('Room ') for call in text.call_args_list))
        rect = atlas.rooms['Room 32']
        menu.hover(24 + (rect[0] + rect[2]) / 2, 100 + (rect[1] + rect[3]) / 2)
        with patch.object(font, 'text', wraps=font.text) as text:
            menu.draw(native, font)
        self.assertIn('Room 32', [call.args[0] for call in text.call_args_list])
        menu.focus = 0
        menu.open_dropdown()
        native = menu.draw(native, font)
        for size in ((510, 384), (1020, 768), (1912, 1440), (800, 602)):
            frame = native.crop((1, 0, 511, 384)).resize(size, Image.Resampling.NEAREST)
            before = frame.copy()
            menu.present_map(frame, font)
            sx, sy = size[0] / 510, size[1] / 384
            rect = (round(199 * sx), round(93 * sy), round(488 * sx), round(113 * sy))
            self.assertEqual(frame.crop(rect).tobytes(), before.crop(rect).tobytes())

    def test_scene_map_cache_is_lazy_read_only_and_mouse_teleport_uses_safe_entry(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        s = self.scene
        s.load_level(3)
        self.assertFalse(hasattr(s, 'development_maps'))
        before = (s.room_id, s.player_x, s.background.tobytes(), s.sequence_state.__dict__.copy(),
                  s.combat.world_frame, random.getstate())
        s.open_dev_mode()
        atlas = s.dev_menu.map_preview
        self.assertIs(s.development_map(3), atlas)
        self.assertEqual(before, (s.room_id, s.player_x, s.background.tobytes(),
                                  s.sequence_state.__dict__, s.combat.world_frame, random.getstate()))
        rect = atlas.rooms['Room 28']
        point = 24 + (rect[0] + rect[2]) / 2, 100 + (rect[1] + rect[3]) / 2
        with patch.object(s, 'dev_pointer', return_value=point):
            s.dev_hover(SimpleNamespace())
            self.assertEqual(s.canvas.cget('cursor'), 'hand2')
            s.dev_pointer_leave(None)
            self.assertIsNone(s.dev_menu.hovered_screen)
            self.assertEqual(s.canvas.cget('cursor'), '')
            s.dev_click(SimpleNamespace(num=1))
        self.assertEqual(s.room_id, 27)
        self.assertIsNone(s.dev_menu)
        self.assertFalse(s.paused)

    def test_actual_presenter_uses_high_resolution_map_after_resize(self):
        from PIL import ImageTk
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        s = self.scene
        s.load_level(3)
        s.open_dev_mode()
        native = s.native_viewport.copy()
        for width, height in ((1020, 768), (1920, 1080), (2560, 1440)):
            with self.subTest(size=(width, height)), \
                    patch.object(s.canvas, 'winfo_width', return_value=width), \
                    patch.object(s.canvas, 'winfo_height', return_value=height):
                s.present_viewport()
                actual = ImageTk.getimage(s.image_ref).convert('RGB')
                low = native.crop((1, 0, 511, 384)).resize(actual.size, Image.Resampling.NEAREST)
                expected = s.dev_menu.present_map(low.copy(), s.ui_font).convert('RGB')
                self.assertEqual(actual.tobytes(), expected.tobytes())
                self.assertIsNotNone(ImageChops.difference(actual, low.convert('RGB')).getbbox())
                self.assertEqual(s.native_viewport.tobytes(), native.tobytes())
