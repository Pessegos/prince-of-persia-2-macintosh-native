"""The Controls page of the game menu: what each key and button does.

Port-only. The overview draws the keyboard or the controller with each
action's keys lit; the remap view lists two keys per action. It edits the
window's live Bindings, so a change works at once; the window keeps it.
"""

import sys

from PIL import Image, ImageDraw

from pop2.bitmap_labels import label_text
from pop2 import menu_theme
from pop2.menu_theme import c
from pop2.controls_art import (INK, PAD_HEIGHT, PAD_WIDTH, XBOX_COLORS, button_icon, draw_leds,
                               key_top, keyboard_case, keycap, legend_ink, pad_art, windows_flag)
from pop2.game_ui import DevelopmentMenu, centered_panel
from pop2.input_bindings import ACTION_BY_NAME, LOCKED_KEYS, PAD_LOCKED, key_name, key_token, pad_name

GOLD, WHITE, MUTED, ERROR = '#f4d873', '#eeeeee', '#999999', '#ff9b9b'
# Jump, Crouch, Sword and Time left take the Xbox colours of their default
# buttons (A, B, X, Y); Move takes the friezes' turquoise.
ACTION_COLORS = {
    'left': (82, 181, 189), 'right': (82, 181, 189), 'up': XBOX_COLORS['a'], 'down': XBOX_COLORS['b'],
    'grab': (232, 128, 52), 'sword': XBOX_COLORS['x'], 'time': XBOX_COLORS['y'], 'pause': (156, 118, 214),
    'menu': (214, 128, 176),
}
LEGEND = (('Move', ('left', 'right')), ('Up / Jump', ('up',)), ('Down / Crouch', ('down',)),
          ('Grab / Step', ('grab',)), ('Sword / Strike', ('sword',)), ('Time left', ('time',)),
          ('Pause', ('pause',)), ('Game menu', ('menu',)))

# 3x5 pixel letters for keycaps and small button labels (NFNT is too tall).
MINI = {
    'A': '.#.|#.#|###|#.#|#.#', 'B': '##.|#.#|##.|#.#|##.', 'C': '.##|#..|#..|#..|.##',
    'D': '##.|#.#|#.#|#.#|##.', 'E': '###|#..|##.|#..|###', 'F': '###|#..|##.|#..|#..',
    'G': '.##|#..|#.#|#.#|.##', 'H': '#.#|#.#|###|#.#|#.#', 'I': '###|.#.|.#.|.#.|###',
    'J': '..#|..#|..#|#.#|.#.', 'K': '#.#|#.#|##.|#.#|#.#', 'L': '#..|#..|#..|#..|###',
    'M': '#.#|###|###|#.#|#.#', 'N': '#..#|##.#|#.##|#..#|#..#',
    'O': '.#.|#.#|#.#|#.#|.#.', 'P': '##.|#.#|##.|#..|#..', 'Q': '.#.|#.#|#.#|##.|.##',
    'R': '##.|#.#|##.|#.#|#.#', 'S': '.##|#..|.#.|..#|##.', 'T': '###|.#.|.#.|.#.|.#.',
    'U': '#.#|#.#|#.#|#.#|###', 'V': '#.#|#.#|#.#|#.#|.#.', 'W': '#.#|#.#|#.#|###|#.#',
    'X': '#.#|#.#|.#.|#.#|#.#', 'Y': '#.#|#.#|.#.|.#.|.#.', 'Z': '###|..#|.#.|#..|###',
    '0': '###|#.#|#.#|#.#|###', '1': '.#.|##.|.#.|.#.|###', '2': '##.|..#|.#.|#..|###',
    '3': '##.|..#|.#.|..#|##.', '4': '#.#|#.#|###|..#|..#', '5': '###|#..|##.|..#|##.',
    '6': '.##|#..|###|#.#|###', '7': '###|..#|.#.|.#.|.#.', '8': '###|#.#|###|#.#|###',
    '9': '###|#.#|###|..#|##.', '-': '...|...|###|...|...', '=': '...|###|...|###|...',
    '[': '##|#.|#.|#.|##', ']': '##|.#|.#|.#|##', '\\': '#..|#..|.#.|..#|..#',
    ';': '..|.#|..|.#|#.', "'": '#|#|.|.|.', ',': '..|..|..|.#|#.', '.': '.|.|.|.|#',
    '/': '..#|..#|.#.|#..|#..', '`': '#.|.#|..|..|..', '+': '...|.#.|###|.#.|...',
    '*': '...|#.#|.#.|#.#|...',
    ' ': '..|..|..|..|..',
}


