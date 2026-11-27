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
the sky has only a few stars, middling and bright, and its shooting stars stay within
the thin band of sky over the mountains. On the first visit to the horse's
room, a large shooting star leaves a glowing line that sheds sparks after a short wait.

The wind. In a room open to the sky one gust sends one or two waving streaks across
the ruins. Each can roll briefly and run out or travel farther as it winds inward.
Both styles share a gust clock that runs across room changes. The desert has its own wind.

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
the Prince's steps, skids and landings (but on the desert's sand, which raises sand
instead), a loose floor landing, a gate or a door coming down. They are the caves' own puffs, in the pale rose of the ruins' grit.

The desert. One wind runs from the chasm along the dunes of level nine and up to the
horse. Wisps sweep across the left bank as sand trickles off its ledges. Rising
air carries a little sand on the right side of the gorge.
The wind comes in stronger gusts, now and then two or
three close together, then a lull, each its own strength, speed and stretch of the room,
blowing harder and softer as it goes. Each runs along the crest of the near dune and blows a low spray of sand
off it, sweeps loose sand up off the plain, runs streams of sand along the ground, hits
the rocks (sand runs at a big rock's foot, grains bounce up its face, and the ground
lies still in its lee) and now and then a small dust devil of sand grains spins along
the crest for a while, each its own size, shape, ways and life. A few low grains curl
around its foot, with short sprays of sand skipping away to either side. All of it is
a little gentler than the sand's own colours, and none of it blows over the blue dunes far away.
On the sand the Prince's running steps kick a few grains back off his heel, a landing
throws some to both sides and a skid sprays them ahead of his toe; his feet leave
prints that stay a second and then fill in from their ends; and a gust going by him
blows sand off his legs and feet, downwind.
"""

from collections import deque
from itertools import chain
from dataclasses import dataclass, field, replace
import math
import random

import numpy
from PIL import Image

from pop2.cavern_ambience import (
    CLOUD_CRUMBLE, CLOUD_PALER, CLOUD_STEPS, EMPTY_TILES, FLOOR_STRIP, LANDING_DEPTH, MOST_CLOUDS, SHUT_PUFF,
    LANDING_PUFF, SKID_PUFF, SLAM_PUFF, STEP_PUFF, TILE_HEIGHT, TILE_PUFF, TILE_WIDTH, TIP_LUMINANCE, Cloud, Fleck,
    Thud, colours_of, floor_y, footfalls, landing, open_air,
)

WIDTH, HEIGHT = 510, 365

RUINS_LEVELS = frozenset({6, 7, 8, 9})
# Level 9's contiguous desert, from left to right. Internal room indices are zero-based.
HORSE_ROOM = 1
CHASM_ROOM = 15
DESERT_ROOMS = (CHASM_ROOM, 14, 13, 12, 11, 10, HORSE_ROOM)

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
HORSE_STAR_DELAY_TICKS = 12
# NIS 2 uses the same 12 Hz cadence as the playable desert.
HORSE_AMBIENCE_TICKS_PER_SECOND = 12
HORSE_LINE_TICKS = 14
HORSE_SPARK_DELAY, HORSE_SPARK_LIFE = (3, 10), (36, 48)
HORSE_SPARK_FADE = 10
HORSE_STAR = ShooterKind('horse arrival', 31.0, 9, 0, (GOLD_BRIGHT.steps[-1], *LILAC[4:0:-1]),
                         WHITE, (9, 9), 0, linger=HORSE_SPARK_DELAY[1] + HORSE_SPARK_LIFE[1])
SHOOTERS = (FAINT, NORMAL, GRAZER, FIREBALL)
STAR_CROSS = ((1, 0), (-1, 0), (0, 1), (0, -1))
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
OPEN_SKY = 0.02
TICKS_BETWEEN_GUSTS = (26, 58)
OPENING_CLIFF = (6, 26)
OPEN_COURTYARD = (8, 8)
CLIFF_WIND_ORIGIN = (267, 25)
CLIFF_WIND_FADE_TICKS = 10
RUINS_WIND_PRIME_TICKS = 12
GUST_TICKS = 44
STREAKS_A_GUST = (1, 2)
SECOND_STREAK_BELOW = (16, 32)
# Horizontal streaks in the open ruins.
STREAK_TOP, STREAK_BOTTOM = 20, 300
STREAK_LEFT, STREAK_RIGHT = -30, WIDTH - 260
RUINS_STREAK_RUN = (175, 235)
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
GRIT_FLOOR_DEPTH = 30
# In the floor profile: a floor's own pixels, and the broken slab of a fallen loose floor
# lying on one. The lowest pixels of each run of floor in a column are a face, not a
# surface: the front lip, or the cut side of a slab's end where the next tile is gone.
GRIT_FLOOR, GRIT_DEBRIS = 1, 2
GRIT_FACE = 5
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
FIRST_DEVIL, TICKS_BETWEEN_DEVILS = (30, 360), (320, 960)
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
# The Prince on the sand of the desert (the user's ideas, 2026-11-27). His running steps
# kick a few grains back off his heel, a landing throws them to both sides and a skid
# sprays them ahead of his toe: how many, how fast back (or ahead) and up, how fast they
# fall back and how long they fly at most. The user, 2026-11-27: with the puffs gone,
# more of it (it was 3-5, 6-9 and 4-6, and 2-4 a tick off his legs).
STEP_KICK, STEP_KICK_BACK, STEP_KICK_UP = (5, 8), (0.7, 1.9), (0.9, 2.0)
LANDING_KICK, LANDING_KICK_SIDE, LANDING_KICK_UP = (9, 13), (0.6, 2.2), (0.6, 1.6)
# A landing's grains leave from beyond the ends of his shoes, which would hide them.
LANDING_KICK_FROM = 7
SKID_KICK, SKID_KICK_AHEAD, SKID_KICK_UP = (6, 9), (1.5, 3.0), (0.3, 1.0)
KICK_FALL, KICK_DRAG, KICK_LIFE = 0.35, 0.9, (4, 9)
# Where his foot comes down it leaves a print in the sand, about half his shoe long: two
# rows darker than the sand, the far one darkest and shorter. It stays a second, then the
# sand fills it in from its ends, a pixel each end every PRINT_FILL ticks.
PRINT_WIDTH, PRINT_SHADOW, PRINT_DARKER = (6, 8), 0.28, 0.15
PRINT_HOLD, PRINT_FILL = (12, 16), 3
# A new print only where his foot has moved on this far from the last.
PRINT_APART = 6
# A gust's front that has just gone past him blows sand off his legs and feet, from their
# downwind side: how far past, grains a tick at full strength, from how high up his legs,
# and their flight.
SHED_BEHIND = 30
SHED_GRAINS, SHED_HIGH = (3, 6), 22
SHED_SPEED, SHED_LIFT, SHED_SETTLE, SHED_LIFE = (2.5, 4.5), (-0.3, 0.2), 0.06, (6, 12)
DESERT_COLOURS = (*SAND, *FAR_SANDS, *NEAR_SANDS, NEAR_SIDE, FAR_SIDE, FLUNG, FOOT_HIGHLIGHT)

# Every colour the effects use, each shown as the nearest of the room's palette.
INK_COLOURS = ALL_COLOURS | frozenset(GRIT_COLOURS) | frozenset(DESERT_COLOURS)


def sky_mask(rgb):
    """[y, x] of the night sky in an RGB picture of the room."""
    red, green, blue = (rgb[..., channel].astype(numpy.int32) for channel in range(3))
    return (green == 0) & (blue >= SKY_LEAST_BLUE) & (red <= SKY_MOST_RED)


def is_sky(colour):
    return colour[1] == 0 and colour[2] >= SKY_LEAST_BLUE and colour[0] <= SKY_MOST_RED


def is_painted_sky(colour):
    red, green, blue = colour[:3]
    return (blue > red) & (blue > green)


def opening_star_mask(painted_sky, covered=None):
    sky = numpy.zeros_like(painted_sky)
    sky[8:114, 234:-8] = painted_sky[8:114, 234:-8]
    if covered is not None:
        sky &= ~covered
    return sky


def opening_stars(rgb, sky):
    seed = OPENING_CLIFF[0] * 100 + OPENING_CLIFF[1]
    return place_stars(sky, numpy.maximum(blueness(rgb), 0.6), random.Random(seed), density=120)


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


def place_stars(sky, blue, rng, *, density=STARS_PER_SKY):
    """[(x, y, kind)], more of them where the sky is bluest."""
    weight = clear_of(sky, STAR_CLEAR) * blue ** 2
    wanted = int(round(density * float(weight.sum()) / (WIDTH * HEIGHT)))
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
    # {(RGB behind, how much darker): RGBA} of the footprints, filled as it is wanted.
    darker: dict = field(default_factory=dict)
    # The room's palette as the caves key their tables (colours_of), for the puffs.
    palette_key: tuple = ()
    chasm: bool = False
    cliff_wind_sky: numpy.ndarray | None = None
    cliff_sand: numpy.ndarray | None = None
    grit_floor: numpy.ndarray | None = None

    def in_sky(self, x, y):
        return 0 <= x < WIDTH and 0 <= y < HEIGHT and bool(self.sky[y, x])

    def is_covered(self, x, y):
        return self.covered is not None and bool(self.covered[y, x])

    def paler_than(self, behind, amount, *, allow_same=False):
        key = behind, amount, allow_same
        if key not in self.paler:
            self.paler[key] = (*paler(behind, amount, self.palette, allow_same=allow_same), 255)
        return self.paler[key]

    def darker_than(self, behind, amount):
        key = behind, amount
        if key not in self.darker:
            self.darker[key] = (*darker(behind, amount, self.palette), 255)
        return self.darker[key]

    def gentle(self, behind, drawn, amount=GENTLE):
        """The sand drawn over behind, amount of the way back toward it, never behind
        itself."""
        key = behind, drawn, amount
        if key not in self.gentler:
            self.gentler[key] = (*gentler_colour(behind, drawn, self.palette, amount), 255)
        return self.gentler[key]


def gentler_colour(behind, drawn, palette, amount=GENTLE):
    """Blend toward the scenery, keeping a distinct ink from the palette."""
    wanted = numpy.array(behind) + (numpy.array(drawn) - numpy.array(behind)) * (1 - amount)
    distance = (((palette - wanted) * (2, 3, 2)) ** 2).sum(axis=1)
    return next((tuple(int(value) for value in palette[i]) for i in distance.argsort(kind='stable')
                 if tuple(int(value) for value in palette[i]) != behind), behind)


def paler(behind, amount, palette, *, allow_same=False):
    """The nearest paler palette colour, with the base eligible during a fade."""
    wanted = numpy.minimum(255, numpy.array(behind) + amount)
    distance = (((palette - wanted) * (2, 3, 2)) ** 2).sum(axis=1)
    for index in distance.argsort(kind='stable'):
        colour = tuple(int(value) for value in palette[index])
        if sum(colour) > sum(behind) or (allow_same and colour == tuple(behind)):
            return colour
    return tuple(behind)


def darker(behind, amount, palette):
    """The palette colour nearest to behind made this share darker, and darker than it."""
    wanted = numpy.array(behind) * (1 - amount)
    distance = (((palette - wanted) * (2, 3, 2)) ** 2).sum(axis=1)
    for index in distance.argsort(kind='stable'):
        colour = tuple(int(value) for value in palette[index])
        if sum(colour) < sum(behind):
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


def grit_floor_profile(pieces):
    """Visible floor depth at each X, grouped by the three tile rows.

    Only the course at the foot of a piece counts. A pillar, door or
    staircase can share an image with a floor and rise above that course.
    Pieces are (row, sprite, position[, debris]) in drawing order, so a broken
    slab covers the floor it lies on.
    """
    profile = numpy.zeros((3, GRIT_FLOOR_DEPTH, WIDTH), dtype=numpy.uint8)
    for row, sprite, (x, y), *debris in pieces:
        base = (row + 1) * TILE_HEIGHT + 5
        band_top = base - GRIT_FLOOR_DEPTH
        left, right = max(0, x), min(WIDTH, x + sprite.width)
        top, bottom = max(band_top, y), min(base, y + sprite.height)
        if left < right and top < bottom:
            alpha = numpy.asarray(sprite.getchannel('A'))[top - y:bottom - y, left - x:right - x]
            profile[row, top - band_top:bottom - band_top, left:right][alpha > 0] = (
                GRIT_DEBRIS if debris and debris[0] else GRIT_FLOOR)
    return profile


def supported_depth(row, masked, wanted):
    """Where grit falling at wanted's depth stops in one column of the row, or None when
    it falls past: over a gap, or in front of the lowest GRIT_FACE pixels of floor, the
    front lip or the cut side of a slab's end."""
    band_top = (row + 1) * TILE_HEIGHT + 5 - GRIT_FLOOR_DEPTH
    column = numpy.asarray(masked)
    debris = numpy.flatnonzero(column == GRIT_DEBRIS)
    # A broken slab that rises to the spot catches the grain on its top.
    if debris.size and band_top + debris[0] <= wanted:
        return band_top + int(debris[0])
    heights = numpy.flatnonzero(column) + band_top
    if not heights.size or wanted > heights[-1] - GRIT_FACE:
        return int(band_top + debris[0]) if debris.size else None
    surface = heights[heights <= heights[-1] - GRIT_FACE]
    if not surface.size:
        return int(heights[0])  # A sliver of floor in front of the spot hides the rest of the fall.
    return int(surface[numpy.abs(surface - wanted).argmin()])


