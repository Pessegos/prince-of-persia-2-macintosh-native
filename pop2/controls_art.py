"""Pixel-art drawings of a controller and keyboard for the Controls page.

Port-only artwork, drawn by code at the game's native resolution: every
shape is a mask lit from the upper left and reduced to a few hard shades,
the way a 1993 artist would shade an object, with no blending or blur.
The colours come from the game's palace palette. Results are cached;
nothing here depends on the game's resources.
"""

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

LIGHT = np.array((-0.55, -0.75, 0.62))
LIGHT = LIGHT / np.linalg.norm(LIGHT)


DISTANCE_CAP = 40  # no shading looks further in than this


def distance_inside(mask, cap=DISTANCE_CAP):
    """Euclidean distance from each inside pixel to the nearest outside one.

    Exact up to `cap` (beyond the frame counts as outside): first the
    distance along each column, then the nearest such column in each row.
    """
    height, width = mask.shape
    inside = mask.astype(bool)
    down, up = (np.zeros((height, width), np.float32) for _ in range(2))
    for rows, target in ((range(height), down), (range(height - 1, -1, -1), up)):
        previous = np.zeros(width, np.float32)
        for y in rows:
            previous = np.where(inside[y], np.minimum(previous + 1, cap + 1), 0)
            target[y] = previous
    column = np.minimum(down, up)
    padded = np.pad(column, ((0, 0), (cap, cap)))
    best = column * column
    for dx in range(-cap, cap + 1):
        if dx:
            shifted = padded[:, cap + dx:cap + dx + width]
            best = np.minimum(best, shifted * shifted + dx * dx)
    return np.where(inside, np.sqrt(best), 0).astype(np.float32)


def blur(values, sigma):
    radius = max(1, int(sigma * 3))
    kernel = np.exp(-0.5 * (np.arange(-radius, radius + 1) / sigma) ** 2)
    kernel /= kernel.sum()
    padded = np.pad(values, radius, mode='edge')
    rows = np.apply_along_axis(lambda line: np.convolve(line, kernel, 'valid'), 1, padded)
    return np.apply_along_axis(lambda line: np.convolve(line, kernel, 'valid'), 0, rows)


def lit_levels(mask, rim=6.0, dome=0.0, span=24.0, slope=0.0, concave=False, bias=0.0,
               thresholds=None, smooth=1.2):
    """Shade index (1 = darkest, len - 1 = brightest) for each inside pixel.

    rim rounds the edge over that many pixels; dome adds a broad swell that
    levels off `span` pixels in; slope darkens towards the bottom.
    """
    distance = distance_inside(mask)
    clipped = np.minimum(distance, rim)
    height = np.sqrt(np.maximum(0.0, rim * rim - (rim - clipped) ** 2))
    if dome:
        swell = np.minimum(distance, span) / span
        height = height + dome * span * (1 - (1 - swell) ** 2)
    if concave:
        height = -height
    if smooth:
        height = blur(height, smooth)
    gy, gx = np.gradient(height)
    normal = np.stack((-gx, -gy, np.ones_like(gx)), axis=-1)
    normal /= np.linalg.norm(normal, axis=-1, keepdims=True)
    light = normal @ LIGHT + bias
    if slope:
        rows = np.nonzero(mask.any(axis=1))[0]
        top, bottom = rows[0], rows[-1]
        light = light - slope * (np.arange(mask.shape[0])[:, None] - top) / max(1, bottom - top)
    thresholds = thresholds or (0.05, 0.3, 0.52, 0.7, 0.86)
    levels = np.digitize(light, thresholds) + 1
    levels[~mask] = 0
    return tidy(levels, mask)


