"""Macintosh pressure links and cavern gate, exit and shooter controllers."""

from dataclasses import dataclass, field, replace
import struct

from pop2.coordinates import port_room
from pop2.bridge import bridge_checked
from pop2.loose_floors import pressure_tile
from pop2.darts import Darts
from pop2.terrain import floor_contact_x
from pop2.opponent_generation import character_column
from pop2.mechanism_audio import GateSound

# ATMGate's AddGateSound calls (5:42b4, 4360, 43dc, 4416) and StopGate
# (5:14b6-14cc) test LEVL 0x2186: the caverns' stone gates sound 17/18/20,
# the iron gates of every other environment 272 (moving), 273 (opened),
# 274 (stopped) and 275 (slam). Exit doors (ATMExit 5:15c0) keep 17/18/20.
IRON_GATE_CUES = {'moving': 272, 'opened': 273, 'stopped': 274, 'slam': 275}
STONE_GATE_CUES = {'moving': 17, 'opened': 18, 'stopped': 18, 'slam': 20}


def can_trigger_exit(level, room, sword_type):
    """TriggerObject 5:1f18-1f3c: level eight needs the father's sword.

    The entrance-room exit is exempt, including before the throne vision.
    A missing sword context must not unlock the level-eight final exit.
    """
    number = struct.unpack_from('>H', level, 0x218a)[0]
    entry = port_room(struct.unpack_from('>H', level, 0x2198)[0])
    return number != 8 or room == entry or sword_type == 1


