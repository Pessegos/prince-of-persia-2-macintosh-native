"""The look of the port's menus: one colour table and frame per environment.

The menus are an addition of the port, not original behaviour. Every menu
page writes its colours as the neutral (grey and gold) values and passes
them through ``c``; the current theme maps each neutral colour to its own.
The neutral theme maps every colour to itself, so pages look exactly as
they did before themes existed.

The frames are drawn here from a few hard shades. They follow the colours of
the level art but contain none of the game's own pictures, so they need no
imported resources.
"""

import math
import os
import random
from dataclasses import dataclass, field

from PIL import Image, ImageDraw

# Role -> the neutral colour that pages write.
NEUTRAL_ROLES = {
    'accent': '#f4d873', 'text': '#eeeeee', 'muted': '#999999', 'muted_light': '#b9b9b9',
    'dim_text': '#777777', 'faint': '#5a5a5a',
    'panel': '#181818', 'panel_edge': '#858585', 'backdrop': '#101010', 'rule': '#383838',
    'row': '#222222', 'row_dark': '#1c1c1c', 'row_edge': '#626262', 'row_edge_soft': '#404040',
    'row_edge_dark': '#4a4a4a', 'row_edge_lit': '#8a8a8a',
    'selected': '#303030', 'hover': '#454545', 'listening': '#3a3320',
    'well': '#121212', 'well_dark': '#0c0c0c',
    'active': '#77c9dc', 'active_map': '#63c8e5', 'active_fill': '#253033',
    'active_field': '#202a2d', 'text_selection': '#385462',
    'error': '#ff9b9b', 'danger': '#422622', 'danger_soft': '#2b1d1b',
}


@dataclass(frozen=True)
class MenuTheme:
    name: str
    roles: dict = field(default_factory=dict)
    dim: int = 100            # black veil over the room behind the F1 menu, 0-255
    # 'rock', 'bands', 'sand', 'studs', 'pillars', 'columns' or None for a plain outline
    frame: str | None = None
    grow: tuple = (0, 0, 0)   # how far the frame reaches beyond a panel: sides, top, bottom
    # 'bands': the moulding's rows from the outside inwards; a row of several
    # colours is speckled with them.
    bands: tuple = ()
    # 'rock': the stone's grain as (colour, how often), then the extra shades
    # that lit and shadowed edges may use. None of them is black, so a frame
    # never shows a hole that is not really there.
    grain: tuple = ()
    shades: tuple = ()

    @property
    def frame_width(self):
        """How far the frame reaches inwards from its outer edge."""
        if self.frame == 'bands':
            return len(self.bands)
        return 0 if self.frame is None else _THICKNESS[self.frame][0]

    def __post_init__(self):
        unknown = set(self.roles) - set(NEUTRAL_ROLES)
        if unknown:
            raise ValueError(f'unknown menu colour roles: {sorted(unknown)}')
        object.__setattr__(self, 'colours', {
            neutral: self.roles.get(role, neutral) for role, neutral in NEUTRAL_ROLES.items()})

    def colour(self, role):
        return self.colours[NEUTRAL_ROLES[role]]


NEUTRAL = MenuTheme('neutral')

# Level 1: the palace's dark blue frieze, cream cornice and red wall band.
PALACE = MenuTheme('palace', {
    'accent': '#fdae61', 'text': '#ffffd6', 'muted': '#6f8ca8', 'muted_light': '#9fb6c9',
    'dim_text': '#56728c', 'faint': '#3f5a75',
    'panel': '#001831', 'panel_edge': '#cebea7', 'backdrop': '#00101f', 'rule': '#215284',
    'row': '#183152', 'row_dark': '#10284a', 'row_edge': '#215284', 'row_edge_soft': '#215284',
    'row_edge_dark': '#1b4470', 'row_edge_lit': '#4993b5',
    'selected': '#9c1042', 'hover': '#2a4a78', 'listening': '#5a2a3a',
    'well': '#001831', 'well_dark': '#000f22',
    'active': '#52b5bd', 'active_map': '#52b5bd', 'active_fill': '#1d4a66',
    'active_field': '#153a55', 'text_selection': '#347d95',
    'danger': '#5a1030', 'danger_soft': '#3a1030',
}, dim=100, frame='bands', grow=(1, 6, 7), bands=(
    # A cream cornice with the light on its outer edge, then the wall's
    # turquoise and orange trim lines.
    ('#000010',), ('#ffffd6',), ('#e5e3c6',), ('#f7e3b0', '#f7f7ad', '#f0d6ae'),
    ('#f7e3b0', '#f0d6ae', '#f7e3b0', '#f7f7ad'), ('#e7cead', '#e7cead', '#e7cead', '#e7cead', '#f0d6ae'),
    ('#cebea7',), ('#ae9594',), ('#8c6d87', '#876e77'), ('#000010',), ('#52b5bd',), ('#fdae61',),
))

