"""Pixel-art drawings of a controller and keyboard for the Controls page.

Port-only artwork, drawn by code at the game's native resolution: every
shape is a mask lit from the upper left and reduced to a few hard shades,
the way a 1993 artist would shade an object, with no blending or blur.
Results are cached; nothing here depends on the game's resources.
"""

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw

LIGHT = np.array((-0.55, -0.75, 0.62))
LIGHT = LIGHT / np.linalg.norm(LIGHT)

# Ramps run from the outline to the highlight.
SHELL = ((22, 21, 24), (92, 89, 92), (126, 122, 123), (158, 154, 153), (186, 182, 179),
         (210, 206, 201), (232, 228, 221))
SHOULDER = ((18, 18, 20), (60, 59, 63), (82, 81, 86), (104, 103, 108), (128, 127, 132),
            (152, 151, 156), (178, 177, 182))
DARK = ((10, 10, 12), (26, 26, 29), (38, 38, 42), (52, 52, 57), (70, 70, 76), (96, 96, 103),
        (134, 134, 142))


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


def paint(image, levels, ramp, offset=(0, 0), outline=True):
    """Composite shaded levels onto an RGBA image; the rim takes ramp[0]."""
    mask = levels > 0
    if outline:
        padded = np.pad(mask, 1, constant_values=False)
        rim = mask & ~(padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:])
        levels = np.where(rim, 0, levels)
    colors = np.array([(*color, 255) for color in ramp], np.uint8)
    pixels = colors[np.clip(levels, 0, len(ramp) - 1)]
    pixels[~mask] = 0
    layer = Image.fromarray(pixels, 'RGBA')
    image.alpha_composite(layer, offset)


def mask_from(draw_shape, size):
    canvas = Image.new('L', size, 0)
    draw_shape(ImageDraw.Draw(canvas))
    return np.array(canvas) > 127


def circle_mask(radius):
    size = 2 * radius + 1
    yy, xx = np.mgrid[:size, :size] - radius
    return xx * xx + yy * yy <= radius * radius + radius * 0.8


def bezier(points, steps=24):
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = points
    t = np.linspace(0, 1, steps)
    a, b, c, d = (1 - t) ** 3, 3 * t * (1 - t) ** 2, 3 * t * t * (1 - t), t ** 3
    return list(zip(a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3))


def mirrored_outline(half, centre):
    """A symmetric closed outline from its left half (top to bottom)."""
    left = []
    for segment in half:
        left.extend(bezier(segment))
    right = [(2 * centre - x, y) for x, y in reversed(left)]
    return left + right


