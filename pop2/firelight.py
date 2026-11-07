"""Firelight traced over painted rock, once per room.

A port improvement for the cave ambience. The room is only a painting, so the
rock's shape is read from it: lit paint stands forward and dark paint falls
back, which is how the artist meant the eye to read the veins and the hollows.

The flame is a light with an area, not a point: it is cut into a few cells, and
rays run from each cell over the relief. A surface takes light by how much it
faces the cell, how far away it is, and whether rock stands in between.

That is done once. What makes it a candle is that the light then changes shape:
each frame of flame is measured all the way round its middle, and where it burns
further than usual the light reaches further that way. Raising the light to a
power does that without moving the rock's veins, and nothing lit becomes dark or
the reverse. Moving the whole light instead, tried first, only gave a steady oval
that changed place.

The torch's own recess is painted as already lit, so it takes little more. Lit
as much as the rock, it stood out as a bright oval plate the shape of the sprite.

The result is only numbers from 0 to 1. Turning them into palette colours is
left to the ambience, which holds them to the room's palette.
"""

from dataclasses import dataclass
import math

import numpy

# How much of a pixel's brightness becomes height, in pixels of depth. Broad
# shapes come from a wide blur, the veins from narrow ones. Shades are raised
# to a power below one because the back wall's relief is all in its dark paint.
ROCK_SHADE = 0.6
ROCK_MASS = 12.0
ROCK_VEINS = 16.0
# The flame stands this far off the rock behind it. Any closer, and the rim of the
# recess shuts the light in: a bright plate with an edge, whatever the flame does.
FLAME_LIFT = 32.0
# Pixels: where the light is a quarter gone, and where it has run out.
LIGHT_NEAR = 18.0
LIGHT_REACH = 70
# Cells of the flame, in pixels.
CELL_WIDTH, CELL_HEIGHT = 10, 14
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
# How much of the light the torch's painted recess takes.
RECESS_LIGHT = 0.5
RECESS_EDGE = 7.0
# Directions a flame is measured in, and how many of them its outline is blurred
# over, so that one tongue of flame does not throw a spoke of light.
DIRECTIONS = 48
OUTLINE_SOFTNESS = 2.0


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


def around(values, softness):
    """Blurred around the circle, along the last axis."""
    count = values.shape[-1]
    spectrum = numpy.fft.rfft(values, axis=-1)
    waves = numpy.arange(spectrum.shape[-1]) * softness * math.tau / count
    return numpy.fft.irfft(spectrum * numpy.exp(-waves ** 2 / 2), count, axis=-1)


def rock_height(shades):
    """Height in pixels from brightness 0..1."""
    shades = shades ** ROCK_SHADE
    veins = 0.6 * gaussian(shades, 2.2) + 0.4 * gaussian(shades, 0.9)
    return ROCK_MASS * gaussian(shades, 7.0) + ROCK_VEINS * veins


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


def direction_of(across, down):
    """Where among the DIRECTIONS a point lies from the flame's middle."""
    return (numpy.arctan2(down, across) + math.pi) / math.tau * DIRECTIONS % DIRECTIONS


def flame_outlines(heat):
    """(x, y) of the flame's middle, and [frame, direction] of how much further
    than usual each frame burns that way, as a share of the flame's usual size."""
    mass = heat.sum(axis=0)
    rows, columns = numpy.mgrid[:heat.shape[1], :heat.shape[2]]
    middle_x, middle_y = (mass * columns).sum() / mass.sum(), (mass * rows).sum() / mass.sum()
    reach = numpy.zeros((len(heat), DIRECTIONS))
    for frame, burning in enumerate(heat):
        down, across = numpy.nonzero(burning)
        down, across = down - middle_y, across - middle_x
        numpy.maximum.at(reach[frame], direction_of(across, down).astype(numpy.int32), numpy.hypot(across, down))
    reach = around(reach, OUTLINE_SOFTNESS)
    alight = heat.any(axis=(1, 2))
    usual = reach[alight].mean(axis=0)
    return middle_x, middle_y, numpy.where(alight[:, None], (reach - usual) / usual.mean(), 0.0)


