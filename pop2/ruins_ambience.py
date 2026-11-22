"""Optional ambience for the ruins (levels six to nine): the night sky.

A port improvement, drawn with the "Cave ambience" menu item like the caves'
(pop2.cavern_ambience) but made of the ruins' own things: the user did not want the
caves' dust and drops again here. Nothing comes from the original game and nothing
touches it. The effect is drawn on the frame, behind the actors, and reads the room
only. Its random numbers come from a private generator, so turning it on cannot
change an opponent, a route or a test.

Each look was shown on its own and approved by the user before it came here
(rendered/ruins-ambience, local only). The same rules hold as in the caves: every
pixel left on the frame is a colour of the room's palette, and everything moves once
per game tick.

The sky. Where the ruins open onto the deep blue of the night there are stars, more
where the sky is bluest and fewer by the purple of the horizon, each in the same
place every time the Prince comes in. Most are dim lilac. Now and then one dips for a
moment, and a bright one flares a small cross. A few of the middling and bright ones
are warm, rose or pale gold. Once in a long while a shooting star crosses the sky: a
faint quick one, an ordinary one, one grazing low and slow, or most rarely a fireball
that bursts at the end and leaves its trail a moment. Over the desert of level nine
the sky has only a few stars, middling and bright.
"""

from dataclasses import dataclass, field
import math
import random

import numpy
from PIL import Image

WIDTH, HEIGHT = 510, 365

RUINS_LEVELS = frozenset({6, 7, 8, 9})

# The night sky: what the ruins paint it with, and how blue it is (1 in the deep blue
# overhead, 0 in the purple by the horizon).
SKY_LEAST_BLUE, SKY_MOST_RED = 60, 100
BLUE_FROM_RED, BLUE_OVER_RED = 16, 40
# A desert room: this much of the room is sky, and this much of it is sand.
DESERT_SKY, DESERT_SAND = 0.1, 0.2
SAND_REDDER, SAND_LEAST_RED = 25, 100


@dataclass(frozen=True)
class StarKind:
    """share: of the stars placed; steps: its light dipped and lit (RGB); cross:
    whether it flares a small cross."""

    share: float
    steps: tuple
    cross: bool


DIM = StarKind(0.7, ((54, 44, 90), (84, 86, 140)), False)
MID = StarKind(0.22, ((84, 86, 140), (103, 103, 149)), False)
BRIGHT = StarKind(0.08, ((103, 103, 149), (134, 134, 175)), True)
# A few warm stars among the lilac ones: a share of the middling and the bright.
ROSE_MID = StarKind(0.22, ((103, 84, 112), (168, 122, 138)), False)
ROSE_BRIGHT = StarKind(0.08, ((168, 122, 138), (240, 196, 196)), True)
GOLD_BRIGHT = StarKind(0.08, ((160, 127, 127), (234, 217, 154)), True)
WARM_MID, WARM_BRIGHT = 0.35, 0.5
STAR_KINDS = (DIM, MID, BRIGHT, ROSE_MID, ROSE_BRIGHT, GOLD_BRIGHT)
# How many stars a room of pure deep-blue sky gets, how far apart they keep, and how
# much clear sky each has around it.
STARS_PER_SKY = 32
STAR_APART = 14
STAR_CLEAR = 2
# The desert's sky: a few stars, far apart, one in five bright.
DESERT_STARS = 9
DESERT_STAR_APART = 30
DESERT_STAR_CLEAR = 3
DESERT_BRIGHT = 0.2
# A star holds its light; now and then it dips one step for a few ticks, and a bright
# one flares its cross for a few.
DIP_CHANCE, DIP_TICKS = 0.012, (2, 5)
FLARE_CHANCE, FLARE_TICKS = 0.02, (2, 4)

LILAC = ((54, 44, 90), (84, 86, 140), (103, 103, 149), (134, 134, 175), (183, 178, 210))
WHITE = (236, 228, 240)