@dataclass
class PressurePlates:
    foreground: dict = field(default_factory=dict)
    active: dict = field(default_factory=dict)
    timers: dict = field(default_factory=dict)
    triggered: list = field(default_factory=list)
    slams: list = field(default_factory=list)
    slam_sounds: list = field(default_factory=list)
    songs: list = field(default_factory=list)
    stopped_sounds: list = field(default_factory=list)
    gate_sounds: list = field(default_factory=list)
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

    def press(self, terrain, motion, state, record, alive=True, *, sword_type=None):
        if state.actor_type == 1 and 29 <= state.selected_sequence_id <= 42:
            return ()
        # CheckPress 5:129a-12a2: a floating Prince presses no plate.
        caverns = getattr(terrain, 'caverns', None)
        if state.actor_type in (0, None) and caverns is not None and caverns.potions.floating:
            return ()
        tile = pressure_tile(terrain, motion, state, record)
        if tile is None or tile.kind not in (5, 6, 34):
            return ()
        # TriggerGateWithRevPlate 8:2d66-2d96: a skeleton on level five's
        # bridge rooms (row not 0) cannot open a shut reversible gate.
        shut_only = (state.actor_type == 4 and motion.row != 0 and bridge_checked(
            struct.unpack_from('>H', terrain.level, 0x218a)[0], motion.room))
        return self.push(terrain, tile, permanent=not alive and state.actor_type != 4,
                         action=state.action, shut_only=shut_only, sword_type=sword_type)

    def impact(self, terrain, room, cell, kind, *, sword_type=None):
        value = struct.unpack_from('>H', terrain.level, 0x780 + room * 120 + cell * 4)[0]
        value = self.foreground.get((room, cell), value)
        tile = replace(terrain.tile(room, cell % 10, cell // 10), kind=kind, foreground=value)
        return self.push(terrain, tile, permanent=True, impact=True, sword_type=sword_type)

    def push(self, terrain, tile, permanent=False, action=15, impact=False, shut_only=False,
             *, sword_type=None):
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
        cues.extend(self.trigger(terrain, index, tile.kind, bool(tile.foreground & 0x2000), impact,
                                 shut_only, sword_type=sword_type))
        # PushPlate writes the depression bit after traversing the entire chain.
        self.foreground[key] = tile.foreground | 0x2000
        return tuple(cues)

    def trigger(self, terrain, index, how, depressed=False, impact=False, shut_only=False,
                *, sword_type=None):
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
            tile = terrain.tile(port_room(room), cell % 10, cell // 10)
            key = port_room(room), cell
            self.triggered.append((tile.kind, *key, how))
            if tile.kind == 4:
                self.trigger_gate(key, tile.foreground, how, depressed, impact, shut_only)
            elif tile.kind == 33 and not depressed and not tile.foreground & 7:
                # TriggerObject 5:1f8c and TriggerDart 5:49b6: a fresh plate
                # and an idle shooter; the first mouth pose loads immediately.
                self.add(key, 1)
                self.foreground[key] = tile.foreground + 1
                self.darts.spawn(*key)
                cues.append(65)
            elif tile.kind == 27 and not depressed and tile.foreground in (0, 3):
                # TriggerCaveBars 8:1672-16d0: a fresh plate opens fully closed
                # bars (trob direction 0) and closes fully open ones (1).
                self.add(key, int(tile.foreground == 3))
            elif (tile.kind == 17 and not tile.foreground & 255
                  and can_trigger_exit(terrain.level, tile.room, sword_type)):
                # TriggerObject 5:1f40: only a completely closed exit starts.
                self.add(key, 1)
                if 297 not in self.songs:
                    self.songs.append(297)
            index = following
        return tuple(cues)

    def trigger_gate(self, key, foreground, how, depressed=False, impact=False, shut_only=False):
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
                    if shut_only:
                        return
                    if impact or not depressed:
                        self.add(key, 3 if impact else 2)
                elif position != 56:
                    self.add(key, 4)
        elif how == 5:
            if position == 255:
                return
            if position >= 184:
                # TriggerGate 5:1dac-1dcc: an open gate only restarts its
                # wait at 237; no new trob, so no repeated "opened" sound.
                # (A dead or off-screen presser opens it for good, 1de8.)
                self.foreground[key] = high | 237
                return
            self.foreground[key] = high | (position + 3) & 0xfc
            self.add(key, 2)
        elif how == 6:
            if phase != 4 and (phase is not None or position != 0):
                self.add(key, 4)

    @staticmethod
    def squashing_player(terrain, key, state, motion, record):
        # ATMGate 5:41c8-425e uses the copied player's selected sequence,
        # floor row and current/adjacent column, including horizontal cuts.
        if state is None or motion is None or record is None or state.source_sequence_id != 118:
            return False
        room, cell = key
        row, column = divmod(cell, 10)
        if room != motion.room:
            if room == terrain.neighbor(motion.room, 'left'):
                column -= 10
            elif room == terrain.neighbor(motion.room, 'right'):
                column += 10
            else:
                return False
        foot = character_column(floor_contact_x(state.target_x, state.facing, record))
        return row == motion.row and abs(column - foot) <= 1

    @staticmethod
    def crushing_body_under_gate(terrain, key, state, motion, record):
        # CaveMoveSquishingGate 8:3a60-3ab0 uses linear cells, with
        # horizontal room rebasing, and only the gate/preceding foot cell.
        room, cell = key
        foot = character_column(floor_contact_x(state.target_x, state.facing, record))
        player_cell = motion.row * 10 + foot
        if room != motion.room:
            if room == terrain.neighbor(motion.room, 'left'):
                player_cell += 10
            elif room == terrain.neighbor(motion.room, 'right'):
                player_cell -= 10
            else:
                return False
        return player_cell in (cell, cell - 1)

    @staticmethod
    def fingers_under_gate(key, state, motion, record):
        # CheckSquishedFingers 5:153c: compare linear cells in the copied
        # player's room; neither facing nor a climb request is required.
        if state is None or motion is None or record is None:
            return False
        room, cell = key
        if room != motion.room or state.animation_state not in (2, 6):
            return False
        foot = character_column(floor_contact_x(state.target_x, state.facing, record))
        return motion.row * 10 + foot in (cell + 10, cell + 11)

    def advance(self, terrain, state=None, motion=None, record=None):
        self.triggered.clear()
        self.slams.clear()
        self.slam_sounds.clear()
        self.gate_sounds.clear()
        cues = []

        def gate_sound(cue, opening, source):
            self.gate_sounds.append(GateSound(cue, opening, source))
            if cue is not None:
                cues.append(cue)

        stone = struct.unpack_from('>H', terrain.level, 0x2186)[0] == 3
        gate_cues = STONE_GATE_CUES if stone else IRON_GATE_CUES

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
            if tile.kind == 27:
                # 8:1508-1576: one bar phase per update, sound 282 as they
                # start opening and 284 as they start closing.
                bars = value & 7
                if phase == 0 and bars < 3:
                    if bars == 0:
                        cues.append(282)
                    self.foreground[key] = (value & 0xfff8) | (bars + 1)
                elif phase == 1 and bars:
                    if bars == 3:
                        cues.append(284)
                    self.foreground[key] = (value & 0xfff8) | (bars - 1)
                else:
                    del self.active[key]
                continue
            if tile.kind == 17:
                # ATMExit 5:161c: one pixel/update, permanently open at 79.
                position = (value & 255) + 1
                self.foreground[key] = (value & 0xff00) | position
                if position >= 79:
                    del self.active[key]
                    gate_sound(18, True, key)
                else:
                    gate_sound(17, True, key)
                continue
            if tile.kind != 4:
                del self.active[key]
                continue
            position = value & 255
            opening = phase in (2, 3)
            squashing = self.squashing_player(terrain, key, state, motion, record)
            if phase >= 4:
                phase = min(8, phase + 1)
                position -= (0, 0, 0, 20, 40, 60, 80, 100, 120)[phase]
                if position <= 0:
                    position, phase = 56 if squashing else 0, -1
                    if not squashing and self.fingers_under_gate(key, state, motion, record):
                        cues.append(29)
                    if not squashing:
                        # ATMGate 5:42c6-42ce asks 5:4766 whether this slam
                        # shut opponents out (the level-four "phew").
                        self.slams.append(key)
                    self.slam_sounds.append(key)
                    gate_sound(gate_cues['slam'], False, key)
            elif position == 255:
                phase = -1
                gate_sound(gate_cues['stopped'], opening, key)
            else:
                position += (-1, -4, 4, 4)[phase]
                if phase in (0, 1):
                    if position <= 0:
                        position, phase = 56 if squashing else 0, -1
                        gate_sound(gate_cues['stopped'], False, key)
                        if self.fingers_under_gate(key, state, motion, record):
                            cues.append(29)
                    elif position < 184:
                        phase = 1
                        gate_sound(gate_cues['moving'], False, key)
                        # SEQS:118 signals the final slam with mode 3 on
                        # its last kneeling frame, before the flattened poses.
                        if squashing and self.crushing_body_under_gate(terrain, key, state, motion, record):
                            if state.sequence_mode == 3:
                                position, phase = 48, -1
                                gate_sound(20, False, key)
                                gate_sound(18, False, key)
                            elif state.action == 264:
                                position += 3
                            elif state.action == 265:
                                position = 56
                            elif state.action == 266:
                                phase = -1
                                self.stopped_sounds.append(17)
                                gate_sound(None, False, key)
                    elif (struct.unpack_from('>H', terrain.level, 0x218a)[0] == 5
                          and room == 6):
                        # ATMGate 5:4396-43bc: level five's room-7 gate undoes
                        # its waiting step, so once open it stays open.
                        position -= (-1, -4)[phase]
                elif position < 184:
                    # 5:43d4-43da: a rising iron gate asks every eighth pixel.
                    if stone or not position & 7:
                        gate_sound(gate_cues['moving'], True, key)
                elif phase == 2:
                    position, phase = 237, 0
                    gate_sound(gate_cues['opened'], True, key)
                else:
                    position, phase = 255, -1
                    gate_sound(gate_cues['stopped'], True, key)
            self.foreground[key] = (value & 0xff00) | position
            if phase < 0:
                del self.active[key]
            else:
                self.active[key] = phase
        return tuple(cues)
