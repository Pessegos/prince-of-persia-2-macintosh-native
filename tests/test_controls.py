"""Remappable keys, controllers and the Controls page (port-only feature)."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image

from pop2 import controls_art, controls_page
from pop2.controls_page import (ACTION_COLORS, BRACKET_X, ControlsPage, draw_keycap, keyboard_bounds,
                                keyboard_keys, led_rect, line_pixels, lock_lights)
from pop2.game_menu import GameMenu
from pop2.gamepad import Hysteresis, PadReader, PadState, pad_style
from pop2.input_bindings import (Bindings, CONTROLLER_DEFAULTS, KEYBOARD_DEFAULTS, PAD_BINDABLE, key_name,
                                 key_token, pad_name)
from pop2.input_routing import KeyRouter, key_source
from pop2.preferences import load_preferences, remember
from pop2.window_controls import WindowControls

KYO = (('left', 'a'), ('down', 's'), ('right', 'd'), ('up', 'k'), ('grab', 'j'),
       ('sword', 'l'), ('time', 'o'), ('pause', 'i'), ('menu', 'u'))


def kyo_layout():
    """The layout asked for on GitHub: arrows kept, letters as second keys."""
    bindings = Bindings('keyboard')
    for action, token in KYO:
        bindings.assign(action, 1, token)
    return bindings


class BindingTests(unittest.TestCase):
    def test_defaults_are_the_original_keys(self):
        bindings = Bindings('keyboard')
        self.assertEqual(bindings.keys('left'), ('Left',))
        self.assertEqual(bindings.keys('grab'), ('Shift',))
        self.assertEqual(bindings.keys('sword'), ('Control',))
        self.assertEqual(bindings.keys('time'), ('space',))
        self.assertEqual(set(bindings.slots), set(KEYBOARD_DEFAULTS))
        pad = Bindings('controller')
        self.assertNotIn('left', pad.slots)
        self.assertEqual(set(pad.slots), set(CONTROLLER_DEFAULTS))

    def test_physical_keys_are_saved_independently_of_shift_and_num_lock(self):
        self.assertEqual(key_token('A'), 'a')
        self.assertEqual(key_token('Shift_R'), 'Shift')
        self.assertEqual(key_token('Control_L'), 'Control')
        self.assertEqual(key_token('KP_Left'), 'KP_4')
        self.assertEqual(key_token('KP_4'), 'KP_4')
        self.assertEqual(key_source('J'), key_source('j'))
        self.assertEqual(key_source('KP_Home'), key_source('KP_7'))

    def test_a_used_key_swaps_places_instead_of_doing_two_things(self):
        bindings = Bindings('keyboard')
        self.assertTrue(bindings.assign('up', 1, 'Shift'))
        self.assertEqual(bindings.slots['up'], ['Up', 'Shift'])
        self.assertEqual(bindings.slots['grab'], [None, None])
        self.assertTrue(bindings.assign('grab', 0, 'Up'))
        self.assertEqual(bindings.slots['grab'], ['Up', None])
        self.assertEqual(bindings.slots['up'], [None, 'Shift'])
        self.assertTrue(bindings.assign('up', 0, 'Shift'))
        self.assertEqual(bindings.slots['up'], ['Shift', None])

    def test_escape_f1_and_window_keys_cannot_be_moved_or_reused(self):
        bindings = Bindings('keyboard')
        for token in ('Escape', 'F1', 'F2', 'F8', 'Alt_L', 'Caps_Lock', 'dead_acute'):
            with self.subTest(token=token):
                self.assertFalse(bindings.assign('up', 1, token))
        self.assertFalse(bindings.assign('pause', 0, 'p'))
        self.assertFalse(bindings.clear('menu', 0))
        self.assertTrue(bindings.assign('pause', 1, 'p'))
        pad = Bindings('controller')
        for token in ('start', 'guide', 'dpup', 'stickup'):
            self.assertFalse(pad.assign('up', 1, token))
        self.assertTrue(pad.assign('up', 1, 'lefttrigger'))

    def test_saved_tables_are_repaired_rather_than_trusted(self):
        saved = {'left': ['a', 'a'], 'right': ['a', 'F5'], 'pause': ['q', 'p'],
                 'up': 'k', 'grab': ['j', 7], 'unknown': ['x']}
        bindings = Bindings.from_saved('keyboard', saved)
        self.assertEqual(bindings.slots['left'], ['a', None])
        self.assertEqual(bindings.slots['right'], [None, None])
        self.assertEqual(bindings.slots['pause'], ['Escape', 'p'])
        self.assertEqual(bindings.slots['up'], [None, None])
        self.assertEqual(bindings.slots['grab'], ['j', None])
        self.assertNotIn('unknown', bindings.slots)
        self.assertEqual(Bindings.from_saved('keyboard', {}), Bindings('keyboard'))
        self.assertEqual(Bindings.from_saved('keyboard', None), Bindings('keyboard'))
        round_trip = Bindings.from_saved('keyboard', kyo_layout().to_saved())
        self.assertEqual(round_trip, kyo_layout())

    def test_names_fit_the_menu_font(self):
        self.assertEqual(key_name('Control'), 'Ctrl')
        self.assertEqual(key_name('KP_4'), 'Num 4')
        self.assertEqual(key_name('bracketleft'), 'Left bracket')
        self.assertEqual(key_name('k'), 'K')
        self.assertEqual(pad_name('a', 'playstation'), 'Cross')
        # Positional: the bottom button of a Nintendo pad is printed B.
        self.assertEqual(pad_name('a', 'nintendo'), 'B')
        self.assertEqual(pad_name('righttrigger', 'xbox'), 'RT')

    def test_preferences_keep_the_tables_between_sessions(self):
        with TemporaryDirectory() as directory, \
                patch('pop2.preferences.PREFERENCES_PATH', Path(directory) / 'preferences.json'):
            self.assertEqual(load_preferences().keyboard_bindings, {})
            remember(keyboard_bindings=kyo_layout().to_saved(), controller_enabled=False)
            preferences = load_preferences()
            self.assertFalse(preferences.controller_enabled)
            self.assertFalse(preferences.cave_ambience)
            self.assertEqual(Bindings.from_saved('keyboard', preferences.keyboard_bindings), kyo_layout())
            (Path(directory) / 'preferences.json').write_text('{"keyboard_bindings": [1]}')
            self.assertEqual(load_preferences().keyboard_bindings, {})


class RouterTests(unittest.TestCase):
    def test_a_key_held_by_two_sources_is_released_by_the_last(self):
        router = KeyRouter()
        self.assertTrue(router.press('key:w', 'Up'))
        self.assertFalse(router.press('pad:a', 'Up'))
        self.assertEqual(router.release('key:w'), ('Up', False))
        self.assertEqual(router.release('pad:a'), ('Up', True))
        self.assertEqual(router.release('pad:a'), (None, False))
        router.press('key:Left', None)
        self.assertEqual(router.release('key:Left'), (None, False))


class RoutedHost(WindowControls):
    """WindowControls with recorded gameplay handlers, no scene behind it."""

    def __init__(self, bindings=None):
        self.root = Mock()
        self.window_keys_down = set()
        self.pause_resume_keys = set()
        self.game_menu = self.dev_menu = None
        self.paused = False
        self.escape_held = False
        self.calls = []
        if bindings is not None:
            self.keyboard_bindings = bindings
        self.apply_game_action = Mock()
        self.open_game_menu = Mock()
        self.show_remaining_time = Mock()
        self.death = SimpleNamespace(counter=-1)

    def gameplay_controls_available(self):
        return self.game_menu is None

    def horizontal_key(self, event, direction, pressed):
        self.calls.append(('horizontal', direction, pressed))
        return 'break'

    def up_key(self, event):
        self.calls.append(('up', True))
        return 'break'

    def set_key_state(self, key, pressed):
        self.calls.append((key, pressed))
        return 'break'

    def escape_key(self, event=None):
        self.calls.append(('escape', True))
        return 'break'

    def escape_release(self, event=None):
        self.calls.append(('escape', False))
        return 'break'


def send(host, keysym, pressed, state=0):
    """A key as Tk delivers it: class binding first, then the window's own."""
    event = SimpleNamespace(keysym=keysym, state=state, char=keysym if len(keysym) == 1 else '')
    result = (host.dev_key_press if pressed else host.dev_key_release)(event)
    if result is None:
        host.run_key_binding(keysym, pressed, event)
    return result