@dataclass(frozen=True)
class ShooterKind:
    """A kind of shooting star: its speed in pixels a tick, the ticks it flies, its
    longest tail, the tail's colours (brightest first), its head, its angle below the
    horizontal in degrees, how often it comes, and for the fireball the ticks of its
    burst at the end and of the trail it leaves."""

    name: str
    speed: float
    ticks: int
    tail: int
    colours: tuple
    head: tuple
    angle: tuple
    weight: int
    burst: int = 0
    linger: int = 0

    @property
    def lasts(self):
        return self.ticks + max(self.burst, self.linger)


FAINT = ShooterKind('faint', 12.0, 4, 6, LILAC[2::-1], LILAC[2], (25, 40), 40)
NORMAL = ShooterKind('normal', 11.0, 7, 11, LILAC[3::-1], LILAC[4], (20, 35), 35)
GRAZER = ShooterKind('grazer', 6.0, 16, 18, LILAC[3::-1], LILAC[4], (6, 12), 18)
FIREBALL = ShooterKind('fireball', 9.0, 10, 14, (LILAC[4], *LILAC[3::-1]), WHITE, (12, 20), 7, burst=2, linger=3)
SHOOTERS = (FAINT, NORMAL, GRAZER, FIREBALL)
# How far back along its path the fireball's trail stays.
LINGER_REACH = 28
# Where a shooting star may start, and how blue its sky must be at its start, halfway
# and at its end.
SHOOTER_LEFT, SHOOTER_TOP, SHOOTER_BOTTOM = 40, 12, 130
SHOOTER_BLUE = 0.4
SHOOTER_TRIES = 500
# Rare: the first comes some time after the Prince does, then one every 20 to 45
# seconds or so, never two at once.
FIRST_SHOOTER = (36, 540)
TICKS_BETWEEN_SHOOTERS = (240, 540)

ALL_COLOURS = frozenset((*(colour for kind in STAR_KINDS for colour in kind.steps), *LILAC, WHITE))


def sky_mask(rgb):
    """[y, x] of the night sky in an RGB picture of the room."""
    red, green, blue = (rgb[..., channel].astype(numpy.int32) for channel in range(3))
    return (green == 0) & (blue >= SKY_LEAST_BLUE) & (red <= SKY_MOST_RED)


def is_sky(colour):
    return colour[1] == 0 and colour[2] >= SKY_LEAST_BLUE and colour[0] <= SKY_MOST_RED


def blueness(rgb):
    """[y, x]: 1 in the deep blue of the upper sky, 0 in the purple by the horizon."""
    return numpy.clip(1 - (rgb[..., 0].astype(numpy.float32) - BLUE_FROM_RED) / BLUE_OVER_RED, 0, 1)


def sand_mask(rgb):
    red, blue = rgb[..., 0].astype(numpy.int32), rgb[..., 2].astype(numpy.int32)
    return (red > blue + SAND_REDDER) & (red >= SAND_LEAST_RED)


def clear_of(sky, margin):
    """The sky with sky all round it, so that no star touches a ruin."""
    clear = sky.copy()
    for dy in (-margin, 0, margin):
        for dx in (-margin, 0, margin):
            clear &= numpy.roll(numpy.roll(sky, dy, 0), dx, 1)
    return clear


def place_stars(sky, blue, rng):
    """[(x, y, kind)], more of them where the sky is bluest."""
    weight = clear_of(sky, STAR_CLEAR) * blue ** 2
    wanted = int(round(STARS_PER_SKY * float(weight.sum()) / (WIDTH * HEIGHT)))
    ys, xs = numpy.nonzero(weight > 0)
    stars = []
    for _ in range(wanted * 40):
        if len(stars) >= wanted or not len(xs):
            break
        i = rng.randrange(len(xs))
        x, y = int(xs[i]), int(ys[i])
        if rng.random() > weight[y, x] or any(math.hypot(x - a, y - b) < STAR_APART for a, b, _ in stars):
            continue
        pick, kind = rng.random(), DIM
        if pick > DIM.share:
            kind = MID if pick < DIM.share + MID.share else BRIGHT
        stars.append((x, y, kind))
    return stars