def mini_width(text):
    widths = [len(MINI[char].split('|')[0]) for char in text.upper() if char in MINI]
    return sum(widths) + len(widths) - 1


def mini_text(draw, x, y, text, fill, align='left'):
    glyphs = [MINI[char] for char in text.upper() if char in MINI]
    width = sum(len(shape.split('|')[0]) + 1 for shape in glyphs) - 1
    if align == 'center':
        x -= width // 2
    elif align == 'right':
        x -= width
    for shape in glyphs:
        rows = shape.split('|')
        for row, line in enumerate(rows):
            for column, cell in enumerate(line):
                if cell == '#':
                    draw.point((x + column, y + row), fill=fill)
        x += len(rows[0]) + 1
    return width


# -- keyboard drawing ---------------------------------------------------
def _letters(text):
    return [(char, char.upper(), 1) for char in text]


KEYBOARD_ROWS = (
    [('Escape', 'ESC', 1), (None, '', 1)] + [(f'F{n}', f'F{n}', 1) for n in range(1, 5)]
    + [(None, '', .5)] + [(f'F{n}', f'F{n}', 1) for n in range(5, 9)] + [(None, '', .5)]
    + [(f'F{n}', f'F{n}', 1) for n in range(9, 13)],
    [('grave', '`', 1)] + _letters('1234567890') + [('minus', '-', 1), ('equal', '=', 1),
                                                    ('BackSpace', 'BACK', 2)],
    [('Tab', 'TAB', 1.5)] + _letters('qwertyuiop') + [('bracketleft', '[', 1),
                                                     ('bracketright', ']', 1), ('backslash', '\\', 1.5)],
    [('Caps_Lock', 'CAPS', 1.75)] + _letters('asdfghjkl') + [('semicolon', ';', 1),
                                                            ('apostrophe', "'", 1), ('Return', 'ENTER', 2.25)],
    [('Shift', 'SHIFT', 2.25)] + _letters('zxcvbnm') + [('comma', ',', 1), ('period', '.', 1),
                                                       ('slash', '/', 1), ('Shift', 'SHIFT', 2.75)],
    [('Control', 'CTRL', 1.25), ('Win_L', 'WIN', 1.25), ('Alt_L', 'ALT', 1.25), ('space', '', 6.25),
     ('Alt_R', 'ALT', 1.25), ('Win_R', 'WIN', 1.25), ('App', 'MENU', 1.25), ('Control', 'CTRL', 1.25)],
)
# '|' starts a second line of legend.
NAV_ROWS = ((('Print', 'PRT|SCR'), ('Scroll_Lock', 'SCR|LCK'), ('Pause', 'PAU|BRK')),
            (('Insert', 'INS'), ('Home', 'HOME'), ('Prior', 'PG|UP')),
            (('Delete', 'DEL'), ('End', 'END'), ('Next', 'PG|DN')), (),
            ((None, ''), ('Up', '^'), (None, '')), (('Left', '<'), ('Down', 'v'), ('Right', '>')))
# The numeric keypad: (token, label, column, row, width, height) in keys.
KEYPAD = (('Num_Lock', 'NUM', 0, 1, 1, 1), ('KP_Divide', '/', 1, 1, 1, 1),
          ('KP_Multiply', '*', 2, 1, 1, 1), ('KP_Subtract', '-', 3, 1, 1, 1),
          ('KP_7', '7', 0, 2, 1, 1), ('KP_8', '8', 1, 2, 1, 1), ('KP_9', '9', 2, 2, 1, 1),
          ('KP_Add', '+', 3, 2, 1, 2), ('KP_4', '4', 0, 3, 1, 1), ('KP_5', '5', 1, 3, 1, 1),
          ('KP_6', '6', 2, 3, 1, 1), ('KP_1', '1', 0, 4, 1, 1), ('KP_2', '2', 1, 4, 1, 1),
          ('KP_3', '3', 2, 4, 1, 1), ('KP_Enter', 'ENT', 3, 4, 1, 2), ('KP_0', '0', 0, 5, 2, 1),
          ('KP_Decimal', '.', 2, 5, 1, 1))
