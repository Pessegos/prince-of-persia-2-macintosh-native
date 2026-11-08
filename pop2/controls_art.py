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
    """Merge lone pixels into a neighbouring band, as an artist would."""
    padded = np.pad(levels, 1, mode='edge')
    neighbours = np.stack((padded[:-2, 1:-1], padded[2:, 1:-1], padded[1:-1, :-2], padded[1:-1, 2:]))
    alone = mask & (neighbours != levels).all(axis=0)
    if alone.any():
        replacement = np.sort(neighbours, axis=0)[1]
        levels = np.where(alone, replacement, levels)
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


@lru_cache(maxsize=None)
def color_ramp(color):
    return tuple(tone(color, factor, lift) for factor, lift in (
        (.16, 4), (.42, 0), (.58, 0), (.76, 0), (.92, 0), (1.04, 8), (1.06, 46)))


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
GOLD = ((50, 28, 6), (98, 60, 14), (164, 110, 30), (204, 150, 48), (234, 188, 76), (250, 218, 116),
        (255, 246, 186))  # the guide button; [1] is the cut mark
BUTTON = ((74, 33, 16), (190, 168, 140), (214, 193, 144), (231, 206, 173), (247, 227, 176),
          (255, 255, 214), (255, 255, 236))  # the Xbox's small ivory buttons
BED = ((74, 33, 16), (74, 46, 50), (90, 60, 66), (98, 70, 76), (108, 78, 86), (119, 90, 107),
       (138, 112, 122))  # the recess the keys sit in
INK = (74, 33, 16)            # callout lines over the shell, legends on light keys
LIGHT_INK = (255, 252, 230)   # letters and icons on dark or coloured buttons
# Face button gems, in the Xbox colours; the Controls page colours the same
# actions alike, so a default button and its label always match.
GEMS = {'a': (52, 170, 88), 'b': (218, 50, 50), 'x': (48, 108, 196), 'y': (240, 194, 60)}


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
# button: (side, row, the points its line passes on the way to the button);
# 'move' is the left stick's movement, 'leftstick' its click.
# Lines run level from the labels, then bend at most once, so they never
# cross one another or pass over another button.
SHARED_ROUTES = {
    'lefttrigger': ('left', -7, ((44, -7), (52, 2))), 'righttrigger': ('right', -7, ((196, -7), (188, 2))),
    'leftshoulder': ('left', 11, ((45, 11),)), 'rightshoulder': ('right', 11, ((195, 11),)),
    'y': ('right', 29, ((189, 29),)), 'b': ('right', 47, ((207, 47),)),
    'x': ('right', 65, ((216, 65), (171, 50))), 'a': ('right', 83, ((198, 83), (187, 72))),
    'rightstick': ('right', 101, ((169, 101), (163, 95))),
}
ROUTES = {
    'xbox': {**SHARED_ROUTES,
             'back': ('left', -25, ((104, -25), (104, 42))),
             'start': ('right', -25, ((136, -25), (136, 42))),
             'move': ('left', 47, ((42, 47),)), 'leftstick': ('left', 65, ((41, 65), (47, 59))),
             'dpad': ('left', 83, ((70, 83),)),
             'misc1': ('left', 137, ((120, 137), (120, 67)))},
    'playstation': {**SHARED_ROUTES,
                    'touchpad': ('left', -25, ((110, -25), (110, 17))),
                    'start': ('right', -25, ((146, -25), (146, 20))),
                    'back': ('left', 29, ((90, 29),)), 'dpad': ('left', 47, ((41, 47),)),
                    'move': ('left', 83, ((71, 83),)), 'leftstick': ('left', 101, ((71, 101), (77, 95))),
                    'misc1': ('left', 137, ((120, 137), (120, 82)))},
}


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
    return polygon(half + [(240 - x, y) for x, y in reversed(half)])


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
# Face buttons: gem colour (None = dark plastic) and symbol colour.
FACE_STYLES = {
    'xbox': {name: (color, LIGHT_INK) for name, color in GEMS.items()},
    'playstation': {'a': (None, (132, 166, 232)), 'b': (None, (232, 116, 116)),
                    'x': (None, (220, 146, 210)), 'y': (None, (98, 204, 176))},
    'nintendo': {name: (None, SHELL[5]) for name in 'abxy'},
}
NINTENDO_LETTERS = {'a': 'B', 'b': 'A', 'x': 'Y', 'y': 'X'}


def sphere_light(radius):
    """x, y (in radii) and the light on a dome filling circle_mask(radius)."""
    size = 2 * radius + 1
    yy, xx = (np.mgrid[:size, :size] - radius) / (radius + 0.5)
    up = np.sqrt(np.clip(1 - xx * xx - yy * yy, 0, 1))
    return xx, yy, xx * LIGHT[0] + yy * LIGHT[1] + up * LIGHT[2]


