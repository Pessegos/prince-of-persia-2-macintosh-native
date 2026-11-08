"""The Controls page of the game menu: what each key and button does.

Port-only. The overview draws the keyboard or the controller with each
action's keys lit; the remap view lists two keys per action. It edits the
window's live Bindings, so a change works at once; the window keeps it.
"""

from PIL import Image, ImageDraw

from pop2.bitmap_labels import label_text
from pop2.controls_art import (PAD_HEIGHT, PAD_WIDTH, button_icon, keyboard_case, keycap, legend_ink,
                               pad_art)
from pop2.game_ui import DevelopmentMenu, centered_panel
from pop2.input_bindings import ACTION_BY_NAME, LOCKED_KEYS, PAD_LOCKED, key_name, key_token, pad_name

GOLD, WHITE, MUTED, ERROR = '#f4d873', '#eeeeee', '#999999', '#ff9b9b'
ACTION_COLORS = {
    'left': (244, 216, 115), 'right': (244, 216, 115), 'up': (150, 204, 104),
    'down': (104, 184, 214), 'grab': (226, 152, 86), 'sword': (222, 98, 92),
    'time': (186, 150, 226), 'pause': (196, 196, 196), 'menu': (214, 128, 176),
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
    'M': '#...#|##.##|#.#.#|#...#|#...#', 'N': '#..#|##.#|#.##|#..#|#..#',
    'O': '.#.|#.#|#.#|#.#|.#.', 'P': '##.|#.#|##.|#..|#..', 'Q': '.#.|#.#|#.#|##.|.##',
    'R': '##.|#.#|##.|#.#|#.#', 'S': '.##|#..|.#.|..#|##.', 'T': '###|.#.|.#.|.#.|.#.',
    'U': '#.#|#.#|#.#|#.#|###', 'V': '#.#|#.#|#.#|#.#|.#.', 'W': '#...#|#...#|#.#.#|##.##|#...#',
    'X': '#.#|#.#|.#.|#.#|#.#', 'Y': '#.#|#.#|.#.|.#.|.#.', 'Z': '###|..#|.#.|#..|###',
    '0': '###|#.#|#.#|#.#|###', '1': '.#.|##.|.#.|.#.|###', '2': '##.|..#|.#.|#..|###',
    '3': '##.|..#|.#.|..#|##.', '4': '#.#|#.#|###|..#|..#', '5': '###|#..|##.|..#|##.',
    '6': '.##|#..|###|#.#|###', '7': '###|..#|.#.|.#.|.#.', '8': '###|#.#|###|#.#|###',
    '9': '###|#.#|###|..#|##.', '-': '...|...|###|...|...', '=': '...|###|...|###|...',
    '[': '##|#.|#.|#.|##', ']': '##|.#|.#|.#|##', '\\': '#..|#..|.#.|..#|..#',
    ';': '..|.#|..|.#|#.', "'": '#|#|.|.|.', ',': '..|..|..|.#|#.', '.': '.|.|.|.|#',
    '/': '..#|..#|.#.|#..|#..', '`': '#.|.#|..|..|..', '+': '...|.#.|###|.#.|...',
    ' ': '..|..|..|..|..',
}


def mini_text(draw, x, y, text, fill, align='left'):
    glyphs = [MINI[char] for char in text.upper() if char in MINI]
    width = sum(len(glyph.split('|')[0]) + 1 for glyph in glyphs) - 1
    if align == 'center':
        x -= width // 2
    elif align == 'right':
        x -= width
    for glyph in glyphs:
        rows = glyph.split('|')
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
NAV_ROWS = ((), (('Insert', 'INS'), ('Home', 'HOME'), ('Prior', 'PGUP')),
            (('Delete', 'DEL'), ('End', 'END'), ('Next', 'PGDN')), (),
            ((None, ''), ('Up', '^'), (None, '')), (('Left', '<'), ('Down', 'v'), ('Right', '>')))
# Keys that sit where a US key is drawn on common European layouts.
POSITION_ALIASES = {'ccedilla': 'semicolon', 'ntilde': 'semicolon', 'odiaeresis': 'semicolon',
                    'masculine': 'grave', 'KP_Enter': 'Return'}


