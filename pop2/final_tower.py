"""CODE 9's final-tower controller for Jaffar's type-6 figures.

Environment 6 (level 14). AutoCtrl 6:4efe sends actor type 6 to 9:08e8,
which runs 9:1526 for the false Princes of native room 6 and 9:16fe (the
path controller) everywhere else. CheckStab 6:52b8-52ca makes any hit by
or on a type-6 figure fatal (100 points); its kill routine 6:55ca selects
SEQS 196 for a type-6 victim, and 6:56a6 calls AllOtherJaffarsShimmerAway
9:090e when a type-6 figure kills the Prince.

Port facing 1 is the native facing word 0 (right).
"""

from dataclasses import dataclass

COPY_TYPE = 6
COPY_ROOM = 5          # native room 6
FINAL_ROOM = 7         # native room 8, the palace's right view
# 9:19fa: native X 1132 in room 6's coordinates, less the room width 510.
FINAL_START_X = 622 - 207
STRIKE_SEQUENCE = 75   # SEQS 75: pose 151, then the strike 203
SHEATHE_SEQUENCE = 92
LAUGH_SEQUENCE = 197
LAUGH_SOUND = 261
RISE_SEQUENCE = 49
SHIMMER_SEQUENCE = 240   # nine idle poses, then 196
DISSOLVE_SEQUENCE = 196  # sound 260, poses 301-305, then -17 (removal)
# SetKidDeathMethod for a type-6 killer (CheckStab's table at 6:570e).
COPY_DEATH_METHOD = 17
FATAL_DAMAGE = 100
# FRAM +8 flag 0x40 (Kid handle a5-0x3472); poses 191-205 also qualify.
FRAME_FLAG_EXPOSED = 0x40


@dataclass(frozen=True)
class PrinceView:
    """The fields of the saved Prince (a5-0x50d2) and the opponent record
    (a5-0x5094) that 9:1526 reads. ``alive`` is native ALIVE: -1 while
    living, then the death counter."""
    alive: int
    selected_sequence: int
    actor_type: int
    action: int
    animation_state: int
    facing: int
    room: int
    row: int
    x: int


def prince_exposed(pose, frames):
    # 9:15c8-1602: FRAM flag 0x40, or poses 0xbf-0xcd.
    flags = frames[pose].aux if 0 <= pose < len(frames) else 0
    return bool(flags & FRAME_FLAG_EXPOSED) or 191 <= pose <= 205


def copy_distance(copy, prince):
    """CharDistance 4:49ee with the Prince as the opponent record."""
    if copy.room != prince.room or copy.row != prince.row:
        return 999
    distance = prince.x - copy.state.target_x
    if not copy.state.facing:
        distance = -distance
    if distance >= 0 and copy.state.facing != prince.facing:
        distance += 21
    return distance


@dataclass
class CopyDecision:
    sequence: int | None = None
    sound: int | None = None
    sword_drawn: bool | None = None
    turn: bool = False
    x_offset: int = 0


def copy_control(copy, prince, count, frames):
    """9:1526: one AutoCtrl decision for a false Prince in native room 6.

    ``count`` is the room's bank count (level +0x20e6 + room * 0xc0),
    which includes this figure. Returns a CopyDecision; the caller turns,
    moves (AddCharX 4:2bae), arms and selects the sequence."""
    decision = CopyDecision()
    if not copy.alive:
        return decision
    if prince.actor_type == 1:
        # 9:1568-1572: the shadow does not count against the figures.
        count -= 1
    if (count == 1 and copy.state.selected_sequence_id != SHIMMER_SEQUENCE
            and prince.alive < 0):
        # 9:1574-1594: the last figure shimmers away.
        decision.sequence = SHIMMER_SEQUENCE
        return decision
    pose = copy.state.action
    if pose == 15:
        if (prince.alive >= 0 or prince.selected_sequence in (44, 6)
                or prince.actor_type != 0 or not prince_exposed(prince.action, frames)
                or prince.animation_state in (3, 4)):
            return decision
        distance = copy_distance(copy, prince)
        strike = False
        if copy.state.facing == prince.facing:
            # 9:162a-163a: behind him, 25..70 after removing 15.
            strike = 24 < distance - 15 < 71
        elif distance < 0:
            # 9:164c-1664: he is behind; the figure turns to strike.
            strike = 24 < -15 - distance < 71
            decision.turn = strike
        elif prince.action == 145:
            # 9:1668-1680: facing him while he lands from a jump (pose 0x91).
            strike = 24 < distance - 15 < 78
        if strike:
            # 9:1686-16a2: AddCharX(15), sword drawn, SEQS 75.
            decision.x_offset = 15
            decision.sword_drawn = True
            decision.sequence = STRIKE_SEQUENCE
        return decision
    if pose == 171:
        # 9:16a6-16be: en garde puts the sword away.
        decision.sword_drawn = False
        decision.sequence = SHEATHE_SEQUENCE
    elif pose == 52 and prince.alive > 0:
        # 9:16c0-16e4: after the Prince's death the figure laughs.
        decision.sequence = LAUGH_SEQUENCE
        decision.sound = LAUGH_SOUND
    elif pose == 109:
        # 9:16e6-16f2: a landed figure stands up.
        decision.sequence = RISE_SEQUENCE
    return decision


def shimmer_others(copies, killer):
    """AllOtherJaffarsShimmerAway 9:090e: every other idle figure (pose 15)
    of the killer's room bank selects SEQS 240."""
    shimmered = []
    for copy in copies:
        if (copy is not killer and copy.state.actor_type == COPY_TYPE
                and copy.state.action == 15):
            shimmered.append(copy)
    return shimmered
