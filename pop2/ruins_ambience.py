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

The wind. In a room open to the sky a gust now and then sends one or two thin streaks
of air across it, over the ruins too: a long wavy line a few shades paler than what is
behind it, which runs in, rolls one small curl that comes out a little higher than it
went in, and runs out. It slows down to wind its curl and fades in and out in three
steps of the palette, as a game of the time would. The desert has its own wind.
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

# The wind blows in rooms with this much sky. A gust: ticks between gusts (counted once
# the last is over), how long one lasts, its streaks, and how far below the first the
# second runs.
OPEN_SKY = 0.04
TICKS_BETWEEN_GUSTS = (90, 160)
GUST_TICKS = 44
STREAKS_A_GUST = (1, 2)
SECOND_STREAK_BELOW = (16, 32)
# A streak: where it may start, its run in and out, its wave, its curl's first radius
# and how much higher it comes out, and how many pixels of it show at once.
STREAK_TOP, STREAK_BOTTOM = 20, 300
STREAK_LEFT, STREAK_RIGHT = -30, WIDTH - 260
RUN_IN, RUN_OUT = (90, 140), (60, 110)
WAVE, WAVE_LENGTH = (1.0, 2.5), (60, 90)
CURL_RADIUS, CURL_RISE = (4.0, 4.5), 2.0
STREAK_LENGTH = (40, 60)
# Pixels of its path its head runs a tick, slower near its curl and slower still in it.
STREAK_SPEED, NEAR_CURL_SPEED, CURL_SPEED = 8, 5, 3
NEAR_CURL = 16
# How much paler than what is behind it: its body, and its two ends; and the ticks of
# each of its three steps of fading in and out.
BODY_PALER, END_PALER = (52, 50, 62), (26, 25, 31)
FADE_STEP = 2


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


def palette_rgb(palette):
    return numpy.array(sorted({tuple(colour[:3]) for colour in palette.values()}), dtype=numpy.int64)


def nearest_colours(palette, wanted):
    """{RGB: the nearest RGBA of the palette} by the weighted distance the caves use."""
    rgb = palette_rgb(palette)
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
    # Wind only where the room is open to the sky; never in the desert.
    windy: bool = False
    # [y, x] of what the foreground covers.
    covered: numpy.ndarray | None = None
    palette: numpy.ndarray | None = None
    # {(RGB behind, how much paler): RGBA}, filled as it is wanted.
    paler: dict = field(default_factory=dict)

    def in_sky(self, x, y):
        return 0 <= x < WIDTH and 0 <= y < HEIGHT and bool(self.sky[y, x])

    def is_covered(self, x, y):
        return self.covered is not None and bool(self.covered[y, x])

    def paler_than(self, behind, amount):
        key = behind, amount
        if key not in self.paler:
            self.paler[key] = (*paler(behind, amount, self.palette), 255)
        return self.paler[key]


def paler(behind, amount, palette):
    """The palette colour nearest to a few steps paler than behind, never behind itself."""
    wanted = numpy.minimum(255, numpy.array(behind) + amount)
    distance = (((palette - wanted) * (2, 3, 2)) ** 2).sum(axis=1)
    for index in distance.argsort(kind='stable'):
        colour = tuple(int(value) for value in palette[index])
        if colour != tuple(behind) and sum(colour) > sum(behind):
            return colour
    return tuple(behind)


def read_room(level_number, room, rgb, palette, covered=None):
    """The air of a room from an RGB picture of its scenery, its palette and [y, x] of
    what its foreground covers."""
    sky, blue = sky_mask(rgb), blueness(rgb)
    open_sky = float(sky.mean())
    desert = bool(open_sky >= DESERT_SKY and sand_mask(rgb).mean() >= DESERT_SAND)
    seed = level_number * 100 + room
    if desert:
        stars = place_desert_stars(sky, random.Random(seed + 41))
    else:
        stars = warm_some(place_stars(sky, blue, random.Random(seed)), random.Random(seed + 7))
    return RuinsAir(sky, blue, tuple(stars), nearest_colours(palette, ALL_COLOURS), desert,
                    windy=open_sky >= OPEN_SKY and not desert, covered=covered, palette=palette_rgb(palette))


def ruins_air(level_number, room, art, terrain=None, raised=None):
    """The air of a room as the game draws it (terrain and raised as in room_air)."""
    from pop2.caverns import room_assets

    palette = room_assets(level_number, room)[2]
    rgb = numpy.asarray(Image.alpha_composite(art.background, art.foreground).convert('RGB'))
    covered = numpy.asarray(art.foreground.getchannel('A')) > 0
    return read_room(level_number, room, rgb, palette, covered)


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


def clean_line(points):
    """The pixels of a path, one each, without the corner pixel of a diagonal step."""
    pixels = []
    for px, py in points:
        pixel = (int(round(px)), int(round(py)))
        if not pixels or pixels[-1] != pixel:
            pixels.append(pixel)
    clean = [pixels[0]]
    for i in range(1, len(pixels) - 1):
        a, b = clean[-1], pixels[i + 1]
        if abs(a[0] - b[0]) == 1 and abs(a[1] - b[1]) == 1:
            continue
        clean.append(pixels[i])
    clean.append(pixels[-1])
    return clean


def curl(bx, by, r0, rise):
    """A curl from (bx, by), heading right: up by the right, over the top, down the left
    and back under, its radius shrinking by rise so that it ends rise higher than it
    began and does not close."""
    cx, cy = bx, by - r0
    points, steps = [], 720
    for i in range(1, steps + 1):
        turn = i / steps
        angle = -math.pi / 2 + 2 * math.pi * turn
        r = r0 - rise * turn
        points.append((cx + r * math.cos(angle), cy - r * math.sin(angle)))
    return points


