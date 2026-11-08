"""Remappable keys, controllers and the Controls page (port-only feature)."""

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from PIL import Image

from pop2.controls_page import ControlsPage, keyboard_keys
from pop2.game_menu import GameMenu
from pop2.gamepad import Hysteresis, PadReader, PadState, pad_style
from pop2.input_bindings import (Bindings, CONTROLLER_DEFAULTS, KEYBOARD_DEFAULTS, key_name,
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
