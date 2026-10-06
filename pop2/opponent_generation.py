"""Native ordinary-opponent generation points, for the supported rooftop row."""

from dataclasses import dataclass
import struct

from pop2.enemy_profiles import ENEMY_DATA


# CODE:3 IsWall / IsObstacle / IsEmpty; ordinary rooftop actors only.
WALL_TILES = frozenset((20, 2, 7, 25, 43))
OBSTACLE_TILES = frozenset((11, 15, 26, 12, 13, 24))
EMPTY_TILES = frozenset((0, 9, 27, 47, 49))


def character_column(scene_x):
    # CODE:4 0x3ad6 -> CODE:5 0x48b0, signed division towards zero.
    value = scene_x + 185
    numerator = value - 4
    quotient = abs(numerator) // 51
    if numerator < 0:
        quotient = -quotient
    return quotient - 4 - int(value < 0)


def tile_kind(level, room, column, row):
    while not 0 <= column < 10 or not 0 <= row < 3:
        if row < 0:
            link, row = 4, row + 3
        elif row >= 3:
            link, row = 6, row - 3
        elif column < 0:
            link, column = 0, column + 10
        else:
            link, column = 2, column - 10
        room = struct.unpack_from(">H", level, 0x2080 + room * 8 + link)[0] - 1
        if room < 0:
            return 20
    return struct.unpack_from(">H", level, room * 60 + (row * 10 + column) * 2)[0]


def first_wall_column(level, room, column, row, direction):
    # CODE:5 0x2198; IsWall at CODE:3 0x4ef2.
    while True:
        column += direction
        if tile_kind(level, room, column, row) in WALL_TILES:
            return column
        if column < -1 or column > 10:
            return column


@dataclass
class OpponentGenerationPoint:
    room: int
    index: int
    skill: int
    row: int
    column: int
    countdown: int
    repeat_wait: int
    alternate_row: int
    remaining: int
    max_between: int
    flags: int
    life_word: int

    @classmethod
    def from_level(cls, level, room):
        start = 0x3986 + (room + 1) * 0x44
        count, skill = struct.unpack_from(">2h", level, start)
        if not 0 <= count <= 3 or not 0 <= skill < 12:
            raise ValueError("Invalid ordinary-opponent generation header")
        points = []
        for index in range(count):
            fields = struct.unpack_from(">10h", level, start + 8 + index * 20)
            if not 0 <= fields[3] < 10:
                raise ValueError("Invalid generation column")
            points.append(cls(room, index, skill, fields[2], fields[3],
                              fields[4], fields[5], fields[7], fields[8],
                              fields[1], fields[6], fields[9]))
        return points

    @property
    def x(self):
        return ENEMY_DATA["generation_native_x"][self.column] - 207

    @property
    def facing(self):
        return int(self.column <= 5)

    @property
    def life(self):
        # GenerateOpponent 0x3bb8-0x3bc4; unlike InitOpps, no default of 3.
        return self.life_word & 15

    @property
    def tumble_enabled(self):
        # IsOppGenPtWithTumbleOn, CODE:6 0x40b6: packed LIFE, not flags.
        return bool(self.life_word & 0x80)

    def eligible(self, player, guards, frame, level):
        # IsActiveOppGenPt 0x3daa and IsTimeToGenOpp 0x3e0a.
        if (not player.alive or player.state.actor_type == 1
                or player.room != self.room or len(guards) >= 5
                or frame % 3 == 0 or self.remaining == 0
                or player.row not in (self.row, self.alternate_row)):
            return False
        player_column = character_column(player.state.target_x)
        if abs(self.column - player_column) <= 2:
            return False
        wall = first_wall_column(level, self.room, self.column, self.row,
                                 1 if self.column < 5 else -1)
        between = 0
        for guard in guards:
            if not guard.alive or abs(guard.row - player.row) > 1:
                continue
            if not (self.column < player_column and guard.state.target_x < player.state.target_x
                    or self.column > player_column and guard.state.target_x > player.state.target_x):
                continue
            if min(self.column, player_column) <= wall <= max(self.column, player_column):
                continue
            between += 1
            if between >= self.max_between:
                return False
            guard_column = character_column(guard.state.target_x)
            if (self.column < player_column and self.column >= guard_column
                    or self.column > player_column and self.column > guard_column):
                return False
        return True

    def advance(self, player, guards, frame, level):
        if not self.eligible(player, guards, frame, level):
            return False
        # CheckOppGenPts 0x3a48-0x3a68 only counts eligible world frames.
        if self.countdown:
            self.countdown -= 1
            return False
        self.countdown = self.repeat_wait
        self.remaining -= 1
        return True
