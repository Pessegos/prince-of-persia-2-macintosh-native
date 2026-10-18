import os
import random
import struct
import time
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, call, patch

from pop2.audio import AudioEngine, MixerPlayback
from pop2.game_menu import GameMenu
from pop2.ui_audio import menu_pcm
from pop2.window_controls import WindowControls


class MenuPcmTests(unittest.TestCase):
    def test_ticks_are_short_quiet_faded_deterministic_and_stereo_aligned(self):
        before = random.getstate()
        for rate in (16000, 44100, 48000):
            for kind, duration, peak in (('hover', 0.022, 0.035), ('click', 0.038, 0.085)):
                with self.subTest(rate=rate, kind=kind):
                    pcm = menu_pcm(kind, rate, 2)
                    self.assertEqual(len(pcm), round(duration * rate) * 4)
                    self.assertEqual(pcm, menu_pcm(kind, rate, 2))
                    samples = struct.unpack('<' + 'h' * (len(pcm) // 2), pcm)
                    self.assertEqual(samples[::2], samples[1::2])
                    self.assertEqual((samples[0], samples[-1]), (0, 0))
                    self.assertEqual(max(abs(sample) for sample in samples), round(peak * 32767))
                    mono = menu_pcm(kind, rate, 1)
                    self.assertEqual(struct.unpack('<' + 'h' * (len(mono) // 2), mono), samples[::2])
        self.assertEqual(random.getstate(), before)
        with self.assertRaises(ValueError):
            menu_pcm('unknown', 48000, 2)


class MenuAudioEngineTests(unittest.TestCase):
    def engine(self):
        engine = AudioEngine.__new__(AudioEngine)
        engine.playback = Mock()
        engine.sound_enabled = True
        engine.last_ui_hover_at = float('-inf')
        engine.paused = True
        engine.current_effect, engine.current_music = 17, 40
        engine.pending_effect, engine.pending_song = 18, 41
        return engine

    def test_hover_is_rate_limited_but_click_and_game_audio_state_are_independent(self):
        engine = self.engine()
        with patch('pop2.audio.time.perf_counter', side_effect=(1, 1.01, 1.07, 1.08)):
            for kind in ('hover', 'hover', 'hover', 'click'):
                engine.play_ui(kind)
        self.assertEqual(engine.playback.play_ui.call_args_list,
                         [call('hover'), call('hover'), call('click')])
        engine.playback.play.assert_not_called()
        engine.playback.pause.assert_not_called()
        self.assertEqual((engine.current_effect, engine.current_music, engine.pending_effect,
                          engine.pending_song, engine.paused), (17, 40, 18, 41, True))

    def test_sound_off_silences_current_and_future_ui_ticks(self):
        engine = self.engine()
        engine.set_sound_enabled(False)
        engine.playback.stop_ui.assert_called_once()
        engine.play_ui('hover')
        engine.play_ui('click')
        engine.playback.play_ui.assert_not_called()
        engine.set_sound_enabled(True)
        engine.play_ui('click')
        engine.playback.play_ui.assert_called_once_with('click')


class MenuInputAudioTests(unittest.TestCase):
    def setUp(self):
        self.host = WindowControls.__new__(WindowControls)
        self.host.audio = Mock()
        self.host.sound_enabled = True
        self.host.game_menu = GameMenu()
        self.host.dev_menu = self.host.copy_challenge = None
        self.host.dev_pointer = Mock()
        self.host.canvas = Mock()
        self.host.canvas.cget.return_value = ''
        self.host.window_keys_down = set()
        self.host.pause_resume_keys = set()
        self.host.render = Mock()
        self.host.redraw_dev_menu = Mock()
        self.host.apply_game_action = Mock()
        self.host.apply_dev_action = Mock()

    def hover(self, point):
        self.host.dev_pointer.return_value = point
        self.host.dev_hover(SimpleNamespace())

    def test_hover_sounds_only_on_new_enabled_targets_and_reentry(self):
        menu = self.host.game_menu
        for index in (0, 0, 1, 7):
            rect = menu.row_rect(index)
            self.hover((rect[0] + 10, rect[1] + 4))
        self.hover((-1, -1))
        rect = menu.row_rect(0)
        self.hover((rect[0] + 10, rect[1] + 4))
        self.assertEqual(self.host.audio.play_ui.call_args_list, [call('hover')] * 3)
        self.host.sound_enabled = False
        rect = menu.row_rect(1)
        self.hover((rect[0] + 10, rect[1] + 4))
        self.assertEqual(self.host.audio.play_ui.call_count, 3)

    def test_clicks_ignore_empty_space_disabled_rows_and_other_mouse_buttons(self):
        host, menu = self.host, self.host.game_menu
        host.dev_pointer.return_value = (0, 0)
        host.dev_click(SimpleNamespace(num=1))
        rect = menu.row_rect(7)
        host.dev_pointer.return_value = (rect[0] + 10, rect[1] + 4)
        host.dev_click(SimpleNamespace(num=1))
        rect = menu.row_rect(1)
        host.dev_pointer.return_value = (rect[0] + 10, rect[1] + 4)
        host.dev_click(SimpleNamespace(num=3))
        host.audio.play_ui.assert_not_called()
        host.dev_click(SimpleNamespace(num=1))
        host.audio.play_ui.assert_called_once_with('click')
        host.apply_game_action.assert_called_with('confirm_new')

    def test_keyboard_navigation_activation_and_dropdown_selection_have_feedback(self):
        host, menu = self.host, self.host.game_menu
        host.menu_key_action(menu, SimpleNamespace(keysym='Down', state=0))
        host.menu_key_action(menu, SimpleNamespace(keysym='Return', state=0))
        self.assertEqual(host.audio.play_ui.call_args_list, [call('hover'), call('click')])
        menu.focus = 7
        host.menu_key_action(menu, SimpleNamespace(keysym='Return', state=0))
        host.menu_key_action(menu, SimpleNamespace(keysym='x', state=0))
        self.assertEqual(host.audio.play_ui.call_count, 2)
        menu.show_page('screenshots')
        host.menu_key_action(menu, SimpleNamespace(keysym='Return', state=0))
        self.assertTrue(menu.dropdown)
        host.menu_key_action(menu, SimpleNamespace(keysym='Down', state=0))
        host.menu_key_action(menu, SimpleNamespace(keysym='Return', state=0))
        self.assertEqual(host.audio.play_ui.call_args_list[-3:],
                         [call('click'), call('hover'), call('click')])

    def test_held_activation_key_does_not_repeat_click_feedback(self):
        host = self.host
        host.paused = True
        event = SimpleNamespace(keysym='Return', state=0)
        host.dev_key_press(event)
        host.dev_key_press(event)
        host.audio.play_ui.assert_called_once_with('click')

    def test_map_targets_are_individual_rooms_not_the_entire_workspace(self):
        from tests.test_development_map import DevelopmentMapModelTests, room_point

        host = self.host
        host.game_menu = None
        host.dev_menu = menu = DevelopmentMapModelTests().menu()
        for label in ('Room 1', 'Room 1', 'Room 2'):
            self.hover(room_point(menu, label))
        self.hover((200, 250))
        host.dev_click(SimpleNamespace(num=1))
        self.assertEqual(host.audio.play_ui.call_args_list, [call('hover'), call('hover')])
        self.hover(room_point(menu, 'Room 3'))
        host.dev_click(SimpleNamespace(num=1))
        self.assertEqual(host.audio.play_ui.call_args_list[-2:], [call('hover'), call('click')])
        host.apply_dev_action.assert_called_with('go')

    def test_gallery_image_and_caption_share_a_target_and_gaps_are_silent(self):
        from tests.test_playback_preview import GalleryModelTests, part_point
        from pop2.playback_preview import gallery_caption_rect

        host = self.host
        host.game_menu = None
        host.dev_menu, _provider = GalleryModelTests().menu()
        menu = host.dev_menu
        menu.activate()
        self.hover(part_point(menu, 0))
        rect = gallery_caption_rect(menu.gallery_preview.rooms['0'])
        left, top, _right, _bottom = menu.control_rect(4)
        self.hover((left + (rect[0] + rect[2]) / 2, top + (rect[1] + rect[3]) / 2))
        self.hover((172, 60))
        self.assertEqual(host.audio.play_ui.call_args_list, [call('hover')])
        self.hover(part_point(menu, 1))
        host.dev_click(SimpleNamespace(num=1))
        self.assertEqual(host.audio.play_ui.call_args_list[-2:], [call('hover'), call('click')])
        host.apply_dev_action.assert_called_with('seek')


class MenuSdlTests(unittest.TestCase):
    def test_ui_finishes_while_game_audio_is_paused_without_interrupting_it(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'SDL_AUDIODRIVER': 'dummy'}):
            playback = MixerPlayback(directory, {})
            try:
                time.sleep(0.02)
                playback.sounds[1] = playback.mixer.Sound(buffer=bytes(48000 * 4 // 2))
                playback.play('effect', 1)
                playback.play('music', 1)
                playback.pause(True)
                playback.play_ui('click')
                self.assertTrue(playback.ui_channels['click'].get_busy())
                time.sleep(0.10)
                self.assertFalse(playback.ui_channels['click'].get_busy())
                self.assertTrue(playback.busy('effect'))
                self.assertTrue(playback.busy('music'))
                self.assertIs(playback.channels['effect'].get_sound(), playback.sounds[1])
                playback.play_ui('hover')
                playback.stop_ui()
                self.assertFalse(any(channel.get_busy() for channel in playback.ui_channels.values()))
                self.assertTrue(playback.busy('effect'))
            finally:
                playback.close()


if __name__ == '__main__':
    unittest.main()
