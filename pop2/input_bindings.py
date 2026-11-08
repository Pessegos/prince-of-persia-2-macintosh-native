"""Keys and controller buttons the player chose for the game's actions.

This is a port-only feature. The original reads a fixed keyboard; the game
logic here still receives exactly the keys it always did (arrows, Shift,
Ctrl, Space, Escape, F1). A chosen key is translated into that original key
before any game rule sees it, so remapping never changes how a command acts.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Action:
    name: str
    label: str
    canonical: str            # the original key the game logic receives
    native: tuple             # physical keysyms that already are that key
    on_controller: bool = True


ACTIONS = (
    Action('left', 'Left', 'Left', ('Left',), on_controller=False),
    Action('right', 'Right', 'Right', ('Right',), on_controller=False),
    Action('up', 'Up / Jump', 'Up', ('Up',)),
    Action('down', 'Down / Crouch', 'Down', ('Down',)),
    Action('grab', 'Grab / Careful step', 'Shift_L', ('Shift_L', 'Shift_R')),
    Action('sword', 'Sword / Strike', 'Control_L', ('Control_L', 'Control_R')),
    Action('time', 'Show time left', 'space', ('space',)),
    Action('pause', 'Pause', 'Escape', ('Escape',)),
    Action('menu', 'Game menu', 'F1', ('F1',)),
)
ACTION_BY_NAME = {action.name: action for action in ACTIONS}
GAMEPLAY_ACTIONS = ('left', 'right', 'up', 'down', 'grab', 'sword', 'time')
COMMAND_ACTIONS = ('pause', 'menu')
SLOTS = 2

# Every key the game logic itself listens to during play. A physical key with
# one of these names that the player moved elsewhere must not still act.
CANONICAL_KEYS = frozenset(key for action in ACTIONS for key in action.native)

# Keys that keep their window/system meaning and cannot be chosen.
RESERVED_KEYS = frozenset({
    'Alt_L', 'Alt_R', 'Meta_L', 'Meta_R', 'Super_L', 'Super_R', 'Win_L', 'Win_R',
    'Caps_Lock', 'Num_Lock', 'Scroll_Lock', 'Print', 'Sys_Req', 'App', 'Menu',
    '??', 'NoSymbol', 'VoidSymbol',
}) | frozenset(f'F{number}' for number in range(1, 25))
# Escape and F1 always pause and open the menu, so a menu can never be lost.
LOCKED_KEYS = {'pause': 'Escape', 'menu': 'F1'}

KEYPAD_ALIASES = {
    'KP_Insert': 'KP_0', 'KP_End': 'KP_1', 'KP_Down': 'KP_2', 'KP_Next': 'KP_3',
    'KP_Left': 'KP_4', 'KP_Begin': 'KP_5', 'KP_Right': 'KP_6', 'KP_Home': 'KP_7',
    'KP_Up': 'KP_8', 'KP_Prior': 'KP_9', 'KP_Delete': 'KP_Decimal',
}


def key_token(keysym):
    """The name a physical key is saved under, independent of Shift/Num Lock."""
    if not isinstance(keysym, str) or not keysym:
        return None
    if keysym in ('Shift_L', 'Shift_R'):
        return 'Shift'
    if keysym in ('Control_L', 'Control_R'):
        return 'Control'
    if len(keysym) == 1:
        return keysym.lower()
    return KEYPAD_ALIASES.get(keysym, keysym)


def key_reserved(token):
    return (token is None or token in RESERVED_KEYS or token.startswith('XF86')
            or token.startswith('dead_'))


KEY_NAMES = {
    'Left': 'Left', 'Right': 'Right', 'Up': 'Up', 'Down': 'Down',
    'Shift': 'Shift', 'Control': 'Ctrl', 'space': 'Space', 'Return': 'Enter',
    'BackSpace': 'Backspace', 'Tab': 'Tab', 'Escape': 'Esc', 'Insert': 'Insert',
    'Delete': 'Delete', 'Home': 'Home', 'End': 'End', 'Prior': 'Page Up',
    'Next': 'Page Down', 'Pause': 'Pause', 'KP_Add': 'Num plus',
    'KP_Subtract': 'Num -', 'KP_Multiply': 'Num *', 'KP_Divide': 'Num /',
    'KP_Decimal': 'Num .', 'KP_Enter': 'Num Enter', 'comma': ',', 'period': '.',
    'minus': '-', 'slash': '/', 'semicolon': ';', 'apostrophe': "'",
    'grave': '`', 'quoteleft': '`', 'bracketleft': 'Left bracket',
    'bracketright': 'Right bracket', 'backslash': 'Backslash', 'equal': 'Equals',
    'plus': 'Plus', 'less': 'Less than', 'greater': '>', 'ccedilla': 'Ç',
    'ntilde': 'Ñ', 'masculine': 'º', 'ordfeminine': 'ª',
    'guillemotleft': '«', 'guillemotright': '»', 'numbersign': '#',
    'exclam': '!', 'quotedbl': '"', 'ampersand': '&', 'parenleft': '(',
    'parenright': ')', 'asterisk': '*', 'colon': ':', 'question': '?',
    'underscore': '_', 'percent': '%', 'egrave': 'È', 'eacute': 'É',
    'agrave': 'À', 'ugrave': 'Ù', 'odiaeresis': 'Ö',
    'adiaeresis': 'Ä', 'udiaeresis': 'Ü', 'ssharp': 'ß',
}


def key_name(token):
    """A short label for a saved key, for the Controls page."""
    if token is None:
        return ''
    if token in KEY_NAMES:
        return KEY_NAMES[token]
    if len(token) == 1:
        return token.upper()
    if token.startswith('KP_') and token[3:].isdigit():
        return 'Num ' + token[3:]
    return token.replace('_', ' ')[:1].upper() + token.replace('_', ' ')[1:]


# Controller buttons use SDL's position names: 'a' is always the bottom face
# button, whatever is printed on it.
PAD_BUTTONS = ('a', 'b', 'x', 'y', 'back', 'guide', 'start', 'leftstick', 'rightstick',
               'leftshoulder', 'rightshoulder', 'dpup', 'dpdown', 'dpleft', 'dpright',
               'misc1', 'paddle1', 'paddle2', 'paddle3', 'paddle4', 'touchpad')
PAD_TRIGGERS = ('lefttrigger', 'righttrigger')
# The D-pad and left stick always move; the guide button belongs to the system.
PAD_RESERVED = frozenset({'guide', 'dpup', 'dpdown', 'dpleft', 'dpright'})
PAD_LOCKED = {'menu': 'start'}
PAD_BINDABLE = tuple(button for button in PAD_BUTTONS + PAD_TRIGGERS
                     if button not in PAD_RESERVED)

PAD_STYLES = ('xbox', 'playstation', 'nintendo')
PAD_NAMES = {
    'xbox': {'a': 'A', 'b': 'B', 'x': 'X', 'y': 'Y', 'back': 'View', 'start': 'Menu',
             'leftshoulder': 'LB', 'rightshoulder': 'RB', 'lefttrigger': 'LT',
             'righttrigger': 'RT', 'leftstick': 'LS', 'rightstick': 'RS', 'misc1': 'Share'},
    'playstation': {'a': 'Cross', 'b': 'Circle', 'x': 'Square', 'y': 'Triangle',
                    'back': 'Create', 'start': 'Options', 'leftshoulder': 'L1',
                    'rightshoulder': 'R1', 'lefttrigger': 'L2', 'righttrigger': 'R2',
                    'leftstick': 'L3', 'rightstick': 'R3', 'misc1': 'Mic',
                    'touchpad': 'Touchpad'},
    # Positional: the bottom button of a Nintendo pad is printed B.
    'nintendo': {'a': 'B', 'b': 'A', 'x': 'Y', 'y': 'X', 'back': 'Minus', 'start': 'Plus',
                 'leftshoulder': 'L', 'rightshoulder': 'R', 'lefttrigger': 'ZL',
                 'righttrigger': 'ZR', 'leftstick': 'LS', 'rightstick': 'RS',
                 'misc1': 'Capture'},
}


def pad_name(token, style='xbox'):
    if token is None:
        return ''
    names = PAD_NAMES.get(style, PAD_NAMES['xbox'])
    if token in names:
        return names[token]
    if token.startswith('paddle'):
        return 'P' + token[6:]
    return PAD_NAMES['xbox'].get(token, token.capitalize())


KEYBOARD_DEFAULTS = {
    'left': ('Left', None), 'right': ('Right', None), 'up': ('Up', None),
    'down': ('Down', None), 'grab': ('Shift', None), 'sword': ('Control', None),
    'time': ('space', None), 'pause': ('Escape', None), 'menu': ('F1', None),
}
CONTROLLER_DEFAULTS = {
    'up': ('a', None), 'down': ('b', None), 'grab': ('rightshoulder', 'righttrigger'),
    'sword': ('x', None), 'time': ('y', None), 'pause': ('back', None),
    'menu': ('start', None),
}


class Bindings:
    """Two slots per action; one physical key or button belongs to one slot."""

    def __init__(self, kind, slots=None):
        if kind not in ('keyboard', 'controller'):
            raise ValueError('Unknown binding kind')
        self.kind = kind
        defaults = KEYBOARD_DEFAULTS if kind == 'keyboard' else CONTROLLER_DEFAULTS
        self.slots = {name: list(defaults[name]) for name in self.actions}
        if slots is not None:
            self.slots = {name: list(slots.get(name, (None, None))) for name in self.actions}

    @property
    def actions(self):
        return tuple(action.name for action in ACTIONS
                     if self.kind == 'keyboard' or action.on_controller)

    @property
    def locked(self):
        return LOCKED_KEYS if self.kind == 'keyboard' else PAD_LOCKED

    @classmethod
    def defaults(cls, kind):
        return cls(kind)

    def copy(self):
        return Bindings(self.kind, {name: tuple(slots) for name, slots in self.slots.items()})

    def __eq__(self, other):
        return isinstance(other, Bindings) and (self.kind, self.slots) == (other.kind, other.slots)

    def keys(self, action):
        return tuple(token for token in self.slots.get(action, ()) if token is not None)

    def action_for(self, token):
        return next((name for name, slots in self.slots.items() if token in slots), None)

    def slot_locked(self, action, slot):
        return slot == 0 and action in self.locked

    def valid_token(self, token):
        if self.kind == 'keyboard':
            return not key_reserved(token) and token not in LOCKED_KEYS.values()
        return token in PAD_BINDABLE and token not in PAD_LOCKED.values()

    def assign(self, action, slot, token):
        """Put a key in a slot; a key already used elsewhere swaps places."""
        if action not in self.slots or not 0 <= slot < SLOTS:
            raise ValueError('Invalid binding slot')
        if self.slot_locked(action, slot) or not self.valid_token(token):
            return False
        previous = self.slots[action][slot]
        for other, slots in self.slots.items():
            for index, existing in enumerate(slots):
                if existing == token and (other, index) != (action, slot):
                    slots[index] = previous
        self.slots[action][slot] = token
        return True

    def clear(self, action, slot):
        if action not in self.slots or self.slot_locked(action, slot):
            return False
        self.slots[action][slot] = None
        return True

    def to_saved(self):
        return {name: list(slots) for name, slots in self.slots.items()}

    @classmethod
    def from_saved(cls, kind, data):
        """Accept a saved table, repairing anything a hand edit could break."""
        bindings = cls(kind)
        if not isinstance(data, dict) or not data:
            return bindings
        chosen = cls(kind, {})
        seen = set()
        for name in chosen.actions:
            saved = data.get(name)
            saved = list(saved)[:SLOTS] if isinstance(saved, (list, tuple)) else []
            saved += [None] * (SLOTS - len(saved))
            for slot, token in enumerate(saved):
                if chosen.slot_locked(name, slot):
                    chosen.slots[name][slot] = chosen.locked[name]
                elif isinstance(token, str) and chosen.valid_token(token) and token not in seen:
                    chosen.slots[name][slot] = token
                    seen.add(token)
        return chosen
