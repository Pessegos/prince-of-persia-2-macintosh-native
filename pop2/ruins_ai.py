"""Ruins heads and serpents at runtime: the CODE 7 controllers and their
TestStrike/CheckStab rules (docs/research/ruins-head-leaves.md).
CombatEncounter owns one RuinsCreatures for opponent sets 5/6.

Names follow the original working actor. `native_x` includes the 207-pixel
origin, native facing is 0 (right) or -1 (left) where the port stores 1/0,
and a head's mode lives in its generator record (+0x1c), kept here in
`RuinsMind`. The ruins actors are kept apart from the ordinary guard bank,
so none of the guard AI paths sees them.
"""

from dataclasses import dataclass, field
import struct

from pop2.coordinates import NATIVE_X_ORIGIN, scene_x
from pop2.opponent_generation import EMPTY_TILES, WALL_TILES, character_column
from pop2.opponent_selection import nearest_opponent
from pop2.ruins_actors import (
    FLEE_REST, HEAD_TYPES, SERPENT_TYPE, chomp_again, frame_index, initial_state, ruins_spawns,
)
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import floor_contact_x, floor_edge_distance, floor_y

# SetCharFloor 4:31fa-3222: heads float 33 pixels above the floor.
HEAD_FLOOR_Y = -33
# 4:52bc: cell kinds with a barrier type (a gate only while it blocks).
BARRIER_TILES = frozenset((2, 7, 12, 20, 25))
HEAD_HOVER_POSES = (150, 165, 166, 159, 173)


def is_wall(kind):
    return kind in WALL_TILES


def is_space(kind):
    return kind in EMPTY_TILES


def is_floor(kind):
    # IsFloor 3:4da6: neither IsWall nor IsSpace.
    return not is_wall(kind) and not is_space(kind)


def signed_remainder(value, divisor):
    # 19:4bd0: the DIVS remainder takes the dividend's sign.
    remainder = abs(value) % divisor
    return -remainder if value < 0 else remainder


def x_within_middle(native_x, tolerance):
    # 7:1768: the inclusive window around a cell's horizontal middle.
    return 25 - tolerance <= signed_remainder(native_x - 229, 51) <= 25 + tolerance


def y_within_middle(native_y, tolerance):
    # YWithinMiddleOfCell 7:17c8.
    return 60 - tolerance <= signed_remainder(native_y - 5, 120) <= 60 + tolerance


def character_row(native_y):
    # GetRow 4:3afa.
    value = native_y - 5
    row = abs(value) // 120 * (-1 if value < 0 else 1)
    return row - 1 if value <= 0 else row


def column_remainder(x):
    # 5:48b0's remainder (a5-0x481c) for a scene X.
    return signed_remainder(x + 181, 51)


def serpent_passable(tile):
    # 7:1c46-1c88: a floor (a gate needs foreground bit 0x80) or an
    # uncovered crevice (type 7 with bit 0x80).
    if is_floor(tile.kind):
        return tile.kind != 4 or bool(tile.foreground & 0x80)
    return tile.kind == 7 and bool(tile.foreground & 0x80)


@dataclass
class RuinsMind:
    """The generator-record state that drives one head or serpent."""
    actor_type: int
    kind: int
    skill: int
    slot: int
    mode: int = 0
    dest_column: int = 0
    dest_row: int = 0
    timer: int = 0
    song: int = 0
    alert: int = 0
    removed: bool = False
    # AlignHeadOnKidNeck 7:0006: this frame's drawing point (scene X, Y).
    neck: tuple | None = None


@dataclass
class PrinceView:
    """The cached opponent (4:3272) as the ruins controllers read it."""
    column: int
    row: int
    native_x: int
    native_y: int
    facing: int
    pose: int
    room: int
    alive: int
    life: int
    armed: bool
    selected: int


