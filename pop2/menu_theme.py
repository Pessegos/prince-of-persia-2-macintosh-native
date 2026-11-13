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

import functools
import os
import random
from dataclasses import dataclass, field

import numpy
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
    # The Cutscene Viewer's own neutral colours.
    'card': '#252525', 'card_selected': '#493c25', 'card_hover': '#c6b58c', 'viewer_edge': '#8c7954',
    'track': '#282828', 'track_thumb': '#999076', 'off': '#505050',
}
# A theme that does not name one of these roles uses its colour for another.
_ROLE_FALLBACK = {
    'card': 'row', 'card_selected': 'selected', 'card_hover': 'row_edge_lit', 'viewer_edge': 'panel_edge',
    'track': 'row_dark', 'track_thumb': 'row_edge_lit', 'off': 'faint',
}


@dataclass(frozen=True)
class MenuTheme:
    name: str
    roles: dict = field(default_factory=dict)
    dim: int = 100            # black veil over the room behind the F1 menu, 0-255
    # 'rock', 'bands', 'sand', 'studs', 'columns' or None for a plain outline
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
    # A sign left faintly on the page, given as the colour it leans towards.
    mark: str | None = None

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
            neutral: self.roles.get(role, self.roles.get(_ROLE_FALLBACK.get(role), neutral))
            for role, neutral in NEUTRAL_ROLES.items()})

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
}, dim=120, frame='studs', grow=(2, 5, 7), mark='#04011c')

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
}, dim=140, frame='columns', grow=(2, 5, 7))

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


def panel_scaled(image, rect, point, limit=None):
    """Draw a framed panel on a page drawn at the window's resolution.

    ``point`` maps the page's 512x384 coordinates to the image's pixels. The
    frame is drawn at the game's resolution and enlarged without smoothing,
    like the rest of the page. Returns False for a theme without a frame, and
    the page then draws its own plain rectangle. A page laid out wider than
    the game's picture gives its own ``limit``, the area its frame may cover.
    """
    theme = _current
    if theme.frame is None:
        return False
    outer = frame_rect(rect, theme, True, limit or _SCREEN)
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


def _edge_columns(width, height, y, margin):
    """The columns of row ``y`` that lie within ``margin`` of the picture's edge.

    The painters only visit these: a frame is a thin band, and visiting every
    pixel of the panel inside it made a menu hesitate the first time it opened.
    """
    if y < margin or y >= height - margin or width <= 2 * margin:
        return range(width)
    return (*range(margin), *range(width - margin, width))


def _fill_inside(picture, margin, colour):
    if picture.width > 2 * margin and picture.height > 2 * margin:
        picture.paste(colour, (margin, margin, picture.width - margin, picture.height - margin))


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
        for x in _edge_columns(width, height, y, len(bands)):
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

    @functools.lru_cache(maxsize=None)     # each pixel is asked about by its four neighbours
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

    @functools.lru_cache(maxsize=None)     # few grain colours, four ways of lighting them
    def nearest(colour, shade):
        lit = tuple(channel * shade for channel in colour)
        return min(every_shade, key=lambda s: sum((a - b) ** 2 for a, b in zip(s, lit)))

    picture = Image.new('RGBA', size, (0, 0, 0, 0))
    opaque_fill = fill + (255,)
    _fill_inside(picture, thickness + 4, opaque_fill)
    pixels = picture.load()
    for y in range(height):
        for x in _edge_columns(width, height, y, thickness + 4):
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
                colour = nearest(colour, shade)
            pixels[x, y] = colour + (255,)
    return picture


# --- Shared helpers for the drawn frames.
_THICKNESS = {'rock': (9, 9, 9), 'sand': (11, 11, 11), 'studs': (9, 9, 9), 'columns': (13, 12, 12)}


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
    _fill_inside(picture, radius, fill + (255,))
    pixels = picture.load()
    for y in range(height):
        for x in _edge_columns(width, height, y, radius):
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


# --- The ruins: the palace wall's band of square sockets, in straight dressed
# stone that has started to fall apart. Every damaged place is different: a
# piece broken out, a flake off the surface, a nick, a crack. A carved ring
# marks each corner, as on the wall's arches.
_RING = (
    '.........',
    '..dddd...',
    '.d...ll..',
    '.d.dd.l..',
    '.d.d..l..',
    '.d...ll..',
    '..llll...',
    '.........',
    '.........',
)
# The kinds of damage, and how often each turns up along a side. Small panels
# get only the lighter kinds.
_DAMAGE = ('break', 'flake', 'nick', 'crack', 'split', 'inside', 'socket', 'socket', 'nick', 'crack')
_LIGHT_DAMAGE = ('nick', 'crack', 'inside', 'socket')