def warm_some(stars, rng):
    """A share of the middling and bright stars turned rose or pale gold."""
    warmed = []
    for x, y, kind in stars:
        if kind is MID and rng.random() < WARM_MID:
            kind = ROSE_MID
        elif kind is BRIGHT and rng.random() < WARM_BRIGHT:
            kind = rng.choice((ROSE_BRIGHT, GOLD_BRIGHT))
        warmed.append((x, y, kind))
    return warmed


def place_desert_stars(sky, rng):
    """[(x, y, kind)]: a few over the desert, anywhere in its sky."""
    ys, xs = numpy.nonzero(clear_of(sky, DESERT_STAR_CLEAR))
    stars = []
    for _ in range(2000):
        if len(stars) >= DESERT_STARS or not len(xs):
            break
        i = rng.randrange(len(xs))
        x, y = int(xs[i]), int(ys[i])
        if any(abs(x - a) + abs(y - b) < DESERT_STAR_APART for a, b, _ in stars):
            continue
        stars.append((x, y, BRIGHT if rng.random() < DESERT_BRIGHT else MID))
    return stars


def nearest_colours(palette, wanted):
    """{RGB: the nearest RGBA of the palette} by the weighted distance the caves use."""
    rgb = numpy.array(sorted({tuple(colour[:3]) for colour in palette.values()}), dtype=numpy.int64)
    found = {}
    for colour in wanted:
        distance = (((rgb - numpy.array(colour)) * (2, 3, 2)) ** 2).sum(axis=1)
        found[colour] = (*(int(value) for value in rgb[distance.argmin()]), 255)
    return found


@dataclass(frozen=True, eq=False)
class RuinsAir:
    """What the effects need to know about one room."""

    sky: numpy.ndarray
    blue: numpy.ndarray
    stars: tuple
    inks: dict
    desert: bool = False

    def in_sky(self, x, y):
        return 0 <= x < WIDTH and 0 <= y < HEIGHT and bool(self.sky[y, x])


def read_room(level_number, room, rgb, palette):
    """The air of a room from an RGB picture of its scenery and its palette."""
    sky, blue = sky_mask(rgb), blueness(rgb)
    desert = bool(sky.mean() >= DESERT_SKY and sand_mask(rgb).mean() >= DESERT_SAND)
    seed = level_number * 100 + room
    if desert:
        stars = place_desert_stars(sky, random.Random(seed + 41))
    else:
        stars = warm_some(place_stars(sky, blue, random.Random(seed)), random.Random(seed + 7))
    return RuinsAir(sky, blue, tuple(stars), nearest_colours(palette, ALL_COLOURS), desert)


def ruins_air(level_number, room, art, terrain=None, raised=None):
    """The air of a room as the game draws it (terrain and raised as in room_air)."""
    from pop2.caverns import room_assets

    palette = room_assets(level_number, room)[2]
    rgb = numpy.asarray(Image.alpha_composite(art.background, art.foreground).convert('RGB'))
    return read_room(level_number, room, rgb, palette)


@dataclass
class Shooter:
    kind: ShooterKind
    x: float
    y: float
    dx: float
    dy: float
    age: int = 0

    def at(self, distance):
        return int(round(self.x + self.dx * distance)), int(round(self.y + self.dy * distance))


def shooter_path(air, kind, rng):
    """(x, y, dx, dy) of a shooting star whose whole flight is over deep blue sky, or None."""
    travel = kind.speed * kind.ticks
    for _ in range(SHOOTER_TRIES):
        angle = math.radians(rng.uniform(*kind.angle))
        side = rng.choice((1, -1))
        dx, dy = side * math.cos(angle), math.sin(angle)
        x, y = rng.uniform(SHOOTER_LEFT, WIDTH - SHOOTER_LEFT), rng.uniform(SHOOTER_TOP, SHOOTER_BOTTOM)
        ends = [(x + dx * travel * share, y + dy * travel * share) for share in (0, 0.5, 1)]
        if all(0 <= ex < WIDTH and 0 <= ey < HEIGHT and air.sky[int(ey), int(ex)]
               and air.blue[int(ey), int(ex)] > SHOOTER_BLUE for ex, ey in ends):
            return x, y, dx, dy
    return None