@dataclass
class Streak:
    """A streak of wind: its path's pixels, where its curl begins and ends among them,
    how many show at once, and how far its head has run."""

    pixels: list
    curl: tuple
    length: int
    y: float
    head: float = 0.0
    shown: int = 0
    tangents: list | None = None

    @property
    def gone(self):
        return self.head - self.length >= len(self.pixels)

    def step(self):
        """How far its head runs this tick: slower about its curl."""
        begin, end = self.curl
        if begin - 2 <= self.head <= end + 2:
            return CURL_SPEED
        if begin - NEAR_CURL <= self.head <= end + NEAR_CURL:
            return NEAR_CURL_SPEED
        return STREAK_SPEED

    def strength(self):
        """How much of its paleness shows: a third, two thirds or all of it."""
        left = (len(self.pixels) + self.length - self.head) / STREAK_SPEED
        level = min(3, self.shown // FADE_STEP + 1, math.ceil(max(0.0, left) / FADE_STEP))
        return max(1, level) / 3

    def showing(self):
        head = int(self.head)
        return range(max(0, head - self.length), min(head, len(self.pixels)))


def ribbon(x0, y0, rng):
    """(pixels, (curl begin, curl end)) of a streak's path from (x0, y0)."""
    run_in, run_out = rng.uniform(*RUN_IN), rng.uniform(*RUN_OUT)
    wave, wave_length = rng.uniform(*WAVE), rng.uniform(*WAVE_LENGTH)
    phase = rng.uniform(0, 2 * math.pi)
    r0 = rng.uniform(*CURL_RADIUS)
    points, x = [], 0.0
    while x < run_in:
        points.append((x0 + x, y0 + wave * math.sin(phase + 2 * math.pi * x / wave_length)))
        x += 0.25
    bx, by = points[-1]
    run = len(points)
    points += curl(bx, by, r0, CURL_RISE)
    ex, ey = points[-1]
    start = wave * math.sin(phase + 2 * math.pi * run_in / wave_length)
    x = 0.25
    while x < run_out:
        points.append((ex + x, ey + wave * math.sin(phase + 2 * math.pi * (run_in + x) / wave_length) - start))
        x += 0.25
    path = clean_line(points)
    # The pixels nearest where the curl begins and ends: cleaning may drop the very ones.
    near = len(clean_line(points[:run]))
    begin = min(range(max(0, near - 4), min(len(path), near + 4)),
                key=lambda i: math.hypot(path[i][0] - bx, path[i][1] - by))
    end = min(range(begin + 5, min(len(path), begin + 80)),
              key=lambda i: math.hypot(path[i][0] - ex, path[i][1] - ey))
    return path, (begin, end)


def new_streak(rng, gust_y=None):
    y0 = gust_y + rng.uniform(*SECOND_STREAK_BELOW) if gust_y is not None else rng.uniform(STREAK_TOP, STREAK_BOTTOM)
    x0 = rng.uniform(STREAK_LEFT, STREAK_RIGHT)
    pixels, bends = ribbon(x0, y0, rng)
    return Streak(pixels, bends, rng.randint(*STREAK_LENGTH), y0)


def streak_pixels(streak):
    """(x, y, how much paler) of what shows of a streak, its ends less pale."""
    showing = streak.showing()
    strength = streak.strength()
    last = max(1, len(showing) - 1)
    for i, index in enumerate(showing):
        share = i / last
        amount = END_PALER if share < 0.25 or share > 0.9 else BODY_PALER
        yield (*streak.pixels[index], tuple(round(value * strength) for value in amount))


@dataclass
class RuinsAmbience:
    room: int
    air: RuinsAir
    rng: random.Random = field(default_factory=random.Random)
    # Per star: ticks it stays dipped, ticks it keeps its cross.
    twinkles: list = field(default_factory=list)
    shooter: Shooter | None = None
    shooter_wait: int = 0
    streaks: list = field(default_factory=list)
    gust: int = 0
    gust_wait: int = 0
    tick: int = 0

    def __post_init__(self):
        self.twinkles = [[0, 0] for _ in self.air.stars]
        self.shooter_wait = self.rng.randint(*FIRST_SHOOTER)
        self.gust_wait = self.rng.randint(*TICKS_BETWEEN_GUSTS)

    def see_gates(self, art):
        """The caves' torches watch the gates; nothing here does."""

    def advance(self, terrain=None, footing=None, thuds=()):
        """One game tick."""
        self.tick += 1
        self.twinkle()
        self.advance_shooter()
        self.blow()
        self.advance_streaks()

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

    def blow(self):
        """Now and then a gust, with its streaks: only in rooms open to the sky."""
        if not self.air.windy:
            return
        if self.gust:
            self.gust -= 1
            return
        self.gust_wait -= 1
        if self.gust_wait > 0:
            return
        rng = self.rng
        self.gust, self.gust_wait = GUST_TICKS, rng.randint(*TICKS_BETWEEN_GUSTS)
        gust_y = None
        for _ in range(rng.randint(*STREAKS_A_GUST)):
            streak = new_streak(rng, gust_y)
            gust_y = streak.y
            self.streaks.append(streak)

    def advance_streaks(self):
        for streak in self.streaks:
            streak.head += streak.step()
            streak.shown += 1
        self.streaks = [streak for streak in self.streaks if not streak.gone]

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
        # The wind, behind what the foreground covers, paler than what it crosses.
        for streak in self.streaks:
            for x, y, amount in streak_pixels(streak):
                if 0 <= x < WIDTH and 0 <= y < HEIGHT and not air.is_covered(x, y):
                    canvas[x, y] = air.paler_than(tuple(canvas[x, y][:3]), amount)
        return frame
