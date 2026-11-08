"""The Controls page of the game menu: what each key and button does.

Port-only. The overview draws the keyboard or the controller with each
action's keys lit; the remap view lists two keys per action. It edits the
window's live Bindings, so a change works at once; the window keeps it.
"""

from PIL import Image, ImageDraw

from pop2.bitmap_labels import label_text
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


def shade(color, factor):
    return tuple(max(0, min(255, round(channel * factor))) for channel in color[:3])


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
KEYBOARD_UNITS = 18.5


def keyboard_keys(origin, unit, key_height=19, pitch=21):
    """(token, label, rect) for every drawn key."""
    left, top = origin
    keys = []
    for row, entries in enumerate(KEYBOARD_ROWS):
        y = top + row * pitch + (4 if row else 0)
        units = 0.0
        for token, label, width in entries:
            if token is not None:
                keys.append((token, label, (left + round(units * unit) + 1, y,
                                            left + round((units + width) * unit) - 1, y + key_height)))
            units += width
        for column, (token, label) in enumerate(NAV_ROWS[row]):
            if token is not None:
                x = 15.5 + column
                keys.append((token, label, (left + round(x * unit) + 1, y,
                                            left + round((x + 1) * unit) - 1, y + key_height)))
    return keys


def draw_arrow(draw, cx, cy, direction, fill):
    points = {'^': ((cx, cy - 2), (cx - 3, cy + 1), (cx + 3, cy + 1)),
              'v': ((cx, cy + 2), (cx - 3, cy - 1), (cx + 3, cy - 1)),
              '<': ((cx - 2, cy), (cx + 1, cy - 3), (cx + 1, cy + 3)),
              '>': ((cx + 2, cy), (cx - 1, cy - 3), (cx - 1, cy + 3))}[direction]
    draw.polygon(points, fill=fill)


def draw_keycap(draw, rect, label, color=None):
    left, top, right, bottom = rect
    if color is None:
        face, edge, light, ink = (40, 40, 40), (20, 20, 20), (72, 72, 72), (128, 128, 128)
    else:
        face, edge, light, ink = shade(color, .62), shade(color, .3), shade(color, .95), (18, 16, 12)
    draw.rectangle(rect, fill=edge)
    draw.rectangle((left, top, right, bottom - 2), fill=face)
    draw.line(((left + 1, top), (right - 1, top)), fill=light)
    draw.line(((left, top + 1), (left, bottom - 3)), fill=light)
    cx, cy = (left + right) // 2, top + (bottom - top) // 2 - 1
    if label in ('^', 'v', '<', '>'):
        draw_arrow(draw, cx, cy, label, ink if color is not None else (150, 150, 150))
    elif label:
        mini_text(draw, cx + 1, cy - 2, label, ink, 'center')


def draw_keyboard(image, origin, unit, token_colors):
    draw = ImageDraw.Draw(image)
    for token, label, rect in keyboard_keys(origin, unit):
        draw_keycap(draw, rect, label, token_colors.get(token))


# -- controller drawing -------------------------------------------------
# Positions on a 196x124 design grid, scaled by PAD_SCALE when drawn.
PAD_SCALE = 1.25
PAD_SIZE = (round(196 * PAD_SCALE), round(124 * PAD_SCALE))
LAYOUTS = {
    # name: (left stick, dpad, right stick, face centre, back, start, guide)
    'xbox': ((50, 44), (76, 80), (122, 80), (148, 44), (84, 42), (112, 42), (98, 26)),
    'playstation': ((70, 82), (46, 46), (126, 82), (150, 46), (70, 28), (126, 28), (98, 70)),
}
FACE_OFFSETS = {'y': (0, -11), 'x': (-11, 0), 'b': (11, 0), 'a': (0, 11)}
XBOX_FACE = {'a': (110, 196, 82), 'b': (224, 98, 90), 'x': (92, 152, 226), 'y': (234, 204, 86)}
PLAYSTATION_FACE = {'a': (136, 174, 232), 'b': (232, 128, 128), 'x': (222, 160, 214),
                    'y': (118, 214, 184)}
