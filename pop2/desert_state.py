"""Desert stones and exit controller recovered from CODE 18."""

from dataclasses import dataclass, field
import random

from pop2.opponent_generation import character_column
from pop2.terrain import floor_contact_x


STANDING_POSES = {15, 109, 7, 46, 11, 12, 13, 14, 38, 44, 26, 158, 170, 171}


@dataclass
class Stone:
    phase: int = 0
    delay: int = 0
    direction: int = 1

    def sink(self):
        self.delay = 0
        self.direction = -1

    def advance(self):
        if self.delay:
            self.delay -= 1
        elif self.direction:
            self.phase = max(0, min(13, self.phase + self.direction))
            if self.phase in (0, 13):
                self.direction = 0


@dataclass
class DesertState:
    symbol: int = field(default_factory=lambda: random.randint(0, 2))
    marked_stone: int = field(default_factory=lambda: random.randint(1, 5))
    stones: list = field(default_factory=lambda: [Stone(delay=random.randint(21, 31)) for _ in range(6)])
    last_column: int = -1
    failed: bool = False
    counter: int = 0
    gate: int = 0
    visited_cave: bool = False

    def advance(self, room, state, record, alive=True):
        sounds = []
        # DesertFunc runs before object animations (18:01e6/01ea).
        if room == 0 and alive:
            self.visited_cave = True
            column = character_column(floor_contact_x(state.target_x, state.facing, record))
            if state.action in STANDING_POSES:
                if column != self.last_column and 2 <= self.last_column <= 7:
                    stone = self.stones[self.last_column - 2]
                    if stone.phase:
                        sounds.append(53)
                    stone.sink()
                    if self.last_column == self.marked_stone + 2:
                        sounds.append(49)
                self.last_column = column
            if not self.gate and not self.failed:
                if self.last_column == self.marked_stone + 2:
                    self.failed = True
                ready = not self.failed and all(
                    (stone.phase != 0) if i == self.marked_stone and self.counter < 10
                    else (i == self.marked_stone or stone.phase == 0)
                    for i, stone in enumerate(self.stones))
                if ready:
                    if self.counter >= 20:
                        self.gate = 1
                        sounds.append(47)
                    else:
                        if self.counter in (6, 9):
                            sounds.append(46 if self.counter == 6 else 55)
                        if self.counter == 10:
                            self.stones[self.marked_stone].sink()
                        self.counter += 1
                else:
                    self.counter = 0
            elif self.gate and self.gate < 20:
                self.gate += 1
        if alive:
            for stone in self.stones:
                if stone.phase == 0 and stone.delay == 0 and stone.direction == 1:
                    sounds.append(52)
                stone.advance()
        return sounds

    @property
    def exit_open(self):
        return self.gate == 20