class KeyRoutingTests(unittest.TestCase):
    def test_default_keys_pass_through_untouched(self):
        host = RoutedHost()
        with patch.object(host, 'key_press_unrouted', wraps=host.key_press_unrouted) as press:
            send(host, 'Left', True)
        self.assertEqual(press.call_args.args[0].keysym, 'Left')
        self.assertFalse(hasattr(press.call_args.args[0], 'synthetic'))
        send(host, 'Left', False)
        send(host, 'Shift_R', True)
        send(host, 'Shift_R', False)
        self.assertEqual(host.calls, [('horizontal', -1, True), ('horizontal', -1, False),
                                      ('shift', True), ('shift', False)])

    def test_chosen_letters_reach_the_game_as_the_original_keys(self):
        host = RoutedHost(kyo_layout())
        for letter in 'adksjl':
            self.assertEqual(send(host, letter, True), 'break')
            self.assertEqual(send(host, letter, False), 'break')
        self.assertEqual(host.calls, [
            ('horizontal', -1, True), ('horizontal', -1, False),
            ('horizontal', 1, True), ('horizontal', 1, False),
            ('up', True), ('up', False), ('down', True), ('down', False),
            ('shift', True), ('shift', False), ('ctrl', True), ('ctrl', False)])
        # The original keys reach the same state the window keeps for pauses.
        send(host, 'k', True)
        self.assertIn('Up', host.window_keys_down)
        self.assertNotIn('k', host.window_keys_down)

    def test_shift_held_letters_and_autorepeat_stay_the_same_key(self):
        host = RoutedHost(kyo_layout())
        send(host, 'd', True)
        send(host, 'D', True, state=1)
        send(host, 'D', False, state=1)
        self.assertEqual(host.calls, [('horizontal', 1, True), ('horizontal', 1, True),
                                      ('horizontal', 1, False)])

    def test_two_keys_for_one_action_release_together(self):
        bindings = kyo_layout()
        bindings.assign('up', 1, 'w')
        host = RoutedHost(bindings)
        send(host, 'Up', True)
        send(host, 'w', True)
        send(host, 'Up', False)
        self.assertEqual(host.calls, [('up', True), ('up', True)])
        self.assertIn('Up', host.window_keys_down)
        send(host, 'w', False)
        self.assertEqual(host.calls[-1], ('up', False))
        self.assertNotIn('Up', host.window_keys_down)

    def test_a_moved_original_key_no_longer_acts_during_play(self):
        bindings = Bindings('keyboard')
        bindings.assign('left', 0, 'a')
        bindings.assign('time', 0, 'o')
        host = RoutedHost(bindings)
        self.assertEqual(send(host, 'Left', True), 'break')
        self.assertEqual(send(host, 'Left', False), 'break')
        self.assertEqual(send(host, 'space', True), 'break')
        host.show_remaining_time.assert_not_called()
        self.assertEqual(host.calls, [])
        send(host, 'o', True)
        host.show_remaining_time.assert_called_once_with()

    def test_menus_keep_their_own_keys_but_take_chosen_pause_and_menu_keys(self):
        bindings = kyo_layout()
        bindings.assign('left', 0, 'q')
        host = RoutedHost(bindings)
        host.game_menu = GameMenu()
        host.menu_key_action = Mock(return_value='changed')
        host.play_menu_sound = Mock()
        send(host, 'Left', True)
        self.assertEqual(host.menu_key_action.call_args.args[1].keysym, 'Left')
        send(host, 'Left', False)
        send(host, 'a', True)
        self.assertEqual(host.menu_key_action.call_args.args[1].keysym, 'a')
        send(host, 'a', False)
        send(host, 'u', True)
        host.open_game_menu.assert_called_once_with()

    def test_alt_shortcuts_are_never_translated(self):
        bindings = kyo_layout()
        bindings.assign('right', 1, 'r')
        host = RoutedHost(bindings)
        with patch('pop2.window_controls.sys.platform', 'win32'):
            send(host, 'r', True, state=0x20000)
        host.apply_game_action.assert_called_once_with('restart', preserve_controls=True)
        self.assertEqual(host.calls, [])

    def test_text_fields_receive_the_letters_themselves(self):
        host = RoutedHost(kyo_layout())
        host.game_menu = SimpleNamespace(page='saves', save_browser=SimpleNamespace(editing=True))
        self.assertEqual(host.input_context(), 'text')
        self.assertEqual(host.routed_key(SimpleNamespace(keysym='a', state=0), 'text'), ('a', False))

    def test_a_release_follows_the_meaning_its_press_had(self):
        host = RoutedHost(kyo_layout())
        send(host, 'd', True)
        host.game_menu = GameMenu()
        host.key_release_unrouted = Mock(return_value='break')
        send(host, 'd', False)
        self.assertEqual(host.key_release_unrouted.call_args.args[0].keysym, 'Right')

    def test_focus_loss_forgets_every_routed_hold(self):
        host = RoutedHost(kyo_layout())
        host.clear_keys = Mock()
        host.root.after_idle.return_value = 'idle'
        send(host, 'd', True)
        host.focus_pause_after_id = None
        host.copy_pointer_held = False
        host.focus_out(SimpleNamespace(widget=host.root))
        self.assertEqual(host.key_router.sources, {})