def _broken_edge(rng, length, deepest):
    """How deep a broken-out piece reaches at each step: ragged and lopsided."""
    peak = rng.randint(length // 4, length * 3 // 4)
    edge = []
    for index in range(length):
        share = index / peak if index < peak else (length - 1 - index) / max(1, length - 1 - peak)
        depth = 1 + round((deepest - 1) * share) + rng.choice((-1, 0, 0, 0, 1))
        edge.append(min(deepest, max(1, depth)))
    return edge


def _studs_frame(theme, size, fill):
    width, height = size
    thickness = _THICKNESS['studs'][0]
    lit, face, dark, deep, sunk = (_rgb(colour) + (255,) for colour in (
        '#9a93b5', '#736b96', '#332a67', '#251c5d', '#413871'))
    marble = [_rgb('#5c5485')] * 5 + [_rgb('#534b7e')] * 3 + [_rgb('#4e467b')]
    stain = {_rgb('#5c5485'): _rgb('#4a4178'), _rgb('#534b7e'): _rgb('#413871'), _rgb('#4e467b'): _rgb('#3c336e')}
    rng = random.Random(0x5D)
    wear = random.Random(width * 1000 + height)
    longest = max(width, height)
    stained = [_stepped(longest, wear, (0, 0, 0, 1), (10, 34)) for _side in range(4)]
    opaque_fill = fill + (255,)
    picture = Image.new('RGBA', size, opaque_fill)
    pixels = picture.load()

    def place(side, along, depth):
        return ((along, depth), (along, height - 1 - depth), (depth, along), (width - 1 - depth, along))[side]

    # Walk along each side and damage it here and there, never twice the same way running.
    gone = [[0] * longest for _side in range(4)]      # broken out of the outer edge
    eaten = [[0] * longest for _side in range(4)]     # broken out of the inner edge
    cracks, crumbled = [], []
    for side in range(4):
        length = width if side < 2 else height
        kinds = _DAMAGE if length >= 150 else _LIGHT_DAMAGE
        along = thickness + wear.randint(6, 22)
        last = None
        while along < length - thickness - 30:
            kind = wear.choice([kind for kind in kinds if kind != last])
            last = kind
            span = 0
            if kind == 'break':
                edge = _broken_edge(wear, wear.randint(10, 19), wear.randint(3, 5))
                if wear.random() < 0.6:
                    cracks.append((side, along + edge.index(max(edge)), max(edge) + 1, thickness - 1))
            elif kind == 'flake':
                edge = [wear.choice((1, 1, 2)) for _step in range(wear.randint(12, 30))]
                edge[0] = edge[-1] = 1
            elif kind == 'nick':
                edge = _broken_edge(wear, wear.randint(3, 7), wear.randint(1, 3))
            else:
                edge = []
            if kind == 'inside':
                bite = _broken_edge(wear, wear.randint(4, 11), wear.randint(1, 3))
                for index, depth in enumerate(bite):
                    eaten[side][along + index] = depth
                span = len(bite)
            elif kind == 'crack':
                cracks.append((side, along, 1, wear.randint(4, 7)))
            elif kind == 'split':
                # A crack right through the band, with a second one branching off it.
                cracks.append((side, along, 0, thickness))
                cracks.append((side, along + 1, wear.randint(3, 5), thickness - 1))
            elif kind == 'socket':
                crumbled.append((side, along))
            for index, depth in enumerate(edge):
                gone[side][along + index] = depth
            along += max(span, len(edge)) + wear.randint(14, 46)

    # One corner has come away altogether.
    lost = wear.randrange(4) if min(width, height) >= 150 else None
    ragged = [wear.choice((6, 7, 7, 8, 9)) for _step in range(2 * thickness + 8)]

    for y in range(height):
        run, colour = 0, marble[0]
        for x in _edge_columns(width, height, y, thickness):
            dx, dy = min(x, width - 1 - x), min(y, height - 1 - y)
            depth = min(dx, dy)
            if depth >= thickness:
                continue
            if run == 0:
                run, colour = rng.choice(_ROCK_RUNS) + 1, rng.choice(marble)
            run -= 1
            if dy <= dx:
                side, along = (0 if y < height // 2 else 1), x
            else:
                side, along = (2 if x < width // 2 else 3), y
            upper = side in (0, 2)
            missing, bitten = gone[side][along], eaten[side][along]
            if depth < missing:
                pixels[x, y] = (0, 0, 0, 0)
            elif missing and depth == missing:
                pixels[x, y] = deep        # the broken face
            elif depth >= thickness - bitten:
                continue                   # the panel shows where the inner edge is gone
            elif bitten and depth == thickness - 1 - bitten:
                pixels[x, y] = dark
            elif depth == 0:
                pixels[x, y] = lit if upper else dark
            elif depth == thickness - 1:
                pixels[x, y] = deep if upper else face
            else:
                pixels[x, y] = (stain[colour] if stained[side][along] else colour) + (255,)

    # The sockets: sunk squares, dark under their upper and left rims.
    solid = set(marble) | set(stain.values())
    for side in range(4):
        length = width if side < 2 else height
        room = length - 2 * thickness - 2
        count = (room + 3) // 8
        start = thickness + 1 + (room - (count * 8 - 3)) // 2
        for index in range(count):
            for i in range(5):
                for j in range(5):
                    x, y = place(side, start + index * 8 + i, 2 + j)
                    if pixels[x, y][:3] not in solid:
                        continue           # broken away here
                    dx, dy = (i, j) if side < 2 else (j, i)
                    if side == 1:
                        dy = 4 - dy
                    if side == 3:
                        dx = 4 - dx
                    pixels[x, y] = deep if dy == 0 or dx == 0 else face if dy == 4 or dx == 4 else sunk
        # A socket whose rim has crumbled: the hollow has spread unevenly around it.
        for crumbled_side, along in crumbled:
            if crumbled_side != side:
                continue
            first = start + max(0, min(count - 1, (along - start) // 8)) * 8
            for _grain in range(wear.randint(5, 9)):
                i, j = wear.choice(((-1, wear.randint(0, 4)), (5, wear.randint(0, 4)),
                                    (wear.randint(0, 4), -1), (wear.randint(0, 4), 5),
                                    (wear.randint(1, 3), 4), (4, wear.randint(1, 3))))
                x, y = place(side, first + i, 2 + j)
                if pixels[x, y][3]:
                    pixels[x, y] = sunk if wear.random() < 0.6 else deep
    for corner, (left, top) in enumerate(((0, 0), (width - thickness, 0), (0, height - thickness),
                                          (width - thickness, height - thickness))):
        _stamp(pixels, left, top, _RING, {'d': deep, 'l': lit})
        if corner != lost:
            continue
        for j in range(thickness + 3):
            for i in range(thickness + 3):
                x = i if corner in (0, 2) else width - 1 - i
                y = j if corner in (0, 1) else height - 1 - j
                reach = ragged[i - j + thickness + 3]
                if i + j < reach:
                    pixels[x, y] = (0, 0, 0, 0)
                elif i + j == reach and pixels[x, y][3] and min(i, j) < thickness:
                    pixels[x, y] = deep
    for side, along, first, last in cracks:
        for depth in range(first, last):
            x, y = place(side, along, depth)
            if pixels[x, y][3]:
                pixels[x, y] = deep
            along += wear.choice((-1, 0, 0, 1, 1))
    return picture


# The invaders' serpent sign, large, drawn after the one daubed on the palace
# walls: an uneven brush line, not a neat curve. The head curls back inside the
# upper loop; the neck runs down into a wide, flattened coil that thins to its
# tail. Each point is the middle of the line and half its thickness there.
_SERPENT = (
    (31.0, 13.0, 0.8), (33.0, 11.5, 1.6), (34.0, 9.0, 2.2), (34.5, 6.5, 3.2), (33.0, 4.0, 2.6),
    (30.0, 2.3, 2.0), (25.0, 1.8, 2.0), (20.5, 3.0, 2.3), (18.5, 6.0, 2.8), (19.5, 10.0, 2.8),
    (21.5, 14.0, 2.5), (24.0, 17.5, 2.3), (28.5, 20.5, 2.2), (33.0, 23.5, 2.3), (36.0, 27.5, 2.6),
    (36.5, 32.5, 2.2), (34.0, 37.5, 2.4), (29.0, 42.0, 2.3), (22.0, 44.8, 2.0), (14.0, 45.0, 2.2),
    (7.5, 42.0, 2.6), (3.5, 37.0, 2.8), (3.0, 31.0, 2.8), (5.5, 26.0, 2.6), (11.0, 23.0, 2.2),
    (18.0, 22.8, 2.0), (23.0, 25.0, 2.3), (25.5, 29.5, 2.2), (25.5, 34.0, 2.0), (22.5, 37.3, 1.9),
    (17.0, 38.0, 1.8), (13.0, 36.0, 1.9), (12.0, 33.0, 1.8), (14.0, 30.8, 1.5), (17.5, 30.5, 1.1),
    (19.5, 31.5, 0.6),
)


def _serpent_mask(height):
    scale = height / 48.0
    image = Image.new('L', (round(40 * scale), height), 0)
    draw = ImageDraw.Draw(image)
    rng = random.Random(0x5E)
    points = (_SERPENT[0],) + _SERPENT + (_SERPENT[-1],)
    wobble = 1.0
    for index in range(1, len(points) - 2):
        before, start, end, after = points[index - 1:index + 3]
        for step in range(16):
            t = step / 16.0
            # A curve through the points (Catmull-Rom), so the line has no corners.
            x, y, half = (0.5 * (2 * b + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t * t
                                 + (3 * b - a - 3 * c + d) * t ** 3)
                          for a, b, c, d in zip(before, start, end, after))
            if step % 4 == 0:
                wobble = rng.uniform(0.88, 1.12)       # the brush pressed unevenly
            half = max(0.5, half * wobble) * scale
            draw.ellipse((x * scale - half, y * scale - half, x * scale + half, y * scale + half), fill=255)
    return image


_marks = {}


def watermark(image, rect, point=None, avoid=()):
    """Leave the theme's sign on a finished page, faintly, behind its text.

    Only the page's own background colours change, each to a slightly darker
    shade, so text, outlines and pictures stay as they are. ``point`` is given
    by pages drawn at the window's resolution: the sign is then drawn at the
    game's resolution and enlarged without smoothing. ``avoid`` lists the
    rectangles where pictures go, in the image's own pixels: a slot still waiting for its picture has a
    background colour, and the sign must not show there and then vanish.
    """
    theme = _current
    if theme.mark is None:
        return
    height = (rect[3] - rect[1]) * 3 // 5
    if height < 60:
        return
    if height not in _marks:
        _marks[height] = _serpent_mask(height)
    mask = _marks[height]
    left = (rect[0] + rect[2] + 1 - mask.width) // 2
    top = (rect[1] + rect[3] + 1 - mask.height) // 2 + 6
    box = (left, top, left + mask.width, top + mask.height)
    if point is not None:
        box = (*point(box[0], box[1]), *point(box[2], box[3]))
        key = height, box[2] - box[0], box[3] - box[1]
        if key not in _marks:
            _marks[key] = mask.resize(key[1:], Image.Resampling.NEAREST)
        mask = _marks[key]
    # One pass over the pixels under the sign: these pages are redrawn on every key.
    region = image.crop(box)
    pixels = numpy.array(region.convert('RGB'))
    packed = (pixels[..., 0].astype(numpy.uint32) << 16) | (pixels[..., 1].astype(numpy.uint32) << 8) | pixels[..., 2]
    inside = numpy.asarray(mask) > 0
    for left, top, right, bottom in avoid:
        inside[max(0, top - box[1]):max(0, bottom + 1 - box[1]), max(0, left - box[0]):max(0, right + 1 - box[0])] = False
    toward = _rgb(theme.mark)
    changed = numpy.zeros(inside.shape, dtype=bool)
    for colour in {_rgb(theme.colour(role)) for role in ('panel', 'row', 'row_dark', 'selected', 'hover')}:
        same = inside & (packed == (colour[0] << 16 | colour[1] << 8 | colour[2]))
        pixels[same] = tuple(round(a + (b - a) * 0.4) for a, b in zip(colour, toward))
        changed |= same
    image.paste(Image.fromarray(pixels), box, Image.fromarray(changed))


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


_PAINTERS = {'rock': _rock_frame, 'bands': _band_frame, 'sand': _sand_frame,
             'studs': _studs_frame, 'columns': _columns_frame}