# Level 2: sandstone around the dark sea, with the sun's yellow.
DESERT = MenuTheme('desert', {
    'accent': '#ffd75a', 'text': '#fff3d6', 'muted': '#6fa3a8', 'muted_light': '#a5c9c8',
    'dim_text': '#4f8088', 'faint': '#2f6068',
    'panel': '#012a33', 'panel_edge': '#d8ab71', 'backdrop': '#011d24', 'rule': '#0b5a66',
    'row': '#063c47', 'row_dark': '#04323c', 'row_edge': '#0b5a66', 'row_edge_soft': '#0b5a66',
    'row_edge_dark': '#084650', 'row_edge_lit': '#01929c',
    'selected': '#0b6f7a', 'hover': '#0b5a66', 'listening': '#5a4a18',
    'well': '#012a33', 'well_dark': '#011d24',
    'active': '#fedea5', 'active_map': '#fedea5', 'active_fill': '#3a4a3a',
    'active_field': '#063c47', 'text_selection': '#01929c',
    'danger': '#5a2010', 'danger_soft': '#3a2018',
}, dim=115, frame='sand', grow=(2, 5, 7))

# Levels 3-5: cavern rock, bone-coloured text and torch flame.
CAVERNS = MenuTheme('caverns', {
    'accent': '#f7b54a', 'text': '#f0dcc8', 'muted': '#8c6b5a', 'muted_light': '#b59a88',
    'dim_text': '#735242', 'faint': '#5a3929',
    'panel': '#180808', 'panel_edge': '#7b5a4a', 'backdrop': '#100404', 'rule': '#4a3129',
    'row': '#291008', 'row_dark': '#210c06', 'row_edge': '#4a3129', 'row_edge_soft': '#4a3129',
    'row_edge_dark': '#392118', 'row_edge_lit': '#8c6b5a',
    'selected': '#523931', 'hover': '#634a42', 'listening': '#5a3a18',
    'well': '#180808', 'well_dark': '#0c0202',
    'active': '#a8c8b8', 'active_map': '#a8c8b8', 'active_fill': '#2a2a22',
    'active_field': '#2a2420', 'text_selection': '#5a4a30',
    'danger': '#4a1410', 'danger_soft': '#32100c',
}, dim=140, frame='rock', grow=(2, 5, 7), grain=(
    ('#523931', 211), ('#5a4239', 140), ('#634231', 135), ('#634a42', 74), ('#6b4a39', 61),
    ('#735242', 38), ('#524a39', 23), ('#523121', 22), ('#5a3929', 21), ('#423131', 20),
    ('#633931', 17), ('#524242', 14), ('#734a31', 12), ('#4a2929', 10), ('#4a2921', 9),
    ('#7b5a4a', 8), ('#4a3129', 8), ('#4a1818', 7), ('#6b524a', 6), ('#7b5242', 5),
), shades=('#8c6b5a', '#9c6b5a', '#a57b63', '#392118', '#312121', '#291008', '#291818'))

# Levels 6-9: the ruins' violet stone over indigo shadow, with the sand's gold.
RUINS = MenuTheme('ruins', {
    'accent': '#f7bd84', 'text': '#ece6f5', 'muted': '#7c749c', 'muted_light': '#a59fc0',
    'dim_text': '#5c5485', 'faint': '#413871',
    'panel': '#100839', 'panel_edge': '#736b96', 'backdrop': '#0a0528', 'rule': '#332a67',
    'row': '#1c1650', 'row_dark': '#150f45', 'row_edge': '#332a67', 'row_edge_soft': '#332a67',
    'row_edge_dark': '#251c5d', 'row_edge_lit': '#736b96',
    'selected': '#413871', 'hover': '#372f6a', 'listening': '#5a3a28',
    'well': '#100839', 'well_dark': '#0a0528',
    'active': '#9fd0c8', 'active_map': '#9fd0c8', 'active_fill': '#1f2a55',
    'active_field': '#1a1f4c', 'text_selection': '#534b7e',
    'danger': '#522118', 'danger_soft': '#3a1830',
}, dim=120, frame='pillars', grow=(2, 5, 7))

# Levels 10-13: the temple's carved red stone and candle flame.
TEMPLE = MenuTheme('temple', {
    'accent': '#ffd97a', 'text': '#f6e7cf', 'muted': '#a05a4c', 'muted_light': '#c89080',
    'dim_text': '#7a3a30', 'faint': '#5a1810',
    'panel': '#180000', 'panel_edge': '#a1251e', 'backdrop': '#100000', 'rule': '#631810',
    'row': '#330404', 'row_dark': '#290202', 'row_edge': '#631810', 'row_edge_soft': '#5a1008',
    'row_edge_dark': '#450a0a', 'row_edge_lit': '#a1251e',
    'selected': '#781313', 'hover': '#520808', 'listening': '#5a3a10',
    'well': '#180000', 'well_dark': '#0c0000',
    'active': '#b9b4cc', 'active_map': '#b9b4cc', 'active_fill': '#3a2a30',
    'active_field': '#33202a', 'text_selection': '#6c2107',
    'danger': '#6b1808', 'danger_soft': '#450a0a',
}, dim=100, frame='columns', grow=(2, 5, 7))