NAV_X, KEYPAD_X = 15.25, 18.5  # where the two right-hand blocks start, in keys
# Light keys, as on the office keyboards of the 1990s; the rest are darker.
LIGHT_KEYS = frozenset([*'abcdefghijklmnopqrstuvwxyz0123456789', 'grave', 'minus', 'equal',
                        'bracketleft', 'bracketright', 'backslash', 'semicolon', 'apostrophe',
                        'comma', 'period', 'slash', 'space', 'KP_Decimal',
                        *(f'F{n}' for n in range(1, 13)), *(f'KP_{n}' for n in range(10))])
# Keys that sit where a US key is drawn on common European layouts.
POSITION_ALIASES = {'ccedilla': 'semicolon', 'ntilde': 'semicolon', 'odiaeresis': 'semicolon',
                    'masculine': 'grave'}


# Keys sit a pixel apart, as on the old office keyboards; the function keys
# stand a little apart from the rest.
KEY_HEIGHT, KEY_PITCH, FUNCTION_GAP = 16, 17, 5


def keyboard_keys(origin, unit):
    """(token, label, rect) for every drawn key."""
    left, top = origin

    def rect(x, row, width=1, height=1):
        y = top + row * KEY_PITCH + (FUNCTION_GAP if row else 0)
        return (left + round(x * unit), y,
                left + round((x + width) * unit) - 2, y + (height - 1) * KEY_PITCH + KEY_HEIGHT - 1)

    keys = []
    for row, entries in enumerate(KEYBOARD_ROWS):
        units = 0.0
        for token, label, width in entries:
            if token is not None:
                keys.append((token, label, rect(units, row, width)))
            units += width
        for column, (token, label) in enumerate(NAV_ROWS[row]):
            if token is not None:
                keys.append((token, label, rect(NAV_X + column, row)))
    for token, label, column, row, width, height in KEYPAD:
        keys.append((token, label, rect(KEYPAD_X + column, row, width, height)))
    return keys


def led_rect(origin, unit):
    """Where the lock lights sit: above the keypad."""
    left, top = origin
    return (left + round(KEYPAD_X * unit), top, left + round((KEYPAD_X + 4) * unit) - 2,
            top + KEY_HEIGHT - 1)


def draw_arrow(draw, cx, cy, direction, fill):
    points = {'^': ((cx, cy - 2), (cx - 3, cy + 1), (cx + 3, cy + 1)),
              'v': ((cx, cy + 2), (cx - 3, cy - 1), (cx + 3, cy - 1)),
              '<': ((cx - 2, cy), (cx + 1, cy - 3), (cx + 1, cy + 3)),
              '>': ((cx + 2, cy), (cx - 1, cy - 3), (cx - 1, cy + 3))}[direction]
    draw.polygon(points, fill=fill)


