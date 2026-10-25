"""Ruins special opponents (opponent set 5): heads and serpents.

Data and initialization; pop2/ruins_ai.py runs the controllers
(docs/research/ruins-head-leaves.md and level7-head-*.md).
"""

from dataclasses import dataclass
import struct

from pop2.coordinates import native_room, scene_x

# InitOpps 6:2bd2-2c0e: sets 5/6 keep the record kind (+0x18), which the
# DATA table a5-0x5280 turns into the working actor type.
ACTOR_TYPES = (2, 10, 4, 6, 1, 7, 8, 2, 11, 12, 0, 10)
HEAD_TYPES = (7, 8)
SERPENT_TYPE = 11
# ChompAgain 7:0494: bite-count bounds by record skill (+6).
CHOMP_LOWER = (1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 99)
CHOMP_UPPER = (1, 1, 2, 2, 2, 3, 3, 3, 3, 4, 4, 99)
# Flee 7:0d1c-0d7a: rest frames after returning, by skill (a5-0x2ca2).
FLEE_REST = (70, 65, 60, 55, 50, 45, 40, 35, 30, 25, 20, 15)


@dataclass(frozen=True)
class RuinsSpawn:
    """One opponent-set-5 generator record of a room (38 bytes at LEVL
    0x20e6 + native room * 0xc0 + 2)."""
    room: int
    slot: int
    row: int
    native_x: int
    kind: int
    actor_type: int
    skill: int
    sequence_id: int
    mode: int
    words: tuple

    @property
    def column(self):
        # GetCharCol (4:3ad6 -> 5:48b0) of the record X.
        from pop2.opponent_generation import character_column

        return character_column(scene_x(self.native_x))


def ruins_spawns(level, room):
    """The room's head and serpent records (LEVL +0x21a4 == 5), else ()."""
    if struct.unpack_from('>h', level, 0x21a4)[0] not in (5, 6):
        return ()
    offset = 0x20e6 + native_room(room) * 0xc0
    count = struct.unpack_from('>H', level, offset)[0]
    spawns = []
    for slot in range(count):
        words = struct.unpack_from('>19h', level, offset + 2 + slot * 38)
        kind = words[12]
        actor_type = ACTOR_TYPES[kind] if 0 <= kind < len(ACTOR_TYPES) else None
        if actor_type not in (*HEAD_TYPES, SERPENT_TYPE):
            raise ValueError(f'Unsupported ruins opponent kind {kind}')
        spawns.append(RuinsSpawn(room, slot, words[0] // 10, words[1], kind, actor_type,
                                 words[3], words[4], words[14], words))
    return tuple(spawns)


@dataclass
class RuinsStart:
    """HeadAddOpponent 7:0574's result for a live (negative ALIVE) actor."""
    x: int
    facing: int
    sequence_id: int
    mode: int
    armed: bool
    special: int = 0
    sound: int | None = None


def initial_state(spawn):
    """HeadAddOpponent 7:05f6-0628 (heads) and 7:0596-05f4 (serpents)."""
    if spawn.actor_type in HEAD_TYPES:
        # Column anchor + 47, facing left (native -1), SEQS 130, unarmed,
        # mode 0. Port facing 0 is left.
        return RuinsStart(scene_x(207 + spawn.column * 51 + 47), 0, 130, 0, False)
    if spawn.mode <= 0:
        return RuinsStart(scene_x(spawn.native_x), 0, 170, -1, True, sound=128)
    return RuinsStart(scene_x(spawn.native_x), 0, 175, spawn.mode, True, special=6, sound=128)


def frame_index(actor_type, pose):
    """LoadFrame 4:2a8e's Head FRAM record for a pose (149-289)."""
    if not 149 <= pose <= 289:
        raise ValueError(f'Pose {pose} is outside the Head frames')
    # The type-8 head uses the second set of early poses.
    return pose - 149 + (43 if actor_type == 8 and pose <= 181 else 0)


def chomp_again(bites, skill, wounds, rnd):
    """ChompAgain 7:0494: bite again? `wounds` is a5-0x36a0; `rnd(n)` is
    the original inclusive Rnd(n)."""
    level = 2 if wounds > 30 else 1 if wounds > 20 else 0
    if bites < CHOMP_LOWER[skill] - level:
        return True
    if bites >= CHOMP_UPPER[skill] - level:
        return False
    return bool(rnd(1))