def flame_burn(heat):
    """[frame] of how hot each frame burns, one being usual."""
    burnt = heat.sum(axis=(1, 2))
    return burnt / burnt[burnt > 0].mean()


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

    def flame(self, places, shares):
        """All of the flame's light."""
        return sum(share * self.light_from(x, y) for (x, y), share in zip(places, shares))


def pressed(light):
    return (1 - numpy.exp(-EXPOSURE * light)) / (1 - numpy.exp(-EXPOSURE))


@dataclass(frozen=True)
class Firelight:
    """Light on the rock around a torch, in one window of the room."""

    left: int
    top: int
    rest: numpy.ndarray
    # [y, x]: where among the directions each pixel lies, and the share of light
    # it takes.
    direction: numpy.ndarray
    taken: numpy.ndarray
    # For each frame of flame: [direction] of how far it burns, and how hot.
    outlines: numpy.ndarray
    burn: numpy.ndarray

    def at(self, reach, strength):
        """The light at a strength, and [direction] of how far it goes each way,
        one being as traced. Always 0 to 1."""
        lit = pressed(self.rest * strength).clip(1e-6, 1)
        # Between two directions, so that no spoke of light shows.
        way = self.direction.astype(numpy.int32)
        between = self.direction - way
        here = reach[way] * (1 - between) + reach[(way + 1) % DIRECTIONS] * between
        return lit ** (1 / here) * self.taken

    @property
    def steady(self):
        return self.at(numpy.ones(DIRECTIONS), 1.0)


def trace_firelight(shades, recess, heat, left, top):
    """Light on the rock around a torch.

    shades: the room's brightness, 0..1, drawn with the torch unlit.
    recess: [y, x] of the torch sprite's outline, placed at left and top.
    heat: [frame, y, x] of how hot each pixel of the sprite burns.
    """
    if not heat.any():
        return Firelight(left, top, numpy.zeros((1, 1), dtype=numpy.float32),
                         numpy.zeros((1, 1), dtype=numpy.float32), numpy.ones((1, 1), dtype=numpy.float32),
                         numpy.zeros((len(heat), DIRECTIONS)), numpy.zeros(len(heat)))
    room_height, room_width = shades.shape
    middle_x, middle_y, outlines = flame_outlines(heat)
    middle_x, middle_y = middle_x + left, middle_y + top
    window_left, window_right = max(0, int(middle_x) - LIGHT_REACH), min(room_width, int(middle_x) + LIGHT_REACH)
    window_top, window_bottom = max(0, int(middle_y) - LIGHT_REACH), min(room_height, int(middle_y) + LIGHT_REACH)
    outline = numpy.zeros(shades.shape)
    bottom, right = min(room_height, top + recess.shape[0]), min(room_width, left + recess.shape[1])
    outline[top:bottom, left:right] = recess[:bottom - top, :right - left]
    window = slice(window_top, window_bottom), slice(window_left, window_right)
    relief = Relief(rock_height(shades[window]).astype(numpy.float32))
    places, shares = flame_cells(heat)
    cast = relief.flame(places + (left - window_left, top - window_top), shares)
    rest = (cast + BOUNCE * gaussian(cast, BOUNCE_SPREAD)) / max(numpy.percentile(cast, PEAK_PERCENTILE), 1e-6)
    rows, columns = numpy.mgrid[window_top:window_bottom, window_left:window_right]
    direction = direction_of(columns - middle_x, rows - middle_y).astype(numpy.float32)
    taken = 1 - (1 - RECESS_LIGHT) * gaussian(outline[window], RECESS_EDGE)
    return Firelight(window_left, window_top, rest.astype(numpy.float32), direction, taken.astype(numpy.float32),
                     outlines, flame_burn(heat))
