"""Optional dust, ash, water drops and a calmer torch for cavern rooms.

A port improvement. Nothing here comes from the original game, and nothing
here touches it: the effect is drawn on the frame, behind the actors, while the
"Cave ambience" menu item is on. It reads the room and never writes game state.
Its random numbers come from a private generator, so turning it on cannot
change an opponent, a route or a test.

The look is held to the 1993 art by two rules. Every pixel it leaves on the
frame is a colour of the room's own palette, and everything moves once per game
tick like the rest of the game: motion any smoother stood out against it. Soft
things are done the way a 256-colour game did them. A mote between two pixels
shares itself among the four around it, each blend landing on the nearest
palette colour, and the faint warmth at a torch and around the lava is a table
of what each palette colour becomes at each brightness, stepped through an
ordered dither.

It is meant to be barely noticed, and it is tied to the scenery. Drops hang
from the tips of the stalactites and end on the floor or in the lava, single
grains of ash rise from the lava and the flame, and dust drifts through the
open air. The flame stays exactly the game's, while the light it paints on the
wall eases instead of blinking. The user rejected a wider firelight and sparks
with trails as far too much: a change here should be small.
"""

from dataclasses import dataclass, field
from functools import lru_cache
import math
import random

import numpy
from PIL import Image, ImageFilter

from pop2.opponent_generation import EMPTY_TILES, WALL_TILES
from pop2.terrain import TILE_HEIGHT, TILE_WIDTH, floor_y

WIDTH, HEIGHT = 510, 365

# One room for the approved prototype: level four, room 17 of the development
# menu (the torch, the lava pool and the long stalactites are all in view).
AMBIENCE_ROOMS = frozenset({(4, 16)})

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

MOST_DUST = 30
# A grain lives this long, and is seen coming and going: all times are ticks.
DUST_LIFE = (220, 480)
DUST_FADE_IN = 48
DUST_FADE_OUT = 84
# A new grain needs this much clear air ahead, or it could only flash by.
DUST_SHORTEST_LIFE = 140
# Of this many places for a new grain, it takes the one furthest from the rest.
DUST_PLACES = 5
DUST_TRIES = 24
# Pixels a tick, and radians around rightwards: one slow draught crosses the
# room. With every heading of its own it looked like insects.
DUST_SPEED = (0.13, 0.24)
DUST_HEADING = (-0.6, 0.25)
DUST_BY_FLAME = 0.35
DUST_BY_POOL = 0.1
# A little of it can be seen in the dark as well, and never much by the flame.
DUST_DARK = 0.65
DUST_BRIGHTEST = 0.75
TORCH_DRAUGHT = 0.1
POOL_DRAUGHT = 0.12
DUST_TORCH_REACH = 84
DUST_POOL_REACH = (84, 62)
# Dust over the lava is a dull glow, so that it is not read as more ash.
DUST_POOL_STRENGTH = 0.6

ASH_LIFE = (34, 76)
MOST_ASH = 5
ASH_PER_TICK = 0.036
EMBER_PER_TICK = 0.03
EMBER_LIFE = (18, 34)

# The nine lit frames of every cavern torch (CaveGetTorchFrame 8:3b4e picks one
# at random each tick). Their wall has two lightings, painted on about a hundred
# pixels, and the random order blinks between the two. The flame's frame is left
# as the game drew it, and the wall eases to that frame's lighting by dither.
TORCH_FRAMES = range(3581, 3590)
FIRE_RED = 200
WALL_EASE = 0.2
# Share of a torch that must be on screen for it to be there at all.
TORCH_SEEN = 0.5

