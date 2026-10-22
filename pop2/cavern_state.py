"""Recovered cavern state, independent of the window and original executable."""

from dataclasses import dataclass, field
import random

from pop2.bridge import Bridge
from pop2.loose_floors import LooseFloors
from pop2.lava import Lava
from pop2.pressure_plates import PressurePlates
from pop2.potions import Potions
from pop2.wall_spikes import WallSpikes
from pop2.gate_crush import GateCrush


@dataclass
class CavernState:
    entry_room: int | None = None
    entry_cell: int | None = None
    entry_frames: tuple = ()
    entry_frame: int = 0
    torches: dict = field(default_factory=dict)
    loose: LooseFloors = field(default_factory=LooseFloors)
    lava: Lava = field(default_factory=Lava)
    plates: PressurePlates = field(default_factory=PressurePlates)
    potions: Potions = field(default_factory=Potions)
    spikes: WallSpikes = field(default_factory=WallSpikes)
    crush: GateCrush = field(default_factory=GateCrush)
    bridge: Bridge = field(default_factory=Bridge)

    def configure_lava(self, metadata, enhanced=True):
        self.lava = Lava(metadata, enhanced=enhanced)

    def configure_torches(self, metadata):
        self.torches.clear()
        for records in metadata.values():
            for record in records:
                key = record['room'], record['cell']
                if key not in self.torches:
                    # TriggerTorch 5:2050-2072: Rnd(8), preserving upper bits.
                    self.torches[key] = (record['foreground'] & 0xfff0) | random.randint(0, 8)

    def advance_torches(self, records):
        for key in {(record['room'], record['cell']) for record in records}:
            value = self.torches[key]
            previous = value & 15
            phase = random.randint(0, 8)
            # CaveGetTorchFrame 8:3b4e: adjacent phase if Rnd repeats.
            if phase == previous:
                phase = (phase + 1) % 9
            self.torches[key] = (value & 0xfff0) | phase

    def configure_entry(self, metadata):
        if metadata is None:
            return
        self.entry_room, self.entry_cell = metadata['room'], metadata['cell']
        self.entry_frames = tuple((frame['phase'], tuple(frame['sounds'])) for frame in metadata['frames'])
        self.entry_frame = 0

    def foreground(self, room, cell, value):
        if (room, cell) in self.potions.tiles:
            return self.potions.tiles[room, cell][1]
        value = self.potions.phases.get((room, cell), value)
        value = self.plates.foreground.get((room, cell), value)
        value = self.spikes.foreground.get((room, cell), value)
        if (room, cell) in self.loose.tiles:
            kind, foreground = self.loose.tiles[room, cell]
            if kind == 19 and (room, cell) in self.torches:
                foreground = (foreground & 0xfff0) | (self.torches[room, cell] & 15)
            return self.plates.foreground.get((room, cell), foreground)
        if (room, cell) == (self.entry_room, self.entry_cell) and self.entry_frames:
            return (value & 0xff00) | self.entry_frames[self.entry_frame][0]
        if (room, cell) in self.torches:
            return self.torches[room, cell]
        return value

    def advance(self):
        if self.entry_frame + 1 >= len(self.entry_frames):
            return ()
        self.entry_frame += 1
        return self.entry_frames[self.entry_frame][1]
