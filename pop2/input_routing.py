"""Chosen keys and controller buttons, delivered as the game's own keys.

Every physical key or pad input that stands for a game action is turned into
the key the existing handlers already understand (an arrow, Shift, Ctrl,
Space, Escape or F1) before they see it. Pause, retry, menu and held-key
rules therefore stay exactly as they are for the keyboard. A small router
counts which physical sources hold each of those keys, so two sources for
one key (W and K, or the D-pad and the stick) release it only together.
"""

from types import SimpleNamespace
import time

from pop2.input_bindings import (ACTION_BY_NAME, CANONICAL_KEYS, COMMAND_ACTIONS, PAD_BINDABLE,
                                 PAD_LOCKED, Bindings, KEYPAD_ALIASES, key_token)


class KeyRouter:
    def __init__(self):
        self.sources = {}

    def press(self, source, key):
        """Record a source; True when it is the first one holding `key`."""
        first = key is not None and key not in self.sources.values()
        self.sources[source] = key
        return first

    def recorded(self, source):
        return source in self.sources

    def key_of(self, source):
        return self.sources.get(source)

    def release(self, source):
        """(key, last) for a recorded source; key None if it was swallowed."""
        if source not in self.sources:
            return None, False
        key = self.sources.pop(source)
        return key, key is not None and key not in self.sources.values()

    def holding(self, key):
        return [source for source, held in self.sources.items() if held == key]

    def pad_sources(self):
        return [source for source in self.sources if source.startswith('pad:')]

    def clear(self, prefix=None):
        if prefix is None:
            self.sources.clear()
        else:
            for source in [source for source in self.sources if source.startswith(prefix)]:
                del self.sources[source]


def key_source(keysym):
    """One physical key, whatever case or Num Lock state it reports."""
    if len(keysym) == 1:
        return 'key:' + keysym.lower()
    return 'key:' + KEYPAD_ALIASES.get(keysym, keysym)


# Fixed controller meanings outside play (menus, intro, cutscene replay).
PAD_MENU_KEYS = {'dpup': 'Up', 'stickup': 'Up', 'dpdown': 'Down', 'stickdown': 'Down',
                 'dpleft': 'Left', 'stickleft': 'Left', 'dpright': 'Right',
                 'stickright': 'Right', 'a': 'Return', 'b': 'Escape', 'start': 'F1',
                 'leftshoulder': 'Prior', 'rightshoulder': 'Next'}
PAD_DIRECTIONS = {'dpup': 'Up', 'stickup': 'Up', 'dpdown': 'Down', 'stickdown': 'Down',
                  'dpleft': 'Left', 'stickleft': 'Left', 'dpright': 'Right',
                  'stickright': 'Right'}
PAD_INTRO_KEYS = {'a': 'space', 'b': 'space', 'x': 'space', 'y': 'space', 'start': 'F1',
                  'back': 'Escape'}
PAD_REPLAY_KEYS = {'a': 'Escape', 'b': 'BackSpace', 'back': 'Escape', 'start': 'F1'}
# Modifiers reach the game before directions pressed in the same poll, as
# the keyboard restore order does (mac_input chords).
PRESS_ORDER = {'Shift_L': 0, 'Control_L': 0, 'Up': 1, 'Down': 1, 'Left': 2, 'Right': 2}
MENU_REPEAT_DELAY = 0.35
MENU_REPEAT_INTERVAL = 0.08


