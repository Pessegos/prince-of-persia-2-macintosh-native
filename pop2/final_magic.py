"""The Prince's magic in the final tower: the shadow form and the fireball.

Environment 6 (level 14). Rapid standing turns (CODE 4:1fb2, counted in
a5-0x5004) cost life and capacity from the fourth; the eighth, with life
to spare, leaves the body behind (4:2206) and makes the Kid record the
shadow (actor type 1, draw mode 0x30, CTBL 2001 at palette 48). While the
shadow's life is above 2 it carries the magic fire: in the palace (native
rooms 7/8) the sword key casts SEQS 242 (9:2674), whose pose 281 throws a
fireball (9:2868). The fireball (ATM 9:27a0, wall test 9:25e4) burns
Jaffar (9:24ee): SEQS 230, whose mode-12 ending advances the level.
Crouching beside the body (4:1f1e) lies down in it; the shadow's dead
pose next to the body rejoins it (6:0b5a, 4:25ce).

Port facing 1 is the native facing word 0 (right).
"""

from dataclasses import dataclass

from pop2.sequence_runtime import SequenceState

TURN_SEQUENCE = 5
TURN_POSES = range(46, 52)     # 4:250a: 0x2d < pose < 0x34
TURN_FIRST_POSE, TURN_LAST_POSE = 45, 52   # 4:2188-2196
STANDING_POSE = 15
COLLAPSE_SEQUENCE = 71         # SEQS 71: pose 179, then SEQS 213 to 185
DEAD_POSE = 185
REJOIN_SEQUENCE = 231          # rise from the body (4:260e)
CAST_SEQUENCE = 242
CAST_POSES = range(272, 282)   # 6:0732-0742: 0x110-0x119
THROW_POSE = 281
BURN_SEQUENCE = 230
SHADOW_PALETTE, GLOW_PALETTE = 2000, 2001
TURN_SOUND = 288               # 4:2098: AddSound(0x120) for turns >= 4
TRANSFORM_SOUND, TRANSFORM_SONG = 260, 290
CAST_SONG = 265                # 9:26aa: AddSong(0x109)
FIREBALL_SOUND, WALL_SOUND, BURN_SOUND = 258, 259, 289
FLYING_SHAPE, BURST_SHAPE = 4115, 4119   # 9:275c: 0x1013 / 0x1017 + frame
SHAPE_FRAMES = 4
# 4:1f1e: crouching within 51 pixels of the body lies down on it; 6:0bc0:
# the dead pose within 2 pixels rejoins it.
BODY_REACH, REJOIN_REACH = 51, 2
# 9:2674: casting needs life above 2 and costs 2 (DecLifePts(2)).
CAST_LIFE, CAST_COST = 2, 2
# 4:2046: the eighth turn transforms when life is above 4.
TRANSFORM_TURNS, TRANSFORM_LIFE, GLOW_TURNS = 8, 4, 4
FIREBALL_START_SPEED, FIREBALL_ACCELERATION, FIREBALL_TOP_SPEED = 12, 3, 25
FIREBALL_REACH = 17            # 9:256e-2586: a 34-pixel span around it
ROOM_WIDTH = 510
# 9:0062: the defeated Kid lies in native room 11 (port 10), column 6
# (a5-0x4b88[6] = 513, scene X 306), row 2 (Y 2 * 120 + 112 = 352).
DEFEAT_ROOM, DEFEAT_COLUMN, DEFEAT_ROW = 10, 6, 2
DEFEAT_FRAMES = 5              # 9:00b2-00be: AnimChar five times


def turn_flash(pose, turns):
    """4:250a: whether this turn pose draws the shadow colours (draw mode
    0x30) once the turns reach four."""
    if turns < GLOW_TURNS or pose not in TURN_POSES:
        return False
    extra, phase = turns - GLOW_TURNS, pose - 46
    if extra < 2:
        return phase % (3 - extra) == 0
    return (phase + 1) % 3 != 0


def count_turn_frame(magic, pose, selected, room):
    """4:2174, GenCtrl's turn count for the Kid each frame (port room).
    Standing (pose 15) clears the count; a turn pose (45-52) outside native
    rooms 1/2 flashes once it reaches four (4:250a, draw mode 0x30); any
    other pose outside SEQS 5 clears it and restores the palette (3:5f1c)."""
    if pose == STANDING_POSE:
        magic.turns, magic.flash = 0, False
    elif TURN_FIRST_POSE <= pose <= TURN_LAST_POSE and room not in (0, 1):
        if magic.turns >= GLOW_TURNS:
            magic.flash = turn_flash(pose, magic.turns)
    elif selected != TURN_SEQUENCE and magic.turns:
        magic.turns, magic.flash = 0, False


