import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from pop2.game_ui import DevelopmentMenu, fit_viewport, viewport_point
from pop2.playback_navigation import PlaybackGroup
import tests.test_terrain as test_terrain


SCREENS = ("1", "2", "3", "4", "5", "6", "7", "Secret (right)")


class MenuModelTests(unittest.TestCase):
    def setUp(self):
        self.menu = DevelopmentMenu(SCREENS, 4, False)

    def test_screen_keys_wrap_and_popup_commits_only_on_selection(self):
        menu = self.menu
        menu.key("Right")
        self.assertEqual(menu.screen, "6")
        menu.key("Return")
        menu.key("Down")
        self.assertEqual(menu.screen, "6")
        self.assertEqual(menu.option_index, 6)
        menu.key("Return")
        self.assertEqual(menu.screen, "7")
        menu.key("Right")
        menu.key("Right")
        self.assertEqual(menu.screen, "1")
        menu.key("Left")
        self.assertEqual(menu.screen, "Secret (right)")

    def test_escape_cancels_popup_before_closing_menu(self):
        menu = self.menu
        menu.key("Return")
        menu.key("Down")
        self.assertEqual(menu.key("Escape"), "changed")
        self.assertEqual(menu.screen, "5")
        self.assertFalse(menu.dropdown)
        self.assertEqual(menu.key("Escape"), "resume")

    def test_focus_and_checkbox_are_keyboard_accessible(self):
        menu = self.menu
        menu.key("Tab")
        self.assertEqual(menu.key("space"), "peaceful")
        self.assertTrue(menu.peaceful)
        menu.key("Down")
        self.assertEqual(menu.key("Return"), "go")
        menu.key("Tab")
        self.assertEqual(menu.key("space"), "resume")
        menu.key("Tab")
        self.assertEqual(menu.focus, -1)
        menu.key("Tab")
        self.assertEqual(menu.focus, 0)
        menu.key("Tab", backwards=True)
        self.assertEqual(menu.focus, -1)
        menu.key("Tab", backwards=True)
        self.assertEqual(menu.focus, 3)

    def test_mouse_popup_does_not_activate_covered_controls(self):
        menu = self.menu
        menu.click(220, 150)
        self.assertTrue(menu.dropdown)
        menu.click(220, 166 + 3 * 19 + 8)
        self.assertEqual(menu.screen, "4")
        self.assertFalse(menu.peaceful)
        menu.click(220, 150)
        menu.click(150, 195)
        self.assertFalse(menu.dropdown)
        self.assertFalse(menu.peaceful)
        self.assertEqual(menu.click(150, 195), "peaceful")
        self.assertEqual(menu.click(150, 245), "go")
        self.assertEqual(menu.click(290, 245), "resume")

    def test_horizontal_keys_follow_the_two_buttons_without_activating_them(self):
        menu = self.menu
        menu.focus = 2
        for key, focus in (("Right", 3), ("Right", 3), ("Left", 2), ("Left", 2)):
            with self.subTest(key=key, focus=focus):
                self.assertEqual(menu.key(key), "changed")
                self.assertEqual(menu.focus, focus)
                self.assertEqual(menu.screen, "5")
                self.assertFalse(menu.peaceful)
                self.assertFalse(menu.dropdown)
        menu.focus = 1
        menu.key("Right")
        self.assertEqual(menu.focus, 1)

    def test_hover_changes_only_real_controls_or_popup_options(self):
        menu = self.menu
        self.assertFalse(menu.hover(30, 30))
        self.assertTrue(menu.hover(150, 195))
        self.assertFalse(menu.hover(150, 195))
        menu.focus = 0
        menu.open_dropdown()
        self.assertTrue(menu.hover(220, 172))
        self.assertEqual(menu.option_index, 0)
        self.assertEqual(menu.screen, "5")

    def test_tabs_and_display_checkbox_are_keyboard_accessible(self):
        menu = self.menu
        menu.focus = -1
        menu.key("Right")
        self.assertEqual((menu.tab, menu.focus), (1, -1))
        menu.key("Right")
        menu.key("Down")
        self.assertEqual((menu.tab, menu.focus), (2, 1))
        self.assertEqual(menu.key("space"), "debug_status")
        self.assertTrue(menu.debug_status)
        menu.key("Down")
        menu.key("Left")
        self.assertEqual(menu.focus, 3)

    def test_playback_dropdown_scrolls_to_all_parts_without_covering_the_viewport(self):
        menu = self.menu
        menu.sections = tuple(f"Story {i}" for i in range(30))
        menu.change_tab(1)
        menu.focus = 4
        menu.open_dropdown()
        for _ in range(25):
            menu.key("Down")
        self.assertEqual(menu.option_index, 25)
        self.assertEqual(menu.popup_start, 21)
        self.assertEqual(menu.popup_count, 8)
        menu.click(220, 208 + (25 - menu.popup_start) * 19 + 8)
        self.assertEqual(menu.section_index, 25)
        menu.focus = 2
        self.assertEqual(menu.key("Return"), "seek")

    def test_disabled_level_controls_cannot_activate_or_receive_button_focus(self):
        menu = self.menu
        menu.level_available = False
        menu.change_tab(0)
        self.assertEqual(menu.focus, 3)
        menu.key("Left")
        self.assertEqual(menu.focus, 3)
        self.assertEqual(menu.click(150, 195), "changed")
        self.assertFalse(menu.peaceful)

    def test_popup_hover_keeps_rows_stable_and_wheel_reaches_both_ends(self):
        menu = self.menu
        menu.sections = tuple(f"Story {i}" for i in range(30))
        menu.section_index = 15
        menu.change_tab(1)
        menu.focus = 4
        menu.open_dropdown()
        start = menu.popup_start
        menu.hover(220, 214)
        self.assertEqual(menu.popup_start, start)
        menu.click(220, 214)
        self.assertEqual(menu.section_index, start)
        menu.open_dropdown()
        menu.scroll(100)
        self.assertEqual((menu.option_index, menu.popup_start), (29, 22))
        menu.scroll(-100)
        self.assertEqual((menu.option_index, menu.popup_start), (0, 0))
        self.assertEqual(menu.section_index, start)

    def test_playback_sequences_filter_parts_and_preserve_absolute_selection(self):
        menu = self.menu
        menu.sections = ("Story 1", "Story 2", "Clouds", "Screen 1", "Screen 2")
        menu.section_groups = (PlaybackGroup("Prologue", (0, 1)),
                               PlaybackGroup("Titles", (2,)),
                               PlaybackGroup("Level 1 demo", (3, 4)))
        menu.section_index = 4
        menu.change_tab(1)
        self.assertEqual(menu.group_index, 2)
        self.assertEqual(menu.options, ("Prologue", "Titles", "Level 1 demo"))
        self.assertEqual(menu.field_options(4), ("Screen 1", "Screen 2"))
        self.assertEqual(menu.field_selected_index(4), 1)
        menu.key("Left")
        self.assertEqual(menu.section_index, 2)
        self.assertEqual(menu.field_options(4), ("Clouds",))
        menu.key("Left")
        menu.key("Down")
        self.assertEqual(menu.focus, 4)
        menu.key("Right")
        self.assertEqual(menu.section_index, 1)
        self.assertEqual(menu.next_section_index, 2)
        menu.key("Down")
        self.assertEqual(menu.key("Return"), "next_part")

    def test_sequence_popup_cancel_does_not_change_current_part(self):
        menu = self.menu
        menu.sections = ("First", "Second")
        menu.section_groups = (PlaybackGroup("Intro", (0,)), PlaybackGroup("Demo", (1,)))
        menu.change_tab(1)
        menu.key("Return")
        menu.key("Down")
        self.assertEqual(menu.section_index, 0)
        menu.key("Escape")
        self.assertEqual(menu.group_index, 0)
        menu.click(220, 150)
        menu.click(220, 166 + 19 + 8)
        self.assertEqual(menu.section_index, 1)

    def test_playback_buttons_keep_horizontal_navigation_and_click_actions(self):
        menu = self.menu
        menu.sections = ("First", "Second")
        menu.change_tab(1)
        menu.click(220, 194)
        self.assertEqual(menu.dropdown_control, 4)
        menu.click(220, 208 + 19 + 8)
        self.assertEqual(menu.section_index, 1)
        menu.focus = 2
        menu.key("Right")
        self.assertEqual(menu.focus, 3)
        menu.key("Left")
        self.assertEqual(menu.focus, 2)
        self.assertEqual(menu.click(150, 285), "seek")
        self.assertEqual(menu.click(290, 285), "resume")
        self.assertEqual(menu.click(220, 232), "next_part")

    def test_native_pointer_coordinates_survive_resize_and_letterboxing(self):
        for dimensions in ((512, 384), (800, 900), (1920, 1080), (2560, 1440)):
            with self.subTest(dimensions=dimensions):
                size, origin = fit_viewport(*dimensions)
                for x, y in ((220, 150), (150, 195), (290, 245)):
                    mapped = viewport_point(origin[0] + (x - 1) * size[0] / 510,
                                            origin[1] + y * size[1] / 384, *dimensions)
                    self.assertAlmostEqual(mapped[0], x)
                    self.assertAlmostEqual(mapped[1], y)
                self.assertIsNone(viewport_point(origin[0] - 1, origin[1], *dimensions))
                self.assertIsNone(viewport_point(origin[0] + size[0], origin[1], *dimensions))


