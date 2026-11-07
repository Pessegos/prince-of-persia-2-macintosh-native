"""Optional dust, ash, water drops and traced firelight for cavern rooms.

A port improvement. Nothing here comes from the original game, and nothing
here touches it: the effect is drawn on the frame, behind the actors, while the
"Cave ambience" menu item is on. It reads the room and never writes game state.
Its random numbers come from a private generator, so turning it on cannot
change an opponent, a route or a test.

The look is held to the 1993 art by two rules. Every pixel it leaves on the
frame is a colour of the room's own palette, and everything moves once per game
tick like the rest of the game: motion any smoother stood out against it. Soft
things are done the way a 256-colour game did them. A grain of dust is a small
soft spot, each blend landing on the nearest palette colour, and the light of
a torch and around the lava is a table of what each palette colour becomes at
each brightness, stepped through an ordered dither.

It is meant to be barely noticed, and it is tied to the scenery. Drops hang
from the tips of the stalactites and end on the floor or in the lava, single
grains of ash rise from the lava and the flame, and a little dust drifts through
the open air. The flame stays exactly the game's. Its light does not: the frames'
painted wall keeps still, and the light is traced over the relief of the rock by
pop2.firelight and changes shape with the flame, like a candle's. The user rejected
a wider glow over everything and sparks with trails as far too much: the light
must stay in the rock, not on top of it.
"""

from dataclasses import dataclass, field, replace
from functools import lru_cache
import math
import random

import numpy
from PIL import Image, ImageFilter

from pop2.firelight import DIRECTIONS, Firelight, gaussian, trace_firelight
from pop2.opponent_generation import EMPTY_TILES, WALL_TILES
from pop2.terrain import TILE_HEIGHT, TILE_WIDTH, floor_y

WIDTH, HEIGHT = 510, 365

# The cavern levels. The look was settled on level four, room 17 of the development
# menu, where the torch, the lava pool and the long stalactites are all in view.
AMBIENCE_LEVELS = frozenset({3, 4, 5})

# How far above a floor's walking line its surface starts in the art.
FLOOR_STRIP = 14

# Scenery darker than this is open air against the cave's back wall.
AIR_LUMINANCE = 60
TIP_LUMINANCE = 72
TIP_CLEARANCE = 12
TIP_LENGTH = 8
TIP_WIDTH = 4
TIP_TAPER = 7
DRIP_SPACING = 26
MOST_DRIPS = 4
SHORTEST_FALL = 48
# How far in front of a floor's walking line a drop may land, by source.
LANDING_DEPTH = (-3, 3)

# A stalactite drips to its own steady rhythm. All times are game ticks.
TICKS_BETWEEN_DROPS = (90, 230)
DROP_RHYTHM_JITTER = 14
SWELL_TICKS = 18
GRAVITY = 1.15
FASTEST_FALL = 15.0

# Dust is two kinds of grain. It read as snow when there was a lot of one kind:
# pale, evenly spread, half of it falling. So it is sparse, it gathers in patches,
# only the coarse grains ever sink, and its colour is the rock's, not white.
#
# Fine grains are small opaque pixels. The brighter one is, the shorter it lasts:
# most are dim and stay a while, and now and then one shines for a few seconds and
# is gone. Coarse grains are soft, the slowest, and heavy enough to come down.
@dataclass(frozen=True)
class DustKind:
    """Times are ticks, speeds pixels a tick."""

    count: int
    speed: tuple
    # How long the dimmest grains of this kind last.
    life: int
    # How wide its spot is in pixels, how much of what is under it it hides, and
    # its colour in the dark.
    softness: float
    strength: float
    ink: int
    # The share of them that sink, how soon they take up a change in the air, and
    # how bright they can get on the way to DUST_PALE_INK.
    sinkers: float
    follows: float
    brightest: float


DUST_SOFTNESS = 0.8
DUST_SHARPNESS = 0.36
FINE_DUST = DustKind(24, (0.13, 0.26), 360, DUST_SHARPNESS, 1.0, 104, 0.0, 0.1, 1.0)
COARSE_DUST = DustKind(5, (0.11, 0.2), 540, DUST_SOFTNESS, 0.62, 67, 0.8, 0.06, 0.0)
DUST_KINDS = (FINE_DUST, COARSE_DUST)
MOST_DUST = sum(kind.count for kind in DUST_KINDS)
# A room with no fire has less of it, and none that shines: with nothing to light
# it, it is only just there.
QUIET_DUST = (replace(FINE_DUST, count=12, brightest=0.3), replace(COARSE_DUST, count=3, strength=0.45))
# Most fine grains are dim: a grain's brightness is a random number raised to this
# power. The brightest last this long, and life falls fast as they brighten.
DUST_SKEW = 2.5
DUST_BRIGHT_LIFE = 36
DUST_LIFE_CURVE = 0.6
DUST_LIFE_SPREAD = (0.8, 1.2)
DUST_LONGEST_LIFE = int(max(kind.life for kind in DUST_KINDS) * DUST_LIFE_SPREAD[1])
# How much of its span a grain takes to come, and to go.
DUST_FADE_IN = 0.14
DUST_FADE_OUT = 0.24
# A new grain needs this much clear air ahead, or it could only flash by.
DUST_SHORTEST_LIFE = 140
# Dust gathers in a few pockets of still air, this far apart at the least, and a
# grain starts about this far from the middle of one, all in pixels. Keeping new
# grains as far as possible from the rest spread them as evenly as snow.
DUST_POCKETS = 4
DUST_POCKETS_APART = 110
DUST_PATCH = 24
DUST_TRIES = 24
# Radians around rightwards: one slow draught crosses the room. With every heading
# of its own the dust looked like insects.
DUST_HEADING = (-0.6, 0.25)
# Dust shows best where there is light, so that is where most of it starts.
DUST_BY_FLAME = 0.25
DUST_NEAR_FLAME = (14, 70)
DUST_BY_POOL = 0.1
# The draught turns very slowly, and each grain sways in it. A grain has a
# little weight: it takes a while to follow any change in the air.
DRAUGHT_TURN = 0.3
DUST_SWAY = 0.05
# Air is drawn in beside a flame, rises through it and spreads out over it.
HEAT_REACH = 84
HEAT_PULL = 0.1
HEAT_RISE = 0.22
HEAT_SPREAD = 0.06
HEAT_PLUME = 12
POOL_DRAUGHT = 0.12
# Ticks of air a grain looks ahead. With rock there it slows and settles.
DUST_LOOK_AHEAD = 16
DUST_SETTLE = 36
DUST_BRAKE = 0.93
# How fast a sinking grain sinks. It starts with a floor no further below it than
# this, in pixels, and the draught carries it less than the others, or it would
# only ever settle on a pillar. One that reaches a floor comes down on it this far
# before the walking line, in pixels, and lies there this many ticks, fading, as a
# single pale speck.
DUST_SINK = (0.1, 0.2)
DUST_DROP = 70
DUST_SINKER_DRIFT = 0.5
DUST_REST_DEPTH = (2, 12)
DUST_REST = (80, 170)
DUST_LANDING_REACH = 40
# A grain's colour warms as light falls on it, and a soft grain comes into focus:
# one sharp pixel that waits, then slides into the next. As it tumbles a face of it
# catches the fire for a moment. There is nothing to catch in the dark, so the
# glints are as strong as the light on the grain.
DUST_LIT = 0.3
DUST_GLINT = 0.3
DUST_FLASH = 1.5
DUST_LYING = 0.75
DUST_SPIN = (0.13, 0.27)
DUST_FOCUS_LIGHT = 0.35
DUST_POOL_REACH = (84, 62)
# Dust over the lava is a dull glow, so that it is not read as more ash.
DUST_POOL_STRENGTH = 0.6