# One pad body on a 240-pixel-wide grid (y grows downwards); the shoulders
# stand ABOVE pixels above it. Coordinates in the tables below are on the
# body's grid, before that offset.
ABOVE = 12
PAD_WIDTH, PAD_HEIGHT = 241, 172 + ABOVE
BODY_HALF = (
    ((120, 15), (92, 15), (58, 14), (36, 24)),
    ((36, 24), (19, 31), (10, 46), (8, 64)),
    ((8, 64), (5, 92), (12, 124), (24, 146)),
    ((24, 146), (33, 163), (52, 171), (66, 160)),
    ((66, 160), (76, 152), (84, 134), (96, 126)),
    ((96, 126), (106, 120), (113, 119), (120, 119)),
)
SHOULDERS = {
    # bumper and trigger strokes for the left side, mirrored for the right
    'bumper': (((20, 33), (25, 18), (44, 9), (74, 12)), 10),
    'trigger': (((36, 9), (42, 2), (56, 1), (64, 7)), 11),
}
STICK_WELL, STICK_CAP, FACE_RADIUS, DPAD_DISH = 18, 11, 7, 16
FACE = {'y': (176, 40), 'x': (158, 58), 'b': (194, 58), 'a': (176, 76)}
LAYOUTS = {
    'xbox': {'leftstick': (62, 58), 'dpad': (94, 94), 'rightstick': (146, 94), **FACE,
             'back': (104, 58), 'start': (136, 58), 'guide': (120, 34), 'misc1': (120, 72)},
    'playstation': {'dpad': (62, 58), 'leftstick': (94, 96), 'rightstick': (146, 96), **FACE,
                    'back': (86, 30), 'start': (154, 30), 'touchpad': (120, 34),
                    'guide': (120, 76), 'misc1': (120, 90)},
}
# Callout rows, 18 pixels apart, shared by both columns of labels.
ROWS = (-14, 4, 22, 40, 58, 76, 94, 112, 130)
# button: (side, row, the points its line passes on the way to the button);
# 'move' is the left stick's movement, 'leftstick' its click.
# Lines run level from the labels, then bend at most once, so they never
# cross one another or pass over another button.
SHARED_ROUTES = {
    'lefttrigger': ('left', 4, ((31, 4),)), 'righttrigger': ('right', 4, ((209, 4),)),
    'leftshoulder': ('left', 22, ((17, 22),)), 'rightshoulder': ('right', 22, ((223, 22),)),
    'y': ('right', 40, ((184, 40),)), 'b': ('right', 58, ((202, 58),)),
    'x': ('right', 76, ((212, 76), (166, 61))), 'a': ('right', 94, ((194, 94), (182, 82))),
}
ROUTES = {
    'xbox': {**SHARED_ROUTES,
             'back': ('left', -14, ((104, -14), (104, 52))),
             'start': ('right', -14, ((136, -14), (136, 52))),
             'move': ('left', 58, ((43, 58),)), 'dpad': ('left', 94, ((77, 94),)),
             'leftstick': ('left', 76, ((44, 76), (49, 71))),
             'rightstick': ('right', 112, ((164, 112), (159, 107))),
             'misc1': ('left', 130, ((120, 130), (120, 76)))},
    'playstation': {**SHARED_ROUTES,
                    'back': ('left', -14, ((86, -14), (86, 25))),
                    'start': ('right', -14, ((154, -14), (154, 25))),
                    'dpad': ('left', 58, ((45, 58),)), 'move': ('left', 94, ((75, 94),)),
                    'leftstick': ('left', 112, ((78, 112), (81, 109))),
                    'touchpad': ('left', 40, ((99, 40),)),
                    'rightstick': ('right', 112, ((162, 112), (159, 109))),
                    'misc1': ('left', 130, ((120, 130), (120, 94)))},
}


def layout_name(style):
    return 'playstation' if style == 'playstation' else 'xbox'


def body_mask():
    outline = [(x, y + ABOVE) for x, y in mirrored_outline(BODY_HALF, 120)]
    return mask_from(lambda draw: draw.polygon(outline, fill=255), (PAD_WIDTH, PAD_HEIGHT))


def thick_curve(draw, points, width):
    """A stroke with round ends along a smooth curve."""
    path = bezier(points, 32)
    draw.line(path, fill=255, width=width, joint='curve')
    radius = width / 2 - 0.5
    for x, y in (path[0], path[-1]):
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=255)


def shoulder_masks(body):
    """Bumpers hug the body's top corners; triggers rise behind them."""
    size = (body.shape[1], body.shape[0])
    masks = []
    for part in ('trigger', 'bumper'):
        points, width = SHOULDERS[part]

        def stroke(draw, points=points, width=width):
            for flip in (False, True):
                curve = [((240 - x) if flip else x, y + ABOVE) for x, y in points]
                thick_curve(draw, curve, width)
        masks.append(mask_from(stroke, size))
    triggers, bumpers = masks
    return triggers & ~bumpers & ~body, bumpers & ~body


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