# Only the torch's own recess, and it moves like a candle: a wider light with a
# real pulse looked like a bomb about to go off.
LIGHT_LEVELS = 8
RECESS_REACH = (30, 44)
RECESS_GAIN, RECESS_ADD = (1.15, 1.08, 1.0), (26.0, 13.0, 2.0)
CANDLE = (0.78, 0.2)
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
DUST_DARK_INK = 85
DUST_WARM_INK = 207
DUST_HOT_INK = 210
ASH_INKS = (192, 189, 186, 212, 211, 110)
ALL_INKS = frozenset((*DROP_INKS, *SWELL_INKS, *SPLASH_INKS, *STEAM_INKS, *FLASH_INKS, *ASH_INKS,
                      DUST_DARK_INK, DUST_WARM_INK, DUST_HOT_INK))


class Colours:
    """The room's palette, and the tables that keep every result inside it."""

    def __init__(self, palette):
        rgb = sorted({tuple(colour[:3]) for colour in palette.values()})
        self.rgb = numpy.array(rgb, dtype=numpy.int32)
        self.keys = (self.rgb[:, 0] << 16) | (self.rgb[:, 1] << 8) | self.rgb[:, 2]
        # The flame and the lava are the light; they do not receive it.
        self.receives = self.rgb[:, 0] < 240
        self.cube = self.nearest_cube().tobytes()
        self.firelight = self.light_table(RECESS_GAIN, RECESS_ADD)
        self.lavalight = self.light_table(POOL_GLOW_GAIN, POOL_GLOW_ADD)

    def closest(self, values):
        distance = (((values[:, None, :] - self.rgb[None, :, :]) * (2, 3, 2)) ** 2).sum(axis=2)
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
        for level in range(LIGHT_LEVELS + 1):
            amount = level / LIGHT_LEVELS
            lit = self.rgb * (1 + (numpy.array(gain) - 1) * amount) + numpy.array(add) * amount
            table[level] = self.rgb[self.closest(lit.clip(0, 255).astype(numpy.int32))]
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


def glow_around(x, y, reach, table):
    reach_x, reach_y = reach
    left, right = max(0, x - reach_x), min(WIDTH, x + reach_x)
    top, bottom = max(0, y - reach_y), min(HEIGHT, y + reach_y)
    rows, columns = numpy.mgrid[top:bottom, left:right]
    distance = numpy.hypot((columns - x) / reach_x, (rows - y) / reach_y)
    falloff = (1 - distance).clip(0, 1).astype(numpy.float32) ** 1.4
    return Glow(left, top, falloff, BAYER[rows % 4, columns % 4], table)


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
    """A torch's nine frames, read apart into the flame and the wall it lights."""

    left: int
    top: int
    frames: numpy.ndarray
    lighting: tuple
    wall: numpy.ndarray
    unlit_wall: numpy.ndarray
    lit_wall: numpy.ndarray
    order: numpy.ndarray

    @property
    def box(self):
        return self.left, self.top, self.left + self.frames.shape[2], self.top + self.frames.shape[1]


def read_torch(frames, left, top):
    """frames: [frame, y, x, RGBA] of one size, all with the same outline."""
    fire = frames[..., 0] >= FIRE_RED
    plain_wall = ~fire.any(axis=0) & (frames[0, ..., 3] > 0)
    every_frame = range(len(frames))

    def wall_change(first, second):
        return (frames[first] != frames[second]).any(axis=2) & plain_wall

    # The two lightings: the first frame's, and the one furthest from it.
    other = max(every_frame, key=lambda index: wall_change(0, index).sum())
    lighting = tuple(int(wall_change(index, other).sum() < wall_change(index, 0).sum())
                     for index in every_frame)
    wall = wall_change(0, other)
    rows, columns = numpy.nonzero(wall)
    order = BAYER[(rows + top) % 4, (columns + left) % 4]
    return TorchArt(left, top, frames, lighting, wall, frames[0][wall], frames[other][wall], order)


def torch_art(record, resources, palette, shapes):
    from pop2.caverns import clipped_sprite, decode_shap

    sprites = []
    for index in TORCH_FRAMES:
        if index not in shapes:
            shapes[index] = decode_shap(resources['SHAP'][index]['data'], palette)
        clipped = clipped_sprite(shapes[index], record['command'])
        if clipped is None:
            return None
        sprites.append(clipped)
    frames = numpy.stack([numpy.array(sprite.convert('RGBA')) for sprite, _position in sprites])
    return read_torch(frames, *sprites[0][1])


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
    glows: tuple = ()
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