def keyboard_keys(origin, unit, key_height=19, pitch=22):
    """(token, label, rect) for every drawn key."""
    left, top = origin
    keys = []
    for row, entries in enumerate(KEYBOARD_ROWS):
        y = top + row * pitch + (4 if row else 0)
        units = 0.0
        for token, label, width in entries:
            if token is not None:
                keys.append((token, label, (left + round(units * unit) + 1, y,
                                            left + round((units + width) * unit) - 2, y + key_height)))
            units += width
        for column, (token, label) in enumerate(NAV_ROWS[row]):
            if token is not None:
                x = 15.5 + column
                keys.append((token, label, (left + round(x * unit) + 1, y,
                                            left + round((x + 1) * unit) - 2, y + key_height)))
    return keys


def draw_arrow(draw, cx, cy, direction, fill):
    points = {'^': ((cx, cy - 2), (cx - 3, cy + 1), (cx + 3, cy + 1)),
              'v': ((cx, cy + 2), (cx - 3, cy - 1), (cx + 3, cy - 1)),
              '<': ((cx - 2, cy), (cx + 1, cy - 3), (cx + 1, cy + 3)),
              '>': ((cx + 2, cy), (cx - 1, cy - 3), (cx - 1, cy + 3))}[direction]
    draw.polygon(points, fill=fill)


def draw_keycap(image, rect, label, color=None):
    left, top, right, bottom = rect
    cap = keycap(right - left + 1, bottom - top + 1, color)
    image.alpha_composite(cap, (left, top))
    draw = ImageDraw.Draw(image)
    ink = legend_ink(color)
    cx, cy = (left + right) // 2, top + (bottom - top - 3) // 2
    if label in ('^', 'v', '<', '>'):
        draw_arrow(draw, cx, cy, label, ink)
    elif label:
        mini_text(draw, cx + 1, cy - 2, label, ink, 'center')


KEYBOARD_MARGIN = 6


def keyboard_bounds(origin, unit):
    rects = [rect for _token, _label, rect in keyboard_keys(origin, unit)]
    return (min(rect[0] for rect in rects) - KEYBOARD_MARGIN, min(rect[1] for rect in rects) - KEYBOARD_MARGIN,
            max(rect[2] for rect in rects) + KEYBOARD_MARGIN, max(rect[3] for rect in rects) + KEYBOARD_MARGIN)


def draw_keyboard(image, origin, unit, token_colors):
    left, top, right, bottom = keyboard_bounds(origin, unit)
    image.alpha_composite(keyboard_case(right - left + 1, bottom - top + 1), (left, top))
    for token, label, rect in keyboard_keys(origin, unit):
        draw_keycap(image, rect, label, token_colors.get(token))


# -- controller drawing -------------------------------------------------
SHORT_LABELS = {'left': 'Move', 'right': 'Move', 'up': 'Jump', 'down': 'Crouch', 'grab': 'Grab',
                'sword': 'Sword', 'time': 'Time left', 'pause': 'Pause', 'menu': 'Menu'}
LINE_ON_DARK, LINE_ON_LIGHT = (132, 130, 128), (64, 62, 66)


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
    """A one-pixel leader line, dark where it crosses the light shell."""
    pad = art.image
    for x, y in line_pixels(points):
        px, py = x - origin[0], y - origin[1]
        over = (0 <= px < pad.width and 0 <= py < pad.height) and pad.getpixel((px, py))
        light = over and over[3] and sum(over[:3]) > 330
        if 0 <= x < image.width and 0 <= y < image.height:
            image.putpixel((x, y), (*(LINE_ON_LIGHT if light else LINE_ON_DARK), 255))


