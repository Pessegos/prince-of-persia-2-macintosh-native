"""Macintosh pressure links and cavern gate, exit and shooter controllers."""

from dataclasses import dataclass, field, replace
import struct

from pop2.loose_floors import pressure_tile
from pop2.darts import Darts


@dataclass
class PressurePlates:
    foreground: dict = field(default_factory=dict)
    active: dict = field(default_factory=dict)
    timers: dict = field(default_factory=dict)
    triggered: list = field(default_factory=list)
    songs: list = field(default_factory=list)
    darts: Darts = field(default_factory=Darts)

    def link(self, terrain, index):
        if not 0 <= index < 256:
            raise ValueError('Invalid pressure-plate link')
        return struct.unpack_from('>5h', terrain.level, 0x1680 + index * 10)

    def timer(self, terrain, index):
        return self.timers.get(index, self.link(terrain, index)[2])

    def add(self, key, phase):
        if key in self.active or len(self.active) < 20:
            self.active[key] = phase

    def press(self, terrain, motion, state, record, alive=True):
        if state.actor_type == 1 and 29 <= state.selected_sequence_id <= 42:
            return ()
        tile = pressure_tile(terrain, motion, state, record)
        if tile is None or tile.kind not in (5, 6, 34):
            return ()
        return self.push(terrain, tile, permanent=not alive and state.actor_type != 4,
                         action=state.action)

    def impact(self, terrain, room, cell, kind):
        value = struct.unpack_from('>H', terrain.level, 0x780 + room * 120 + cell * 4)[0]
        value = self.foreground.get((room, cell), value)
        tile = replace(terrain.tile(room, cell % 10, cell // 10), kind=kind, foreground=value)
        return self.push(terrain, tile, permanent=True, impact=True)

    def push(self, terrain, tile, permanent=False, action=15, impact=False):
        if tile.room is None or tile.kind not in (5, 6, 34):
            return ()
        index = tile.foreground & 255
        if permanent:
            self.timers[index] = 31
        timer = self.timer(terrain, index)
        key = tile.room, tile.row * 10 + tile.column
        cues = []
        if timer != 31:
            self.timers[index] = 5
            if timer < 2:
                self.add(key, 1)
                if action != 185:
                    cues.append(27)
        cues.extend(self.trigger(terrain, index, tile.kind, bool(tile.foreground & 0x2000), impact))
        # PushPlate writes the depression bit after traversing the entire chain.
        self.foreground[key] = tile.foreground | 0x2000
        return tuple(cues)

    def trigger(self, terrain, index, how, depressed=False, impact=False):
        seen = set()
        cues = []
        while index != -3:
            if index in seen:
                raise ValueError('Cyclic pressure-plate link chain')
            seen.add(index)
            room, cell, _timer, _previous, following = self.link(terrain, index)
            if room == -2:
                break
            if not 1 <= room <= 32 or not 0 <= cell < 30:
                raise ValueError('Invalid pressure-plate destination')
            tile = terrain.tile(room - 1, cell % 10, cell // 10)
            key = room - 1, cell
            self.triggered.append((tile.kind, *key, how))
            if tile.kind == 4:
                self.trigger_gate(key, tile.foreground, how, depressed, impact)
            elif tile.kind == 33 and not depressed and not tile.foreground & 7:
                # TriggerObject 5:1f8c and TriggerDart 5:49b6: a fresh plate
                # and an idle shooter; the first mouth pose loads immediately.
                self.add(key, 1)
                self.foreground[key] = tile.foreground + 1
                self.darts.spawn(*key)
                cues.append(65)
            elif tile.kind == 17 and not tile.foreground & 255:
                # TriggerObject 5:1f40: only a completely closed exit starts.
                self.add(key, 1)
                if 297 not in self.songs:
                    self.songs.append(297)
            index = following
        return tuple(cues)

    def trigger_gate(self, key, foreground, how, depressed=False, impact=False):
        position = foreground & 255
        high = foreground & 0xff00
        phase = self.active.get(key)
        if how == 34:
            # TriggerGateWithRevPlate 8:2c38: do not reverse a gate still opening.
            if phase in (0, 1):
                if depressed:
                    self.foreground[key] = high | 237
                else:
                    self.foreground[key] = high | min(position, 184)
                    self.active[key] = 4
            elif phase == 2 and impact:
                self.active[key] = 3
            elif phase is None and position != 255:
                if position == 0:
                    if impact or not depressed:
                        self.add(key, 3 if impact else 2)
                elif position != 56:
                    self.add(key, 4)
        elif how == 5:
            if position == 255:
                return
            self.foreground[key] = high | (237 if position >= 184 else (position + 3) & 0xfc)
            self.add(key, 2)
        elif how == 6:
            if phase != 4 and (phase is not None or position != 0):
                self.add(key, 4)

    def advance(self, terrain):
        self.triggered.clear()
        cues = []
        for key, phase in tuple(self.active.items()):
            room, cell = key
            tile = terrain.tile(room, cell % 10, cell // 10)
            value = tile.foreground
            if tile.kind == 33:
                if (value & 7) < 6:
                    self.foreground[key] = value + 1
                else:
                    self.foreground[key] = value & 0xfff8
                    del self.active[key]
                continue
            if tile.kind in (5, 6, 34):
                index = value & 255
                timer = self.timer(terrain, index)
                if timer >= 31:
                    del self.active[key]
                    continue
                self.timers[index] = timer - 1
                if timer < 2:
                    self.foreground[key] = value & 0xdfff
                    del self.active[key]
                continue
            if tile.kind == 17:
                # ATMExit 5:161c: one pixel/update, permanently open at 79.
                position = (value & 255) + 1
                self.foreground[key] = (value & 0xff00) | position
                if position >= 79:
                    del self.active[key]
                    cues.append(18)
                else:
                    cues.append(17)
                continue
            if tile.kind != 4:
                del self.active[key]
                continue
            position = value & 255
            if phase >= 4:
                phase = min(8, phase + 1)
                position -= (0, 0, 0, 20, 40, 60, 80, 100, 120)[phase]
                if position <= 0:
                    position, phase = 0, -1
                    cues.append(20)
            elif position == 255:
                phase = -1
                cues.append(18)
            else:
                position += (-1, -4, 4, 4)[phase]
                if phase in (0, 1):
                    if position <= 0:
                        position, phase = 0, -1
                        cues.append(18)
                    elif position < 184:
                        phase = 1
                        cues.append(17)
                elif position < 184:
                    cues.append(17)
                elif phase == 2:
                    position, phase = 237, 0
                    cues.append(18)
                else:
                    position, phase = 255, -1
                    cues.append(18)
            self.foreground[key] = (value & 0xff00) | position
            if phase < 0:
                del self.active[key]
            else:
                self.active[key] = phase
        return tuple(cues)