def choose_drips(air, shades, terrain, room, pools):
    """Fixed sources: the longest stalactites first, kept apart."""
    sources = []
    for x, top, length in stalactite_tips(shades):
        ground = landing(terrain, room, x, top)
        if ground is None or ground - top < SHORTEST_FALL:
            continue
        pool = surface_under(pools, x)
        path = range(top + 1, (pool or ground) - FLOOR_STRIP)
        # A drop that would have to pass through a ledge has no source here.
        if sum(air[y * WIDTH + x] != 0 for y in path) < len(path) * 0.7:
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
        pools.append(columns)
    return tuple(pools)


def torch_flames(program, room):
    flames = []
    for record in program.get('torches', {}).get(str(room), ()):
        top, left, bottom, right = record['command'][6]
        flames.append(((left + right) // 2, (top + bottom) // 2))
    return tuple(flames)


def analyze_room(program, room, art, terrain, palette, resources=None, shapes=None):
    luminance = Image.alpha_composite(art.background, art.foreground).convert('L')
    air = open_air(luminance, terrain, room)
    covered = art.foreground.getchannel('A').point(lambda value: 255 if value else 0).tobytes()
    pools = lava_surfaces(program, room, palette)
    inks = {index: tuple(palette[index][:3]) + (255,) for index in ALL_INKS}
    drips = choose_drips(air, luminance.tobytes(), terrain, room, pools)
    colours = colours_of(tuple(sorted(palette.items())))
    flames = torch_flames(program, room)
    centres = tuple(pool_centre(columns) for columns in pools)
    glows = tuple(glow_around(x, y, RECESS_REACH, colours.firelight) for x, y in flames)
    pool_glows = tuple(glow_along(columns, POOL_GLOW_REACH, colours.lavalight) for columns in pools)
    torches = ()
    if resources is not None:
        records = program.get('torches', {}).get(str(room), ())
        torches = tuple(filter(None, (torch_art(record, resources, palette, shapes) for record in records)))
    return Air(air, covered, drips, flames, pools, colours, inks, glows, centres, pool_glows, torches)


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
    size: float
    age: float = 0.0


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
    """How far a torch's wall is towards its other lighting, and which lighting
    the frame on screen asks for."""

    light: float = 0.5
    wanted: int = 0


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
    ash: list = field(default_factory=list)
    flecks: list = field(default_factory=list)
    flickers: list = field(default_factory=list)
    tick: int = 0

    def __post_init__(self):
        self.falls = []
        for source in self.air.drips:
            period = self.rng.randint(*TICKS_BETWEEN_DROPS)
            self.falls.append(Fall(source, period, self.rng.randrange(period)))
        self.flickers = [Flicker() for _torch in self.air.torches]
        if self.air.flames or self.air.pools:
            for _ in range(MOST_DUST):
                mote = self.new_mote()
                if mote is not None:
                    # The room was already dusty before the Prince came in.
                    mote.age = self.rng.uniform(0, mote.life)
                    self.motes.append(mote)

    # Light

    def flame_strength(self):
        # A candle: it swells and dips a little, irregularly, and never beats.
        middle, swing = CANDLE
        return middle + swing * wave(self.tick, (0.55, 0.23, 0.0), (0.3, 0.57, 1.3), (0.15, 1.13, 2.1))

    def pool_strength(self):
        return 0.92 + 0.06 * wave(self.tick, (0.6, 0.07, 0.0), (0.4, 0.043, 1.0))

    def light_at(self, x, y):
        """(flame, pool): 0..1 of the light each kind of fire casts on a point."""
        flame = pool = 0.0
        for flame_x, flame_y in self.air.flames:
            flame = max(flame, 1 - math.hypot(x - flame_x, y - flame_y) / DUST_TORCH_REACH)
        for pool_x, pool_y in self.air.centres:
            reach = 1 - math.hypot((x - pool_x) / DUST_POOL_REACH[0], (y - pool_y + 10) / DUST_POOL_REACH[1])
            pool = max(pool, reach)
        return flame * self.flame_strength(), pool * DUST_POOL_STRENGTH

    def draught(self, x, y):
        """The upward pull of the hot air over a pool or around a flame."""
        strongest = 0.0
        for columns in self.air.pools:
            surface = columns.get(int(x))
            if surface is not None and surface - DUST_POOL_REACH[1] < y < surface:
                strongest = max(strongest, POOL_DRAUGHT * (1 - (surface - y) / DUST_POOL_REACH[1]))
        for flame_x, flame_y in self.air.flames:
            reach = 1 - math.hypot(x - flame_x, y - flame_y) / DUST_TORCH_REACH
            strongest = max(strongest, TORCH_DRAUGHT * reach)
        return strongest

    # Dust

    def clear_air(self, x, y, dx, dy):
        """Ticks of drifting from a point before reaching rock, up to the longest life."""
        for ticks in range(8, DUST_LIFE[1], 8):
            if not self.air.is_open(int(x + dx * ticks), int(y + dy * ticks)):
                return ticks
        return DUST_LIFE[1]

    def place_for_dust(self, near):
        rng = self.rng
        if near < DUST_BY_FLAME and self.air.flames:
            flame_x, flame_y = rng.choice(self.air.flames)
            angle, distance = rng.uniform(0, math.tau), rng.uniform(14, 110)
            return flame_x + math.cos(angle) * distance, flame_y + math.sin(angle) * distance * 0.9
        if near < DUST_BY_FLAME + DUST_BY_POOL and self.air.pools:
            return rng.choice(tuple(rng.choice(self.air.pools))), rng.uniform(100, 215)
        return rng.uniform(0, WIDTH), rng.uniform(0, HEIGHT)

    def new_mote(self):
        """A new grain starts unseen where the dust is thinnest, with room to
        drift through its whole life, so that old and new never show as a swap."""
        rng = self.rng
        near = rng.random()
        best, room, found = None, -1.0, 0
        for _ in range(DUST_TRIES):
            x, y = self.place_for_dust(near)
            if not self.air.is_open(int(x), int(y)):
                continue
            heading, speed = rng.uniform(*DUST_HEADING), rng.uniform(*DUST_SPEED)
            dx, dy = math.cos(heading) * speed, math.sin(heading) * speed
            clear = self.clear_air(x, y, dx, dy)
            if clear < DUST_SHORTEST_LIFE:
                continue
            found += 1
            apart = min((math.hypot(x - mote.x, y - mote.y) for mote in self.motes), default=WIDTH)
            if apart > room:
                room = apart
                best = Mote(x, y, dx, dy, rng.uniform(0, math.tau), min(clear, rng.uniform(*DUST_LIFE)),
                            rng.uniform(0.6, 1.0))
            if found == DUST_PLACES:
                break
        return best

    def advance_dust(self):
        breeze = math.sin(self.tick * 0.009) * 0.05
        motes = []
        for mote in self.motes:
            mote.age += 1
            mote.x += mote.dx + breeze
            mote.y += mote.dy + 0.04 * math.sin(mote.phase + mote.age * 0.05) - self.draught(mote.x, mote.y)
            if mote.age >= mote.life or not self.air.is_open(int(mote.x), int(mote.y)):
                mote = self.new_mote()
                if mote is None:
                    continue
            motes.append(mote)
        self.motes = motes

    def dust_colour(self, mote):
        """(red, green, blue, strength) of a mote where it is now."""
        flame, pool = self.light_at(mote.x, mote.y)
        fade = min(1.0, mote.age / DUST_FADE_IN, (mote.life - mote.age) / DUST_FADE_OUT)
        strength = mote.size * fade * fade * (3 - 2 * fade) * min(DUST_BRIGHTEST, DUST_DARK + max(flame, pool))
        inks = self.air.inks
        ink = DUST_DARK_INK if max(flame, pool) <= 0 else (DUST_WARM_INK if flame >= pool else DUST_HOT_INK)
        return (*inks[ink][:3], strength)

    # The torch

    def advance_torches(self):
        for flicker in self.flickers:
            flicker.light += max(-WALL_EASE, min(WALL_EASE, flicker.wanted - flicker.light))

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
        self.advance_dust()
        self.advance_ash()
        self.advance_flecks()
        self.advance_torches()

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

    def shed_light(self, frame, glow, strength):
        """Step each lit pixel to what its palette colour becomes at that light."""
        colours = self.air.colours
        pixels = numpy.array(frame.crop(glow.box))
        keys = (pixels[..., 0].astype(numpy.int32) << 16 | pixels[..., 1].astype(numpy.int32) << 8
                | pixels[..., 2])
        known = numpy.searchsorted(colours.keys, keys).clip(0, len(colours.keys) - 1)
        level = numpy.minimum((glow.falloff * strength * LIGHT_LEVELS + glow.dither).astype(numpy.int32),
                              LIGHT_LEVELS)
        lit = (level > 0) & (colours.keys[known] == keys) & colours.receives[known]
        pixels[..., :3][lit] = glow.table[level[lit], known[lit]]
        frame.paste(Image.fromarray(pixels), glow.box[:2])

    def calm_torch(self, frame, torch, flicker):
        """Ease the wall behind the frame of the torch that the game drew."""
        shown = numpy.array(frame.crop(torch.box))
        same = (torch.frames == shown).all(axis=3)
        game_frame = int(same.sum(axis=(1, 2)).argmax())
        drawn = same[game_frame]
        if drawn.sum() < TORCH_SEEN * (torch.frames[0, ..., 3] > 0).sum():
            return
        flicker.wanted = torch.lighting[game_frame]
        eased = shown.copy()
        eased[torch.wall] = numpy.where((torch.order < flicker.light)[:, None], torch.lit_wall, torch.unlit_wall)
        shown[drawn] = eased[drawn]
        frame.paste(Image.fromarray(shown), torch.box[:2])

    def share(self, canvas, mote):
        """A soft point: split a mote among the four pixels around it, and let
        each blend land on the nearest palette colour."""
        red, green, blue, strength = self.dust_colour(mote)
        air, nearest = self.air, self.air.colours.nearest
        left, top = math.floor(mote.x), math.floor(mote.y)
        right_share, lower_share = mote.x - left, mote.y - top
        for column, row, part in ((left, top, (1 - right_share) * (1 - lower_share)),
                                  (left + 1, top, right_share * (1 - lower_share)),
                                  (left, top + 1, (1 - right_share) * lower_share),
                                  (left + 1, top + 1, right_share * lower_share)):
            amount = part * strength
            if amount < 0.04 or not air.is_open(column, row) or air.is_covered(column, row):
                continue
            under = canvas[column, row]
            canvas[column, row] = nearest(int(under[0] + (red - under[0]) * amount),
                                          int(under[1] + (green - under[1]) * amount),
                                          int(under[2] + (blue - under[2]) * amount))

    def draw(self, frame):
        air, inks = self.air, self.air.inks
        for torch, flicker in zip(air.torches, self.flickers):
            self.calm_torch(frame, torch, flicker)
        for glow in air.glows:
            self.shed_light(frame, glow, self.flame_strength())
        for glow in air.pool_glows:
            self.shed_light(frame, glow, self.pool_strength())
        canvas = frame.load()
        for mote in self.motes:
            self.share(canvas, mote)
        for x, y, ink in self.crisp_pixels():
            if 0 <= x < WIDTH and 0 <= y < HEIGHT and not air.is_covered(x, y):
                canvas[x, y] = inks[ink]
        return frame
