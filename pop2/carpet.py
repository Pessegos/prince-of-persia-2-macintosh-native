"""Level five's flying carpet in room 3 (CODE 8 "Caverns"), window-free."""

from dataclasses import dataclass


CARPET_LEVEL = 5
CARPET_ROOM = 2
CARPET_TILE = 18
SIT_SEQUENCE, CRASH_SEQUENCE = 128, 129
RIDE_FRAME = 295
# a5-0x311c/-0x311e: the unused carpet lies at X 149, bottom 363 (shape 9).
STATIC_X, STATIC_BOTTOM, STATIC_SHAPE = 149, 363, 25312
SHAPE_BASE = 25303
# a5-0x311a: shape offsets by carpet frame; a5-0x3104: (dy, dx) per frame.
SHAPES = (0, 0, 1, 2, 3, 4, 5, 6, 7, 15, 15)
OFFSETS = ((0, 0), (11, -68), (13, -67), (15, -60), (15, -63), (13, -59), (11, -62),
           (13, -59), (17, -59), (9, -69), (8, -69))
OPEN_SONG, CLOSED_SONG, CRASH_SOUND = 115, 116, 117
CRASH_Y = 100


def carpet_room(level_number, room):
    return level_number == CARPET_LEVEL and room == CARPET_ROOM


@dataclass
class Carpet:
    counter: int = 0
    crashed: bool = False

    def frame(self):
        # 8:11e4-1238.
        if self.crashed:
            return min(self.counter + 8, 10)
        return self.counter % 9 if self.counter < 9 else self.counter % 6 + 3

    def sit_x(self, facing):
        # 8:14be-14ce: native X 425 (+30 facing right), less the 207 origin.
        return 218 + (30 if facing else 0)

    def drawing(self, x, y, facing):
        """SetupCarpet 8:12d6-1334: shape and top-left beneath a riding Prince."""
        index = self.frame()
        dy, dx = OFFSETS[index]
        return SHAPE_BASE + SHAPES[index], x + dx - (30 if facing else 0), y + dy

    def sit(self, y, bars_open):
        """Sitting 8:13a8 at Prince frame 295; returns (sound, crash, kill)."""
        if self.counter == 0:
            self.counter = 1
            return None, False, False
        if not self.crashed and y < CRASH_Y and not bars_open:
            self.counter, self.crashed = 1, True
            return CRASH_SOUND, True, False
        return None, False, self.crashed and self.counter >= 1

    def advance(self):
        # DrawObjCarpet 8:11a4-11ac counts each drawn frame of a used carpet.
        if self.counter:
            self.counter += 1
