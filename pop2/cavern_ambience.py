"""Optional dust and water drops for cavern rooms: a port improvement.

Nothing here comes from the original game, and nothing here touches it: the
effect is pixels drawn on the frame, behind the actors, while the "Cave
ambience" menu item is on. It reads the room and never writes game state. Its
random numbers come from a private generator, so turning it on cannot change
an opponent, a route or a test.

The look is held to the 1993 art. Every particle is one or two opaque pixels
in a colour of the room's own palette, with no glow, blur or transparency.
Light is shown by stepping along a palette ramp. Particles are tied to the
scenery: drops fall from the tips of the stalactites and end on the floor or
in the lava, ash rises from the lava, and dust is dark until it crosses the
light of a torch.
"""

from dataclasses import dataclass, field
import math
import random

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

# A stalactite drips to its own steady rhythm.
TICKS_BETWEEN_DROPS = (90, 230)
DROP_RHYTHM_JITTER = 14
SWELL_TICKS = 18
GRAVITY = 1.15
FASTEST_FALL = 15.0

DUST_PER_AIR_PIXELS = 5200
MOST_DUST = 14
DUST_LIFE = (240, 620)
# Share of the dust that starts near a torch, where it can be seen, and of the
# dust that is a two-pixel fleck rather than a single grain.
DUST_BY_TORCH = 0.35
DUST_FLECKS = 0.3
TORCH_DRAUGHT = 0.16
HEAT_DRAUGHT = 0.3
GLINT_CHANCE = 0.03
ASH_LIFE = (34, 76)
MOST_ASH = 3
ASH_CHANCE = 0.022
HEAT_HEIGHT = 92
TORCH_REACH = 74
LAVA_REACH = 62

# Palette indices. The blues are the flasks' water.
DROP_INKS = (218, 217, 216, 215)
SWELL_INKS = (214, 216, 217)
SPLASH_INKS = (218, 216, 215, 214)
STEAM_INKS = (67, 219, 110)
FLASH_INKS = (199, 192)
# The first entries are how a mote arrives and leaves; it rests on the others.
DUST_INKS = (127, 110, 105, 96)
DUST_REST = (1, 2, 3)
TORCH_INKS = (210, 209, 208, 207)
LAVA_INKS = (211, 210, 188)
ASH_INKS = (192, 189, 186, 212, 211, 110)
ALL_INKS = frozenset((*DROP_INKS, *SWELL_INKS, *SPLASH_INKS, *STEAM_INKS, *FLASH_INKS, *DUST_INKS,
                      *TORCH_INKS, *LAVA_INKS, *ASH_INKS))


@dataclass(frozen=True)
class Drip:
    x: int
    top: int
    bottom: int
    into_lava: bool


@dataclass(frozen=True)
class Air:
    """What the effects need to know about one room."""

    open: bytes
    covered: bytes
    drips: tuple
    torches: tuple
    pools: tuple
    inks: dict

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


def analyze_room(program, room, art, terrain, palette):
    luminance = Image.alpha_composite(art.background, art.foreground).convert('L')
    air = open_air(luminance, terrain, room)
    covered = art.foreground.getchannel('A').point(lambda value: 255 if value else 0).tobytes()
    pools = lava_surfaces(program, room, palette)
    inks = {index: tuple(palette[index][:3]) + (255,) for index in ALL_INKS}
    drips = choose_drips(air, luminance.tobytes(), terrain, room, pools)
    return Air(air, covered, drips, torch_flames(program, room), pools, inks)


def room_air(level_number, room, art, terrain):
    from pop2.caverns import room_assets

    program, _resources, palette, _shapes = room_assets(level_number, room)
    return analyze_room(program, room, art, terrain, palette)


@dataclass
class Mote:
    x: float
    y: float
    drift: float
    rise: float
    phase: float
    life: int
    shade: int
    fleck: bool = False
    ash: bool = False
    glint: bool = False
    age: int = 0