ASH_LIFE = (34, 76)
MOST_ASH = 5
ASH_PER_TICK = 0.036
EMBER_PER_TICK = 0.03
EMBER_LIFE = (18, 34)

# The nine lit frames of every cavern torch (CaveGetTorchFrame 8:3b4e picks one
# at random each tick), and the same recess with the torch out. The lit frames
# paint a rich wall, but about a hundred loose pixels of it differ from frame to
# frame and blink at random. Those keep one colour here, and the flame is the
# game's. The unlit recess is only used for what the wall is made of.
TORCH_FRAMES = range(3581, 3590)
UNLIT_TORCH = 3590
FIRE_RED = 200
# The flame's dark rim: its red is also painted on the wall's cracks, so it only
# counts within this many pixels of the flame.
FLAME_RIM_RED = 120
FLAME_RIM = 3
# Share of a torch that must show for it to be there at all. Most stand a little
# behind a pillar, and a few are shut behind one: those have no fire to speak of.
TORCH_SEEN = 0.35

# Light multiplies what the paint already is, so dark hollows stay dark and only
# the rock lights up. A wide light laid over everything looked like a bomb about
# to go off.
LIGHT_LEVELS = 10
AURA_GAIN, AURA_ADD = (1.9, 1.45, 1.05), (26.0, 11.0, 1.0)
# A candle's light keeps changing shape. Each frame of flame says how far it burns
# in each direction, and the light reaches that much further or less that way:
# quickly for the licks of the flame, slowly for the way it breathes. DEPTH is how
# much of the light's reach one share of the flame's size moves. How hot the frame
# burns is followed too, deepened because the nine frames are much alike.
QUICK_FOLLOW, QUICK_DEPTH = 0.3, 1.6
SLOW_FOLLOW, SLOW_DEPTH = 0.12, 2.4
SHORTEST_REACH, LONGEST_REACH = 0.6, 1.4
FLICKER_FOLLOW = 0.35
FLICKER_DEPTH = 2.5
# How far past its step a pixel's light must go before the pixel changes, in
# steps. Without this a third of the pixels that changed flipped straight back.
LIGHT_HOLD = 0.5
# How far the light on the rock is spread to tell how lit the air is before it.
AIR_LIGHT_SPREAD = 6.0
# Fainter still: the lava seems to radiate, and it must not light the room.
POOL_GLOW_REACH = (34, 30)
POOL_GLOW_GAIN, POOL_GLOW_ADD = (1.08, 1.03, 1.0), (18.0, 5.0, 0.0)
BAYER = numpy.array(((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5)), dtype=numpy.float32) / 16

# Palette indices. The blues are the flasks' water.
DROP_INKS = (218, 217, 216, 215)
SWELL_INKS = (214, 216, 217)
SPLASH_INKS = (218, 216, 215, 214)
STEAM_INKS = (67, 219, 110)
FLASH_INKS = (199, 192)
DUST_PALE_INK = 67
DUST_WARM_INK = 208
DUST_SHINE_INK = 207
DUST_HOT_INK = 210
ASH_INKS = (192, 189, 186, 212, 211, 110)
ALL_INKS = frozenset((*DROP_INKS, *SWELL_INKS, *SPLASH_INKS, *STEAM_INKS, *FLASH_INKS, *ASH_INKS,
                      *(kind.ink for kind in DUST_KINDS), DUST_PALE_INK, DUST_WARM_INK, DUST_SHINE_INK,
                      DUST_HOT_INK))


class Colours:
    """The room's palette, and the tables that keep every result inside it."""

    def __init__(self, palette):
        rgb = sorted({tuple(colour[:3]) for colour in palette.values()})
        self.rgb = numpy.array(rgb, dtype=numpy.int32)
        self.keys = (self.rgb[:, 0] << 16) | (self.rgb[:, 1] << 8) | self.rgb[:, 2]
        # The flame and the lava are the light; they do not receive it. Nor do the
        # painted cracks: lifting them broke their thin lines into dots, and rock
        # must not turn into them.
        self.receives = (self.rgb[:, 0] < 240) & ~((self.rgb[:, 0] >= 100) & (self.rgb[:, 1] * 10 <= self.rgb[:, 0]))
        self.cube = self.nearest_cube().tobytes()
        self.firelight = self.light_table(AURA_GAIN, AURA_ADD)
        self.lavalight = self.light_table(POOL_GLOW_GAIN, POOL_GLOW_ADD)

    def closest(self, values, among=None):
        among = self.rgb if among is None else among
        distance = (((values[:, None, :] - among[None, :, :]) * (2, 3, 2)) ** 2).sum(axis=2)
        return distance.argmin(axis=1)

    def nearest_cube(self):
        """Nearest palette colour for every 5-bit red, green and blue."""
        levels = numpy.arange(32, dtype=numpy.int32) * 8 + 4
        green, blue = numpy.meshgrid(levels, levels, indexing='ij')
        planes = []
        for red in levels:
            values = numpy.stack((numpy.full(green.size, red), green.ravel(), blue.ravel()), axis=1)
            planes.append(self.rgb[self.closest(values)])
        return numpy.concatenate(planes).astype(numpy.uint8)

    def light_table(self, gain, add):
        """[level, colour] -> what that palette colour becomes at that light."""
        table = numpy.zeros((LIGHT_LEVELS + 1, len(self.rgb), 3), dtype=numpy.uint8)
        # Lit rock is still rock: however bright, it never turns into fire.
        rock = self.rgb[self.receives]
        for level in range(LIGHT_LEVELS + 1):
            amount = level / LIGHT_LEVELS
            lit = self.rgb * (1 + (numpy.array(gain) - 1) * amount) + numpy.array(add) * amount
            table[level] = rock[self.closest(lit.clip(0, 255).astype(numpy.int32), rock)]
        return table

    def nearest(self, red, green, blue):
        offset = ((red >> 3) << 10 | (green >> 3) << 5 | blue >> 3) * 3
        cube = self.cube
        return cube[offset], cube[offset + 1], cube[offset + 2], 255