# Face buttons: dome colour (None = dark plastic) and symbol colour.
FACE_STYLES = {
    'xbox': {'a': ((96, 178, 74), (20, 34, 16)), 'b': ((210, 78, 70), (44, 14, 12)),
             'x': ((74, 132, 214), (12, 24, 48)), 'y': ((226, 186, 62), (52, 38, 8))},
    'playstation': {'a': (None, (132, 166, 232)), 'b': (None, (232, 116, 116)),
                    'x': (None, (220, 146, 210)), 'y': (None, (98, 204, 176))},
    'nintendo': {name: (None, (214, 214, 220)) for name in 'abxy'},
}
NINTENDO_LETTERS = {'a': 'B', 'b': 'A', 'x': 'Y', 'y': 'X'}


def face_button(image, centre, button, style, radius=FACE_RADIUS):
    from pop2.controls_page import mini_text  # 3x5 letters shared with the keycaps

    dome, ink = FACE_STYLES.get(style, FACE_STYLES['xbox'])[button]
    stamp(image, circle_mask(radius), centre, color_ramp(dome) if dome else DARK, rim=4, dome=.5)
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
    letter = NINTENDO_LETTERS[button] if style == 'nintendo' else button.upper()
    mini_text(draw, cx + 1, cy - 2, letter, ink, 'center')


