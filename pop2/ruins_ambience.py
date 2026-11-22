"""Optional ambience for the ruins (levels six to nine): the night sky.

A port improvement, drawn with the "Ambient effects" menu item like the caves'
(pop2.cavern_ambience) but made of the ruins' own things: the user did not want the
caves' floating dust and drops again here, only, later, the puffs of dust their feet,
tiles and gates raise (2026-11-22). Nothing comes from the original game and nothing
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

The grit. Every few seconds a little grit trickles from a crack in the underside of a
block or a ledge, now and then a thin pour that heaps a small mound on the floor and
wears away later. Its grains are mostly specks, some chips and a few crumbs that
tumble as they fall and break in two when they land; a few bits jump up where they
land and some lie a moment. A blow shakes grit down from the ceilings, most near it:
the Prince bumping his head jumping up, stamping, landing hard, a gate slamming or
shutting, a loose floor landing; the strongest bring down a pebble or two. Grit falling
on the Prince bounces off his head and shoulders, and a streak of wind passing carries
the grains along its way. Over pale stone the grit is a step darker so that it shows,
and all of it is a little gentler than its own colours.
The paintings (the start room, the throne room, the horse and the desert) shed none.

The puffs. Whatever comes down knocks up a puff of dust from the floor, as in the caves:
the Prince's steps, skids and landings, a loose floor landing, a gate or a door coming
down. They are the caves' own puffs, in the pale rose of the ruins' grit.

The desert. A light breeze carries sand along the connected rooms of level nine's dunes.
The wind comes in stronger gusts, now and then two or
three close together, then a lull, each its own strength, speed and stretch of the room,
blowing harder and softer as it goes. Each runs along the crest of the near dune and blows a low spray of sand
off it, sweeps loose sand up off the plain, runs streams of sand along the ground, hits
the rocks (sand runs at a big rock's foot, grains bounce up its face, and the ground
lies still in its lee) and now and then a small dust devil of sand grains spins along
the crest for a while, each its own size, shape, ways and life. A few low grains curl
around its foot, with short sprays of sand skipping away to either side. All of it is
a little gentler than the sand's own colours, and none of it blows over the blue dunes far away.
"""

from collections import deque
from dataclasses import dataclass, field
import math
import random

import numpy
from PIL import Image

from pop2.cavern_ambience import (
    CLOUD_CRUMBLE, CLOUD_PALER, CLOUD_STEPS, EMPTY_TILES, FLOOR_STRIP, LANDING_DEPTH, MOST_CLOUDS, SHUT_PUFF,
    SLAM_PUFF, TILE_HEIGHT, TILE_PUFF, TILE_WIDTH, TIP_LUMINANCE, Cloud, Fleck, colours_of, floor_y,
    footfalls, landing, open_air,
)

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
# Low in the purple by the horizon, fewer stars and fainter: muted lilac, never a cross.
HAZE_DIM = StarKind(0.8, ((63, 48, 104), (87, 73, 118)), False)
HAZE_MID = StarKind(0.2, ((87, 73, 118), (100, 87, 122)), False)
STAR_KINDS = (DIM, MID, BRIGHT, ROSE_MID, ROSE_BRIGHT, GOLD_BRIGHT, HAZE_DIM, HAZE_MID)
# How many stars a room of pure deep-blue sky gets, how far apart they keep, and how
# much clear sky each has around it.
STARS_PER_SKY = 32
STAR_APART = 14
STAR_CLEAR = 2
# The purple has this share of the stars the deep blue would, further apart.
HAZE_SHARE = 0.4
HAZE_APART = 22
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
SHOOTER_LEFT = 40
SHOOTER_TRIES = 500
# Rare: the first comes some time after the Prince does, then one every 20 to 45
# seconds or so, never two at once.
FIRST_SHOOTER = (24, 120)
TICKS_BETWEEN_SHOOTERS = (120, 300)

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

# The grit's colours, as RGB, each shown as the nearest of the room's palette.
GRIT_PALE, GRIT_HEAD, GRIT_TAIL, GRIT_DIM = (173, 141, 141), (166, 131, 131), (135, 110, 110), (113, 87, 113)
# The puffs' steps, thinnest first, as the caves' (CLOUD_SHADES): the colour, and how
# much of what is behind it the step hides at full strength. The ruins' warm light
# colours, the grit's pale rose; never lit by a torch, as nothing here is.
PUFF_SHADES = (((160, 127, 127), 0.5), (GRIT_HEAD, 0.75), (GRIT_PALE, 1.0))
# How far round a puff's pixel what is behind it is taken from (a square of 5).
PUFF_BEHIND = 2
PEBBLE_DARK = (82, 62, 86)
GRIT_COLOURS = (GRIT_PALE, GRIT_HEAD, GRIT_TAIL, GRIT_DIM, PEBBLE_DARK)
# Where grit comes from: the underside of stone this many pixels thick, with this much
# clear air below, at most GRIT_UNDERSIDE above the bottom of its row, never a door's
# arch, falling at least GRIT_SHORTEST_FALL onto a floor with most of the way clear.
GRIT_STONE_ABOVE = 6
GRIT_CLEAR_BELOW = 10
GRIT_UNDERSIDE = 30
GRIT_NOT_FROM = (16, 17)
GRIT_SHORTEST_FALL = 48
GRIT_PATH_CLEAR = 0.9
# The room's own cracks: how many and how far apart.
MOST_GRIT, GRIT_APART = 4, 60
# Ceiling c is the underside over row c: within these pixels of c * TILE_HEIGHT + 5,
# with this much clear air below.
CEILING_ABOVE, CEILING_BELOW, CEILING_CLEAR = 25, 7, 6
# The room's rhythm: ticks between trickles, a sprinkle's grains, how often one is a pour
# instead, and its grains. The user, 2026-11-22: every 2 to 5 seconds (24-60 ticks) was a
# little too much; now every 3.5 to 8 seconds or so.
TICKS_BETWEEN_TRICKLES = (40, 100)
SPRINKLE = (3, 6)
POUR_CHANCE, POUR = 0.25, (14, 26)
SPRINKLE_GAP = (0, 1)
GRIT_GRAVITY, GRIT_FASTEST = 0.8, 6.0
# A new trickle this close to one still running is not started.
SAME_CRACK = 2
# A blow: how strong each kind is, from what speed a landing is one (1.0 from twice
# that), grains right over the hands of a bump, how far a shake reaches (rows count 0.7
# of their height), how fast it spreads (pixels a tick) and the most cracks it opens.
STRENGTH = dict(bump=1.0, stamp=0.45, slam=0.9, tile=0.9, shut=0.35)
HARD_LANDING = 18
BUMP_REACH, BUMP_SPOTS, BUMP_GRAINS = 14, (3, 5), (4, 8)
SHAKE_REACH, SHAKE_SPREAD, SHAKE_EVERY, MOST_SPOTS = 120, 50, 12, 12
ONE_BLOW_APART = 40
# Pebbles: from blows this strong, how many, their fall, bounce and rest.
PEBBLE_FROM, PEBBLES = 0.7, (1, 3)
PEBBLE_GRAVITY, PEBBLE_FASTEST, PEBBLE_BOUNCE = 1.0, 7.0, 0.3
PEBBLE_REST = (8, 16)
# A grain's head, by chance (the middle shades most), and the two steps of its tail.
HEADS = (GRIT_PALE, GRIT_HEAD, GRIT_HEAD, GRIT_TAIL)
TAILS = {GRIT_PALE: (GRIT_HEAD, GRIT_TAIL), GRIT_HEAD: (GRIT_TAIL, GRIT_DIM), GRIT_TAIL: (GRIT_DIM, GRIT_DIM)}
# A sprinkle's grains: how often each size, and the turns of a chip and a crumb as they
# tumble (one turn every TUMBLE ticks, either way round), lit at the top left.
SIZES = (('speck', 0.7), ('chip', 0.25), ('crumb', 0.05))
TURNS = {'chip': (((0, 0), (0, 1)), ((0, 0), (1, 1)), ((0, 0), (1, 0)), ((1, 0), (0, 1))),
         'crumb': (((0, 0), (1, 0), (0, 1)), ((0, 0), (1, 0), (1, 1)), ((1, 0), (0, 1), (1, 1)),
                   ((0, 0), (0, 1), (1, 1)))}
TUMBLE = 2
SHADES = {GRIT_PALE: (GRIT_PALE, GRIT_HEAD, GRIT_TAIL), GRIT_HEAD: (GRIT_HEAD, GRIT_TAIL, GRIT_DIM),
          GRIT_TAIL: (GRIT_TAIL, GRIT_DIM, PEBBLE_DARK)}
# A pour's thread: grains this close are joined, its dither running down, and its grains
# spaced at its start and end.
THREAD_GAP = 4
THREAD = (GRIT_HEAD, GRIT_PALE, GRIT_TAIL, GRIT_HEAD)
POUR_THIN_START, POUR_THIN_END = 3, 4
# Landing: the chance a grain kicks bits up (a pour's less), how many, how high and how
# far aside (pixels a tick), how fast they fall back, how long they last; and the
# chance it lies on the floor a moment, and how long.
SPLASH_CHANCE, POUR_SPLASH_CHANCE = 0.45, 0.25
SPLASH_BITS, SPLASH_LIFT, SPLASH_SIDE = (1, 2), (0.8, 1.6), (0.4, 1.1)
SPLASH_PULL, SPLASH_LIFE = 0.45, (3, 5)
REST_CHANCE, POUR_REST_CHANCE = 0.5, 0.2
REST_LIFE = (6, 12)
# A pour's mound: its heights (offsets -3..3 from where it lands), the chance a grain
# stays on it, how long it stays after the pour and how often it then loses a grain.
MOUND = (1, 2, 3, 4, 3, 2, 1)
HEAP_CHANCE = 0.75
MOUND_STAYS, MOUND_WEARS = (72, 144), (4, 8)
# Off the Prince: how far aside and up a bit is thrown, how fast it falls back, how many
# times it may bounce again, and the most ticks it flies.
OFF_SIDE, OFF_UP, OFF_PULL, OFF_BOUNCES = (0.5, 1.3), (0.6, 1.5), 0.5, 2
OFF_LIFE = 30
# The streak's own wind: how near the grit must be, its strongest push (pixels a tick),
# how quickly a grain takes it up, and how much of an upward push lifts it.
STREAK_REACH, STREAK_PUSH, STREAK_TAKE, STREAK_LIFT = 14.0, 6.0, 0.5, 0.6
# Background this bright (0-255) counts as pale stone: there the grit steps darker.
PALE_STONE = 140
ON_PALE = {GRIT_PALE: GRIT_TAIL, GRIT_HEAD: GRIT_DIM, GRIT_TAIL: PEBBLE_DARK, GRIT_DIM: PEBBLE_DARK}