def gem(image, centre, color, radius):
    """A round cabochon: dark lower right, lit upper left, a glint and a
    little light thrown back along the lower right rim."""
    ramp = color_ramp(color)
    xx, yy, light = sphere_light(radius)
    levels = np.digitize(light, (0.15, 0.45, 0.75, 0.93)) + 1
    thrown = (xx * 0.6 + yy * 0.8 > 0.55) & (xx * xx + yy * yy > 0.55)
    levels = np.where(thrown & (levels <= 2), 3, levels)
    levels[~circle_mask(radius)] = 0
    paint(image, levels, (ramp[0], ramp[1], ramp[2], ramp[4], ramp[5], ramp[6]),
          (centre[0] - radius, centre[1] - radius))


def face_button(image, centre, button, style, radius=FACE_RADIUS):
    color, ink = FACE_STYLES.get(style, FACE_STYLES['xbox'])[button]
    if color:
        gem(image, centre, color, radius)
    else:
        stamp(image, circle_mask(radius), centre, WELL, rim=4, dome=.5)
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
    letter = FACE_LETTERS[NINTENDO_LETTERS[button] if style == 'nintendo' else button.upper()]
    x, y = cx - len(letter[0]) // 2, cy - len(letter) // 2
    if color:
        glyph(draw, x + 1, y + 1, letter, tone(color, .3))  # cut into the stone
    glyph(draw, x, y, letter, ink)


def bezier(start, control, end, steps=16):
    (x0, y0), (x1, y1), (x2, y2) = start, control, end
    return [((1 - t) ** 2 * x0 + 2 * (1 - t) * t * x1 + t * t * x2,
             (1 - t) ** 2 * y0 + 2 * (1 - t) * t * y1 + t * t * y2) for t in np.linspace(0, 1, steps)]


def on_rim(angle, reach=1.0):
    return reach * np.cos(np.radians(angle)), reach * np.sin(np.radians(angle))


def rim_arc(start, end, reach=1.3):
    return [on_rim(angle, reach) for angle in np.linspace(start, end, 8)]


# The Xbox mark, in radii from the centre (y grows downwards): an X whose
# arms flare out to the rim, between four faces that each come to a point
# at the crossing: a small notch at the top, a tall pointed arch below and a
# crescent each side. Each edge is a curve from the point to the rim:
# (point, control, rim angle in degrees).
GUIDE_TOP = ((0, -0.34), (-0.2, -0.6), -112)
GUIDE_BOTTOM = ((0, 0.02), (-0.44, 0.3), 116)
GUIDE_SIDE = ((-0.3, -0.08), ((-0.5, -0.42), 213), ((-0.52, 0.34), 151))


def guide_faces():
    """The four faces as polygons, closed outside the rim."""
    faces = []
    for point, control, angle in (GUIDE_TOP, GUIDE_BOTTOM):
        edge = bezier(point, control, on_rim(angle))
        mirrored = 180 - angle if 180 - angle <= 180 else -180 - angle
        faces.append([*edge, *rim_arc(angle, mirrored), *((-x, y) for x, y in reversed(edge))])
    point, (upper, upper_angle), (lower, lower_angle) = GUIDE_SIDE
    side = [*reversed(bezier(point, upper, on_rim(upper_angle))), *bezier(point, lower, on_rim(lower_angle)),
            *rim_arc(lower_angle, upper_angle)]
    return faces + [side, [(-x, y) for x, y in side]]


@lru_cache(maxsize=None)
def guide_mark(radius, scale=16):
    """True where the X is cut into a coin of this radius."""
    size = 2 * radius + 1
    unit = (radius + 0.5) * scale
    canvas = Image.new('L', (size * scale, size * scale), 0)
    draw = ImageDraw.Draw(canvas)
    for face in guide_faces():
        draw.polygon([(unit + x * unit, unit + y * unit) for x, y in face], fill=255)
    faces = np.array(canvas.resize((size, size), Image.Resampling.BOX)) > 128
    faces &= ~edge(circle_mask(radius))
    # A lone pixel of gold between an arm and the rim joins the arm.
    padded = np.pad(faces, 1)
    lone = faces & ~(padded[:-2, 1:-1] | padded[2:, 1:-1] | padded[1:-1, :-2] | padded[1:-1, 2:])
    return circle_mask(radius) & ~edge(circle_mask(radius)) & ~(faces & ~lone)