class MenuSceneTests(unittest.TestCase):
    setUp = test_terrain.RooftopSceneTests.setUp
    tick = test_terrain.RooftopSceneTests.tick

    @staticmethod
    def event(key, state=0):
        return SimpleNamespace(keysym=key, state=state)

    def test_overlay_is_in_the_viewport_without_another_window_or_texture_mutation(self):
        scene = self.scene
        scene.jump_to_screen("5")
        before = scene.native_viewport.copy()
        scenery = scene.background.tobytes()
        children = scene.root.winfo_children()
        scene.open_dev_mode()
        self.assertEqual(scene.root.winfo_children(), children)
        self.assertEqual(scene.native_viewport.size, (512, 384))
        original, dimmed = before.getpixel((30, 20)), scene.native_viewport.getpixel((30, 20))
        self.assertTrue(all(dimmed[i] < original[i] for i in range(3)))
        self.assertEqual(scene.native_viewport.getpixel((101, 71)), (24, 24, 24, 255))
        self.assertEqual(scene.background.tobytes(), scenery)
        scene.close_dev_mode()
        self.assertEqual(scene.native_viewport.tobytes(), before.tobytes())

    def test_dev_mode_heading_uses_the_same_name_as_the_game_menu(self):
        scene = self.scene
        with patch.object(scene.ui_font, "text", wraps=scene.ui_font.text) as text:
            scene.open_dev_mode()
        labels = [call.args[0] for call in text.call_args_list]
        self.assertIn("Dev Mode", labels)
        self.assertNotIn("Development", labels)

    def test_debug_status_is_hidden_by_default_and_restored_only_when_enabled(self):
        scene = self.scene
        self.assertFalse(scene.debug_status)
        self.assertEqual(scene.status_label.winfo_manager(), "")
        scene.open_dev_mode()
        scene.dev_menu.change_tab(2)
        scene.dev_menu.focus = 1
        scene.apply_dev_action(scene.dev_menu.activate())
        self.assertTrue(scene.debug_status)
        self.assertEqual(scene.status_label.winfo_manager(), "pack")
        with patch.object(scene.root, "attributes"), patch.object(scene.root, "state"):
            scene.toggle_fullscreen()
            self.assertEqual(scene.status_label.winfo_manager(), "")
            scene.toggle_fullscreen()
            self.assertEqual(scene.status_label.winfo_manager(), "pack")
        scene.apply_dev_action(scene.dev_menu.activate())
        self.assertFalse(scene.debug_status)
        self.assertEqual(scene.status_label.winfo_manager(), "")

    def test_mouse_wheel_scrolls_only_the_open_dev_dropdown(self):
        scene = self.scene
        event = SimpleNamespace(delta=-120)
        self.assertIsNone(scene.dev_scroll(event))
        scene.open_dev_mode()
        scene.dev_menu.sections = tuple(f"Story {i}" for i in range(30))
        scene.dev_menu.change_tab(1)
        scene.dev_menu.focus = 4
        scene.dev_menu.open_dropdown()
        with patch.object(scene, "dev_pointer", return_value=(220, 214)):
            for _ in range(20):
                self.assertEqual(scene.dev_scroll(event), "break")
        self.assertEqual(scene.dev_menu.option_index, 20)
        self.assertEqual(scene.dev_menu.section_index, 0)

    def test_simulation_and_game_inputs_stay_frozen_and_pause_state_is_restored(self):
        scene = self.scene
        scene.jump_to_screen("5")
        for was_paused in (False, True):
            scene.set_paused(was_paused)
            scene.open_dev_mode()
            before = (scene.action, scene.player_x, scene.combat.world_frame,
                      scene.combat.guard.state.__dict__.copy())
            for key in ("Control_L", "F5", "Shift_L"):
                self.assertEqual(scene.dev_key_press(self.event(key)), "break")
            scene.horizontal_key(None, 1, True)
            scene.set_key_state("up", True)
            self.tick(10)
            self.assertEqual(before, (scene.action, scene.player_x, scene.combat.world_frame,
                                     scene.combat.guard.state.__dict__))
            scene.close_dev_mode()
            self.assertEqual(scene.paused, was_paused)
            self.assertEqual(scene.held_directions, [])
            self.assertFalse(scene.up_held)
            self.assertIsNone(scene.pending_action)

    def test_escape_autorepeat_does_not_pause_again_after_closing(self):
        scene = self.scene
        scene.open_dev_mode()
        scene.dev_key_press(self.event("Escape"))
        self.assertIsNone(scene.dev_menu)
        scene.escape_key()
        self.assertFalse(scene.paused)
        scene.dev_key_release(self.event("Escape"))
        scene.escape_key()
        self.assertTrue(scene.paused)

    def test_horizontal_button_navigation_stays_in_menu_without_teleporting_or_resuming(self):
        scene = self.scene
        scene.open_dev_mode()
        before = scene.room_id, scene.player_x, scene.sequence_state.__dict__.copy()
        scene.dev_menu.focus = 2
        for key, focus in (("Right", 3), ("Left", 2)):
            self.assertEqual(scene.dev_key_press(self.event(key)), "break")
            self.assertEqual(scene.dev_menu.focus, focus)
            self.assertTrue(scene.paused)
            self.assertEqual(before, (scene.room_id, scene.player_x, scene.sequence_state.__dict__))

    def test_f2_toggles_without_repeated_open_close_while_held(self):
        scene = self.scene
        event = self.event("F2")
        scene.open_dev_mode(event)
        scene.open_dev_mode(event)
        self.assertIsNotNone(scene.dev_menu)
        scene.dev_key_release(event)
        scene.open_dev_mode(event)
        scene.open_dev_mode(event)
        self.assertIsNone(scene.dev_menu)
        self.assertFalse(scene.paused)

    def test_fullscreen_cursor_is_visible_only_during_menu_and_alt_enter_is_not_consumed(self):
        scene = self.scene
        scene.fullscreen = True
        scene.canvas.configure(cursor="none")
        scene.open_dev_mode()
        self.assertEqual(scene.canvas.cget("cursor"), "")
        for modifier in (0x8, 0x20000, 0x20008):
            self.assertIsNone(scene.dev_key_press(self.event("Return", state=modifier)))
            scene.dev_key_release(self.event("Return"))
        scene.close_dev_mode()
        self.assertEqual(scene.canvas.cget("cursor"), "none")
        scene.open_dev_mode()
        with patch.object(scene.root, "attributes"), patch.object(scene.root, "state"):
            scene.toggle_fullscreen()
            scene.toggle_fullscreen()
        self.assertEqual(scene.canvas.cget("cursor"), "")
        self.assertIsNotNone(scene.dev_menu)

    def test_mouse_uses_presented_viewport_and_ignores_black_bars(self):
        scene = self.scene
        scene.open_dev_mode()
        with patch.object(scene.canvas, "winfo_width", return_value=1920), \
                patch.object(scene.canvas, "winfo_height", return_value=1080):
            scene.dev_click(SimpleNamespace(x=100, y=200))
            self.assertFalse(scene.peaceful)
            scene.dev_click(SimpleNamespace(x=240 + 150 * 1080 / 384, y=195 * 1080 / 384))
            self.assertTrue(scene.peaceful)
            scene.dev_hover(SimpleNamespace(x=240 + 290 * 1080 / 384, y=245 * 1080 / 384))
            self.assertEqual(scene.dev_menu.focus, 3)

    def test_invalid_destination_keeps_menu_and_scene_intact_with_inline_error(self):
        scene = self.scene
        scene.open_dev_mode()
        snapshot = scene.room_id, scene.player_x, scene.combat.guard
        with patch.object(scene, "jump_to_screen", side_effect=ValueError("This screen has no supported entry")):
            scene.apply_dev_action("go")
        self.assertIsNotNone(scene.dev_menu)
        self.assertTrue(scene.paused)
        self.assertIn("no supported entry", scene.dev_menu.error)
        self.assertEqual(snapshot, (scene.room_id, scene.player_x, scene.combat.guard))
        scene.dev_menu.key("Right")
        self.assertEqual(scene.dev_menu.error, "")

    def test_dropdown_and_error_render_within_the_native_viewport(self):
        scene = self.scene
        menu = DevelopmentMenu(SCREENS, 7, True)
        menu.error = "This screen has no supported entry"
        viewport = Image.new("RGBA", (512, 384), (80, 80, 80, 255))
        menu.open_dropdown()
        result = menu.draw(viewport, scene.ui_font)
        self.assertEqual(result.size, viewport.size)
        self.assertEqual(viewport.getpixel((256, 200)), (80, 80, 80, 255))
        self.assertEqual(result.getpixel((200, 166 + 8 * 19)), (244, 216, 115, 255))
        self.assertIn("DevelopmentInput", scene.root.bindtags())
        self.assertIn("DevelopmentInput", scene.canvas.bindtags())

    def test_playback_part_popup_fits_below_the_second_selector(self):
        scene = self.scene
        menu = DevelopmentMenu(SCREENS, 0, False, sections=tuple(f"Story {i}" for i in range(30)))
        menu.change_tab(1)
        menu.focus = 4
        menu.open_dropdown()
        viewport = Image.new("RGBA", (512, 384), (80, 80, 80, 255))
        result = menu.draw(viewport, scene.ui_font)
        bottom = menu.control_rect(4)[3] + menu.popup_count * menu.OPTION_HEIGHT
        self.assertEqual(bottom, 360)
        left = menu.control_rect(4)[0]
        self.assertEqual(result.getpixel((left, bottom)), (244, 216, 115, 255))
        self.assertEqual(result.getpixel((left, bottom + 1)), result.getpixel((30, 20)))

    def test_ordinary_keys_resume_pause_without_gameplay_or_repeat_until_release(self):
        scene = self.scene
        scene.jump_to_screen("5")
        for key in ("Left", "Right", "Up", "Down", "a", "space", "Return", "Tab", "KP_0"):
            with self.subTest(key=key):
                scene.set_paused(True)
                before = scene.sequence_state.__dict__.copy()
                event = self.event(key)
                self.assertEqual(scene.dev_key_press(event), "break")
                self.assertFalse(scene.paused)
                self.assertEqual(scene.dev_key_press(event), "break")
                self.assertEqual(scene.sequence_state.__dict__, before)
                self.assertEqual(scene.horizontal_input, 0)
                self.assertFalse(scene.up_held)
                self.assertFalse(scene.ctrl_held)
                self.assertIsNone(scene.pending_action)
                self.assertEqual(scene.dev_key_release(event), "break")
                self.assertIsNone(scene.dev_key_press(event))

    def test_command_lock_function_and_media_keys_leave_the_game_paused(self):
        scene = self.scene
        scene.set_paused(True)
        keys = ("Control_L", "Control_R", "Shift_L", "Alt_L", "Alt_R", "Super_L",
                "Caps_Lock", "Num_Lock", "Scroll_Lock", "Pause", "Print", "F1", "F5",
                "F12", "XF86AudioMute", "XF86AudioLowerVolume", "XF86AudioRaiseVolume",
                "XF86AudioPlay", "Insert", "Delete", "Home", "End", "Prior", "Next")
        for key in keys:
            with self.subTest(key=key):
                self.assertEqual(scene.dev_key_press(self.event(key)), "break")
                self.assertTrue(scene.paused)
                scene.dev_key_release(self.event(key))

    def test_system_shortcuts_do_not_resume_but_shifted_text_does(self):
        scene = self.scene
        scene.set_paused(True)
        for key, state in (("Tab", 0x8), ("Tab", 0x20000), ("a", 0x4), ("d", 0x40)):
            with self.subTest(key=key, state=state):
                event = self.event(key, state)
                self.assertEqual(scene.dev_key_press(event), "break")
                self.assertTrue(scene.paused)
                scene.dev_key_release(event)
        scene.dev_key_press(self.event("Alt_L"))
        self.assertEqual(scene.dev_key_press(self.event("Tab")), "break")
        self.assertTrue(scene.paused)
        scene.clear_keys(SimpleNamespace())
        event = self.event("A", 1)
        event.char = "A"
        self.assertEqual(scene.dev_key_press(event), "break")
        self.assertFalse(scene.paused)

    def test_alt_enter_remains_available_without_resuming_pause(self):
        scene = self.scene
        scene.set_paused(True)
        self.assertIsNone(scene.dev_key_press(self.event("Return", 0x20000)))
        scene.toggle_fullscreen()
        self.assertTrue(scene.fullscreen)
        self.assertTrue(scene.paused)
        scene.toggle_fullscreen()

    def test_mouse_buttons_keep_pause_and_do_not_close_development_menu(self):
        scene = self.scene
        for button in (1, 2, 3):
            scene.set_paused(True)
            event = SimpleNamespace(x=10, y=10, num=button)
            self.assertEqual(scene.dev_click(event), "break")
            self.assertTrue(scene.paused)
            scene.open_dev_mode()
            scene.dev_click(event)
            self.assertIsNotNone(scene.dev_menu)
            self.assertTrue(scene.paused)
            scene.close_dev_mode()

    def test_f2_from_pause_keeps_pause_and_focus_loss_clears_consumed_key(self):
        scene = self.scene
        scene.set_paused(True)
        self.assertEqual(scene.dev_key_press(self.event("F2")), "break")
        self.assertIsNotNone(scene.dev_menu)
        scene.close_dev_mode()
        self.assertTrue(scene.paused)
        scene.dev_key_press(self.event("Left"))
        scene.clear_keys(None)
        self.assertIsNone(scene.dev_key_press(self.event("Left")))

    def test_held_menu_activation_does_not_unpause_a_previously_paused_game(self):
        scene = self.scene
        scene.set_paused(True)
        scene.open_dev_mode()
        scene.dev_menu.focus = 3
        scene.dev_key_press(self.event("Return"))
        self.assertIsNone(scene.dev_menu)
        self.assertEqual(scene.dev_key_press(self.event("Return")), "break")
        self.assertTrue(scene.paused)
        scene.dev_key_release(self.event("Return"))
        scene.dev_key_press(self.event("Return"))
        self.assertFalse(scene.paused)


    def test_held_navigation_key_cannot_reach_gameplay_after_keyboard_close(self):
        scene = self.scene
        scene.jump_to_screen("1")
        scene.open_dev_mode()
        scene.dev_menu.focus = 2
        self.assertEqual(scene.dev_key_press(self.event("Right")), "break")
        self.assertEqual(scene.dev_menu.focus, 3)
        scene.dev_key_press(self.event("Return"))
        self.assertFalse(scene.paused)
        self.assertEqual(scene.dev_key_press(self.event("Right")), "break")
        self.assertEqual(scene.horizontal_input, 0)
        self.assertFalse(scene.run_active)
        self.assertEqual(scene.dev_key_release(self.event("Right")), "break")
        self.assertIsNone(scene.dev_key_press(self.event("Right")))

    def test_mouse_close_consumes_all_held_keys_even_after_peaceful_toggle(self):
        scene = self.scene
        scene.open_dev_mode()
        keys = ("Left", "Up", "Control_L", "Shift_L")
        for key in keys:
            scene.dev_key_press(self.event(key))
        scene.set_peaceful(True)
        with patch.object(scene, "dev_pointer", return_value=(300, 245)):
            scene.dev_click(SimpleNamespace(x=600, y=490, num=1))
        self.assertIsNone(scene.dev_menu)
        for key in keys:
            self.assertEqual(scene.dev_key_press(self.event(key)), "break")
            self.assertEqual(scene.dev_key_release(self.event(key)), "break")
        self.assertEqual(scene.horizontal_input, 0)
        self.assertFalse(scene.sword_drawn)

    def test_released_menu_key_is_not_consumed_after_close(self):
        scene = self.scene
        scene.open_dev_mode()
        scene.dev_key_press(self.event("Down"))
        scene.dev_key_release(self.event("Down"))
        scene.close_dev_mode()
        self.assertIsNone(scene.dev_key_press(self.event("Down")))

    def test_consumed_f2_and_escape_releases_reset_their_toggle_guards(self):
        scene = self.scene
        scene.open_dev_mode()
        scene.dev_key_press(self.event("F2"))
        scene.open_dev_mode(self.event("F2"))
        self.assertIsNone(scene.dev_menu)
        self.assertTrue(scene.dev_toggle_held)
        scene.dev_key_release(self.event("F2"))
        self.assertFalse(scene.dev_toggle_held)
        scene.open_dev_mode()
        scene.dev_key_press(self.event("Escape"))
        self.assertTrue(scene.escape_held)
        scene.dev_key_release(self.event("Escape"))
        self.assertFalse(scene.escape_held)
        scene.escape_key()
        self.assertTrue(scene.paused)

    def test_focus_loss_clears_physical_keys_and_modal_toggle_guards(self):
        scene = self.scene
        scene.window_keys_down.update(("Right", "F2", "Escape"))
        scene.pause_resume_keys.add("Right")
        scene.escape_held = scene.dev_toggle_held = True
        scene.clear_keys(SimpleNamespace())
        self.assertEqual(scene.window_keys_down, set())
        self.assertEqual(scene.pause_resume_keys, set())
        self.assertFalse(scene.escape_held)
        self.assertFalse(scene.dev_toggle_held)

    def test_existing_held_key_cannot_immediately_resume_pause(self):
        scene = self.scene
        scene.dev_key_press(self.event("Right"))
        scene.set_paused(True)
        self.assertEqual(scene.dev_key_press(self.event("Right")), "break")
        self.assertTrue(scene.paused)
        scene.dev_key_release(self.event("Right"))
        scene.dev_key_press(self.event("Right"))
        self.assertFalse(scene.paused)


if __name__ == "__main__":
    unittest.main()