@dataclass
class RuinsCreatures:
    """Opponent sets 5/6 for one level: per-room actors and the tension."""
    rooms: dict = field(default_factory=dict)
    tension_level: int = 0
    tension: int = 0
    banked: object | None = None
    # a5-0x481c: the remainder of the last GetCharCol (5:48b0) call.
    remainder: int = 0

    # ---- rooms -------------------------------------------------------

    def actors(self, room):
        return self.rooms.get(room, [])

    def load_room(self, encounter, room):
        if room in self.rooms:
            for actor in self.rooms[room]:
                if actor.alive and not actor.ruins.removed:
                    self._restart(encounter, actor)
            return
        actors = []
        for spawn in ruins_spawns(encounter.level, room):
            start = initial_state(spawn)
            state = SequenceState(start.sequence_id, current_x=start.x, target_x=start.x,
                                  facing=start.facing, actor_type=spawn.actor_type,
                                  level_kind=encounter.level_kind)
            from pop2.combat import Fighter

            life = spawn.words[13] or 3
            actor = Fighter(SequenceRuntime(encounter.sequences, state), life, life, room,
                            spawn.row, sword_drawn=start.armed, skill=spawn.skill,
                            selected_sequence=start.sequence_id)
            actor.ruins = RuinsMind(spawn.actor_type, spawn.kind, spawn.skill, spawn.slot,
                                    mode=start.mode)
            state.sequence_mode = start.special
            if spawn.actor_type in HEAD_TYPES:
                state.current_y = HEAD_FLOOR_Y
            if start.sound is not None:
                state.sound_events.append(start.sound)
            actor.runtime.next_frame()
            actors.append(actor)
        self.rooms[room] = actors

    def _restart(self, encounter, actor):
        # Re-entering a room runs HeadAddOpponent 7:0574 on the saved
        # record again: heads return to rest in their column.
        mind, state = actor.ruins, actor.state
        if mind.actor_type in HEAD_TYPES:
            column = character_column(state.target_x)
            state.target_x = state.current_x = scene_x(NATIVE_X_ORIGIN + column * 51 + 47)
            state.facing = 0
            state.select(130)
            actor.selected_sequence = 130
            state.current_y = HEAD_FLOOR_Y
            state.horizontal_velocity = state.vertical_velocity = 0
            actor.sword_drawn = False
            mind.mode = mind.alert = 0
            state.sequence_mode = 0
        elif mind.mode <= 0:
            state.select(170)
            mind.mode = -1
            actor.sword_drawn = True
        else:
            state.select(175)
            state.sequence_mode = 6
            actor.sword_drawn = True
        actor.runtime.next_frame()

    def living(self, room):
        return [actor for actor in self.actors(room) if not actor.ruins.removed]

    # ---- native helpers -----------------------------------------------

    @staticmethod
    def facing(actor):
        return 0 if actor.state.facing else -1

    @staticmethod
    def set_facing(actor, facing):
        actor.state.facing = 1 if facing == 0 else 0

    @staticmethod
    def native_x(actor):
        return actor.state.target_x + NATIVE_X_ORIGIN

    @staticmethod
    def set_native_x(actor, value):
        actor.state.target_x = actor.state.current_x = value - NATIVE_X_ORIGIN

    @staticmethod
    def native_y(actor):
        return floor_y(actor.row) + actor.state.current_y

    def add_char_x(self, actor, delta):
        # AddCharX 4:2bae: relative to the facing.
        return self.native_x(actor) + (delta if actor.state.facing else -delta)

    @staticmethod
    def stop(actor):
        # StopChar 4:34e2.
        actor.state.horizontal_velocity = actor.state.vertical_velocity = 0

    @staticmethod
    def set_floor(actor):
        actor.state.current_y = HEAD_FLOOR_Y if actor.ruins.actor_type in HEAD_TYPES else 0

    def jump(self, actor, sequence):
        # JumpSeq 6:0006: heads at rest always turn left first (6:003e-0090).
        state = actor.state
        if (actor.ruins.actor_type in HEAD_TYPES and state.facing
                and (130 <= sequence <= 139 or sequence == 166)):
            state.facing = 0
            if state.action in (150, 159):
                self.set_native_x(actor, self.add_char_x(actor, 12))
            self.column(actor, None, native=True)  # The frame reload 4:2a72.
        actor.selected_sequence = sequence
        state.select(sequence)

    def record(self, actor, encounter):
        # LoadFrame 4:2a8e reads Head.rsrc FRAM 750 for the whole family.
        frames = head_frames()
        if frames is None:
            return None
        return frames[frame_index(actor.ruins.actor_type, actor.state.action)]

    def column(self, actor, encounter, *, native=False):
        # The stored supporting column (GetCharCol of GetFCharX). With
        # `native` the original computes it here, setting a5-0x481c.
        record = self.record(actor, encounter)
        x = actor.state.target_x
        contact = floor_contact_x(x, actor.state.facing, record) if record else x
        if native:
            self.remainder = column_remainder(contact)
        return character_column(contact)

    def edge_distance(self, actor, encounter):
        # GetDist1 4:3a92 of the supporting foot.
        record = self.record(actor, encounter)
        x = actor.state.target_x
        contact = floor_contact_x(x, actor.state.facing, record) if record else x
        return floor_edge_distance(contact, actor.state.facing)

    def prince(self, encounter):
        player = encounter.player
        counter = getattr(encounter, 'player_death_counter', -1)
        alive = -1 if player.alive else max(0, counter if counter is not None else 0)
        return PrinceView(encounter._supporting_column(player), player.row,
                          self.native_x(player), self.native_y(player), self.facing(player),
                          player.state.action, player.room, alive, player.life,
                          player.sword_drawn, player.state.source_sequence_id)

    @staticmethod
    def tile(encounter, room, column, row):
        return encounter.terrain.tile(room, column, row)

    def gate_blocks(self, actor, encounter, tile):
        # 4:5b0e, ruins heads: body height plus 46 (type 7) or 33 (type 8).
        art = getattr(encounter, 'guard_art', None)
        height = 30
        if art is not None:
            # ShapeBounds 4:5cbc: the viewport-clipped body rectangle.
            left, top, right, bottom = art.bounds(actor.state, floor_y(actor.row))
            height = max(0, min(365, bottom + 1) - max(0, top))
        height += 46 if actor.ruins.actor_type == 7 else 33
        return 2 * ((tile.foreground & 255) >> 2) + 11 < height + 13

    def set_tension(self, level, amount):
        # SetTensionLevel 6:5022 (a5-0x36a2 level, a5-0x36a0 amount).
        if self.tension_level != level:
            if {self.tension_level, level} == {2, 3}:
                self.tension -= 10
            else:
                self.tension = 0
            self.tension_level = level
        self.tension = max(0, self.tension + amount)

    @staticmethod
    def rnd(encounter, limit):
        # Rnd 17:6e06 is inclusive.
        return encounter.rng.randrange(limit + 1)

    # ---- heads: sight and movement ------------------------------------

    def can_see(self, actor, encounter, prince):
        """CharCanSeeOpp 7:00f8: -1, a direction 0-3, or 4."""
        column = self.column(actor, encounter)
        if column == prince.column and actor.row == prince.row:
            return 4
        room = actor.room
        record = self.record(actor, encounter)
        offset = record.offset_x if record is not None else 0
        hy, hx = 2 * actor.row, 2 * column
        if signed_remainder(self.native_x(actor) + offset - 195, 51) > 25:
            hx += 1
        py, px = 2 * prince.row + 1, 2 * prince.column
        if signed_remainder(prince.native_x - 207, 51) > 25:
            px += 1
        dx, dy = abs(px - hx), abs(py - hy)
        sx = 1 if px > hx else -1
        sy = 1 if py > hy else -1
        clear = True

        def cell(x, y):
            return self.tile(encounter, room, x >> 1, y >> 1).kind

        def row_cell(x, y):
            return cell(x, y - 1 if sy < 0 else y)

        if dx > dy:
            error, step, both = 2 * dy - dx, 2 * dy, 2 * (dy - dx)
            while True:
                hx += sx
                if (sx > 0 and not hx & 1) or (sx < 0 and hx & 1):
                    clear = not is_wall(cell(hx, hy))
                if clear:
                    if error < 0:
                        error += step
                    else:
                        if (sy > 0 and hy & 1) or (sy < 0 and not hy & 1):
                            clear = is_space(row_cell(hx, hy))
                        hy += sy
                        error += both
                dx -= 1
                if not dx or not clear:
                    break
        else:
            error, step, both = 2 * dx - dy, 2 * dx, 2 * (dx - dy)
            while True:
                if (sy > 0 and hy & 1) or (sy < 0 and not hy & 1):
                    clear = is_space(row_cell(hx, hy))
                if clear:
                    hy += sy
                    if error < 0:
                        error += step
                    else:
                        hx += sx
                        if (sx > 0 and not hx & 1) or (sx < 0 and hx & 1):
                            clear = not is_wall(cell(hx, hy))
                        error += both
                dy -= 1
                if not dy or not clear:
                    break
        if not clear:
            return -1
        if not self.nearest_on_side(actor, encounter, prince):
            return 4
        if actor.row != prince.row:
            return 2 if sy > 0 else 3
        return 1 if sx > 0 else 0

    def nearest_on_side(self, actor, encounter, prince):
        # 6:3946: only the opponent nearest the Prince on its side moves.
        side = -1 if prince.native_x >= self.native_x(actor) else 0
        return nearest_opponent(encounter.player, self.living(actor.room), side) is actor

    def distance(self, actor, prince):
        # 4:49ee: 999 unless the Prince has life and shares room and row.
        if (prince.life == 0 or prince.room != actor.room or prince.row != actor.row):
            return 999
        distance = prince.native_x - self.native_x(actor)
        if self.facing(actor):
            distance = -distance
        if distance >= 0 and self.facing(actor) != prince.facing:
            distance += 21
        return distance

    def overshoot(self, actor):
        # 7:170a: a vertical move past the row's floor height.
        selected = actor.state.source_sequence_id
        y = actor.state.current_y
        return selected == 144 and y > HEAD_FLOOR_Y or selected == 143 and y < HEAD_FLOOR_Y

    def can_move(self, actor, encounter, direction):
        """7:0936: may a head start moving in this direction?"""
        column, row, room = self.column(actor, encounter), actor.row, actor.room
        if direction in (0, 1):
            if direction == 0 and column < -1 or direction == 1 and column > 10:
                return False
            if self.overshoot(actor):
                return False
            probe_x = scene_x(self.add_char_x(actor, 26))
            probe, self.remainder = character_column(probe_x), column_remainder(probe_x)
            if probe != column:
                tile = self.tile(encounter, room, column + (1 if direction else -1), row)
                if is_wall(tile.kind) or tile.kind == 4 and self.gate_blocks(actor, encounter, tile):
                    return False
            if direction == 1:
                tile = self.tile(encounter, room, column, row)
                if tile.kind == 4 and self.gate_blocks(actor, encounter, tile):
                    return False
            return True
        if direction == 2:
            return (row != 2 and x_within_middle(self.native_x(actor), 12)
                    and is_space(self.tile(encounter, room, column, row).kind))
        if direction == 3:
            return (row != 0 and x_within_middle(self.native_x(actor), 12)
                    and is_space(self.tile(encounter, room, column, row - 1).kind))
        return False

    # ---- heads: the leaves --------------------------------------------

    def face_prince(self, actor, encounter, prince):
        # 7:0c5e.
        column = self.column(actor, encounter)
        if column < prince.column:
            if self.facing(actor) == -1:
                self.set_native_x(actor, self.add_char_x(actor, -12))
                self.set_facing(actor, 0)
                self.stop(actor)
        elif self.facing(actor) == 0:
            self.set_native_x(actor, self.add_char_x(actor, -12))
            self.set_facing(actor, -1)
            self.stop(actor)

    def get_angry(self, actor, encounter, prince):
        # HeadGetAngry 7:0f88.
        mind = actor.ruins
        mind.mode, mind.dest_row, mind.dest_column, mind.timer = 1, prince.row, prince.column, 1
        self.jump(actor, 140)
        self.stop(actor)
        self.face_prince(actor, encounter, prince)
        mind.alert = 3
        actor.sword_drawn = True
        if self.banked is None or self.banked.ruins.removed or not self.banked.alive:
            self.banked = actor
        actor.state.sound_events.append(131)

    def get_peaceful(self, actor, encounter):
        # HeadGetPeaceful 7:1012.
        mind = actor.ruins
        mind.mode = 0
        actor.sword_drawn = False
        self.stop(actor)
        self.jump(actor, 139)
        column = self.column(actor, encounter, native=True)
        self.set_native_x(actor, NATIVE_X_ORIGIN + column * 51 + 47)
        self.set_floor(actor)
        mind.alert = 0

    def idle(self, actor, encounter):
        # 7:1268: only pose 150 decides.
        if actor.state.action != 150:
            return
        direction = self.rnd(encounter, 3)
        selected = actor.state.source_sequence_id
        if direction == 3:
            direction = 0 if 131 <= selected <= 133 else 1 if 134 <= selected <= 136 else -1
        elif direction == 2:
            direction += self.rnd(encounter, 1)
        if direction == -1 or not self.can_move(actor, encounter, direction):
            return
        if direction == 3:
            sequence = 137
        elif direction == 2:
            sequence = 138
        else:
            sequence = (131 if direction == 0 else 134) + self.rnd(encounter, 2)
        self.jump(actor, sequence)

    def attack(self, actor, encounter, prince):
        # HeadAttackProg 7:064c.
        mind, selected = actor.ruins, actor.state.source_sequence_id
        if selected in (140, 152, 156, 162):
            return
        if 147 <= selected <= 151:
            self.focus(actor, encounter, prince)
            return
        if actor.state.action not in HEAD_HOVER_POSES:
            return
        seen = self.can_see(actor, encounter, prince)
        if seen == -1:
            if mind.timer:
                mind.timer = 0
                mind.dest_column, mind.dest_row = prince.column, prince.row
            self.go_to_destination(actor, encounter)
            return
        mind.timer = 1
        column = self.column(actor, encounter)
        dc, dr = abs(column - prince.column), abs(actor.row - prince.row)
        hover = (selected != 166 and y_within_middle(self.native_y(actor), 30))
        if dr == 0 and dc < 2:
            direction = 1 if self.native_x(actor) < prince.native_x else 0
            if dc == 0 or self.can_move(actor, encounter, direction):
                if selected != 147:
                    self.jump(actor, 147)
            elif hover:
                self.jump(actor, 166)
            return
        if dc == 0 and dr == 1 and self.can_move(actor, encounter, seen):
            sequence = 143 if actor.row > prince.row else 144
            if selected != sequence:
                self.jump(actor, sequence)
            return
        if seen == 4:
            if dc | dr and hover:
                self.jump(actor, 166)
            return
        mind.dest_row, mind.dest_column = prince.row, prince.column
        direction = seen
        if direction in (2, 3) and not self.can_move(actor, encounter, direction):
            direction = 1 if self.native_x(actor) < prince.native_x else 0
        if self.can_move(actor, encounter, direction):
            if direction == 3:
                sequence = 143
            elif direction == 2:
                sequence = 144
            else:
                sequence = 142
                # 7:0856-0896 compares a boolean with 12, so only an
                # unfinished turn (SEQS 142) skips facing and the floor snap.
                if selected != 142:
                    self.face_prince(actor, encounter, prince)
                    self.set_floor(actor)
        else:
            sequence = 166
            self.stop(actor)
        if selected != sequence:
            self.jump(actor, sequence)

    def focus(self, actor, encounter, prince):
        # HeadFocusOnNeck 7:0e8c.
        selected = actor.state.source_sequence_id
        if selected not in (147, 144, 143):
            return
        low, high = (0, 60) if prince.armed else (5, 68)
        distance = self.distance(actor, prince)
        same_row = actor.row == prince.row
        if same_row and low <= distance <= high:
            self.stop(actor)
            self.jump(actor, 150 + self.rnd(encounter, 1))
            actor.ruins.mode, actor.ruins.dest_column = 3, 1
            return
        threshold = -16 if prince.armed else -11
        if selected == 147:
            if distance < threshold:
                self.stop(actor)
                self.jump(actor, 156)
            elif not same_row:
                self.jump(actor, 142)
        if distance - 101 <= high and same_row and actor.state.source_sequence_id != 144:
            actor.state.sound_events.append(134)

    def locked(self, actor, encounter, prince):
        # HeadLockedProg 7:1164: the bite.
        mind, state = actor.ruins, actor.state
        selected, released = state.source_sequence_id, False
        if (selected == 150 and state.action == 167 and state.sequence_mode != 1
                or selected == 151 and state.action == 166):
            if chomp_again(mind.dest_column, mind.skill, self.tension,
                           lambda limit: self.rnd(encounter, limit)):
                if prince.alive < 0:
                    mind.dest_column += 1
                    self.jump(actor, 151 if selected == 150 else 150)
                elif mind.skill >= 11:
                    self.jump(actor, 165)
            else:
                self.jump(actor, 152)
                self.set_native_x(actor, self.add_char_x(actor, -12))
                released = True
        if released or state.source_sequence_id in (158, 157, 155):
            mind.mode, mind.dest_column, mind.dest_row = 1, prince.column, prince.row

    def finish_attack(self, actor, encounter, prince):
        # HeadDoneAttackingKid 7:0b16.
        if prince.alive >= 6:
            self.get_peaceful(actor, encounter)
        elif actor.state.source_sequence_id != 166:
            self.set_floor(actor)
            self.jump(actor, 166)
        actor.state.sequence_mode = 0

    def go_to_destination(self, actor, encounter):
        # HeadGoToDest 7:107a.
        mind = actor.ruins
        column, moved = self.column(actor, encounter), False
        if mind.dest_column == column and mind.dest_row == actor.row:
            self.get_peaceful(actor, encounter)
            return False
        if mind.dest_row != actor.row:
            direction, sequence = (2, 144) if mind.dest_row > actor.row else (3, 143)
            moved = self.can_move(actor, encounter, direction)
            if moved and actor.state.source_sequence_id != sequence:
                self.jump(actor, sequence)
        if not moved and mind.dest_column != column:
            direction = 1 if mind.dest_column > column else 0
            moved = self.can_move(actor, encounter, direction)
            if not moved:
                remainder = self.remainder
                moved = direction == 1 and remainder < 25 or direction == 0 and remainder > 25
            if moved and actor.state.source_sequence_id != 142:
                self.jump(actor, 142)
        if not moved:
            self.get_peaceful(actor, encounter)
        return moved

    def flee(self, actor, encounter, prince):
        # 7:0cae.
        mind, selected = actor.ruins, actor.state.source_sequence_id
        if selected == 153:
            if actor.state.sequence_mode == 2:
                mind.alert = 0
                self.jump(actor, 159)
            return
        target_ok = prince.life != 0 and not (
            prince.selected == 70 and (prince.pose == 0 or prince.pose >= 223))
        near = actor.row == prince.row and abs(self.column(actor, encounter) - prince.column) < 3
        if selected == 159:
            if (self.column(actor, encounter) == mind.dest_column
                    and x_within_middle(self.native_x(actor), 3)):
                if near:
                    self.get_angry(actor, encounter, prince)
                else:
                    self.jump(actor, 160)
                    mind.timer = FLEE_REST[mind.skill]
        elif near and target_ok:
            self.get_angry(actor, encounter, prince)
        else:
            mind.timer -= 1
            if not mind.timer:
                if target_ok and self.can_see(actor, encounter, prince) != -1:
                    self.get_angry(actor, encounter, prince)
                    self.jump(actor, 162)
                else:
                    self.get_peaceful(actor, encounter)
                    self.jump(actor, 163)
        if not mind.song and not encounter_sound_playing(encounter, 131):
            mind.song = 1
            actor.state.sound_events.append(136)

    def able_to_flee(self, actor, encounter, prince):
        """IsAbleToFleeInRoom 7:1454."""
        mind = actor.ruins
        others = self.actors(actor.room)
        if len(others) <= 1 or any(other.ruins.mode == 2 or other.ruins.kind == 8 for other in others):
            return False
        if self.rnd(encounter, mind.skill // 3 + 1):
            return False
        right = self.facing(actor) == 0
        column = self.column(actor, encounter)
        if right and column < 3 or not right and column + 3 > 10:
            return False
        edge, behind = (-1, -1) if right else (10, 1)
        clear, scan = True, column
        while scan != edge:
            tile = self.tile(encounter, actor.room, scan, actor.row)
            if tile.kind in BARRIER_TILES or tile.kind == 4 and self.gate_blocks(actor, encounter, tile):
                clear = False
            scan += behind
            if scan == edge or not clear:
                break
        if clear:
            scan -= behind
        else:
            scan -= 2 * behind
            clear = abs(scan - column) >= 3
        if not clear:
            return False
        actor.sword_drawn = False
        mind.alert = 1
        mind.mode, mind.dest_column, mind.dest_row = 2, scan, actor.row
        mind.timer, mind.song = -1, 0
        if self.banked is actor:
            self.banked = None
        return True

    def control_head(self, actor, encounter):
        # The wrapper 7:1324 (Codex: level7-head-mode-routing.md).
        prince = self.prince(encounter)
        target_ok = prince.life != 0 and not (
            prince.selected == 70 and (prince.pose == 0 or prince.pose >= 223))
        mode = actor.ruins.mode
        if mode == 0:
            if (target_ok and actor.state.action in HEAD_HOVER_POSES
                    and self.can_see(actor, encounter, prince) != -1):
                self.get_angry(actor, encounter, prince)
            else:
                self.idle(actor, encounter)
        elif mode == 1:
            if target_ok:
                self.attack(actor, encounter, prince)
            else:
                self.finish_attack(actor, encounter, prince)
        elif mode == 2:
            self.flee(actor, encounter, prince)
        elif mode == 3:
            if target_ok:
                self.locked(actor, encounter, prince)
            else:
                self.finish_attack(actor, encounter, prince)

    # ---- serpents --------------------------------------------------

    def serpent_alert(self, actor, encounter, prince):
        # The ordinary alert 2:6ee4 with its serpent exceptions.
        state = actor.state
        if (prince.alive >= 0 or prince.pose == 0 or 217 <= prince.pose < 226
                or actor.row != prince.row or state.sequence_mode == 6):
            return 0
        low, high = sorted((self.column(actor, encounter), prince.column))
        if low < high and self.tile(encounter, actor.room, high, actor.row).kind == 4:
            high -= 1
        alert = 3
        for column in range(low, high + 1) if low < high else ():
            tile = self.tile(encounter, actor.room, column, actor.row)
            if is_wall(tile.kind):
                if tile.kind == 7 and tile.foreground & 0x80:
                    continue
                return 0
            if tile.kind in (12, 13):
                continue
            if (tile.kind in EMPTY_TILES or tile.kind in (11, 15, 26, 24)
                    or tile.kind == 4 and tile.foreground & 255 < 104):
                alert = 1
        return alert

    def faces_prince(self, actor, encounter, prince):
        # 7:1dc6.
        mind = actor.ruins
        if actor.state.source_sequence_id == 171 or mind.alert < 2:
            return False
        column = self.column(actor, encounter)
        return column <= prince.column if self.facing(actor) == 0 else column >= prince.column

    def control_serpent(self, actor, encounter):
        # SnakeComeOutOfHole 7:1824.
        prince = self.prince(encounter)
        mind = actor.ruins
        if mind.mode < 0:
            if self.faces_prince(actor, encounter, prince):
                self.strike(actor, encounter, prince)
            else:
                self.inactive(actor, encounter, prince)
        else:
            self.wait(actor, encounter, prince)

    def ahead(self, actor, encounter, steps=1):
        direction = 1 if actor.state.facing else -1
        return self.tile(encounter, actor.room, self.column(actor, encounter) + steps * direction,
                         actor.row)

    def here(self, actor, encounter):
        return self.tile(encounter, actor.room, self.column(actor, encounter), actor.row)

    def strike(self, actor, encounter, prince):
        # 7:187e.
        state, selected = actor.state, actor.state.source_sequence_id
        distance = self.distance(actor, prince)
        lunging = 1 <= prince.pose <= 14 or 49 <= prince.pose <= 56
        strike = False
        if 31 <= distance <= 71:
            if state.action in (278, 279) or selected == 176 and lunging:
                strike = True
            elif selected not in (176, 173) and 20 <= distance <= 60:
                self.jump(actor, 176)
                state.sound_events.append(128)
        elif selected == 176 and lunging and 31 < distance < 79:
            strike = True
        elif selected == 176 and 135 <= prince.pose <= 149 and 31 < distance < 71:
            strike = True
        elif (state.action in (278, 279) and (distance < 31 or distance > 77)
                and serpent_passable(self.ahead(actor, encounter))):
            self.jump(actor, 177)
        if strike and actor.state.source_sequence_id != 173:
            self.set_native_x(actor, self.add_char_x(actor, distance - 58))
            self.jump(actor, 173)

    def inactive(self, actor, encounter, prince):
        # SnakeGoIntoHole 7:1b52.
        mind, state = actor.ruins, actor.state
        selected = state.source_sequence_id
        if prince.alive >= 0:
            if selected != 176 and state.action not in (278, 279):
                self.jump(actor, 176)
            return
        if not (selected in (171, 172) or state.sequence_mode == 9):
            here = self.here(actor, encounter)
            if (here.foreground & 0xf00) >> 8 == 15:
                remainder = signed_remainder(self.native_x(actor) - 229, 51)
                if 16 <= remainder <= 28:
                    delta = 22 - remainder
                    delta = -delta if self.facing(actor) == -1 else delta - 2
                    self.set_native_x(actor, self.add_char_x(actor, delta))
                    self.jump(actor, 171)
                return
            ahead = self.ahead(actor, encounter)
            if selected in (176, 168) or state.action in (278, 279):
                if serpent_passable(ahead):
                    self.jump(actor, 177)
                return
            if serpent_passable(ahead):
                return
            if is_wall(ahead.kind):
                if ahead.kind == 7:
                    self.jump(actor, 168)
                elif self.facing(actor) == 0:
                    state.sequence_mode = 9
                elif state.action in (254, 238):
                    self.jump(actor, 168)
            elif self.edge_distance(actor, encounter) < 25:
                self.jump(actor, 168)
            return
        if state.sequence_mode == 9:
            here = self.here(actor, encounter)
            if is_wall(here.kind) and self.edge_distance(actor, encounter) < 12:
                state.action = 264
                self.jump(actor, 168)
        if state.action == 264:
            state.sequence_mode = 6
            mind.mode = 6 if mind.alert == 2 else self.rnd(encounter, 60) + 36

    def wait(self, actor, encounter, prince):
        # 7:19fe.
        mind, state = actor.ruins, actor.state
        mind.mode -= 1
        if mind.mode > 0:
            return
        mind.mode = -1
        column = self.column(actor, encounter)

        def floor_edge(direction):
            # 5:2198: the next wall in that direction.
            scan = column
            while True:
                scan += direction
                if is_wall(self.tile(encounter, actor.room, scan, actor.row).kind):
                    return scan
                if scan < -1 or scan > 10:
                    return scan

        left, right = floor_edge(-1), floor_edge(1)
        here = self.here(actor, encounter)
        hidden = is_wall(here.kind) and not (here.kind == 7 and here.foreground & 0x80)
        if prince.room == actor.room and prince.row == actor.row and left < column < right:
            if column > prince.column:
                self.set_facing(actor, -1)
            else:
                self.set_facing(actor, -1 if hidden else 0)
        else:
            self.set_facing(actor, 0 if self.facing(actor) == -1 else -1)
        if hidden:
            self.jump(actor, 170)
            self.set_native_x(actor, self.add_char_x(actor, 61))
        else:
            self.jump(actor, 172)
        state.sequence_mode = 0

    # ---- combat (TestStrike 6:57b2, CheckStab 6:5092) --------------------

    @staticmethod
    def striking_pose(fighter):
        # IsStrikingPos 6:5d60.
        kind, pose = fighter.state.actor_type, fighter.state.action
        if kind in HEAD_TYPES:
            return 165 <= pose <= 167 or pose == 181
        if kind == SERPENT_TYPE:
            return fighter.state.source_sequence_id == 173 and pose in (274, 280)
        return pose in (153, 154) or kind == 0 and pose in (244, 245)

    @staticmethod
    def strike_pose(fighter):
        # IsTheStrikePos 6:5e42.
        kind, pose = fighter.state.actor_type, fighter.state.action
        if kind == SERPENT_TYPE:
            return pose == 280
        return pose == 154 or kind == 0 and pose == 245

    def strike_range(self, striker, defender, sword_type):
        # GetCharStrikeRanges 6:5b38 for the ruins pairs.
        same = striker.state.facing == defender.state.facing
        if striker.state.actor_type == 0:
            if defender.state.actor_type == SERPENT_TYPE:
                if (defender.state.sequence_mode == 6 or defender.state.source_sequence_id == 171
                        or striker.state.source_sequence_id != 96):
                    return None
                low, high = (62, 126) if same else (-11, 79)
            else:
                low, high = 32, 92
            return low, high - (10 if sword_type == 2 else 0)
        if striker.state.actor_type == SERPENT_TYPE:
            if self.native_y(defender) < defender.row * 120 + 96:
                return None
            return (8, 52) if same else (-32, 6)
        return None

    def contact(self, striker, defender):
        # CheckStrikes 6:5896's gates.
        heads = HEAD_TYPES
        if (not striker.sword_drawn or striker.room != defender.room or striker.row != defender.row
                or not striker.targetable or not defender.targetable):
            return False
        if (striker.state.actor_type not in heads and defender.state.actor_type not in heads
                and abs(self.native_y(striker) - self.native_y(defender)) >= 15):
            return False
        return (self.striking_pose(striker) and defender.alive
                and defender.state.animation_state != 8
                and defender.state.source_sequence_id != 110)

    def head_hit(self, actor, encounter):
        """HeadHit 7:08fa: a blocked head loses a life point."""
        actor.life = max(0, actor.life - 1)
        if actor.alive:
            actor.state.sound_events.append(131)
            self.able_to_flee(actor, encounter, self.prince(encounter))
            sequence = 153
        else:
            sequence = 154
            if self.banked is actor:
                self.banked = None
        self.set_tension(1, -1)
        return sequence

    def kill(self, actor, encounter):
        # 6:5562 for heads and serpents.
        actor.ruins.alert = 0
        if actor.ruins.actor_type in HEAD_TYPES:
            self.set_facing(actor, 0 if self.facing(encounter.player) == -1 else -1)
            self.set_tension(1, -1)
            self.jump(actor, 154)
            actor.state.sound_events.append(137)
        else:
            self.jump(actor, 174)
        if self.banked is actor:
            self.banked = None

    def test_strike(self, striker, defender, encounter, sword_type):
        from pop2.combat import opponent_distance

        distance = opponent_distance(striker, defender)
        kind = striker.state.actor_type
        low, high = (0, 55) if kind in HEAD_TYPES else (61, 99)
        if (striker.state.facing != defender.state.facing and low <= distance <= high
                and defender.state.actor_type not in (*HEAD_TYPES, SERPENT_TYPE)
                and kind != SERPENT_TYPE and defender.state.action in (161, 150)):
            # 6:5a3c: the parry; a blocked head is hurt by HeadHit.
            defender.state.action = 161
            encounter.parry_timer = 4
            if kind in HEAD_TYPES:
                self.jump(striker, self.head_hit(striker, encounter))
                striker.runtime.next_frame()
            return 'parry'
        if self.strike_pose(striker):
            limits = self.strike_range(striker, defender, sword_type)
            if limits is not None and limits[0] <= distance <= limits[1]:
                return 'hit'
        elif kind in HEAD_TYPES and striker.state.sequence_mode == 1 and not encounter.parry_timer:
            return 'hit'
        return None

    def resolve(self, encounter):
        """TestStrike/CheckStab for the ruins actors in the Prince's room."""
        from pop2.combat import CombatEvent

        player = encounter.player
        actors = [actor for actor in self.living(player.room) if actor.alive]
        if not actors or player.state.action == 0 or 219 <= player.state.action < 229:
            return []
        sword_type = getattr(encounter, 'sword_type', 1)
        events, stabbed, prince_hit = [], [], False
        for actor in actors:
            if self.contact(actor, player):
                result = self.test_strike(actor, player, encounter, sword_type)
                if result == 'parry':
                    events.append(CombatEvent('parry', 'player', sound=0))
                prince_hit |= result == 'hit'
        for actor in actors:
            if self.contact(player, actor) and self.test_strike(player, actor, encounter, sword_type) == 'hit':
                stabbed.append(actor)
        for actor in stabbed:
            events.append(self.stab(actor, encounter, sword_type))
        if prince_hit and not stabbed:
            # 6:51ae: the striker is found again by its pose.
            striker = next((actor for actor in actors
                            if (actor.state.action in (167, 181) if actor.state.actor_type in HEAD_TYPES
                                else self.strike_pose(actor))), None)
            if striker is not None:
                events.append(self.stab_prince(striker, encounter))
        return [event for event in events if event is not None]

    def stab(self, actor, encounter, sword_type):
        # CheckStab 6:51f2 for a struck head or serpent.
        from pop2.combat import CombatEvent

        if actor.ruins.actor_type in HEAD_TYPES:
            damage = 1 if sword_type == 2 else 2
            if actor.life > damage:
                self.able_to_flee(actor, encounter, self.prince(encounter))
            sound = 130
        else:
            damage, sound = 100, 127
        actor.life = max(0, actor.life - damage)
        if actor.alive:
            self.jump(actor, 153)
        else:
            self.kill(actor, encounter)
        self.set_floor(actor)
        actor.state.vertical_velocity = 0
        actor.runtime.next_frame()
        return CombatEvent('hit' if actor.alive else 'death', 'guard', sound=sound)

    def stab_prince(self, striker, encounter):
        # CheckStab 6:51f2-5560 and 6:5562 for the Prince.
        from pop2.combat import CombatEvent, select_sequence

        player = encounter.player
        state = player.state
        frames = getattr(encounter, 'player_frames', None)
        terrain = getattr(encounter, 'terrain', None)
        serpent = striker.state.actor_type == SERPENT_TYPE
        direction = 1 if state.facing else -1

        def foot():
            record = frames[state.action] if frames is not None else None
            contact = floor_contact_x(state.target_x, state.facing, record) if record else state.target_x
            return character_column(contact), floor_edge_distance(contact, state.facing)

        # The stored column (a5-0x504a) is not recalculated after the pushes
        # below; every cell test of this routine reads around it.
        column = foot()[0] if terrain is not None else 0

        def cell(offset):
            return terrain.tile(player.room, column + offset, player.row).kind

        def shift(delta):
            state.target_x += delta if state.facing else -delta
            state.current_x = state.target_x

        fatal = state.source_sequence_id in (10, 16, 28, 14) or player.sword_lost
        damage = 100 if fatal or serpent else 1
        sequence = 74
        # 6:52a0-52b4: a serpent's bite goes straight to DecLifePts(100).
        if not fatal and not serpent and state.facing == striker.state.facing:
            sequence = 94
            # 6:5306-5340: an unarmed Prince backed against a wall.
            if not player.sword_drawn and terrain is not None and is_wall(cell(direction)):
                distance = foot()[1]
                if distance < 36:
                    shift(distance - 36)
        if not fatal and not serpent:
            pose = state.action
            flagged = bool(frames is not None and frames[pose].aux & 0x40) or 191 <= pose <= 205
            if not player.sword_drawn and (not flagged or 102 <= pose <= 106):
                sequence = 45
            elif 246 <= pose <= 261 and terrain is not None:
                # 6:53a4-53f4: knocked off a wall behind or ahead.
                if is_wall(cell(-direction)):
                    shift(25)
                elif is_wall(cell(direction)):
                    shift(-25)
        crouched = 246 <= state.action <= 261
        if not getattr(encounter, 'god_mode', False):
            player.life = max(0, player.life - damage)
        player.contact_consumed = True
        if sequence != 45 and not fatal and not serpent:
            # 6:53f8-5406 arms the Prince.
            player.sword_drawn, player.sword_lost = True, False
            state.callback_flag = 1
        if player.alive:
            player.recovering = sequence != 45
            select_sequence(player, sequence)
            # SetCharFloor 6:5478-547e.
            state.current_y = state.vertical_velocity = 0
            player.runtime.next_frame()
            return CombatEvent('hit', 'player', sound=0)
        player.recovering = False
        if not fatal and terrain is not None and frames is not None:
            # 6:5428-54b2: a fatal bite at a ledge tips the Prince over it.
            distance = foot()[1]
            offset = None
            if is_space(cell(0)):
                offset = distance - 12
            elif is_space(cell(-direction)) and distance >= 6:
                offset = distance - 12 - 51
            if offset is not None:
                shift(offset)
                # As the guards' fatal fall in CombatEncounter._hurt.
                from pop2.terrain import TerrainMotion

                player.row += 1
                state.current_y -= 120
                if player.terrain_motion is None:
                    player.terrain_motion = TerrainMotion(player.room, player.row)
                player.terrain_motion.row = player.row
                player.terrain_motion.falling = player.terrain_motion.hit_fall = True
                player.targetable = False
                select_sequence(player, 81)
                player.runtime.next_frame()
                return CombatEvent('death', 'player', 0, sound=0)
        if serpent:
            # The death-method table 6:570e sends type 11 to 6:574a (7).
            sequence, method = (98 if crouched else 97), 7
            state.sound_events.append(126)
        else:
            sequence, method = (98 if crouched else 85), 6
            if crouched:
                state.sound_events.append(133)
            self.set_tension(1, 5)
        select_sequence(player, sequence)
        state.current_y = state.vertical_velocity = 0
        player.runtime.next_frame()
        if sequence == 85 and terrain is not None and frames is not None:
            terrain.align_flat_death(player.room, player.row, state, frames[state.action])
        return CombatEvent('death', 'player', method, sound=0)

    # ---- per frame ------------------------------------------------------

    def advance(self, encounter):
        """Control, animate and move the ruins actors in the Prince's room."""
        if encounter.player.room not in self.rooms:
            self.load_room(encounter, encounter.player.room)
        for actor in list(self.living(encounter.player.room)):
            actor.runtime.rng = encounter.rng
            # AutoCtrl 6:4e90 decrements the shared timers on every call.
            encounter.parry_timer = max(0, encounter.parry_timer - 1)
            encounter.advance_pause = max(0, encounter.advance_pause - 1)
            encounter.attack_pause = max(0, encounter.attack_pause - 1)
            if actor.alive:
                if actor.ruins.actor_type in HEAD_TYPES:
                    self.control_head(actor, encounter)
                else:
                    # The alert routine 2:6ee4 runs before AutoCtrl.
                    actor.ruins.alert = self.serpent_alert(actor, encounter, self.prince(encounter))
                    self.control_serpent(actor, encounter)
            actor.runtime.next_frame()
            self._after_frame(actor, encounter)

    def _after_frame(self, actor, encounter):
        state = actor.state
        events, state.sequence_events = state.sequence_events, []
        if any(event[0] == -17 for event in events):
            # SEQS opcode -17 (4:48f8) removes the actor.
            actor.ruins.removed = True
            if self.banked is actor:
                self.banked = None
            return
        self.align_on_neck(actor, encounter)
        if state.engine_counter:
            # AnimChar -4/-3 (4:2d88/3030) change the row, not the height.
            actor.row += state.engine_counter
            state.current_y -= 120 * state.engine_counter
            state.engine_counter = 0
        if actor.ruins.actor_type in HEAD_TYPES:
            # MoveChar 4:3464: heads fly with their velocity.
            if state.vertical_velocity:
                native_y = self.native_y(actor) + state.vertical_velocity
                actor.row = character_row(native_y)
                state.current_y = native_y - floor_y(actor.row)
            if state.horizontal_velocity:
                self.set_native_x(actor, self.add_char_x(actor, state.horizontal_velocity))
            self._wall_contact(actor, encounter)

    def align_on_neck(self, actor, encounter):
        """AlignHeadOnKidNeck 7:0006, run by the head's drawing setup
        (3:0b32-0b9c) while its special flag is 1 (the bite frames)."""
        mind, state = actor.ruins, actor.state
        mind.neck = None
        if mind.actor_type not in HEAD_TYPES or state.sequence_mode != 1:
            return
        table, frames = neck_table(), getattr(encounter, 'player_frames', None)
        art = getattr(encounter, 'guard_art', None)
        player = getattr(encounter, 'player', None)
        if table is None or frames is None or art is None or player is None or player.room != actor.room:
            return
        record = frames[player.state.action]
        if record.shape_index < 0:
            return
        # The Prince's drawn object (GetObj 3:3e7c kind 2): his drawing point.
        offset = record.offset_x if player.state.facing else -record.offset_x
        point_x = player.state.target_x + offset
        point_y = floor_y(player.row) + player.state.current_y + record.offset_y
        dy, dx = table[record.shape_index]
        body = art.body(state)
        width = body.width if body is not None else 0
        if self.facing(actor) == self.facing(player):
            dx = -dx - width - (17 if mind.actor_type == 7 else 25)
        if mind.actor_type == 8:
            dx += 10
        if self.facing(actor) == 0:
            dx = -dx
        mind.neck = (point_x + dx, point_y + dy)
        # The working X becomes the drawing X + 207; Y is left alone.
        state.target_x = state.current_x = point_x + dx

    def body_edges(self, actor, encounter):
        """ShapeBounds 4:5cbc for a head: native left/right edges and the
        width (image width + 1), from its drawing point."""
        art = getattr(encounter, 'guard_art', None)
        body = art.body(actor.state) if art is not None else None
        if body is None:
            return None
        record = art.frames[frame_index(actor.ruins.actor_type, actor.state.action)]
        if actor.ruins.neck is not None:
            point = actor.ruins.neck[0] + NATIVE_X_ORIGIN
        else:
            point = self.add_char_x(actor, record.offset_x)
        width = body.width + 1
        if self.facing(actor) == 0:
            return point - width, point, width, body.height
        return point, point + width, width, body.height

    def _wall_contact(self, actor, encounter):
        """CheckBarrier 4:62b0 for a head, with HeadEnemyCollide 7:0b6e."""
        state, mind = actor.state, actor.ruins
        if mind.actor_type not in HEAD_TYPES:
            return  # 4:5654: serpents never meet a barrier.
        selected = state.source_sequence_id
        if (state.animation_state != 0 and selected == 164 or not actor.sword_drawn
                or selected == 58):
            return
        column = self.column(actor, encounter)
        direction = 1 if state.facing else -1

        def blocking(tile):
            return is_wall(tile.kind) or tile.kind == 4 and self.gate_blocks(actor, encounter, tile)

        cell = None
        for offset in (0, direction):
            tile = self.tile(encounter, actor.room, column + offset, actor.row)
            if blocking(tile):
                cell, cell_column = tile, column + offset
                break
        if cell is None:
            return
        edges = self.body_edges(actor, encounter)
        # 4:5654: kinds 10 and 12 are no barrier for heads; a gate only blocks.
        if edges is None or cell.kind in (10, 12) or cell.kind == 4 and not self.gate_blocks(
                actor, encounter, cell):
            return
        left, right, width, height = edges
        cell_x = NATIVE_X_ORIGIN + cell_column * 51 + 22
        # GetBarrierType 4:52bc and the edge tables a5-0x3620/-0x360e.
        barrier = {2: 4, 25: 4, 20: 4, 4: 1, 12: 6}.get(cell.kind, 0)
        if cell.kind == 7:
            barrier = 4 if height > 34 else 2
        level = getattr(encounter, 'level', None)
        if (cell.kind == 4 and level is not None and actor.room == 8
                and struct.unpack_from('>H', level, 0x218a)[0] == 8):
            barrier = 8  # 4:532e-5344: level eight's room 9 gates.
        face_offset = (0, 40, 0, -22, 3, 18, 8, 0, 16, 0)[barrier]
        back_offset = (0, 0, 50, -22, 0, 0, 16, 0, 24, 0)[barrier]

        def face():
            # GetBarrDistFromFace 4:6562.
            if barrier == 0:
                return -1
            if self.facing(actor) == 0:
                return cell_x + face_offset - right
            return left - (cell_x + 50 - back_offset)

        def back():
            # GetBarrDistFromBack 4:6610.
            if barrier == 0:
                return 200
            if self.facing(actor) == 0:
                return left - (cell_x + 50 - back_offset)
            return cell_x + face_offset - right

        to_face, to_back = face(), back()
        nearest = to_face if abs(to_face) < abs(to_back) else to_back
        if abs(nearest) < 5:
            if nearest:
                nearest = -5 if nearest < 0 else 5
            else:
                nearest = 5 if (to_face or to_back) >= 0 else -5
            if is_wall(cell.kind) and nearest < 0 and abs(to_face) < 5:
                nearest = -nearest
        result = -1
        if (state.sequence_mode != 1 and to_face < 5 and to_face >= -width):
            # HeadEnemyCollide 7:0b6e: pushed out of the wall.
            self.set_native_x(actor, self.add_char_x(actor, -22 - to_face))
            if actor.alive and selected != 153:
                result = 157
            elif selected != 164:
                if state.action <= 191:
                    result = 164
                    anchor = NATIVE_X_ORIGIN + cell_column * 51 + 22
                    self.set_native_x(actor, anchor + (51 if self.facing(actor) == -1 else 0))
                else:
                    self.jump(actor, 145)
                actor.life = 0
        if result == -1 and nearest < 5 and nearest >= -width:
            if (cell.kind == 4 and nearest > 0
                    or is_wall(cell.kind) and nearest < 0 and nearest == to_face):
                nearest = -nearest
            self.set_native_x(actor, self.add_char_x(actor, -nearest))
            # 4:64fc reads the selected sequence again: HeadEnemyCollide may
            # have just jumped to 145.
            if state.source_sequence_id not in (145, 164) and state.sequence_mode != 1:
                result = 158
        if result != -1:
            self.jump(actor, result)
            actor.runtime.next_frame()

_HEAD_FRAMES = []
_NECK_TABLE = []


def neck_table():
    """Head.rsrc's type-zero 755: (dy, dx) per Kid shape index."""
    if not _NECK_TABLE:
        try:
            from pop2.render_opening import load_resource_file

            data = load_resource_file('Head.rsrc')['\0\0\0\0'][755]['data']
            _NECK_TABLE.append([struct.unpack_from('>2h', data, offset)
                                for offset in range(0, len(data), 4)])
        except (OSError, KeyError):
            _NECK_TABLE.append(None)
    return _NECK_TABLE[0]


def head_frames():
    """Head.rsrc's FRAM 750 records, or None without imported resources."""
    if not _HEAD_FRAMES:
        try:
            from pop2.animation_data import parse_frame_records
            from pop2.render_opening import load_resource_file

            _HEAD_FRAMES.append(parse_frame_records(load_resource_file('Head.rsrc')['FRAM'][750]['data']))
        except (OSError, KeyError):
            _HEAD_FRAMES.append(None)
    return _HEAD_FRAMES[0]


def encounter_sound_playing(encounter, sound):
    # IsSoundPlaying 5:52c8; the host's mixer is not consulted here.
    playing = getattr(encounter, 'sound_playing', None)
    return bool(playing and playing(sound))
