"""Transient audio feedback uses the pause HUD without changing game state."""

from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from PIL import ImageChops

from pop2.render_opening import ROOM_HEIGHT, VIEWPORT_HEIGHT, VIEWPORT_WIDTH
from pop2.window_controls import WindowControls


class AudioNoticeTimerTests(unittest.TestCase):
    def host(self):
        host = WindowControls()
        host.root = Mock()
        host.ui_font = Mock()
        host.hud_text_color = (253, 255, 168, 255)
        host.audio_notice_after_id = None
        host.render = Mock()
        return host

    def test_all_four_labels_use_hud_colour_and_two_second_timer(self):
        for action, enabled, message in (
                ('sound', False, 'Sounds Off'), ('sound', True, 'Sounds On'),
                ('music', False, 'Ambient Music Off'), ('music', True, 'Ambient Music On')):
            with self.subTest(message=message):
                host = self.host()
                host.show_audio_notice(action, enabled)
                host.ui_font.text.assert_called_once_with(message, host.hud_text_color)
                self.assertIs(host.audio_notice_text, host.ui_font.text.return_value)
                host.root.after.assert_called_once_with(2000, host.clear_audio_notice)
                host.render.assert_called_once_with()

    def test_new_toggle_replaces_and_retimes_previous_notice(self):
        host = self.host()
        host.root.after.return_value = 'timer-one'
        host.show_audio_notice('sound', False)
        host.root.after.return_value = 'timer-two'
        host.show_audio_notice('music', True)
        host.root.after_cancel.assert_called_once_with('timer-one')
        self.assertEqual(host.audio_notice_after_id, 'timer-two')

    def test_timeout_clears_only_notice_and_redraws(self):
        host = self.host()
        host.paused = True
        host.clear_audio_notice()
        self.assertIsNone(host.audio_notice_text)
        self.assertIsNone(host.audio_notice_after_id)
        self.assertTrue(host.paused)
        host.render.assert_called_once_with()

    def test_destroy_cancels_timer_only_for_root(self):
        host = self.host()
        host.audio_notice_after_id = 'timer-one'
        host.cancel_audio_notice(SimpleNamespace(widget=object()))
        host.root.after_cancel.assert_not_called()
        host.cancel_audio_notice(SimpleNamespace(widget=host.root))
        host.root.after_cancel.assert_called_once_with('timer-one')
        self.assertIsNone(host.audio_notice_after_id)


class AudioNoticeSceneTests(unittest.TestCase):
    def setUp(self):
        from tests.test_terrain import RooftopSceneTests
        RooftopSceneTests.setUp(self)
        self.scene.jump_to_screen('5')

    def press(self, key):
        event = SimpleNamespace(keysym=key, state=0x20000)
        result = self.scene.dev_key_press(event)
        self.scene.dev_key_release(event)
        return result

    def test_shortcuts_draw_exact_pause_style_and_restore_paused_or_running_hud(self):
        scene = self.scene
        scene.audio = Mock()
        for paused in (False, True):
            scene.set_paused(paused)
            scene.render()
            before = scene.native_viewport.copy()
            position = scene.player_x, scene.action, scene.combat.world_frame
            for key, action, label in (('t', 'sound', 'Sounds'), ('m', 'music', 'Ambient Music')):
                for enabled in (False, True):
                    with self.subTest(paused=paused, action=action, enabled=enabled):
                        self.assertEqual(self.press(key), 'break')
                        text = scene.ui_font.text(f"{label} {'On' if enabled else 'Off'}", scene.hud_text_color)
                        self.assertEqual(scene.audio_notice_text.tobytes(), text.tobytes())
                        ink = text.getbbox()
                        y = ROOM_HEIGHT + (VIEWPORT_HEIGHT - ROOM_HEIGHT - (ink[3] - ink[1])) // 2 - ink[1]
                        expected = scene.screenshot_viewport.copy()
                        expected.paste(text, ((VIEWPORT_WIDTH - text.width) // 2, y), text)
                        self.assertEqual(scene.native_viewport.tobytes(), expected.tobytes())
                        self.assertEqual(scene.paused, paused)
                        self.assertEqual(position, (scene.player_x, scene.action, scene.combat.world_frame))
                        getattr(scene.audio, f'set_{action}_enabled').assert_called_with(enabled)
                        scene.root.after_cancel(scene.audio_notice_after_id)
                        scene.clear_audio_notice()
                        self.assertEqual(scene.native_viewport.tobytes(), before.tobytes())

    def test_repeated_key_does_not_toggle_again_or_restart_notice_timer(self):
        scene = self.scene
        event = SimpleNamespace(keysym='t', state=0x20000)
        scene.dev_key_press(event)
        timer = scene.audio_notice_after_id
        text = scene.audio_notice_text
        scene.dev_key_press(event)
        self.assertIs(scene.audio_notice_text, text)
        self.assertEqual(scene.audio_notice_after_id, timer)
        self.assertFalse(scene.sound_enabled)
        scene.dev_key_release(event)

    def test_menu_checkmarks_update_and_notice_never_covers_menu(self):
        scene = self.scene
        scene.open_game_menu()
        scene.apply_game_action('music')
        self.assertFalse(scene.game_menu.music)
        expected = scene.game_menu.draw(scene.screenshot_viewport.copy(), scene.ui_font)
        self.assertIsNone(ImageChops.difference(scene.native_viewport.convert('RGB'), expected.convert('RGB')).getbbox())
        scene.close_game_menu(resume=True)
        self.assertIsNotNone(scene.audio_notice_text)

    def test_notice_does_not_enter_clean_screenshots(self):
        scene = self.scene
        scene.render()
        clean = scene.screenshot_viewport.copy()
        self.press('t')
        self.assertEqual(scene.screenshot_viewport.tobytes(), clean.tobytes())
        self.assertNotEqual(scene.native_viewport.tobytes(), clean.tobytes())

    def test_level_complete_message_does_not_overlap_notice_and_returns_after_timeout(self):
        scene = self.scene
        scene.level_complete = True
        self.assertIsNone(scene.game.exit)
        scene.render()
        before = scene.native_viewport.copy()
        self.press('m')
        text = scene.audio_notice_text
        ink = text.getbbox()
        y = ROOM_HEIGHT + (VIEWPORT_HEIGHT - ROOM_HEIGHT - (ink[3] - ink[1])) // 2 - ink[1]
        expected = scene.screenshot_viewport.copy()
        expected.paste(text, ((VIEWPORT_WIDTH - text.width) // 2, y), text)
        self.assertEqual(scene.native_viewport.tobytes(), expected.tobytes())
        scene.root.after_cancel(scene.audio_notice_after_id)
        scene.clear_audio_notice()
        self.assertEqual(scene.native_viewport.tobytes(), before.tobytes())


if __name__ == '__main__':
    unittest.main()
