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
    frame: str | None = None  # 'rock', 'bands' or None for a plain outline
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
        return {'rock': _ROCK_THICKNESS, 'bands': len(self.bands)}.get(self.frame, 0)

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
}, dim=115, frame='rock', grow=(2, 5, 7), grain=(
    ('#ecbc86', 30), ('#f2cd8d', 30), ('#d8ab71', 15), ('#e9b471', 10), ('#d4b68b', 8), ('#d5a056', 7),
), shades=('#fedea5', '#b78742', '#af9361', '#91622b'))

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
}, dim=120, frame='rock', grow=(2, 5, 7), grain=(
    ('#5c5485', 25), ('#534b7e', 22), ('#736b96', 15), ('#4e467b', 12), ('#4a4178', 10),
    ('#7c749c', 8), ('#413871', 8),
), shades=('#9a93b5', '#3c336e', '#332a67', '#2a2161', '#251c5d'))

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
}, dim=100, frame='bands', grow=(1, 6, 7), bands=(
    # A red moulding lit on its outer edge, then a line of candle gold.
    ('#100000',), ('#a1251e',), ('#781313',), ('#6b1808', '#631810'), ('#631810', '#5a1810'),
    ('#520808',), ('#450a0a',), ('#310000',), ('#100000',), ('#d9a441',), ('#6c2107',), ('#100000',),
))

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
        _frames[key] = (_rock_frame if theme.frame == 'rock' else _band_frame)(theme, size, fill)
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
