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
    # SetTensionLevel 6:5022 (a5-0x36a2 level, a5-0x36a0 amount).
    tension_level: int = 0
    tension: int = 0
    # a5-0x3134: plank columns 1-8 (bits 0-7) near a character on the bridge,
    # and each wobbling plank's foreground nibble (1 up, 2 down).
    marks: int = 0
    wobble: dict = field(default_factory=dict)

    def set_tension(self, level, amount):
        if self.tension_level != level:
            if {self.tension_level, level} == {2, 3}:
                self.tension -= 10
            else:
                self.tension = 0
            self.tension_level = level
        self.tension = max(0, self.tension + amount)

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

    def mark(self, prince, opponent):
        # 8:0534-057c: both characters on the bridge mark every plank; one
        # marks its column and both neighbours (MarkBridgeForCol 8:05cc).
        if prince is not None and opponent is not None:
            self.marks = 0xff
            return
        column = prince if prince is not None else opponent
        self.marks = 0 if column is None else sum(
            1 << (current - 1) for current in range(max(column - 1, 1), min(column + 1, 8) + 1))

    def advance_wobble(self, rng=None):
        """ATMBrgFloor 8:06d8 for each plank trob of room 10 on screen.

        A marked plank at rest wobbles (nibble Rnd(3) - 1) when Rnd(3) >= 2;
        any wobbling plank returns to rest the next frame.
        """
        rng = rng or random
        for column in range(1, 9):
            previous = self.wobble.pop(column, 0)
            if column in self.pieces or not self.marks & (1 << (column - 1)):
                continue
            roll = rng.randint(0, 3)
            if roll > 1 and not previous:
                self.wobble[column] = roll - 1

    def creak(self, prince, opponent, sound_playing, rng=None):
        # 8:0534-05ac: Rnd(40) with both characters on the bridge, Rnd(80)
        # with one, unless sound 122 is still playing.
        self.mark(prince, opponent)
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


def bridge_sag(terrain, room, column, row, action, record=None):
    # 8:063e-067a: on a bridge tile, outside jump frames 34-44, a character's
    # Y follows the plank's sag; 8:0682-06be: on a floor pose (frame flag
    # 0x40) a wobbling plank also moves him up (nibble 1) or down (2).
    if not on_bridge(terrain, room, column, row) or 34 <= action <= 44:
        return 0
    tile = terrain.tile(room, column, row)
    sag = SAG.get(tile.column, 0)
    caverns = getattr(terrain, 'caverns', None)
    if record is not None and record.aux & 0x40 and caverns is not None:
        sag += {1: -1, 2: 1}.get(caverns.bridge.wobble.get(tile.column), 0)
    return sag


def bridge_column(room, column):
    # BridgeGetCharCol 8:0188: rooms 7 and 12 continue room 10's columns.
    return column - 10 if room == 6 else column + 10 if room == 11 else column


def bridge_engage(room, column, facing_right, x, opponent_room, opponent_column, opponent_x,
                  opponent_armed, gate_open, tension_level, tension):
    """8:02ae: may a character in the bridge rooms press forward?

    Facing left, from bridge column 8 on. Facing right, from a column below
    2, when the opponent stands behind room 7's open gate (8:0424: bridge
    column below 2), or against an armed opponent less than 204 pixels
    ahead in its own column 6 or lower while the bridge tension is level 2
    with at least 20. Rooms and columns are port numbers."""
    own = bridge_column(room, column)
    if not facing_right:
        return own >= 8
    if own < 2 or gate_open and bridge_column(opponent_room, opponent_column) < 2:
        return True
    return (opponent_armed and -204 < x - opponent_x < 0 and opponent_column <= 6
            and tension_level == 2 and tension >= 20)


def bridge_gate_open(terrain):
    # IsBrgGateOpen 8:0458: room 7's gate (cell 13) has a trob in phase 0 or 2.
    caverns = getattr(terrain, 'caverns', None)
    return caverns is not None and caverns.plates.active.get((6, 13)) in (0, 2)


def bridge_tension(terrain):
    caverns = getattr(terrain, 'caverns', None)
    return (caverns.bridge.tension_level, caverns.bridge.tension) if caverns is not None else (0, 0)
