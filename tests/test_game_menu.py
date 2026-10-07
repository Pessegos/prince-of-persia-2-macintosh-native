from types import SimpleNamespace
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from pop2.game_menu import GameMenu
from pop2.game_ui import fit_viewport
from tests import test_terrain


class GameMenuModelTests(unittest.TestCase):
    def test_shortcuts_exclude_quit_and_alt_f_but_keep_alt_enter(self):
        items = GameMenu().items
        shortcuts = {item.shortcut for item in items}
        self.assertNotIn("Alt+Q", shortcuts)
        self.assertNotIn("Alt+F", shortcuts)
        self.assertIn("Alt+Enter", shortcuts)
        self.assertEqual({item.action for item in items if not item.enabled},
                         {"save", "open", "end", "hall"})

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
        menu = GameMenu(development=False)
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
        self.assertEqual(menu.click(256, 240), "close")


class GameMenuSceneTests(unittest.TestCase):
    setUp = test_terrain.RooftopSceneTests.setUp
    tick = test_terrain.RooftopSceneTests.tick

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
        self.press("N", 0x8)
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
        self.press("n", 0x8)
        with patch.object(scene, "restart_opening") as new, \
                patch.object(scene, "restart_level") as restart:
            for key, state in (("F1", 0), ("F2", 0), ("F5", 0), ("n", 8),
                               ("r", 8), ("v", 8), ("t", 8)):
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
        self.press("r", 8)
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
        self.press("r", 8)
        self.assertEqual((scene.combat.player.max_life, scene.combat.player.life), (5, 5))
        self.press("n", 8)
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
            self.press(key, 8)
            self.assertTrue(getattr(scene, field + "_enabled"))
            self.assertTrue(scene.paused)

    def test_audio_toggle_does_not_consume_an_existing_run_key_release(self):
        scene = self.scene
        scene.jump_to_screen("5")
        scene.dev_key_press(self.event("Left"))
        scene.horizontal_key(None, -1, True)
        self.press("m", 8)
        self.assertNotIn("Left", scene.pause_resume_keys)
        self.assertIsNone(scene.dev_key_release(self.event("Left")))
        scene.horizontal_key(None, -1, False)
        self.assertEqual(scene.horizontal_input, 0)

    def test_releasing_shift_during_a_shortcut_cannot_repeat_or_stick_the_command(self):
        scene = self.scene
        scene.dev_key_press(self.event("T", 9))
        self.assertFalse(scene.sound_enabled)
        scene.dev_key_press(self.event("t", 8))
        self.assertFalse(scene.sound_enabled)
        scene.dev_key_release(self.event("t"))
        self.assertNotIn("T", scene.window_keys_down)
        self.assertNotIn("T", scene.pause_resume_keys)
        self.press("t", 8)
        self.assertTrue(scene.sound_enabled)

    def test_menu_preferences_survive_new_game_and_restart(self):
        scene = self.scene
        scene.jump_to_screen("9")
        scene.peaceful = True
        self.press("m", 8)
        self.press("t", 8)
        self.press("r", 8)
        self.assertFalse(scene.music_enabled)
        self.assertFalse(scene.sound_enabled)
        self.assertTrue(scene.peaceful)
        self.press("n", 8)
        self.press("Right")
        self.press("Return")
        self.assertFalse(scene.music_enabled)
        self.assertFalse(scene.sound_enabled)
        self.assertTrue(scene.peaceful)

    def test_disabled_shortcuts_show_the_unavailable_entry_without_mutating_progress(self):
        scene = self.scene
        scene.jump_to_screen("9")
        before = (scene.room_id, scene.player_x, scene.checkpoint)
        for key, action in (("s", "save"), ("o", "open"), ("e", "end"), ("h", "hall")):
            self.press(key, 8)
            item = scene.game_menu.items[scene.game_menu.focus]
            self.assertEqual(item.action, action)
            self.assertFalse(item.enabled)
            self.press("Return")
            self.assertEqual(before, (scene.room_id, scene.player_x, scene.checkpoint))
            self.press("Escape")

    def test_f1_and_f2_switch_menus_without_losing_the_original_pause_state(self):
        scene = self.scene
        for paused in (True, False):
            scene.set_paused(paused)
            scene.open_dev_mode()
            self.press("F1")
            self.assertIsNone(scene.dev_menu)
            self.assertIsNotNone(scene.game_menu)
            self.assertTrue(scene.paused)
            self.assertIsNone(scene.dev_key_press(self.event("F2")))
            scene.open_dev_mode(self.event("F2"))
            scene.dev_key_release(self.event("F2"))
            self.assertIsNone(scene.game_menu)
            self.assertIsNotNone(scene.dev_menu)
            scene.close_dev_mode()
            self.assertEqual(scene.paused, paused)

    def test_about_from_shortcut_and_menu_return_to_the_correct_parent(self):
        scene = self.scene
        self.press("v", 8)
        self.assertEqual(scene.game_menu.page, "about")
        self.press("Return")
        self.assertIsNone(scene.game_menu)
        self.press("F1")
        scene.game_menu.focus = 9
        self.press("Return")
        self.assertEqual(scene.game_menu.page, "about")
        self.press("Escape")
        self.assertEqual(scene.game_menu.page, "menu")

    def test_excluded_shortcuts_and_altgr_do_not_trigger_commands(self):
        scene = self.scene
        with patch.object(scene, "restart_opening") as restart:
            for key, state in (("q", 8), ("f", 8), ("n", 0x20004)):
                self.press(key, state)
                self.assertIsNone(scene.game_menu)
            restart.assert_not_called()
        self.assertFalse(scene.fullscreen)

    def test_alt_enter_is_available_in_confirmation_without_confirming(self):
        scene = self.scene
        self.press("n", 8)
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
        with patch.object(scene.canvas, "winfo_width", return_value=3440), \
                patch.object(scene.canvas, "winfo_height", return_value=1440):
            scene.dev_click(SimpleNamespace(x=20, y=50, num=1))
            self.assertIsNotNone(scene.game_menu)
            scene.dev_click(SimpleNamespace(x=origin[0] + 200 * size[0] / 512,
                                             y=origin[1] + 72 * size[1] / 384, num=3))
            self.assertIsNotNone(scene.game_menu)
            scene.dev_click(SimpleNamespace(x=origin[0] + 200 * size[0] / 512,
                                             y=origin[1] + 72 * size[1] / 384, num=1))
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

    def test_shortcuts_avoid_the_original_fonts_trademark_glyph(self):
        font = self.scene.ui_font
        with patch.object(font, "text", wraps=font.text) as text:
            GameMenu().draw(self.scene.native_viewport, font)
        labels = [call.args[0] for call in text.call_args_list]
        self.assertIn("Alt-N", labels)
        self.assertIn("Alt-Enter", labels)
        self.assertFalse(any("+" in label for label in labels))

    def test_real_tk_bindings_route_alt_n_escape_f1_and_alt_enter(self):
        result = subprocess.run([sys.executable, "-c", textwrap.dedent("""
            from unittest.mock import patch
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