NINTENDO_FACE = {name: (214, 214, 214) for name in 'abxy'}
SHORT_LABELS = {'left': 'Move', 'right': 'Move', 'up': 'Jump', 'down': 'Crouch', 'grab': 'Grab',
                'sword': 'Sword', 'time': 'Time left', 'pause': 'Pause', 'menu': 'Menu'}
BODY, BODY_LIT, BODY_EDGE, BODY_SHADOW = (46, 46, 50), (60, 60, 65), (172, 172, 176), (32, 32, 35)
WELL, RING, CAP = (26, 26, 28), (148, 148, 152), (70, 70, 75)
TOP = 22  # room above the body for bumpers and triggers
_BODY_CACHE = {}


def face_colors(style):
    return {'playstation': PLAYSTATION_FACE, 'nintendo': NINTENDO_FACE}.get(style, XBOX_FACE)


def scaled(point):
    return round(point[0] * PAD_SCALE), round(point[1] * PAD_SCALE)


def pad_points(style):
    """Where each button sits on the drawn pad, relative to its corner."""
    layout = LAYOUTS['playstation' if style == 'playstation' else 'xbox']
    left_stick, dpad, right_stick, face, back, start, guide = layout
    points = {'leftstick': left_stick, 'dpad': dpad, 'rightstick': right_stick,
              'back': back, 'start': start, 'guide': guide,
              'leftshoulder': (43, 1), 'rightshoulder': (153, 1),
              'lefttrigger': (38, -12), 'righttrigger': (158, -12)}
    for button, (dx, dy) in FACE_OFFSETS.items():
        points[button] = (face[0] + dx, face[1] + dy)
    if style == 'playstation':
        points['touchpad'] = (98, 34)
    return {name: scaled(point) for name, point in points.items()}


