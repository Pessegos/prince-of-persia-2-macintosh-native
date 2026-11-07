"""Firelight traced over painted rock, once per room.

A port improvement for the cave ambience. The room is only a painting, so the
rock's shape is read from it: lit paint stands forward and dark paint falls
back, which is how the artist meant the eye to read the veins and the hollows.
The recess a torch stands in is its sprite's outline, sunk into that surface.

The flame is a light with an area, not a point: it is cut into a few cells, and
rays run from each cell over the relief. A surface takes light by how much it
faces the cell, how far away it is, and whether rock stands in between.

That is done five times: with the flame at rest, and moved to each side, up and
down. Between those a tick only has to mix, so the flame can stand anywhere
among them and the shadows swing with it. One map for each of the nine frames
could not do that. The frames come in random order, so following them made the
light tremble in place, a steady oval around the torch, and never lean.

The result is only numbers from 0 to 1. Turning them into palette colours is
left to the ambience, which holds them to the room's palette.
"""

from dataclasses import dataclass

import numpy

# How much of a pixel's brightness becomes height, in pixels of depth. Broad
# shapes come from a wide blur, the veins from narrow ones. Shades are raised
# to a power below one because the back wall's relief is all in its dark paint.
ROCK_SHADE = 0.6
ROCK_MASS = 12.0
ROCK_VEINS = 16.0
RECESS_DEPTH = 5.0
# The flame stands this far off the rock behind it. Relief any deeper against
# this, and the rim of the recess shuts the light in: it stays one oval, however
# the flame moves.
FLAME_LIFT = 20.0
# Pixels: where the light is a quarter gone, and where it has run out.
LIGHT_NEAR = 40.0
LIGHT_REACH = 125
# Cells of the flame, in pixels.
CELL_WIDTH, CELL_HEIGHT = 10, 14
# How far the flame is moved each way, in pixels.
SWING = 14.0
# Points tested along each ray, and the slope over which rock goes from letting
# the light by to stopping it. Shadows are worked out on every other pixel: the
# veins in the light come from which way the rock faces, on every pixel.
RAY_STEPS = 14
SHADOW_EDGE = 1.6
RAY_CLEARANCE = 2.5
SHADOW_STRIDE = 2
# The warm light rock throws back on what is around it.
BOUNCE = 0.3
BOUNCE_SPREAD = 12.0
# Highlights are pressed down so that the light fades out across the rock
# instead of stopping at the edge of a white patch. Too much of this leaves the
# rock by the flame always at full light, with nothing left to move.
EXPOSURE = 1.8
# The brightest few pixels are left out of what counts as full light.
PEAK_PERCENTILE = 99.5


def gaussian(values, sigma):
    radius = int(sigma * 3 + 0.5)
    offsets = numpy.arange(-radius, radius + 1)
    kernel = numpy.exp(-offsets ** 2 / (2 * sigma * sigma))
    kernel /= kernel.sum()
    padded = numpy.pad(values, radius, mode='edge')
    across = sum(weight * padded[:, radius + offset:padded.shape[1] - radius + offset]
                 for offset, weight in zip(offsets, kernel))
    return sum(weight * across[radius + offset:across.shape[0] - radius + offset]
               for offset, weight in zip(offsets, kernel))


def rock_height(shades, recess):
    """Height in pixels from brightness 0..1 and a mask of the sunken recess."""
    shades = shades ** ROCK_SHADE
    veins = 0.6 * gaussian(shades, 2.2) + 0.4 * gaussian(shades, 0.9)
    return ROCK_MASS * gaussian(shades, 7.0) + ROCK_VEINS * veins - RECESS_DEPTH * gaussian(recess, 2.0)


