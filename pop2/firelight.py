"""Firelight traced over painted rock, once per room.

A port improvement for the cave ambience. The room is only a painting, so the
rock's shape is read from it: lit paint stands forward and dark paint falls
back, which is how the artist meant the eye to read the veins and the hollows.
The recess a torch stands in is its sprite's outline, sunk into that surface.

The flame is a light with an area, not a point: its nine frames are cut into a
few cells, and rays run from each cell over the relief. A surface takes light
by how much it faces the cell, how far away it is, and whether rock stands in
between. Each frame then adds up the cells by how much of it burns there, so a
tall frame lights the top of the recess and shifts the shadows, and a small one
lights less. That leaves one map per frame, read back cheaply on every tick.

The result is only numbers from 0 to 1. Turning them into palette colours is
left to the ambience, which holds them to the room's palette.
"""

import numpy

# How much of a pixel's brightness becomes height, in pixels of depth. Broad
# shapes come from a wide blur, the veins from narrow ones. Shades are raised
# to a power below one because the back wall's relief is all in its dark paint.
ROCK_SHADE = 0.6
ROCK_MASS = 26.0
ROCK_VEINS = 30.0
RECESS_DEPTH = 7.0
# The flame stands this far off the rock behind it.
FLAME_LIFT = 14.0
# Pixels: where the light is a quarter gone, and where it has run out.
LIGHT_NEAR = 34.0
LIGHT_REACH = 125
# Cells of the flame, in pixels.
CELL_WIDTH, CELL_HEIGHT = 6, 8
# Points tested along each ray, and the slope over which rock goes from letting
# the light by to stopping it.
RAY_STEPS = 14
SHADOW_EDGE = 1.6
RAY_CLEARANCE = 2.5
# The warm light rock throws back on what is around it.
BOUNCE = 0.3
BOUNCE_SPREAD = 12.0
# Highlights are pressed down so that the light fades out across the rock
# instead of stopping at the edge of a white patch.
EXPOSURE = 5.0
# The brightest few pixels are left out of what counts as full light.
PEAK_PERCENTILE = 99.5
# The nine frames are much alike, far more than a real flame from one moment to
# the next, so what sets each frame's light apart from the average is deepened.
FLICKER_DEPTH = 6.0


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
    """(x, y) of each cell of the flame, and [frame, cell] of how much it burns."""
    frames, rows, columns = numpy.nonzero(heat)
    mass = heat[frames, rows, columns]
    _cells, cell = numpy.unique(rows // CELL_HEIGHT * 4096 + columns // CELL_WIDTH, return_inverse=True)
    cell = cell.ravel()
    count = int(cell.max()) + 1
    total = numpy.bincount(cell, mass, count)
    places = numpy.stack((numpy.bincount(cell, mass * columns, count) / total,
                          numpy.bincount(cell, mass * rows, count) / total), axis=1)
    burning = numpy.zeros((len(heat), count))
    numpy.add.at(burning, (frames, cell), mass)
    return places, burning / burning.sum(axis=1).mean()


class Relief:
    """The rock in one window of the room."""

    def __init__(self, height):
        self.height = height
        self.down, self.across = numpy.gradient(height)
        self.length = numpy.sqrt(self.across ** 2 + self.down ** 2 + 1)
        rows, columns = numpy.mgrid[:height.shape[0], :height.shape[1]]
        self.rows, self.columns = rows.astype(numpy.float64), columns.astype(numpy.float64)

    def shadow(self, to_x, to_y, to_z, distance):
        """How much of each point can see the light, by walking towards it."""
        height, rows, columns = self.height, self.rows, self.columns
        last_row, last_column = height.shape[0] - 1, height.shape[1] - 1
        seen = numpy.ones_like(height)
        for step in range(1, RAY_STEPS + 1):
            along = step / (RAY_STEPS + 1)
            row = (rows + to_y * along + 0.5).astype(numpy.int32).clip(0, last_row)
            column = (columns + to_x * along + 0.5).astype(numpy.int32).clip(0, last_column)
            clear = height + to_z * along - height[row, column]
            # A point cannot shade itself, and the flame stands in free air.
            counted = (distance * along > RAY_CLEARANCE) & (distance * (1 - along) > RAY_CLEARANCE)
            seen = numpy.minimum(seen, numpy.where(counted, (clear / SHADOW_EDGE * 0.5 + 0.5).clip(0, 1), 1.0))
        return seen

    def light_from(self, x, y):
        """The light one cell of flame, at a place in the window, casts on the rock."""
        lift = self.height[int(y), int(x)] + FLAME_LIFT
        to_x, to_y, to_z = x - self.columns, y - self.rows, lift - self.height
        squared = to_x ** 2 + to_y ** 2 + to_z ** 2
        distance = numpy.sqrt(squared)
        facing = ((to_z - self.across * to_x - self.down * to_y) / (self.length * distance)).clip(0, 1)
        fading = (1 - squared / LIGHT_REACH ** 2).clip(0, 1) ** 2
        return facing * fading / (1 + squared / LIGHT_NEAR ** 2) * self.shadow(to_x, to_y, to_z, distance)


def trace_firelight(shades, recess, heat, left, top):
    """Light on the rock around a torch.

    shades: the room's brightness, 0..1, drawn with the torch unlit.
    recess: [y, x] of the torch sprite's outline, placed at left and top.
    heat: [frame, y, x] of how hot each pixel of the sprite burns.
    Returns [frame, y, x] of light, 0..1, and the left and top of that window.
    """
    if not heat.any():
        return numpy.zeros((len(heat), 1, 1), dtype=numpy.float32), left, top
    room_height, room_width = shades.shape
    rows, columns = numpy.nonzero(heat.any(axis=0))
    middle_x, middle_y = int(columns.mean()) + left, int(rows.mean()) + top
    window_left, window_right = max(0, middle_x - LIGHT_REACH), min(room_width, middle_x + LIGHT_REACH)
    window_top, window_bottom = max(0, middle_y - LIGHT_REACH), min(room_height, middle_y + LIGHT_REACH)
    outline = numpy.zeros(shades.shape)
    bottom, right = min(room_height, top + recess.shape[0]), min(room_width, left + recess.shape[1])
    outline[top:bottom, left:right] = recess[:bottom - top, :right - left]
    window = slice(window_top, window_bottom), slice(window_left, window_right)
    relief = Relief(rock_height(shades[window], outline[window]))
    places, burning = flame_cells(heat)
    cast = numpy.stack([relief.light_from(x + left - window_left, y + top - window_top) for x, y in places])
    lights = numpy.tensordot(burning, cast, axes=1)
    # By ratio, so that a small frame dims the light and cannot put it out.
    average = lights.mean(axis=0)
    lights = average * (lights / numpy.maximum(average, 1e-9)) ** FLICKER_DEPTH
    lights = lights / max(numpy.percentile(average, PEAK_PERCENTILE), 1e-6)
    lights = numpy.stack([light + BOUNCE * gaussian(light, BOUNCE_SPREAD) for light in lights])
    pressed = (1 - numpy.exp(-EXPOSURE * lights)) / (1 - numpy.exp(-EXPOSURE))
    return pressed.clip(0, 1).astype(numpy.float32), window_left, window_top