def draw_keycap(image, rect, token, label, color=None):
    left, top, right, bottom = rect
    dark = token not in LIGHT_KEYS
    image.alpha_composite(keycap(right - left + 1, bottom - top + 1, color, dark), (left, top))
    draw = ImageDraw.Draw(image)
    ink = legend_ink(color, dark)
    centre = ((left + right) // 2, (top + bottom - 4) // 2)
    if label in ('^', 'v', '<', '>'):
        draw_arrow(draw, *centre, label, ink)
    elif label == 'WIN':
        windows_flag(image, centre, ink, key_top(color, dark))
    else:
        # Legends sit at the top left, as printed on those keyboards; one
        # too wide for that margin is centred instead.
        lines = label.split('|') if label else []
        for line, text in enumerate(lines):
            inset = 3 if mini_width(text) + 3 <= right - left - 1 else 1
            mini_text(draw, left + inset, top + (1 if len(lines) > 1 else 2) + 6 * line, text, ink)


# The case's border round the keys: left, top, right and a deeper bottom.
KEYBOARD_MARGIN = (9, 9, 9, 12)


def keyboard_bounds(origin, unit):
    rects = [rect for _token, _label, rect in keyboard_keys(origin, unit)]
    left, top, right, bottom = KEYBOARD_MARGIN
    return (min(rect[0] for rect in rects) - left, min(rect[1] for rect in rects) - top,
            max(rect[2] for rect in rects) + right, max(rect[3] for rect in rects) + bottom)


# The lock lights and the Windows virtual keys whose toggle they show.
LOCK_KEYS = (('NUM', 0x90), ('CAPS', 0x14), ('SCRL', 0x91))


def lock_lights():
    """The lock lights the real keyboard shows now, or None where they
    cannot be read (then the drawing keeps Num Lock alone lit)."""
    if sys.platform != 'win32':
        return None
    try:
        import ctypes

        state = ctypes.windll.user32.GetKeyState
        return frozenset(name for name, code in LOCK_KEYS if state(code) & 1)
    except (AttributeError, OSError):
        return None


def draw_keyboard(image, origin, unit, token_colors, lit=('NUM',)):
    left, top, right, bottom = keyboard_bounds(origin, unit)
    keys = keyboard_keys(origin, unit)
    holes = tuple((x0 - left, y0 - top, x1 - left, y1 - top) for _token, _label, (x0, y0, x1, y1) in keys)
    image.alpha_composite(keyboard_case(right - left + 1, bottom - top + 1, holes), (left, top))
    for token, label, rect in keys:
        draw_keycap(image, rect, token, label, token_colors.get(token))
    draw_leds(image, led_rect(origin, unit), lit)


# -- controller drawing -------------------------------------------------
SHORT_LABELS = {'left': 'Move', 'right': 'Move', 'up': 'Jump', 'down': 'Crouch', 'grab': 'Grab',
                'sword': 'Sword', 'time': 'Time left', 'pause': 'Pause', 'menu': 'Menu'}
LINE = (132, 130, 128)  # over the panel; over a light shell the finish's ink
# Where each side's brackets stand, from the pad's left edge, and how wide
# a label may be beside its icon.
BRACKET_X = {'left': -6, 'right': PAD_WIDTH + 5}
LABEL_WIDTH = 76


def line_pixels(points):
    """Every pixel of a polyline, in order (one per step, no doubles)."""
    pixels = []
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        x0, y0, x1, y1 = round(x0), round(y0), round(x1), round(y1)
        steps = max(abs(x1 - x0), abs(y1 - y0), 1)
        for step in range(steps + 1):
            pixel = (round(x0 + (x1 - x0) * step / steps), round(y0 + (y1 - y0) * step / steps))
            if not pixels or pixels[-1] != pixel:
                pixels.append(pixel)
    return pixels


def draw_callout(image, points, art, origin):
    """A one-pixel leader line, dark where it crosses a light shell."""
    pad = art.image
    ink = INK
    for x, y in line_pixels(points):
        px, py = x - origin[0], y - origin[1]
        over = (0 <= px < pad.width and 0 <= py < pad.height) and pad.getpixel((px, py))
        light = over and over[3] and sum(over[:3]) > 330
        if 0 <= x < image.width and 0 <= y < image.height:
            image.putpixel((x, y), (*(ink if light else LINE), 255))


class ControlsPage:
    PANEL = centered_panel(470, 350)
    TABS = ((150, 38, 252, 60), (260, 38, 362, 60))
    BUTTONS = ((100, 318, 250, 344), (262, 318, 412, 344))
    # Its label is centred under the status line; the check box stands to the left of it.
    TOGGLE = (169, 286, 325, 304)
    ROW_TOP = 52
    ROW_HEIGHT = 22
    SLOT_X = ((232, 344), (352, 464))
    KEYBOARD_ORIGIN = (54, 83)   # the free height is shared: tabs, keyboard, legend, buttons
    KEYBOARD_UNIT = 18
    LEGEND_X = (103, 291)
    LEGEND_TOP = 220
    LEGEND_ROW = 22
    PAD_ORIGIN = (256 - PAD_WIDTH // 2, 89)

    def __init__(self, keyboard, controller, pads=(), controller_enabled=True,
                 controller_available=True, return_to_menu=True):
        self.keyboard = keyboard
        self.controller = controller
        self.pads = tuple(pads)
        self.controller_enabled = controller_enabled
        self.controller_available = controller_available
        self.return_to_menu = return_to_menu
        self.device = 'keyboard'
        self.view = 'overview'
        self.focus = 0
        self.listening = None
        self.message = ''
        self.message_error = False
        self.input_device = 'keyboard'
        self.locks = frozenset(('NUM',))

    def refresh_locks(self, read=None):
        """Follow the real keyboard's lock lights; True if they changed."""
        locks = (read or lock_lights)()
        if locks is None or locks == self.locks:
            return False
        self.locks = locks
        return True

    # -- model ----------------------------------------------------------
    @property
    def bindings(self):
        return self.keyboard if self.device == 'keyboard' else self.controller

    @property
    def style(self):
        return self.pads[0].style if self.pads else 'xbox'

    def controls(self):
        """Focusable controls of the current view, in Tab order."""
        if self.view == 'overview':
            return ['tab_keyboard', 'tab_controller'] + (
                ['toggle'] if self.device == 'controller' else []) + ['change', 'back']
        return [('slot', action, slot) for action in self.bindings.actions
                for slot in range(2)] + ['defaults', 'back']

    @property
    def focused(self):
        controls = self.controls()
        return controls[min(self.focus, len(controls) - 1)]

    def name(self, token):
        return key_name(token) if self.device == 'keyboard' else pad_name(token, self.style)

    def switch_device(self, device):
        if device == self.device:
            return 'changed'
        self.device = device
        self.listening = None
        self.message = ''
        controls = self.controls()
        if self.view == 'overview':
            self.focus = controls.index('tab_' + device)
        else:
            self.focus = min(self.focus, len(controls) - 1)
        return 'changed'

    def say(self, message, error=False):
        self.message, self.message_error = message, error

    # -- input ----------------------------------------------------------
    def activate(self):
        control = self.focused
        if control in ('tab_keyboard', 'tab_controller'):
            return self.switch_device(control[4:])
        if control == 'toggle':
            self.controller_enabled = not self.controller_enabled
            return 'controller_toggle'
        if control == 'change':
            self.view = 'remap'
            self.focus = 0
            self.message = ''
            return 'changed'
        if control == 'back':
            return self.back()
        if control == 'defaults':
            restored = type(self.bindings).defaults(self.bindings.kind)
            self.bindings.slots = restored.slots
            self.say('Default keys restored' if self.device == 'keyboard'
                     else 'Default buttons restored')
            return 'controls_saved'
        _kind, action, slot = control
        if self.bindings.slot_locked(action, slot):
            locked = (LOCKED_KEYS if self.device == 'keyboard' else PAD_LOCKED)[action]
            self.say(f'{self.name(locked)} always {"pauses" if action == "pause" else "opens this menu"}')
            return 'changed'
        self.listening = (action, slot)
        self.message = ''
        return 'changed'

    def back(self):
        self.listening = None
        if self.view == 'remap':
            self.view = 'overview'
            self.message = ''
            self.focus = self.controls().index('change')
            return 'changed'
        return 'controls_back'

    def key(self, key, backwards=False, char='', control=False):
        if key == 'Escape':
            return self.back()
        if key in ('Prior', 'Next'):
            return self.switch_device('keyboard' if key == 'Prior' else 'controller')
        if key == 'Tab':
            self.focus = (self.focus + (-1 if backwards else 1)) % len(self.controls())
            return 'changed'
        if key in ('Return', 'KP_Enter', 'space'):
            return self.activate()
        if self.view == 'overview':
            return self.overview_key(key)
        return self.remap_key(key)

    def overview_key(self, key):
        controls = self.controls()
        control = self.focused
        if key in ('Left', 'Right') and control in ('tab_keyboard', 'tab_controller'):
            return self.switch_device('keyboard' if key == 'Left' else 'controller')
        if key in ('Left', 'Right') and control in ('change', 'back'):
            self.focus = controls.index('change' if key == 'Left' else 'back')
        elif key in ('Up', 'Down'):
            rows = [['tab_keyboard', 'tab_controller']] + (
                [['toggle']] if 'toggle' in controls else []) + [['change', 'back']]
            row = next(i for i, items in enumerate(rows) if control in items)
            column = rows[row].index(control)
            row = (row + (-1 if key == 'Up' else 1)) % len(rows)
            if rows[row] == ['tab_keyboard', 'tab_controller']:
                target = 'tab_' + self.device
            else:
                target = rows[row][min(column, len(rows[row]) - 1)]
            self.focus = controls.index(target)
        return 'changed'

    def remap_key(self, key):
        controls = self.controls()
        control = self.focused
        actions = self.bindings.actions
        if key in ('Delete', 'BackSpace') and isinstance(control, tuple):
            _kind, action, slot = control
            if self.bindings.clear(action, slot):
                self.message = ''
                return 'controls_saved'
            return self.activate()
        if isinstance(control, tuple):
            _kind, action, slot = control
            row = actions.index(action)
        else:
            row, slot = len(actions), 0 if control == 'defaults' else 1
        if key in ('Left', 'Right'):
            slot = 0 if key == 'Left' else 1
        elif key in ('Up', 'Down'):
            row = (row + (-1 if key == 'Up' else 1)) % (len(actions) + 1)
        else:
            return 'changed'
        self.focus = (controls.index(('slot', actions[row], slot)) if row < len(actions)
                      else controls.index('defaults' if slot == 0 else 'back'))
        return 'changed'

    def capture_key(self, keysym):
        """The key pressed while a keyboard slot waits for one."""
        if self.listening is None:
            return 'changed'
        action, slot = self.listening
        self.listening = None
        if keysym == 'Escape':
            self.message = ''
            return 'changed'
        return self.capture(action, slot, key_token(keysym))

    def capture_pad(self, token):
        if self.listening is None:
            return 'changed'
        action, slot = self.listening
        self.listening = None
        if self.device != 'controller' or token == 'start':
            self.message = ''
            return 'changed'
        return self.capture(action, slot, token)

    def capture(self, action, slot, token):
        bindings = self.bindings
        before = {name: list(slots) for name, slots in bindings.slots.items()}
        if not bindings.assign(action, slot, token):
            self.say(f'{self.name(token) or "That key"} is kept for the window'
                     if self.device == 'keyboard' else f'{self.name(token)} cannot be used', True)
            return 'changed'
        moved = [name for name, slots in bindings.slots.items()
                 if name != action and slots != before[name]]
        self.say(f'Swapped with {ACTION_BY_NAME[moved[0]].label}' if moved else '')
        return 'controls_saved'

    # -- pointer --------------------------------------------------------
    def row_top(self):
        """The remap rows, centred where the nine keyboard rows sit."""
        return self.ROW_TOP + (9 - len(self.bindings.actions)) * self.ROW_HEIGHT // 2

    def control_rect(self, control):
        if control in ('tab_keyboard', 'tab_controller'):
            return self.TABS[0 if control == 'tab_keyboard' else 1]
        if control == 'toggle':
            return self.TOGGLE
        if control == 'change':
            return self.BUTTONS[0]
        if control == 'defaults':
            return self.BUTTONS[0]
        if control == 'back':
            return self.BUTTONS[1]
        _kind, action, slot = control
        top = self.row_top() + self.bindings.actions.index(action) * self.ROW_HEIGHT
        left, right = self.SLOT_X[slot]
        return left, top, right, top + self.ROW_HEIGHT - 3

    def hit(self, x, y):
        return next((index for index, control in enumerate(self.controls())
                     if DevelopmentMenu.contains(self.control_rect(control), x, y)), None)

    def hover(self, x, y):
        index = self.hit(x, y)
        if index is None or index == self.focus or self.listening is not None:
            return False
        self.focus = index
        return True

    def click(self, x, y):
        index = self.hit(x, y)
        if self.listening is not None:
            self.listening = None
            return 'changed'
        if index is None:
            return 'changed'
        self.focus = index
        return self.activate()

    # -- drawing --------------------------------------------------------
    def draw(self, viewport, font):
        image = Image.alpha_composite(viewport, Image.new('RGBA', viewport.size, (0, 0, 0, menu_theme.current().dim)))
        draw = ImageDraw.Draw(image)

        def text(value, x, y, color=c(WHITE), align='left', max_width=None):
            glyphs = label_text(font, value, color)
            if max_width is not None and glyphs.width > max_width:
                glyphs = glyphs.resize((max_width, glyphs.height), Image.Resampling.NEAREST)
            ink = glyphs.getbbox()
            if align == 'center':
                x -= glyphs.width // 2
            elif align == 'right':
                x -= glyphs.width
            image.paste(glyphs, (x, y - (ink[1] if ink else 0)), glyphs)

        def button(rect, label, selected, color=c(WHITE)):
            draw.rectangle(rect, fill=c('#303030') if selected else c('#222222'),
                           outline=c(GOLD) if selected else c('#626262'))
            text(label, (rect[0] + rect[2]) // 2, rect[1] + (rect[3] - rect[1]) // 2 - 4,
                 color, 'center', rect[2] - rect[0] - 12)

        menu_theme.panel(image, self.PANEL, clear_sides=True)  # labels reach the panel's sides
        draw = ImageDraw.Draw(image)
        focused = self.focused
        if self.view == 'overview':
            text('Controls', 256, self.PANEL[1] + 12, c(GOLD), 'center')
            for rect, device, label in zip(self.TABS, ('keyboard', 'controller'),
                                           ('Keyboard', 'Controller')):
                chosen = device == self.device
                draw.rectangle(rect, fill=c('#303030') if chosen else c('#1c1c1c'),
                               outline=c(GOLD) if focused == 'tab_' + device else
                               c('#8a8a8a') if chosen else c('#4a4a4a'))
                text(label, (rect[0] + rect[2]) // 2, rect[1] + 7,
                     c(GOLD) if chosen else c(MUTED), 'center')
            if self.device == 'keyboard':
                self.draw_keyboard_overview(image, draw, text)
                button(self.BUTTONS[0], 'Change keys...', focused == 'change')
            else:
                self.draw_controller_overview(image, draw, text)
                left, top, right, bottom = self.TOGGLE
                selected = focused == 'toggle'
                draw.rectangle(self.TOGGLE, fill=c('#303030') if selected else c('#181818'),
                               outline=c(GOLD) if selected else c('#181818'))
                draw.rectangle((left + 6, top + 4, left + 16, top + 14), fill=c('#121212'), outline=c(MUTED))
                if self.controller_enabled:
                    draw.line(((left + 8, top + 9), (left + 10, top + 12), (left + 14, top + 6)),
                              fill=c(GOLD), width=2)
                text('Use controller', (left + right) // 2 + 9, top + 5, align='center')
                button(self.BUTTONS[0], 'Change buttons...', focused == 'change')
            button(self.BUTTONS[1], 'Back' if self.return_to_menu else 'Close', focused == 'back')
        else:
            self.draw_remap(image, draw, text, button, lambda value: label_text(font, value, c(WHITE)).width)
        menu_theme.watermark(image, self.PANEL)
        return image

    def keyboard_colors(self):
        colors = {}
        for action in self.keyboard.actions:
            for token in self.keyboard.keys(action):
                colors[POSITION_ALIASES.get(token, token)] = ACTION_COLORS[action]
        return colors

    def draw_keyboard_overview(self, image, draw, text):
        colors = self.keyboard_colors()
        draw_keyboard(image, self.KEYBOARD_ORIGIN, self.KEYBOARD_UNIT, colors, self.locks)
        drawn = {token for token, _label, _rect in keyboard_keys(self.KEYBOARD_ORIGIN, self.KEYBOARD_UNIT)}
        for index, (label, actions) in enumerate(LEGEND):
            column, row = index % 2, index // 2
            x, y = self.LEGEND_X[column], self.LEGEND_TOP + row * self.LEGEND_ROW
            color = ACTION_COLORS[actions[0]]
            image.alpha_composite(keycap(13, 12, color), (x, y))
            hidden = [key_name(token) for action in actions for token in self.keyboard.keys(action)
                      if POSITION_ALIASES.get(token, token) not in drawn]
            missing = not any(self.keyboard.keys(action) for action in actions)
            value = label + (f' ({", ".join(hidden)})' if hidden else '') + (' (none)' if missing else '')
            text(value, x + 19, y + 2, c(ERROR) if missing else c(WHITE), max_width=150)

    def callouts(self):
        """(group, side, line row, line points, rows) for each drawn group;
        rows are (button, label, action, y), one per bound button."""
        art = pad_art(self.style)
        x0, y0 = self.PAD_ORIGIN
        bound = {token: action for action in self.controller.actions
                 for token in self.controller.keys(action)}
        entries = []
        for name, (side, first, line, buttons, path) in art.groups.items():
            rows = []
            for button in buttons:
                # The left stick and the D-pad always move.
                action = 'left' if button in ('move', 'dpad') else bound.get(button)
                if action is not None:
                    rows.append((button, SHORT_LABELS[action], action, y0 + first + 18 * len(rows)))
            if not rows:
                continue
            start = x0 + BRACKET_X[side]
            points = [(start, y0 + line)] + [(x0 + x, y0 + y) for x, y in path]
            entries.append((name, side, y0 + line, points, rows))
        return entries

    def draw_controller_overview(self, image, draw, text):
        art = pad_art(self.style)
        x0, y0 = self.PAD_ORIGIN
        image.alpha_composite(art.image, (x0, y0))
        callouts = self.callouts()
        if any(name == 'face' for name, *_rest in callouts):
            draw_callout(image, [(x0 + x, y0 + y) for x, y in art.frame], art, (x0, y0))
        for _name, side, line_y, points, rows in callouts:
            draw_callout(image, points, art, (x0, y0))
            bracket = points[0][0]
            ys = [y for *_entry, y in rows] + [line_y]
            draw.line(((bracket, min(ys) - 6), (bracket, max(ys) + 6)), fill=LINE)
            for button, label, _action, y in rows:
                icon = button_icon(button, self.style)
                left = bracket - 21 if side == 'left' else bracket + 4
                if icon is not None:
                    image.alpha_composite(icon, (left, y - 6))
                if side == 'left':
                    text(label, left - 3, y - 5, c(WHITE), 'right', LABEL_WIDTH)
                else:
                    text(label, left + 20, y - 5, c(WHITE), 'left', LABEL_WIDTH)
        status_y = y0 + PAD_HEIGHT + 6
        if not self.controller_available:
            text('Controller support is unavailable here', 256, status_y, c(MUTED), 'center', 420)
        elif not self.controller_enabled:
            text('Controller input is switched off', 256, status_y, c(MUTED), 'center', 420)
        elif self.pads:
            names = ', '.join(pad.name for pad in self.pads)
            text(names, 256, status_y, c(GOLD), 'center', 420)
        else:
            text('No controller connected', 256, status_y, c(MUTED), 'center', 420)

    def hints(self):
        if self.input_device == 'pad':
            confirm, clear, back = (pad_name(button, self.style) for button in ('a', 'x', 'b'))
        else:
            confirm, clear, back = 'Enter', 'Delete', 'Esc'
        return f'{confirm}: change    {clear}: clear    {back}: back'

    def draw_remap(self, image, draw, text, button, measure):
        keyboard = self.device == 'keyboard'
        text('Keyboard keys' if keyboard else 'Controller buttons', 256, self.PANEL[1] + 12, c(GOLD), 'center')
        heading = 'Key' if keyboard else 'Button'
        row_top = self.row_top()
        text('Action', 50, row_top - 15, c(MUTED))
        for index, (left, right) in enumerate(self.SLOT_X):
            text(f'{heading} {index + 1}', (left + right) // 2, row_top - 15, c(MUTED), 'center')
        bindings = self.bindings
        focused = self.focused
        for row, action in enumerate(bindings.actions):
            top = row_top + row * self.ROW_HEIGHT
            unbound = not bindings.keys(action) and action not in ('time',)
            color = ACTION_COLORS[action]
            draw.rectangle((38, top + 7, 43, top + 12), fill=color)
            text(ACTION_BY_NAME[action].label, 50, top + 5, c(ERROR) if unbound else c(WHITE), max_width=176)
            for slot in range(2):
                rect = self.control_rect(('slot', action, slot))
                selected = focused == ('slot', action, slot)
                listening = self.listening == (action, slot)
                locked = bindings.slot_locked(action, slot)
                draw.rectangle(rect, fill=c('#3a3320') if listening else c('#303030') if selected else c('#222222'),
                               outline=c(GOLD) if selected or listening else c('#404040'))
                token = bindings.slots[action][slot]
                cx = (rect[0] + rect[2]) // 2
                if listening:
                    text('Press a key...' if keyboard else 'Press a button...', cx, rect[1] + 5, c(GOLD),
                         'center', rect[2] - rect[0] - 8)
                elif token is None:
                    text('-', cx, rect[1] + 9, c('#5a5a5a'), 'center')
                elif keyboard:
                    text(self.name(token), cx, rect[1] + 5, c(MUTED) if locked else c(WHITE), 'center',
                         rect[2] - rect[0] - 8)
                else:
                    name = self.name(token)
                    icon = button_icon(token, self.style)
                    gap = 5 if icon is not None else 0
                    width = (icon.width if icon is not None else 0) + gap + min(measure(name), 80)
                    x = cx - width // 2
                    if icon is not None:
                        image.alpha_composite(icon, (x, rect[1] + 3))
                        x += icon.width + gap
                    text(name, x, rect[1] + 5, c(MUTED) if locked else c(WHITE), max_width=80)
        button(self.BUTTONS[0], 'Defaults', focused == 'defaults')
        button(self.BUTTONS[1], 'Back', focused == 'back')
        bottom = row_top + len(bindings.actions) * self.ROW_HEIGHT
        if self.message:
            text(self.message, 256, bottom + 8, c(ERROR) if self.message_error else c(GOLD), 'center', 420)
        text(self.hints(), 256, self.BUTTONS[0][1] - 18, c(MUTED), 'center', 420)
