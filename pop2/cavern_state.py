"""Recovered cavern state, independent of the window and original executable."""

from dataclasses import dataclass


@dataclass
class CavernState:
    entry_room: int | None = None
    entry_cell: int | None = None
    entry_frames: tuple = ()
    entry_frame: int = 0

    def configure_entry(self, metadata):
        if metadata is None:
            return
        self.entry_room, self.entry_cell = metadata['room'], metadata['cell']
        self.entry_frames = tuple((frame['phase'], tuple(frame['sounds'])) for frame in metadata['frames'])
        self.entry_frame = 0

    def foreground(self, room, cell, value):
        if (room, cell) == (self.entry_room, self.entry_cell) and self.entry_frames:
            return (value & 0xff00) | self.entry_frames[self.entry_frame][0]
        return value

    def advance(self):
        if self.entry_frame + 1 >= len(self.entry_frames):
            return ()
        self.entry_frame += 1
        return self.entry_frames[self.entry_frame][1]