def flame_cells(heat):
    """(x, y) of each cell of the flame as it burns on average, and its share."""
    burning = heat.sum(axis=0)
    rows, columns = numpy.nonzero(burning)
    mass = burning[rows, columns]
    _cells, cell = numpy.unique(rows // CELL_HEIGHT * 4096 + columns // CELL_WIDTH, return_inverse=True)
    cell = cell.ravel()
    count = int(cell.max()) + 1
    total = numpy.bincount(cell, mass, count)
    places = numpy.stack((numpy.bincount(cell, mass * columns, count) / total,
                          numpy.bincount(cell, mass * rows, count) / total), axis=1)
    return places, total / total.sum()


def flame_lean(heat):
    """[frame, (x, y)] of how far each frame's middle stands from the average one,
    in units of how far they usually do, and [frame] of how hot it burns."""
    burnt = heat.sum(axis=(1, 2))
    rows, columns = numpy.mgrid[:heat.shape[1], :heat.shape[2]]
    alight = numpy.maximum(burnt, 1e-9)
    middles = numpy.stack(((heat * columns).sum(axis=(1, 2)) / alight,
                           (heat * rows).sum(axis=(1, 2)) / alight), axis=1)
    lean = middles - middles[burnt > 0].mean(axis=0)
    spread = lean[burnt > 0].std(axis=0)
    lean = numpy.where(spread > 0, lean / numpy.where(spread > 0, spread, 1), 0.0)
    return lean, burnt / burnt[burnt > 0].mean()


class Relief:
    """The rock in one window of the room."""

    def __init__(self, height):
        self.height = height
        self.down, self.across = numpy.gradient(height)
        self.length = numpy.sqrt(self.across ** 2 + self.down ** 2 + 1)
        rows, columns = numpy.mgrid[:height.shape[0], :height.shape[1]]
        self.rows, self.columns = rows.astype(numpy.float32), columns.astype(numpy.float32)

    def shadow(self, to_x, to_y, to_z, distance):
        """How much of each point can see the light, by walking towards it."""
        height, stride = self.height, SHADOW_STRIDE
        rows, columns = self.rows[::stride, ::stride], self.columns[::stride, ::stride]
        to_x, to_y = to_x[::stride, ::stride], to_y[::stride, ::stride]
        to_z, distance = to_z[::stride, ::stride], distance[::stride, ::stride]
        surface = height[::stride, ::stride]
        last_row, last_column = height.shape[0] - 1, height.shape[1] - 1
        seen = numpy.ones_like(surface)
        for step in range(1, RAY_STEPS + 1):
            along = step / (RAY_STEPS + 1)
            row = (rows + to_y * along + 0.5).astype(numpy.int32).clip(0, last_row)
            column = (columns + to_x * along + 0.5).astype(numpy.int32).clip(0, last_column)
            clear = surface + to_z * along - height[row, column]
            # A point cannot shade itself, and the flame stands in free air.
            counted = (distance * along > RAY_CLEARANCE) & (distance * (1 - along) > RAY_CLEARANCE)
            seen = numpy.minimum(seen, numpy.where(counted, (clear / SHADOW_EDGE * 0.5 + 0.5).clip(0, 1), 1.0))
        spread = seen.repeat(stride, axis=0).repeat(stride, axis=1)
        return spread[:height.shape[0], :height.shape[1]]

    def light_from(self, x, y):
        """The light one cell of flame, at a place in the window, casts on the rock."""
        row = min(max(int(y), 0), self.height.shape[0] - 1)
        column = min(max(int(x), 0), self.height.shape[1] - 1)
        lift = self.height[row, column] + FLAME_LIFT
        to_x, to_y, to_z = x - self.columns, y - self.rows, lift - self.height
        squared = to_x ** 2 + to_y ** 2 + to_z ** 2
        distance = numpy.sqrt(squared)
        facing = ((to_z - self.across * to_x - self.down * to_y) / (self.length * distance)).clip(0, 1)
        fading = (1 - squared / LIGHT_REACH ** 2).clip(0, 1) ** 2
        return facing * fading / (1 + squared / LIGHT_NEAR ** 2) * self.shadow(to_x, to_y, to_z, distance)

    def flame_at(self, places, shares, x, y):
        """All of the flame's light with the flame moved x and y pixels."""
        return sum(share * self.light_from(place_x + x, place_y + y)
                   for (place_x, place_y), share in zip(places, shares))


def pressed(light):
    return (1 - numpy.exp(-EXPOSURE * light)) / (1 - numpy.exp(-EXPOSURE))


@dataclass(frozen=True)
class Firelight:
    """Light on the rock around a torch, in one window of the room."""

    left: int
    top: int
    rest: numpy.ndarray
    # [right, left, down, up]: what moving the flame that way changes.
    swings: numpy.ndarray
    # For each frame of flame: where it leans, and how hot it burns.
    lean: numpy.ndarray
    burn: numpy.ndarray

    def at(self, x, y, strength):
        """The light with the flame x and y pixels from rest, up to SWING, as a
        share of what it casts at that strength. Always 0 to 1."""
        across = self.swings[0 if x >= 0 else 1] * min(abs(x) / SWING, 1.0)
        down = self.swings[2 if y >= 0 else 3] * min(abs(y) / SWING, 1.0)
        return pressed(numpy.maximum(self.rest + across + down, 0) * strength).clip(0, 1)


def trace_firelight(shades, recess, heat, left, top):
    """Light on the rock around a torch.

    shades: the room's brightness, 0..1, drawn with the torch unlit.
    recess: [y, x] of the torch sprite's outline, placed at left and top.
    heat: [frame, y, x] of how hot each pixel of the sprite burns.
    """
    if not heat.any():
        return Firelight(left, top, numpy.zeros((1, 1), dtype=numpy.float32),
                         numpy.zeros((4, 1, 1), dtype=numpy.float32),
                         numpy.zeros((len(heat), 2)), numpy.zeros(len(heat)))
    room_height, room_width = shades.shape
    rows, columns = numpy.nonzero(heat.any(axis=0))
    middle_x, middle_y = int(columns.mean()) + left, int(rows.mean()) + top
    window_left, window_right = max(0, middle_x - LIGHT_REACH), min(room_width, middle_x + LIGHT_REACH)
    window_top, window_bottom = max(0, middle_y - LIGHT_REACH), min(room_height, middle_y + LIGHT_REACH)
    outline = numpy.zeros(shades.shape)
    bottom, right = min(room_height, top + recess.shape[0]), min(room_width, left + recess.shape[1])
    outline[top:bottom, left:right] = recess[:bottom - top, :right - left]
    window = slice(window_top, window_bottom), slice(window_left, window_right)
    relief = Relief(rock_height(shades[window], outline[window]).astype(numpy.float32))
    places, shares = flame_cells(heat)
    places = places + (left - window_left, top - window_top)
    moves = ((0, 0), (SWING, 0), (-SWING, 0), (0, SWING), (0, -SWING))
    casts = [relief.flame_at(places, shares, *move) for move in moves]
    peak = max(numpy.percentile(casts[0], PEAK_PERCENTILE), 1e-6)
    maps = numpy.stack([(cast + BOUNCE * gaussian(cast, BOUNCE_SPREAD)) / peak for cast in casts])
    lean, burn = flame_lean(heat)
    return Firelight(window_left, window_top, maps[0].astype(numpy.float32),
                     (maps[1:] - maps[0]).astype(numpy.float32), lean, burn)