def outline(mask):
    """The one-pixel rim of a mask, as a pixel artist would ink it."""
    pixels = mask.load()
    width, height = mask.size
    edge = Image.new('1', mask.size, 0)
    out = edge.load()
    for y in range(height):
        for x in range(width):
            if pixels[x, y] and any(not (0 <= x + dx < width and 0 <= y + dy < height)
                                    or not pixels[x + dx, y + dy]
                                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                out[x, y] = 1
    return edge


def shape(draw_shape, size):
    mask = Image.new('1', size, 0)
    draw_shape(ImageDraw.Draw(mask))
    return mask


def pad_body(style):
    key = 'playstation' if style == 'playstation' else 'xbox'
    if key in _BODY_CACHE:
        return _BODY_CACHE[key]
    width, height = PAD_SIZE
    size = (width, height + TOP)

    def r(*values):
        return [round(value * PAD_SCALE) + (TOP if index % 2 else 0)
                for index, value in enumerate(values)]

    def body_shape(draw):
        draw.rounded_rectangle(r(14, 4, 182, 74), radius=round(26 * PAD_SCALE), fill=1)
        draw.ellipse(r(6, 30, 74, 122), fill=1)
        draw.ellipse(r(122, 30, 190, 122), fill=1)
        if key == 'playstation':
            draw.rectangle(r(72, 74, 124, 92), fill=0)

    def bumper_shape(draw):
        draw.rounded_rectangle(r(22, -4, 64, 8), radius=6, fill=1)
        draw.rounded_rectangle(r(132, -4, 174, 8), radius=6, fill=1)

    def trigger_shape(draw):
        draw.rounded_rectangle(r(28, -17, 48, -6), radius=4, fill=1)
        draw.rounded_rectangle(r(148, -17, 168, -6), radius=4, fill=1)

    body, bumpers, triggers = (shape(fn, size) for fn in (body_shape, bumper_shape, trigger_shape))
    image = Image.new('RGBA', size, (0, 0, 0, 0))
    for mask, fill in ((triggers, (84, 84, 90)), (bumpers, (70, 70, 76))):
        image.paste(fill + (255,), (0, 0), mask)
        image.paste(BODY_EDGE + (255,), (0, 0), outline(mask))
    image.paste(BODY + (255,), (0, 0), body)
    # A bevel just inside the rim: lit where the edge faces up or left,
    # shaded where it faces down, two hard pixels wide like a 1993 icon.
    pixels = body.load()
    lit, dark = (Image.new('1', size, 0) for _ in range(2))
    lit_pixels, dark_pixels = lit.load(), dark.load()
    for y in range(size[1]):
        for x in range(size[0]):
            if not pixels[x, y]:
                continue

            def outside(dx, dy):
                return not (0 <= x + dx < size[0] and 0 <= y + dy < size[1]) or not pixels[x + dx, y + dy]
            if any(outside(0, -step) or outside(-step, 0) for step in (2, 3)):
                lit_pixels[x, y] = 1
            elif any(outside(0, step) for step in (2, 3, 4)):
                dark_pixels[x, y] = 1
    image.paste(BODY_LIT + (255,), (0, 0), lit)
    image.paste(BODY_SHADOW + (255,), (0, 0), dark)
    image.paste(BODY_EDGE + (255,), (0, 0), outline(body))
    _BODY_CACHE[key] = image
    return image


def draw_face_symbol(draw, cx, cy, button, style, ink):
    if style == 'playstation':
        if button == 'a':
            draw.line(((cx - 2, cy - 2), (cx + 2, cy + 2)), fill=ink)
            draw.line(((cx - 2, cy + 2), (cx + 2, cy - 2)), fill=ink)
        elif button == 'b':
            draw.ellipse((cx - 3, cy - 3, cx + 3, cy + 3), outline=ink)
        elif button == 'x':
            draw.rectangle((cx - 2, cy - 2, cx + 2, cy + 2), outline=ink)
        else:
            draw.line(((cx, cy - 3), (cx - 3, cy + 2), (cx + 3, cy + 2), (cx, cy - 3)), fill=ink)
        return
    mini_text(draw, cx + 1, cy - 2, pad_name(button, style), ink, 'center')


def draw_pad(image, origin, style):
    """Draw the pad with its corner at origin; returns button centres."""
    x0, y0 = origin
    image.alpha_composite(pad_body(style), (x0, y0 - TOP))
    draw = ImageDraw.Draw(image)
    points = {name: (x0 + x, y0 + y) for name, (x, y) in pad_points(style).items()}
    for name in ('lefttrigger', 'righttrigger', 'leftshoulder', 'rightshoulder'):
        cx, cy = points[name]
        mini_text(draw, cx + 1, cy - 2, pad_name(name, style), (18, 18, 20), 'center')
    if style == 'playstation':
        tx, ty = points['touchpad']
        draw.rounded_rectangle((tx - 26, ty - 14, tx + 26, ty + 12), radius=3,
                               fill=BODY_SHADOW, outline=(118, 118, 122))
    for name in ('leftstick', 'rightstick'):
        cx, cy = points[name]
        draw.ellipse((cx - 15, cy - 15, cx + 15, cy + 15), fill=WELL, outline=RING)
        draw.ellipse((cx - 9, cy - 9, cx + 9, cy + 9), fill=CAP, outline=(122, 122, 126))
        draw.arc((cx - 6, cy - 6, cx + 6, cy + 6), 200, 290, fill=(112, 112, 118))
    cx, cy = points['dpad']
    arm, half = 13, 5
    draw.rectangle((cx - half, cy - arm, cx + half, cy + arm), fill=WELL)
    draw.rectangle((cx - arm, cy - half, cx + arm, cy + half), fill=WELL)
    draw.line(((cx - half, cy - arm), (cx + half, cy - arm), (cx + half, cy - half),
               (cx + arm, cy - half), (cx + arm, cy + half), (cx + half, cy + half),
               (cx + half, cy + arm), (cx - half, cy + arm), (cx - half, cy + half),
               (cx - arm, cy + half), (cx - arm, cy - half), (cx - half, cy - half),
               (cx - half, cy - arm)), fill=RING)
    for direction, (dx, dy) in (('^', (0, -8)), ('v', (0, 8)), ('<', (-8, 0)), ('>', (8, 0))):
        draw_arrow(draw, cx + dx, cy + dy, direction, (100, 100, 104))
    for name in ('back', 'start'):
        cx, cy = points[name]
        draw.rounded_rectangle((cx - 5, cy - 4, cx + 5, cy + 4), radius=3, fill=WELL, outline=RING)
        if name == 'back':
            draw.rectangle((cx - 2, cy - 2, cx + 1, cy + 1), outline=(150, 150, 154))
        else:
            for row in (-2, 0, 2):
                draw.line(((cx - 2, cy + row), (cx + 2, cy + row)), fill=(150, 150, 154))
    gx, gy = points['guide']
    draw.ellipse((gx - 8, gy - 8, gx + 8, gy + 8), fill=WELL, outline=(118, 118, 122))
    colors = face_colors(style)
    for name in ('a', 'b', 'x', 'y'):
        cx, cy = points[name]
        color = colors[name]
        draw.ellipse((cx - 7, cy - 7, cx + 7, cy + 7), fill=WELL, outline=shade(color, .75))
        draw_face_symbol(draw, cx, cy, name, style, color)
    return points


BUTTON_RADIUS = {'leftstick': 15, 'rightstick': 15, 'dpad': 13, 'a': 7, 'b': 7, 'x': 7, 'y': 7,
                 'back': 5, 'start': 5, 'guide': 8, 'touchpad': 14}


def pad_icon(image, x, y, token, style):
    """A small button glyph for the remap list; returns its width."""
    draw = ImageDraw.Draw(image)
    if token in ('a', 'b', 'x', 'y'):
        color = face_colors(style)[token]
        draw.ellipse((x, y, x + 12, y + 12), fill=WELL, outline=shade(color, .85))
        draw_face_symbol(draw, x + 6, y + 6, token, style, color)
        return 13
    if token in ('back', 'start'):
        cx, cy = x + 6, y + 6
        draw.rounded_rectangle((x, y + 1, x + 12, y + 11), radius=3, fill=WELL, outline=RING)
        if token == 'back':
            draw.rectangle((cx - 2, cy - 2, cx + 1, cy + 1), outline=(190, 190, 194))
        else:
            for row in (-2, 0, 2):
                draw.line(((cx - 2, cy + row), (cx + 2, cy + row)), fill=(190, 190, 194))
        return 13
    return 0


# Labels for the small centre buttons sit higher, so their lines pass
# above the sticks rather than across them.
CALLOUT_LIFT = {'back': -36, 'start': -36}
# Callout rows, top to bottom, so lines rarely cross.
PAD_CALLOUTS = {'left': ('lefttrigger', 'leftshoulder', 'move', 'back', 'leftstick', 'misc1',
                         'paddle1', 'paddle3'),
                'right': ('righttrigger', 'rightshoulder', 'y', 'start', 'b', 'x', 'a',
                          'rightstick', 'touchpad', 'paddle2', 'paddle4')}


class ControlsPage:
    PANEL = centered_panel(470, 350)
    TABS = ((150, 34, 252, 56), (260, 34, 362, 56))
    BUTTONS = ((100, 318, 250, 344), (262, 318, 412, 344))
    TOGGLE = (196, 292, 316, 310)
    ROW_TOP = 52
    ROW_HEIGHT = 22
    SLOT_X = ((232, 344), (352, 464))
    KEYBOARD_ORIGIN = (43, 66)
    KEYBOARD_UNIT = 23
    PAD_ORIGIN = (256 - PAD_SIZE[0] // 2, 88)

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
        top = self.ROW_TOP + self.bindings.actions.index(action) * self.ROW_HEIGHT
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
            self.draw_remap(image, draw, text, button)
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
            x, y = 92 + column * 176, 212 + row * 18
            color = ACTION_COLORS[actions[0]]
            draw.rectangle((x, y + 1, x + 9, y + 10), fill=shade(color, .62), outline=shade(color, .95))
            hidden = [key_name(token) for action in actions for token in self.keyboard.keys(action)
                      if POSITION_ALIASES.get(token, token) not in drawn]
            missing = not any(self.keyboard.keys(action) for action in actions)
            value = label + (f' ({", ".join(hidden)})' if hidden else '') + (' (none)' if missing else '')
            text(value, x + 15, y + 1, ERROR if missing else WHITE, max_width=150)

    def draw_controller_overview(self, image, draw, text):
        style = self.style
        bound = {}
        for action in self.controller.actions:
            for token in self.controller.keys(action):
                bound[token] = action
        origin = self.PAD_ORIGIN
        points = draw_pad(image, origin, style)
        ends = {'left': origin[0] - 16, 'right': origin[0] + PAD_SIZE[0] + 16}
        line = (118, 118, 122)
        for side, buttons in PAD_CALLOUTS.items():
            entries = []
            for button in buttons:
                if button == 'move':
                    action, targets = 'left', ('leftstick', 'dpad')
                elif button in bound and button in points:
                    action, targets = bound[button], (button,)
                else:
                    continue
                wanted = (sum(points[target][1] for target in targets) / len(targets)
                          + CALLOUT_LIFT.get(button, 0))
                entries.append((wanted, buttons.index(button), action, targets))
            # Each label as level with its button as the 17-pixel rows allow.
            entries.sort()
            rows, top, bottom = [], origin[1] - 18, origin[1] + PAD_SIZE[1] - 4
            for wanted, *_rest in entries:
                rows.append(max(round(wanted), rows[-1] + 17 if rows else top))
            overflow = (rows[-1] - bottom) if rows else 0
            if overflow > 0:
                rows = [max(top + index * 17, y - overflow) for index, y in enumerate(rows)]
            for y, (_wanted, _order, action, targets) in zip(rows, entries):
                end = ends[side]
                elbow = end + (10 if side == 'left' else -10)
                for target in targets:
                    tx, ty = points[target]
                    dx, dy = elbow - tx, y - ty
                    length = max(1.0, (dx * dx + dy * dy) ** .5)
                    radius = BUTTON_RADIUS.get(target, 4) + 1
                    stop = (round(tx + dx * radius / length), round(ty + dy * radius / length))
                    draw.line(((end, y), (elbow, y), stop), fill=line)
                color = ACTION_COLORS[action]
                swatch = end - 6 if side == 'left' else end + 2
                draw.rectangle((swatch, y - 2, swatch + 4, y + 2), fill=shade(color, .95))
                text(SHORT_LABELS[action], end - 10 if side == 'left' else end + 10, y - 5, WHITE,
                     'right' if side == 'left' else 'left', 92)
        status_y = origin[1] + PAD_SIZE[1] + 8
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

    def draw_remap(self, image, draw, text, button):
        keyboard = self.device == 'keyboard'
        text('Keyboard keys' if keyboard else 'Controller buttons', 256, self.PANEL[1] + 12, GOLD, 'center')
        heading = 'Key' if keyboard else 'Button'
        text('Action', 44, self.ROW_TOP - 15, MUTED)
        for index, (left, right) in enumerate(self.SLOT_X):
            text(f'{heading} {index + 1}', (left + right) // 2, self.ROW_TOP - 15, MUTED, 'center')
        bindings = self.bindings
        focused = self.focused
        for row, action in enumerate(bindings.actions):
            top = self.ROW_TOP + row * self.ROW_HEIGHT
            unbound = not bindings.keys(action) and action not in ('time',)
            color = ACTION_COLORS[action]
            draw.rectangle((36, top + 5, 41, top + 10), fill=shade(color, .9))
            text(ACTION_BY_NAME[action].label, 48, top + 4, ERROR if unbound else WHITE, max_width=176)
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
                    icon_x = rect[0] + 8
                    width = pad_icon(image, icon_x, rect[1] + 3, token, self.style)
                    text(name, icon_x + width + 5, rect[1] + 5, MUTED if locked else WHITE,
                         max_width=rect[2] - icon_x - width - 10)
        button(self.BUTTONS[0], 'Defaults', focused == 'defaults')
        button(self.BUTTONS[1], 'Back', focused == 'back')
        bottom = self.ROW_TOP + len(bindings.actions) * self.ROW_HEIGHT
        if self.message:
            text(self.message, 256, bottom + 8, ERROR if self.message_error else GOLD, 'center', 420)
        text(self.hints(), 256, self.BUTTONS[0][1] - 18, MUTED, 'center', 420)