def guide_button(image, centre, radius=GUIDE_RADIUS):
    """The guide button: a gold coin with the Xbox mark cut through it."""
    _xx, _yy, light = sphere_light(radius)
    levels = np.digitize(light, (0.2, 0.5, 0.78, 0.93)) + 2
    levels[guide_mark(radius)] = 1
    levels[~circle_mask(radius)] = 0
    paint(image, levels, GOLD, (centre[0] - radius, centre[1] - radius))


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
    'view': ('####...', '#......', '#.#####', '#.#...#', '..#...#', '..#####'),
    'menu': ('######', '......', '######', '......', '######'),
    # an arrow rising out of a tray
    'share': ('...#...', '..###..', '...#...', '#..#..#', '#.....#', '#######'),
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


def stick(image, centre):
    cx, cy = centre
    stamp(image, circle_mask(STICK_WELL), centre, WELL, rim=4, concave=True)
    paint(image, stick_cap(), FRIEZE, (cx - STICK_CAP, cy + 1 - STICK_CAP))


def dpad(image, centre):
    stamp(image, circle_mask(DPAD_DISH), centre, WELL, rim=4, concave=True)
    cross = mask_from(lambda draw: (draw.rounded_rectangle((9, 0, 20, 30), 3, fill=255),
                                    draw.rounded_rectangle((0, 9, 30, 20), 3, fill=255)), (31, 31))
    stamp(image, cross, centre, TAPESTRY, rim=3, bias=.15)


@dataclass(frozen=True)
class PadArt:
    image: Image.Image
    points: dict   # button -> centre on the image
    routes: dict   # button -> (side, row y, line points), on the image


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
    stick(image, points['leftstick'])
    stick(image, points['rightstick'])
    dpad(image, points['dpad'])
    for name in ('y', 'x', 'b', 'a'):
        face_button(image, points[name], name, style)
    if layout == 'playstation':
        stamp(image, rounded(37, 25, 4), points['touchpad'], BUMPER, rim=3, bias=-.05)
        stamp(image, circle_mask(5), points['guide'], WELL, rim=3, dome=.3)
        small_button(image, points['misc1'], 'dot', (9, 5))
        small_button(image, points['back'], 'dot', (7, 11))
        small_button(image, points['start'], 'dot', (7, 11))
    elif style == 'nintendo':
        stamp(image, circle_mask(8), points['guide'], WELL, rim=3, dome=.3)
        small_icon(ImageDraw.Draw(image), *points['guide'], 'home', SHELL[5])
        small_button(image, points['back'], 'minus')
        small_button(image, points['start'], 'plus')
        small_button(image, points['misc1'], 'dot', (9, 9))
    else:
        guide_button(image, points['guide'])
        ivory_button(image, points['back'], 'view')
        ivory_button(image, points['start'], 'menu')
        ivory_button(image, points['misc1'], 'share', (15, 11))
    routes = {button: (side, row + ABOVE, tuple(shifted(point) for point in path))
              for button, (side, row, path) in ROUTES[layout].items()}
    return PadArt(image, points, routes)


SHORT_NAMES = {'leftstick': 'L', 'rightstick': 'R'}


@lru_cache(maxsize=None)
def button_icon(token, style):
    """A small picture of one button for the remap list (None if there is none)."""
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
        mini_text(ImageDraw.Draw(image), 9, 4, pad_name(token, style), INK, 'center')
    elif token in ('leftstick', 'rightstick'):
        stamp(image, circle_mask(6), centre, FRIEZE, rim=3, dome=.4)
        mini_text(ImageDraw.Draw(image), 9, 4, SHORT_NAMES[token], FRIEZE[6], 'center')
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


# The Windows 98 flag: four panes waving in a black frame, a trail of
# pieces flying off to the left; small enough for the key.
WINDOWS_FLAG = ('........kkkkkkkk',
                '....k..krrrkgggk',
                '..r..k.krrrkgggk',
                '....k.krrrkgggk.',
                'r..k..kkkkkkkkk.',
                '..b..kkbbbkyyyk.',
                'b...k.kbbbkyyyk.',
                '..b..kbbbkyyyk..',
                '....kkkkkkkkkk..')
FLAG_COLORS = {'k': (20, 12, 14), 'r': (240, 96, 48), 'g': (100, 196, 80), 'b': (60, 136, 210),
               'y': (250, 200, 30)}


def windows_flag(image, centre):
    draw = ImageDraw.Draw(image)
    x0 = centre[0] - (max(len(row) for row in WINDOWS_FLAG) - 1) // 2
    y0 = centre[1] - (len(WINDOWS_FLAG) - 1) // 2
    for row, line in enumerate(WINDOWS_FLAG):
        for column, cell in enumerate(line):
            if cell in FLAG_COLORS:
                draw.point((x0 + column, y0 + row), fill=FLAG_COLORS[cell])
