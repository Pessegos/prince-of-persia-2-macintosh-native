"""Checkpoint records and ordinary death/retry bookkeeping."""

from copy import deepcopy
from dataclasses import dataclass
import struct

from pop2.opponent_generation import character_column


DEAD_POSES = frozenset((185, 242, 243, 271, 266))


@dataclass(frozen=True)
class Checkpoint:
    slot: int
    room: int
    tile: int

    @property
    def row(self):
        return self.tile // 10

    @property
    def x(self):
        # SetKidDefaults 2:5d50: tile anchor +22, without opening adjustment.
        return self.tile % 10 * 51 + 22

    def matches(self, room, row, contact_x, animation_state, alive,
                level_number=1, story_flag=0):
        # SaveRebirthPt 2:6b46 rejects ordinary falling and dead actors.
        return (alive and animation_state != 4 and self.room == room
                and self.tile == row * 10 + character_column(contact_x)
                and not (level_number == 8 and room == 8 and story_flag != 1))


def level_checkpoints(level):
    records = struct.unpack_from(">4h", level, 0x39a6)
    return tuple(Checkpoint(slot + 1, room - 1, tile)
                 for slot, (room, tile) in enumerate(zip(records[::2], records[1::2]))
                 if 1 <= room <= 32 and 0 <= tile < 30)


@dataclass
class RebirthSnapshot:
    checkpoint: Checkpoint
    facing: int
    max_life: int
    room_encounters: dict

    @classmethod
    def capture(cls, checkpoint, combat):
        world = deepcopy(combat.room_encounters, {id(combat.sequences): combat.sequences})
        return cls(checkpoint, combat.player.state.facing, combat.player.max_life, world)

    def restore_world(self, combat):
        combat.reset()
        combat.room_encounters = deepcopy(
            self.room_encounters, {id(combat.sequences): combat.sequences})
        combat.player.max_life = combat.player.life = self.max_life


@dataclass
class DeathState:
    counter: int = -1
    method: int = 0
    prompt_visible: bool = False

    def begin(self, method):
        if self.counter < 0:
            self.counter = 0
            self.method = method

    @property
    def can_restart(self):
        # ReadKeyboard 2:47e6 tests the copied death counter >6.
        return self.counter > 6

    def advance(self, action, interval, audio=None):
        if self.counter < 0 or action not in DEAD_POSES:
            return
        if audio is not None and not audio.death_ready():
            return
        if self.counter < 6:
            self.counter += 1
        elif self.counter == 6:
            if audio is not None:
                audio.death_song(self.method)
            self.counter = 7
        elif self.counter == 7:
            finished = audio is None or (not audio.music_busy and not audio.effect_busy)
            if finished:
                self.prompt_visible = True
                self.counter = 8