class ControlsPage:
    PANEL = centered_panel(470, 350)
    TABS = ((150, 34, 252, 56), (260, 34, 362, 56))
    BUTTONS = ((100, 318, 250, 344), (262, 318, 412, 344))
    TOGGLE = (196, 286, 316, 304)
    ROW_TOP = 52
    ROW_HEIGHT = 22
    SLOT_X = ((232, 344), (352, 464))
    KEYBOARD_ORIGIN = (43, 70)
    KEYBOARD_UNIT = 23
    LEGEND_X = (103, 291)
    PAD_ORIGIN = (256 - PAD_WIDTH // 2, 68)

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
        image = Image.alpha_composite(viewport, Image.new('RGBA', viewport.size, (0, 0, 0, 100)))
        draw = ImageDraw.Draw(image)

        def text(value, x, y, color=WHITE, align='left', max_width=None):
            glyphs = label_text(font, value, color)
            if max_width is not None and glyphs.width > max_width:
                glyphs = glyphs.resize((max_width, glyphs.height), Image.Resampling.NEAREST)
            ink = glyphs.getbbox()
            if align == 'center':
                x -= glyphs.width // 2
            elif align == 'right':
                x -= glyphs.width
            image.paste(glyphs, (x, y - (ink[1] if ink else 0)), glyphs)

        def button(rect, label, selected, color=WHITE):
            draw.rectangle(rect, fill='#303030' if selected else '#222222',
                           outline=GOLD if selected else '#626262')
            text(label, (rect[0] + rect[2]) // 2, rect[1] + (rect[3] - rect[1]) // 2 - 4,
                 color, 'center', rect[2] - rect[0] - 12)

        draw.rectangle(self.PANEL, fill='#181818', outline='#858585')
        focused = self.focused
        if self.view == 'overview':
            text('Controls', 256, self.PANEL[1] + 12, GOLD, 'center')
            for rect, device, label in zip(self.TABS, ('keyboard', 'controller'),
                                           ('Keyboard', 'Controller')):
                chosen = device == self.device
                draw.rectangle(rect, fill='#303030' if chosen else '#1c1c1c',
                               outline=GOLD if focused == 'tab_' + device else
                               '#8a8a8a' if chosen else '#4a4a4a')
                text(label, (rect[0] + rect[2]) // 2, rect[1] + 7,
                     GOLD if chosen else MUTED, 'center')
            if self.device == 'keyboard':
                self.draw_keyboard_overview(image, draw, text)
                button(self.BUTTONS[0], 'Change keys...', focused == 'change')
            else:
                self.draw_controller_overview(image, draw, text)
                left, top, right, bottom = self.TOGGLE
                selected = focused == 'toggle'
                draw.rectangle(self.TOGGLE, fill='#303030' if selected else '#181818',
                               outline=GOLD if selected else '#181818')
                draw.rectangle((left + 6, top + 4, left + 16, top + 14), fill='#121212', outline=MUTED)
                if self.controller_enabled:
                    draw.line(((left + 8, top + 9), (left + 10, top + 12), (left + 14, top + 6)),
                              fill=GOLD, width=2)
                text('Use controller', left + 24, top + 5)
                button(self.BUTTONS[0], 'Change buttons...', focused == 'change')
            button(self.BUTTONS[1], 'Back' if self.return_to_menu else 'Close', focused == 'back')
        else:
            self.draw_remap(image, draw, text, button, lambda value: label_text(font, value, WHITE).width)
        return image

    def keyboard_colors(self):
        colors = {}
        for action in self.keyboard.actions:
            for token in self.keyboard.keys(action):
                colors[POSITION_ALIASES.get(token, token)] = ACTION_COLORS[action]
        return colors

    def draw_keyboard_overview(self, image, draw, text):
        colors = self.keyboard_colors()
        draw_keyboard(image, self.KEYBOARD_ORIGIN, self.KEYBOARD_UNIT, colors)
        drawn = {token for token, _label, _rect in keyboard_keys(self.KEYBOARD_ORIGIN, self.KEYBOARD_UNIT)}
        for index, (label, actions) in enumerate(LEGEND):
            column, row = index % 2, index // 2
            x, y = self.LEGEND_X[column], 224 + row * 18
            color = ACTION_COLORS[actions[0]]
            image.alpha_composite(keycap(13, 12, color), (x, y))
            hidden = [key_name(token) for action in actions for token in self.keyboard.keys(action)
                      if POSITION_ALIASES.get(token, token) not in drawn]
            missing = not any(self.keyboard.keys(action) for action in actions)
            value = label + (f' ({", ".join(hidden)})' if hidden else '') + (' (none)' if missing else '')
            text(value, x + 19, y + 2, ERROR if missing else WHITE, max_width=150)

    def callouts(self):
        """(button, side, row, line points, label, action) for each drawn label."""
        art = pad_art(self.style)
        x0, y0 = self.PAD_ORIGIN
        bound = {token: action for action in self.controller.actions
                 for token in self.controller.keys(action)}
        entries = []
        for button, (side, row, path) in art.routes.items():
            # The left stick and the D-pad always move.
            action = 'left' if button in ('move', 'dpad') else bound.get(button)
            if action is None:
                continue
            label = SHORT_LABELS[action]
            start = x0 - 8 if side == 'left' else x0 + PAD_WIDTH + 8
            points = [(start, y0 + row)] + [(x0 + x, y0 + y) for x, y in path]
            entries.append((button, side, y0 + row, points, label, action))
        return entries

    def draw_controller_overview(self, image, draw, text):
        art = pad_art(self.style)
        x0, y0 = self.PAD_ORIGIN
        image.alpha_composite(art.image, (x0, y0))
        for _button, side, row, points, label, action in self.callouts():
            draw_callout(image, points, art, (x0, y0))
            color = ACTION_COLORS[action]
            if side == 'left':
                swatch, anchor, align = x0 - 14, x0 - 18, 'right'
            else:
                swatch, anchor, align = x0 + PAD_WIDTH + 10, x0 + PAD_WIDTH + 18, 'left'
            draw.rectangle((swatch, row - 2, swatch + 4, row + 2), fill=color)
            text(label, anchor, row - 5, WHITE, align, 88)
        status_y = y0 + PAD_HEIGHT + 6
        if not self.controller_available:
            text('Controller support is unavailable here', 256, status_y, MUTED, 'center', 420)
        elif not self.controller_enabled:
            text('Controller input is switched off', 256, status_y, MUTED, 'center', 420)
        elif self.pads:
            names = ', '.join(pad.name for pad in self.pads)
            text(names, 256, status_y, GOLD, 'center', 420)
        else:
            text('No controller connected', 256, status_y, MUTED, 'center', 420)

    def hints(self):
        if self.input_device == 'pad':
            confirm, clear, back = (pad_name(button, self.style) for button in ('a', 'x', 'b'))
        else:
            confirm, clear, back = 'Enter', 'Delete', 'Esc'
        return f'{confirm}: change    {clear}: clear    {back}: back'

    def draw_remap(self, image, draw, text, button, measure):
        keyboard = self.device == 'keyboard'
        text('Keyboard keys' if keyboard else 'Controller buttons', 256, self.PANEL[1] + 12, GOLD, 'center')
        heading = 'Key' if keyboard else 'Button'
        row_top = self.row_top()
        text('Action', 50, row_top - 15, MUTED)
        for index, (left, right) in enumerate(self.SLOT_X):
            text(f'{heading} {index + 1}', (left + right) // 2, row_top - 15, MUTED, 'center')
        bindings = self.bindings
        focused = self.focused
        for row, action in enumerate(bindings.actions):
            top = row_top + row * self.ROW_HEIGHT
            unbound = not bindings.keys(action) and action not in ('time',)
            color = ACTION_COLORS[action]
            draw.rectangle((38, top + 7, 43, top + 12), fill=color)
            text(ACTION_BY_NAME[action].label, 50, top + 5, ERROR if unbound else WHITE, max_width=176)
            for slot in range(2):
                rect = self.control_rect(('slot', action, slot))
                selected = focused == ('slot', action, slot)
                listening = self.listening == (action, slot)
                locked = bindings.slot_locked(action, slot)
                draw.rectangle(rect, fill='#3a3320' if listening else '#303030' if selected else '#222222',
                               outline=GOLD if selected or listening else '#404040')
                token = bindings.slots[action][slot]
                cx = (rect[0] + rect[2]) // 2
                if listening:
                    text('Press a key...' if keyboard else 'Press a button...', cx, rect[1] + 5, GOLD,
                         'center', rect[2] - rect[0] - 8)
                elif token is None:
                    text('-', cx, rect[1] + 9, '#5a5a5a', 'center')
                elif keyboard:
                    text(self.name(token), cx, rect[1] + 5, MUTED if locked else WHITE, 'center',
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
                    text(name, x, rect[1] + 5, MUTED if locked else WHITE, max_width=80)
        button(self.BUTTONS[0], 'Defaults', focused == 'defaults')
        button(self.BUTTONS[1], 'Back', focused == 'back')
        bottom = row_top + len(bindings.actions) * self.ROW_HEIGHT
        if self.message:
            text(self.message, 256, bottom + 8, ERROR if self.message_error else GOLD, 'center', 420)
        text(self.hints(), 256, self.BUTTONS[0][1] - 18, MUTED, 'center', 420)