@dataclass
class Fleck:
    """A splash droplet or a wisp of steam: a short ballistic pixel."""

    x: float
    y: float
    dx: float
    dy: float
    pull: float
    inks: tuple
    life: int
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
class CavernAmbience:
    room: int
    air: Air
    rng: random.Random = field(default_factory=random.Random)
    falls: list = field(default_factory=list)
    motes: list = field(default_factory=list)
    flecks: list = field(default_factory=list)
    glows: tuple = ()
    tick: int = 0

    def __post_init__(self):
        self.glows = tuple((sum(columns) / len(columns), sum(columns.values()) / len(columns))
                           for columns in self.air.pools)
        self.falls = []
        for source in self.air.drips:
            period = self.rng.randint(*TICKS_BETWEEN_DROPS)
            self.falls.append(Fall(source, period, self.rng.randrange(period)))
        count = min(MOST_DUST, self.air.open.count(255) // DUST_PER_AIR_PIXELS)
        for _ in range(count):
            mote = self.new_mote()
            if mote is not None:
                # The room was already dusty before the Prince came in.
                mote.age = self.rng.randrange(mote.life)
                self.motes.append(mote)

    def new_mote(self):
        rng = self.rng
        torches = self.air.torches
        near_torch = bool(torches) and rng.random() < DUST_BY_TORCH
        for _ in range(24):
            if near_torch:
                flame_x, flame_y = rng.choice(torches)
                angle, distance = rng.uniform(0, math.tau), rng.uniform(16, TORCH_REACH * 1.2)
                x, y = int(flame_x + math.cos(angle) * distance), int(flame_y + math.sin(angle) * distance)
            else:
                x, y = rng.randrange(WIDTH), rng.randrange(HEIGHT)
            if self.air.is_open(x, y):
                return Mote(float(x), float(y), rng.uniform(-0.05, 0.05), rng.uniform(-0.03, 0.03),
                            rng.uniform(0, math.tau), rng.randint(*DUST_LIFE), rng.choice(DUST_REST),
                            fleck=rng.random() < DUST_FLECKS)
        return None

    def new_ash(self, columns):
        rng = self.rng
        x = rng.choice(tuple(columns))
        return Mote(float(x), float(columns[x] - 2), rng.uniform(-0.08, 0.08), -rng.uniform(0.45, 0.8),
                    rng.uniform(0, math.tau), rng.randint(*ASH_LIFE), 0, ash=True)

    def draught(self, x, y):
        """The upward pull of the hot air over a pool or around a flame."""
        strongest = 0.0
        for columns in self.air.pools:
            surface = columns.get(int(x))
            if surface is not None and surface - HEAT_HEIGHT < y < surface:
                strongest = max(strongest, HEAT_DRAUGHT * (1 - (surface - y) / HEAT_HEIGHT))
        for flame_x, flame_y in self.air.torches:
            reach = 1 - math.hypot(x - flame_x, y - flame_y) / TORCH_REACH
            strongest = max(strongest, TORCH_DRAUGHT * reach)
        return strongest

    def advance(self, terrain=None):
        self.tick += 1
        for fall in self.falls:
            self.advance_fall(fall, terrain)
        breeze = math.sin(self.tick * 0.011) * 0.07
        kept = []
        for mote in self.motes:
            mote.age += 1
            if mote.age >= mote.life:
                if not mote.ash:
                    mote = self.new_mote()
                    if mote is not None:
                        kept.append(mote)
                continue
            # Ash flutters in the hot air; dust only wanders.
            sway = (math.sin(mote.phase + mote.age * 0.13) * 0.3 if mote.ash
                    else math.sin(mote.phase + mote.age * 0.047) * 0.06)
            mote.x += mote.drift + breeze + sway
            mote.y += mote.rise + math.cos(mote.phase * 1.7 + mote.age * 0.031) * 0.035
            if not mote.ash:
                mote.y -= self.draught(mote.x, mote.y)
                mote.glint = self.rng.random() < GLINT_CHANCE
            kept.append(mote)
        self.motes = kept
        for columns in self.air.pools:
            ash = sum(mote.ash for mote in self.motes)
            if ash < MOST_ASH and self.rng.random() < ASH_CHANCE:
                self.motes.append(self.new_ash(columns))
        flecks = []
        for fleck in self.flecks:
            fleck.age += 1
            fleck.x += fleck.dx
            fleck.y += fleck.dy
            fleck.dy += fleck.pull
            if fleck.age < fleck.life and fleck.y <= fleck.floor:
                flecks.append(fleck)
        self.flecks = flecks

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

    def light(self, x, y):
        """The brightest ramp position a point receives, or None in the dark."""
        best = None
        for flame_x, flame_y in self.air.torches:
            reach = 1 - math.hypot(x - flame_x, y - flame_y) / TORCH_REACH
            if reach > 0:
                level = min(len(TORCH_INKS) - 1, int(reach * len(TORCH_INKS)))
                best = TORCH_INKS[level]
        for glow_x, glow_y in self.glows:
            reach = 1 - math.hypot((x - glow_x) * 0.6, y - glow_y) / LAVA_REACH
            if reach > 0 and best is None:
                best = LAVA_INKS[min(len(LAVA_INKS) - 1, int(reach * len(LAVA_INKS)))]
        return best

    def mote_ink(self, mote):
        if mote.ash:
            return ASH_INKS[min(len(ASH_INKS) - 1, mote.age * len(ASH_INKS) // mote.life)]
        lit = self.light(mote.x, mote.y)
        if lit is not None:
            # A grain turning in the light catches it for a moment.
            return TORCH_INKS[-1] if mote.glint and lit in TORCH_INKS else lit
        # Dust appears and leaves by stepping along the ramp, never by alpha.
        edge = min(mote.age, mote.life - mote.age)
        shade = mote.shade - (edge < 24) - (edge < 12)
        return DUST_INKS[shade] if shade >= 0 else None

    def pixels(self):
        """(x, y, palette index) of everything in this tick, rear first."""
        air = self.air
        for mote in self.motes:
            x, y = int(mote.x), int(mote.y)
            ink = self.mote_ink(mote)
            # Ash is born on the lava, in front of the floor's rear rim.
            if ink is not None and (mote.ash or air.is_open(x, y)):
                yield x, y, ink
                if mote.fleck and air.is_open(x + 1, y):
                    yield x + 1, y, ink
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

    def draw(self, frame):
        air, inks = self.air, self.air.inks
        canvas = frame.load()
        for x, y, ink in self.pixels():
            if 0 <= x < WIDTH and 0 <= y < HEIGHT and not air.is_covered(x, y):
                canvas[x, y] = inks[ink]
        return frame
