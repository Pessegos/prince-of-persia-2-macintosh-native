"""Macintosh RECG control streams (CODE 5:60c0-638a)."""

from dataclasses import dataclass
import struct


@dataclass(frozen=True)
class RecordedControls:
    forward: int = 0
    backward: int = 0
    up: int = 0
    down: int = 0
    modifier: int = 0

    @classmethod
    def unpack(cls, word):
        return cls(*((word >> shift & 3) - 1 for shift in (14, 12, 10, 8)),
                   (word >> 3 & 31) - 2)


@dataclass(frozen=True)
class RecordedFrame:
    frame: int
    commands: tuple


@dataclass(frozen=True)
class RecordedGame:
    level: int
    last_frame: int
    frames: tuple

    @classmethod
    def read(cls, data):
        if len(data) < 6:
            raise ValueError("Truncated RECG header")
        level, last_frame, size = struct.unpack_from(">3H", data)
        if not 1 <= level <= 14 or size > len(data) - 6:
            raise ValueError("Invalid RECG header")
        # The level-four resource retains an unused tail from an older take.
        data = data[:6 + size]
        frames, offset, previous = [], 6, -1
        while offset < len(data):
            if offset + 8 > len(data):
                raise ValueError("Truncated RECG frame")
            frame, count = struct.unpack_from(">2H", data, offset)
            end = offset + 8 + count * 4
            if not previous < frame <= last_frame or end > len(data) or count > 6:
                raise ValueError("Invalid RECG frame")
            commands = tuple(struct.iter_unpack(">2H", data[offset + 4:end - 4]))
            if any(actor > 5 for actor, _word in commands):
                raise ValueError("Invalid RECG actor")
            if len({actor for actor, _word in commands}) != count:
                raise ValueError("Duplicate RECG actor")
            frames.append(RecordedFrame(frame, commands))
            previous, offset = frame, end
        return cls(level, last_frame, tuple(frames))


class RecordedPlayback:
    def __init__(self, game):
        self.game = game
        self.frame = -1
        self.cursor = 0
        self.controls = [RecordedControls.unpack(0) for _ in range(6)]

    @property
    def done(self):
        return self.frame > self.game.last_frame

    def advance(self):
        self.frame += 1
        while (self.cursor < len(self.game.frames)
               and self.game.frames[self.cursor].frame <= self.frame):
            for actor, word in self.game.frames[self.cursor].commands:
                self.controls[actor] = RecordedControls.unpack(word)
            self.cursor += 1
        return self.controls