THEMES = {theme.name: theme for theme in (NEUTRAL, PALACE, DESERT, CAVERNS, RUINS, TEMPLE)}

_current = NEUTRAL


def current():
    return _current


def use(theme):
    """Select the theme that the menu pages draw with from now on."""
    global _current
    _current = theme if theme is not None else NEUTRAL
    return _current


def c(neutral):
    """The current theme's colour for a neutral menu colour."""
    key = neutral.lower()
    themed = _current.colours.get(key, key)
    return neutral if themed == key else themed


def theme_for(game):
    """The menu theme of the level being played; neutral where none is drawn.

    POP2_MENU_THEME names one theme to use everywhere instead ("neutral" turns
    the level themes off); the test suite sets it so that layout tests keep
    checking the neutral look whatever level their scene loads.
    """
    forced = THEMES.get(os.environ.get('POP2_MENU_THEME', '').strip().lower())
    if forced is not None:
        return forced
    if game is None:
        return NEUTRAL
    if getattr(game, 'caverns', None) is not None:
        # Ruins, temple and the last level (kind 6) share the cavern state object.
        return {3: CAVERNS, 4: RUINS, 2: TEMPLE}.get(getattr(game.level, 'kind', None), NEUTRAL)
    if getattr(game, 'desert', None) is not None:
        return DESERT
    if getattr(game, 'harbor', None) is not None:
        return PALACE
    return NEUTRAL


_ROCK_THICKNESS = 9
# The area menus may cover: the room, above the health strip.
_LIMIT = (1, 0, 510, 364)
# Pages drawn at the window's resolution cover the health strip as well.
_SCREEN = (1, 0, 510, 383)


def frame_rect(rect, theme=None, clear_sides=False, limit=_LIMIT):
    """Where a panel's frame is drawn: the panel grown by the theme's margins.

    A page whose content reaches the panel's sides asks for clear sides: the
    frame then stands wholly outside the panel there.
    """
    theme = theme or _current
    side, top, bottom = theme.grow
    if clear_sides:
        side = max(side, theme.frame_width)
    return (max(limit[0], rect[0] - side), max(limit[1], rect[1] - top),
            min(limit[2], rect[2] + side), min(limit[3], rect[3] + bottom))


def panel(image, rect, clear_sides=False):
    """Draw a menu panel: its fill and the current theme's frame, in place."""
    theme = _current
    if theme.frame is None:
        ImageDraw.Draw(image).rectangle(rect, fill=c('#181818'), outline=c('#858585'))
        return
    outer = frame_rect(rect, theme, clear_sides)
    size = (outer[2] - outer[0] + 1, outer[3] - outer[1] + 1)
    picture = _frame_picture(theme.name, size)
    image.paste(picture, outer[:2], picture)


def panel_scaled(image, rect, point):
    """Draw a framed panel on a page drawn at the window's resolution.

    ``point`` maps the page's 512x384 coordinates to the image's pixels. The
    frame is drawn at the game's resolution and enlarged without smoothing,
    like the rest of the page. Returns False for a theme without a frame, and
    the page then draws its own plain rectangle.
    """
    theme = _current
    if theme.frame is None:
        return False
    outer = frame_rect(rect, theme, True, _SCREEN)
    size = (outer[2] - outer[0] + 1, outer[3] - outer[1] + 1)
    left, top = point(outer[0], outer[1])
    right, bottom = point(outer[2] + 1, outer[3] + 1)
    scaled = max(1, right - left), max(1, bottom - top)
    key = theme.name, size, scaled
    if key not in _frames:
        if len(_frames) > 24:
            _frames.clear()
        _frames[key] = _frame_picture(theme.name, size).resize(scaled, Image.Resampling.NEAREST)
    image.paste(_frames[key], (left, top), _frames[key])
    return True


_frames = {}


def _frame_picture(name, size):
    key = name, size
    if key not in _frames:
        theme = THEMES[name]
        fill = _rgb(theme.colour('panel'))
        _frames[key] = _PAINTERS[theme.frame](theme, size, fill)
    return _frames[key]


def _rgb(colour):
    return tuple(int(colour[i:i + 2], 16) for i in (1, 3, 5))


def _band_frame(theme, size, fill):
    """A straight moulding: the same rows on every side, mitred at the corners."""
    width, height = size
    picture = Image.new('RGBA', size, fill + (255,))
    pixels = picture.load()
    rng = random.Random(0xC0)
    bands = [[_rgb(colour) + (255,) for colour in band] for band in theme.bands]
    for y in range(height):
        for x in range(width):
            vertical, horizontal = min(y, height - 1 - y), min(x, width - 1 - x)
            depth = min(vertical, horizontal)
            if depth < len(bands):
                band = bands[depth]
                pixels[x, y] = band[0] if len(band) == 1 else rng.choice(band)
    return picture


