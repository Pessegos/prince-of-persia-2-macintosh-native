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
        if not self.phase and not self.direction:
            return False
        self.delay = 0
        self.direction = -1
        return True

    def advance(self, delay_enabled=True):
        if self.delay:
            if delay_enabled:
                self.delay -= 1
        elif self.direction:
            if (self.direction > 0 and self.phase == 13
                    or self.direction < 0 and self.phase == 0):
                self.direction = 0
            else:
                self.phase += self.direction


@dataclass
class DesertState:
    symbol: int = field(default_factory=lambda: random.randint(0, 2))
    marked_stone: int = field(default_factory=lambda: random.randint(1, 5))
    stones: list = field(default_factory=lambda: [Stone(direction=0) for _ in range(6)])
    last_column: int = -1
    failed: bool = False
    counter: int = 0
    gate: int = 0
    visited_cave: bool = False
    room: int | None = None
    gate_active: bool = False

    def enter_room(self, room):
        # SetupDesert (18:043c) resets contact/failure on each room load.
        self.room = room
        self.last_column = -1
        self.failed = False
        if room == 0:
            self.visited_cave = True
            # KeepTime (2:512a) triggers only the stones in the loaded room.
            for stone in self.stones:
                if stone.phase == 0:
                    stone.delay = random.randint(21, 31)
                    stone.direction = 1

    def sink_stone(self, index, sounds):
        stone = self.stones[index]
        phase = stone.phase
        triggered = stone.sink()
        if triggered:
            if phase:
                sounds.append(53)
            # SinkDsrtStone (18:0cce) animates once before AnimTrobs.
            stone.advance()
        return triggered

    def advance(self, room, state, record, alive=True, audio=None):
        sounds = []
        if room != self.room:
            # The original room load follows AnimTrobs for the cut frame.
            self.enter_room(room)
            return sounds
        # DesertFunc runs contact, puzzle checks, then object animations.
        if room == 0 and alive:
            column = character_column(floor_contact_x(state.target_x, state.facing, record))
            if state.action in STANDING_POSES:
                if column != self.last_column and 2 <= self.last_column <= 7:
                    triggered = self.sink_stone(self.last_column - 2, sounds)
                    if triggered and self.last_column == self.marked_stone + 2:
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
                    self.gate_active = True
                    sounds.append(47)
                else:
                    if self.counter in (6, 9):
                        sounds.append(46 if self.counter == 6 else 55)
                    if self.counter == 10:
                        self.sink_stone(self.marked_stone, sounds)
                    self.counter += 1
            else:
                self.counter = 0
        sequence = getattr(state, 'source_sequence_id', getattr(state, 'sequence_id', None))
        delay_enabled = alive and sequence != 27
        for stone in self.stones:
            if stone.phase == 0 and stone.delay == 0 and stone.direction == 1:
                sounds.append(52)
            stone.advance(delay_enabled)
        if self.gate_active:
            if self.gate == 20:
                self.gate_active = False
                if audio is not None:
                    audio.stop_sound(17)
            else:
                self.gate += 1
                if audio is None or not audio.sound_playing(55):
                    sounds.append(17)
        return sounds

    @property
    def exit_open(self):
        return self.gate == 20