class PadReaderTests(unittest.TestCase):
    def test_hysteresis_holds_near_the_edge(self):
        gate = Hysteresis(.5, .35)
        self.assertEqual([gate.update(v) for v in (.4, .55, .4, .36, .3, .45)],
                         [False, True, True, True, False, False])

    def test_stick_up_needs_a_firmer_push_than_sideways(self):
        reader = PadReader()
        pad = PadState(1, 'Pad', 'xbox', frozenset(), {'leftx': .55, 'lefty': -.55})
        self.assertEqual(reader.inputs([pad]), {'stickright'})
        pad = PadState(1, 'Pad', 'xbox', frozenset(), {'leftx': .7, 'lefty': -.7})
        self.assertEqual(reader.inputs([pad]), {'stickright', 'stickup'})

    def test_triggers_and_several_pads_merge(self):
        reader = PadReader()
        pads = [PadState(1, 'One', 'xbox', frozenset({'a'}), {'righttrigger': .9}),
                PadState(2, 'Two', 'playstation', frozenset({'b'}), {})]
        self.assertEqual(reader.inputs(pads), {'a', 'b', 'righttrigger'})
        self.assertEqual(reader.inputs(pads[1:]), {'b'})

    def test_styles_come_from_sdl_types_or_names(self):
        self.assertEqual(pad_style(4), 'playstation')
        self.assertEqual(pad_style(7), 'playstation')
        self.assertEqual(pad_style(5), 'nintendo')
        self.assertEqual(pad_style(2), 'xbox')
        self.assertEqual(pad_style(0, 'Wireless Controller DualSense'), 'playstation')
        self.assertEqual(pad_style(0, 'Generic USB Gamepad'), 'xbox')


class PadRoutingTests(unittest.TestCase):
    def test_pad_buttons_reach_the_game_as_original_keys_in_chord_order(self):
        host = RoutedHost()
        host.process_pad_input({'dpright', 'rightshoulder', 'a'}, now=0)
        self.assertEqual(host.calls, [('shift', True), ('up', True), ('horizontal', 1, True)])
        host.process_pad_input({'dpright'}, now=.1)
        # Releases run the other way: the modifier outlives what it modifies.
        self.assertEqual(host.calls[-2:], [('up', False), ('shift', False)])

    def test_dpad_and_stick_hold_one_direction_together(self):
        host = RoutedHost()
        host.process_pad_input({'dpleft'}, now=0)
        host.process_pad_input({'dpleft', 'stickleft'}, now=.1)
        host.process_pad_input({'stickleft'}, now=.2)
        self.assertEqual(host.calls, [('horizontal', -1, True), ('horizontal', -1, True)])
        host.process_pad_input(set(), now=.3)
        self.assertEqual(host.calls[-1], ('horizontal', -1, False))

    def test_pad_and_keyboard_share_one_key(self):
        host = RoutedHost()
        send(host, 'Right', True)
        host.process_pad_input({'dpright'}, now=0)
        host.process_pad_input(set(), now=.1)
        self.assertEqual(host.calls[-1], ('horizontal', 1, True))
        send(host, 'Right', False)
        self.assertEqual(host.calls[-1], ('horizontal', 1, False))

    def test_inputs_held_while_unfocused_wait_for_a_fresh_press(self):
        host = RoutedHost()
        host.process_pad_input({'a'}, now=0, foreground=False)
        host.process_pad_input({'a'}, now=.1)
        self.assertEqual(host.calls, [])
        host.process_pad_input(set(), now=.2)
        host.process_pad_input({'a'}, now=.3)
        self.assertEqual(host.calls, [('up', True)])

    def test_menus_use_fixed_buttons_with_repeat(self):
        host = RoutedHost()
        host.game_menu = GameMenu()
        host.menu_key_action = Mock(return_value='changed')
        host.play_menu_sound = Mock()
        host.process_pad_input({'dpdown'}, now=0)
        host.process_pad_input({'dpdown'}, now=.2)
        host.process_pad_input({'dpdown'}, now=.36)
        host.process_pad_input({'dpdown'}, now=.45)
        keys = [call.args[1].keysym for call in host.menu_key_action.call_args_list]
        self.assertEqual(keys, ['Down', 'Down', 'Down'])
        host.process_pad_input({'a'}, now=.5)
        self.assertEqual(host.menu_key_action.call_args.args[1].keysym, 'Return')
        host.escape_key = Mock(return_value='break')
        host.process_pad_input({'b'}, now=.6)
        host.escape_key.assert_called_once()

    def test_intro_and_cutscene_replay_have_their_own_buttons(self):
        host = RoutedHost()
        host.intro = object()
        host.finish_intro = Mock()
        host.process_pad_input({'a'}, now=0)
        host.finish_intro.assert_called_once_with()
        host.intro = None
        host.cutscene_replay = object()
        host.cutscene_replay_key = Mock(return_value=True)
        host.process_pad_input({'b'}, now=.1)
        self.assertEqual(host.cutscene_replay_key.call_args.args[0].keysym, 'BackSpace')