# --- A strip of rough stone with a worn edge and no outline.
_ROCK_RUNS = (1,) * 47 + (2,) * 9 + (3,) * 3 + (4, 5)


def _worn(length, rng, corner):
    """An edge that steps in and out by a pixel, with a shallow bite now and then."""
    edge = []
    while len(edge) < length:
        edge += [rng.choice((0, 0, 0, 1, 1))] * rng.randint(4, 12)
    edge = edge[:length]
    position = rng.randint(10, 30)
    while position < length - 12:
        for index, depth in enumerate(rng.choice(((1, 2, 2, 1), (2, 2, 2), (1, 2, 2, 2, 1)))):
            edge[position + index] = max(edge[position + index], depth)
        position += rng.randint(40, 90)
    for index, depth in enumerate(corner):
        if index < length:
            edge[index] = max(edge[index], depth)
            edge[length - 1 - index] = max(edge[length - 1 - index], depth)
    return edge


def _rock_frame(theme, size, fill):
    width, height = size
    thickness = _ROCK_THICKNESS
    rng = random.Random(width * 1000 + height)
    corner = (3, 2, 1)
    top_out, bottom_out = _worn(width, rng, corner), _worn(width, rng, corner)
    left_out, right_out = _worn(height, rng, corner), _worn(height, rng, corner)
    top_in, bottom_in = _worn(width, rng, ()), _worn(width, rng, ())
    left_in, right_in = _worn(height, rng, ()), _worn(height, rng, ())

    def solid(x, y):
        return (0 <= x < width and 0 <= y < height
                and top_out[x] <= y <= height - 1 - bottom_out[x]
                and left_out[y] <= x <= width - 1 - right_out[y])

    def hole(x, y):
        return (0 <= x < width and 0 <= y < height
                and thickness + top_in[x] <= y <= height - 1 - thickness - bottom_in[x]
                and thickness + left_in[y] <= x <= width - 1 - thickness - right_in[y])

    def rock(x, y):
        return solid(x, y) and not hole(x, y)

    grain_rng = random.Random(0x60C)
    shades = [_rgb(colour) for colour, _count in theme.grain]
    weights = [count for _colour, count in theme.grain]
    every_shade = tuple(shades) + tuple(_rgb(colour) for colour in theme.shades)
    period = 240
    grain = []
    for _row in range(thickness + 4):
        row = []
        while len(row) < period:
            row += [grain_rng.choices(shades, weights)[0]] * grain_rng.choice(_ROCK_RUNS)
        grain.append(row[:period])

    picture = Image.new('RGBA', size, (0, 0, 0, 0))
    pixels = picture.load()
    opaque_fill = fill + (255,)
    for y in range(height):
        for x in range(width):
            if hole(x, y):
                # The rock stands proud of the panel: a hard shadow below and beside it.
                pixels[x, y] = (0, 0, 0, 255) if rock(x, y - 1) or rock(x - 1, y) else opaque_fill
                continue
            if not solid(x, y):
                continue
            vertical, horizontal = min(y, height - 1 - y), min(x, width - 1 - x)
            depth = min(vertical, horizontal, len(grain) - 1)
            shade = 1.0
            if not rock(x - 1, y):
                shade = 1.15
            if not rock(x + 1, y):
                shade = 0.7
            if not rock(x, y - 1):
                shade = 1.3
            if not rock(x, y + 1):
                shade = 0.6
            colour = grain[depth][(x if vertical <= horizontal else y) % period]
            if shade != 1.0:
                lit = tuple(channel * shade for channel in colour)
                colour = min(every_shade, key=lambda s: sum((a - b) ** 2 for a, b in zip(s, lit)))
            pixels[x, y] = colour + (255,)
    return picture


# --- Shared helpers for the drawn frames.
_THICKNESS = {'rock': (9, 9, 9), 'sand': (11, 11, 11), 'studs': (9, 9, 9), 'pillars': (13, 10, 10),
              'columns': (13, 12, 12)}


def _stepped(length, rng, values, runs=(5, 14)):
    line = []
    while len(line) < length:
        line += [rng.choice(values)] * rng.randint(*runs)
    return line[:length]


def _stamp(pixels, left, top, rows, colours, mirror=False):
    """Draw a small picture given as rows of letters; '.' leaves the pixel alone."""
    for j, row in enumerate(rows):
        for i, letter in enumerate(reversed(row) if mirror else row):
            if letter != '.':
                pixels[left + i, top + j] = colours[letter]


# --- The desert: a band of sand with wind ripples, wet where it meets the sea panel.
_STARFISH = ('...s...', '...s...', 'sssssss', '.sstss.', '..sss..', '.ss.ss.', '.s...s.')