def small_button(image, centre, icon, size=(13, 10)):
    stamp(image, rounded(*size, radius=min(size) // 2), centre, DARK, rim=2, bias=.1)
    small_icon(ImageDraw.Draw(image), centre[0], centre[1], icon, DARK[6])


def small_icon(draw, x, y, icon, fill):
    if icon == 'view':
        draw.rectangle((x - 3, y - 2, x, y), outline=fill)
        draw.rectangle((x - 1, y, x + 2, y + 2), fill=fill)
    elif icon == 'menu':
        for row in (-2, 0, 2):
            draw.line(((x - 2, y + row), (x + 2, y + row)), fill=fill)
    elif icon == 'share':
        draw.line(((x, y - 2), (x, y + 1)), fill=fill)
        draw.line(((x - 1, y - 1), (x + 1, y - 1)), fill=fill)
    elif icon == 'minus':
        draw.line(((x - 2, y), (x + 2, y)), fill=fill)
    elif icon == 'plus':
        draw.line(((x - 2, y), (x + 2, y)), fill=fill)
        draw.line(((x, y - 2), (x, y + 2)), fill=fill)
    elif icon == 'dot':
        draw.point((x, y), fill=fill)


def arrow(draw, tip, direction, fill):
    x, y = tip
    points = {'^': ((x, y - 2), (x - 2, y), (x + 2, y)), 'v': ((x, y + 2), (x - 2, y), (x + 2, y)),
              '<': ((x - 2, y), (x, y - 2), (x, y + 2)), '>': ((x + 2, y), (x, y - 2), (x, y + 2))}
    draw.polygon(points[direction], fill=fill)


def stick(image, centre):
    cx, cy = centre
    stamp(image, circle_mask(STICK_WELL), (cx, cy), DARK, rim=4, concave=True)
    stamp(image, circle_mask(STICK_CAP), (cx, cy + 1), DARK, rim=6, dome=0.4)
    stamp(image, circle_mask(7), (cx, cy + 1), DARK, rim=3, concave=True, bias=.12)


def dpad(image, centre):
    cx, cy = centre
    stamp(image, circle_mask(DPAD_DISH), (cx, cy), DARK, rim=4, concave=True)
    cross = mask_from(lambda draw: (draw.rectangle((9, 0, 17, 26), fill=255),
                                    draw.rectangle((0, 9, 26, 17), fill=255)), (27, 27))
    stamp(image, cross, (cx, cy), DARK, rim=3, bias=.15)
    draw = ImageDraw.Draw(image)
    for direction, (dx, dy) in (('^', (0, -9)), ('v', (0, 9)), ('<', (-9, 0)), ('>', (9, 0))):
        arrow(draw, (cx + dx, cy + dy), direction, DARK[5])


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
    paint(image, lit_levels(triggers, rim=4, smooth=1.6, bias=.08), DARK)
    paint(image, lit_levels(bumpers, rim=3, smooth=1.0, bias=.04), SHOULDER)
    paint(image, lit_levels(body, rim=10, dome=0.2, span=36, slope=0.1,
                            thresholds=(0.15, 0.38, 0.55, 0.7, 0.9), smooth=3.6), SHELL)
    stick(image, points['leftstick'])
    stick(image, points['rightstick'])
    dpad(image, points['dpad'])
    for name in ('y', 'x', 'b', 'a'):
        face_button(image, points[name], name, style)
    if layout == 'playstation':
        tx, ty = points['touchpad']
        stamp(image, rounded(41, 25, 4), (tx, ty), SHOULDER, rim=3, bias=-.05)
        stamp(image, circle_mask(5), points['guide'], DARK, rim=3, dome=.3)
        small_button(image, points['misc1'], 'dot', (9, 5))
        small_button(image, points['back'], 'share', (7, 11))
        small_button(image, points['start'], 'menu', (7, 11))
    else:
        stamp(image, circle_mask(9), points['guide'], SHOULDER, rim=4, dome=.4)
        stamp(image, circle_mask(5), points['guide'], SHOULDER, rim=2, concave=True, bias=.1)
        nintendo = style == 'nintendo'
        small_button(image, points['back'], 'minus' if nintendo else 'view')
        small_button(image, points['start'], 'plus' if nintendo else 'menu')
        small_button(image, points['misc1'], 'dot' if nintendo else 'share', (10, 7))
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
        icons = {'playstation': ('share', 'menu'), 'nintendo': ('minus', 'plus')}.get(style, ('view', 'menu'))
        small_button(image, centre, icons[token == 'start'])
    elif token in ('leftshoulder', 'rightshoulder', 'lefttrigger', 'righttrigger'):
        trigger = token.endswith('trigger')
        stamp(image, rounded(15, 13 if trigger else 9, 4), centre, SHOULDER, rim=3)
        mini_text(ImageDraw.Draw(image), 9, 4, pad_name(token, style), (18, 18, 20), 'center')
    elif token in ('leftstick', 'rightstick'):
        stamp(image, circle_mask(6), centre, DARK, rim=3, dome=.4)
        mini_text(ImageDraw.Draw(image), 9, 4, SHORT_NAMES[token], DARK[6], 'center')
    else:
        return None
    return image


# -- keyboard ---------------------------------------------------------------
@lru_cache(maxsize=None)
def keycap(width, height, color=None):
    """One key seen from above and a little in front: cap, sides and skirt."""
    ramp = color_ramp(color) if color else DARK
    image = Image.new('RGBA', (width, height), (*ramp[0], 255))
    draw = ImageDraw.Draw(image)
    right, bottom = width - 1, height - 1
    draw.rectangle((1, 1, right - 1, bottom - 1), fill=ramp[2])          # sides
    draw.rectangle((1, bottom - 3, right - 1, bottom - 1), fill=ramp[1])  # front skirt
    draw.rectangle((2, 1, right - 2, bottom - 4), fill=ramp[4])          # cap
    draw.line(((2, 1), (right - 2, 1)), fill=ramp[5])                     # lit top edge
    draw.line(((2, 2), (2, bottom - 5)), fill=ramp[5])                    # lit left edge
    draw.line(((right - 2, 2), (right - 2, bottom - 4)), fill=ramp[3])    # shaded right
    draw.line(((3, 1), (5, 1)), fill=ramp[6])                             # a glint
    for corner in ((0, 0), (right, 0), (0, bottom), (right, bottom)):
        image.putpixel(corner, (0, 0, 0, 0))
    return image


def legend_ink(color):
    return tone(color, .22) if color else DARK[6]


@lru_cache(maxsize=None)
def keyboard_case(width, height):
    mask = rounded(width, height, 7)
    image = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    paint(image, lit_levels(mask, rim=5, slope=0.08, thresholds=(0.15, 0.38, 0.55, 0.7, 0.9),
                            smooth=2.0), SHELL)
    return image