@lru_cache(maxsize=4)
def colours_of(palette):
    return Colours(dict(palette))


@dataclass(frozen=True)
class Drip:
    x: int
    top: int
    bottom: int
    into_lava: bool


@dataclass(frozen=True)
class Glow:
    """A pool of light: how far it reaches over which rectangle of the room."""

    left: int
    top: int
    falloff: numpy.ndarray
    dither: numpy.ndarray
    table: numpy.ndarray

    @property
    def box(self):
        return self.left, self.top, self.left + self.falloff.shape[1], self.top + self.falloff.shape[0]


def glow_along(columns, reach, table):
    """A glow measured from a pool's surface, not from one point."""
    reach_x, reach_y = reach
    start, end = min(columns), max(columns)
    surface = sum(columns.values()) // len(columns)
    left, right = max(0, start - reach_x), min(WIDTH, end + reach_x)
    top, bottom = max(0, surface - reach_y), min(HEIGHT, surface + reach_y)
    rows, columns_at = numpy.mgrid[top:bottom, left:right]
    beyond = numpy.maximum(0, numpy.maximum(start - columns_at, columns_at - end))
    distance = numpy.hypot(beyond / reach_x, (rows - surface) / reach_y)
    falloff = (1 - distance).clip(0, 1).astype(numpy.float32) ** 1.4
    return Glow(left, top, falloff, BAYER[rows % 4, columns_at % 4], table)


@dataclass(frozen=True)
class TorchArt:
    """A torch's nine frames, read apart into the flame and its light."""

    left: int
    top: int
    frames: numpy.ndarray
    wall: numpy.ndarray
    flame: numpy.ndarray
    firelight: Firelight
    light: Glow
    lit_air: numpy.ndarray

    @property
    def box(self):
        return self.left, self.top, self.left + self.frames.shape[2], self.top + self.frames.shape[1]

    def air_light(self, x, y):
        """How lit the air is at a point of the room."""
        column, row = int(x) - self.light.left, int(y) - self.light.top
        height, width = self.lit_air.shape
        return float(self.lit_air[row, column]) if 0 <= row < height and 0 <= column < width else 0.0


def flame_pixels(frames):
    """[frame, y, x] of what is flame, leaving the painted wall out."""
    red, green, blue = (frames[..., channel].astype(numpy.int32) for channel in range(3))
    solid = frames[..., 3] > 0
    flame = solid & ((red >= FIRE_RED) | (blue > red))
    rim = solid & (red >= FLAME_RIM_RED) & (green == 0)
    for _ in range(FLAME_RIM):
        beside = numpy.zeros_like(flame)
        beside[:, 1:] |= flame[:, :-1]
        beside[:, :-1] |= flame[:, 1:]
        beside[:, :, 1:] |= flame[:, :, :-1]
        beside[:, :, :-1] |= flame[:, :, 1:]
        flame = flame | (beside & rim)
    return flame


def flame_heat(frames, flame):
    """How hot each pixel of flame burns: yellow most, the dark rim hardly."""
    hot = 0.5 + frames[..., 1].astype(numpy.float64) / 255
    return numpy.where(frames[..., 0] >= FIRE_RED, hot, 0.15) * flame


def steady_wall(frames, flame, unlit):
    """The painted wall with its blinking taken out. Each pixel keeps the colour
    it shows most often where no flame covers it. Behind the flame in every
    frame, there is only the unlit recess to go by."""
    wall = numpy.array(frames[0])
    codes = frames[..., 0].astype(numpy.int64) << 16 | frames[..., 1].astype(numpy.int64) << 8 | frames[..., 2]
    for row, column in numpy.argwhere((codes != codes[0]).any(axis=0) | flame.any(axis=0)):
        shows = codes[:, row, column][~flame[:, row, column]]
        if len(shows):
            colours, counts = numpy.unique(shows, return_counts=True)
            kept = int(colours[counts.argmax()])
            wall[row, column, :3] = kept >> 16, (kept >> 8) & 255, kept & 255
        else:
            wall[row, column] = unlit[row, column]
    return wall


def read_torch(frames, unlit, left, top, scenery, table, in_front=None):
    """frames: [frame, y, x, RGBA] of one size, all with the same outline, and
    unlit: the same recess with the torch out. scenery: the room's RGB pixels, and
    in_front: [y, x] of what the room draws in front of the torch."""
    flame = flame_pixels(frames)
    outline = frames[0, ..., 3] > 0
    bottom, right = min(HEIGHT, top + outline.shape[0]), min(WIDTH, left + outline.shape[1])
    room = scenery.copy()
    inside = outline[:bottom - top, :right - left]
    room[top:bottom, left:right][inside] = unlit[:bottom - top, :right - left, :3][inside]
    shades = (room @ numpy.array((0.30, 0.59, 0.11))) / 255
    firelight = trace_firelight(shades, outline.astype(numpy.float64), flame_heat(frames, flame), left, top)
    # The recess takes less of the light. The air before it does not.
    lit_air = gaussian(firelight.steady / firelight.taken, AIR_LIGHT_SPREAD).astype(numpy.float32)
    if in_front is not None:
        # Rock in front of a torch has its back to the flame. Lit, it stood out as a
        # pale plate on the pillars and the walls.
        height, width = firelight.rest.shape
        behind = ~in_front[firelight.top:firelight.top + height, firelight.left:firelight.left + width]
        firelight = replace(firelight, taken=firelight.taken * behind)
    at_rest = firelight.steady
    rows, columns = numpy.mgrid[firelight.top:firelight.top + at_rest.shape[0],
                                firelight.left:firelight.left + at_rest.shape[1]]
    glow = Glow(firelight.left, firelight.top, at_rest, BAYER[rows % 4, columns % 4], table)
    return TorchArt(left, top, frames, steady_wall(frames, flame, unlit), flame, firelight, glow, lit_air)