# The desert. The near dune's crest is its first run of this much solid sand down each
# column; a room is dunes when the crest runs right across it this flat.
CREST_SOLID = 4
DUNE_CREST_SPREAD = 40
# Gusts. The user, 2026-11-22: the same straight wave each time, on the same beat, looked
# made. Each gust is its own now: they come in spells of two or three close together
# (SPELL_CHANCE that another follows soon) and lulls, about as often as before overall;
# each has its own strength, speed and stretch of the room, its sands only off the crest,
# only off the plain or both, and blows harder and softer as it goes. The first comes
# this soon.
FIRST_DESERT_GUST = (3, 16)
GUST_SOON, GUST_LULL, SPELL_CHANCE = (18, 45), (70, 190), 0.45
# Its strength scales the sand it lifts: about as much on the whole as before, when every
# gust lifted the same.
GUST_STRENGTH = (0.55, 1.45)
GUST_SPEED = (4.5, 7.5)
# Where its front comes down, most often off the left edge, now and then a way in (the
# share of the way GUST_FROM's range, squared), and how far it runs, rising over the
# first GUST_RISE pixels and dying away over the last share.
GUST_FROM = (-60, 150)
GUST_REACH = (200, 640)
GUST_RISE, GUST_DIES = 40, 0.35
# Of the gusts: both the crest and the plain, the crest only, the plain only.
GUST_KINDS = ((0.6, True, True), (0.15, True, False), (0.25, False, True))
# The crest's spray: its sands, palest first; how fast the gust's front runs along the
# crest (pixels a tick), the grains leaving by it a tick, and their flight.
SAND = ((166, 120, 104), (148, 98, 90), (125, 88, 68))
CREST_FRONT = 6.0
CREST_GRAINS = (2, 4)
CREST_BEHIND = 24
CREST_LIFE, CREST_SPEED, CREST_LIFT, CREST_SETTLE, CREST_DRAG = (7, 15), (2.5, 5.0), (0.3, 1.0), 0.12, 0.96
# A fast young grain leaves a dimmer pixel behind it.
FAST_GRAIN = 3.5
# The plain: where it starts below the crest's lowest point, the front's speed, the
# grains it lifts a tick from how far behind it, and their flight (the far end of each
# range at the top of the plain, the near end at the bottom of the room).
GROUND_FROM = 20
GROUND_FRONT = 7.0
GROUND_GRAINS = (5, 8)
GROUND_REACH = 40
GROUND_SPEED = ((1.5, 3.0), (3.5, 6.0))
GROUND_LIFT = ((0.2, 0.6), (0.4, 1.1))
GROUND_SETTLE, GROUND_DRAG = 0.12, 0.95
GROUND_LIFE = ((5, 9), (8, 14))
FAR_SANDS = ((157, 114, 98), (149, 106, 90), (134, 99, 83))
NEAR_SANDS = ((173, 141, 141), (166, 131, 131), (157, 114, 98))
# The lighter breeze that runs across the whole stretch of dunes, even between gusts.
# Each row gives a depth on the plain, spacing in world pixels, speed and starting phase.
DUNE_BREEZE = ((0.05, 173, 2, 31), (0.19, 227, 3, 129), (0.32, 191, 3, 59),
               (0.49, 263, 4, 206), (0.66, 219, 4, 87), (0.84, 281, 5, 42))
BREEZE_TRAIL = ((0, 0, 0), (6, -1, 1), (13, 2, 1), (22, 0, 2))
# Streams of sand along the ground: how many a gust, how late, their fronts, how far they
# run, their grains a tick and the grains' flight.
STREAMS, STREAM_DELAY = (2, 4), 14
STREAM_FRONT, STREAM_TRAVEL = (6.0, 9.0), (220, 420)
STREAM_GRAINS = (2, 3)
# A grain's speed: the near ends at the top of the plain, plus these at the bottom.
STREAM_SPEED, STREAM_NEAR_SPEED = (1.5, 2.0), (3.0, 6.0)
STREAM_LIFT, STREAM_SETTLE, STREAM_LIFE = (0.2, 0.7), 0.15, (6, 12)
# Rocks: a patch of the plain this big that is not sand; a grain riding this near its foot
# runs into it and is kicked back and up its face; as a gust reaches a rock this big sand
# runs at its foot.
SMALLEST_ROCK = 12
FOOT_DEPTH = 6
KICK_BACK, KICK_UP = (0.15, 0.4), (1.2, 2.4)
BIG_ROCK, AT_ROCK = 40, (4, 7)
# The dust devil: how long it lives and takes to rise and to die away, how far it drifts
# a tick, grains it lifts a tick at full strength, how fast they spin and climb, its
# height, how wide it opens at the top, how far its top leans downwind, and its colours.
FIRST_DEVIL, TICKS_BETWEEN_DEVILS = (30, 360), (240, 720)
DEVIL_LIFE, DEVIL_RISE, DEVIL_FADE = 190, 24, 24
DEVIL_DRIFT = 0.4
DEVIL_FROM = (60, WIDTH - 140)
DEVIL_FOOT, DEVIL_SMOOTH = 10, 12
DEVIL_GRAINS = 5
SPIN, CLIMB = (0.45, 0.75), (0.5, 0.9)
HEIGHT_OF_DEVIL, TOP_RADIUS, LEAN = 30, 6.0, 4.0
# The user, 2026-11-22: every devil looked the same, with the same moves. Each is its own
# now, drawn from these: how long it lives, how fast it drifts and how far it wanders to
# and fro, its height, how wide it opens, how far it leans, how many grains it lifts, how
# fast and how far it sways, and how much it thickens and thins as it goes.
DEVIL_LIVES = (130, 260)
DEVIL_DRIFTS = (0.2, 0.6)
DEVIL_WANDER, DEVIL_WANDER_TICKS = (0.0, 4.0), (30, 70)
DEVIL_HEIGHTS = (22, 36)
DEVIL_TOPS = (4.5, 7.5)
DEVIL_LEANS = (1.5, 6.0)
DEVIL_GRAIN_COUNTS = (3.5, 6.5)
DEVIL_SWAY_SPEEDS, DEVIL_SWAYS = (0.15, 0.35), (0.6, 2.2)
DEVIL_PULSE, DEVIL_PULSE_TICKS = (0.0, 0.4), (12, 30)
# At its foot a few grains spin close to the funnel between short sprays of sand.
FOOT_WIDTH = (2.4, 4.2)
FOOT_GRAINS = (1, 2)
FOOT_HOP, FOOT_LIFE = (0.3, 0.9), (4, 7)
FOOT_SPIN = (0.6, 1.1)
FOOT_SPRAY_TICKS, FOOT_SPRAY_GRAINS = (9, 15), (8, 11)
THROWN_DX, THROWN_DY, THROWN_FALL = (0.68, 1.76), (-1.25, -0.5), 0.24
FOOT_HIGHLIGHT = (240, 196, 196)
NEAR_SIDE, FAR_SIDE, FLUNG = (166, 131, 131), (149, 106, 90), (125, 88, 68)
# Every pixel of blown sand sits this much of the way back toward the colour behind it.
GENTLE = 0.4
DESERT_COLOURS = (*SAND, *FAR_SANDS, *NEAR_SANDS, NEAR_SIDE, FAR_SIDE, FLUNG, FOOT_HIGHLIGHT)

# Every colour the effects use, each shown as the nearest of the room's palette.
INK_COLOURS = ALL_COLOURS | frozenset(GRIT_COLOURS) | frozenset(DESERT_COLOURS)


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


def place_haze_stars(sky, blue, stars, rng):
    """[(x, y, kind)]: a few faint ones in the purple by the horizon, clear of the others."""
    weight = clear_of(sky, STAR_CLEAR) * (1 - blue) ** 2
    wanted = int(round(STARS_PER_SKY * HAZE_SHARE * float(weight.sum()) / (WIDTH * HEIGHT)))
    ys, xs = numpy.nonzero(weight > 0)
    placed = []
    for _ in range(wanted * 40):
        if len(placed) >= wanted or not len(xs):
            break
        i = rng.randrange(len(xs))
        x, y = int(xs[i]), int(ys[i])
        if (rng.random() > weight[y, x] or any(math.hypot(x - a, y - b) < STAR_APART for a, b, _ in stars)
                or any(math.hypot(x - a, y - b) < HAZE_APART for a, b, _ in placed)):
            continue
        placed.append((x, y, HAZE_DIM if rng.random() < HAZE_DIM.share else HAZE_MID))
    return placed


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


