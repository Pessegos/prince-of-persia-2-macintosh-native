from types import SimpleNamespace
from pathlib import Path
from tempfile import TemporaryDirectory
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import Mock, patch

from PIL import Image, ImageTk

from pop2.game_menu import GameMenu
from pop2.game_ui import PLAYFIELD_VIEWPORT, fit_viewport, viewport_point
from pop2.screenshots import ScreenshotSettings


class GameMenuModelTests(unittest.TestCase):
    def test_shortcuts_exclude_quit_and_alt_f_but_keep_alt_enter(self):
        items = GameMenu().items
        shortcuts = {item.shortcut for item in items}
        self.assertNotIn("Alt+Q", shortcuts)
        self.assertNotIn("Alt+F", shortcuts)
        self.assertNotIn("Alt+E", shortcuts)
        self.assertIn("Alt+Enter", shortcuts)
        self.assertNotIn("F2", shortcuts)
        self.assertNotIn("F3", shortcuts)
        self.assertNotIn("development", {item.action for item in items})
        self.assertNotIn("screenshots", {item.action for item in items})
        self.assertEqual({item.action for item in items if not item.enabled},
                         {"hall"})

    def test_navigation_wraps_and_activation_is_explicit(self):
        menu = GameMenu()
        self.assertEqual(menu.key("Up"), "changed")
        self.assertEqual(menu.focus, len(menu.items) - 1)
        menu.key("Tab")
        self.assertEqual(menu.focus, 0)
        menu.key("Down")
        self.assertEqual(menu.key("Return"), "confirm_new")
        self.assertEqual(menu.page, "menu")
        menu.key("Tab", backwards=True)
        self.assertEqual(menu.key("space"), "resume")

    def test_confirmation_defaults_to_cancel_and_returns_to_its_parent(self):
        menu = GameMenu(focus=1)
        menu.show_page("confirm")
        self.assertEqual(menu.focus, 0)
        self.assertEqual(menu.key("Return"), "changed")
        self.assertEqual(menu.page, "menu")
        menu = GameMenu(page="confirm", return_to_menu=False)
        self.assertEqual(menu.key("Escape"), "close")
        menu.key("Right")
        self.assertEqual(menu.key("Return"), "new_game")

    def test_disabled_items_are_visible_but_never_activate(self):
        menu = GameMenu()
        for index, item in enumerate(menu.items):
            if not item.enabled:
                menu.focus = index
                self.assertEqual(menu.key("Return"), "changed")
                rect = menu.row_rect(index)
                self.assertEqual(menu.click(rect[0] + 8, rect[1] + 8), "changed")

    def test_mouse_requires_a_control_hit_and_does_not_confirm_on_hover(self):
        menu = GameMenu(page="confirm", return_to_menu=False)
        self.assertEqual(menu.click(10, 10), "changed")
        self.assertTrue(menu.hover(300, 240))
        self.assertEqual(menu.page, "confirm")
        self.assertEqual(menu.click(300, 240), "new_game")
        self.assertEqual(menu.click(130, 240), "close")

    def test_about_returns_to_menu_or_game_as_appropriate(self):
        menu = GameMenu()
        menu.show_page("about")
        self.assertEqual(menu.key("space"), "changed")
        self.assertEqual(menu.page, "menu")
        menu = GameMenu(page="about", return_to_menu=False)
        self.assertEqual(menu.click(256, menu.ABOUT_BUTTON[1] + 8), "close")

    def test_all_command_rows_fit_inside_the_panel(self):
        menu = GameMenu()
        for index in range(len(menu.items)):
            left, top, right, bottom = menu.row_rect(index)
            self.assertTrue(menu.PANEL[0] < left < right < menu.PANEL[2])
            self.assertTrue(menu.PANEL[1] < top < bottom < menu.PANEL[3])

    def test_all_game_menu_pages_are_centered_above_the_health_strip(self):
        menu = GameMenu()
        for panel in (menu.PANEL, menu.SCREENSHOT_PANEL, menu.DIALOG, menu.ABOUT_DIALOG):
            with self.subTest(panel=panel):
                self.assertEqual(panel[0] - 1, 511 - panel[2])
                self.assertLessEqual(abs(panel[1] - (PLAYFIELD_VIEWPORT[3] - panel[3])), 1)
                self.assertLess(panel[3], PLAYFIELD_VIEWPORT[3])

    def test_centered_capture_controls_and_dropdown_share_mouse_geometry(self):
        menu = GameMenu(page="screenshots", return_to_menu=False)
        for index, (left, top, right, bottom) in enumerate(menu.CAPTURE_CONTROLS):
            self.assertEqual(menu.hit((left + right) // 2, (top + bottom) // 2), index)
            self.assertTrue(menu.SCREENSHOT_PANEL[1] < top < bottom < menu.SCREENSHOT_PANEL[3])
        left, top, right, bottom = menu.CAPTURE_CONTROLS[0]
        menu.click(left + 8, top + 8)
        self.assertTrue(menu.dropdown)
        menu.click(left + 8, bottom + 3 * menu.ROW_HEIGHT + 8)
        self.assertEqual(menu.screenshot_scale, 4)
        self.assertFalse(menu.dropdown)

    def test_centered_game_and_capture_hits_survive_window_and_fullscreen_scaling(self):
        for page in ("menu", "screenshots"):
            menu = GameMenu(page=page)
            rects = (menu.CAPTURE_CONTROLS if page == "screenshots" else
                     [menu.row_rect(i) for i in range(len(menu.items))])
            for dimensions in ((512, 384), (800, 900), (1920, 1080), (3440, 1440)):
                size, origin = fit_viewport(*dimensions)
                for index, (left, top, right, bottom) in enumerate(rects):
                    with self.subTest(page=page, dimensions=dimensions, control=index):
                        x, y = (left + right) / 2, (top + bottom) / 2
                        point = viewport_point(origin[0] + (x - 1) * size[0] / 510,
                                               origin[1] + y * size[1] / 384, *dimensions)
                        self.assertEqual(menu.hit(*point), index)


class GameMenuSceneTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.setUp(self)

    def tick(self, count=1):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.tick(self, count)

    @staticmethod
    def event(key, state=0):
        return SimpleNamespace(keysym=key, state=state)

    def press(self, key, state=0):
        result = self.scene.dev_key_press(self.event(key, state))
        self.scene.dev_key_release(self.event(key, state))
        return result

    def test_f1_is_a_paused_in_game_overlay_without_another_window(self):
        scene = self.scene
        scene.jump_to_screen("5")
        before = scene.native_viewport.copy()
        children = scene.root.winfo_children()
        position = (scene.player_x, scene.action, scene.combat.world_frame)
        self.assertEqual(self.press("F1"), "break")
        self.assertEqual(scene.root.winfo_children(), children)
        self.assertTrue(scene.paused)
        self.assertEqual(scene.game_menu.page, "menu")
        self.assertTrue(all(scene.native_viewport.getpixel((30, 20))[i] < before.getpixel((30, 20))[i]
                            for i in range(3)))
        self.tick(12)
        self.assertEqual(position, (scene.player_x, scene.action, scene.combat.world_frame))
        self.press("F1")
        self.assertIsNone(scene.game_menu)
        self.assertFalse(scene.paused)
        self.assertEqual(scene.native_viewport.tobytes(), before.tobytes())

    def test_opening_f1_menu_renders_only_once_while_it_pauses(self):
        scene = self.scene
        with patch.object(scene, "render", wraps=scene.render) as render:
            self.assertEqual(self.press("F1"), "break")
        self.assertEqual(render.call_count, 1)

    def test_f2_capture_works_during_intro_with_developer_tools_unavailable(self):
        scene = self.scene
        scene.start_intro()
        scene.render()
        intro = scene.intro
        with TemporaryDirectory() as directory:
            scene.screenshot_settings = ScreenshotSettings(Path(directory), 1)
            with patch.object(scene, "development_available", return_value=False):
                self.press("F2")
                self.assertEqual(scene.game_menu.page, "screenshots")
                expected = scene.screenshot_viewport.crop((1, 0, 511, 384)).convert("RGB")
                self.press("F8")
                files = list(Path(directory).glob("*.png"))
                self.assertEqual(len(files), 1)
                with Image.open(files[0]) as image:
                    self.assertEqual(image.tobytes(), expected.tobytes())
                self.assertTrue(scene.paused)
                self.assertIs(scene.intro, intro)
                self.assertIsNone(scene.dev_menu)
                self.press("F2")
                self.assertIsNone(scene.game_menu)
                self.assertFalse(scene.paused)

    def test_f2_hold_and_escape_close_restore_running_and_paused_states(self):
        scene = self.scene
        for paused in (False, True):
            with self.subTest(paused=paused):
                scene.set_paused(paused)
                event = self.event("F2")
                scene.dev_key_press(event)
                self.assertEqual(scene.game_menu.page, "screenshots")
                scene.dev_key_press(event)
                self.assertIsNotNone(scene.game_menu)
                self.assertTrue(scene.paused)
                scene.dev_key_release(event)
                self.press("Escape")
                self.assertIsNone(scene.game_menu)
                self.assertEqual(scene.paused, paused)

    def test_shift_f8_preserves_visible_pause_menus_and_cutscene_overlay(self):
        scene = self.scene
        with TemporaryDirectory() as directory:
            scene.screenshot_settings = ScreenshotSettings(Path(directory), 1)
            for overlay in ('pause', 'menu', 'saves', 'screenshots', 'tools', 'playback', 'intro'):
                with self.subTest(overlay=overlay):
                    if scene.game_menu is not None:
                        scene.close_game_menu(resume=True)
                    if scene.dev_menu is not None:
                        scene.close_dev_mode()
                    scene.clear_screenshot_toast()
                    scene.set_paused(False)
                    if overlay == 'pause':
                        scene.set_paused(True)
                    elif overlay in ('menu', 'saves', 'screenshots'):
                        if overlay == 'saves':
                            scene.apply_game_action('save')
                        else:
                            scene.open_game_menu(overlay)
                    elif overlay in ('tools', 'playback'):
                        scene.open_dev_mode()
                        scene.dev_menu.show_page(overlay)
                    else:
                        scene.start_intro()
                        scene.set_paused(True)
                    scene.render()
                    expected = scene.native_viewport.crop((1, 0, 511, 384)).convert('RGB')
                    clean = scene.screenshot_viewport.crop((1, 0, 511, 384)).convert('RGB')
                    self.assertNotEqual(expected.tobytes(), clean.tobytes())
                    menus = scene.game_menu, scene.dev_menu
                    position = scene.player_x, scene.action, scene.combat.world_frame
                    before = set(Path(directory).glob('*.png'))
                    self.assertEqual(self.press('F8', 0x1), 'break')
                    path, = set(Path(directory).glob('*.png')) - before
                    with Image.open(path) as image:
                        self.assertEqual(image.tobytes(), expected.tobytes())
                    self.assertTrue(scene.paused)
                    self.assertIs(scene.game_menu, menus[0])
                    self.assertIs(scene.dev_menu, menus[1])
                    self.assertEqual(position, (scene.player_x, scene.action, scene.combat.world_frame))
                    before.add(path)
                    self.press('F8')
                    path, = set(Path(directory).glob('*.png')) - before
                    with Image.open(path) as image:
                        self.assertEqual(image.tobytes(), clean.tobytes())

    def test_save_browser_presentation_keeps_source_detail_at_fitted_window_resolution(self):
        scene = self.scene
        scene.apply_game_action('save')
        browser = scene.game_menu.save_browser
        preview = browser.current.preview
        self.assertEqual(preview.size, (510, 365))
        for width, height in ((1020, 768), (1920, 1080), (3440, 1440), (800, 900)):
            with self.subTest(window=(width, height)), \
                    patch.object(scene.canvas, 'winfo_width', return_value=width), \
                    patch.object(scene.canvas, 'winfo_height', return_value=height), \
                    patch('pop2.window_controls.ImageTk.PhotoImage', wraps=ImageTk.PhotoImage) as photo:
                scene.present_viewport()
                frame = photo.call_args.args[0]
                size, _origin = fit_viewport(width, height)
                self.assertEqual(frame.size, size)
                sx, sy = size[0] / 510, size[1] / 384
                left, top, right, bottom = browser.PREVIEW
                rect = (round(left * sx), round((top + 1) * sy),
                        round((right - 2) * sx), round((bottom - 1) * sy))
                expected = preview.resize((rect[2] - rect[0], rect[3] - rect[1]), Image.Resampling.NEAREST)
                self.assertEqual(frame.crop(rect).convert('RGB').tobytes(), expected.tobytes())
                old = scene.native_viewport.crop((1, 0, 511, 384)).resize(size, Image.Resampling.NEAREST)
                self.assertNotEqual(frame.crop(rect).tobytes(), old.crop(rect).tobytes())
                panel = browser.PANEL
                self.assertEqual(frame.getpixel((round((panel[0] - 1) * sx), round(panel[1] * sy))),
                                 (133, 133, 133, 255))

    def test_shift_f8_saves_refined_browser_and_confirmations_at_selected_scale(self):
        scene = self.scene
        scene.apply_game_action('save')
        browser = scene.game_menu.save_browser
        with TemporaryDirectory() as directory:
            for confirmation in (None, 'save', 'load', 'delete'):
                for scale in (1, 2, 3, 4):
                    with self.subTest(confirmation=confirmation, scale=scale):
                        scene.clear_screenshot_toast()
                        browser.confirmation = confirmation
                        scene.screenshot_settings = ScreenshotSettings(Path(directory), scale)
                        scene.render()
                        source = scene.screenshot_viewport.resize((512 * scale, 384 * scale), Image.Resampling.NEAREST)
                        expected = browser.draw(source, scene.ui_font).crop((scale, 0, 511 * scale, 384 * scale)).convert('RGB')
                        path = scene.capture_screenshot(include_ui=True)
                        with Image.open(path) as image:
                            self.assertEqual(image.size, (510 * scale, 384 * scale))
                            self.assertEqual(image.tobytes(), expected.tobytes())
                        self.assertEqual(browser.confirmation, confirmation)
                        self.assertTrue(scene.paused)

    def test_alt_n_never_restarts_until_explicit_confirmation(self):
        scene = self.scene
        scene.jump_to_screen("9")
        checkpoint = scene.checkpoint
        before = (scene.room_id, scene.player_x, scene.action)
        self.press("n", 0x20000)
        self.assertEqual(scene.game_menu.page, "confirm")
        self.assertEqual(scene.game_menu.focus, 0)
        self.press("Return")
        self.assertIsNone(scene.game_menu)
        self.assertEqual(before, (scene.room_id, scene.player_x, scene.action))
        self.assertIs(scene.checkpoint, checkpoint)
        self.assertFalse(scene.paused)
        self.press("N", 0x20000)
        self.press("Right")
        self.press("Return")
        self.assertIsNone(scene.game_menu)
        self.assertIsNone(scene.checkpoint)
        self.assertEqual(scene.room_id, scene.level_map.start_room)
        self.assertTrue(scene.opening.active)
        self.assertFalse(scene.paused)

    def test_holding_activation_cannot_confirm_a_new_page(self):
        scene = self.scene
        self.press("F1")
        scene.game_menu.focus = 1
        scene.dev_key_press(self.event("Return"))
        self.assertEqual(scene.game_menu.page, "confirm")
        self.press("Right")
        with patch.object(scene, "restart_opening") as restart:
            scene.dev_key_press(self.event("Return"))
            restart.assert_not_called()
        scene.dev_key_release(self.event("Return"))
        self.press("Return")
        self.assertIsNone(scene.game_menu)

    def test_confirmation_cannot_be_bypassed_by_function_or_command_keys(self):
        scene = self.scene
        self.press("n", 0x20000)
        with patch.object(scene, "restart_opening") as new, \
                patch.object(scene, "restart_level") as restart:
            for key, state in (("F1", 0), ("F2", 0), ("F3", 0), ("F5", 0), ("n", 0x20000),
                               ("r", 0x20000), ("v", 0x20000), ("t", 0x20000)):
                self.assertEqual(self.press(key, state), "break")
                self.assertEqual(scene.game_menu.page, "confirm")
                self.assertIsNone(scene.dev_menu)
            new.assert_not_called()
            restart.assert_not_called()

    def test_escape_from_confirmation_returns_to_menu_and_does_not_toggle_pause(self):
        scene = self.scene
        self.press("F1")
        scene.game_menu.focus = 1
        self.press("Return")
        scene.dev_key_press(self.event("Escape"))
        self.assertEqual(scene.game_menu.page, "menu")
        scene.dev_key_press(self.event("Escape"))
        self.assertIsNotNone(scene.game_menu)
        scene.dev_key_release(self.event("Escape"))
        self.press("Escape")
        self.assertIsNone(scene.game_menu)
        self.assertFalse(scene.paused)

    def test_cancel_restores_pause_but_resume_explicitly_resumes(self):
        scene = self.scene
        scene.set_paused(True)
        self.press("F1")
        self.press("Escape")
        self.assertTrue(scene.paused)
        self.press("F1")
        self.press("Return")
        self.assertFalse(scene.paused)

    def test_alt_r_uses_the_existing_checkpoint_without_a_death_gate(self):
        scene = self.scene
        scene.jump_to_screen("9")
        snapshot = scene.checkpoint
        scene.combat.player.life = 1
        self.assertFalse(scene.death.can_restart)
        self.press("r", 0x20000)
        point = snapshot.checkpoint
        self.assertEqual((scene.room_id, scene.terrain_motion.row, scene.player_x),
                         (point.room, point.row, point.x))
        self.assertIs(scene.checkpoint, snapshot)
        self.assertEqual(scene.combat.player.life, scene.combat.player.max_life)
        self.assertFalse(scene.paused)

    def test_restart_without_checkpoint_preserves_capacity_but_new_game_resets_it(self):
        scene = self.scene
        scene.jump_to_screen("5")
        scene.combat.player.max_life = 5
        self.press("r", 0x20000)
        self.assertEqual((scene.combat.player.max_life, scene.combat.player.life), (5, 5))
        self.press("n", 0x20000)
        self.press("Right")
        self.press("Return")
        self.assertEqual((scene.combat.player.max_life, scene.combat.player.life), (3, 3))

    def test_menu_restart_resumes_and_clears_menu_and_queued_gameplay(self):
        scene = self.scene
        scene.jump_to_screen("5")
        self.press("F1")
        scene.game_menu.focus = 2
        scene.dev_key_press(self.event("Return"))
        self.assertIsNone(scene.game_menu)
        self.assertFalse(scene.paused)
        self.assertTrue(scene.opening.active)
        self.assertIsNone(scene.pending_action)
        self.assertEqual(scene.dev_key_press(self.event("Return")), "break")

    def test_sound_shortcuts_work_when_paused_and_do_not_repeat_or_resume(self):
        scene = self.scene
        scene.audio = Mock()
        scene.set_paused(True)
        for key, field in (("t", "sound"), ("m", "music")):
            scene.dev_key_press(self.event(key, 0x20000))
            self.assertFalse(getattr(scene, field + "_enabled"))
            scene.dev_key_press(self.event(key, 0x20000))
            getattr(scene.audio, "set_" + field + "_enabled").assert_called_once_with(False)
            self.assertTrue(scene.paused)
            scene.dev_key_release(self.event(key))
            self.press(key, 0x20000)
            self.assertTrue(getattr(scene, field + "_enabled"))
            self.assertTrue(scene.paused)

    def test_audio_toggle_does_not_consume_an_existing_run_key_release(self):
        scene = self.scene
        scene.jump_to_screen("5")
        scene.dev_key_press(self.event("Left"))
        scene.horizontal_key(None, -1, True)
        self.press("m", 0x20000)
        self.assertNotIn("Left", scene.pause_resume_keys)
        self.assertIsNone(scene.dev_key_release(self.event("Left")))
        scene.horizontal_key(None, -1, False)
        self.assertEqual(scene.horizontal_input, 0)

    def test_releasing_shift_during_a_shortcut_cannot_repeat_or_stick_the_command(self):
        scene = self.scene
        scene.dev_key_press(self.event("T", 0x20001))
        self.assertFalse(scene.sound_enabled)
        scene.dev_key_press(self.event("t", 0x20000))
        self.assertFalse(scene.sound_enabled)
        scene.dev_key_release(self.event("t"))
        self.assertNotIn("T", scene.window_keys_down)
        self.assertNotIn("T", scene.pause_resume_keys)
        self.press("t", 0x20000)
        self.assertTrue(scene.sound_enabled)

    def test_menu_preferences_survive_new_game_and_restart(self):
        scene = self.scene
        scene.jump_to_screen("9")
        scene.peaceful = True
        self.press("m", 0x20000)
        self.press("t", 0x20000)
        self.press("r", 0x20000)
        self.assertFalse(scene.music_enabled)
        self.assertFalse(scene.sound_enabled)
        self.assertTrue(scene.peaceful)
        self.press("n", 0x20000)
        self.press("Right")
        self.press("Return")
        self.assertFalse(scene.music_enabled)
        self.assertFalse(scene.sound_enabled)
        self.assertTrue(scene.peaceful)

    def test_disabled_shortcuts_show_the_unavailable_entry_without_mutating_progress(self):
        scene = self.scene
        scene.jump_to_screen("9")
        before = (scene.room_id, scene.player_x, scene.checkpoint)
        for key, action in (("h", "hall"),):
            self.press(key, 0x20000)
            item = scene.game_menu.items[scene.game_menu.focus]
            self.assertEqual(item.action, action)
            self.assertFalse(item.enabled)
            self.press("Return")
            self.assertEqual(before, (scene.room_id, scene.player_x, scene.checkpoint))
            self.press("Escape")

    def test_removed_end_game_shortcut_does_not_reset_or_open_a_menu(self):
        scene = self.scene
        scene.jump_to_screen("9")
        before = scene.room_id, scene.player_x, scene.checkpoint
        for paused in (False, True):
            scene.set_paused(paused)
            self.press("e", 0x20000)
            self.assertIsNone(scene.game_menu)
            self.assertEqual(scene.paused, paused)
            self.assertEqual((scene.room_id, scene.player_x, scene.checkpoint), before)

    def test_f1_f2_and_f3_switch_menus_without_losing_the_original_pause_state(self):
        scene = self.scene
        for paused in (True, False):
            scene.set_paused(paused)
            scene.open_dev_mode()
            self.press("F1")
            self.assertIsNone(scene.dev_menu)
            self.assertIsNotNone(scene.game_menu)
            self.assertTrue(scene.paused)
            self.press("F2")
            self.assertEqual(scene.game_menu.page, "screenshots")
            self.assertFalse(scene.game_menu.return_to_menu)
            self.press("F1")
            self.assertEqual(scene.game_menu.page, "menu")
            self.assertEqual(scene.dev_key_press(self.event("F3")), "break")
            scene.dev_key_release(self.event("F3"))
            self.assertIsNone(scene.game_menu)
            self.assertIsNotNone(scene.dev_menu)
            scene.close_dev_mode()
            self.assertEqual(scene.paused, paused)

    def test_about_from_shortcut_and_menu_return_to_the_correct_parent(self):
        scene = self.scene
        self.press("v", 0x20000)
        self.assertEqual(scene.game_menu.page, "about")
        self.press("Return")
        self.assertIsNone(scene.game_menu)
        self.press("F1")
        scene.game_menu.focus = next(i for i, item in enumerate(scene.game_menu.items)
                                     if item.action == "about")
        self.press("Return")
        self.assertEqual(scene.game_menu.page, "about")
        self.press("Escape")
        self.assertEqual(scene.game_menu.page, "menu")

    def test_excluded_shortcuts_and_altgr_do_not_trigger_commands(self):
        scene = self.scene
        with patch.object(scene, "restart_opening") as restart:
            for key, state in (("q", 0x20000), ("f", 0x20000), ("n", 0x20004)):
                self.press(key, state)
                self.assertIsNone(scene.game_menu)
            restart.assert_not_called()
        self.assertFalse(scene.fullscreen)

    def test_alt_enter_is_available_in_confirmation_without_confirming(self):
        scene = self.scene
        self.press("n", 0x20000)
        event = self.event("Return", 0x20000)
        self.assertIsNone(scene.dev_key_press(event))
        self.assertEqual(scene.dev_key_press(event), "break")
        with patch.object(scene.root, "attributes"), patch.object(scene.root, "state"):
            scene.toggle_fullscreen()
        self.assertTrue(scene.fullscreen)
        self.assertEqual(scene.canvas.cget("cursor"), "")
        self.assertEqual(scene.game_menu.page, "confirm")
        scene.dev_key_release(event)
        self.press("Escape")
        self.assertEqual(scene.canvas.cget("cursor"), "none")

    def test_focus_loss_while_in_menu_keeps_pause_after_cancel(self):
        scene = self.scene
        self.press("F1")
        with patch.object(scene.root, "focus_get", return_value=None):
            scene.pause_if_unfocused()
        self.press("Escape")
        self.assertTrue(scene.paused)

    def test_mouse_coordinates_follow_fullscreen_letterboxing_and_do_not_leak_input(self):
        scene = self.scene
        self.press("F1")
        for key in ("Left", "Up", "Control_L", "Shift_L"):
            scene.dev_key_press(self.event(key))
        size, origin = fit_viewport(3440, 1440)
        row_y = scene.game_menu.row_rect(0)[1] + 8
        with patch.object(scene.canvas, "winfo_width", return_value=3440), \
                patch.object(scene.canvas, "winfo_height", return_value=1440):
            scene.dev_click(SimpleNamespace(x=20, y=50, num=1))
            self.assertIsNotNone(scene.game_menu)
            scene.dev_click(SimpleNamespace(x=origin[0] + 199 * size[0] / 510,
                                             y=origin[1] + row_y * size[1] / 384, num=3))
            self.assertIsNotNone(scene.game_menu)
            scene.dev_click(SimpleNamespace(x=origin[0] + 199 * size[0] / 510,
                                             y=origin[1] + row_y * size[1] / 384, num=1))
        self.assertIsNone(scene.game_menu)
        for key in ("Left", "Up", "Control_L", "Shift_L"):
            self.assertEqual(scene.dev_key_press(self.event(key)), "break")
            scene.dev_key_release(self.event(key))
        self.assertEqual(scene.horizontal_input, 0)
        self.assertFalse(scene.up_held)
        self.assertFalse(scene.ctrl_held)

    def test_all_pages_fit_the_native_canvas_and_leave_source_untouched(self):
        viewport = Image.new("RGBA", (512, 384), (80, 80, 80, 255))
        for page in ("menu", "confirm", "about"):
            menu = GameMenu(page=page)
            rendered = menu.draw(viewport, self.scene.ui_font)
            self.assertEqual(rendered.size, viewport.size)
            self.assertEqual(viewport.getpixel((256, 192)), (80, 80, 80, 255))
            for rect in ([menu.row_rect(i) for i in range(len(menu.items))]
                         if page == "menu" else menu.BUTTONS):
                self.assertTrue(0 <= rect[0] < rect[2] <= 512)
                self.assertTrue(0 <= rect[1] < rect[3] <= 384)

    def test_centered_panels_and_controls_are_drawn_at_their_mouse_coordinates(self):
        from pop2.game_ui import DevelopmentMenu
        from pop2.render_opening import ROOM_HEIGHT

        self.assertEqual(PLAYFIELD_VIEWPORT[3], ROOM_HEIGHT)
        viewport = Image.new("RGBA", (512, 384), (80, 80, 80, 255))
        menus = [(GameMenu(page=page), panel) for page, panel in (
            ("menu", GameMenu.PANEL), ("screenshots", GameMenu.SCREENSHOT_PANEL),
            ("confirm", GameMenu.DIALOG), ("about", GameMenu.ABOUT_DIALOG))]
        for levels in ((), ((1, "Level 1", ("1", "2")),)):
            for page in ('tools', 'playback'):
                menu = DevelopmentMenu(("1", "2"), 0, False, page=page,
                                       sections=("First", "Second"), level_options=levels)
                menus.append((menu, menu.panel_rect))
        for menu, (left, top, right, bottom) in menus:
            with self.subTest(menu=type(menu).__name__, panel=(left, top, right, bottom)):
                image = menu.draw(viewport, self.scene.ui_font)
                for point in ((left, top), (right, top), (left, bottom), (right, bottom)):
                    self.assertEqual(image.getpixel(point), (133, 133, 133, 255))
                self.assertEqual(left + right, 512)
                self.assertLessEqual(abs(top - (ROOM_HEIGHT - bottom)), 1)
                if isinstance(menu, DevelopmentMenu):
                    rects = [menu.control_rect(i) for i in menu.controls]
                else:
                    rects = (menu.CAPTURE_CONTROLS if menu.page == "screenshots" else
                             menu.BUTTONS if menu.page == "confirm" else
                             (menu.ABOUT_BUTTON,) if menu.page == "about" else
                             [menu.row_rect(i) for i in range(len(menu.items))])
                for index, rect in enumerate(rects):
                    self.assertEqual(menu.hit((rect[0] + rect[2]) // 2, (rect[1] + rect[3]) // 2),
                                     menu.controls[index] if isinstance(menu, DevelopmentMenu) else index)
                    self.assertNotEqual(image.getpixel((rect[0], rect[1])), (24, 24, 24, 255))

    def test_shortcuts_avoid_the_original_fonts_trademark_glyph(self):
        font = self.scene.ui_font
        with patch.object(font, "text", wraps=font.text) as text:
            GameMenu().draw(self.scene.native_viewport, font)
        labels = [call.args[0] for call in text.call_args_list]
        self.assertIn("Alt-N", labels)
        self.assertIn("Alt-Enter", labels)
        self.assertFalse(any("+" in label for label in labels))

    def test_about_credit_fits_below_the_button_inside_the_dialog(self):
        font = self.scene.ui_font
        menu = GameMenu(page="about")
        with patch.object(font, "text", wraps=font.text) as text:
            image = menu.draw(self.scene.native_viewport, font)
        self.assertIn("by Pessegos", [call.args[0] for call in text.call_args_list])
        credit = font.text("by Pessegos", "#999999")
        ink = credit.getbbox()
        self.assertGreaterEqual(420 - credit.width + ink[0], menu.ABOUT_DIALOG[0] + 1)
        credit_y = menu.ABOUT_DIALOG[1] + 162
        self.assertLess(credit_y + ink[3] - ink[1], menu.ABOUT_DIALOG[3])
        footer = image.crop((420 - credit.width, credit_y, 420, credit_y + 16))
        self.assertIn((153, 153, 153, 255),
                      {color for _count, color in footer.getcolors(footer.width * footer.height)})

    def test_real_tk_bindings_route_alt_n_escape_f1_and_alt_enter(self):
        result = subprocess.run([sys.executable, "-c", textwrap.dedent("""
            from unittest.mock import patch
            import sys
            from tests.test_game_menu import GameMenuSceneTests

            fixture = GameMenuSceneTests()
            fixture.setUp()
            scene = fixture.scene
            root = scene.root
            try:
                root.deiconify()
                root.update()
                root.focus_force()
                root.update()
                scene.set_paused(False)

                def key(symbol, state=0):
                    root.event_generate('<KeyPress>', keysym=symbol, state=state)
                    root.event_generate('<KeyRelease>', keysym=symbol, state=state)

                if sys.platform == 'win32':
                    scene.start_intro()
                    intro = scene.intro
                    key('s', 8)
                    assert scene.game_menu is None and scene.intro is intro
                    key('space', 8)
                    assert scene.intro is None and scene.opening.active
                    scene.jump_to_screen('5')
                    scene.set_paused(True)
                    root.event_generate('<KeyPress>', keysym='Right', state=8)
                    assert not scene.paused and scene.horizontal_input == 1
                    root.event_generate('<KeyRelease>', keysym='Right', state=8)
                    assert scene.horizontal_input == 0
                    key('F1', 8)
                    assert scene.game_menu.page == 'menu'
                    key('Return', 8)
                    assert scene.game_menu is None and not scene.paused
                    key('F2', 8)
                    assert scene.game_menu.page == 'screenshots'
                    key('Return', 8)
                    assert scene.game_menu.dropdown and not scene.fullscreen
                    key('Escape', 8)
                    key('F2', 8)
                    with patch.object(scene, 'capture_screenshot') as capture:
                        key('F8', 8)
                        capture.assert_called_once_with()
                key('n', 0x20000)
                assert scene.game_menu.page == 'confirm'
                key('Escape')
                assert scene.game_menu is None and not scene.paused
                key('F1')
                assert scene.game_menu.page == 'menu'
                with patch.object(root, 'attributes'), patch.object(root, 'state'):
                    key('Return', 0x20000)
                assert scene.fullscreen and scene.game_menu.page == 'menu'
                key('Escape')
                assert scene.game_menu is None and not scene.paused
                root.update_idletasks()
            finally:
                fixture.doCleanups()
        """)], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