class InputRouting:
    """Mixed into WindowControls; needs its key handlers and menu state."""

    # -- shared state ---------------------------------------------------
    @property
    def key_router(self):
        router = self.__dict__.get('_key_router')
        if router is None:
            router = self.__dict__['_key_router'] = KeyRouter()
        return router

    @property
    def keyboard_bindings(self):
        bindings = self.__dict__.get('_keyboard_bindings')
        if bindings is None:
            bindings = self.__dict__['_keyboard_bindings'] = Bindings('keyboard')
        return bindings

    @keyboard_bindings.setter
    def keyboard_bindings(self, bindings):
        self.__dict__['_keyboard_bindings'] = bindings

    @property
    def controller_bindings(self):
        bindings = self.__dict__.get('_controller_bindings')
        if bindings is None:
            bindings = self.__dict__['_controller_bindings'] = Bindings('controller')
        return bindings

    @controller_bindings.setter
    def controller_bindings(self, bindings):
        self.__dict__['_controller_bindings'] = bindings

    def controls_page(self):
        menu = getattr(self, 'game_menu', None)
        return getattr(menu, 'controls_page', None) if getattr(menu, 'page', None) == 'controls' else None

    def input_context(self):
        if getattr(self, 'cutscene_replay', None) is not None:
            return 'replay'
        menu = getattr(self, 'game_menu', None)
        if menu is not None:
            page = self.controls_page()
            if page is not None and page.listening is not None:
                return 'listening'
            page_name = getattr(menu, 'page', None)
            gallery = getattr(menu, 'screenshot_gallery', None)
            if ((page_name == 'saves' and getattr(getattr(menu, 'save_browser', None), 'editing', False))
                    or (page_name == 'screenshots' and getattr(gallery, 'choosing', False))):
                return 'text'
            return 'menu'
        if getattr(self, 'dev_menu', None) is not None:
            return 'dev'
        if getattr(self, 'copy_challenge', None) is not None:
            return 'copy'
        if getattr(self, 'intro', None) is not None or getattr(self, 'demo', None) is not None:
            return 'intro'
        return 'gameplay'

    # -- keyboard -------------------------------------------------------
    def routed_key(self, event, context):
        """The original key a physical key stands for here: (key, routed).

        routed is False for keys that pass through untouched; key None with
        routed True swallows a moved original key during play.
        """
        keysym = event.keysym
        if context in ('text', 'dev', 'listening') or self.alt_held(event):
            return keysym, False
        action = self.keyboard_bindings.action_for(key_token(keysym))
        if action is not None and (context == 'gameplay' or action in COMMAND_ACTIONS):
            definition = ACTION_BY_NAME[action]
            return (keysym if keysym in definition.native else definition.canonical), True
        if context == 'gameplay' and keysym in CANONICAL_KEYS:
            return None, True
        return keysym, False

    def alt_held(self, event):
        from pop2.window_controls import alt_pressed

        return alt_pressed(event, getattr(self, 'window_keys_down', ()))

    def synthetic_key(self, keysym, event=None):
        return SimpleNamespace(
            keysym=keysym, state=getattr(event, 'state', 0),
            char={'space': ' ', 'Return': '\r'}.get(keysym, ''), keycode=None,
            widget=getattr(event, 'widget', None), synthetic=True)

    def note_input_device(self, device):
        self.__dict__['last_input_device'] = device
        page = self.controls_page()
        if page is not None:
            page.input_device = device

    def dev_key_press(self, event):
        self.note_input_device('keyboard')
        context = self.input_context()
        source = key_source(event.keysym)
        router = self.key_router
        if context == 'listening':
            page = self.controls_page()
            if not router.recorded(source) and (page.device == 'keyboard' or event.keysym == 'Escape'):
                # The chosen key stays inert until released, so its
                # autorepeat cannot also act on the page (Enter, say).
                router.press(source, None)
                self.apply_game_action(page.capture_key(event.keysym))
            return 'break'
        if router.recorded(source):
            if context == 'text':
                return 'break'
            key, routed = router.key_of(source), True
        else:
            key, routed = self.routed_key(event, context)
        if not routed:
            return self.key_press_unrouted(event)
        router.press(source, key)
        if key is None:
            return 'break'
        if key == event.keysym:
            return self.key_press_unrouted(event)
        return self.deliver_key(key, True, event)

    def dev_key_release(self, event):
        source = key_source(event.keysym)
        router = self.key_router
        if not router.recorded(source):
            return self.key_release_unrouted(event)
        key, last = router.release(source)
        if key is None or not last:
            return 'break'
        if key == event.keysym:
            return self.key_release_unrouted(event)
        return self.deliver_key(key, False, event)

    def deliver_key(self, key, pressed, event=None):
        """Hand an original key to the same handlers a real key reaches."""
        synthetic = self.synthetic_key(key, event)
        result = (self.key_press_unrouted if pressed else self.key_release_unrouted)(synthetic)
        if result is None:
            self.run_key_binding(key, pressed, synthetic)
        return 'break'

    def run_key_binding(self, keysym, pressed, event):
        """The window's own gameplay bindings, shared with create_window."""
        if keysym in ('Left', 'Right'):
            return self.horizontal_key(event, -1 if keysym == 'Left' else 1, pressed)
        if keysym == 'Up':
            return self.up_key(event) if pressed else self.set_key_state('up', False)
        if keysym == 'Down':
            return self.set_key_state('down', pressed)
        if keysym in ('Shift_L', 'Shift_R'):
            return self.set_key_state('shift', pressed)
        if keysym in ('Control_L', 'Control_R'):
            return self.set_key_state('ctrl', pressed)
        if keysym == 'Escape':
            return self.escape_key(event) if pressed else self.escape_release(event)
        return None

    def forget_routed_keys(self):
        """Focus loss: every hold is gone, so are the router's records."""
        self.key_router.clear()
        self.__dict__['pad_suppressed'] = set(self.__dict__.get('pad_held', ()))
        self.__dict__['pad_repeat'] = {}

    # -- controllers ----------------------------------------------------
    def pad_key(self, name, context):
        if context in ('menu', 'text', 'copy', 'dev'):
            if name in ('a', 'b') or name in PAD_DIRECTIONS:
                return PAD_MENU_KEYS[name]
            if name == 'x' and self.controls_page() is not None:
                return 'Delete'
            action = self.controller_bindings.action_for(name)
            if action == 'pause':
                return 'Escape'
            if action == 'menu':
                return 'F1'
            return PAD_MENU_KEYS.get(name)
        if context == 'intro':
            return PAD_INTRO_KEYS.get(name)
        if context == 'replay':
            return PAD_REPLAY_KEYS.get(name)
        if name in PAD_DIRECTIONS:
            return PAD_DIRECTIONS[name]
        action = self.controller_bindings.action_for(name)
        return ACTION_BY_NAME[action].canonical if action is not None else None

    def process_pad_input(self, held, now=None, foreground=True):
        """Edges between two pad snapshots, as presses of original keys."""
        now = time.perf_counter() if now is None else now
        state = self.__dict__
        previous = state.get('pad_held', frozenset())
        suppressed = state.setdefault('pad_suppressed', set())
        repeat = state.setdefault('pad_repeat', {})
        state['pad_held'] = held = frozenset(held)
        suppressed &= held
        if not foreground:
            suppressed |= held
            return
        router = self.key_router
        released = previous - held
        for name in sorted(released, key=lambda name: (
                -PRESS_ORDER.get(router.key_of('pad:' + name), 3), name)):
            repeat.pop(name, None)
            source = 'pad:' + name
            if router.recorded(source):
                self.release_pad_source(source)
        pressed = held - previous - suppressed
        context = self.input_context()
        if context == 'listening':
            page = self.controls_page()
            for name in sorted(pressed):
                suppressed.add(name)
                if page.device == 'controller' and (name in PAD_BINDABLE or name in PAD_LOCKED.values()):
                    self.apply_game_action(page.capture_pad(name))
                    break
                if name in ('b', 'start') and page.device == 'keyboard':
                    self.apply_game_action(page.capture_key('Escape'))
                    break
            return
        presses = []
        if pressed:
            self.note_input_device('pad')
        for name in pressed:
            key = self.pad_key(name, context)
            if key is not None:
                presses.append((PRESS_ORDER.get(key, 3), name, key))
        for _order, name, key in sorted(presses):
            source = 'pad:' + name
            router.press(source, key)
            if context in ('menu', 'text', 'copy', 'dev') and name in PAD_DIRECTIONS:
                repeat[name] = now + MENU_REPEAT_DELAY
            self.deliver_key(key, True)
            if self.input_context() != context:
                # A press that opened or closed a menu ends this poll's chord.
                for _later, rest, _key in sorted(presses):
                    if rest != name and not router.recorded('pad:' + rest):
                        suppressed.add(rest)
                break
        for name, due in list(repeat.items()):
            if name not in held or self.input_context() not in ('menu', 'text', 'copy', 'dev'):
                repeat.pop(name, None)
            elif now >= due:
                repeat[name] = now + MENU_REPEAT_INTERVAL
                key = self.key_router.key_of('pad:' + name)
                if key is not None:
                    self.deliver_key(key, True)

    def release_pad_source(self, source):
        key, last = self.key_router.release(source)
        if key is not None and last:
            self.deliver_key(key, False)

    def release_all_pad_inputs(self):
        for source in self.key_router.pad_sources():
            self.release_pad_source(source)
        self.__dict__['pad_repeat'] = {}
