"""Cavern wall spikes, recovered from Macintosh CODE:5 and CODE:8."""

from dataclasses import dataclass, field

from pop2.opponent_generation import character_column
from pop2.terrain import floor_contact_x, floor_y


# InitCaveSpikes 8:2c18: DATA's two DrawObjSpikes piece banks.
BACK_PIECES = (0, 70, 73, 72, 71, 70, 69, 74)
FRONT_PIECES = (0, 76, 79, 78, 77, 76, 75, 80)
PIECE_OFFSETS = ((-17, 13), (-16, 13), (-15, 12), (-14, 12), (-14, 12), (-14, 12),
                 (-8, 1), (-8, 1), (-7, 0), (-3, 0), (-2, 0), (-2, 0))


def drawing_phase(value):
    value &= 255
    return 7 if value == 240 else 3 if value & 128 else value


def lethal(value):
    # MobSpikes 5:3fa4: only the two outward-moving poses can impale.
    value &= 255
    return value in (1, 2)


@dataclass
class WallSpikes:
    foreground: dict = field(default_factory=dict)
    active: set = field(default_factory=set)

    def trigger(self, tile):
        if tile.room is None or tile.kind != 2:
            return
        key = tile.room, tile.row * 10 + tile.column
        value = tile.foreground & 255
        if value == 0:
            self.foreground[key] = tile.foreground + 1
            if len(self.active) < 30:
                self.active.add(key)
        elif value & 128 and value != 240:
            # TriggerSpikes 5:415c: proximity keeps the extended pose alive,
            # but never restarts a retracting or bloodied trap.
            self.foreground[key] = 143

    def approach(self, terrain, motion, state, record, bounds, sword_drawn=False):
        # CheckSpikes 5:3c42: look one supporting-foot column to the left.
        if state.actor_type == 4:
            return
        column = character_column(floor_contact_x(state.target_x, state.facing, record))
        if column < 0 or floor_y(motion.row) + state.current_y < motion.row * 120 + 35:
            return
        tile = terrain.tile(motion.room, column - 1, motion.row)
        if tile.kind != 2:
            return
        threshold = (column - 1) * 51 + 73 + (3 if sword_drawn else 25)
        if state.facing:
            threshold += bounds[2] - bounds[0] + 2
        if state.target_x <= threshold:
            self.trigger(tile)

    def contact(self, terrain, motion, state, record, bounds, alive=True, sword_drawn=False):
        # CheckSpikeHit 5:3af8. Idle/cautious-step/dead poses, skeletons
        # and mice are exempt; airborne actors must clear the height gate.
        if (not alive or state.actor_type in (1, 4) or state.source_sequence_id == 85
                or state.action in (15, 185, 242, 243, 266, 271)
                or 121 <= state.action <= 132
                or floor_y(motion.row) + state.current_y < motion.row * 120 + 56):
            return None
        column = character_column(floor_contact_x(state.target_x, state.facing, record))
        for col in (column - 1, column):
            tile = terrain.tile(motion.room, col, motion.row)
            if tile.kind != 2 or not lethal(tile.foreground):
                continue
            if bounds[0] - int(bool(state.facing)) >= col * 51 + (88 if sword_drawn else 95):
                continue
            key = tile.room, tile.row * 10 + tile.column
            self.foreground[key] = 240
            return (54 if state.facing else 51), col * 51 + 90
        return None

    @staticmethod
    def visible_column(terrain, view_room, room, column):
        if room == view_room:
            return column
        if room == terrain.neighbor(view_room, 'left') and column == 9:
            return -1
        return None

    def advance(self, terrain, view_room):
        cues = []
        for key in tuple(self.active):
            room, cell = key
            row, column = divmod(cell, 10)
            value = terrain.tile(room, column, row).foreground & 255
            # ATMSpikes 5:39c8 removes offscreen MOBs, preserving blood.
            if self.visible_column(terrain, view_room, room, column) is None:
                if value != 240:
                    self.foreground[key] = 0
                self.active.remove(key)
                continue
            if value == 240:
                continue
            if value == 1:
                cues.append(282)
            if value & 128:
                value -= 1
                if not value & 127:
                    value = 4
                    cues.append(284)
            else:
                value += 1
                if value == 3:
                    value = 143
                elif value == 7:
                    value = 0
                    self.active.remove(key)
            self.foreground[key] = value
        return tuple(cues)

    def drawing_commands(self, terrain, view_room, front=False):
        for (room, cell), value in self.foreground.items():
            row, column = divmod(cell, 10)
            column = self.visible_column(terrain, view_room, room, column)
            if column is None:
                continue
            phase = drawing_phase(value)
            piece = (FRONT_PIECES if front else BACK_PIECES)[phase]
            if not piece:
                continue
            dy, dx = PIECE_OFFSETS[piece - 69]
            yield ['front' if front else 'back', 3500 + piece,
                   column * 51 + 63 + dx, row * 120 + 106 + dy, 16]