def shooter_pixels(shooter):
    """(x, y, RGB) of a shooting star at its age, the later over the earlier."""
    kind, age = shooter.kind, shooter.age
    travelled = kind.speed * min(age, kind.ticks - 1)
    # The fireball's trail stays a moment, dimmest, where it has just been.
    if kind.linger and age >= 2:
        fading = max(0, age - kind.ticks)
        if fading < kind.linger:
            for step in range(max(0, int(travelled) - LINGER_REACH), int(travelled)):
                if (step * 7 + age) % 3 or fading < 2:
                    yield (*shooter.at(step), kind.colours[-1])
    if age >= kind.ticks:
        if kind.burst and age < kind.ticks + kind.burst:
            x, y = shooter.at(travelled)
            for ox, oy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                yield x + ox, y + oy, kind.head if (ox, oy) == (0, 0) else kind.colours[0]
        return
    # The tail shortens as it burns out.
    length = max(2, int(kind.tail * (1.15 - age / kind.ticks)))
    for step in range(length, 0, -1):
        share = step / length
        yield (*shooter.at(travelled - step),
               kind.colours[min(len(kind.colours) - 1, int(share * len(kind.colours)))])
    yield (*shooter.at(travelled), kind.head)
    if kind is FIREBALL:
        # A head two pixels across: the second one dimmer, beside it on the slope.
        x, y = shooter.at(travelled)
        yield x, y + 1 if abs(shooter.dx) > abs(shooter.dy) else y, kind.colours[0]


@dataclass
class RuinsAmbience:
    room: int
    air: RuinsAir
    rng: random.Random = field(default_factory=random.Random)
    # Per star: ticks it stays dipped, ticks it keeps its cross.
    twinkles: list = field(default_factory=list)
    shooter: Shooter | None = None
    shooter_wait: int = 0
    tick: int = 0

    def __post_init__(self):
        self.twinkles = [[0, 0] for _ in self.air.stars]
        self.shooter_wait = self.rng.randint(*FIRST_SHOOTER)

    def see_gates(self, art):
        """The caves' torches watch the gates; nothing here does."""

    def advance(self, terrain=None, footing=None, thuds=()):
        """One game tick."""
        self.tick += 1
        self.twinkle()
        self.advance_shooter()

    def twinkle(self):
        rng = self.rng
        for (_x, _y, kind), twinkle in zip(self.air.stars, self.twinkles):
            if twinkle[0]:
                twinkle[0] -= 1
            elif rng.random() < DIP_CHANCE:
                twinkle[0] = rng.randint(*DIP_TICKS)
            if twinkle[1]:
                twinkle[1] -= 1
            elif kind.cross and rng.random() < FLARE_CHANCE:
                twinkle[1] = rng.randint(*FLARE_TICKS)

    def advance_shooter(self):
        if self.shooter is not None:
            self.shooter.age += 1
            if self.shooter.age >= self.shooter.kind.lasts:
                self.shooter = None
            return
        self.shooter_wait -= 1
        if self.shooter_wait > 0:
            return
        self.shooter_wait = self.rng.randint(*TICKS_BETWEEN_SHOOTERS)
        kind = self.rng.choices(SHOOTERS, weights=[kind.weight for kind in SHOOTERS])[0]
        path = shooter_path(self.air, kind, self.rng)
        if path is not None:
            self.shooter = Shooter(kind, *path)

    def sky_pixels(self):
        """(x, y, RGB) of the stars and the shooting star, the later over the earlier."""
        for (x, y, kind), (dipped, flared) in zip(self.air.stars, self.twinkles):
            yield x, y, kind.steps[0] if dipped else kind.steps[-1]
            if kind.cross and flared:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    yield x + dx, y + dy, kind.steps[0]
        if self.shooter is not None:
            yield from shooter_pixels(self.shooter)

    def draw(self, frame):
        """Only on the sky, and only where the frame still shows it: a gate or a tile
        coming down in front of the sky covers the stars too."""
        air, inks = self.air, self.air.inks
        canvas = frame.load()
        drawn = set()
        for x, y, colour in self.sky_pixels():
            if air.in_sky(x, y) and ((x, y) in drawn or is_sky(canvas[x, y])):
                canvas[x, y] = inks[colour]
                drawn.add((x, y))
        return frame