class ControlsPageTests(unittest.TestCase):
    def page(self, **options):
        return ControlsPage(Bindings('keyboard'), Bindings('controller'), **options)

    def test_overview_tabs_and_remap_navigation(self):
        page = self.page()
        self.assertEqual(page.focused, 'tab_keyboard')
        page.key('Right')
        self.assertEqual((page.device, page.focused), ('controller', 'tab_controller'))
        page.key('Down')
        self.assertEqual(page.focused, 'toggle')
        page.key('Down')
        self.assertEqual(page.focused, 'change')
        page.key('Return')
        self.assertEqual(page.view, 'remap')
        self.assertEqual(page.focused, ('slot', 'up', 0))
        page.key('Right')
        page.key('Down')
        self.assertEqual(page.focused, ('slot', 'down', 1))
        page.key('Up')
        page.key('Up')
        self.assertEqual(page.focused, 'back')
        self.assertEqual(page.key('Escape'), 'changed')
        self.assertEqual((page.view, page.focused), ('overview', 'change'))
        self.assertEqual(page.key('Escape'), 'controls_back')
        page.key('Prior')
        self.assertEqual(page.device, 'keyboard')

    def test_listening_assigns_swaps_and_explains(self):
        page = self.page()
        page.view = 'remap'
        page.focus = page.controls().index(('slot', 'up', 1))
        page.key('Return')
        self.assertEqual(page.listening, ('up', 1))
        self.assertEqual(page.capture_key('Shift_L'), 'controls_saved')
        self.assertEqual(page.keyboard.slots['up'], ['Up', 'Shift'])
        self.assertIn('Grab', page.message)
        page.key('Return')
        self.assertEqual(page.capture_key('F2'), 'changed')
        self.assertTrue(page.message_error)
        page.key('Return')
        self.assertEqual(page.capture_key('Escape'), 'changed')
        self.assertIsNone(page.listening)
        self.assertEqual(page.keyboard.slots['up'], ['Up', 'Shift'])
        self.assertEqual(page.key('Delete'), 'controls_saved')
        self.assertEqual(page.keyboard.slots['up'], ['Up', None])
        page.focus = page.controls().index(('slot', 'pause', 0))
        page.key('Return')
        self.assertIsNone(page.listening)
        self.assertIn('Esc', page.message)
        page.focus = page.controls().index('defaults')
        self.assertEqual(page.key('Return'), 'controls_saved')
        self.assertEqual(page.keyboard, Bindings('keyboard'))

    def test_controller_slots_take_buttons_and_start_cancels(self):
        page = self.page(pads=(PadState(1, 'Pad', 'playstation'),))
        page.switch_device('controller')
        page.view = 'remap'
        page.focus = page.controls().index(('slot', 'sword', 1))
        page.key('Return')
        self.assertEqual(page.capture_pad('start'), 'changed')
        self.assertEqual(page.controller.slots['sword'], ['x', None])
        page.key('Return')
        self.assertEqual(page.capture_pad('y'), 'controls_saved')
        self.assertEqual(page.controller.slots['sword'], ['x', 'y'])
        self.assertEqual(page.controller.slots['time'], [None, None])
        page.input_device = 'pad'
        self.assertIn('Cross: change', page.hints())

    def test_every_control_can_be_clicked(self):
        for device in ('keyboard', 'controller'):
            for view in ('overview', 'remap'):
                page = self.page()
                page.device, page.view = device, view
                for index, control in enumerate(page.controls()):
                    left, top, right, bottom = page.control_rect(control)
                    with self.subTest(device=device, view=view, control=control):
                        self.assertTrue(page.PANEL[0] < left < right < page.PANEL[2])
                        self.assertTrue(page.PANEL[1] < top < bottom < page.PANEL[3])
                        self.assertEqual(page.hit((left + right) // 2, (top + bottom) // 2), index)

    def test_drawings_stay_inside_the_panel(self):
        self.assertLessEqual(max(rect[2] for _token, _label, rect in
                                 keyboard_keys(ControlsPage.KEYBOARD_ORIGIN, ControlsPage.KEYBOARD_UNIT)),
                             ControlsPage.PANEL[2] - 8)
        # The case, borders and all, sits clear of the panel's sides, the
        # tabs above it and the legend below it.
        left, top, right, bottom = keyboard_bounds(ControlsPage.KEYBOARD_ORIGIN, ControlsPage.KEYBOARD_UNIT)
        self.assertGreaterEqual(left, ControlsPage.PANEL[0] + 16)
        self.assertLessEqual(right, ControlsPage.PANEL[2] - 16)
        self.assertGreater(top, max(tab[3] for tab in ControlsPage.TABS) + 8)
        self.assertLess(bottom, ControlsPage.LEGEND_TOP - 8)

    def test_lock_lights_follow_the_real_keyboard(self):
        page = self.page()
        self.assertEqual(page.locks, {'NUM'})  # until the real state is read
        self.assertTrue(page.refresh_locks(lambda: frozenset({'CAPS', 'SCRL'})))
        self.assertFalse(page.refresh_locks(lambda: frozenset({'CAPS', 'SCRL'})))
        self.assertFalse(page.refresh_locks(lambda: None))  # unreadable: keep what is shown
        image = page.draw(Image.new('RGBA', (512, 384), 'black'), FakeFont())
        left, top, right, _bottom = led_rect(ControlsPage.KEYBOARD_ORIGIN, ControlsPage.KEYBOARD_UNIT)
        step = (right - left) / len(controls_art.LEDS)
        for index, name in enumerate(controls_art.LEDS):
            cx = round(left + step * (index + .5))
            with self.subTest(light=name):
                self.assertEqual(image.getpixel((cx + 1, top + 11))[:3],
                                 controls_art.LED_GREEN[1 if name in ('CAPS', 'SCRL') else 0])

    def test_lock_lights_read_the_toggle_bit_on_windows_only(self):
        states = {0x90: 0x8000, 0x14: 1, 0x91: 0x8001}  # Num held but off; Caps and Scroll on
        windll = SimpleNamespace(user32=SimpleNamespace(GetKeyState=lambda code: states.get(code, 0)))
        with patch.object(controls_page.sys, 'platform', 'win32'), patch('ctypes.windll', windll, create=True):
            self.assertEqual(lock_lights(), {'CAPS', 'SCRL'})
        with patch.object(controls_page.sys, 'platform', 'linux'):
            self.assertIsNone(lock_lights())

    def test_window_redraws_when_a_lock_light_changes(self):
        host = RoutedHost()
        host.render = Mock()
        page = self.page()
        host.game_menu = SimpleNamespace(page='controls', controls_page=page)
        with patch('pop2.controls_page.lock_lights', return_value=frozenset({'NUM', 'CAPS'})):
            host.watch_lock_lights()
            host.render.assert_called_once()
            host.watch_lock_lights()  # unchanged: no redraw, still watching
            host.render.assert_called_once()
        host.root.after.assert_called_with(host.LOCK_POLL_MS, host.watch_lock_lights)
        host.game_menu = None
        host.root.after.reset_mock()
        host.watch_lock_lights()  # the page has closed: the watch ends
        host.root.after.assert_not_called()

    def test_every_view_and_style_draws(self):
        font = FakeFont()
        for device in ('keyboard', 'controller'):
            for view in ('overview', 'remap'):
                for style in ('xbox', 'playstation', 'nintendo'):
                    page = self.page(pads=(PadState(1, 'Pad', style),))
                    page.device, page.view = device, view
                    page.listening = ('up', 1) if view == 'remap' else None
                    image = page.draw(Image.new('RGBA', (512, 384), 'black'), font)
                    self.assertEqual(image.size, (512, 384))


class PadArtTests(unittest.TestCase):
    """The drawn controller: tidy callouts and an exact distance field."""

    STYLES = ('xbox', 'playstation', 'nintendo')
    ROUND = {'leftstick': controls_art.STICK_WELL, 'rightstick': controls_art.STICK_WELL,
             'dpad': controls_art.DPAD_DISH, 'a': controls_art.FACE_RADIUS,
             'b': controls_art.FACE_RADIUS, 'x': controls_art.FACE_RADIUS,
             'y': controls_art.FACE_RADIUS, 'back': 6, 'start': 6, 'guide': controls_art.GUIDE_RADIUS,
             'misc1': 5}

    @staticmethod
    def polyline(side, line, path):
        return [(BRACKET_X[side], line), *path]

    @staticmethod
    def crosses(p, q, r, s):
        def turn(a, b, c):
            value = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            return (value > 0) - (value < 0)
        return turn(p, q, r) * turn(p, q, s) < 0 and turn(r, s, p) * turn(r, s, q) < 0

    @staticmethod
    def clearance(point, a, b):
        (px, py), (ax, ay), (bx, by) = point, a, b
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / max(1e-9, dx * dx + dy * dy)))
        return ((px - ax - t * dx) ** 2 + (py - ay - t * dy) ** 2) ** .5

    def test_callout_lines_neither_cross_nor_touch_another_button(self):
        cx, cy, reach = controls_art.FACE_FRAME
        cy += controls_art.ABOVE
        for style in self.STYLES:
            art = controls_art.pad_art(style)
            lines = {name: self.polyline(side, line, path)
                     for name, (side, _first, line, _buttons, path) in art.groups.items()}
            frame = list(zip(art.frame, art.frame[1:]))
            for name, line in lines.items():
                segments = list(zip(line, line[1:]))
                buttons = art.groups[name][3]
                for other, centre in art.points.items():
                    if other in buttons or other not in self.ROUND or (name == 'face' and other in 'abxy'):
                        continue
                    with self.subTest(style=style, line=name, near=other):
                        self.assertGreater(min(self.clearance(centre, *segment) for segment in segments),
                                           self.ROUND[other] + 1)
                for other, other_line in lines.items():
                    if other <= name:
                        continue
                    with self.subTest(style=style, line=name, other=other):
                        self.assertFalse(any(self.crosses(*first, *second)
                                             for first in segments
                                             for second in zip(other_line, other_line[1:])))
                if name != 'face':
                    # Only the face group's line reaches the face buttons' frame.
                    with self.subTest(style=style, line=name, near='frame'):
                        self.assertFalse(any(self.crosses(*first, *second) for first in segments
                                             for second in frame))
                        self.assertTrue(all(abs(x - cx) + abs(y - cy) > reach for x, y in line))

    def test_callout_lines_run_level_then_straight_up_or_down(self):
        for style in self.STYLES:
            for name, (side, _first, line, _buttons, path) in controls_art.pad_art(style).groups.items():
                points = self.polyline(side, line, path)
                with self.subTest(style=style, group=name):
                    self.assertEqual(points[1][1], line)  # leaves its bracket level
                    self.assertLessEqual(len(points), 3)  # bends at most once
                    for (x0, y0), (x1, y1) in zip(points, points[1:]):
                        self.assertTrue(x0 == x1 or y0 == y1)

    def test_face_frame_keeps_clear_of_the_buttons_round_it(self):
        cx, cy, reach = controls_art.FACE_FRAME
        cy += controls_art.ABOVE
        for style in self.STYLES:
            for button, centre in controls_art.pad_art(style).points.items():
                if button not in self.ROUND:
                    continue
                nearest = abs(centre[0] - cx) + abs(centre[1] - cy)
                with self.subTest(style=style, button=button):
                    if button in 'abxy':
                        # inside, with room to spare all round
                        self.assertLess(nearest + self.ROUND[button] * 2 ** .5, reach)
                    else:
                        self.assertGreater(nearest - self.ROUND[button] * 2 ** .5, reach)

    def test_labels_sit_on_one_grid_and_never_share_a_row(self):
        rows = {row + controls_art.ABOVE for row in controls_art.ROWS}
        for style in self.STYLES:
            used = {}
            for name, (side, first, line, buttons, _path) in controls_art.pad_art(style).groups.items():
                block = [first + 18 * index for index in range(len(buttons))]
                with self.subTest(style=style, group=name):
                    self.assertTrue(set(block) <= rows)
                    self.assertIn(line, block)
                    for row in block:
                        self.assertNotIn((side, row), used)
                        used[side, row] = name

    def test_every_drawn_bindable_button_has_a_callout(self):
        for style in self.STYLES:
            art = controls_art.pad_art(style)
            members = {button for _side, _first, _line, buttons, _path in art.groups.values()
                       for button in buttons}
            self.assertIn('move', members)
            for button in PAD_BINDABLE:
                if button in art.points or button.endswith(('shoulder', 'trigger')):
                    with self.subTest(style=style, button=button):
                        self.assertIn(button, members)

    def test_moving_a_button_changes_only_its_own_callout(self):
        def labels(page):
            return {button: label for _name, _side, _line, _points, rows in page.callouts()
                    for button, label, _action, _y in rows}

        page = ControlsPage(Bindings('keyboard'), Bindings('controller'),
                            pads=(PadState(1, 'Pad', 'xbox'),))
        before = labels(page)
        self.assertEqual(before['move'], 'Move')
        self.assertNotIn('leftstick', before)
        self.assertEqual(before['dpad'], 'Move')
        self.assertEqual(before['righttrigger'], 'Grab')
        self.assertNotIn('leftshoulder', before)
        self.assertNotIn('leftshoulders', {entry[0] for entry in page.callouts()})
        page.controller.assign('sword', 1, 'leftshoulder')
        after = labels(page)
        self.assertEqual(after['leftshoulder'], 'Sword')
        self.assertEqual({k: v for k, v in after.items() if k != 'leftshoulder'}, before)

    def test_a_group_lists_its_bound_buttons_from_its_first_row(self):
        page = ControlsPage(Bindings('keyboard'), Bindings('controller'),
                            pads=(PadState(1, 'Pad', 'xbox'),))
        page.controller.slots['time'] = [None, None]  # Y left unbound
        face = next(entry for entry in page.callouts() if entry[0] == 'face')
        first = page.PAD_ORIGIN[1] + controls_art.GROUPS['xbox']['face'][1] + controls_art.ABOVE
        self.assertEqual([(button, y) for button, _label, _action, y in face[4]],
                         [('x', first), ('b', first + 18), ('a', first + 36)])

    def test_distance_field_matches_brute_force(self):
        mask = controls_art.body_mask()[::3, ::3]
        fast = controls_art.distance_inside(mask)
        inside = np.argwhere(mask)
        outside = np.argwhere(np.pad(~mask, 1, constant_values=True)) - 1
        for y, x in inside[::17]:
            expected = np.sqrt(((outside - (y, x)) ** 2).sum(axis=1)).min()
            self.assertAlmostEqual(float(fast[y, x]), float(expected), places=4)

    def test_guide_coin_is_a_whole_disc_with_its_outline_round_it(self):
        coin = controls_art.GUIDE_COIN
        disc = controls_art.circle_mask(controls_art.GUIDE_RADIUS)
        drawn = np.array([[cell != ' ' for cell in row] for row in coin])
        self.assertTrue((drawn == disc).all())
        outline = np.array([[cell == '0' for cell in row] for row in coin])
        self.assertTrue(outline[controls_art.edge(disc)].all())
        self.assertTrue(all(cell == ' ' or int(cell) < len(controls_art.GOLD) for row in coin for cell in row))

    def test_shading_never_bites_into_a_shape(self):
        for mask, shading in ((controls_art.rounded(15, 11, 5), dict(rim=2, bias=.1)),
                              (controls_art.circle_mask(6, slack=1.0), dict(rim=2, dome=.3)),
                              (controls_art.dpad_cross(), dict(rim=3, bias=.15))):
            with self.subTest(shape=mask.shape):
                self.assertTrue(((controls_art.lit_levels(mask, **shading) > 0) == mask).all())

    def test_sticks_and_dpad_sit_centred_in_their_dishes(self):
        # The pad's own, and the small ones of the legends drawn by the same code.
        stick, dpad = controls_art.stick, controls_art.dpad
        for draw, args, size, ramp, least in (
                (stick, (), controls_art.STICK_WELL, controls_art.FRIEZE, 300),
                (dpad, (), controls_art.DPAD_DISH, controls_art.TAPESTRY, 300),
                (stick, controls_art.ICON_STICK, controls_art.ICON_STICK[0], controls_art.FRIEZE, 40),
                (dpad, controls_art.ICON_DPAD, controls_art.ICON_DPAD[0], controls_art.TAPESTRY, 40)):
            image = Image.new('RGBA', (2 * size + 1, 2 * size + 1), (0, 0, 0, 0))
            draw(image, (size, size), *args)
            pixels = np.array(image)[:, :, :3]
            # The cap or cross: every pixel in its own colours, mirrored both ways.
            part = np.zeros(pixels.shape[:2], bool)
            for color in ramp:
                part |= (pixels == color).all(axis=2)
            well = np.zeros(pixels.shape[:2], bool)
            for color in controls_art.WELL:
                well |= (pixels == color).all(axis=2)
            with self.subTest(part=draw.__name__, size=size):
                self.assertGreater(part.sum(), least)
                self.assertTrue((part == part[::-1]).all() and (part == part[:, ::-1]).all())
                self.assertGreater(well.sum(), least // 4)  # its dark dish shows round it

    def test_legend_icons_are_round_and_their_letters_centred(self):
        disc = controls_art.circle_mask(6, slack=1.0)
        for token in ('a', 'b', 'x', 'y', 'leftshoulder', 'rightshoulder', 'lefttrigger', 'righttrigger'):
            icon = np.array(controls_art.button_icon(token, 'xbox'))
            shape = icon[:, :, 3] > 0
            if token in 'abxy':
                letter = (icon[:, :, :3] == controls_art.SHELL[5]).all(axis=2)
            else:  # ink inside the outline, which is the same colour
                letter = (icon[:, :, :3] == controls_art.INK).all(axis=2) & ~controls_art.edge(shape)
            rows, columns = np.nonzero(shape)
            letter_rows, letter_columns = np.nonzero(letter)
            with self.subTest(token=token):
                self.assertTrue(letter.any())
                self.assertEqual(rows.min() + rows.max(), letter_rows.min() + letter_rows.max())
                self.assertEqual(columns.min() + columns.max(), letter_columns.min() + letter_columns.max())
                if token in 'abxy':  # a round button, not an octagon
                    self.assertTrue((shape[:, 2:15] == disc).all())

    def test_callout_lines_stop_short_of_their_controls(self):
        gap = controls_art.LINE_GAP
        for style in self.STYLES:
            art = controls_art.pad_art(style)
            height, width = art.controls.shape
            for name, (side, _first, line, _buttons, path) in art.groups.items():
                if name == 'face':  # it meets the frame round the face buttons
                    continue
                points = self.polyline(side, line, path)
                (x0, y0), (x1, y1) = points[-2:]
                dx, dy = (x1 > x0) - (x1 < x0), (y1 > y0) - (y1 < y0)
                ahead = [bool(art.controls[y1 + dy * step, x1 + dx * step]) for step in range(1, gap + 2)]
                with self.subTest(style=style, group=name):
                    self.assertEqual(ahead, [False] * gap + [True])
                    self.assertFalse(any(art.controls[y, x] for x, y in line_pixels(points)
                                         if 0 <= x < width and 0 <= y < height))

    def test_windows_flag_is_uncoloured_fits_its_key_and_fades_to_the_left(self):
        left, top, right, bottom = next(rect for token, _label, rect in keyboard_keys(
            ControlsPage.KEYBOARD_ORIGIN, ControlsPage.KEYBOARD_UNIT) if token == 'Win_L')
        width, height = right - left + 1, bottom - top + 1
        image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        draw_keycap(image, (0, 0, width - 1, height - 1), 'Win_L', 'WIN')
        plain = np.array(controls_art.keycap(width, height, None, True))
        drawn = np.array(image)
        flag = (drawn != plain).any(axis=2)
        rows, columns = np.nonzero(flag)
        # A pixel of the key's top left clear all round (its top ends 4 rows above the bottom).
        self.assertGreater(rows.min(), 1)
        self.assertLess(rows.max(), height - 6)
        self.assertGreater(columns.min(), 0)
        self.assertLess(columns.max(), width - 2)
        # Only shades between the key's top and its ink.
        paper, ink = np.array(controls_art.KEY_DARK[4]), np.array(controls_art.legend_ink(None, True))
        tones = {tuple(np.round(paper + (ink - paper) * n / 9).astype(int)) for n in range(1, 10)}
        self.assertTrue(all(tuple(int(v) for v in drawn[y, x, :3]) in tones for y, x in zip(rows, columns)))
        # The trail left of the flag only grows fainter outwards.
        cells = controls_art.WINDOWS_FLAG
        body = min(row.index('9') for row in cells)
        darkest = [max((int(row[x]) for row in cells if row[x] != '.'), default=0) for x in range(body)]
        seen = [value for value in reversed(darkest) if value]
        self.assertTrue(seen and seen == sorted(seen, reverse=True) and seen[-1] < seen[0])
        # Its particles are single pixels: none touches another or the frame.
        drawn_cells = {(x, y) for y, row in enumerate(cells) for x, cell in enumerate(row) if cell != '.'}
        for y, row in enumerate(cells):
            for x, cell in enumerate(row):
                if cell not in '.9':
                    with self.subTest(particle=(x, y)):
                        self.assertFalse({(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)} & drawn_cells)
        # The panes are clear: inside its frame a row shows only the key.
        for row in cells:
            width = cells[0].count('9')
            pane = '.' * ((width - 3) // 2)
            self.assertIn(row[row.index('9'):].rstrip('.'), ('9' * width, '9' + pane + '9' + pane + '9'))

    def test_shell_top_is_one_unbroken_line(self):
        body = controls_art.body_mask()
        top = np.nonzero(body.any(axis=1))[0][0]
        columns = np.nonzero(body[top])[0]
        self.assertEqual(len(columns), columns[-1] - columns[0] + 1)
        self.assertEqual(top, controls_art.SHELL_HALF[0][1] + controls_art.ABOVE)

    def test_stick_dish_edge_is_a_whole_circle(self):
        levels = controls_art.stick_cap()
        pad = controls_art.STICK_CAP - controls_art.STICK_DISH
        ring = np.pad(controls_art.edge(controls_art.circle_mask(controls_art.STICK_DISH)), pad)
        self.assertTrue((levels[ring] == 1).all())
        self.assertFalse((levels[~ring] == 1).any())

    def test_default_actions_take_their_xbox_buttons_colours(self):
        bindings = Bindings('controller')
        for button in 'abxy':
            action = next(action for action in bindings.actions if button in bindings.keys(action))
            with self.subTest(button=button, action=action):
                self.assertEqual(ACTION_COLORS[action], controls_art.XBOX_COLORS[button])

    def test_keyboard_draws_the_keypad_and_no_key_overlaps_another(self):
        keys = keyboard_keys(ControlsPage.KEYBOARD_ORIGIN, ControlsPage.KEYBOARD_UNIT)
        tokens = {token for token, _label, _rect in keys}
        self.assertTrue({'KP_0', 'KP_5', 'KP_Enter', 'KP_Add', 'Pause'} <= tokens)
        rects = [rect for _token, _label, rect in keys]
        for index, (left, top, right, bottom) in enumerate(rects):
            for other in rects[index + 1:]:
                self.assertFalse(left <= other[2] and other[0] <= right and top <= other[3] and other[1] <= bottom,
                                 ((left, top, right, bottom), other))


class FakeFont:
    height = 16
    glyphs = {code: None for code in range(32, 127)}

    def text(self, value, color=(255, 255, 255, 255)):
        return Image.new('RGBA', (max(1, 7 * len(value)), 16), color)


class GameMenuRowTests(unittest.TestCase):
    def test_controls_row_follows_the_cutscene_viewer_and_fits(self):
        menu = GameMenu()
        actions = [item.action for item in menu.items]
        self.assertEqual(actions.index('controls'), actions.index('cutscenes') + 1)
        self.assertLessEqual(menu.row_rect(len(menu.items) - 1)[3], menu.PANEL[3])
        self.assertGreaterEqual(menu.PANEL[1], 0)

    def test_menu_delegates_to_the_controls_page(self):
        menu = GameMenu()
        menu.show_page('controls')
        menu.controls_page = ControlsPage(Bindings('keyboard'), Bindings('controller'))
        self.assertEqual(menu.key('Right'), 'changed')
        self.assertEqual(menu.controls_page.device, 'controller')
        self.assertEqual(menu.key('Escape'), 'controls_back')


class CopyProtectionKeyTests(unittest.TestCase):
    def test_arrows_and_enter_pick_a_symbol(self):
        host = RoutedHost()
        host.copy_challenge = SimpleNamespace(focus=None, input_ready=True, choose=Mock())
        host.render = Mock()
        host.resolve_copy_challenge = Mock()
        for key in ('Right', 'Right', 'Down', 'Left'):
            send(host, key, True)
            send(host, key, False)
        self.assertEqual(host.copy_challenge.focus, 5)
        send(host, 'Return', True)
        host.copy_challenge.choose.assert_called_once_with(5)
        host.resolve_copy_challenge.assert_called_once_with()
        host.process_pad_input({'dpup'}, now=0)
        self.assertEqual(host.copy_challenge.focus, 0)


class SceneTests(unittest.TestCase):
    """The real game: chosen keys and a controller act exactly like the keyboard."""

    SCRIPT = (('Left', True, 6), ('Up', True, 1), ('Up', False, 10), ('Left', False, 8),
              ('Right', True, 3), ('Right', False, 6), ('Shift_L', True, 0), ('Left', True, 1),
              ('Left', False, 6), ('Shift_L', False, 2), ('Down', True, 6), ('Down', False, 6),
              ('Escape', True, 0), ('Escape', False, 0), ('Right', True, 0), ('Escape', True, 0),
              ('Escape', False, 4), ('Right', False, 6), ('space', True, 1), ('space', False, 2))
    LETTERS = {'Left': 'a', 'Right': 'd', 'Up': 'k', 'Down': 's', 'Shift_L': 'j',
               'space': 'o', 'Escape': 'i'}

    def setUp(self):
        from tests.test_terrain import RooftopSceneTests

        self.fixture = RooftopSceneTests
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch('pop2.preferences.PREFERENCES_PATH', Path(directory.name) / 'preferences.json')
        patcher.start()
        self.addCleanup(patcher.stop)

    def new_scene(self):
        import tkinter

        # A second hidden root in one test must own its own images.
        tkinter._default_root = None
        self.fixture.setUp(self)
        self.tick(19)
        return self.scene

    def tick(self, count=1):
        self.fixture.tick(self, count)

    def state(self):
        scene = self.scene
        return (scene.player_x, scene.action, scene.room_id, scene.sequence_state.sequence_id,
                scene.sequence_state.facing, scene.paused, getattr(scene, 'time_message', None))

    def run_script(self, translate):
        trace = []
        for key, pressed, ticks in self.SCRIPT:
            send(self.scene, translate(key), pressed)
            trace.append(self.state())
            for _ in range(ticks):
                self.tick()
                trace.append(self.state())
        return trace

    def test_chosen_letters_play_exactly_like_the_original_keys(self):
        self.new_scene()
        expected = self.run_script(lambda key: key)
        # The script really moves, turns, steps, crouches, pauses and asks the time.
        self.assertGreater(len({state[0] for state in expected}), 5)
        self.assertGreater(len({state[3] for state in expected}), 5)
        self.assertEqual({state[4] for state in expected}, {0, 1})
        self.assertIn(True, {state[5] for state in expected})
        scene = self.new_scene()
        bindings = Bindings('keyboard')
        for action in ('left', 'right', 'up', 'down', 'grab', 'time'):
            original = bindings.slots[action][0]
            letter = self.LETTERS['Shift_L' if original == 'Shift' else original]
            bindings.assign(action, 0, letter)
        bindings.assign('pause', 1, 'i')
        scene.keyboard_bindings = bindings
        self.assertEqual(self.run_script(lambda key: self.LETTERS[key]), expected)
        self.assertEqual(scene.key_router.sources, {})

    def test_a_controller_plays_exactly_like_the_keyboard(self):
        self.new_scene()
        expected = self.run_script(lambda key: key)
        scene = self.new_scene()
        names = {'Left': 'dpleft', 'Right': 'dpright', 'Up': 'a', 'Down': 'b',
                 'Shift_L': 'rightshoulder', 'space': 'y', 'Escape': 'back'}
        held = set()
        trace = []
        for key, pressed, ticks in self.SCRIPT:
            (held.add if pressed else held.discard)(names[key])
            scene.process_pad_input(set(held), now=self.now, foreground=True)
            trace.append(self.state())
            for _ in range(ticks):
                self.tick()
                trace.append(self.state())
        self.assertEqual(trace, expected)

    def test_start_opens_the_menu_and_the_pad_drives_it(self):
        scene = self.new_scene()
        scene.process_pad_input({'start'}, now=0, foreground=True)
        self.assertEqual(scene.game_menu.page, 'menu')
        self.assertTrue(scene.paused)
        scene.process_pad_input(set(), now=.1, foreground=True)
        scene.process_pad_input({'dpdown'}, now=.2, foreground=True)
        self.assertEqual(scene.game_menu.focus, 1)
        scene.process_pad_input(set(), now=.3, foreground=True)
        scene.process_pad_input({'b'}, now=.4, foreground=True)
        self.assertIsNone(scene.game_menu)
        self.assertFalse(scene.paused)
        # Still held, B is the Escape that closed the menu, not a crouch.
        self.tick(3)
        self.assertFalse(scene.down_held)
        scene.process_pad_input(set(), now=.5, foreground=True)
        self.assertEqual(scene.key_router.sources, {})

    def test_unplugging_a_used_controller_pauses_and_releases_it(self):
        scene = self.new_scene()
        pad = PadState(7, 'Xbox Series X Controller', 'xbox', frozenset({'dpright'}))
        scene.update_gamepads([pad], now=0, foreground=True)
        self.assertEqual(scene.held_directions, [1])
        self.assertIsNotNone(scene.audio_notice_text)
        scene.update_gamepads([], now=.1, foreground=True)
        self.assertTrue(scene.paused)
        self.assertEqual(scene.held_directions, [])
        self.assertEqual(scene.key_router.sources, {})

    def test_a_connected_but_idle_controller_leaving_does_not_pause(self):
        scene = self.new_scene()
        scene.update_gamepads([PadState(7, 'Pad', 'xbox')], now=0, foreground=True)
        scene.update_gamepads([], now=.1, foreground=True)
        self.assertFalse(scene.paused)

    def test_switching_the_controller_off_ignores_it(self):
        scene = self.new_scene()
        scene.controller_enabled = False
        scene.update_gamepads([PadState(7, 'Pad', 'xbox', frozenset({'dpright'}))], now=0,
                              foreground=True)
        self.assertEqual(scene.held_directions, [])

    def test_controls_page_remaps_a_key_and_keeps_it(self):
        scene = self.new_scene()
        send(scene, 'F1', True)
        send(scene, 'F1', False)
        menu = scene.game_menu
        menu.focus = next(i for i, item in enumerate(menu.items) if item.action == 'controls')
        send(scene, 'Return', True)
        send(scene, 'Return', False)
        page = menu.controls_page
        self.assertEqual(menu.page, 'controls')
        self.assertIsNotNone(page)
        page.focus = page.controls().index('change')
        send(scene, 'Return', True)
        send(scene, 'Return', False)
        page.focus = page.controls().index(('slot', 'grab', 1))
        send(scene, 'Return', True)
        send(scene, 'Return', False)
        self.assertEqual(scene.input_context(), 'listening')
        send(scene, 'j', True)
        # The chosen key does nothing more until it is released.
        send(scene, 'j', True)
        send(scene, 'j', False)
        self.assertEqual(scene.keyboard_bindings.slots['grab'], ['Shift', 'j'])
        self.assertEqual(load_preferences().keyboard_bindings['grab'], ['Shift', 'j'])
        send(scene, 'Escape', True)
        send(scene, 'Escape', False)
        send(scene, 'Escape', True)
        send(scene, 'Escape', False)
        self.assertEqual(menu.page, 'menu')
        self.assertEqual(menu.items[menu.focus].action, 'controls')
        send(scene, 'Escape', True)
        send(scene, 'Escape', False)
        self.assertIsNone(scene.game_menu)
        send(scene, 'j', True)
        self.assertTrue(scene.shift_held)
        send(scene, 'j', False)
        self.assertFalse(scene.shift_held)

    def test_alt_k_opens_the_page_from_play_and_the_page_draws(self):
        scene = self.new_scene()
        with patch('pop2.window_controls.sys.platform', 'win32'):
            send(scene, 'k', True, state=0x20000)
        self.assertEqual(scene.game_menu.page, 'controls')
        self.assertFalse(scene.game_menu.return_to_menu)
        for device in ('keyboard', 'controller'):
            scene.game_menu.controls_page.switch_device(device)
            scene.render()
            self.assertEqual(scene.native_viewport.size, (512, 384))
        send(scene, 'F1', True)
        self.assertEqual(scene.game_menu.page, 'menu')


if __name__ == '__main__':
    unittest.main()
