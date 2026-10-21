import random
from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from PIL import Image, ImageChops

from pop2.development_map import (DevelopmentMap, MAP_SIZE, build_development_map,
                                  level_landmarks, room_positions)
from pop2.game_ui import DevelopmentMenu
from pop2.paths import ASSET_DIR


def preview():
    return DevelopmentMap(Image.new('RGB', MAP_SIZE, '#101010'),
                          {'Room 1': (0, 0, 50, 40), 'Room 2': (50, 0, 100, 40),
                           'Room 3': (50, 40, 100, 80)},
                          {'Room 1': (0, 0), 'Room 2': (1, 0), 'Room 3': (1, 1)})


def room_point(menu, label):
    rect = menu.map_preview.rooms[label]
    left, top, right, bottom = menu.control_rect(4)
    scale, (ox, oy) = menu.map_preview.transform((right - left, bottom - top))
    return left + ox + (rect[0] + rect[2]) / 2 * scale, top + oy + (rect[1] + rect[3]) / 2 * scale


class DevelopmentMapModelTests(unittest.TestCase):
    def test_landmarks_use_native_start_and_all_exit_rooms_but_not_entrance(self):
        labels = {0: 'Room 1', 12: 'Room 13', 29: 'Room 30', 31: 'Room 32'}
        exits = {(0, 14), (12, 16), (29, 25)}
        terrain = SimpleNamespace(tile=lambda room, column, row:
                                  SimpleNamespace(kind=17 if (room, row * 10 + column) in exits else 1))
        level = SimpleNamespace(number=3, start_room=0)
        self.assertEqual(level_landmarks(level, terrain, labels),
                         ('Room 1', frozenset({'Room 13', 'Room 30'})))

    def test_custom_endings_are_the_ship_and_stone_chamber_not_the_far_shore(self):
        terrain = SimpleNamespace(tile=lambda *_: SimpleNamespace(kind=1))
        self.assertEqual(level_landmarks(SimpleNamespace(number=1, start_room=3), terrain,
                                         {3: '1', 18: '10'}), ('1', frozenset({'10'})))
        self.assertEqual(level_landmarks(SimpleNamespace(number=2, start_room=1), terrain,
                                         {0: '2 (Stones)', 1: '1', 2: 'Right shore'}),
                         ('1', frozenset({'2 (Stones)'})))

    def menu(self, opened=True):
        atlas = preview()
        return DevelopmentMenu(tuple(atlas.rooms), 0, False,
                               level_options=((3, 'Level 3', tuple(atlas.rooms)),),
                               map_provider=lambda _number: atlas, focus=4, map_open=opened,
                               return_screens={3: 'Room 1'})

    def test_map_hits_are_half_open_and_do_not_select_gaps(self):
        atlas = preview()
        for point, expected in (((0, 0), 'Room 1'), ((49.9, 39.9), 'Room 1'),
                                ((50, 0), 'Room 2'), ((50, 40), 'Room 3'),
                                ((0, 40), None), ((100, 20), None), ((-1, 0), None)):
            self.assertEqual(atlas.hit(*point), expected)

    def test_open_map_is_a_separate_page_and_escape_returns_to_tools(self):
        menu = self.menu(opened=False)
        self.assertEqual(menu.controls, (4, 8, 1, 11, 3))
        self.assertFalse(menu.map_enabled)
        self.assertEqual(menu.key('Return'), 'changed')
        self.assertTrue(menu.map_enabled)
        self.assertEqual(menu.focus, 4)
        menu.key('Right')
        self.assertEqual(menu.screen, 'Room 2')
        self.assertEqual(menu.key('Escape'), 'changed')
        self.assertFalse(menu.map_enabled)
        self.assertEqual(menu.key('Return'), 'changed')
        self.assertTrue(menu.map_enabled)
        self.assertEqual(menu.screen, 'Room 2')
        menu.key('Escape')
        self.assertEqual(menu.key('Escape'), 'resume')

    def test_popup_back_button_and_level_arrows_do_not_close_tools_or_teleport(self):
        menu = self.menu()
        menu.level_options += ((4, 'Level 4', tuple(menu.map_preview.rooms)),)
        menu.focus = 6
        self.assertEqual(menu.activate(), 'changed')
        self.assertEqual(menu.level_number, 4)
        self.assertTrue(menu.map_enabled)
        self.assertEqual(menu.focus, 6)
        menu.focus = 5
        menu.activate()
        self.assertEqual(menu.level_number, 3)
        menu.focus = 0
        menu.open_dropdown()
        self.assertEqual(menu.key('Escape'), 'changed')
        self.assertFalse(menu.dropdown)
        self.assertTrue(menu.map_enabled)
        rect = menu.control_rect(7)
        self.assertEqual(menu.click(rect[0] + 4, rect[1] + 4), 'changed')
        self.assertFalse(menu.map_enabled)

    def test_map_preserves_aspect_ratio_and_hits_inside_taller_workspace(self):
        menu = self.menu()
        left, top, right, bottom = menu.control_rect(4)
        scale, (ox, oy) = menu.map_preview.transform((right - left, bottom - top))
        self.assertGreater(oy, 0)
        self.assertEqual(ox, 0)
        self.assertAlmostEqual(scale, (right - left) / MAP_SIZE[0])
        self.assertIsNone(menu.map_hit(left + 1, top + 1))
        for label in menu.map_preview.rooms:
            self.assertEqual(menu.map_hit(*room_point(menu, label)), label)

    def test_focus_order_never_visits_hidden_tabs_in_map(self):
        menu = self.menu()
        for _ in range(len(menu.controls) * 2):
            menu.key('Tab')
            self.assertIn(menu.focus, menu.controls)
        menu.key('Escape')
        self.assertEqual(menu.focus, 4)
        menu.key('Tab', backwards=True)
        self.assertEqual(menu.focus, 3)
        menu.focus = 8
        menu.activate()
        self.assertEqual(menu.page, 'playback')

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
        point = room_point(menu, 'Room 2')
        self.assertTrue(menu.hover(*point))
        self.assertEqual(menu.hovered_screen, 'Room 2')
        self.assertEqual(menu.screen, 'Room 1')
        self.assertFalse(menu.hover(*point))
        self.assertTrue(menu.hover(200, 250))
        self.assertIsNone(menu.hovered_screen)
        self.assertEqual(menu.click(200, 250), 'changed')
        self.assertEqual(menu.screen, 'Room 1')
        self.assertEqual(menu.click(*point), 'go')
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
        rect = menu.control_rect(0)
        self.assertEqual(menu.click(220, rect[3] + 6), 'changed')
        self.assertFalse(menu.dropdown)
        self.assertEqual(menu.screen, 'Room 1')

    def test_level_changes_clear_hover_without_loading_or_teleporting_game(self):
        menu = self.menu()
        menu.level_options += ((4, 'Level 4', ('Other',)),)
        menu.hover(*room_point(menu, 'Room 2'))
        menu.focus = 0
        menu.select(1)
        self.assertEqual((menu.level_number, menu.screen), (4, 'Other'))
        self.assertIsNone(menu.hovered_screen)
        menu.show_page('playback')
        self.assertFalse(menu.map_enabled)

    def test_destination_highlight_requires_keyboard_navigation_and_resets_on_level_change(self):
        menu = self.menu()
        self.assertFalse(menu.preview_keyboard_selection)
        menu.key('Right')
        self.assertTrue(menu.preview_keyboard_selection)
        menu.hover(*room_point(menu, 'Room 2'))
        self.assertFalse(menu.preview_keyboard_selection)
        menu.key('Left')
        self.assertTrue(menu.preview_keyboard_selection)
        menu.level_options += ((4, 'Level 4', menu.screens),)
        menu.cycle_level(1)
        self.assertFalse(menu.preview_keyboard_selection)
        menu.key('Right')
        menu.close_map()
        menu.open_map()
        self.assertFalse(menu.preview_keyboard_selection)

    def test_map_panel_and_controls_remain_inside_playfield(self):
        menu = self.menu()
        left, top, right, bottom = menu.panel_rect
        self.assertEqual(left + right, 512)
        self.assertEqual((left, top, right, bottom), (1, 0, 511, 384))
        for control in menu.controls:
            x1, y1, x2, y2 = menu.control_rect(control)
            self.assertTrue(left < x1 < x2 < right)
            self.assertTrue(top < y1 < y2 < bottom)

    def test_return_room_uses_history_for_selected_level_and_never_changes_peaceful(self):
        menu = self.menu()
        menu.focus = 1
        self.assertEqual(menu.activate(), 'return_room')
        self.assertEqual(menu.return_screen, 'Room 1')
        self.assertFalse(menu.peaceful)
        menu.return_screens.clear()
        self.assertIsNone(menu.return_screen)
        self.assertNotIn(1, menu.controls)
        self.assertEqual(menu.activate(), 'changed')
        menu.return_screens[4] = 'Room 2'
        menu.level_options += ((4, 'Level 4', menu.screens),)
        menu.focus = 6
        menu.activate()
        self.assertEqual(menu.return_screen, 'Room 2')

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

    def test_return_remembers_room_before_restart_and_uses_safe_entry(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        s = self.scene
        s.load_level(3)
        s.jump_to_screen('Room 17')
        s.restart_level()
        self.assertEqual(s.development_return_screens[3], 'Room 17')
        s.open_dev_mode()
        s.apply_dev_action(s.dev_menu.activate())
        self.assertEqual(s.dev_menu.return_screen, 'Room 17')
        s.dev_menu.focus = 1
        s.apply_dev_action(s.dev_menu.activate())
        self.assertIsNone(s.dev_menu)
        self.assertEqual(s.room_id, 16)
        self.assertTrue(s.combat.player.alive)
        self.assertFalse(s.paused)
        self.assertEqual(s.development_return_screens[3], 'Room 17')

    def test_dead_room_overrides_old_history_before_restart_and_pause_is_preserved(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        s = self.scene
        s.load_level(3)
        s.development_return_screens = {3: 'Room 17'}
        s.jump_to_screen('Room 20')
        s.combat.player.life = 0
        s.set_paused(True)
        s.open_dev_mode()
        s.apply_dev_action(s.dev_menu.activate())
        self.assertEqual(s.dev_menu.return_screen, 'Room 20')
        s.dev_menu.focus = 1
        s.apply_dev_action(s.dev_menu.activate())
        self.assertEqual(s.room_id, 19)
        self.assertTrue(s.combat.player.alive)
        self.assertTrue(s.paused)

    def test_all_supported_levels_have_real_scenery_and_selectable_rooms(self):
        from pop2.level_rendering import LevelRenderer
        from pop2.terrain import LevelMap

        for number in (1, 2, 3, 4):
            with self.subTest(level=number):
                level = self.resources.level(number)
                atlas = build_development_map(level)
                expected = {1: ('1', {'10'}), 2: ('1', {'2 (Stones)'}),
                            3: ('Room 1', {'Room 13', 'Room 30'}),
                            4: ('Room 1', {'Room 22'})}[number]
                self.assertEqual((atlas.start, atlas.exits), expected)
                self.assertEqual(atlas.image.size, MAP_SIZE)
                self.assertEqual(set(atlas.rooms), set(LevelRenderer(level).screen_entries()))
                positions = room_positions(LevelMap(level.data))
                self.assertTrue(set(atlas.positions.values()).issubset(set(positions.values())))
                self.assertGreater(len(atlas.image.getcolors(100000)), 200)
                for label, (left, top, right, bottom) in atlas.rooms.items():
                    self.assertEqual(atlas.hit((left + right) / 2, (top + bottom) / 2), label)
                    self.assertEqual(atlas.source_frames[label].size, (510, 360))

    def test_desert_map_includes_closed_door_and_settled_stones_without_changing_rng(self):
        from pop2.desert import DesertScene
        from pop2.desert_state import DesertState
        from pop2.render_opening import load_resource_file

        before = random.getstate()
        atlas = build_development_map(self.resources.level(2))
        self.assertEqual(random.getstate(), before)
        scene = DesertScene.read(load_resource_file('Desert.rsrc'), 0)
        world = DesertState(symbol=0, marked_stone=1)
        for stone in world.stones:
            stone.phase = 13
        reference = scene.draw(scene.room.background.copy(), 0, world)
        reference = Image.alpha_composite(reference, scene.room.foreground).crop((0, 0, 510, 360)).convert('RGB')
        actual = atlas.source_frames['2 (Stones)']
        self.assertEqual(actual.tobytes(), reference.tobytes())
        old = Image.alpha_composite(scene.room.background, scene.room.foreground).convert('RGB')
        for rect in ((13, 75, 86, 248), (100, 205, 440, 250)):
            self.assertIsNotNone(ImageChops.difference(actual.crop(rect), old.crop(rect)).getbbox())

    def test_landmark_badges_stay_visible_without_hover_and_at_high_resolution(self):
        from pop2.game_ui import MacintoshFont

        atlas = build_development_map(self.resources.level(3))
        atlas = replace(atlas, image=Image.new('RGB', atlas.image.size, '#202020'),
                        source_frames={}, scaled_images={})
        font = MacintoshFont(self.resources.prince['NFNT'][23331]['data'])
        menu = DevelopmentMenu(tuple(atlas.rooms), 0, False,
                               level_options=((3, 'Level 3', tuple(atlas.rooms)),),
                               map_provider=lambda _: atlas, map_open=True,
                               current_level=3, current_screen='Room 17')
        for size in ((488, 284), (1464, 852)):
            with self.subTest(size=size):
                layer = menu.map_layer(font, size)
                scale, (ox, oy) = atlas.transform(size)
                for label, color in ((atlas.start, (127, 223, 170)), ('Room 13', (255, 157, 122))):
                    left, top = atlas.rooms[label][:2]
                    point = round(left * scale + ox), round(top * scale + oy)
                    expected = Image.alpha_composite(Image.new('RGBA', (1, 1), '#202020'),
                                                     Image.new('RGBA', (1, 1), (*color, 85)))
                    self.assertEqual(layer.getpixel(point), expected.getpixel((0, 0)))
                self.assertNotIn((127, 223, 170, 255),
                                 {color for _count, color in layer.getcolors(layer.width * layer.height)})
                self.assertEqual(layer.size, size)
        for label, caption in ((atlas.start, 'Start'), ('Room 13', 'End'), ('Room 30', 'End')):
            menu.hovered_screen = label
            with patch.object(font, 'text', wraps=font.text) as draw_text:
                menu.map_layer(font)
            self.assertIn(label + ' - ' + caption, [call.args[0] for call in draw_text.call_args_list])

    def test_landmark_borders_do_not_dim_current_hover_or_keyboard_selection(self):
        from pop2.game_ui import MacintoshFont

        atlas = build_development_map(self.resources.level(3))
        font = MacintoshFont(self.resources.prince['NFNT'][23331]['data'])
        menu = DevelopmentMenu(tuple(atlas.rooms), tuple(atlas.rooms).index(atlas.start), False,
                               level_options=((3, 'Level 3', tuple(atlas.rooms)),),
                               map_provider=lambda _: atlas, map_open=True, focus=4)
        size = (1464, 852)
        scale, (ox, oy) = atlas.transform(size)
        left, top = atlas.rooms[atlas.start][:2]
        point = round(left * scale + ox), round(top * scale + oy)
        menu.preview_keyboard_selection = True
        self.assertEqual(menu.map_layer(font, size).getpixel(point), (238, 238, 238, 255))
        menu.current_level, menu.current_screen = 3, atlas.start
        self.assertEqual(menu.map_layer(font, size).getpixel(point), (99, 200, 229, 255))
        menu.hovered_screen = atlas.start
        self.assertEqual(menu.map_layer(font, size).getpixel(point), (244, 216, 115, 255))

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
        self.assertEqual(len(atlas.scaled_images), 2)

    def test_map_covers_hud_and_current_room_is_distinct_from_selection(self):
        from pop2.game_ui import MacintoshFont

        font = MacintoshFont(self.resources.prince['NFNT'][23331]['data'])
        menu = DevelopmentMapModelTests().menu()
        menu.current_level, menu.current_screen = 3, 'Room 1'
        menu.key('Right')
        self.assertEqual(menu.screen, 'Room 2')
        layer = menu.map_layer(font)
        scale, (ox, oy) = menu.map_preview.transform(layer.size)
        for label, color in (('Room 1', (99, 200, 229)), ('Room 2', (238, 238, 238))):
            x, y = menu.map_preview.rooms[label][:2]
            self.assertEqual(layer.getpixel((round(x * scale + ox), round(y * scale + oy)))[:3], color)
        result = menu.draw(Image.new('RGBA', (512, 384), '#ff00ff'), font)
        hud, footer = result.crop((1, 365, 511, 384)), result.crop((1, 373, 511, 384))
        self.assertNotIn((255, 0, 255, 255), {color for _count, color in hud.getcolors(10000)})
        self.assertEqual(footer.getcolors(), [(footer.width * footer.height, (16, 16, 16, 255))])

    def test_disk_cache_reuses_native_room_art_in_a_new_session_and_invalidates(self):
        from pop2.development_map import cached_development_map

        level = self.resources.level(3)
        with TemporaryDirectory() as directory:
            path = Path(directory)
            first = cached_development_map(level, 'art-v1', path)
            with patch('pop2.development_map.build_development_map',
                       side_effect=AssertionError('Warm cache rebuilt artwork')):
                second = cached_development_map(level, 'art-v1', path)
            self.assertEqual(first.rooms, second.rooms)
            self.assertEqual(first.positions, second.positions)
            self.assertEqual(first.enemy_rooms, second.enemy_rooms)
            self.assertEqual(first.start, second.start)
            self.assertEqual(first.exits, second.exits)
            self.assertEqual(first.detail((1830, 982)).tobytes(), second.detail((1830, 982)).tobytes())
            with patch('pop2.development_map.build_development_map', return_value=first) as build:
                cached_development_map(level, 'art-v2', path)
                build.assert_called_once_with(level)

    def test_native_and_hd_redraws_reuse_both_images_without_resizing_rooms(self):
        atlas = build_development_map(self.resources.level(3))
        sizes = ((488, 262), (1830, 982))
        images = [atlas.detail(size) for size in sizes]
        with patch.object(Image.Image, 'resize', side_effect=AssertionError('Map cache missed')):
            for _ in range(5):
                for size, image in zip(sizes, images):
                    self.assertIs(atlas.detail(size), image)
        for size in ((1020, 540), (1300, 680), (800, 430)):
            atlas.detail(size)
            self.assertEqual(len(atlas.scaled_images), 2)

    def test_hub_playback_and_back_are_tabless_and_preserve_world_and_selection(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        s = self.scene
        s.load_level(3)
        s.open_dev_mode()
        menu = s.dev_menu
        before = s.game, s.room_id, s.player_x, s.combat.world_frame
        selected = menu.screen, menu.section_index
        menu.focus = 8
        s.apply_dev_action(menu.activate())
        self.assertEqual(menu.page, 'playback')
        with patch.object(s.ui_font, 'text', wraps=s.ui_font.text) as text:
            menu.draw(s.screenshot_viewport, s.ui_font)
        labels = [call.args[0] for call in text.call_args_list]
        self.assertIn('Playback', labels)
        self.assertIn('Debug status bar', labels)
        self.assertNotIn('Display', labels)
        menu.focus = 7
        s.apply_dev_action(menu.activate())
        self.assertEqual(menu.page, 'tools')
        self.assertEqual(menu.focus, 8)
        self.assertEqual((menu.screen, menu.section_index), selected)
        self.assertEqual(before, (s.game, s.room_id, s.player_x, s.combat.world_frame))

    def test_hover_patches_existing_tk_photo_without_rendering_world_or_leaving_trails(self):
        from PIL import ImageTk
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        s = self.scene
        s.load_level(3)
        s.open_dev_mode()
        s.apply_dev_action(s.dev_menu.activate())
        menu = s.dev_menu
        before = (s.game, s.room_id, s.player_x, s.combat.world_frame,
                  s.screenshot_viewport.tobytes(), random.getstate())
        for width, height in ((1020, 768), (1920, 1080), (2560, 1440), (800, 602)):
            with self.subTest(size=(width, height)), \
                    patch.object(s.canvas, 'winfo_width', return_value=width), \
                    patch.object(s.canvas, 'winfo_height', return_value=height):
                s.present_viewport()
                photo = s.image_ref
                points = [room_point(menu, label) for label in ('Room 1', 'Room 32', 'Room 15')]
                points += [(20, 20), (200, 20), (-1, -1)]
                with patch.object(s, 'render', side_effect=AssertionError('Hover rendered world')):
                    for point in points:
                        with patch.object(s, 'dev_pointer', return_value=point):
                            s.dev_hover(SimpleNamespace())
                        self.assertIs(s.image_ref, photo)
                        actual = ImageTk.getimage(photo).convert('RGB')
                        native = menu.draw(s.screenshot_viewport, s.ui_font)
                        low = native.crop((1, 0, 511, 384)).resize(actual.size, Image.Resampling.NEAREST)
                        expected = menu.present_map(low, s.ui_font).convert('RGB')
                        self.assertEqual(actual.tobytes(), expected.tobytes())
        self.assertEqual(before, (s.game, s.room_id, s.player_x, s.combat.world_frame,
                                  s.screenshot_viewport.tobytes(), random.getstate()))
        menu.focus = 0
        menu.open_dropdown()
        s.redraw_dev_menu()
        self.assertTrue(menu.dropdown)
        menu.key('Escape')
        s.redraw_dev_menu()
        self.assertFalse(menu.dropdown)
        s.close_dev_mode()
        self.assertIsNone(s.dev_map_frame)

    def test_hub_has_no_level_labels_or_map_generation_and_map_has_one_title(self):
        from pop2.game_ui import MacintoshFont

        atlas = build_development_map(self.resources.level(3))
        font = MacintoshFont(self.resources.prince['NFNT'][23331]['data'])
        provider = Mock(return_value=atlas)
        menu = DevelopmentMenu(tuple(atlas.rooms), 0, False,
                               level_options=((3, 'Level 3', tuple(atlas.rooms)),), map_provider=provider)
        with patch.object(font, 'text', wraps=font.text) as text:
            menu.draw(Image.new('RGBA', (512, 384)), font)
        labels = [call.args[0] for call in text.call_args_list]
        self.assertIn('Open map', labels)
        self.assertIn('Playback', labels)
        self.assertNotIn('Game', labels)
        self.assertNotIn('Display', labels)
        self.assertNotIn('Level', labels)
        self.assertNotIn('Level 3', labels)
        provider.assert_not_called()
        menu.activate()
        with patch.object(font, 'text', wraps=font.text) as text:
            menu.draw(Image.new('RGBA', (512, 384)), font)
        labels = [call.args[0] for call in text.call_args_list]
        self.assertEqual(labels.count('Level 3'), 1)
        self.assertNotIn('Developer Tools', labels)
        self.assertNotIn('Playback', labels)
        self.assertNotIn('Level', labels)

    def test_toolbar_tooltip_survives_display_resolution_map_layer(self):
        from pop2.game_ui import MacintoshFont

        atlas = build_development_map(self.resources.level(3))
        font = MacintoshFont(self.resources.prince['NFNT'][23331]['data'])
        menu = DevelopmentMenu(tuple(atlas.rooms), 0, False,
                               level_options=((3, 'Level 3', tuple(atlas.rooms)),),
                               map_provider=lambda _number: atlas, map_open=True)
        rect = menu.control_rect(7)
        menu.hover(rect[0] + 6, rect[1] + 6)
        native = menu.draw(Image.new('RGBA', (512, 384)), font)
        label, (x1, y1, x2, y2) = menu.map_tooltip(font)
        self.assertEqual(label, 'Developer Tools')
        frame = native.crop((1, 0, 511, 384)).resize((1912, 1440), Image.Resampling.NEAREST)
        rect = (round((x1 - 1) * 1912 / 510), round(y1 * 1440 / 384),
                round(x2 * 1912 / 510), round((y2 + 1) * 1440 / 384))
        before = frame.crop(rect)
        menu.present_map(frame, font)
        self.assertEqual(before.tobytes(), frame.crop(rect).tobytes())

    def test_held_enter_and_escape_do_not_skip_nested_map_page(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        s = self.scene
        for paused in (False, True):
            s.set_paused(paused)
            s.open_dev_mode()
            before = s.room_id, s.player_x, s.combat.world_frame
            enter = SimpleNamespace(keysym='Return', state=0)
            escape = SimpleNamespace(keysym='Escape', state=0)
            s.dev_key_press(enter)
            s.dev_key_press(enter)
            self.assertTrue(s.dev_menu.map_enabled)
            self.assertEqual(before, (s.room_id, s.player_x, s.combat.world_frame))
            s.dev_key_release(enter)
            s.dev_key_press(escape)
            s.dev_key_press(escape)
            self.assertIsNotNone(s.dev_menu)
            self.assertFalse(s.dev_menu.map_enabled)
            self.assertTrue(s.paused)
            s.dev_key_release(escape)
            s.dev_key_press(escape)
            self.assertIsNone(s.dev_menu)
            self.assertEqual(s.paused, paused)
            s.dev_key_release(escape)

    def test_browsing_another_level_and_back_does_not_replace_live_game(self):
        from tests.test_terrain import RooftopSceneTests

        RooftopSceneTests.setUp(self)
        s = self.scene
        s.load_level(3)
        before = s.game, s.room_id, s.player_x, s.combat.world_frame
        s.open_dev_mode()
        s.apply_dev_action(s.dev_menu.activate())
        s.dev_menu.focus = 5
        s.apply_dev_action(s.dev_menu.activate())
        self.assertEqual(s.dev_menu.level_number, 2)
        self.assertEqual(before, (s.game, s.room_id, s.player_x, s.combat.world_frame))
        s.dev_menu.focus = 7
        s.apply_dev_action(s.dev_menu.activate())
        self.assertFalse(s.dev_menu.map_enabled)
        s.dev_menu.focus = 3
        s.apply_dev_action(s.dev_menu.activate())
        self.assertIsNone(s.dev_menu)
        self.assertFalse(s.paused)
        self.assertEqual(before, (s.game, s.room_id, s.player_x, s.combat.world_frame))

    def test_labels_only_render_on_hover_and_popup_survives_high_resolution(self):
        from pop2.game_ui import MacintoshFont

        atlas = build_development_map(self.resources.level(3))
        font = MacintoshFont(self.resources.prince['NFNT'][23331]['data'])
        menu = DevelopmentMenu(tuple(atlas.rooms), 0, False,
                               level_options=((3, 'Level 3', tuple(atlas.rooms)),),
                               map_provider=lambda _number: atlas, map_open=True)
        native = Image.new('RGBA', (512, 384))
        with patch.object(font, 'text', wraps=font.text) as text:
            menu.draw(native, font)
        self.assertFalse(any(call.args[0].startswith('Room ') for call in text.call_args_list))
        menu.hover(*room_point(menu, 'Room 32'))
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
            x1, _y1, x2, y2 = menu.control_rect(0)
            rect = (round((x1 - 1) * sx), round(y2 * sy),
                    round(x2 * sx), round((y2 + 20) * sy))
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
        self.assertFalse(hasattr(s, 'development_maps'))
        self.assertFalse(s.dev_menu.map_enabled)
        s.apply_dev_action(s.dev_menu.activate())
        atlas = s.dev_menu.map_preview
        self.assertIs(s.development_map(3), atlas)
        self.assertEqual(before, (s.room_id, s.player_x, s.background.tobytes(),
                                  s.sequence_state.__dict__, s.combat.world_frame, random.getstate()))
        point = room_point(s.dev_menu, 'Room 28')
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
        s.apply_dev_action(s.dev_menu.activate())
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