def _sand_frame(theme, size, fill):
    width, height = size
    thickness, radius = _THICKNESS['sand'][0], 14
    rng = random.Random(width * 1000 + height)
    longest = max(width, height)
    damp = {side: _stepped(longest, rng, (0, 0, 1), (8, 20)) for side in range(4)}
    edge, crest, sand, ripple, shade, wet, wetter = (_rgb(colour) + (255,) for colour in (
        '#d5a056', '#fedea5', '#f2cd8d', '#ecbc86', '#d8ab71', '#b78742', '#91622b'))
    grains = [sand] * 40 + [ripple] * 7 + [crest] * 4 + [shade] * 2
    picture = Image.new('RGBA', size, (0, 0, 0, 0))
    pixels = picture.load()
    for y in range(height):
        for x in range(width):
            dx, dy = min(x, width - 1 - x), min(y, height - 1 - y)
            if dx < radius and dy < radius:
                depth = radius - ((radius - dx - 0.5) ** 2 + (radius - dy - 0.5) ** 2) ** 0.5
            else:
                depth = min(dx, dy)
            if depth < 0:
                continue
            depth = int(depth)
            if dy <= dx:
                side, along = (0 if y < height // 2 else 1), x
            else:
                side, along = (2 if x < width // 2 else 3), y
            if depth == 0:
                colour = edge
            elif depth == 1:
                colour = crest
            elif depth >= thickness:
                colour = fill + (255,)
            elif depth == thickness - 1:
                colour = wetter
            elif depth == thickness - 2 or (depth == thickness - 3 and damp[side][along]):
                colour = wet
            else:
                colour = rng.choice(grains)
            pixels[x, y] = colour

    def place(side, along, depth):
        return ((along, depth), (along, height - 1 - depth), (depth, along), (width - 1 - depth, along))[side]

    # What the wind leaves on sand, no two alike: dunes, hollows, streaks, pebbles.
    pebble = _rgb('#b78742') + (255,)
    for side in range(4):
        along = radius + 3
        end = (width if side < 2 else height) - radius - 3
        while along < end - 14:
            kind = rng.choice(('dune', 'dune', 'hollow', 'streak', 'streak', 'streak', 'pebble', 'pair'))
            depth = rng.randint(3, 6)
            length = 2
            if kind in ('dune', 'hollow'):
                length = rng.randint(4, 11)
                tips = rng.randint(1, max(1, length // 3))
                for index in range(length):
                    tip = index < tips or index >= length - rng.randint(1, tips)
                    row = depth + ((1 if kind == 'dune' else -1) if tip else 0)
                    pixels[place(side, along + index, row)] = shade
                    if not tip and rng.random() < 0.8:
                        pixels[place(side, along + index, row + (-1 if kind == 'dune' else 1))] = (
                            crest if kind == 'dune' else ripple)
            elif kind == 'streak':
                length = rng.randint(5, 15)
                row = depth
                for index in range(length):
                    if rng.random() < 0.22:
                        row = min(6, max(3, row + rng.choice((-1, 1))))
                    pixels[place(side, along + index, row)] = shade if rng.random() < 0.8 else ripple
                    if index < length // 2 and rng.random() < 0.6:
                        pixels[place(side, along + index, row - 1)] = crest
            elif kind == 'pebble':
                pixels[place(side, along, depth)] = pebble
                pixels[place(side, along + 1, depth)] = pebble if rng.random() < 0.6 else shade
                pixels[place(side, along, depth - 1)] = crest
            else:
                length = rng.randint(5, 8)
                for index in range(length):
                    if index < length - 2:
                        pixels[place(side, along + index, depth - 1)] = shade
                    if index > 1:
                        pixels[place(side, along + index, depth + 1)] = shade
            along += length + rng.randint(4, 18)
    _stamp(pixels, 17, height - 9, _STARFISH, {'s': _rgb('#d26a14') + (255,), 't': _rgb('#8e4106') + (255,)})
    return picture


# --- The ruins: a worn band of dressed stone with the wall's row of small square
# studs, and the serpent sign cut into each corner block.
_SERPENT = (
    '....####.#',
    '...#....#.',
    '...#......',
    '....#.....',
    '.....#....',
    '......#...',
    '.####..#..',
    '#....#..#.',
    '#.#..#..#.',
    '#..##...#.',
    '.#.....#..',
    '..#####...',
)
_CORNER = 15


def _studs_frame(theme, size, fill):
    width, height = size
    thickness = _THICKNESS['studs'][0]
    lit, face, body, dark, deep = (_rgb(colour) + (255,) for colour in (
        '#9a93b5', '#736b96', '#5c5485', '#332a67', '#251c5d'))
    marble = [_rgb('#5c5485')] * 5 + [_rgb('#534b7e')] * 3 + [_rgb('#4e467b')]
    stain = {_rgb('#5c5485'): _rgb('#4a4178'), _rgb('#534b7e'): _rgb('#413871'), _rgb('#4e467b'): _rgb('#3c336e')}
    rng = random.Random(0x5D)
    wear = random.Random(width * 1000 + height)
    longest = max(width, height)
    # Where damp has darkened the stone, and where the edges have crumbled.
    stained = {side: _stepped(longest, wear, (0, 0, 0, 1), (10, 34)) for side in range(4)}
    outer = {side: _worn(longest, wear, ()) for side in range(4)}
    inner = {side: _stepped(longest, wear, (0, 0, 0, 0, 1), (3, 9)) for side in range(4)}
    picture = Image.new('RGBA', size, fill + (255,))
    pixels = picture.load()
    opaque_fill = fill + (255,)

    for y in range(height):
        run, colour = 0, marble[0]
        for x in range(width):
            dx, dy = min(x, width - 1 - x), min(y, height - 1 - y)
            corner = dx < _CORNER and dy < _CORNER
            depth = min(dx, dy)
            if depth >= thickness and not corner:
                continue
            if run == 0:
                run, colour = rng.choice(_ROCK_RUNS) + 1, rng.choice(marble)
            run -= 1
            upper = (dy <= dx and y < height // 2) or (dx < dy and x < width // 2)
            if corner:
                # A square block: lit above and on the left, dark below and on the right.
                cx = x if x < _CORNER else x - (width - _CORNER)
                cy = y if y < _CORNER else y - (height - _CORNER)
                if cy == 0 or cx == 0:
                    pixels[x, y] = lit
                elif cy == _CORNER - 1 or cx == _CORNER - 1:
                    pixels[x, y] = deep
                else:
                    pixels[x, y] = face
                continue
            if dy <= dx:
                side, along = (0 if y < height // 2 else 1), x
            else:
                side, along = (2 if x < width // 2 else 3), y
            if depth < outer[side][along]:
                pixels[x, y] = (0, 0, 0, 0)
            elif depth == outer[side][along]:
                pixels[x, y] = lit if upper else dark
            elif depth >= thickness - inner[side][along]:
                pixels[x, y] = opaque_fill
            elif depth == thickness - 1 - inner[side][along]:
                pixels[x, y] = deep if upper else face
            else:
                pixels[x, y] = (stain[colour] if stained[side][along] else colour) + (255,)

    def stud(left, top):
        fate = wear.random()
        for j in range(3):
            for i in range(3):
                if fate < 0.16:      # fallen out: an empty socket
                    shade = deep if i + j < 2 else dark if i + j == 2 else body
                elif i + j < 2:
                    shade = lit
                elif i + j == 2:
                    shade = face
                else:
                    shade = dark
                if 0.16 <= fate < 0.30 and i + j > 2:
                    continue         # chipped: only its lit half is left
                pixels[left + i, top + j] = shade

    for length, place in ((width, lambda at: ((at, 3), (at, height - 6))),
                          (height, lambda at: ((3, at), (width - 6, at)))):
        room = length - 2 * _CORNER - 2
        count = (room + 3) // 6
        start = _CORNER + 1 + (room - (count * 6 - 3)) // 2
        for index in range(count):
            for left, top in place(start + index * 6):
                stud(left, top)
    for left, mirror in ((0, False), (width - _CORNER, True)):
        for top in (0, height - _CORNER):
            _stamp(pixels, left + 3 - mirror, top + 2, _SERPENT, {'#': deep}, mirror)
    return picture


# --- The temple: carved red stone. Two columns with leaf capitals carry a lintel
# with a frieze of rosettes between leaves; a moulded base runs below.
_FRIEZE = (
    '........................',
    '....hh...hhh...hh.......',
    '...hoo..hoooo..ooh..hh..',
    '..hood..ooooo..dooh.od..',
    '..ood...ooood...doo.dd..',
    '..dd.....ddd.....dd.....',
    '........................',
)
_CAPITAL = (
    'ddddddddddddd',
    'hhhhhhhhhhhho',
    'ooooooooooood',
    'ddddddddddddd',
    'dhoodhoodhood',
    'dhoodhoodhood',
    'ddhoddhoddhod',
    '.ddddddddddd.',
    '.ohhhbhhoood.',
    '.ddddddddddd.',
)
_PLINTH = (
    '.ddddddddddd.',
    '.ohhhbhhoood.',
    'ddddddddddddd',
    'hhhhhhhhhhhho',
    'hoooooooooood',
    'hoddddddddhod',
    'hodooooooohod',
    'hodhhhhhhhhod',
    'hoooooooooood',
    'ddddddddddddd',
)
_CORNER_ROSETTE = (
    'd...........d',
    'd.h..hhh..h.d',
    'd...hoooo...d',
    'd...ooooo...d',
    'd...ooood...d',
    'd.h..ddd..h.d',
    'd...........d',
)
_BEAD = ('hh', 'od', 'dd')


def _columns_frame(theme, size, fill):
    width, height = size
    side, top, bottom = _THICKNESS['columns']
    colours = {letter: _rgb(colour) + (255,) for letter, colour in (
        ('.', '#520808'), ('o', '#731100'), ('h', '#a1251e'), ('b', '#c8402a'), ('d', '#210000'))}
    shaft = [_rgb(colour) + (255,) for colour in (
        '#210000', '#390800', '#520808', '#631810', '#7b2108', '#a1251e', '#8a2414', '#731100', '#631810',
        '#520808', '#210000')]
    shadow = _rgb(theme.colour('well_dark')) + (255,)
    lit, face, low, dark = (_rgb(colour) + (255,) for colour in ('#7b2910', '#731100', '#631810', '#210000'))
    opaque_fill = fill + (255,)
    picture = Image.new('RGBA', size, opaque_fill)
    pixels = picture.load()
    under = height - bottom

    # The same carved band above and below; its fillet is on the panel's side.
    for start, edge_rows, frieze_top in ((0, ((0, lit), (1, face), (9, dark), (10, low), (11, dark)), 2),
                                         (under, ((0, dark), (1, low), (2, dark), (10, face), (11, dark)), 3)):
        for x in range(width):
            for row, colour in edge_rows:
                pixels[x, start + row] = colour
            for row in range(7):
                pixels[x, start + frieze_top + row] = colours['.']
        # Whole motifs only, spread evenly between the two corner blocks.
        room = width - 2 * side
        count = max(1, round(room / 24))
        for index in range(count):
            left = side + round((index + 0.5) * room / count - 8.5)
            _stamp(pixels, left, start + frieze_top, [row[2:19] for row in _FRIEZE], colours)
            if index:
                _stamp(pixels, side + round(index * room / count) - 1, start + frieze_top + 2, _BEAD, colours)
        for left in (0, width - side):
            _stamp(pixels, left, start + frieze_top, _CORNER_ROSETTE, colours)
    for x in range(side, width - side):
        pixels[x, top] = shadow

    for left in (0, width - side):
        outside = 0 if left == 0 else side - 1
        for y in range(top, under):
            below, above = y - top, under - 1 - y
            if below < len(_CAPITAL):
                letters = _CAPITAL[below]
            elif above < len(_PLINTH):
                letters = _PLINTH[len(_PLINTH) - 1 - above]
            else:
                letters = None
            for across in range(side):
                x = left + across
                if letters is None:
                    if across in (0, side - 1):
                        # The shaft is slimmer: the room shows outside it, the panel inside.
                        if across == outside:
                            pixels[x, y] = (0, 0, 0, 0)
                        continue
                    # Joints between the drums: a dark line that sags, with light under it.
                    joint = (below - len(_CAPITAL)) % 44
                    sag = 1 if 2 < across < side - 3 else 0
                    if joint == 30 + sag:
                        pixels[x, y] = shaft[0]
                    elif joint == 31 + sag and sag:
                        pixels[x, y] = colours['b']
                    else:
                        pixels[x, y] = shaft[across - 1]
                elif letters[across] == '.' and across in (0, side - 1):
                    pixels[x, y] = (0, 0, 0, 0) if across == outside else opaque_fill
                else:
                    pixels[x, y] = colours[letters[across]]
    for y in range(top + 1, under):
        if pixels[side, y] == opaque_fill:
            pixels[side, y] = shadow
    return picture


# --- The ruins, second idea: a fine palace doorway falling apart. Two tall pale
# pillars with dark carved panels stand between slabs with a carved line; the
# edges are straight, and the ruin shows as broken-out pieces and cracks. The
# invaders' serpent sign is left on the panel like a watermark.
_BREAK = (1, 1, 1, 2, 2, 2, 3, 3, 2, 3, 4, 4, 4, 5, 5, 4, 5, 6, 6, 7, 6, 7, 7, 8, 7, 8, 6, 4, 3, 1)


def _serpent_mark():
    """The serpent sign, large: a hooked neck over a coil, as a 24x27 mask."""
    image = Image.new('L', (24, 27), 0)
    draw = ImageDraw.Draw(image)
    points = [(19, 3), (16, 1), (12, 1), (9, 3), (9, 6), (12, 8), (15, 10), (18, 13)]
    for step in range(33):
        angle = math.radians(-20 + step * 17.5)
        radius = 7.5 - step * 0.17
        points.append((10 + radius * math.cos(angle), 17 + radius * math.sin(angle)))
    draw.line(points, fill=255, width=2)
    draw.rectangle((19, 2, 21, 4), fill=255)   # the head
    draw.point((22, 1), fill=255)              # and its tongue
    return image


def _pillars_frame(theme, size, fill):
    width, height = size
    side, top, bottom = _THICKNESS['pillars']

    def shades(*pairs):
        return [_rgb(colour) + (255,) for colour, count in pairs for _ in range(count)]

    stone = shades(('#715771', 10), ('#5f4566', 5), ('#64577a', 2), ('#404d5b', 1), ('#6c5647', 1))
    plain = shades(('#715771', 8), ('#6f5264', 2), ('#5f4566', 1))
    pale = shades(('#ad8d8d', 5), ('#a07f7f', 3), ('#987b66', 2), ('#876e6e', 1))
    edge, rim, light, gold, dusk, night, pit, teal, mid = (_rgb(colour) + (255,) for colour in (
        '#5f4566', '#876e6e', '#a07f7f', '#ead99a', '#463333', '#3b3030', '#261f1f', '#404d5b', '#795e79'))
    shadow = _rgb(theme.colour('well_dark')) + (255,)
    opaque_fill = fill + (255,)
    rng = random.Random(0x5D)
    wear = random.Random(width * 1000 + height)
    picture = Image.new('RGBA', size, opaque_fill)
    pixels = picture.load()
    under = height - bottom

    # The sign on the panel, either side of where a page's title goes.
    mark = _serpent_mark()
    tint = Image.new('RGBA', mark.size, _rgb(theme.colour('row')) + (255,))
    if width > 2 * side + 150 and height > top + bottom + 60:
        picture.paste(tint, (side + 18, top + 3), mark)
        picture.paste(tint, (width - side - 18 - mark.width, top + 3), mark)

    # The slabs: straight, with a carved line. A piece has broken out of each.
    gaps = {0: side + (width - 2 * side) * 2 // 3, under: side + (width - 2 * side) // 5}
    for start, outer_first in ((0, True), (under, False)):
        thick = top if outer_first else bottom
        gone = [0] * width
        broken = width > 2 * side + 3 * len(_BREAK)     # small dialogs keep whole slabs
        for index, depth in enumerate(_BREAK if broken else ()):
            gone[gaps[start] + index] = depth
        for row in range(thick):
            run, colour = 0, stone[0]
            depth = row if outer_first else thick - 1 - row     # from the outer edge
            for x in range(width):
                if run == 0:
                    run, colour = rng.choice(_ROCK_RUNS) + 1, rng.choice(stone)
                run -= 1
                if depth < gone[x]:
                    pixels[x, start + row] = (0, 0, 0, 0)
                elif gone[x] and depth == gone[x]:
                    pixels[x, start + row] = light if outer_first else night   # the broken face
                elif row == 0:
                    pixels[x, start + row] = light
                elif row == thick - 1:
                    pixels[x, start + row] = dusk
                elif row == 3:
                    pixels[x, start + row] = edge      # the carved line and the light under it
                elif row == 4:
                    pixels[x, start + row] = rim
                else:
                    pixels[x, start + row] = colour
        # A crack runs on from the deepest point of the break.
        if not broken:
            continue
        x = gaps[start] + _BREAK.index(max(_BREAK))
        rows = range(max(_BREAK) + 1, thick - 1) if outer_first else range(thick - 2 - max(_BREAK), 0, -1)
        for row in rows:
            pixels[x, start + row] = night
            x += wear.choice((-1, 0, 1, 1))
    for x in range(side, width - side):
        pixels[x, top] = shadow

    veins = _stepped(height, wear, (0, 0, 0, 1), (3, 9))
    flare, foot = 5, 9
    for left in (0, width - side):
        outside = 0 if left == 0 else side - 1
        for y in range(top, under):
            below, above = y - top, under - 1 - y
            for at in range(side):      # both pillars face the same way: light from the right
                if below < flare:
                    # The capital widens up to the slab.
                    inset = 0 if below < 2 else 1
                    if at < inset or at > side - 1 - inset:
                        colour = (0, 0, 0, 0) if (at < inset) == (outside == 0) else opaque_fill
                    else:
                        colour = dusk if below < 2 else mid if below == flare - 1 else edge
                elif above < foot:
                    step = foot - 1 - above
                    sunny = at >= 9
                    colour = (
                        edge, gold if sunny else mid, light if sunny else edge, gold if sunny else rim,
                        rng.choice(pale) if sunny else rng.choice(plain),
                        rng.choice(pale) if sunny else rng.choice(plain), edge,
                        rim if sunny else night, rim if sunny else night,
                    )[step]
                elif at == 0:
                    colour = edge
                elif at == side - 1:
                    colour = rim
                elif at >= 9:
                    colour = rng.choice(pale)
                elif at == 8:
                    colour = mid
                elif at < 3 or below < flare + 2 or above < foot + 2:
                    colour = rng.choice(plain)
                elif at == 3 or below == flare + 2:
                    colour = pit
                else:
                    # The carved panel: dark lines that swing from side to side.
                    swing = (y // 2) % 8
                    swing = swing if swing < 4 else 8 - swing
                    colour = (pit, night, teal if veins[y] else dusk, night)[(at - 4 + swing) % 4]
                pixels[left + at, y] = colour
    # The right pillar has lost a piece of its lit face, and a crack runs up from it.
    if under - top < 120:
        return picture
    y = top + (under - top) * 3 // 5
    for index, depth in enumerate((1, 1, 2, 3, 3, 4, 4, 3, 4, 4, 3, 2, 2, 1)):
        for at in range(side - depth, side):
            pixels[width - side + at, y + index] = (0, 0, 0, 0)
        pixels[width - depth - 1, y + index] = night
    x = width - 5
    for row in range(1, 16):
        pixels[x, y - row] = night
        x -= wear.choice((0, 0, 1)) if x > width - side + 9 else 0
    return picture


_PAINTERS = {'rock': _rock_frame, 'bands': _band_frame, 'sand': _sand_frame,
             'studs': _studs_frame, 'pillars': _pillars_frame, 'columns': _columns_frame}