def torch_art(record, resources, palette, shapes, table, scenery, in_front):
    from pop2.caverns import clipped_sprite, decode_shap

    sprites = []
    for index in (*TORCH_FRAMES, UNLIT_TORCH):
        if index not in shapes:
            shapes[index] = decode_shap(resources['SHAP'][index]['data'], palette)
        clipped = clipped_sprite(shapes[index], record['command'])
        if clipped is None:
            return None
        sprites.append(clipped)
    frames = numpy.stack([numpy.array(sprite.convert('RGBA')) for sprite, _position in sprites])
    return read_torch(frames[:-1], frames[-1], *sprites[0][1], scenery, table, in_front)


@dataclass(frozen=True)
class Air:
    """What the effects need to know about one room."""

    open: bytes
    covered: bytes
    drips: tuple
    flames: tuple
    pools: tuple
    colours: Colours
    inks: dict
    centres: tuple = ()
    pool_glows: tuple = ()
    torches: tuple = ()

    def is_open(self, x, y):
        return 0 <= x < WIDTH and 0 <= y < HEIGHT and bool(self.open[y * WIDTH + x])

    def is_covered(self, x, y):
        return bool(self.covered[y * WIDTH + x])


def open_air(luminance, terrain, room):
    """Pixels of the dark back wall that are open space in the level map."""
    air = bytearray(luminance.point(lambda value: 255 if value < AIR_LUMINANCE else 0)
                    .filter(ImageFilter.MedianFilter(5)).tobytes())
    blank = bytes(TILE_WIDTH)
    for row in range(3):
        top = row * TILE_HEIGHT + 5
        for column in range(10):
            kind = terrain.tile(room, column, row).kind
            if kind in WALL_TILES:
                closed = range(top, top + TILE_HEIGHT)
            elif kind not in EMPTY_TILES:
                closed = range(floor_y(row) - FLOOR_STRIP, top + TILE_HEIGHT)
            else:
                continue
            start = column * TILE_WIDTH
            for y in closed:
                air[y * WIDTH + start:y * WIDTH + start + TILE_WIDTH] = blank
    return bytes(air)


def stalactite_tips(shades):
    """Ends of thin bright runs of rock, hanging over the dark back wall.

    Read from the raw art: the last pixels of a tip are one pixel wide."""
    def dark(x, y):
        return shades[y * WIDTH + x] < AIR_LUMINANCE

    found = []
    for x in range(TIP_WIDTH, WIDTH - TIP_WIDTH):
        for y in range(TIP_LENGTH, HEIGHT - TIP_CLEARANCE):
            if (shades[y * WIDTH + x] >= TIP_LUMINANCE and dark(x, y + 1)
                    and dark(x - TIP_WIDTH, y - 1) and dark(x + TIP_WIDTH, y - 1)
                    and dark(x - TIP_TAPER, y - TIP_LENGTH) and dark(x + TIP_TAPER, y - TIP_LENGTH)
                    and all(dark(x, below) for below in range(y + 1, y + TIP_CLEARANCE))):
                length = 0
                while length < y and not dark(x, y - length):
                    length += 1
                if length >= TIP_LENGTH:
                    found.append((x, y, length))
    # Neighbouring columns of one stalactite end at different heights: its
    # tip is the lowest of them.
    return [tip for tip in found if not any(
        abs(other[0] - tip[0]) <= TIP_WIDTH and abs(other[1] - tip[1]) <= 2 * TIP_LENGTH
        and other[1] > tip[1] for other in found)]