def glow_palette(life, imbued=False):
    """IsShadowImbued 4:2590 in environment 6: life above 2 (or mode 13)."""
    return GLOW_PALETTE if imbued or life > CAST_LIFE else SHADOW_PALETTE


def body_distance(shadow, body, body_row, shadow_row):
    """4:24b2: X distance to the body on the same row, 6 more when both face
    the same way (unless the shadow lies in pose 185); 999 otherwise."""
    if shadow_row != body_row:
        return 999
    distance = shadow.target_x - body.target_x
    if shadow.facing == body.facing and shadow.action != DEAD_POSE:
        # a5-0x4b94 by facing word: 0 (right) -1, -1 (left) +1.
        distance += (-1 if shadow.facing else 1) * 6
    return distance


@dataclass
class Body:
    """The Prince's body, left lying where he transformed (4:2206)."""
    state: SequenceState
    room: int
    row: int


@dataclass
class Fireball:
    """The magic fire object (a5-0x44a6 X, -44a4 Y, -44a2 room, -449e
    speed, -4498 frame/burst state). X is port drawing X."""
    room: int
    x: int
    y: int
    row: int
    speed: int
    frame: int = 0
    burst: bool = False
    active: bool = True

    @property
    def shape(self):
        return (BURST_SHAPE if self.burst else FLYING_SHAPE) + self.frame


@dataclass
class FinalMagic:
    turns: int = 0
    flash: bool = False
    shadow: bool = False
    body: Body | None = None
    fireball: Fireball | None = None
    palette: int = GLOW_PALETTE
    # A turn chosen at pose 15 this frame: GenCtrl's 4:2174 ran before it.
    fresh_turn: bool = False


# 9:2880-28d8 starts the fire in state 2 (frame 2, not bursting).
THROWN_FRAME = 2


def throw_fireball(state, room, row, floor):
    """9:2880: X = AddCharX(43) - 207, Y = Y - 55, speed 12 along the facing,
    state 2. The caller then runs the wall test 9:25e4 (`fire_hits_wall`)."""
    direction = 1 if state.facing else -1
    return Fireball(room, state.target_x + 43 * direction, floor + state.current_y - 55, row,
                    FIREBALL_START_SPEED * direction, frame=THROWN_FRAME)


def fire_hits_wall(ball, wall_column, width, sounds, resets):
    """9:25e4: the cell at X - 22 + width ahead (X - 22 - width flying
    left); divs truncates, then a negative X steps one column left. A wall
    aligns the burst to the cell, plays sound 259 and resets the cast's
    song 265 (PrinceResetSnd 5:5252)."""
    lead = ball.x - 22 + width
    if ball.speed < 0:
        lead -= 2 * width
    column = int(lead / 51)
    if lead < 0:
        column -= 1
    if not wall_column(ball.room, column, ball.row):
        return False
    ball.x = column * 51 + 22 + (51 if ball.speed < 0 else 0)
    ball.burst, ball.frame = True, 0
    sounds.append(WALL_SOUND)
    resets.append(CAST_SONG)
    return True


def advance_fireball(ball, wall_column, width=0, resets=None):
    """ATM 9:27a0 for one frame. ``wall_column(room, column, row)`` is IsWall
    for the cell (columns outside 0-9 belong to the side rooms); ``width``
    is the last drawn image's width (a5-0x44e4, 9:24b6). Returns the sounds
    and whether the fire ended this frame; ``resets`` receives the cues
    PrinceResetSnd 5:5252 stops (258 when the fire leaves the level, 265
    at a wall)."""
    sounds = []
    resets = [] if resets is None else resets
    if not ball.active:
        return sounds, False
    if ball.burst:
        if ball.frame >= SHAPE_FRAMES - 1:
            ball.active = False
            return sounds, True
        ball.frame += 1
        return sounds, False
    if ball.speed > 0:
        if ball.speed < FIREBALL_TOP_SPEED:
            ball.speed += FIREBALL_ACCELERATION
    elif ball.speed > -FIREBALL_TOP_SPEED:
        ball.speed -= FIREBALL_ACCELERATION
    ball.x += ball.speed
    if ball.room is None:
        ball.active = False
        resets.append(FIREBALL_SOUND)
        return sounds, True
    if fire_hits_wall(ball, wall_column, width, sounds, resets):
        return sounds, False
    ball.frame = (ball.frame + 1) % SHAPE_FRAMES
    sounds.append(FIREBALL_SOUND)
    return sounds, False


def fireball_hits(ball, target_row, left, right, neighbor_offset):
    """9:24ee: the fire's span [x + speed - 17, x + speed + 17] against the
    target's edges (drawing X, inclusive), in the target room's X."""
    if not ball.active or ball.burst or ball.row != target_row:
        return False
    x = ball.x + ball.speed + neighbor_offset
    return x + FIREBALL_REACH > left and x - FIREBALL_REACH <= right
