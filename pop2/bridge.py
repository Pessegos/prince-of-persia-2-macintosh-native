"""Level five's rope bridge (CODE 8 "Caverns"), independent of the window."""

from dataclasses import dataclass, field
import random


BRIDGE_LEVEL = 5
# The bridge state is hardwired to native room 10 (LEVL +0x21c/+0xbb8,
# TriggerBrgFloorMob 8:0c34-0c54); rooms 7 and 12 also run the check.
BRIDGE_ROOM = 9
CHECK_ROOMS = frozenset((6, 9, 11))
BRIDGE_ROW = 1
BRIDGE_TILE = 44
# a5-0x319a: per-column sag that OffsetBrgFloorY 8:07bc adds to each plank.
SAG = {1: 2, 2: 4, 3: 6, 4: 7, 5: 7, 6: 7, 7: 6, 8: 3}
# a5-0x3188/-0x316c/-0x3150: CUST record, Y and X draw offsets per mob frame.
# Frames 0-7 swing a plank that stays hanging; frames 8-13 drop it.
PLANK_FRAMES = ((7, 30, 26), (8, 29, 41), (6, 21, 40), (9, 6, 34), (6, 21, 40),
                (8, 29, 41), (7, 30, 26), (8, 29, 41), (7, 30, 26), (8, 29, 41),
                (6, 60, 38), (9, 75, 24), (3, 89, 29), (7, 154, 45))
HANGING, FALLING = 1, 2
CREAK_SOUND, BREAK_SOUND, BREAK_SONG = 122, 123, 121


def bridge_checked(level_number, room):
    # The Caverns frame hook 8:3b92 calls BridgeCheckBreak in these rooms.
    return level_number == BRIDGE_LEVEL and room in CHECK_ROOMS


def on_bridge(terrain, room, column, row):
    # 8:04e6: the character's stored cell, through room links (4:27ee).
    return terrain.tile(room, column, row).kind == BRIDGE_TILE


@dataclass
class Bridge:
    state: int = 0
    counter: int = 0
    pieces: dict = field(default_factory=dict)
    planks: list = field(default_factory=list)
    songs: list = field(default_factory=list)

    def blocks_turn(self, level_number, room):
        # Prince turn 6:26c0-26d8 and SwordCtrl's voluntary turn 6:2314-2330.
        return level_number == BRIDGE_LEVEL and room == BRIDGE_ROOM and self.state > 0

    def tile(self, room, cell, kind, foreground):
        # TriggerBrgFloorMob 8:0c3e-0c54 empties the cell and marks it custom.
        if room == BRIDGE_ROOM and cell // 10 == BRIDGE_ROW and cell % 10 in self.pieces:
            return 0, 0xc000
        return kind, foreground

    def fallen(self):
        return frozenset(self.pieces)

    def creak(self, prince, opponent, sound_playing, rng=None):
        # 8:0534-05ac: Rnd(40) with both characters on the bridge, Rnd(80)
        # with one, unless sound 122 is still playing.
        if prince is None and opponent is None or sound_playing:
            return ()
        rng = rng or random
        bound = 40 if prince is not None and opponent is not None else 80
        return (CREAK_SOUND,) if rng.randint(0, bound) == 0 else ()

    def check_break(self, prince, opponent, prince_selected, rng=None):
        """BridgeCheckBreak 8:002e-016c for one frame.

        `prince` and `opponent` are the stored columns of characters on a
        bridge tile, or None. Returns (sounds, push): `push` asks for the
        final AddCharX(17) of 8:0138-0150.
        """
        if self.state == 0:
            if prince is not None and opponent is not None:
                if abs(prince - opponent) <= 3:
                    self.counter += 1
                    if (self.counter >= 60 and 4 <= prince <= 6 and 5 <= opponent <= 6
                            and prince_selected != 85):
                        self.state = 1
                elif self.counter:
                    self.counter -= 1
            elif self.counter > 1:
                self.counter -= 2
            return (), False
        if self.state < 0:
            return (), False
        if self.state != 3:
            self.state += 1
            return (), False
        sounds = ()
        column = next((column for column in range(7, 2, -1) if column not in self.pieces), 2)
        if column >= 3:
            self.trigger(column, rng)
            if column == 7:
                sounds = (BREAK_SOUND,)
                self.songs.append(BREAK_SONG)
            if prince_selected != 85:
                return sounds, False
        self.state = -1
        return sounds, True

    def trigger(self, column, rng=None):
        # 8:0c94-0ccc: Rnd(1) chooses a falling plank (frame 8) or a hanging one.
        rng = rng or random
        kind = FALLING if rng.randint(0, 1) else HANGING
        self.pieces[column] = kind
        self.planks.append([column, 8 if kind == FALLING else 0])

    def advance_planks(self):
        # ATMBrgFloor/TriggerBrgFloorMob 8:0bbc-0c10: a hanging plank keeps
        # frame 7; a falling plank ends after frame 13.
        self.planks = [[column, frame if frame == 7 else frame + 1]
                       for column, frame in self.planks if frame != 13]

    def plank_drawings(self):
        # DrawObjBrgFloor 8:0b44: CUST record at the column X (a5-0x4b68) and
        # the row-1 floor (a5-0x4b4e = 245) lowered by the column's sag.
        for column, frame in self.planks:
            record, dy, dx = PLANK_FRAMES[frame]
            yield record, 51 * column + dx, 245 + SAG[column] + dy - 1


def bridge_sag(terrain, room, column, row, action):
    # 8:063e-067a: on a bridge tile, outside jump frames 34-44, a character's
    # Y follows the plank's sag.
    if not on_bridge(terrain, room, column, row) or 34 <= action <= 44:
        return 0
    tile = terrain.tile(room, column, row)
    return SAG.get(tile.column, 0)