def grit_landing(floor, terrain, room, x, top, depth=0):
    """Where grit meets a visible floor, or None when it falls through."""
    if not 0 <= x < WIDTH:
        return None
    if floor is None:
        ground = landing(terrain, room, x, top) if terrain is not None else None
        return None if ground is None else ground + depth
    for row in range(max(0, (int(top) - 5) // TILE_HEIGHT), 3):
        ground = supported_depth(row, floor[row, :, x], floor_y(row) + depth)
        if ground is not None and ground > top:
            return ground
    return None


def grit_sources(air, clear, stone, terrain, room, rng, floor=None):
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
                depth = rng.randint(*LANDING_DEPTH)
                bottom = grit_landing(floor, terrain, room, x, y, depth)
                found.append(Crack(x, y, HEIGHT if bottom is None else bottom))
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
    origin: int = 0

    @property
    def left(self):
        return min(self.foot)

    def covers(self, x, y):
        return self.mask[y, x - self.origin]


@dataclass(frozen=True, eq=False)
class Dunes:
    """The near crest and the start of the plain by column, with its sand and rocks."""

    crest: numpy.ndarray
    ground_top: numpy.ndarray
    sand: numpy.ndarray
    open_sand: numpy.ndarray
    rocks: tuple

    @classmethod
    def join(cls, rooms):
        rocks = []
        for index, room in enumerate(rooms):
            offset = index * WIDTH
            rocks.extend(Rock({x + offset: y for x, y in rock.foot.items()}, rock.mask, rock.size, offset)
                         for rock in room.rocks)
        sand = numpy.concatenate([room.sand for room in rooms], axis=1)
        return cls(numpy.concatenate([room.crest for room in rooms]),
                   numpy.concatenate([room.ground_top for room in rooms]), sand,
                   sand & ~shelter(rocks, sand.shape[1]), tuple(rocks))


def crest_line(sand):
    """[x] the top of the near dune: its first run of solid sand, or -1."""
    solid = runs(sand, CREST_SOLID, False)
    solid[HEIGHT - CREST_SOLID:] = False
    found = solid.any(axis=0)
    return numpy.where(found, solid.argmax(axis=0), -1)


def find_rocks(sand, top):
    """Every patch of the plain below top that is not sand."""
    solid = ~sand & (numpy.arange(HEIGHT)[:, None] >= top)
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


def shelter(rocks, width=WIDTH):
    """[y, x] the still ground downwind of each rock, a rock's width long."""
    still = numpy.zeros((HEIGHT, width), dtype=bool)
    for rock in rocks:
        left, right = min(rock.foot), max(rock.foot)
        base = max(rock.foot.values())
        still[max(0, base - 8):base + 4, right + 1:right + 1 + (right - left)] = True
    return still


def read_dunes(sand, *, horse=False):
    """The desert's dunes, or None where the sand is not a plain of dunes under a crest."""
    if horse:
        # The near dune continues behind the horse. To its right only the exposed
        # ground takes sand; the sandstone pedestal and walls also have warm pixels.
        columns = numpy.arange(WIDTH)
        floor = numpy.interp(columns, (0, 150, 250, 268, 380, 510), (200, 200, 235, 336, 316, 328))
        sand = sand & (numpy.arange(HEIGHT)[:, None] >= floor)
    crest = crest_line(sand)
    if horse:
        ground_top = numpy.where(columns < 250, numpy.maximum(238, crest + GROUND_FROM), floor).astype(int)
        crest[250:] = -1  # Only the exposed dune left of the statue has a near crest.
    else:
        if (crest < 0).any() or crest.max() - crest.min() > DUNE_CREST_SPREAD:
            return None
        ground_top = numpy.full(WIDTH, int(crest.max()) + GROUND_FROM)
    ground_top = numpy.minimum(ground_top, HEIGHT - 6)
    rocks = find_rocks(sand, ground_top)
    return Dunes(crest, ground_top, sand, sand & ~shelter(rocks), rocks)


def chasm_dunes(sand):
    """The chasm has two sandy banks and an open gap, without a continuous crest."""
    x = numpy.arange(WIDTH)
    y = numpy.arange(HEIGHT)[:, None]
    banks = (y >= 219) & ((x < 136) | (x >= 345))
    sand = sand & banks
    return Dunes(numpy.full(WIDTH, -1), numpy.full(WIDTH, 238), sand, sand, ())


def read_room(level_number, room, rgb, palette, covered=None, terrain=None, painted=False, *, grit_floor=None):
    """The air of a room from an RGB picture of its scenery, its palette, [y, x] of what
    its foreground covers and its tiles; a painted room sheds no grit."""
    sky, blue = sky_mask(rgb), blueness(rgb)
    open_sky = float(sky.mean())
    sand = sand_mask(rgb)
    desert = bool(open_sky >= DESERT_SKY and sand.mean() >= DESERT_SAND)
    chasm = (level_number, room) == (9, CHASM_ROOM)
    place = level_number, room
    cliff_wind_sky = None
    if place == OPENING_CLIFF:
        # The painted gradient is blue without matching the night-sky palette.
        cliff_wind_sky = is_painted_sky(numpy.moveaxis(rgb, -1, 0))
        sky = opening_star_mask(cliff_wind_sky, covered)
    windy = not (desert or chasm) and (open_sky >= OPEN_SKY or place in (OPENING_CLIFF, OPEN_COURTYARD))
    seed = level_number * 100 + room
    if desert:
        stars = place_desert_stars(sky, random.Random(seed + 41))
    elif cliff_wind_sky is not None:
        stars = opening_stars(rgb, sky)
    else:
        stars = warm_some(place_stars(sky, blue, random.Random(seed)), random.Random(seed + 7))
        stars += place_haze_stars(sky, blue, stars, random.Random(seed + 13))
    luminance = numpy.asarray(Image.fromarray(numpy.ascontiguousarray(rgb, dtype=numpy.uint8)).convert('L'))
    grit = lines = ()
    if terrain is not None and not painted:
        air = numpy.frombuffer(open_air(luminance, terrain, room), dtype=numpy.uint8).reshape(HEIGHT, WIDTH) != 0
        clear = air if covered is None else air & ~covered
        stone = luminance >= TIP_LUMINANCE
        grit = grit_sources(air, clear, stone, terrain, room, random.Random(seed), grit_floor)
        lines = ceilings(air, clear, stone, terrain, room)
    dunes = None
    if chasm:
        dunes = chasm_dunes(sand)
    elif desert:
        dunes = read_dunes(sand, horse=(level_number, room) == (9, HORSE_ROOM))
    return RuinsAir(sky, blue, tuple(stars), nearest_colours(palette, INK_COLOURS), desert,
                    windy=windy, covered=covered,
                    palette=palette_rgb(palette), grit=grit, ceilings=lines, luminance=luminance,
                    dunes=dunes, palette_key=tuple(sorted(palette.items())), chasm=chasm,
                    cliff_wind_sky=cliff_wind_sky, cliff_sand=sand if place == OPENING_CLIFF else None, grit_floor=grit_floor)


def ruins_air(level_number, room, art, terrain=None, raised=None):
    """The air of a room as the game draws it (terrain and raised as in room_air)."""
    from pop2.caverns import customized_rooms, room_assets

    palette = room_assets(level_number, room)[2]
    rgb = numpy.asarray(Image.alpha_composite(art.background, art.foreground).convert('RGB'))
    covered = numpy.asarray(art.foreground.getchannel('A')) > 0
    painted = room in customized_rooms(level_number)
    return read_room(level_number, room, rgb, palette, covered, terrain, painted,
                     grit_floor=art.grit_floor if terrain is not None and not painted else None)


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


def horse_shooting_star():
    """A fast flight from the right, through the clear sky above the horse."""
    angle = math.radians(HORSE_STAR.angle[0])
    return Shooter(HORSE_STAR, 384, 12, -math.cos(angle), math.sin(angle))


def shooter_path(air, kind, rng):
    """(x, y, dx, dy) of a random shooting star over clear sky."""
    if air.cliff_wind_sky is not None:
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
            # The desert's sky is a thin band over the jagged mountains: all of the way.
            if air.desert and not all(air.in_sky(*Shooter(kind, x, y, dx, dy).at(step))
                                      for step in range(int(travel) + 1)):
                continue
            return x, y, dx, dy
    return None


def shooter_pixels(shooter):
    """(x, y, RGB) of a shooting star at its age, the later over the earlier."""
    kind, age = shooter.kind, shooter.age
    if kind is HORSE_STAR:
        yield from horse_star_pixels(shooter)
        return
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
            yield x, y, kind.head
            for ox, oy in STAR_CROSS:
                yield x + ox, y + oy, kind.colours[0]
        return
    # The tail shortens as it burns out.
    length = max(2, int(kind.tail * (1.15 - age / kind.ticks)))
    for step in range(length, 0, -1):
        share = step / length
        shade = min(len(kind.colours) - 1, int(share * len(kind.colours)))
        yield (*shooter.at(travelled - step), kind.colours[shade])
    yield (*shooter.at(travelled), kind.head)
    if kind is FIREBALL:
        # A head two pixels across: the second one dimmer, beside it on the slope.
        x, y = shooter.at(travelled)
        yield x, y + 1 if abs(shooter.dx) > abs(shooter.dy) else y, kind.colours[0]


def horse_star_glow(tick):
    """Build the glow around the white head, then let it burn down."""
    remaining = HORSE_STAR.ticks - 1 - tick
    return min(1.0, 0.18 + 0.28 * tick, 0.34 + 0.31 * remaining)


def horse_star_pixels(shooter):
    """An afterglow along the full flight path, with sparks falling from it."""
    kind, age = shooter.kind, shooter.age
    distance = int(kind.speed * min(age, kind.ticks - 1))
    shades = len(kind.colours)
    for step in range(distance + 1):
        passed_at = step / kind.speed
        since = age - passed_at
        if since >= HORSE_LINE_TICKS:
            continue
        glow = min(1.0, 0.45 + 0.24 * passed_at) * (1 - since / HORSE_LINE_TICKS) ** 1.35
        # The faint line loses individual pixels in a fixed pattern as it fades.
        if glow < 0.35 * ((step * 37 % 17 + 0.5) / 17):
            continue
        shade = max(0, shades - 1 - int(glow * shades))
        x, y = shooter.at(step)
        colour = kind.head if age < kind.ticks and distance - step <= 6 else kind.colours[shade]
        yield x, y, colour
        if glow >= 0.75 and since < 2:
            yield x, y + 1, kind.colours[shade + 1]

    # The sparks keep their own lifetime after the line fades.
    first_delay, last_delay = HORSE_SPARK_DELAY
    shortest, longest = HORSE_SPARK_LIFE
    for index, sample in enumerate(range(5, distance + 1, 6)):
        step = sample + index * 7 % 5 - 2
        delay = first_delay + index * 5 % (last_delay - first_delay + 1)
        fall = age - step / kind.speed - delay
        life = shortest + index * 3 % (longest - shortest + 1)
        if not 0 <= fall < life:
            continue
        x, y = shooter.at(step)
        drift = round((index % 5 - 2) * fall / 43)
        drop = 1 + round(0.03 * fall + (0.0018 + 0.0002 * (index % 4)) * fall ** 2)
        first_shade = 1 + (index % 4 != 0)
        fade = max(0.0, 1 - (life - fall) / HORSE_SPARK_FADE)
        shade = first_shade + int(fade * (shades - first_shade))
        yield x + drift, y + drop, kind.colours[shade]
        if drop >= 3 and shade < 3 and index % 3 == 0:
            yield x + drift, y + drop - 1, kind.colours[shade + 1]

    if age < kind.ticks:
        x, y = shooter.at(distance)
        glow = horse_star_glow(age)
        shade = max(0, shades - 1 - int(glow * shades))
        yield x, y, kind.head
        if glow >= 0.5:
            for ox, oy in STAR_CROSS:
                yield x + ox, y + oy, kind.colours[shade + 1]


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


def curl(bx, by, r0, rise, *, turns=1.0):
    """Start rightward from (bx, by) and spiral inward as the radius shrinks by rise."""
    cx, cy = bx, by - r0
    points, steps = [], 720
    for i in range(1, steps + 1):
        turn = i / steps
        angle = -math.pi / 2 + 2 * math.pi * turn * turns
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

    def advance(self):
        self.head += self.step()
        self.shown += 1

    @property
    def offset(self):
        return 0, 0

    def visible_pixels(self):
        return streak_pixels(self)

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


@dataclass(frozen=True)
class WindingStyle:
    length: int
    glide_ticks: int
    curl_ticks: int
    drift_per_tick: int
    paler: tuple[int, int, int]

    @property
    def lifetime(self):
        return self.glide_ticks + self.curl_ticks

    def drift_at(self, age):
        return max(0, age - self.glide_ticks) * self.drift_per_tick


RUINS_STREAK_STYLE = WindingStyle(length=54, glide_ticks=32, curl_ticks=22, drift_per_tick=2, paler=(29, 31, 40))
CHASM_STREAK_STYLE = WindingStyle(length=35, glide_ticks=36, curl_ticks=22, drift_per_tick=1, paler=(23, 25, 33))


def winding_streak_path(x, y, travel, lean, radius, turn, *, horizontal=False):
    """A gently waving run that settles into a tight curl."""
    wave_height, wave_length = 2.1, 64
    run = []
    for step in range(4 * travel + 1):
        along = step / 4
        wave = wave_height * math.sin(math.tau * along / wave_length)
        taper = min(1.0, (travel - along) / 18) ** 2
        run.append((along, lean * along / travel + wave * taper))
    curled = curl(travel, lean, radius, radius, turns=1.75)
    pixels = clean_line(run + curled)
    if horizontal:
        path = [(x + along, y + turn * across) for along, across in pixels]
    else:
        path = [(x + turn * across, y - along) for along, across in pixels]
    return path, len(clean_line(run)) - 1


def winding_streak_bounds(path, turn, age, style):
    curl_age = age - style.glide_ticks
    if curl_age < 0:
        head = turn * age // style.glide_ticks
        return head - style.length, head
    progress = curl_age / style.curl_ticks
    if progress >= 1.0:
        return len(path), len(path)
    curl_length = len(path) - turn
    head = turn + round(curl_length * min(1.0, progress * 1.5))
    # The back of the line slows as it winds the last pixels into the center.
    wound = 1.0 - (1.0 - progress) ** 1.25
    tail = turn - style.length + round((style.length + curl_length) * wound)
    return tail, head


def winding_streak_pixels(path, turn, age, direction, style):
    """Glide, then travel with the wind while winding into the spiral."""
    tail, head = winding_streak_bounds(path, turn, age, style)
    glow = min(1.0, age / 5)
    drift = style.drift_at(age)
    dx, dy = direction[0] * drift, direction[1] * drift
    for index in range(max(0, tail), head):
        if index < turn:
            strength = glow * min(1.0, (index - tail + 1) / 5, (head - index) / 4)
        else:
            strength = 1.0 + 0.2 * min(1.0, (index - turn + 1) / 4)
        if round(max(style.paler) * strength) < 2:
            continue
        x, y = path[index]
        yield x + dx, y + dy, tuple(round(amount * strength) for amount in style.paler)


@dataclass
class WindingStreak:
    """A moving stroke that gathers into the center of a spiral."""

    pixels: list
    turn: int
    y: float
    shown: int = 0
    tangents: list | None = None

    @property
    def gone(self):
        return self.shown >= RUINS_STREAK_STYLE.lifetime

    def advance(self):
        self.shown += 1

    @property
    def offset(self):
        return RUINS_STREAK_STYLE.drift_at(self.shown), 0

    def showing(self):
        tail, head = winding_streak_bounds(self.pixels, self.turn, self.shown, RUINS_STREAK_STYLE)
        return range(max(0, tail), head)

    def visible_pixels(self):
        return winding_streak_pixels(self.pixels, self.turn, self.shown, (1, 0), RUINS_STREAK_STYLE)


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


def new_streak(rng, gust_y=None, *, winding=False):
    y0 = gust_y + rng.uniform(*SECOND_STREAK_BELOW) if gust_y is not None else rng.uniform(STREAK_TOP, STREAK_BOTTOM)
    if not winding:
        x0 = rng.uniform(STREAK_LEFT, STREAK_RIGHT)
        pixels, bends = ribbon(x0, y0, rng)
        return Streak(pixels, bends, rng.randint(*STREAK_LENGTH), y0)
    travel = rng.randint(*RUINS_STREAK_RUN)
    # Leave room for the spiral to travel after the long approach.
    right_edge = WIDTH - travel - RUINS_STREAK_STYLE.drift_at(RUINS_STREAK_STYLE.lifetime - 1) - 8
    x0 = rng.uniform(STREAK_LEFT, min(STREAK_RIGHT, right_edge))
    pixels, turn = winding_streak_path(
        round(x0), round(y0), travel, rng.randint(-4, 4), rng.uniform(2.55, 2.8),
        rng.choice((-1, 1)), horizontal=True,
    )
    return WindingStreak(pixels, turn, y0)


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
    depth: int = 0

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
    depth: int = 0


@dataclass
class GritFleck(Fleck):
    settled: bool = False


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
    depth: int = 0


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
class Footprint:
    """A print of his foot in the sand: its middle, its row, how wide, when it was made
    and how long it stays whole."""

    x: int
    y: int
    width: int
    born: int
    hold: int

    def pixels(self, tick):
        """[x] of the dent this tick, filled in from its ends; empty once gone."""
        left, age = self.x - self.width // 2, tick - self.born
        filled = 0 if age < self.hold else 1 + (age - self.hold) // PRINT_FILL
        return list(range(left + filled, left + self.width - filled))


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

    def over(self, tick, width):
        return self.run(tick, GROUND_FRONT) > self.reach or self.start + self.run(tick, CREST_FRONT) > width + 45

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
        age = max(0, min(self.life, tick - self.born))
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
class RuinsWind:
    """One clock and set of live streaks for the open rooms of a level."""

    rng: random.Random = field(default_factory=random.Random)
    streaks: list = field(default_factory=list)
    gust: int = 0
    gust_wait: int = 0
    tick: int = 0

    def prime(self):
        """Have the first gust in view when the Prince reaches open air."""
        for _ in range(RUINS_WIND_PRIME_TICKS):
            self.advance()

    def advance(self):
        self.tick += 1
        self.blow()
        self.advance_streaks()

    def blow(self):
        """Start a gust after the shared lull."""
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
            streak = new_streak(rng, gust_y, winding=rng.random() < 0.5)
            gust_y = streak.y
            self.streaks.append(streak)

    def advance_streaks(self):
        for streak in self.streaks:
            streak.advance()
        self.streaks = [streak for streak in self.streaks if not streak.gone]


@dataclass
class RuinsAmbience:
    room: int
    air: RuinsAir
    rng: random.Random = field(default_factory=random.Random)
    # Per star: ticks it stays dipped, ticks it keeps its cross.
    twinkles: list = field(default_factory=list)
    shooter: Shooter | None = None
    shooter_wait: int = 0
    wind: RuinsWind | None = None
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
    # The puffs of dust from the floor.
    clouds: list = field(default_factory=list)
    # Whether his feet are on the desert's sand, which raises its own sand instead of puffs
    # (the user, 2026-11-27: the puffs covered it).
    on_sand: bool = False
    tick: int = 0
    grit_floor: numpy.ndarray | None = field(init=False)

    def __post_init__(self):
        self.grit_floor = self.air.grit_floor
        self.twinkles = [[0, 0] for _ in self.air.stars]
        self.shooter_wait = self.rng.randint(*FIRST_SHOOTER)
        # Preserve the room-local random sequence now that its wind runs separately.
        self.rng.randint(*TICKS_BETWEEN_GUSTS)
        self.quiet_wait = self.rng.randint(*TICKS_BETWEEN_TRICKLES)
        # Keep the room-local random sequence now that desert wind has its own clock.
        self.rng.randint(*FIRST_DESERT_GUST)
        self.rng.randint(*FIRST_DEVIL)

    @property
    def streaks(self):
        return self.wind.streaks if self.wind is not None else ()

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
        self.advance_trickles(terrain)
        self.advance_mounds(terrain)
        self.advance_pebbles()
        self.advance_bits()
        self.advance_clouds()

    # The puffs

    def puff(self, last, footing, thuds):
        """The puffs his feet and whatever came down raise this tick."""
        raised = list(thuds)
        if last is not None and footing is not None and not self.on_sand:
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
        if last is not None and footing is not None and last.falling and footing.on_floor:
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

    def grit_bottom(self, x, top, fallback, depth=0):
        """Find support below the particle on the current frame."""
        if self.grit_floor is None:
            return fallback
        ground = grit_landing(self.grit_floor, None, self.room, round(x), top, depth)
        return HEIGHT if ground is None else ground

    def mound_floor(self, terrain, x, bottom):
        """A common base for the heap, its slopes and its shadow."""
        row = row_of(bottom)
        if self.grit_floor is None:
            if terrain is None or terrain.tile(self.room, x // TILE_WIDTH, row).kind not in EMPTY_TILES:
                return bottom
            return None
        half = len(MOUND) // 2
        left, right = x - half, x + half + 3
        if 0 <= left < right <= WIDTH:
            under = self.grit_floor[row, :, left:right]
            if (under == GRIT_DEBRIS).any():
                return None  # No heap on the rubble.
            return supported_depth(row, under.all(axis=1), bottom)
        return None

    def busy(self, x, pour=True):
        """Whether a crack near x is pouring, or for a new pour, running at all."""
        return any(abs(trickle.source.x - x) <= SAME_CRACK and trickle.running and (pour or trickle.pour)
                   for trickle in self.trickles)

    def start(self, x, top, grains, wait, pour=False, terrain=None, stone=None):
        stone = stone_row(top) if stone is None else stone
        if self.busy(x, pour) or not self.stands(terrain, x, stone):
            return
        ground = grit_landing(self.grit_floor, terrain, self.room, int(x), top)
        depth = 0 if ground is None else self.rng.randint(*LANDING_DEPTH)
        bottom = grit_landing(self.grit_floor, terrain, self.room, int(x), top, depth) if depth else ground
        self.trickles.append(Trickle(Crack(int(x), top, HEIGHT if bottom is None else bottom),
                                     wait, grains, pour, stone=stone, depth=depth))

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
                                       trickle.wait + rng.randint(0, 3), depth=trickle.depth))

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
            if mound is not None and self.mound_floor(terrain, mound.x, mound.bottom) != mound.bottom:
                mound = trickle.mound = None
            grains = []
            for grain in trickle.grains:
                was = grain.y
                # A streak passing by carries the grain along its way, up in its curl.
                push_x, push_y = self.streak_push(grain.x, grain.y)
                grain.speed = min(GRIT_FASTEST, grain.speed + GRIT_GRAVITY + push_y * STREAK_LIFT)
                grain.y += grain.speed
                grain.wind += (push_x - grain.wind) * STREAK_TAKE
                grain.x += grain.wind
                x = int(round(grain.x))
                bottom = self.grit_bottom(x, was, source.bottom, trickle.depth)
                hit = self.on_prince(x, was, min(grain.y, bottom))
                if hit is not None:
                    self.bounce_off(grain.x, hit - 1, grain.shade, bottom, trickle.depth)
                    continue
                if mound is not None:
                    # On top of the mound, where it has grown under the thread.
                    column = x - mound.x + len(MOUND) // 2
                    if 0 <= column < len(MOUND) and row_of(bottom) == row_of(mound.bottom):
                        bottom = mound.bottom - mound.heights[column]
                if grain.y < bottom:
                    grains.append(grain)
                else:
                    self.land(grain.x, bottom, trickle.pour, trickle)
                    if grain.size == 'crumb':
                        # It breaks in two.
                        edge = self.grit_bottom(grain.x + 1, was, bottom, trickle.depth)
                        if edge <= grain.y:
                            self.land(grain.x + 1, edge, False)
            trickle.grains = grains
            if trickle.running or trickle.grains:
                kept.append(trickle)
            elif trickle.mound is not None:
                trickle.mound.stays = self.rng.randint(*MOUND_STAYS)
        self.trickles = kept

    def heap(self, trickle, x, bottom):
        """A grain of a pour settles on its mound, rolling off a side that is full."""
        mound = trickle.mound
        x = int(round(x))
        if mound is None:
            bottom = self.mound_floor(None, x, bottom)
            if bottom is None:
                return False
            mound = trickle.mound = Mound(x, bottom)
            self.mounds.append(mound)
        elif abs(x - mound.x) > len(MOUND) // 2 or row_of(bottom) != row_of(mound.bottom):
            return False
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
        if pour and trickle is not None and rng.random() < HEAP_CHANCE and self.heap(trickle, x, bottom):
            return
        if rng.random() < (POUR_SPLASH_CHANCE if pour else SPLASH_CHANCE):
            for _ in range(rng.randint(*SPLASH_BITS)):
                self.flecks.append(GritFleck(x, bottom - 1, rng.choice((-1, 1)) * rng.uniform(*SPLASH_SIDE),
                                         -rng.uniform(*SPLASH_LIFT), SPLASH_PULL, (GRIT_HEAD, GRIT_TAIL),
                                         rng.randint(*SPLASH_LIFE), bottom))
        if rng.random() < (POUR_REST_CHANCE if pour else REST_CHANCE):
            self.flecks.append(GritFleck(x + rng.choice((-1, 0, 0, 1)), bottom - rng.randint(0, 2), 0.0, 0.0, 0.0,
                                         (GRIT_TAIL, GRIT_DIM), rng.randint(*REST_LIFE), bottom, settled=True))

    def advance_mounds(self, terrain=None):
        rng, kept = self.rng, []
        for mound in self.mounds:
            if self.mound_floor(terrain, mound.x, mound.bottom) != mound.bottom:
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
            if pebble.rest and self.grit_bottom(pebble.x, pebble.y, pebble.bottom, pebble.depth) == pebble.bottom:
                pebble.rest -= 1
                if pebble.rest:
                    kept.append(pebble)
                continue
            was = pebble.y
            pebble.rest = 0
            pebble.vy = min(PEBBLE_FASTEST, pebble.vy + PEBBLE_GRAVITY)
            pebble.y += pebble.vy
            pebble.x += pebble.vx
            pebble.bottom = self.grit_bottom(pebble.x, was, pebble.bottom, pebble.depth)
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
            if isinstance(fleck, GritFleck):
                # Settled grains can sit on the contact pixel itself.
                top = min(fleck.y, fleck.floor - 1) if fleck.settled else fleck.y
                depth = fleck.floor - floor_y(row_of(fleck.floor)) if fleck.floor < HEIGHT else 0
                bottom = self.grit_bottom(fleck.x, top, fleck.floor, depth)
                if fleck.settled and bottom != fleck.floor:
                    fleck.settled = False
                    fleck.dy = fleck.pull = GRIT_GRAVITY
                    fleck.life = max(fleck.life, fleck.age + OFF_LIFE)
                fleck.floor = bottom
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

    def bounce_off(self, x, y, shade, floor, depth):
        rng = self.rng
        self.bits.append(Bit(float(x), float(y), rng.choice((-1, 1)) * rng.uniform(*OFF_SIDE), -rng.uniform(*OFF_UP),
                             shade, floor, depth=depth))

    def advance_bits(self):
        rng, kept = self.rng, []
        for bit in self.bits:
            was = bit.y
            bit.dy += OFF_PULL
            bit.x += bit.dx
            bit.y += bit.dy
            bit.floor = self.grit_bottom(bit.x, was, bit.floor, bit.depth)
            hit = self.on_prince(round(bit.x), was, min(bit.y, bit.floor)) if bit.dy > 0 else None
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
            dx, dy = streak.offset
            for i in showing:
                x_at, y_at = streak.pixels[i]
                px, py = x_at + dx, y_at + dy
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

    def sky_pixels(self):
        """(x, y, RGB) of the stars and the shooting star, the later over the earlier."""
        for (x, y, kind), (dipped, flared) in zip(self.air.stars, self.twinkles):
            yield x, y, kind.steps[0] if dipped else kind.steps[-1]
            if kind.cross and flared:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    yield x + dx, y + dy, kind.steps[0]
        if self.shooter is not None:
            yield from shooter_pixels(self.shooter)

    def draw_wind(self, canvas):
        air = self.air
        cliff_sky = air.cliff_wind_sky
        opacity = 1.0
        if cliff_sky is not None and self.wind is not None:
            opacity = min(1.0, (self.wind.tick - RUINS_WIND_PRIME_TICKS) / CLIFF_WIND_FADE_TICKS)
            if opacity <= 0:
                return
        for streak in self.streaks:
            drawn = set()
            for x, y, amount in streak.visible_pixels():
                if cliff_sky is not None:
                    # This wind is farther away, beyond the edge of the cliff.
                    x, y = CLIFF_WIND_ORIGIN[0] + x // 2, CLIFF_WIND_ORIGIN[1] + y // 2
                    if (x, y) in drawn:
                        continue
                    drawn.add((x, y))
                if 0 <= x < WIDTH and 0 <= y < HEIGHT and not air.is_covered(x, y):
                    if cliff_sky is None or cliff_sky[y, x]:
                        if opacity < 1.0:
                            amount = tuple(round(channel * opacity) for channel in amount)
                        canvas[x, y] = air.paler_than(tuple(canvas[x, y][:3]), amount, allow_same=opacity < 1.0)

    def draw(self, frame):
        """Only on the sky, and only where the frame still shows it: a gate or a tile
        coming down in front of the sky covers the stars too."""
        air, inks = self.air, self.air.inks
        canvas = frame.load()
        drawn = set()
        matches_sky = is_painted_sky if air.cliff_wind_sky is not None else is_sky
        for x, y, colour in self.sky_pixels():
            if air.in_sky(x, y) and ((x, y) in drawn or matches_sky(canvas[x, y])):
                canvas[x, y] = inks[colour]
                drawn.add((x, y))
        if self.clouds:
            colours = colours_of(air.palette_key)
            for cloud in self.clouds:
                self.draw_cloud(frame, cloud, colours)
            canvas = frame.load()
        self.put_grit(canvas, self.grit_pixels())
        self.draw_wind(canvas)
        if self.wind is not None and air.cliff_sand is not None:
            grains = opening_sand_pixels(self.wind.tick, air.cliff_sand)
            draw_sand_pixels(canvas, air, grains)
        self.put_grit(canvas, self.pebble_pixels())
        # Kept to find the Prince in once he is drawn, while anything could fall on him.
        self.before_actors = frame.copy() if self.watches_the_prince() else None
        return frame


# Each painted ledge has its own lip, grain count and shortest time in free fall.
CHASM_LEDGES = ((132, 241, 26, 23), (77, 284, 16, 17), (40, 325, 12, 12))
OPENING_LEDGES = ((388, 282, 15, 19), (377, 322, 10, 12))


def ledge_approach(points):
    """Sample a path that follows the ground of the painted ledge."""
    xs, ys = zip(*points)
    x = range(xs[0], xs[-1] + 1)
    return tuple(zip(x, numpy.interp(x, xs, ys).round().astype(int)))


# Ground paths start beyond the building's base and pass clear of the rock in the foreground.
OPENING_APPROACHES = (
    ledge_approach(((156, 317), (201, 310), (260, 303), (294, 291), (325, 281), (355, 279), (388, 282))),
    ledge_approach(((156, 332), (186, 321), (235, 318), (286, 320), (340, 318), (377, 322))),
)


def chasm_fall_pixels(tick, sand):
    return ledge_fall_pixels(tick, sand, CHASM_LEDGES)


def opening_sand_pixels(tick, sand):
    return ledge_fall_pixels(tick, sand, OPENING_LEDGES, approaches=OPENING_APPROACHES)


def ledge_fall_pixels(tick, sand, ledges, *, approaches=()):
    """Grains slide up to a painted lip, then accelerate down past it."""
    colours = (NEAR_SANDS[0], SAND[0], FAR_SANDS[1])
    for ledge, (lip_x, lip_y, grains, shortest_fall) in enumerate(ledges):
        approach = approaches[ledge] if approaches else ()
        for index in range(grains):
            life = shortest_fall + index * 7 % 10
            short_run = 6 + index * 3 % 9
            run = round(len(approach) / 2.65) if approach else short_run
            extra_run = run - short_run
            period = 54 + index * 11 % 25 + extra_run
            age = (tick + extra_run + ledge * 13 + index * 17) % period
            fall = age - run
            spread = index * 5 % 7 - 3
            ridge = lip_y + spread
            if fall >= life:
                continue
            if fall < 0:
                if approach:
                    x, y = approach[len(approach) * age // run]
                    y += spread
                else:
                    x, y = lip_x + round(1.65 * fall), ridge
                if sand[y, x]:
                    yield x, y, SAND[0]
                continue
            x = lip_x - 1 + index * 3 % 7 + round((0.21 + 0.09 * (index % 5)) * fall)
            y = ridge + round(0.35 * fall + (0.07 + 0.009 * (index % 4)) * fall ** 2)
            shade = min(2, fall * 3 // life)
            yield x, y, colours[shade]
            if index % 4 == 0 and 4 <= fall < 20:
                yield x, y - 2, colours[min(2, shade + 1)]


def draw_sand_pixels(canvas, air, pixels):
    """Draw sand in the room's palette, blended toward the scenery behind it."""
    drawn = {}
    for x, y, colour in pixels:
        if 0 <= x < WIDTH and 0 <= y < HEIGHT and not air.is_covered(x, y):
            drawn[x, y] = air.inks[colour][:3]
    for (x, y), colour in drawn.items():
        behind = tuple(canvas[x, y][:3])
        if colour != behind:
            canvas[x, y] = air.gentle(behind, colour)


CHASM_UPDRAFT_PATHS = tuple(winding_streak_path(*shape) for shape in (
    (322, 350, 115, 4, 2.65, 1),
    (340, 355, 110, 5, 2.75, -1),
    (312, 349, 108, 3, 2.55, 1),
))
CHASM_CROSSWIND_PATHS = tuple(winding_streak_path(*shape, horizontal=True) for shape in (
    (33, 218, 130, 4, 2.65, -1),
    (24, 219, 142, -3, 2.8, 1),
    (51, 225, 128, 3, 2.55, -1),
))
CHASM_UPDRAFT_PERIOD, CHASM_UPDRAFT_PHASE = 52, 24
CHASM_CROSSWIND_PERIOD, CHASM_CROSSWIND_PHASE = 63, 3


def chasm_updraft_pixels(tick):
    return chasm_wisp_pixels(
        tick, CHASM_UPDRAFT_PATHS, CHASM_UPDRAFT_PERIOD, CHASM_UPDRAFT_PHASE, direction=(0, -1),
    )


def chasm_crosswind_pixels(tick):
    return chasm_wisp_pixels(
        tick, CHASM_CROSSWIND_PATHS, CHASM_CROSSWIND_PERIOD, CHASM_CROSSWIND_PHASE, direction=(1, 0),
    )


def chasm_wisp_pixels(tick, paths, period, phase, *, direction):
    """Keep the wind cadence independent of how long each curl takes."""
    cycle, age = divmod(tick + phase, period)
    if age + period < CHASM_STREAK_STYLE.lifetime:
        path, turn = paths[(cycle - 1) % len(paths)]
        yield from winding_streak_pixels(path, turn, age + period, direction, CHASM_STREAK_STYLE)
    path, turn = paths[cycle % len(paths)]
    yield from winding_streak_pixels(path, turn, age, direction, CHASM_STREAK_STYLE)


def chasm_rising_sand_pixels(tick):
    """A few grains lift almost straight up inside the current."""
    for index in range(7):
        life = 25 + index * 5 % 8
        age = (tick + index * 19) % (55 + index * 7 % 23)
        if age >= life:
            continue
        x = 328 + index * 3 + round(math.sin(age * 0.19 + index))
        y = 289 + index * 3 - round((60 + index * 3) * age / life)
        yield x, y, SAND[min(2, age * 3 // life)]


@dataclass
class DesertWind:
    """One level-owned wind simulation. All sand coordinates are in the joined strip."""
    dunes: Dunes
    rng: random.Random = field(default_factory=random.Random)
    tick: int = field(default=0, init=False)
    desert_gusts: list = field(default_factory=list, init=False)
    spray: list = field(default_factory=list, init=False)
    blown: list = field(default_factory=list, init=False)
    streams: list = field(default_factory=list, init=False)
    devils: list = field(default_factory=list, init=False)
    # The Prince on the sand: his feet last tick (in the strip), the grains he kicks up,
    # his prints, the sand the wind takes off him, and where his last print is.
    footing: object = field(default=None, init=False)
    kicked: list = field(default_factory=list, init=False)
    prints: list = field(default_factory=list, init=False)
    shed: list = field(default_factory=list, init=False)
    last_print: object = field(default=None, init=False)

    def __post_init__(self):
        self.width = self.dunes.crest.size
        self.room_count = self.width // WIDTH
        # The gorge adds wind room without increasing the density of dust devils.
        self.devil_room_count = max(1, math.ceil(numpy.count_nonzero(self.dunes.crest > 0) / WIDTH))
        self.desert_gust_wait = self.rng.randint(*FIRST_DESERT_GUST)
        self.devil_wait = max(1, self.rng.randint(*FIRST_DEVIL) // self.devil_room_count)
        self.rocks_by_column = {}
        for rock in self.dunes.rocks:
            for column in rock.foot:
                self.rocks_by_column.setdefault(column, []).append(rock)

    def prime(self):
        """Start wind across the strip before anyone sees the first desert frame."""
        for origin in range(0, self.width, WIDTH):
            self.start_gust(self.new_gust(origin))
        for _ in range(24):
            self.advance()

    def advance(self):
        self.tick += 1
        rng, tick = self.rng, self.tick
        self.desert_gust_wait -= 1
        if self.desert_gust_wait <= 0:
            gap = rng.randint(*(GUST_SOON if rng.random() < SPELL_CHANCE else GUST_LULL))
            self.desert_gust_wait = gap // self.room_count
            self.start_gust(self.new_gust())
        self.desert_gusts = [gust for gust in self.desert_gusts if not gust.over(tick, self.width)]
        self.blow_the_crest()
        self.blow_the_plain()
        self.run_at_rocks()
        self.run_streams()
        self.advance_blown()
        self.advance_devils()
        self.advance_prince_sand()

    def on_sand(self, x, floor):
        x = int(x)
        return 0 <= x < self.width and 0 <= floor < HEIGHT and bool(self.dunes.sand[floor, x])

    def prince(self, footing, origin=0):
        """The Prince's feet this tick in the room that starts at origin in the strip, or
        None where he is not in the desert. Only read. Returns whether he is on its sand,
        where this sand takes the place of the puffs of dust his feet raise elsewhere."""
        if footing is not None:
            footing = replace(footing, x=footing.x + origin, foot=footing.foot + origin)
        last, self.footing = self.footing, footing
        if footing is None:
            self.last_print = None
            return False
        if not self.on_sand(footing.foot, footing.floor):
            return False
        if last is not None:
            for thud in footfalls(last, footing):
                self.kick(thud, footing.floor)
            if not (last.grounded or last.falling) and footing.on_floor:
                # Down from a jump, which the puffs do not count as a landing.
                self.kick(Thud(footing.foot - 3, footing.foot + 3, footing.floor, footing.floor, LANDING_PUFF),
                          footing.floor)
        if footing.on_floor:
            self.stamp(footing)
            self.shed_sand(footing)
        return True

    def kick(self, thud, floor):
        """The grains a step, a skid or a landing throws up."""
        rng = self.rng
        x = (thud.left + thud.right) / 2
        if thud.kind is STEP_PUFF:
            count, side, up = STEP_KICK, STEP_KICK_BACK, STEP_KICK_UP
        elif thud.kind is SKID_PUFF:
            count, side, up = SKID_KICK, SKID_KICK_AHEAD, SKID_KICK_UP
        else:
            count, side, up = LANDING_KICK, LANDING_KICK_SIDE, LANDING_KICK_UP
        for _ in range(rng.randint(*count)):
            way = thud.only or rng.choice((-1, 1))
            start = x if thud.only else x + way * LANDING_KICK_FROM
            self.kicked.append(Blown(start + rng.uniform(-1, 1), float(floor - 1), float(floor), 1.0,
                                     way * rng.uniform(*side), -rng.uniform(*up), KICK_FALL,
                                     rng.randint(*KICK_LIFE)))

    def stamp(self, footing):
        """A print where his foot has come down on a new place."""
        if self.last_print is not None and abs(footing.foot - self.last_print) < PRINT_APART:
            return
        self.last_print = footing.foot
        self.prints.append(Footprint(int(footing.foot), footing.floor, self.rng.randint(*PRINT_WIDTH),
                                     self.tick, self.rng.randint(*PRINT_HOLD)))

    def shed_sand(self, footing):
        """Sand off his legs and feet where a gust's front has just gone by him."""
        rng = self.rng
        for front, strength in self.fronts(GROUND_FRONT, 'plain'):
            if 0 <= front - footing.x <= SHED_BEHIND:
                for _ in range(some(rng, SHED_GRAINS, strength)):
                    y = footing.floor - 1 - rng.random() ** 1.6 * SHED_HIGH
                    self.shed.append(Blown(footing.x + rng.uniform(2, 6), y, float(footing.floor), 1.0,
                                           rng.uniform(*SHED_SPEED), rng.uniform(*SHED_LIFT), SHED_SETTLE,
                                           rng.randint(*SHED_LIFE)))

    def advance_prince_sand(self):
        for grains in (self.kicked, self.shed):
            kept = []
            for grain in grains:
                grain.x += grain.dx
                grain.y += grain.dy
                grain.dy += grain.settle
                if grains is self.kicked:
                    grain.dx *= KICK_DRAG
                grain.age += 1
                if grain.age < grain.life and grain.y < grain.start:
                    kept.append(grain)
            grains[:] = kept
        self.prints = [footprint for footprint in self.prints if footprint.pixels(self.tick)]

    def prince_pixels(self):
        """World (x, y, RGB) of the sand he kicks up and the wind takes off him."""
        for grain in self.kicked:
            yield int(round(grain.x)), int(round(grain.y)), NEAR_SANDS[min(2, grain.age * 3 // grain.life)]
        for grain in self.shed:
            x, y = int(grain.x), int(grain.y)
            step = min(2, grain.age * 3 // grain.life)
            yield x, y, NEAR_SANDS[step]
            if grain.dx > FAST_GRAIN and step < 2:
                yield x - 1, y, NEAR_SANDS[step + 1]

    def put_prints(self, canvas, air, origin=0):
        """The prints: a dent darker than the sand, darkest along its far side."""
        for footprint in self.prints:
            xs = footprint.pixels(self.tick)
            for row, amount, part in ((footprint.y, PRINT_SHADOW, xs[1:-1]), (footprint.y + 1, PRINT_DARKER, xs)):
                for x in part:
                    sx = x - origin
                    if not (0 <= sx < WIDTH and 0 <= row < HEIGHT) or air.is_covered(sx, row):
                        continue
                    if not self.on_sand(x, row):
                        continue
                    canvas[sx, row] = air.darker_than(tuple(canvas[sx, row][:3]), amount)

    def start_gust(self, gust):
        self.desert_gusts.append(gust)
        if gust.plain:
            rng = self.rng
            for _ in range(some(rng, STREAMS, gust.strength)):
                near = rng.random() ** 0.7
                self.streams.append(Stream(gust.born + rng.randrange(STREAM_DELAY), near,
                                           rng.uniform(gust.start - 20, gust.start + 0.4 * gust.reach),
                                           rng.uniform(*STREAM_FRONT),
                                           rng.uniform(*STREAM_TRAVEL) * min(1.0, gust.reach / 400),
                                           rng.uniform(0, 6.3)))

    def new_gust(self, origin=None):
        rng = self.rng
        pick, share = rng.random(), 0.0
        for chance, crest, plain in GUST_KINDS:
            share += chance
            if pick < share:
                break
        if origin is None and self.room_count > 1:
            start = rng.uniform(GUST_FROM[0], self.width - 120)
        else:
            start = (origin or 0) + GUST_FROM[0] + (GUST_FROM[1] - GUST_FROM[0]) * rng.random() ** 2
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
            if behind <= front <= self.width + ahead and strength > 0:
                yield front, strength

    def blow_the_crest(self):
        rng, crest = self.rng, self.dunes.crest
        for front, strength in self.fronts(CREST_FRONT, 'crest'):
            for _ in range(some(rng, CREST_GRAINS, strength)):
                x = int(front - rng.uniform(0, CREST_BEHIND))
                if 0 <= x < self.width and crest[x] > 0:
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
            if grain.age < grain.life and 0 <= x < self.width and grain.y < crest[x]:
                kept.append(grain)
        self.spray = kept

    def blow_the_plain(self):
        rng, dunes = self.rng, self.dunes
        for front, strength in self.fronts(GROUND_FRONT, 'plain', ahead=40):
            for _ in range(some(rng, GROUND_GRAINS, strength)):
                x = int(front - rng.uniform(0, GROUND_REACH))
                if not 0 <= x < self.width:
                    continue
                top = dunes.ground_top[x]
                y = int(top + rng.random() ** 0.8 * (HEIGHT - 4 - top))
                if not (0 <= y < HEIGHT and dunes.open_sand[y, x]):
                    continue
                near = (y - top) / (HEIGHT - top)
                self.blown.append(Blown(float(x), float(y), float(y), near, rng.uniform(*between(GROUND_SPEED, near)),
                                        -rng.uniform(*between(GROUND_LIFT, near)), GROUND_SETTLE,
                                        rng.randint(*map(round, between(GROUND_LIFE, near)))))

    def run_at_rocks(self):
        """While a gust's front reaches a big rock, sand runs along the ground at its foot."""
        rng, dunes = self.rng, self.dunes
        fronts = tuple(self.fronts(GROUND_FRONT, 'plain', behind=-45, ahead=5))
        if not fronts:
            return
        for rock in dunes.rocks:
            if len(rock.foot) < 4 or rock.size < BIG_ROCK:
                continue
            left = rock.left
            for front, strength in fronts:
                if left - 45 <= front <= left + 5:
                    top = dunes.ground_top[left]
                    for _ in range(some(rng, AT_ROCK, strength)):
                        y = rock.foot.get(left + 2, rock.foot[left]) + rng.randint(-3, 2)
                        near = min(1.0, max(0.0, (y - top) / (HEIGHT - top)))
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
            speed = tuple(far + near * stream.near for far, near in zip(STREAM_SPEED, STREAM_NEAR_SPEED))
            for _ in range(rng.randint(*STREAM_GRAINS)):
                x = front - rng.uniform(0, 16)
                if not 0 <= x < self.width:
                    continue
                top = self.dunes.ground_top[int(x)]
                y = int(top + stream.near * (HEIGHT - 6 - top)) + round(math.sin(x / 23 + stream.phase))
                if not (0 <= y < HEIGHT and self.dunes.open_sand[y, int(x)]):
                    continue
                self.blown.append(Blown(x, float(y), float(y), stream.near, rng.uniform(*speed),
                                        -rng.uniform(*STREAM_LIFT), STREAM_SETTLE, rng.randint(*STREAM_LIFE)))
        self.streams = kept

    def rock_hit(self, x, y, ground):
        """The rock a grain riding at ground row `ground` runs into at (x, y), if any."""
        if not 0 <= y < HEIGHT:
            return None
        for rock in self.rocks_by_column.get(x, ()):
            if rock.covers(x, y) and abs(rock.foot[x] - ground) <= FOOT_DEPTH:
                return rock
        return None

    def advance_blown(self):
        rng, kept = self.rng, []
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
            hidden = (grain.bounced and grain.age > 2 and 0 <= y < HEIGHT
                      and any(rock.covers(x, y) for rock in self.rocks_by_column.get(x, ())))
            landed = grain.y > grain.start + 0.5 and not grain.bounced
            if grain.age < grain.life and not landed and not hidden and 0 <= grain.x < self.width:
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
        crest = self.dunes.crest
        behind, ahead = devil.reach() if devil is not None else (0.0, DEVIL_DRIFT * DEVIL_LIFE)
        for _ in range(20):
            x = self.rng.uniform(DEVIL_FROM[0], self.width - (WIDTH - DEVIL_FROM[1]))
            way = crest[max(0, int(x + behind) - DEVIL_SMOOTH):int(x + ahead) + DEVIL_SMOOTH + 1]
            if len(way) and (way > 0).all() and numpy.abs(numpy.diff(way)).max(initial=0) <= DUNE_CREST_SPREAD:
                return x
        return None

    def advance_devils(self):
        if len(self.devils) < self.devil_room_count:
            self.devil_wait -= 1
            if self.devil_wait <= 0:
                self.devil_wait = self.rng.randint(*TICKS_BETWEEN_DEVILS) // self.devil_room_count
                devil = self.new_devil()
                start = self.devil_start(devil)
                if start is not None:
                    devil.start = start
                    self.devils.append(devil)
        self.devils = [devil for devil in self.devils if self.advance_devil(devil)]

    def advance_devil(self, devil):
        rng, tick = self.rng, self.tick
        strength = devil.strength(tick)
        base_x, base_y = devil.base(tick, self.dunes.crest)
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
        return bool(kept or devil.kicks or devil.thrown or tick - devil.born < devil.life)

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

    def desert_pixels(self, origin=0):
        """World (x, y, RGB) of the blown sand, the later over the earlier."""
        if self.room_count > 1:
            yield from self.breeze_pixels(origin)
        yield from self.devil_pixels(origin)
        yield from self.gust_pixels()
        yield from self.prince_pixels()

    def devil_pixels(self, origin):
        tick = self.tick
        for devil in self.devils:
            base_x, base_y = devil.base(tick, self.dunes.crest)
            if base_x + 45 < origin or base_x - 45 >= origin + WIDTH:
                continue
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

    def gust_pixels(self):
        for grain in self.spray:
            x, y = int(grain.x), int(grain.y)
            step = min(2, grain.age * 3 // grain.life)
            yield x, y, SAND[step]
            if grain.dx > FAST_GRAIN and step < 2 and x > 0:
                yield x - 1, y, SAND[step + 1]
        sand = self.dunes.sand
        for grain in self.blown:
            if grain.bounced:
                continue
            x, y = int(grain.x), int(grain.y)
            if not (0 <= x < self.width and 0 <= y < HEIGHT and sand[y, x]):
                continue
            steps = NEAR_SANDS if grain.near > 0.5 else FAR_SANDS
            step = min(2, grain.age * 3 // grain.life)
            yield x, y, steps[step]
            if grain.dx > FAST_GRAIN and step < 2 and x > 0 and sand[y, x - 1]:
                yield x - 1, y, steps[step + 1]
        for grain in self.blown:
            if grain.bounced:
                yield int(grain.x), int(grain.y), NEAR_SANDS[min(2, grain.age * 3 // grain.life)]

    def breeze_pixels(self, origin):
        """Light trails use the same world X and tick on both sides of a room cut."""
        dunes = self.dunes
        right = origin + WIDTH
        for depth, spacing, speed, phase in DUNE_BREEZE:
            head = origin + (self.tick * speed + phase - origin) % spacing
            colours = NEAR_SANDS if depth >= 0.49 else FAR_SANDS
            for front in range(head, right + BREEZE_TRAIL[-1][0], spacing):
                ripple = round(3 * math.sin(front / 37 + phase))
                for back, dy, shade in BREEZE_TRAIL:
                    x = front - back
                    if not origin <= x < right:
                        continue
                    top = int(dunes.ground_top[x])
                    y = top + round(depth * (HEIGHT - top - 8)) + ripple + dy
                    if 0 <= y < HEIGHT and dunes.open_sand[y, x]:
                        yield x, y, colours[shade]

    def put_sand(self, canvas, air, origin=0):
        """The blown sand, each pixel gentler: part of the way back to what it covers."""
        self.put_prints(canvas, air, origin)
        pixels = ((x - origin, y, colour) for x, y, colour in self.desert_pixels(origin))
        if air.chasm:
            pixels = chain(pixels, chasm_fall_pixels(self.tick, air.dunes.sand),
                           chasm_rising_sand_pixels(self.tick))
        draw_sand_pixels(canvas, air, pixels)
        if air.chasm:
            wisps = chain(chasm_updraft_pixels(self.tick), chasm_crosswind_pixels(self.tick))
            for x, y, amount in wisps:
                if 0 <= x < WIDTH and 0 <= y < HEIGHT and not air.is_covered(x, y):
                    canvas[x, y] = air.paler_than(tuple(canvas[x, y][:3]), amount)