def tidy(levels, mask):
    """Merge lone pixels into a neighbouring band, as an artist would.

    Only neighbours inside the shape count, so an edge pixel is never
    merged into the outside (which would leave a bite out of the rim).
    """
    padded = np.pad(np.where(mask, levels, 0), 1)
    neighbours = np.stack((padded[:-2, 1:-1], padded[2:, 1:-1], padded[1:-1, :-2], padded[1:-1, 2:]))
    inside = neighbours > 0
    count = inside.sum(axis=0)
    alone = mask & (count > 0) & ~((neighbours == levels) & inside).any(axis=0)
    if alone.any():
        ordered = np.sort(np.where(inside, neighbours, 255), axis=0)
        middle = np.take_along_axis(ordered, np.clip((count - 1) // 2, 0, 3)[None], axis=0)[0]
        levels = np.where(alone, middle, levels)
    return levels


def edge(mask):
    """The pixels of a mask that touch the outside (4-connected)."""
    padded = np.pad(mask, 1, constant_values=False)
    return mask & ~(padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:])


def paint(image, levels, ramp, offset=(0, 0), outline=True):
    """Composite shaded levels onto an RGBA image; the rim takes ramp[0]."""
    mask = levels > 0
    if outline:
        levels = np.where(edge(mask), 0, levels)
    colors = np.array([(*color, 255) for color in ramp], np.uint8)
    pixels = colors[np.clip(levels, 0, len(ramp) - 1)]
    pixels[~mask] = 0
    layer = Image.fromarray(pixels, 'RGBA')
    image.alpha_composite(layer, offset)


def mask_from(draw_shape, size):
    canvas = Image.new('L', size, 0)
    draw_shape(ImageDraw.Draw(canvas))
    return np.array(canvas) > 127


def circle_mask(radius, slack=0.8):
    """A disc; more slack rounds a small one's diagonals out."""
    size = 2 * radius + 1
    yy, xx = np.mgrid[:size, :size] - radius
    return xx * xx + yy * yy <= radius * radius + radius * slack


def spline(points, steps=10):
    """A smooth Catmull-Rom curve through the points, both ends included."""
    points = [np.asarray(point, float) for point in points]
    padded = [points[0], *points, points[-1]]
    path = []
    for p0, p1, p2, p3 in zip(padded, padded[1:], padded[2:], padded[3:]):
        for step in range(steps):
            t = step / steps
            path.append(tuple(0.5 * (2 * p1 + (p2 - p0) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                                     + (3 * p1 - p0 - 3 * p2 + p3) * t ** 3)))
    path.append(tuple(points[-1]))
    return path


def stamp(image, mask, centre, ramp, **shading):
    """Shade a small mask and paint it centred on `centre`."""
    levels = lit_levels(mask, **shading)
    height, width = mask.shape
    paint(image, levels, ramp, (centre[0] - width // 2, centre[1] - height // 2))


def rounded(width, height, radius):
    return mask_from(lambda draw: draw.rounded_rectangle((0, 0, width - 1, height - 1),
                                                         radius=radius, fill=255), (width, height))


def tone(color, factor, lift=0):
    return tuple(max(0, min(255, round(channel * factor + lift))) for channel in color)


# -- colours ------------------------------------------------------------------
# Ramps run from the outline to the highlight, in the palace's own colours:
# ivory and cream stone with mauve shadows and the dark brown outline of the
# game's sprites, the friezes' blues and the tapestries' crimson and magenta.
SHELL = ((74, 33, 16), (119, 90, 107), (154, 131, 138), (205, 183, 139), (231, 206, 173),
         (247, 227, 176), (255, 255, 214))
BUMPER = ((74, 33, 16), (98, 66, 82), (119, 90, 107), (154, 131, 138), (190, 168, 140),
          (214, 193, 144), (231, 206, 173))  # also the PlayStation touchpad
TRIGGER = ((58, 26, 14), (80, 52, 66), (98, 66, 82), (119, 90, 107), (138, 112, 122),
           (154, 131, 138), (180, 158, 160))
WELL = ((40, 18, 10), (58, 34, 36), (74, 46, 50), (90, 60, 66), (108, 78, 86), (130, 100, 108),
        (160, 132, 138))  # stick wells, the D-pad dish, small and dark buttons
FRIEZE = ((16, 36, 52), (24, 62, 88), (24, 79, 104), (33, 98, 140), (52, 124, 166), (73, 147, 181),
          (120, 196, 206))  # stick caps
TAPESTRY = ((52, 4, 34), (100, 0, 72), (132, 0, 90), (156, 16, 66), (206, 41, 82), (222, 74, 33),
            (253, 174, 97))  # the D-pad: crimson lit with the tapestries' orange and peach
GOLD = ((50, 28, 6), (98, 60, 14), (132, 80, 20), (164, 110, 30), (204, 150, 48), (234, 188, 76),
        (250, 218, 116), (255, 246, 186))  # the guide button
BUTTON = ((74, 33, 16), (190, 168, 140), (214, 193, 144), (231, 206, 173), (247, 227, 176),
          (255, 255, 214), (255, 255, 236))  # the Xbox's small ivory buttons
BED = ((74, 33, 16), (74, 46, 50), (90, 60, 66), (98, 70, 76), (108, 78, 86), (119, 90, 107),
       (138, 112, 122))  # the recess the keys sit in
INK = (74, 33, 16)            # callout lines over the shell, legends on light keys
# The Xbox face buttons' own colours; the Controls page colours the actions
# those buttons do by default alike (Jump green as A, and so on).
XBOX_COLORS = {'a': (52, 170, 88), 'b': (218, 50, 50), 'x': (48, 108, 196), 'y': (240, 194, 60)}


# -- the controller -----------------------------------------------------------
# An Xbox Series-shaped pad on a 240-pixel grid (y grows downwards), its
# proportions those of the real controller. The triggers rise up to ABOVE
# pixels above the grid; tables below use the grid's own coordinates.
ABOVE = 9
PAD_WIDTH, PAD_HEIGHT = 241, 161 + ABOVE
# The shell's left half, from the top centre round to the bottom centre.
SHELL_HALF = ((120, 6), (100, 6), (86, 7), (72, 8), (60, 10), (50, 13), (42, 17), (36, 22), (31, 28),
              (26, 36), (21, 46), (17, 56), (13, 67), (9, 80), (6, 93), (3, 106), (1, 118), (0, 129),
              (1, 140), (4, 148), (9, 155), (16, 159), (23, 160), (30, 158), (36, 153), (43, 146),
              (51, 138), (59, 131), (67, 125), (77, 121), (90, 120), (105, 120), (120, 120))
# The left bumper wraps the shell's top corner; the trigger rises behind it.
BUMPER_EDGE = (((35, 20), (38, 14), (44, 9), (52, 5), (62, 2), (75, 1), (84, 3), (89, 7)),
               ((89, 10), (80, 10), (68, 11), (56, 13), (46, 17), (40, 21), (36, 23)))
TRIGGER_EDGE = ((46, 12), (48, 4), (54, -2), (63, -6), (74, -6), (81, -3), (85, 2), (86, 8), (66, 10))
STICK_WELL, STICK_CAP, STICK_DISH = 17, 14, 9
FACE_RADIUS, DPAD_DISH, GUIDE_RADIUS = 8, 18, 10
FACE = {'y': (180, 29), 'x': (162, 47), 'b': (198, 47), 'a': (180, 65)}
LAYOUTS = {
    'xbox': {'leftstick': (60, 47), 'dpad': (89, 83), 'rightstick': (151, 83), **FACE,
             'back': (104, 48), 'start': (136, 48), 'misc1': (120, 62), 'guide': (120, 23)},
    'playstation': {'dpad': (60, 50), 'leftstick': (89, 83), 'rightstick': (151, 83), **FACE,
                    'back': (94, 26), 'start': (146, 26), 'touchpad': (120, 30),
                    'guide': (120, 64), 'misc1': (120, 78)},
}
# Callout rows, 18 pixels apart, shared by both columns of labels.
ROWS = (-25, -7, 11, 29, 47, 65, 83, 101, 119, 137)
# The labels come in groups, one per control or cluster, as on a game's
# controls screen: a group lists its buttons, an icon and an action to a
# row from its first row down, beside a bracket; one line runs from the
# bracket, level at its line row, then straight up or down to the control.
# name: (side, first row, line row, buttons, the points the line passes).
# 'move' is the left stick's movement, 'leftstick' its click.
SHARED_GROUPS = {
    'leftshoulders': ('left', -7, -7, ('lefttrigger', 'leftshoulder'), ((52, -7), (52, 1))),
    'rightshoulders': ('right', -7, -7, ('righttrigger', 'rightshoulder'), ((188, -7), (188, 1))),
    'face': ('right', 29, 47, ('y', 'x', 'b', 'a'), ((212, 47),)),
    'rightstick': ('right', 101, 101, ('rightstick',), ((163, 101), (163, 95))),
}
GROUPS = {
    'xbox': {**SHARED_GROUPS,
             'back': ('left', -25, -25, ('back',), ((104, -25), (104, 42))),
             'start': ('right', -25, -25, ('start',), ((136, -25), (136, 42))),
             'leftstick': ('left', 47, 47, ('move', 'leftstick'), ((43, 47),)),
             'dpad': ('left', 83, 83, ('dpad',), ((71, 83),)),
             'misc1': ('left', 137, 137, ('misc1',), ((120, 137), (120, 67)))},
    'playstation': {**SHARED_GROUPS,
                    'touchpad': ('left', -25, -25, ('touchpad',), ((110, -25), (110, 17))),
                    'start': ('right', -25, -25, ('start',), ((146, -25), (146, 20))),
                    'back': ('left', 29, 29, ('back',), ((90, 29),)),
                    'dpad': ('left', 47, 47, ('dpad',), ((42, 47),)),
                    'leftstick': ('left', 83, 83, ('move', 'leftstick'), ((72, 83),)),
                    'misc1': ('left', 137, 137, ('misc1',), ((120, 137), (120, 82)))},
}
# A diamond round the four face buttons, which the face group's line meets:
# its centre and its reach (|dx| + |dy|).
FACE_FRAME = (180, 47, 32)


def layout_name(style):
    return 'playstation' if style == 'playstation' else 'xbox'


def on_grid(path):
    return [(x, y + ABOVE) for x, y in path]


def polygon(path, mirrored=False):
    if mirrored:
        path = [(240 - x, y) for x, y in path]
    return mask_from(lambda draw: draw.polygon(on_grid(path), fill=255), (PAD_WIDTH, PAD_HEIGHT))


def body_mask():
    half = spline(SHELL_HALF)
    mask = polygon(half + [(240 - x, y) for x, y in reversed(half)])
    mask[:SHELL_HALF[0][1] + ABOVE] = False  # the curve overshoots the flat top
    return mask


def shoulder_masks(body):
    outer, inner = BUMPER_EDGE
    bumper = spline(outer) + spline(inner)
    bumpers = polygon(bumper) | polygon(bumper, mirrored=True)
    triggers = polygon(spline(TRIGGER_EDGE)) | polygon(spline(TRIGGER_EDGE), mirrored=True)
    return triggers & ~bumpers & ~body, bumpers


def glyph(draw, x, y, rows, fill):
    for row, line in enumerate(rows):
        for column, cell in enumerate(line):
            if cell == '#':
                draw.point((x + column, y + row), fill=fill)


# Bold 5x6 letters for the face buttons, two pixels to a stroke.
FACE_LETTERS = {
    'A': ('.###.', '##.##', '##.##', '#####', '##.##', '##.##'),
    'B': ('####.', '##.##', '####.', '##.##', '##.##', '####.'),
    'X': ('##.##', '##.##', '.###.', '.###.', '##.##', '##.##'),
    'Y': ('##.##', '##.##', '.###.', '..#..', '..#..', '..#..'),
}
# The same letters a row shorter for the small buttons of the legends, so
# they sit exactly in the middle of a 13-pixel button.
ICON_LETTERS = {
    'A': ('.###.', '##.##', '#####', '##.##', '##.##'),
    'B': ('####.', '##.##', '####.', '##.##', '####.'),
    'X': ('##.##', '.###.', '..#..', '.###.', '##.##'),
    'Y': ('##.##', '##.##', '.###.', '..#..', '..#..'),
}
# Face buttons: dark domes with ivory letters, or the PlayStation symbols in
# their colours.
FACE_STYLES = {
    'xbox': {name: SHELL[5] for name in 'abxy'},
    'playstation': {'a': (132, 166, 232), 'b': (232, 116, 116), 'x': (220, 146, 210), 'y': (98, 204, 176)},
    'nintendo': {name: SHELL[5] for name in 'abxy'},
}
NINTENDO_LETTERS = {'a': 'B', 'b': 'A', 'x': 'Y', 'y': 'X'}


def face_button(image, centre, button, style, radius=FACE_RADIUS):
    ink = FACE_STYLES.get(style, FACE_STYLES['xbox'])[button]
    name = NINTENDO_LETTERS[button] if style == 'nintendo' else button.upper()
    small = radius < FACE_RADIUS
    letter = (ICON_LETTERS if small else FACE_LETTERS)[name]
    stamp(image, circle_mask(radius, slack=1.0 if small else 0.8), centre, WELL,
          rim=2 if small else 4, dome=.5)
    draw = ImageDraw.Draw(image)
    cx, cy = centre
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
    glyph(draw, cx - len(letter[0]) // 2, cy - len(letter) // 2, letter, ink)


# The guide button, pixel by pixel after the user's own sketch: a gold
# coin quartered by the Xbox X, its arms lit ridges with a dark groove on
# their outer side, a bright crossing and a small cap at the top. Digits
# index GOLD (0 is the outline).
GUIDE_COIN = (
    '        00000        ',
    '     00067775000     ',
    '    0036766665310    ',
    '   011116666411110   ',
    '  06666116641166650  ',
    ' 0575577111117644430 ',
    ' 0575557711177444430 ',
    ' 0655555777774444330 ',
    '065555517777714443320',
    '045555117747711433320',
    '045441177444771133220',
    '044411774444477113220',
    '044116744444337611220',
    ' 0411644444333361120 ',
    ' 0316644443333366120 ',
    ' 0066443333333226600 ',
    '  06333333332222260  ',
    '   022333332222220   ',
    '    0222333222220    ',
    '     00022222000     ',
    '        00000        ',
)


def guide_button(image, centre):
    radius = len(GUIDE_COIN) // 2
    pixels = image.load()
    for y, row in enumerate(GUIDE_COIN):
        for x, cell in enumerate(row):
            if cell != ' ':
                pixels[centre[0] - radius + x, centre[1] - radius + y] = (*GOLD[int(cell)], 255)


def small_button(image, centre, icon, size=(11, 11), ramp=WELL, ink=SHELL[5]):
    """View, Menu, Share and the like: round, or a pill when not square."""
    width, height = size
    if width == height:
        stamp(image, circle_mask(width // 2, slack=1.0), centre, ramp, rim=2, dome=.3)
    else:
        stamp(image, rounded(width, height, radius=min(size) // 2), centre, ramp, rim=2, bias=.1)
    small_icon(ImageDraw.Draw(image), centre[0], centre[1], icon, ink)


def ivory_button(image, centre, icon, size=(13, 13)):
    """The Xbox's own small buttons: ivory like the shell, icons in ink."""
    small_button(image, centre, icon, size, BUTTON, INK)


SMALL_ICONS = {
    # two windows, one behind the other
    'view': ('####...', '#.#####', '#.#...#', '..#...#', '..#####'),
    'menu': ('#######', '.......', '#######', '.......', '#######'),
    # an arrow rising out of a tray
    'share': ('...#...', '..###..', '.#####.', '...#...', '#..#..#', '#.....#', '#######'),
    'home': ('..#..', '.###.', '#####', '.#.#.', '.###.'),
    'minus': ('.....', '.....', '#####', '.....', '.....'),
    'plus': ('..#..', '..#..', '#####', '..#..', '..#..'),
    'dot': ('#',),
}


def small_icon(draw, x, y, icon, fill):
    rows = SMALL_ICONS[icon]
    glyph(draw, x - len(rows[0]) // 2, y - len(rows) // 2, rows, fill)


@lru_cache(maxsize=None)
def stick_cap(cap=STICK_CAP, dish=STICK_DISH):
    """Shade levels for a stick's cap: a rolled rim round a shallow dish,
    lit from exact normals so the dish's edge is one whole, even circle."""
    size = 2 * cap + 1
    yy, xx = np.mgrid[:size, :size] - cap
    distance = np.maximum(np.hypot(xx, yy), 1e-6)
    ux, uy = xx / distance, yy / distance
    # The rim rolls over from its flat inner edge to the outside; the dish
    # slopes gently down towards its centre.
    rim = np.clip((distance - dish) / (cap + .5 - dish), 0, 1)
    slope = np.where(distance < dish, -0.45 * distance / dish, rim * 0.97)
    up = np.sqrt(1 - slope * slope)
    light = slope * (ux * LIGHT[0] + uy * LIGHT[1]) + up * LIGHT[2]
    levels = np.digitize(light, (0.35, 0.5, 0.75, 0.92)) + 2
    inside = circle_mask(cap)
    in_dish = circle_mask(dish)
    levels = np.where(np.pad(in_dish, cap - dish), np.clip(levels, 3, 4), levels)
    levels[~inside] = 0
    levels = tidy(levels, inside)
    levels[np.pad(edge(in_dish), cap - dish)] = 1  # the dish's edge, all the way round
    return levels


def stick(image, centre, well=STICK_WELL, cap=STICK_CAP, dish=STICK_DISH):
    cx, cy = centre
    small = well < STICK_WELL
    stamp(image, circle_mask(well, slack=1.0 if small else 0.8), centre, WELL,
          rim=2 if small else 4, concave=True)
    paint(image, stick_cap(cap, dish), FRIEZE, (cx - cap, cy - cap))


@lru_cache(maxsize=None)
def dpad_cross(span=31, arm=13, corner=3):
    """The cross: arms of odd width so it sits exactly on its centre."""
    low = (span - arm) // 2
    cross = mask_from(lambda draw: (draw.rounded_rectangle((low, 0, low + arm - 1, span - 1), corner, fill=255),
                                    draw.rounded_rectangle((0, low, span - 1, low + arm - 1), corner, fill=255)),
                      (span, span))
    cross = cross & cross[::-1] & cross[:, ::-1]
    return cross & cross.T


def dpad(image, centre, dish=DPAD_DISH, span=31, arm=13, corner=3):
    small = dish < DPAD_DISH
    stamp(image, circle_mask(dish, slack=1.0 if small else 0.8), centre, WELL,
          rim=2 if small else 4, concave=True)
    stamp(image, dpad_cross(span, arm, corner), centre, TAPESTRY, rim=2 if small else 3, bias=.15)


@dataclass(frozen=True)
class PadArt:
    image: Image.Image
    points: dict   # button -> centre on the image
    groups: dict   # name -> (side, first row, line row, buttons, line points), on the image
    frame: tuple   # the face buttons' diamond: its corners, on the image
    controls: np.ndarray  # where a control is drawn (not the shell)


def shifted(point):
    return point[0], point[1] + ABOVE


@lru_cache(maxsize=None)
def pad_art(style='xbox'):
    layout = layout_name(style)
    points = {name: shifted(point) for name, point in LAYOUTS[layout].items()}
    image = Image.new('RGBA', (PAD_WIDTH, PAD_HEIGHT), (0, 0, 0, 0))
    body = body_mask()
    triggers, bumpers = shoulder_masks(body)
    paint(image, lit_levels(triggers, rim=4, smooth=1.6, bias=.08), TRIGGER)
    paint(image, lit_levels(body, rim=8, dome=0.1, span=30, slope=0.04,
                            thresholds=(0.05, 0.27, 0.5, 0.75, 0.92), smooth=3.0), SHELL)
    paint(image, lit_levels(bumpers, rim=3, smooth=1.0, bias=.06), BUMPER)
    # The controls go on a layer of their own, so the callouts know where
    # each one begins.
    parts = Image.new('RGBA', image.size, (0, 0, 0, 0))
    stick(parts, points['leftstick'])
    stick(parts, points['rightstick'])
    dpad(parts, points['dpad'])
    for name in ('y', 'x', 'b', 'a'):
        face_button(parts, points[name], name, style)
    if layout == 'playstation':
        stamp(parts, rounded(37, 25, 4), points['touchpad'], BUMPER, rim=3, bias=-.05)
        stamp(parts, circle_mask(5), points['guide'], WELL, rim=3, dome=.3)
        small_button(parts, points['misc1'], 'dot', (9, 5))
        small_button(parts, points['back'], 'dot', (7, 11))
        small_button(parts, points['start'], 'dot', (7, 11))
    elif style == 'nintendo':
        stamp(parts, circle_mask(8), points['guide'], WELL, rim=3, dome=.3)
        small_icon(ImageDraw.Draw(parts), *points['guide'], 'home', SHELL[5])
        small_button(parts, points['back'], 'minus')
        small_button(parts, points['start'], 'plus')
        small_button(parts, points['misc1'], 'dot', (9, 9))
    else:
        guide_button(parts, points['guide'])
        ivory_button(parts, points['back'], 'view')
        ivory_button(parts, points['start'], 'menu')
        ivory_button(parts, points['misc1'], 'share', (15, 11))
    image.alpha_composite(parts)
    controls = triggers | bumpers | (np.array(parts)[:, :, 3] > 0)
    groups = {}
    for name, (side, first, line, buttons, path) in GROUPS[layout].items():
        path = [shifted(point) for point in path]
        if name != 'face':  # that line meets the frame round the face buttons
            previous = path[-2] if len(path) > 1 else (0 if side == 'left' else PAD_WIDTH - 1, path[0][1])
            path[-1] = stop_short(previous, path[-1], controls)
        groups[name] = (side, first + ABOVE, line + ABOVE, buttons, tuple(path))
    x, y, reach = FACE_FRAME
    frame = tuple(shifted(corner) for corner in ((x + reach, y), (x, y + reach), (x - reach, y),
                                                 (x, y - reach), (x + reach, y)))
    return PadArt(image, points, groups, frame, controls)


LINE_GAP = 2  # clear pixels between a callout line's end and its control


def stop_short(previous, end, controls, gap=LINE_GAP, reach=8):
    """Where a level or upright callout line running from `previous`
    towards `end` stops: `gap` clear pixels before the first control pixel
    on its way (looking up to `reach` pixels past `end`), so it points at
    the control without running into it."""
    (x, y), (x1, y1) = previous, end
    dx, dy = (x1 > x) - (x1 < x), (y1 > y) - (y1 < y)
    height, width = controls.shape
    for _step in range(abs(x1 - x) + abs(y1 - y) + reach + 1):
        if 0 <= x < width and 0 <= y < height and controls[y, x]:
            return x - dx * (gap + 1), y - dy * (gap + 1)
        x, y = x + dx, y + dy
    return end


# The legends' sticks and D-pad: the pad's own, small (well, cap, dish and
# dish, span, arm, corner).
ICON_STICK = (6, 4, 2)
ICON_DPAD = (6, 11, 5, 0)
# Small arrows either side of the stick for its movement.
MOVE_ARROWS = (((1, 5), (0, 6), (1, 6), (1, 7)), ((15, 5), (15, 6), (16, 6), (15, 7)))


@lru_cache(maxsize=None)
def button_icon(token, style):
    """A small picture of one button for the remap list and the callouts
    (None if there is none)."""
    from pop2.controls_page import mini_text
    from pop2.input_bindings import pad_name

    image = Image.new('RGBA', (17, 13), (0, 0, 0, 0))
    centre = (8, 6)
    if token in ('a', 'b', 'x', 'y'):
        face_button(image, centre, token, style, radius=6)
    elif token in ('back', 'start'):
        if style not in ('playstation', 'nintendo'):
            ivory_button(image, centre, ('view', 'menu')[token == 'start'])
        else:
            icons = {'playstation': ('dot', 'dot'), 'nintendo': ('minus', 'plus')}[style]
            small_button(image, centre, icons[token == 'start'])
    elif token in ('leftshoulder', 'rightshoulder', 'lefttrigger', 'righttrigger'):
        trigger = token.endswith('trigger')
        stamp(image, rounded(15, 13 if trigger else 9, 4), centre, BUMPER, rim=3)
        mini_text(ImageDraw.Draw(image), centre[0], centre[1] - 2, pad_name(token, style), INK, 'center')
    elif token in ('leftstick', 'rightstick', 'move'):
        # The pad's own stick, small: its dark well and blue cap.
        stick(image, centre, *ICON_STICK)
        if token == 'move':
            draw = ImageDraw.Draw(image)
            for arrow in MOVE_ARROWS:
                draw.point(arrow, fill=SHELL[5])
    elif token == 'dpad':
        dpad(image, centre, *ICON_DPAD)
    elif token == 'misc1':
        if style not in ('playstation', 'nintendo'):
            ivory_button(image, centre, 'share', (15, 11))
        else:
            small_button(image, centre, 'dot', (9, 5) if style == 'playstation' else (9, 9))
    elif token == 'touchpad':
        stamp(image, rounded(15, 11, 3), centre, BUMPER, rim=2, bias=-.05)
    else:
        return None
    return image


# -- keyboard ---------------------------------------------------------------
# A 1990s office keyboard in the palace's colours: light keys for letters,
# digits and F-keys, darker mauve ones for the rest, each seen from above and
# a little in front. Key ramps: bottom shadow, front, right side, left side,
# top, top edge.
KEY_LIGHT = ((170, 148, 120), (214, 193, 144), (205, 183, 139), (232, 214, 178), (252, 244, 214),
             (255, 255, 236))
KEY_DARK = ((100, 76, 88), (138, 116, 124), (128, 106, 116), (166, 146, 150), (182, 162, 164),
            (206, 188, 188))


def key_ramp(color):
    return (tone(color, .55), tone(color, .78), tone(color, .7), tone(color, .92), color,
            tone(color, 1.05, 30))


@lru_cache(maxsize=None)
def keycap(width, height, color=None, dark=False):
    """One key: its top, a narrow side each way and its front below."""
    shadow, front, right_side, left_side, top, edge = (key_ramp(color) if color else
                                                       KEY_DARK if dark else KEY_LIGHT)
    image = Image.new('RGBA', (width, height), (*front, 255))
    draw = ImageDraw.Draw(image)
    right, bottom = width - 1, height - 1
    face = bottom - 4
    draw.rectangle((1, 0, right - 1, face), fill=top)
    draw.line(((0, 0), (0, face)), fill=left_side)
    draw.line(((right, 0), (right, face)), fill=right_side)
    draw.line(((1, 0), (right - 1, 0)), fill=edge)
    draw.line(((0, bottom), (right, bottom)), fill=shadow)
    for corner in ((0, 0), (right, 0), (0, bottom), (right, bottom)):
        image.putpixel(corner, (0, 0, 0, 0))
    return image


def legend_ink(color, dark=False):
    return tone(color, .22) if color else (40, 20, 26) if dark else INK


def key_top(color, dark=False):
    """The colour of a key's top, where its legend is printed."""
    return color if color else KEY_DARK[4] if dark else KEY_LIGHT[4]


@lru_cache(maxsize=None)
def keyboard_case(width, height, keys):
    """The case, lit like the pad's shell, and the recess round its keys
    (`keys` are rectangles relative to the case)."""
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    paint(image, lit_levels(rounded(width, height, 6), rim=4, slope=0.1,
                            thresholds=(0.05, 0.27, 0.5, 0.75, 0.92), smooth=2.0), SHELL)
    bed = mask_from(lambda draw: [draw.rectangle((left - 1, top - 1, right + 1, bottom + 1), fill=255)
                                  for left, top, right, bottom in keys], (width, height))
    paint(image, lit_levels(bed, rim=2, concave=True, smooth=0.8), BED)
    return image


LEDS = ('NUM', 'CAPS', 'SCRL')
LED_GREEN = ((30, 64, 30), (96, 200, 96), (210, 255, 200))  # off, on, its glint


def draw_leds(image, rect, lit=('NUM',)):
    """The three lock lights with their printed names."""
    from pop2.controls_page import mini_text

    left, top, right, _bottom = rect
    draw = ImageDraw.Draw(image)
    step = (right - left) / len(LEDS)
    for index, name in enumerate(LEDS):
        cx = round(left + step * (index + .5))
        mini_text(draw, cx, top + 2, name, SHELL[1], 'center')
        draw.rectangle((cx - 3, top + 9, cx + 3, top + 13), fill=INK)
        on = name in lit
        draw.rectangle((cx - 2, top + 10, cx + 2, top + 12), fill=LED_GREEN[1 if on else 0])
        if on:
            draw.point((cx - 1, top + 10), fill=LED_GREEN[2])


# The Windows 98 flag without its colours, drawn after the colour one: a
# frame leaning to the right round four panes in a shadow tone, and squares
# flying off to the left that shrink and fade into the key. Digits are
# ninths of the way from the key's top colour to its ink.
WINDOWS_FLAG = ('........999999999',
                '.3..77..944494449',
                '....77.944494449.',
                '.......999999999.',
                '.3.77..944494449.',
                '...77.944494449..',
                '1.....999999999..')


def windows_flag(image, centre, ink, paper):
    x0 = centre[0] - (len(WINDOWS_FLAG[0]) - 1) // 2
    y0 = centre[1] - (len(WINDOWS_FLAG) - 1) // 2
    pixels = image.load()
    for y, row in enumerate(WINDOWS_FLAG):
        for x, cell in enumerate(row):
            if cell != '.':
                share = int(cell) / 9
                pixels[x0 + x, y0 + y] = (*(round(p + (i - p) * share) for p, i in zip(paper, ink)), 255)