def landing(terrain, room, x, top):
    """The first floor below a point, or None above an open shaft."""
    for row in range(max(0, (top - 5) // TILE_HEIGHT), 3):
        if floor_y(row) > top and terrain.tile(room, x // TILE_WIDTH, row).kind not in EMPTY_TILES:
            return floor_y(row)
    return None


def surface_under(pools, x):
    for columns in pools:
        if x in columns:
            return columns[x]
    return None


def choose_drips(air, covered, shades, terrain, room, pools):
    """Fixed sources: the longest stalactites first, kept apart."""
    sources = []
    for x, top, length in stalactite_tips(shades):
        ground = landing(terrain, room, x, top)
        if ground is None or ground - top < SHORTEST_FALL:
            continue
        pool = surface_under(pools, x)
        path = range(top + 1, (pool or ground) - FLOOR_STRIP)
        # A drop that would have to pass through a ledge has no source here, and
        # one falling behind the foreground would only take the place of one seen.
        if sum(air[y * WIDTH + x] != 0 and not covered[y * WIDTH + x] for y in path) < len(path) * 0.7:
            continue
        bottom = pool or ground + LANDING_DEPTH[0] + x % (LANDING_DEPTH[1] - LANDING_DEPTH[0] + 1)
        sources.append((length, Drip(x, top, bottom, pool is not None)))
    sources.sort(key=lambda source: (-source[0], source[1].x))
    chosen = []
    for _length, drip in sources:
        if len(chosen) < MOST_DRIPS and all(abs(drip.x - other.x) >= DRIP_SPACING for other in chosen):
            chosen.append(drip)
    return tuple(sorted(chosen, key=lambda drip: drip.x))


def lava_surfaces(program, room, palette):
    """For each pool, {x: middle of the liquid} using the recessed artwork."""
    from pop2.caverns import recessed_lava_liquid_mask, recessed_lava_surface

    pools = []
    records = program.get('lava', {}).get('rooms', {}).get(str(room), ())
    if not records:
        return ()
    dx, dy = program['lava']['piece_offsets']
    liquid = recessed_lava_liquid_mask(recessed_lava_surface(palette))
    pixels = liquid.load()
    for record in records:
        left, top = record['x'] + dx, record['bottom'] + dy - liquid.height
        columns = {}
        for x in range(liquid.width):
            rows = [y for y in range(liquid.height) if pixels[x, y]]
            if rows:
                columns[left + x] = top + (rows[0] + rows[-1]) // 2
        # A room can list a pool that lies off the top of its screen.
        if min(columns.values()) >= 0:
            pools.append(columns)
    return tuple(pools)


def room_torches(program, room):
    """The room's torches, each once: many are listed twice."""
    return tuple({tuple(record['command'][6]): record for record in program.get('torches', {}).get(str(room), ())}.values())


def flame_of(record):
    top, left, bottom, right = record['command'][6]
    return (left + right) // 2, (top + bottom) // 2


def shows(torch, in_front):
    """Whether enough of a torch shows past the foreground."""
    outline = torch.frames[0, ..., 3] > 0
    height, width = outline.shape
    clear = ~in_front[torch.top:torch.top + height, torch.left:torch.left + width]
    return (outline[:clear.shape[0], :clear.shape[1]] & clear).sum() >= TORCH_SEEN * outline.sum()


def analyze_room(program, room, art, terrain, palette, resources=None, shapes=None):
    scenery = Image.alpha_composite(art.background, art.foreground)
    luminance = scenery.convert('L')
    air = open_air(luminance, terrain, room)
    covered = art.foreground.getchannel('A').point(lambda value: 255 if value else 0).tobytes()
    pools = lava_surfaces(program, room, palette)
    inks = {index: tuple(palette[index][:3]) + (255,) for index in ALL_INKS}
    drips = choose_drips(air, covered, luminance.tobytes(), terrain, room, pools)
    colours = colours_of(tuple(sorted(palette.items())))
    records = room_torches(program, room)
    centres = tuple(pool_centre(columns) for columns in pools)
    pool_glows = tuple(glow_along(columns, POOL_GLOW_REACH, colours.lavalight) for columns in pools)
    torches = ()
    if resources is not None:
        pixels = numpy.array(scenery.convert('RGB'))
        in_front = numpy.array(art.foreground.getchannel('A')) > 0
        arts = ((record, torch_art(record, resources, palette, shapes, colours.firelight, pixels, in_front))
                for record in records)
        seen = tuple((record, torch) for record, torch in arts if torch is not None and shows(torch, in_front))
        records, torches = tuple(record for record, _ in seen), tuple(torch for _, torch in seen)
    flames = tuple(flame_of(record) for record in records)
    return Air(air, covered, drips, flames, pools, colours, inks, centres, pool_glows, torches)


def pool_centre(columns):
    return sum(columns) / len(columns), sum(columns.values()) / len(columns)


def room_air(level_number, room, art, terrain):
    from pop2.caverns import room_assets

    program, resources, palette, shapes = room_assets(level_number, room)
    return analyze_room(program, room, art, terrain, palette, resources, shapes)


@dataclass
class Mote:
    x: float
    y: float
    dx: float
    dy: float
    phase: float
    life: float
    kind: DustKind
    spin: float = 0.2
    brightness: float = 0.0
    age: float = 0.0
    # Its speed now, which follows dx and dy and the air around it.
    moving_x: float = 0.0
    moving_y: float = 0.0
    # Falls from one to nothing once it is settling on the rock.
    settling: float = 1.0
    # How fast it sinks, and where it will lie on a floor, for how many ticks.
    sink: float = 0.0
    rest: float | None = None
    lying: float = 0.0


@dataclass
class Ash:
    x: float
    y: float
    drift: float
    rise: float
    phase: float
    life: float
    age: float = 0.0


@dataclass
class Fleck:
    """A splash droplet or a wisp of steam: a short ballistic pixel."""

    x: float
    y: float
    dx: float
    dy: float
    pull: float
    inks: tuple
    life: float
    floor: int
    age: int = 0


@dataclass
class Fall:
    source: Drip
    period: int
    wait: int
    swell: int = 0
    y: float | None = None
    speed: float = 0.0


@dataclass
class Flicker:
    """A torch's light as it stands: how far it reaches each way, how hot it burns,
    the step each pixel holds, and the tick they last moved on."""

    steps: numpy.ndarray
    quick: numpy.ndarray
    slow: numpy.ndarray
    burn: float = 1.0
    tick: int = -1

    def follow(self, outline, burn):
        self.quick = self.quick + (outline - self.quick) * QUICK_FOLLOW
        self.slow = self.slow + (outline - self.slow) * SLOW_FOLLOW
        self.burn += (burn ** FLICKER_DEPTH - self.burn) * FLICKER_FOLLOW

    @property
    def reach(self):
        return (1 + self.quick * QUICK_DEPTH + self.slow * SLOW_DEPTH).clip(SHORTEST_REACH, LONGEST_REACH)


def lifespan(kind, brightness):
    """How many ticks a grain of this brightness lasts: the brighter, the shorter."""
    return kind.life * (DUST_BRIGHT_LIFE / kind.life) ** (brightness ** DUST_LIFE_CURVE)


def mix(one, other, amount):
    return tuple(one[channel] + (other[channel] - one[channel]) * amount for channel in range(3))


def soft_spot(x, y, softness=DUST_SOFTNESS):
    """(column, row, weight) of a spot with one shape, wherever it falls between
    pixels. Split among the four nearest pixels, a slow grain swelled and shrank
    as it crossed each pixel, and looked like a worm going round a small square."""
    left, top = math.floor(x), math.floor(y)
    for row in range(top - 1, top + 3):
        for column in range(left - 1, left + 3):
            yield column, row, math.exp(-((column - x) ** 2 + (row - y) ** 2) / (2 * softness ** 2))


def smooth(amount):
    amount = min(1.0, max(0.0, amount))
    return amount * amount * (3 - 2 * amount)


def on_the_pixels(place, focus):
    """Where a grain shows. In focus it waits on a pixel and crosses quickly."""
    pixel = math.floor(place)
    return place + (pixel + smooth((place - pixel - 0.35) / 0.3) - place) * focus


def light_steps(light, dither, strength):
    """Which step of the light table each pixel takes, through the dither."""
    return numpy.minimum((light * strength * LIGHT_LEVELS + dither).astype(numpy.int32), LIGHT_LEVELS)


def wave(time, *terms):
    """A smooth irregular signal in -1..1: sines that never line up."""
    return sum(weight * math.sin(time * rate + phase) for weight, rate, phase in terms)


@dataclass
class CavernAmbience:
    room: int
    air: Air
    rng: random.Random = field(default_factory=random.Random)
    falls: list = field(default_factory=list)
    motes: list = field(default_factory=list)
    pockets: list = field(default_factory=list)
    ash: list = field(default_factory=list)
    flecks: list = field(default_factory=list)
    flickers: list = field(default_factory=list)
    tick: int = 0

    def __post_init__(self):
        self.falls = []
        for source in self.air.drips:
            period = self.rng.randint(*TICKS_BETWEEN_DROPS)
            self.falls.append(Fall(source, period, self.rng.randrange(period)))
        self.flickers = [self.new_flicker(torch) for torch in self.air.torches]
        self.pockets = self.find_pockets()
        for kind in DUST_KINDS if self.air.flames or self.air.pools else QUIET_DUST:
            for _ in range(kind.count):
                mote = self.new_mote(kind)
                if mote is not None:
                    # The room was already dusty before the Prince came in.
                    mote.age = self.rng.uniform(0, mote.life)
                    self.motes.append(mote)

    # Light

    @staticmethod
    def new_flicker(torch):
        still = numpy.zeros(DIRECTIONS)
        return Flicker(light_steps(torch.light.falloff, torch.light.dither, 1.0), still, still)

    def pool_strength(self):
        return 0.92 + 0.06 * wave(self.tick, (0.6, 0.07, 0.0), (0.4, 0.043, 1.0))

    def light_at(self, x, y):
        """(flame, pool): 0..1 of the light each kind of fire casts on a point.
        The flame's is traced, so the air behind a ledge stays dark."""
        flame = pool = 0.0
        for torch in self.air.torches:
            flame = max(flame, torch.air_light(x, y))
        for pool_x, pool_y in self.air.centres:
            reach = 1 - math.hypot((x - pool_x) / DUST_POOL_REACH[0], (y - pool_y + 10) / DUST_POOL_REACH[1])
            pool = max(pool, reach)
        return flame, pool * DUST_POOL_STRENGTH

    def wind_at(self, x, y):
        """Which way fire moves the air at a point, in pixels a tick, on top of
        the draught each grain rides."""
        wind_x, wind_y = 0.0, 0.0
        for columns in self.air.pools:
            surface = columns.get(int(x))
            if surface is not None and surface - DUST_POOL_REACH[1] < y < surface:
                wind_y -= POOL_DRAUGHT * (1 - (surface - y) / DUST_POOL_REACH[1])
        for flame_x, flame_y in self.air.flames:
            away_x, away_y = x - flame_x, y - flame_y
            distance = math.hypot(away_x, away_y)
            reach = 1 - distance / HEAT_REACH
            if reach > 0:
                inwards = -HEAT_SPREAD if away_y < -HEAT_PLUME else HEAT_PULL
                wind_x -= inwards * reach * away_x / max(distance, 1.0)
                wind_y -= HEAT_RISE * reach * reach
        return wind_x, wind_y

    # Dust

    def find_pockets(self):
        """The places of open air where dust gathers in this visit to the room."""
        rng, pockets = self.rng, []
        for _ in range(DUST_TRIES * DUST_POCKETS):
            x, y = rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT)
            if (self.air.is_open(int(x), int(y)) and len(pockets) < DUST_POCKETS
                    and all(math.hypot(x - other_x, y - other_y) > DUST_POCKETS_APART for other_x, other_y in pockets)):
                pockets.append((x, y))
        return pockets

    def clear_air(self, x, y, dx, dy):
        """Ticks of drifting from a point before reaching rock, up to the longest life."""
        for ticks in range(8, DUST_LONGEST_LIFE, 8):
            if not self.air.is_open(int(x + dx * ticks), int(y + dy * ticks)):
                return ticks
        return DUST_LONGEST_LIFE

    def place_for_dust(self, near):
        rng = self.rng
        if near < DUST_BY_FLAME and self.air.flames:
            flame_x, flame_y = rng.choice(self.air.flames)
            angle, distance = rng.uniform(0, math.tau), rng.uniform(*DUST_NEAR_FLAME)
            return flame_x + math.cos(angle) * distance, flame_y + math.sin(angle) * distance * 0.9
        if near < DUST_BY_FLAME + DUST_BY_POOL and self.air.pools:
            return rng.choice(tuple(rng.choice(self.air.pools))), rng.uniform(100, 215)
        if self.pockets:
            x, y = rng.choice(self.pockets)
            return rng.gauss(x, DUST_PATCH), rng.gauss(y, DUST_PATCH)
        return rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT)

    def new_mote(self, kind=FINE_DUST):
        """A new grain starts unseen, with room to drift through its whole life."""
        rng = self.rng
        near = rng.random()
        sink = rng.uniform(*DUST_SINK) if rng.random() < kind.sinkers else 0.0
        brightness = rng.random() ** DUST_SKEW * kind.brightest
        life = lifespan(kind, brightness) * rng.uniform(*DUST_LIFE_SPREAD)
        for attempt in range(DUST_TRIES):
            x, y = self.place_for_dust(near)
            # A grain that sinks tries first for a place above a floor.
            high_up = sink and attempt < DUST_TRIES / 2 and self.air.is_open(int(x), int(y) + DUST_DROP)
            if high_up or not self.air.is_open(int(x), int(y)):
                continue
            heading = rng.uniform(*DUST_HEADING)
            speed = rng.uniform(*kind.speed) * (DUST_SINKER_DRIFT if sink else 1.0)
            dx, dy = math.cos(heading) * speed, math.sin(heading) * speed
            clear = self.clear_air(x, y, dx, dy)
            if clear >= min(DUST_SHORTEST_LIFE, life):
                # A grain that sinks is not going where it is heading.
                return Mote(x, y, dx, dy, rng.uniform(0, math.tau), life if sink else min(clear, life), kind,
                            rng.uniform(*DUST_SPIN), brightness, moving_x=dx, moving_y=dy, sink=sink)
        return None

    def land(self, mote, terrain):
        """A sinking grain with a floor below it makes for the floor."""
        if terrain is None or not mote.sink or mote.moving_y <= 0:
            return False
        rng, x = self.rng, int(mote.x)
        ground = landing(terrain, self.room, x, int(mote.y))
        if ground is None or surface_under(self.air.pools, x) is not None:
            return False
        place = ground - rng.randint(*DUST_REST_DEPTH)
        if not 0 < place - mote.y < DUST_LANDING_REACH or self.air.is_covered(x, min(place, HEIGHT - 1)):
            return False
        mote.rest, mote.lying, mote.life = float(place), rng.uniform(*DUST_REST), math.inf
        return True

    def come_to_rest(self, mote, terrain):
        """Down to its place on the floor, then lying there; False once it has gone."""
        if mote.y < mote.rest:
            mote.moving_x *= DUST_BRAKE
            mote.x += mote.moving_x
            mote.y = min(mote.rest, mote.y + max(mote.moving_y, DUST_SINK[0]))
            return True
        mote.settling -= 1 / mote.lying
        # A floor that falls takes what lies on it.
        ground = None if terrain is None else landing(terrain, self.room, int(mote.x), int(mote.y))
        return mote.settling > 0 and (terrain is None or (ground is not None and ground - mote.y < DUST_LANDING_REACH))

    def advance_mote(self, mote, turning, terrain=None):
        """One tick of a grain riding the air; False once it has gone."""
        mote.age += 1
        if mote.rest is not None:
            return self.come_to_rest(mote, terrain)
        air = self.air
        if mote.settling < 1 or not air.is_open(int(mote.x + mote.moving_x * DUST_LOOK_AHEAD),
                                                int(mote.y + mote.moving_y * DUST_LOOK_AHEAD)):
            if mote.settling >= 1 and self.land(mote, terrain):
                return True
            mote.settling -= 1 / DUST_SETTLE
            mote.moving_x *= DUST_BRAKE
            mote.moving_y *= DUST_BRAKE
        else:
            wind_x, wind_y = self.wind_at(mote.x, mote.y)
            slow = mote.age * 0.031
            sway_x = DUST_SWAY * wave(slow, (0.7, 1.0, mote.phase), (0.3, 2.7, mote.phase * 2))
            sway_y = DUST_SWAY * wave(slow, (0.7, 0.8, mote.phase * 3), (0.3, 2.1, mote.phase * 5))
            along_x = mote.dx * math.cos(turning) - mote.dy * math.sin(turning)
            along_y = mote.dx * math.sin(turning) + mote.dy * math.cos(turning)
            follows = mote.kind.follows
            mote.moving_x += (along_x + wind_x + sway_x - mote.moving_x) * follows
            mote.moving_y += (along_y + wind_y + sway_y + mote.sink - mote.moving_y) * follows
        mote.x += mote.moving_x
        mote.y += mote.moving_y
        return mote.age < mote.life and mote.settling > 0 and air.is_open(int(mote.x), int(mote.y))

    def advance_dust(self, terrain=None):
        turning = DRAUGHT_TURN * wave(self.tick, (0.6, 0.0037, 0.0), (0.4, 0.0021, 2.0))
        motes = []
        for mote in self.motes:
            if not self.advance_mote(mote, turning, terrain):
                mote = self.new_mote(mote.kind)
                if mote is None:
                    continue
            motes.append(mote)
        self.motes = motes

    def dust_colour(self, mote):
        """(red, green, blue, strength) of a mote where it is now."""
        kind = mote.kind
        flame, pool = self.light_at(mote.x, mote.y)
        light = max(flame, pool)
        span = lifespan(kind, mote.brightness)
        fade = smooth(min(1.0, mote.age / (span * DUST_FADE_IN), (mote.life - mote.age) / (span * DUST_FADE_OUT),
                          mote.settling))
        inks = self.air.inks
        # The floor is brighter than the air, and only a warm pale speck shows on it.
        if mote.rest is not None:
            return (*inks[DUST_SHINE_INK][:3], DUST_LYING * fade)
        # Two rhythms, so that no grain flashes like a beacon.
        turn = mote.phase + mote.age * mote.spin
        glint = max(0.0, math.sin(turn)) ** 12 * max(0.0, math.sin(turn * 0.37 + mote.phase))
        dark = mix(inks[kind.ink], inks[DUST_PALE_INK], mote.brightness)
        lit = mix(dark, inks[DUST_WARM_INK if flame >= pool else DUST_HOT_INK], min(1.0, light / DUST_FOCUS_LIGHT))
        shown = mix(lit, inks[DUST_SHINE_INK], min(1.0, DUST_FLASH * glint * light))
        return (*shown, min(1.0, kind.strength + light * DUST_LIT + DUST_GLINT * glint * light) * fade)

    # Ash

    def new_ash(self, x, y, life):
        rng = self.rng
        return Ash(x, y, rng.uniform(-0.08, 0.08), rng.uniform(0.45, 0.8), rng.uniform(0, math.tau),
                   rng.uniform(*life))

    def advance_ash(self):
        rng = self.rng
        for columns in self.air.pools:
            if len(self.ash) < MOST_ASH and rng.random() < ASH_PER_TICK:
                x = rng.choice(tuple(columns))
                self.ash.append(self.new_ash(float(x), columns[x] - 2.0, ASH_LIFE))
        for flame_x, flame_y in self.air.flames:
            if len(self.ash) < MOST_ASH and rng.random() < EMBER_PER_TICK:
                self.ash.append(self.new_ash(flame_x + rng.uniform(-3, 3), flame_y - rng.uniform(6, 14),
                                             EMBER_LIFE))
        breeze = math.sin(self.tick * 0.011) * 0.07
        ash = []
        for grain in self.ash:
            grain.age += 1
            if grain.age < grain.life:
                # Ash flutters in the hot air.
                grain.x += grain.drift + breeze + 0.3 * math.sin(grain.phase + grain.age * 0.13)
                grain.y += math.cos(grain.phase * 1.7 + grain.age * 0.031) * 0.035 - grain.rise
                ash.append(grain)
        self.ash = ash

    # Water

    def advance_fall(self, fall, terrain):
        source = fall.source
        if fall.y is None:
            if fall.wait > 0:
                fall.wait -= 1
                return
            fall.swell += 1
            if fall.swell >= SWELL_TICKS:
                fall.swell, fall.y, fall.speed = 0, float(source.top + 2), 0.0
            return
        fall.speed = min(FASTEST_FALL, fall.speed + GRAVITY)
        fall.y += fall.speed
        bottom = self.fall_bottom(source, terrain)
        if fall.y < bottom:
            return
        fall.y = None
        fall.wait = fall.period + self.rng.randint(-DROP_RHYTHM_JITTER, DROP_RHYTHM_JITTER)
        if bottom < HEIGHT:
            (self.hiss if source.into_lava else self.splash)(source.x, bottom)

    def fall_bottom(self, source, terrain):
        # A floor that has fallen since the room was entered no longer stops
        # the drop, so ask the live map at the end of each fall.
        if terrain is None or source.into_lava:
            return source.bottom
        ground = landing(terrain, self.room, source.x, source.top)
        if ground is None:
            return HEIGHT
        return source.bottom if ground - source.bottom < 8 else ground

    def splash(self, x, y):
        rng = self.rng
        for side in (-1, 1):
            self.flecks.append(Fleck(x, y - 1, side * rng.uniform(0.5, 1.1), -rng.uniform(1.3, 2.1), 0.55,
                                     SPLASH_INKS, 8, y))
        if rng.random() < 0.5:
            self.flecks.append(Fleck(x, y - 1, rng.uniform(-0.3, 0.3), -rng.uniform(2.0, 2.6), 0.55,
                                     SPLASH_INKS, 8, y))

    def hiss(self, x, y):
        rng = self.rng
        self.flecks.append(Fleck(x, y, 0.0, 0.0, 0.0, FLASH_INKS, 3, y))
        for _ in range(3):
            self.flecks.append(Fleck(x + rng.randint(-1, 1), y - 2, rng.uniform(-0.15, 0.15),
                                     -rng.uniform(0.5, 0.9), -0.01, STEAM_INKS,
                                     rng.randint(9, 15), y))

    def advance_flecks(self):
        flecks = []
        for fleck in self.flecks:
            fleck.age += 1
            fleck.x += fleck.dx
            fleck.y += fleck.dy
            fleck.dy += fleck.pull
            if fleck.age < fleck.life and fleck.y <= fleck.floor:
                flecks.append(fleck)
        self.flecks = flecks

    def advance(self, terrain=None):
        """One game tick."""
        self.tick += 1
        for fall in self.falls:
            self.advance_fall(fall, terrain)
        self.advance_dust(terrain)
        self.advance_ash()
        self.advance_flecks()

    # Drawing

    def crisp_pixels(self):
        """(x, y, palette index) of the drops and the ash, which stay opaque."""
        for grain in self.ash:
            yield (int(grain.x), int(grain.y),
                   ASH_INKS[min(len(ASH_INKS) - 1, int(grain.age * len(ASH_INKS) / grain.life))])
        for fall in self.falls:
            yield from self.fall_pixels(fall)
        for fleck in self.flecks:
            yield (int(fleck.x), int(fleck.y),
                   fleck.inks[min(len(fleck.inks) - 1, fleck.age * len(fleck.inks) // fleck.life)])

    def fall_pixels(self, fall):
        source = fall.source
        if fall.y is None:
            if fall.swell:
                stage = fall.swell * len(SWELL_INKS) // SWELL_TICKS
                yield source.x, source.top + 1, SWELL_INKS[stage]
                if stage == len(SWELL_INKS) - 1:
                    yield source.x, source.top + 2, SWELL_INKS[0]
            return
        length = min(len(DROP_INKS), 1 + int(fall.speed / 4))
        for offset in range(length):
            yield source.x, int(fall.y) - offset, DROP_INKS[offset]

    def shed_light(self, frame, glow, level):
        """Step each lit pixel to what its palette colour becomes at that light."""
        colours = self.air.colours
        pixels = numpy.array(frame.crop(glow.box))
        keys = (pixels[..., 0].astype(numpy.int32) << 16 | pixels[..., 1].astype(numpy.int32) << 8
                | pixels[..., 2])
        known = numpy.searchsorted(colours.keys, keys).clip(0, len(colours.keys) - 1)
        lit = (level > 0) & (colours.keys[known] == keys) & colours.receives[known]
        pixels[..., :3][lit] = glow.table[level[lit], known[lit]]
        frame.paste(Image.fromarray(pixels), glow.box[:2])

    def light_torch(self, frame, torch, flicker):
        """Put the unlit wall behind the flame the game drew, and light the rock
        by that flame."""
        shown = numpy.array(frame.crop(torch.box))
        same = (torch.frames == shown).all(axis=3)
        game_frame = int(same.sum(axis=(1, 2)).argmax())
        drawn = same[game_frame]
        if drawn.sum() < TORCH_SEEN * (torch.frames[0, ..., 3] > 0).sum():
            return
        # A frame can be rendered twice: the light moves once per tick.
        if flicker.tick != self.tick:
            flicker.tick = self.tick
            flicker.follow(torch.firelight.outlines[game_frame], float(torch.firelight.burn[game_frame]))
            light = torch.firelight.at(flicker.reach, flicker.burn)
            wanted = light * LIGHT_LEVELS + torch.light.dither
            moved = numpy.abs(wanted - 0.5 - flicker.steps) > 0.5 + LIGHT_HOLD
            flicker.steps = numpy.where(moved, light_steps(light, torch.light.dither, 1.0), flicker.steps)
        wall = drawn & ~torch.flame[game_frame]
        shown[wall] = torch.wall[wall]
        frame.paste(Image.fromarray(shown), torch.box[:2])
        self.shed_light(frame, torch.light, flicker.steps)

    def dust_spot(self, canvas, mote):
        red, green, blue, strength = self.dust_colour(mote)
        resting = mote.rest is not None
        kind = mote.kind
        sharp = resting or kind.softness <= DUST_SHARPNESS
        focus = 1.0 if sharp else smooth(max(self.light_at(mote.x, mote.y)) / DUST_FOCUS_LIGHT)
        softness = kind.softness + (DUST_SHARPNESS - kind.softness) * focus
        air, nearest = self.air, self.air.colours.nearest
        for column, row, weight in soft_spot(on_the_pixels(mote.x, focus), on_the_pixels(mote.y, focus), softness):
            amount = weight * strength
            inside = 0 <= column < WIDTH and 0 <= row < HEIGHT if resting else air.is_open(column, row)
            if amount < 0.04 or not inside or air.is_covered(column, row):
                continue
            under = canvas[column, row]
            canvas[column, row] = nearest(int(under[0] + (red - under[0]) * amount),
                                          int(under[1] + (green - under[1]) * amount),
                                          int(under[2] + (blue - under[2]) * amount))

    def draw(self, frame):
        air, inks = self.air, self.air.inks
        for torch, flicker in zip(air.torches, self.flickers):
            self.light_torch(frame, torch, flicker)
        for glow in air.pool_glows:
            self.shed_light(frame, glow, light_steps(glow.falloff, glow.dither, self.pool_strength()))
        canvas = frame.load()
        for mote in self.motes:
            self.dust_spot(canvas, mote)
        for x, y, ink in self.crisp_pixels():
            if 0 <= x < WIDTH and 0 <= y < HEIGHT and not air.is_covered(x, y):
                canvas[x, y] = inks[ink]
        return frame