def around(frame, box, radius):
    """[y, x, RGB] of the box of the frame, each pixel the mean of the square of pixels
    radius round it (the frame's edge pixels carried on past it)."""
    left, top, right, bottom = box
    near = (max(0, left - radius), max(0, top - radius), min(WIDTH, right + radius), min(HEIGHT, bottom + radius))
    rgb = numpy.asarray(frame.crop(near).convert('RGB'), dtype=numpy.int64)
    rgb = numpy.pad(rgb, ((near[1] - top + radius, bottom + radius - near[3]),
                          (near[0] - left + radius, right + radius - near[2]), (0, 0)), mode='edge')
    sums = numpy.pad(rgb.cumsum(0).cumsum(1), ((1, 0), (1, 0), (0, 0)))
    side = 2 * radius + 1
    total = sums[side:, side:] - sums[:-side, side:] - sums[side:, :-side] + sums[:-side, :-side]
    return (total // (side * side)).astype(numpy.int32)


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
    # The room's own cracks, and for each ceiling [x] the y grit leaves it at, or -1.
    grit: tuple = ()
    ceilings: tuple = ()
    # [y, x] of the scenery's brightness (0-255).
    luminance: numpy.ndarray | None = None
    # The desert's dunes, when it has them.
    dunes: object = None
    # {(RGB behind, RGB drawn): RGBA} of the gentler sand, filled as it is wanted.
    gentler: dict = field(default_factory=dict)
    # The room's palette as the caves key their tables (colours_of), for the puffs.
    palette_key: tuple = ()

    def in_sky(self, x, y):
        return 0 <= x < WIDTH and 0 <= y < HEIGHT and bool(self.sky[y, x])

    def is_covered(self, x, y):
        return self.covered is not None and bool(self.covered[y, x])

    def paler_than(self, behind, amount):
        key = behind, amount
        if key not in self.paler:
            self.paler[key] = (*paler(behind, amount, self.palette), 255)
        return self.paler[key]

    def gentle(self, behind, drawn, amount=GENTLE):
        """The sand drawn over behind, amount of the way back toward it, never behind
        itself."""
        key = behind, drawn, amount
        if key not in self.gentler:
            wanted = numpy.array(behind) + (numpy.array(drawn) - numpy.array(behind)) * (1 - amount)
            distance = (((self.palette - wanted) * (2, 3, 2)) ** 2).sum(axis=1)
            colour = next((tuple(int(value) for value in self.palette[i]) for i in distance.argsort(kind='stable')
                           if tuple(int(value) for value in self.palette[i]) != behind), behind)
            self.gentler[key] = (*colour, 255)
        return self.gentler[key]


def paler(behind, amount, palette):
    """The palette colour nearest to a few steps paler than behind, never behind itself."""
    wanted = numpy.minimum(255, numpy.array(behind) + amount)
    distance = (((palette - wanted) * (2, 3, 2)) ** 2).sum(axis=1)
    for index in distance.argsort(kind='stable'):
        colour = tuple(int(value) for value in palette[index])
        if colour != tuple(behind) and sum(colour) > sum(behind):
            return colour
    return tuple(behind)


@dataclass(frozen=True)
class Crack:
    """Where grit comes out of the underside of stone, and the floor it lands on."""

    x: int
    top: int
    bottom: int


def runs(picked, length, upward):
    """[y, x]: picked for all of the length rows above (upward) or from (not) each pixel."""
    count = numpy.zeros((picked.shape[0] + 1, picked.shape[1]), dtype=numpy.int32)
    count[1:] = numpy.cumsum(picked, axis=0)
    height = picked.shape[0]
    rows = numpy.arange(height)
    if upward:
        low, high = rows - length, rows
    else:
        low, high = rows, rows + length
    valid = (low >= 0) & (high <= height)
    low, high = low.clip(0, height), high.clip(0, height)
    return (count[high] - count[low] == length) & valid[:, None]


def grit_sources(air, clear, stone, terrain, room, rng):
    """Cracks in the undersides of stone with open air below and a floor to land on."""
    candidates = (runs(stone, GRIT_STONE_ABOVE, True) & runs(clear, GRIT_CLEAR_BELOW, False))
    candidates[1:] &= ~air[:-1]
    candidates[:3] = False
    candidates[HEIGHT - GRIT_SHORTEST_FALL:] = False
    found = []
    for x in range(10, WIDTH - 10, 2):
        for y in numpy.nonzero(candidates[:, x])[0]:
            y = int(y)
            # Only from the underside of a block or a ledge, not from a door's arch or
            # a carving painted on the wall.
            above = (y - 1 - 5) // TILE_HEIGHT
            if not 0 <= above < 3:
                continue
            kind = terrain.tile(room, x // TILE_WIDTH, above).kind
            if kind in EMPTY_TILES or kind in GRIT_NOT_FROM or (above + 1) * TILE_HEIGHT + 5 - y > GRIT_UNDERSIDE:
                continue
            ground = landing(terrain, room, x, y)
            if ground is None or ground - y < GRIT_SHORTEST_FALL:
                continue
            path = clear[y:ground - FLOOR_STRIP, x]
            if path.size and path.mean() >= GRIT_PATH_CLEAR:
                found.append(Crack(x, y, ground + rng.randint(*LANDING_DEPTH)))
    rng.shuffle(found)
    chosen = []
    for crack in found:
        if len(chosen) < MOST_GRIT and all(abs(crack.x - other.x) >= GRIT_APART for other in chosen):
            chosen.append(crack)
    return tuple(sorted(chosen, key=lambda crack: crack.x))


def ceilings(air, clear, stone, terrain, room):
    """For each of the three ceilings, [x] the y grit leaves its underside at, or -1."""
    leaves = numpy.zeros_like(stone)
    leaves[1:] = stone[:-1] & ~air[:-1] & runs(clear, CEILING_CLEAR, False)[1:]
    found = []
    for c in range(3):
        line = [-1] * WIDTH
        top = max(1, c * TILE_HEIGHT + 5 - CEILING_ABOVE)
        bottom = min(HEIGHT - 6, c * TILE_HEIGHT + 5 + CEILING_BELOW)
        for x in range(WIDTH):
            if c > 0:
                kind = terrain.tile(room, x // TILE_WIDTH, c - 1).kind
                if kind in EMPTY_TILES or kind in GRIT_NOT_FROM:
                    continue
            # The lowest underside in reach.
            hits = numpy.nonzero(leaves[top:bottom + 1, x])[0]
            if len(hits):
                line[x] = top + int(hits[-1])
        found.append(tuple(line))
    return tuple(found)


@dataclass(frozen=True, eq=False)
class Rock:
    """A patch of the plain that is not sand: its foot (its lowest y in each column) and
    its pixels."""

    foot: dict
    mask: numpy.ndarray
    size: int

    @property
    def left(self):
        return min(self.foot)


@dataclass(frozen=True, eq=False)
class Dunes:
    """[x] the near dune's crest; where the plain starts; [y, x] of its sand, of the sand
    the wind lifts (out of the rocks' lee), and its rocks."""

    crest: numpy.ndarray
    ground_top: int
    sand: numpy.ndarray
    open_sand: numpy.ndarray
    rocks: tuple


def crest_line(sand):
    """[x] the top of the near dune: its first run of solid sand, or -1."""
    solid = runs(sand, CREST_SOLID, False)
    solid[HEIGHT - CREST_SOLID:] = False
    found = solid.any(axis=0)
    return numpy.where(found, solid.argmax(axis=0), -1)


def find_rocks(sand, top):
    """Every patch of the plain below top that is not sand."""
    solid = ~sand
    solid[:top] = False
    seen = numpy.zeros_like(solid)
    rocks = []
    for y0, x0 in zip(*numpy.nonzero(solid)):
        if seen[y0, x0]:
            continue
        queue, pixels = deque([(int(y0), int(x0))]), []
        seen[y0, x0] = True
        while queue:
            y, x = queue.popleft()
            pixels.append((y, x))
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < HEIGHT and 0 <= nx < WIDTH and solid[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    queue.append((ny, nx))
        if len(pixels) >= SMALLEST_ROCK:
            foot = {}
            for y, x in pixels:
                foot[x] = max(foot.get(x, 0), y)
            mask = numpy.zeros_like(solid)
            ys, xs = zip(*pixels)
            mask[list(ys), list(xs)] = True
            rocks.append(Rock(foot, mask, len(pixels)))
    return tuple(rocks)


def shelter(rocks):
    """[y, x] the still ground downwind of each rock, a rock's width long."""
    still = numpy.zeros((HEIGHT, WIDTH), dtype=bool)
    for rock in rocks:
        left, right = min(rock.foot), max(rock.foot)
        base = max(rock.foot.values())
        still[max(0, base - 8):base + 4, right + 1:min(WIDTH, right + 1 + (right - left))] = True
    return still


def read_dunes(sand):
    """The desert's dunes, or None where the sand is not a plain of dunes under a crest."""
    crest = crest_line(sand)
    if (crest < 0).any() or crest.max() - crest.min() > DUNE_CREST_SPREAD:
        return None
    ground_top = int(crest.max()) + GROUND_FROM
    rocks = find_rocks(sand, ground_top)
    return Dunes(crest, ground_top, sand, sand & ~shelter(rocks), rocks)


def read_room(level_number, room, rgb, palette, covered=None, terrain=None, painted=False):
    """The air of a room from an RGB picture of its scenery, its palette, [y, x] of what
    its foreground covers and its tiles; a painted room sheds no grit."""
    sky, blue = sky_mask(rgb), blueness(rgb)
    open_sky = float(sky.mean())
    sand = sand_mask(rgb)
    desert = bool(open_sky >= DESERT_SKY and sand.mean() >= DESERT_SAND)
    seed = level_number * 100 + room
    if desert:
        stars = place_desert_stars(sky, random.Random(seed + 41))
    else:
        stars = warm_some(place_stars(sky, blue, random.Random(seed)), random.Random(seed + 7))
        stars += place_haze_stars(sky, blue, stars, random.Random(seed + 13))
    luminance = numpy.asarray(Image.fromarray(numpy.ascontiguousarray(rgb, dtype=numpy.uint8)).convert('L'))
    grit = lines = ()
    if terrain is not None and not painted:
        air = numpy.frombuffer(open_air(luminance, terrain, room), dtype=numpy.uint8).reshape(HEIGHT, WIDTH) != 0
        clear = air if covered is None else air & ~covered
        stone = luminance >= TIP_LUMINANCE
        grit = grit_sources(air, clear, stone, terrain, room, random.Random(seed))
        lines = ceilings(air, clear, stone, terrain, room)
    return RuinsAir(sky, blue, tuple(stars), nearest_colours(palette, INK_COLOURS), desert,
                    windy=open_sky >= OPEN_SKY and not desert, covered=covered, palette=palette_rgb(palette),
                    grit=grit, ceilings=lines, luminance=luminance, dunes=read_dunes(sand) if desert else None,
                    palette_key=tuple(sorted(palette.items())))


def ruins_air(level_number, room, art, terrain=None, raised=None):
    """The air of a room as the game draws it (terrain and raised as in room_air)."""
    from pop2.caverns import customized_rooms, room_assets

    palette = room_assets(level_number, room)[2]
    rgb = numpy.asarray(Image.alpha_composite(art.background, art.foreground).convert('RGB'))
    covered = numpy.asarray(art.foreground.getchannel('A')) > 0
    return read_room(level_number, room, rgb, palette, covered, terrain, room in customized_rooms(level_number))


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
    """(x, y, dx, dy) of a shooting star whose whole flight is over the sky, the deep blue
    or the purple, or None. None crosses the desert's sky, as its approved look had it."""
    if air.desert:
        return None
    ys, xs = numpy.nonzero(air.sky[:, SHOOTER_LEFT:WIDTH - SHOOTER_LEFT])
    if not len(xs):
        return None
    travel = kind.speed * kind.ticks
    for _ in range(SHOOTER_TRIES):
        angle = math.radians(rng.uniform(*kind.angle))
        side = rng.choice((1, -1))
        dx, dy = side * math.cos(angle), math.sin(angle)
        i = rng.randrange(len(xs))
        x, y = float(xs[i] + SHOOTER_LEFT), float(ys[i])
        ends = [(x + dx * travel * share, y + dy * travel * share) for share in (0, 0.25, 0.5, 0.75, 1)]
        if all(0 <= ex < WIDTH and 0 <= ey < HEIGHT and air.sky[int(ey), int(ex)] for ex, ey in ends):
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
class Grain:
    y: float
    speed: float
    x: float
    shade: tuple
    wind: float = 0.0
    size: str = 'speck'
    turn: int = 0
    spin: int = 1


@dataclass
class Mound:
    """A pour's heap: its heights, the grains rolling down it to their place, and how
    long it stays once the pour is over (None while it runs)."""

    x: int
    bottom: int
    heights: list = field(default_factory=lambda: [0] * len(MOUND))
    rolling: list = field(default_factory=list)
    stays: int | None = None
    wear: int = 0


@dataclass
class Trickle:
    source: Crack
    wait: int
    left: int
    pour: bool = False
    gap: int = 0
    grains: list = field(default_factory=list)
    shaken: bool = False
    crumbled: bool = False
    released: int = 0
    mound: Mound | None = None
    # The row of the tile it comes out from under (-1: the room above's floor).
    stone: int | None = None

    @property
    def running(self):
        return self.wait > 0 or self.left > 0


@dataclass
class Pebble:
    x: float
    y: float
    bottom: int
    wait: int
    vx: float = 0.0
    vy: float = 0.3
    bounced: bool = False
    rest: int = 0


@dataclass
class Bit:
    """A bit of grit thrown off the Prince, drawn over him."""

    x: float
    y: float
    dx: float
    dy: float
    shade: tuple
    floor: int
    bounces: int = 0
    age: int = 0


def tangents(pixels):
    found = []
    for i in range(len(pixels)):
        (ax, ay), (bx, by) = pixels[max(0, i - 2)], pixels[min(len(pixels) - 1, i + 2)]
        length = math.hypot(bx - ax, by - ay) or 1.0
        found.append(((bx - ax) / length, (by - ay) / length))
    return found


@dataclass
class Blown:
    """A grain of blown sand: where it is, where it left the ground, how near the bottom of
    the room (0-1), its flight, and whether a rock kicked it up."""

    x: float
    y: float
    start: float
    near: float
    dx: float
    dy: float
    settle: float
    life: int
    age: int = 0
    bounced: bool = False


@dataclass
class Gust:
    """One gust over the dunes: when and where its front came down, how far it runs, how
    fast, how strong, what it blows sand off, and the phase of its stronger and weaker
    stretches."""

    born: int
    start: float
    reach: float
    speed: float
    strength: float
    crest: bool = True
    plain: bool = True
    phase: float = 0.0

    def run(self, tick, speed):
        """How far its front has gone at this speed (the crest's or the plain's)."""
        return (tick - self.born) * speed * self.speed / CREST_FRONT

    def over(self, tick):
        return self.run(tick, GROUND_FRONT) > self.reach or self.start + self.run(tick, CREST_FRONT) > WIDTH + 45

    def strength_at(self, run):
        """Its strength where its front has run this far: rising, gusting and dying away."""
        if run < 0 or run > self.reach:
            return 0.0
        rise = min(1.0, run / GUST_RISE)
        dies = min(1.0, (self.reach - run) / (GUST_DIES * self.reach))
        gusting = 0.8 + 0.3 * math.sin(run / 37 + self.phase) * math.sin(run / 89 + 2 * self.phase)
        return self.strength * min(rise, dies) * gusting


def some(rng, counts, strength):
    """A count from the range, at this strength, the fraction left to chance."""
    wanted = rng.randint(*counts) * strength
    return int(wanted) + (rng.random() < wanted % 1)


@dataclass
class Stream:
    born: int
    near: float
    y: int
    x: float
    speed: float
    travel: float
    phase: float


@dataclass
class Whirl:
    """A grain of the dust devil: round it, up it, and once off its top, flung away."""

    angle: float
    spin: float
    climb: float
    wobble: float
    height: float = 0.0
    flung: Blown | None = None


@dataclass
class Kick:
    """A grain circling a devil's foot just above the sand."""

    angle: float
    spin: float
    radius: float
    hop: float
    life: int
    age: int = 0


@dataclass
class Thrown:
    """A grain a devil's foot threw out along the crest, falling back to the sand."""

    x: float
    y: float
    ground: float
    dx: float
    dy: float
    age: int = 0


@dataclass
class Devil:
    """A dust devil. Its defaults are the one devil there used to be; `new_devil` gives
    each its own."""

    born: int
    start: float
    grains: list = field(default_factory=list)
    life: int = DEVIL_LIFE
    drift: float = DEVIL_DRIFT
    wander: float = 0.0
    wander_ticks: float = 50.0
    height: float = HEIGHT_OF_DEVIL
    top: float = TOP_RADIUS
    lean: float = LEAN
    grain_count: float = DEVIL_GRAINS
    sway_speed: float = 0.25
    sway: float = 1.5
    pulse: float = 0.0
    pulse_ticks: float = 20.0
    phase: float = 0.0
    foot: float = 0.0
    kicks: list = field(default_factory=list)
    thrown: list = field(default_factory=list)
    next_spray: int = 0

    def strength(self, tick):
        age = tick - self.born
        if age < 0 or age >= self.life:
            return 0.0
        rise = min(1.0, age / DEVIL_RISE, (self.life - age) / DEVIL_FADE)
        return rise * (1.0 - self.pulse * (0.5 + 0.5 * math.sin(age / self.pulse_ticks + self.phase)))

    def reach(self):
        """How far from its start it can be, either way."""
        return -self.wander, self.drift * self.life + self.wander

    def base(self, tick, crest):
        """Its foot: drifting downwind on the crest smoothed, so that a dip in the
        crest does not trip it, wandering to and fro a little as it goes."""
        age = max(0, tick - self.born)
        x = self.start + self.drift * age + self.wander * math.sin(age / self.wander_ticks + self.phase)
        part = crest[max(0, int(x) - DEVIL_SMOOTH):int(x) + DEVIL_SMOOTH + 1]
        part = part[part > 0]
        if not len(part):
            part = crest[crest > 0]
        return x, int(round(float(numpy.median(part)))) + DEVIL_FOOT

    def kick_point(self, kick, base_x, base_y):
        hop = kick.hop * math.sin(math.pi * kick.age / kick.life)
        return (base_x + kick.radius * math.cos(kick.angle),
                base_y + 0.2 * kick.radius * math.sin(kick.angle) - hop)

    def point(self, grain, tick, base_x, base_y):
        share = min(1.0, grain.height / self.height)
        radius = 1.0 + self.top * share ** 1.3 + grain.wobble
        middle = (base_x + self.lean * share ** 1.5
                  + self.sway * math.sin(tick * self.sway_speed + grain.height * 0.22 + self.phase))
        # Seen a little from above: the near side of the circle a pixel lower than the far.
        return (middle + radius * math.cos(grain.angle),
                base_y - grain.height + 0.3 * radius * math.sin(grain.angle))


def between(pair, near):
    (a, b), (c, d) = pair
    return a + (c - a) * near, b + (d - b) * near


def stone_row(top):
    """The row of the tile a crack at top is in the underside of, as the cracks are found."""
    return (int(top) - 1 - 5) // TILE_HEIGHT


def row_of(floor):
    return max(0, min(2, round((floor - floor_y(0)) / TILE_HEIGHT)))


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
    trickles: list = field(default_factory=list)
    mounds: list = field(default_factory=list)
    pebbles: list = field(default_factory=list)
    flecks: list = field(default_factory=list)
    bits: list = field(default_factory=list)
    quiet_wait: int = 0
    footing: object = None
    # [y, x] of the Prince as last drawn, and the frame just before the actors.
    prince_mask: numpy.ndarray | None = None
    before_actors: Image.Image | None = None
    # The desert's gusts (the ticks they began), its sand and its dust devil.
    desert_gusts: list = field(default_factory=list)
    desert_gust_wait: int = 0
    spray: list = field(default_factory=list)
    blown: list = field(default_factory=list)
    streams: list = field(default_factory=list)
    devil: Devil | None = None
    devil_wait: int = 0
    dune_origin: int | None = None
    # The puffs of dust from the floor.
    clouds: list = field(default_factory=list)
    tick: int = 0

    def __post_init__(self):
        self.twinkles = [[0, 0] for _ in self.air.stars]
        self.shooter_wait = self.rng.randint(*FIRST_SHOOTER)
        self.gust_wait = self.rng.randint(*TICKS_BETWEEN_GUSTS)
        self.quiet_wait = self.rng.randint(*TICKS_BETWEEN_TRICKLES)
        self.desert_gust_wait = self.rng.randint(*FIRST_DESERT_GUST)
        self.devil_wait = self.rng.randint(*FIRST_DEVIL)

    def see_gates(self, art):
        """The caves' torches watch the gates; nothing here does."""

    def advance(self, terrain=None, footing=None, thuds=(), shakes=()):
        """One game tick. shakes: (room, 'bump' or 'stamp', row) of the Prince's own
        blows on the ceiling and the floor this tick."""
        self.tick += 1
        self.twinkle()
        self.advance_shooter()
        last = self.footing
        blows = self.hits(footing, thuds, shakes)
        self.puff(last, footing, thuds)
        self.advance_flecks()
        # One blow in a place a tick: a stamp on landing is one shake, not two.
        done = []
        for x, row, strength, name in sorted(blows, key=lambda blow: -blow[2]):
            if all(abs(x - other) > ONE_BLOW_APART or row != other_row for other, other_row in done):
                done.append((x, row))
                self.shake(x, row, strength, name, terrain)
        self.quiet_trickle(terrain)
        self.blow()
        self.advance_trickles(terrain)
        self.advance_mounds(terrain)
        self.advance_pebbles()
        self.advance_bits()
        self.advance_streaks()
        self.advance_clouds()
        if self.air.dunes is not None:
            self.advance_desert()

    # The puffs

    def puff(self, last, footing, thuds):
        """The puffs his feet and whatever came down raise this tick."""
        raised = list(thuds)
        if last is not None and footing is not None:
            raised += footfalls(last, footing)
        for thud in raised:
            cloud = Cloud(thud, self.rng)
            # Off the side of the screen there is nothing to show.
            if len(self.clouds) < MOST_CLOUDS and cloud.right - cloud.left >= 3 and cloud.bottom - cloud.top >= 3:
                self.clouds.append(cloud)

    def advance_clouds(self):
        for cloud in self.clouds:
            cloud.advance()
        self.clouds = [cloud for cloud in self.clouds if len(cloud.x)]

    def draw_cloud(self, frame, cloud, colours):
        """A few hard shades over what is behind it, each pixel landing on the palette.
        Unlike the caves', each step is worked out from what is behind it a few pixels
        round, not from the pixel itself: over the speckled floors of the ruins the
        pixel's own colour left the puff as speckles again, which hid it."""
        box = cloud.left, cloud.top, cloud.right, cloud.bottom
        pixels = numpy.array(frame.crop(box))
        shown = pixels[..., :3].astype(numpy.int32)
        steps = numpy.digitize(cloud.thickness() + cloud.grain * CLOUD_CRUMBLE, CLOUD_STEPS)
        amount = cloud.kind.most * numpy.array((0, *(share for _, share in PUFF_SHADES)))[steps]
        if self.air.covered is not None:
            amount[self.air.covered[cloud.top:cloud.bottom, cloud.left:cloud.right]] = 0
        if cloud.hidden is not None:
            amount[cloud.hidden] = 0
        behind = around(frame, box, PUFF_BEHIND)
        shades = numpy.array([(0, 0, 0)] + [colour for colour, _ in PUFF_SHADES], dtype=numpy.int32)
        paler = numpy.maximum(shades[steps], behind + CLOUD_PALER)
        wanted = (behind + (paler - behind) * amount[..., None]).clip(0, 255).astype(numpy.int32)
        flat = colours.cube_colours[(wanted[..., 0] >> 3) << 10 | (wanted[..., 1] >> 3) << 5 | wanted[..., 2] >> 3]
        pixels[..., :3] = numpy.where((amount > 0)[..., None], flat, shown)
        frame.paste(Image.fromarray(pixels), box[:2])

    # The grit

    def hits(self, footing, thuds, shakes):
        """(x, row, strength, name) of what hit the ceilings or the floor this tick."""
        last, self.footing = self.footing, footing
        blows = []
        if last is not None and footing is not None and last.falling and not footing.falling:
            if last.speed >= HARD_LANDING:
                blows.append((footing.foot, row_of(footing.floor), min(1.0, last.speed / (2 * HARD_LANDING)),
                              'landing'))
        for thud in thuds:
            for name, kind in (('slam', SLAM_PUFF), ('tile', TILE_PUFF), ('shut', SHUT_PUFF)):
                if thud.kind is kind:
                    blows.append(((thud.left + thud.right) / 2, row_of(thud.left_floor), STRENGTH[name], name))
        for room, name, row in shakes:
            if room == self.room:
                where = footing.foot if footing is not None else WIDTH / 2
                blows.append((where, row, STRENGTH[name], name))
        return blows

    def stands(self, terrain, x, row):
        """Whether the tile over x in row (-1: the room above's floor) is still there: a
        loose floor that has fallen sheds no more grit, from the hole it left."""
        if terrain is None or row is None:
            return True
        column = int(x) // TILE_WIDTH
        if not 0 <= column < 10 or row > 2:
            return True
        if row < 0:
            # The underside of the room above's floor.
            above = terrain.neighbor(self.room, 'up')
            if above is None:
                return True
            return terrain.tile(above, column, 2).kind not in EMPTY_TILES
        return terrain.tile(self.room, column, row).kind not in EMPTY_TILES

    def floor_stands(self, terrain, x, bottom):
        """Whether the floor something lies on at bottom is still there."""
        if terrain is None or not 0 <= int(x) < WIDTH:
            return True
        return terrain.tile(self.room, int(x) // TILE_WIDTH, row_of(bottom)).kind not in EMPTY_TILES

    def busy(self, x, pour=True):
        """Whether a crack near x is pouring, or for a new pour, running at all."""
        return any(abs(trickle.source.x - x) <= SAME_CRACK and trickle.running and (pour or trickle.pour)
                   for trickle in self.trickles)

    def start(self, x, top, grains, wait, pour=False, terrain=None, stone=None):
        stone = stone_row(top) if stone is None else stone
        if self.busy(x, pour) or not self.stands(terrain, x, stone):
            return
        ground = landing(terrain, self.room, int(x), top) if terrain is not None else None
        bottom = HEIGHT if ground is None else ground + self.rng.randint(*LANDING_DEPTH)
        self.trickles.append(Trickle(Crack(int(x), top, bottom), wait, grains, pour, stone=stone))

    def shake(self, x, row, strength, name, terrain):
        """Grit shaken down from the ceilings, most near the blow, a little further off a
        few ticks later; a strong blow brings down a pebble or two."""
        rng, lines = self.rng, self.air.ceilings
        if not lines:
            return
        before = len(self.trickles)
        spots = 0
        if name == 'bump':
            # Right over his hands, at once.
            line = lines[row]
            near = [c for c in range(max(0, int(x) - BUMP_REACH), min(WIDTH, int(x) + BUMP_REACH + 1))
                    if line[c] >= 0]
            for c in rng.sample(near, min(len(near), rng.randint(*BUMP_SPOTS))):
                self.start(c, line[c], rng.randint(*BUMP_GRAINS), rng.randint(0, 2), terrain=terrain, stone=row - 1)
                spots += 1
        candidates = []
        for c, line in enumerate(lines):
            for column in range(rng.randrange(SHAKE_EVERY), WIDTH, SHAKE_EVERY):
                if line[column] < 0:
                    continue
                distance = math.hypot(column - x, (c - row) * TILE_HEIGHT * 0.7)
                chance = strength * math.exp(-distance / SHAKE_REACH)
                if rng.random() < chance and self.stands(terrain, column, c - 1):
                    candidates.append((distance, column, line[column], chance, c - 1))
        candidates.sort()
        for distance, column, top, chance, stone in candidates[:MOST_SPOTS - spots]:
            grains = 1 + int(5 * chance * rng.random() + 2 * chance)
            self.start(column + rng.randint(-3, 3), top, grains, int(distance / SHAKE_SPREAD) + rng.randint(0, 3),
                       terrain=terrain, stone=stone)
        for trickle in self.trickles[before:]:
            trickle.shaken = True
        if strength < PEBBLE_FROM:
            return
        near = self.trickles[before:before + 4]
        for trickle in rng.sample(near, min(len(near), rng.randint(*PEBBLES))):
            source = trickle.source
            self.pebbles.append(Pebble(float(source.x), float(source.top), source.bottom,
                                       trickle.wait + rng.randint(0, 3)))

    def quiet_trickle(self, terrain):
        """The room's own rhythm: now a sprinkle, now a pour, from one of its cracks."""
        rng, sources = self.rng, self.air.grit
        self.quiet_wait -= 1
        if not sources or self.quiet_wait > 0:
            return
        self.quiet_wait = rng.randint(*TICKS_BETWEEN_TRICKLES)
        sources = [crack for crack in sources if self.stands(terrain, crack.x, stone_row(crack.top))]
        if not sources:
            return
        source = rng.choice([crack for crack in sources if not self.busy(crack.x)] or sources)
        pour = rng.random() < POUR_CHANCE
        self.start(source.x, source.top, rng.randint(*(POUR if pour else SPRINKLE)), 0, pour, terrain)

    def release(self, trickle):
        """The next grain out of a crack."""
        rng, source = self.rng, trickle.source
        if not trickle.grains and not trickle.crumbled:
            # Pixels come away from the underside first: one, or a few when shaken.
            trickle.crumbled = True
            for offset in rng.sample((-1, 0, 1), 3 if trickle.shaken else 1):
                self.flecks.append(Fleck(source.x + offset, source.top, 0.0, 0.0, 0.0, (GRIT_DIM,),
                                         rng.randint(2, 3), HEIGHT))
        trickle.left -= 1
        trickle.released += 1
        if trickle.pour:
            # Straight down from the crack, thinner at its start and end.
            trickle.gap = 1 if trickle.released < POUR_THIN_START or trickle.left < POUR_THIN_END else 0
            x, shade, size = source.x, GRIT_HEAD, 'speck'
        else:
            trickle.gap = rng.randint(*SPRINKLE_GAP)
            x = source.x + (rng.random() < 0.25) * rng.choice((-1, 1))
            shade = rng.choice(HEADS)
            size = rng.choices([name for name, _ in SIZES], [share for _, share in SIZES])[0]
        trickle.grains.append(Grain(float(source.top), 0.3, float(x), shade, 0.0, size, rng.randrange(4),
                                    rng.choice((-1, 1))))

    def advance_trickles(self, terrain=None):
        kept = []
        for trickle in self.trickles:
            source, mound = trickle.source, trickle.mound
            if trickle.left > 0 and not self.stands(terrain, source.x, trickle.stone):
                # Its stone fell: what is already falling goes on down, and no more.
                trickle.left = trickle.wait = 0
            if trickle.wait > 0:
                trickle.wait -= 1
            elif trickle.left > 0:
                if trickle.gap > 0:
                    trickle.gap -= 1
                else:
                    self.release(trickle)
            grains = []
            for grain in trickle.grains:
                was = grain.y
                # A streak passing by carries the grain along its way, up in its curl.
                push_x, push_y = self.streak_push(grain.x, grain.y)
                grain.speed = min(GRIT_FASTEST, grain.speed + GRIT_GRAVITY + push_y * STREAK_LIFT)
                grain.y += grain.speed
                grain.wind += (push_x - grain.wind) * STREAK_TAKE
                grain.x += grain.wind
                hit = self.on_prince(int(grain.x), was, grain.y)
                if hit is not None:
                    self.bounce_off(grain.x, hit - 1, grain.shade, source.bottom)
                    continue
                bottom = source.bottom
                if mound is not None:
                    # On top of the mound, where it has grown under the thread.
                    column = int(grain.x) - mound.x + len(MOUND) // 2
                    if 0 <= column < len(MOUND):
                        bottom -= mound.heights[column]
                if grain.y < bottom:
                    grains.append(grain)
                else:
                    self.land(grain.x, bottom, trickle.pour, trickle)
                    if grain.size == 'crumb':
                        # It breaks in two.
                        self.land(grain.x + 1, bottom, False)
            trickle.grains = grains
            if trickle.running or trickle.grains:
                kept.append(trickle)
            elif trickle.mound is not None:
                trickle.mound.stays = self.rng.randint(*MOUND_STAYS)
        self.trickles = kept

    def heap(self, trickle, x):
        """A grain of a pour settles on its mound, rolling off a side that is full."""
        mound = trickle.mound
        if mound is None:
            mound = trickle.mound = Mound(int(x), trickle.source.bottom)
            self.mounds.append(mound)
        rng, heights, middle = self.rng, mound.heights, len(MOUND) // 2
        c = max(0, min(len(MOUND) - 1, middle + round(rng.gauss(0, 1.2))))
        for _ in range(len(MOUND)):
            if heights[c] + sum(1 for target, _ in mound.rolling if target == c) < MOUND[c]:
                # It lands on the top and rolls down to its place.
                mound.rolling.append([c, middle])
                return True
            c = max(0, min(len(MOUND) - 1, c + rng.choice((-1, 1))))
        return False

    def land(self, x, bottom, pour, trickle=None):
        rng = self.rng
        if bottom >= HEIGHT:
            return
        if pour and trickle is not None and rng.random() < HEAP_CHANCE and self.heap(trickle, x):
            return
        if rng.random() < (POUR_SPLASH_CHANCE if pour else SPLASH_CHANCE):
            for _ in range(rng.randint(*SPLASH_BITS)):
                self.flecks.append(Fleck(x, bottom - 1, rng.choice((-1, 1)) * rng.uniform(*SPLASH_SIDE),
                                         -rng.uniform(*SPLASH_LIFT), SPLASH_PULL, (GRIT_HEAD, GRIT_TAIL),
                                         rng.randint(*SPLASH_LIFE), bottom))
        if rng.random() < (POUR_REST_CHANCE if pour else REST_CHANCE):
            self.flecks.append(Fleck(x + rng.choice((-1, 0, 0, 1)), bottom - rng.randint(0, 2), 0.0, 0.0, 0.0,
                                     (GRIT_TAIL, GRIT_DIM), rng.randint(*REST_LIFE), HEIGHT))

    def advance_mounds(self, terrain=None):
        rng, kept = self.rng, []
        for mound in self.mounds:
            if not self.floor_stands(terrain, mound.x, mound.bottom):
                # The floor it lay on fell.
                continue
            for roller in list(mound.rolling):
                target, place = roller
                if place == target:
                    mound.heights[target] += 1
                    mound.rolling.remove(roller)
                else:
                    roller[1] += 1 if target > place else -1
            if mound.rolling:
                kept.append(mound)
                continue
            if mound.stays is not None:
                if mound.stays > 0:
                    mound.stays -= 1
                elif mound.wear > 0:
                    mound.wear -= 1
                else:
                    # The wind takes a grain off the top.
                    tallest = max(mound.heights)
                    c = rng.choice([i for i, height in enumerate(mound.heights) if height == tallest])
                    mound.heights[c] -= 1
                    mound.wear = rng.randint(*MOUND_WEARS)
            if any(mound.heights):
                kept.append(mound)
        self.mounds = kept

    def advance_pebbles(self):
        rng, kept = self.rng, []
        for pebble in self.pebbles:
            if pebble.wait > 0:
                pebble.wait -= 1
                kept.append(pebble)
                continue
            if pebble.rest:
                pebble.rest -= 1
                if pebble.rest:
                    kept.append(pebble)
                continue
            pebble.vy = min(PEBBLE_FASTEST, pebble.vy + PEBBLE_GRAVITY)
            pebble.y += pebble.vy
            pebble.x += pebble.vx
            if pebble.y >= pebble.bottom:
                if pebble.bottom >= HEIGHT:
                    continue
                pebble.y = pebble.bottom - 1
                if not pebble.bounced:
                    pebble.bounced = True
                    pebble.vy = -pebble.vy * PEBBLE_BOUNCE
                    pebble.vx = rng.choice((-1, 1)) * rng.uniform(0.5, 1.0)
                else:
                    pebble.vx = pebble.vy = 0.0
                    pebble.rest = rng.randint(*PEBBLE_REST)
            kept.append(pebble)
        self.pebbles = kept

    def advance_flecks(self):
        kept = []
        for fleck in self.flecks:
            fleck.age += 1
            fleck.x += fleck.dx
            fleck.y += fleck.dy
            fleck.dy += fleck.pull
            if fleck.age < fleck.life and fleck.y <= fleck.floor:
                kept.append(fleck)
        self.flecks = kept

    # Grit on the Prince

    def on_prince(self, x, was, now):
        """The first row of the Prince a grain falling from was to now meets, or None."""
        mask = self.prince_mask
        if mask is None or not 0 <= x < WIDTH:
            return None
        for y in range(max(0, int(was) + 1), min(HEIGHT, int(now) + 1)):
            if mask[y, x]:
                return y
        return None

    def bounce_off(self, x, y, shade, floor):
        rng = self.rng
        self.bits.append(Bit(float(x), float(y), rng.choice((-1, 1)) * rng.uniform(*OFF_SIDE), -rng.uniform(*OFF_UP),
                             shade, floor))

    def advance_bits(self):
        rng, kept = self.rng, []
        for bit in self.bits:
            was = bit.y
            bit.dy += OFF_PULL
            bit.x += bit.dx
            bit.y += bit.dy
            hit = self.on_prince(int(bit.x), was, bit.y) if bit.dy > 0 else None
            if hit is not None and bit.bounces < OFF_BOUNCES:
                # Again, off a shoulder or an arm, with less to it.
                bit.bounces += 1
                bit.y = hit - 1
                bit.dy = -abs(bit.dy) * 0.35
                bit.dx = (bit.dx or rng.choice((-1, 1))) * 1.2
            if bit.y >= bit.floor:
                self.land(bit.x, bit.floor, False)
            elif bit.age < OFF_LIFE:
                bit.age += 1
                kept.append(bit)
        self.bits = kept

    def watches_the_prince(self):
        """Whether anything is falling that could land on him."""
        return bool(self.bits) or any(trickle.grains for trickle in self.trickles)

    def streak_push(self, x, y):
        """The push (x, y, pixels a tick) of the nearest streak showing within reach."""
        best, push = STREAK_REACH, (0.0, 0.0)
        for streak in self.streaks:
            showing = streak.showing()
            if not len(showing):
                continue
            if streak.tangents is None:
                streak.tangents = tangents(streak.pixels)
            for i in showing:
                px, py = streak.pixels[i]
                if abs(px - x) >= best or abs(py - y) >= best:
                    continue
                distance = math.hypot(px - x, py - y)
                if distance < best:
                    best = distance
                    tx, ty = streak.tangents[i]
                    strength = STREAK_PUSH * (1 - distance / STREAK_REACH)
                    push = tx * strength, ty * strength
        return push

    def grit_pixels(self):
        """(x, y, RGB) of the grit, its cracks and its mounds."""
        for fleck in self.flecks:
            yield (int(fleck.x), int(fleck.y),
                   fleck.inks[min(len(fleck.inks) - 1, fleck.age * len(fleck.inks) // fleck.life)])
        for trickle in self.trickles:
            source = trickle.source
            if trickle.wait == 0 and trickle.left > 0:
                # The crack the grit comes out of.
                yield source.x, source.top - 1, PEBBLE_DARK
                if trickle.pour and trickle.released > 1:
                    # The thread starts at the crack, not a row below it.
                    yield source.x, source.top, THREAD[(-self.tick) % len(THREAD)]
            previous = None
            for grain in trickle.grains:
                y, x = int(grain.y), int(round(grain.x))
                if (trickle.pour and previous is not None and 0 < previous[0] - y <= THREAD_GAP
                        and abs(previous[1] - x) <= 3):
                    # Join the thread up to the grain below, its dither running down; in the
                    # wind the two may be a pixel or two apart, so the join leans.
                    low_y, low_x = previous
                    for between in range(y + 1, low_y):
                        lean = round(x + (low_x - x) * (between - y) / (low_y - y))
                        yield lean, between, THREAD[(between - self.tick) % len(THREAD)]
                tails = TAILS.get(grain.shade, (GRIT_DIM, GRIT_DIM))
                if grain.size == 'speck':
                    yield x, y, grain.shade
                    for step in range(min(2, int(grain.speed // 2.5))):
                        yield x, y - 1 - step, tails[step]
                else:
                    turns = TURNS[grain.size]
                    cells = turns[(grain.turn + grain.spin * (self.tick // TUMBLE)) % len(turns)]
                    lit, middle, dark = SHADES.get(grain.shade, SHADES[GRIT_HEAD])
                    first = min(cells, key=lambda cell: (cell[1], cell[0]))
                    for cx, cy in cells:
                        yield x + cx, y + cy, lit if (cx, cy) == first else middle if cy == 0 else dark
                    if grain.speed >= 2.5:
                        # Falling fast: a pixel of its own dust above it.
                        yield x + first[0], y - 1, tails[1]
                previous = y, x
        middle = len(MOUND) // 2
        for mound in self.mounds:
            heights = mound.heights
            for c, height in enumerate(heights):
                for k in range(height):
                    if k == height - 1:
                        shade = GRIT_PALE if c <= middle else GRIT_HEAD
                    else:
                        shade = GRIT_HEAD if c < middle else GRIT_TAIL
                    yield mound.x + c - middle, mound.bottom - 1 - k, shade
                # The speckled floor swallows a mound of its own colours, so its shaded
                # right slope gets a dark edge, light coming from the upper left.
                lower = heights[c + 1] if c + 1 < len(heights) else 0
                if c >= middle:
                    for k in range(lower, height):
                        yield mound.x + c - middle + 1, mound.bottom - 1 - k, PEBBLE_DARK
            for _target, place in mound.rolling:
                yield mound.x + place - middle, mound.bottom - 1 - heights[place], GRIT_PALE
            # Its shadow, on the floor at the foot of the right slope.
            last = max((c for c, height in enumerate(heights) if height), default=None)
            if last is not None:
                yield mound.x + last - middle + 2, mound.bottom - 1, GRIT_DIM

    def pebble_pixels(self):
        for pebble in self.pebbles:
            if pebble.wait > 0:
                continue
            x, y = int(pebble.x), int(pebble.y)
            yield x, y - 1, GRIT_PALE
            yield x + 1, y - 1, GRIT_TAIL
            yield x, y, GRIT_TAIL
            yield x + 1, y, PEBBLE_DARK
            if pebble.vy > 4:
                yield x, y - 2, GRIT_DIM

    def put_grit(self, canvas, pixels):
        """Grit behind the foreground; over pale stone a step darker, so that it shows."""
        air, inks, luminance = self.air, self.air.inks, self.air.luminance
        for x, y, shade in pixels:
            if 0 <= x < WIDTH and 0 <= y < HEIGHT and not air.is_covered(x, y):
                if shade in ON_PALE and luminance is not None and luminance[y, x] >= PALE_STONE:
                    shade = ON_PALE[shade]
                canvas[x, y] = inks[shade]

    def over_actors(self, frame, player_bounds):
        """Where the Prince was drawn, for the grit to fall on, and the bits bouncing off
        him, drawn over him."""
        before = self.before_actors
        self.prince_mask = None
        if before is not None and player_bounds is not None:
            # His pixels: what the characters changed, within his bounds.
            left, top, right, bottom = (int(value) for value in player_bounds)
            box = (max(0, left - 4), max(0, top - 4), min(WIDTH, right + 5), min(HEIGHT, bottom + 2))
            if box[0] < box[2] and box[1] < box[3]:
                mask = numpy.zeros((HEIGHT, WIDTH), dtype=bool)
                mask[box[1]:box[3], box[0]:box[2]] = (numpy.asarray(frame.crop(box))
                                                      != numpy.asarray(before.crop(box))).any(axis=2)
                self.prince_mask = mask
        if not self.bits:
            return frame
        frame = frame.copy()
        canvas = frame.load()
        for bit in self.bits:
            x, y = int(bit.x), int(bit.y)
            if 0 <= x < WIDTH and 0 <= y < HEIGHT:
                canvas[x, y] = self.air.inks[bit.shade]
        return frame

    # The desert

    def advance_desert(self):
        rng, dunes, tick = self.rng, self.air.dunes, self.tick
        self.desert_gust_wait -= 1
        if self.desert_gust_wait <= 0:
            self.desert_gust_wait = rng.randint(*(GUST_SOON if rng.random() < SPELL_CHANCE else GUST_LULL))
            gust = self.new_gust()
            self.desert_gusts.append(gust)
            if gust.plain:
                for _ in range(some(rng, STREAMS, gust.strength)):
                    near = rng.random() ** 0.7
                    self.streams.append(Stream(tick + rng.randrange(STREAM_DELAY), near,
                                               int(dunes.ground_top + near * (HEIGHT - 6 - dunes.ground_top)),
                                               rng.uniform(gust.start - 20, gust.start + 0.4 * gust.reach),
                                               rng.uniform(*STREAM_FRONT),
                                               rng.uniform(*STREAM_TRAVEL) * min(1.0, gust.reach / 400),
                                               rng.uniform(0, 6.3)))
        self.desert_gusts = [gust for gust in self.desert_gusts if not gust.over(tick)]
        self.blow_the_crest()
        self.blow_the_plain()
        self.run_at_rocks()
        self.run_streams()
        self.advance_blown()
        self.advance_devil()

    def new_gust(self):
        rng = self.rng
        pick, share = rng.random(), 0.0
        for chance, crest, plain in GUST_KINDS:
            share += chance
            if pick < share:
                break
        start = GUST_FROM[0] + (GUST_FROM[1] - GUST_FROM[0]) * rng.random() ** 2
        return Gust(self.tick, start, rng.uniform(*GUST_REACH), rng.uniform(*GUST_SPEED),
                    rng.uniform(*GUST_STRENGTH), crest, plain, rng.uniform(0, 6.3))

    def fronts(self, speed, part, behind=-20, ahead=20):
        """(x, strength) of each gust's front blowing this part ('crest' or 'plain')."""
        for gust in self.desert_gusts:
            if not getattr(gust, part):
                continue
            run = gust.run(self.tick, speed)
            front = gust.start + run
            strength = gust.strength_at(run)
            if behind <= front <= WIDTH + ahead and strength > 0:
                yield front, strength

    def blow_the_crest(self):
        rng, crest = self.rng, self.air.dunes.crest
        for front, strength in self.fronts(CREST_FRONT, 'crest'):
            for _ in range(some(rng, CREST_GRAINS, strength)):
                x = int(front - rng.uniform(0, CREST_BEHIND))
                if 0 <= x < WIDTH and crest[x] > 0:
                    self.spray.append(Blown(float(x), float(crest[x] - 1), float(crest[x] - 1), 0.0,
                                            rng.uniform(*CREST_SPEED), -rng.uniform(*CREST_LIFT), CREST_SETTLE,
                                            rng.randint(*CREST_LIFE)))
        kept = []
        for grain in self.spray:
            grain.x += grain.dx
            grain.y += grain.dy
            grain.dy += grain.settle
            grain.dx *= CREST_DRAG
            grain.age += 1
            x = int(grain.x)
            # A grain that falls back onto the dune is gone.
            if grain.age < grain.life and 0 <= x < WIDTH and grain.y < crest[x]:
                kept.append(grain)
        self.spray = kept

    def blow_the_plain(self):
        rng, dunes = self.rng, self.air.dunes
        for front, strength in self.fronts(GROUND_FRONT, 'plain', ahead=40):
            for _ in range(some(rng, GROUND_GRAINS, strength)):
                x = int(front - rng.uniform(0, GROUND_REACH))
                y = int(dunes.ground_top + rng.random() ** 0.8 * (HEIGHT - 4 - dunes.ground_top))
                if not (0 <= x < WIDTH and 0 <= y < HEIGHT and dunes.open_sand[y, x]):
                    continue
                near = (y - dunes.ground_top) / (HEIGHT - dunes.ground_top)
                self.blown.append(Blown(float(x), float(y), float(y), near, rng.uniform(*between(GROUND_SPEED, near)),
                                        -rng.uniform(*between(GROUND_LIFT, near)), GROUND_SETTLE,
                                        rng.randint(*map(round, between(GROUND_LIFE, near)))))

    def run_at_rocks(self):
        """While a gust's front reaches a big rock, sand runs along the ground at its foot."""
        rng, dunes = self.rng, self.air.dunes
        fronts = tuple(self.fronts(GROUND_FRONT, 'plain', behind=-45, ahead=5))
        if not fronts:
            return
        for rock in dunes.rocks:
            if len(rock.foot) < 4 or rock.size < BIG_ROCK:
                continue
            left = rock.left
            for front, strength in fronts:
                if left - 45 <= front <= left + 5:
                    for _ in range(some(rng, AT_ROCK, strength)):
                        y = rock.foot.get(left + 2, rock.foot[left]) + rng.randint(-3, 2)
                        near = (y - dunes.ground_top) / (HEIGHT - dunes.ground_top)
                        self.blown.append(Blown(rng.uniform(left - 30, left - 3), float(y), float(y), near,
                                                rng.uniform(*between(GROUND_SPEED, near)),
                                                -rng.uniform(*between(GROUND_LIFT, near)) * 0.6, GROUND_SETTLE,
                                                rng.randint(8, 14)))

    def run_streams(self):
        rng, kept = self.rng, []
        for stream in self.streams:
            front = stream.x + (self.tick - stream.born) * stream.speed
            if front - stream.x > stream.travel:
                continue
            kept.append(stream)
            if self.tick < stream.born:
                continue
            for _ in range(rng.randint(*STREAM_GRAINS)):
                x = front - rng.uniform(0, 16)
                y = stream.y + round(math.sin(x / 23 + stream.phase))
                speed = tuple(far + near * stream.near for far, near in zip(STREAM_SPEED, STREAM_NEAR_SPEED))
                self.blown.append(Blown(x, float(y), float(y), stream.near, rng.uniform(*speed),
                                        -rng.uniform(*STREAM_LIFT), STREAM_SETTLE, rng.randint(*STREAM_LIFE)))
        self.streams = kept

    def rock_hit(self, x, y, ground):
        """The rock a grain riding at ground row `ground` runs into at (x, y), if any."""
        if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
            return None
        for rock in self.air.dunes.rocks:
            if rock.mask[y, x] and x in rock.foot and abs(rock.foot[x] - ground) <= FOOT_DEPTH:
                return rock
        return None

    def advance_blown(self):
        rng, rocks, kept = self.rng, self.air.dunes.rocks, []
        for grain in self.blown:
            nx, ny = grain.x + grain.dx, grain.y + grain.dy
            if not grain.bounced and self.rock_hit(int(nx), int(ny), int(grain.start)) is not None:
                # It runs into the rock: back off a little and up its face.
                grain.bounced = True
                grain.dx = -abs(grain.dx) * rng.uniform(*KICK_BACK)
                grain.dy = -rng.uniform(*KICK_UP)
                nx, ny = grain.x + grain.dx, grain.y + grain.dy
            grain.x, grain.y = nx, ny
            grain.dy += grain.settle
            if grain.bounced:
                # Kicked up, the wind takes it on again, over the rock if it rose high enough.
                grain.dx = min(grain.dx + 0.5, 2.5)
            else:
                grain.dx *= GROUND_DRAG
            grain.age += 1
            x, y = int(grain.x), int(grain.y)
            hidden = (grain.bounced and grain.age > 2 and 0 <= x < WIDTH and 0 <= y < HEIGHT
                      and any(rock.mask[y, x] for rock in rocks))
            landed = grain.y > grain.start + 0.5 and not grain.bounced
            if grain.age < grain.life and not landed and not hidden and 0 <= grain.x < WIDTH:
                kept.append(grain)
        self.blown = kept

    def new_devil(self):
        """A dust devil of its own shape, size, ways and life, not yet placed."""
        rng = self.rng
        return Devil(self.tick, 0.0, life=rng.randint(*DEVIL_LIVES), drift=rng.uniform(*DEVIL_DRIFTS),
                     wander=rng.uniform(*DEVIL_WANDER), wander_ticks=rng.uniform(*DEVIL_WANDER_TICKS),
                     height=rng.uniform(*DEVIL_HEIGHTS), top=rng.uniform(*DEVIL_TOPS),
                     lean=rng.uniform(*DEVIL_LEANS), grain_count=rng.uniform(*DEVIL_GRAIN_COUNTS),
                     sway_speed=rng.uniform(*DEVIL_SWAY_SPEEDS), sway=rng.uniform(*DEVIL_SWAYS),
                     pulse=rng.uniform(*DEVIL_PULSE), pulse_ticks=rng.uniform(*DEVIL_PULSE_TICKS),
                     phase=rng.uniform(0, 2 * math.pi), foot=rng.uniform(*FOOT_WIDTH))

    def devil_start(self, devil=None):
        """Where a dust devil can rise: with crest all along its way."""
        crest = self.air.dunes.crest
        behind, ahead = devil.reach() if devil is not None else (0.0, DEVIL_DRIFT * DEVIL_LIFE)
        for _ in range(20):
            x = self.rng.uniform(*DEVIL_FROM)
            way = crest[max(0, int(x + behind) - DEVIL_SMOOTH):int(x + ahead) + DEVIL_SMOOTH + 1]
            if len(way) and (way > 0).all():
                return x
        return None

    def advance_devil(self):
        rng, tick, crest = self.rng, self.tick, self.air.dunes.crest
        devil = self.devil
        if devil is None:
            self.devil_wait -= 1
            if self.devil_wait > 0:
                return
            self.devil_wait = rng.randint(*TICKS_BETWEEN_DEVILS)
            devil = self.new_devil()
            start = self.devil_start(devil)
            if start is None:
                return
            devil.start = start
            self.devil = devil
        strength = devil.strength(tick)
        base_x, base_y = devil.base(tick, crest)
        self.advance_foot(devil, strength, base_x, base_y)
        wanted = devil.grain_count * strength
        count = int(wanted) + (rng.random() < wanted % 1)
        for _ in range(count):
            devil.grains.append(Whirl(rng.uniform(0, 2 * math.pi), rng.uniform(*SPIN), rng.uniform(*CLIMB),
                                      rng.uniform(-0.6, 0.6)))
        kept = []
        for grain in devil.grains:
            flung = grain.flung
            if flung is not None:
                # Off the top: carried away downwind, sinking a little, for a few ticks.
                flung.x += flung.dx
                flung.y += flung.dy
                flung.dy += 0.05
                flung.age += 1
                if flung.age < flung.life:
                    kept.append(grain)
                continue
            grain.angle += grain.spin
            grain.height += grain.climb
            if grain.height >= devil.height * (0.8 + 0.2 * rng.random()):
                x, y = devil.point(grain, tick, base_x, base_y)
                grain.flung = Blown(x, y, y, 1.0, rng.uniform(1.0, 2.5), rng.uniform(-0.4, 0.1), 0.05,
                                    rng.randint(4, 9))
            kept.append(grain)
        devil.grains = kept
        if not kept and not devil.kicks and not devil.thrown and tick - devil.born >= devil.life:
            self.devil = None

    def advance_foot(self, devil, strength, base_x, base_y):
        """Twist a few grains around the foot and spray others to either side."""
        rng = self.rng
        if devil.foot > 0 and strength > 0:
            for _ in range(some(rng, FOOT_GRAINS, strength)):
                devil.kicks.append(Kick(rng.uniform(0, 2 * math.pi), rng.uniform(*FOOT_SPIN),
                                        rng.uniform(0.8, devil.foot), rng.uniform(*FOOT_HOP),
                                        rng.randint(*FOOT_LIFE)))
            if strength >= 0.5 and self.tick >= devil.next_spray:
                devil.next_spray = self.tick + rng.randint(*FOOT_SPRAY_TICKS)
                side = rng.choice((-1, 1))
                for _ in range(some(rng, FOOT_SPRAY_GRAINS, strength)):
                    devil.thrown.append(Thrown(base_x + side * rng.uniform(-1, 2), base_y - rng.uniform(0, 1.5),
                                               base_y, side * rng.uniform(*THROWN_DX), rng.uniform(*THROWN_DY)))
        kicks = []
        for kick in devil.kicks:
            kick.angle += kick.spin
            kick.age += 1
            if kick.age < kick.life:
                kicks.append(kick)
        devil.kicks = kicks
        thrown = []
        for grain in devil.thrown:
            grain.x += grain.dx
            grain.y += grain.dy
            grain.dy += THROWN_FALL
            grain.age += 1
            if grain.y < grain.ground + 1 and grain.age < 30:
                thrown.append(grain)
        devil.thrown = thrown

    def desert_pixels(self):
        """(x, y, RGB) of the blown sand, the later over the earlier."""
        dunes, tick = self.air.dunes, self.tick
        if self.dune_origin is not None:
            yield from self.breeze_pixels(dunes)
        devil = self.devil
        if devil is not None:
            base_x, base_y = devil.base(tick, dunes.crest)
            # Draw the far side first, including the grains circling the foot.
            for near in (False, True):
                for kick in devil.kicks:
                    if (math.sin(kick.angle) > 0) == near:
                        x, y = (int(round(value)) for value in devil.kick_point(kick, base_x, base_y))
                        yield x, y, NEAR_SANDS[0] if near else FAR_SIDE
                if near:
                    for grain in devil.thrown:
                        shade = FOOT_HIGHLIGHT if grain.age <= 6 else NEAR_SIDE
                        yield int(round(grain.x)), int(round(grain.y)), shade
                for grain in devil.grains:
                    if grain.flung is not None:
                        if near:
                            yield int(grain.flung.x), int(grain.flung.y), FLUNG
                        continue
                    if (math.sin(grain.angle) > 0) != near:
                        continue
                    x, y = (int(round(value)) for value in devil.point(grain, tick, base_x, base_y))
                    yield x, y, NEAR_SIDE if near else FAR_SIDE
        for grain in self.spray:
            x, y = int(grain.x), int(grain.y)
            step = min(2, grain.age * 3 // grain.life)
            yield x, y, SAND[step]
            if grain.dx > FAST_GRAIN and step < 2 and x > 0:
                yield x - 1, y, SAND[step + 1]
        sand = dunes.sand
        for grain in self.blown:
            if grain.bounced:
                continue
            x, y = int(grain.x), int(grain.y)
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT and sand[y, x]):
                continue
            steps = NEAR_SANDS if grain.near > 0.5 else FAR_SANDS
            step = min(2, grain.age * 3 // grain.life)
            yield x, y, steps[step]
            if grain.dx > FAST_GRAIN and step < 2 and x > 0 and sand[y, x - 1]:
                yield x - 1, y, steps[step + 1]
        for grain in self.blown:
            if grain.bounced:
                yield int(grain.x), int(grain.y), NEAR_SANDS[min(2, grain.age * 3 // grain.life)]

    def breeze_pixels(self, dunes):
        """Light trails use the same world X and tick on both sides of a room cut."""
        for depth, spacing, speed, phase in DUNE_BREEZE:
            head = (self.tick * speed + phase - self.dune_origin) % spacing
            row = dunes.ground_top + round(depth * (HEIGHT - dunes.ground_top - 8))
            colours = NEAR_SANDS if depth >= 0.49 else FAR_SANDS
            for front in range(head, WIDTH + BREEZE_TRAIL[-1][0], spacing):
                ripple = round(3 * math.sin((front + self.dune_origin) / 37 + phase))
                for back, dy, shade in BREEZE_TRAIL:
                    x, y = front - back, row + ripple + dy
                    if 0 <= x < WIDTH and 0 <= y < HEIGHT and dunes.open_sand[y, x]:
                        yield x, y, colours[shade]

    def put_sand(self, canvas):
        """The blown sand, each pixel gentler: part of the way back to what it covers."""
        air, inks = self.air, self.air.inks
        drawn = {}
        for x, y, colour in self.desert_pixels():
            if 0 <= x < WIDTH and 0 <= y < HEIGHT and not air.is_covered(x, y):
                drawn[x, y] = inks[colour][:3]
        for (x, y), colour in drawn.items():
            behind = tuple(canvas[x, y][:3])
            if colour != behind:
                canvas[x, y] = air.gentle(behind, colour)

    # The sky and the wind

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
        if self.clouds:
            colours = colours_of(air.palette_key)
            for cloud in self.clouds:
                self.draw_cloud(frame, cloud, colours)
            canvas = frame.load()
        self.put_grit(canvas, self.grit_pixels())
        # The wind, behind what the foreground covers, paler than what it crosses.
        for streak in self.streaks:
            for x, y, amount in streak_pixels(streak):
                if 0 <= x < WIDTH and 0 <= y < HEIGHT and not air.is_covered(x, y):
                    canvas[x, y] = air.paler_than(tuple(canvas[x, y][:3]), amount)
        self.put_grit(canvas, self.pebble_pixels())
        if air.dunes is not None:
            self.put_sand(canvas)
        # Kept to find the Prince in once he is drawn, while anything could fall on him.
        self.before_actors = frame.copy() if self.watches_the_prince() else None
        return frame
