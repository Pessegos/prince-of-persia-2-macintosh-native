"""Ruins scythe traps (tiles 12/13), recovered from Macintosh CODE:5."""

from dataclasses import dataclass, field

from pop2.opponent_generation import character_column
from pop2.terrain import floor_y


SCYTHE_TILES = (12, 13)
# The low byte of both halves: phase 0-19, 0x40 bloodied blade, 0x80 bloodied
# handle. Phase 0 without blood is the exported room.
SCYTHE_STATES = tuple(flags | phase for flags in (0, 0x40, 0xc0) for phase in range(20))
CUT_SEQUENCE = 113
CUT_SOUND, START_SOUND, RETRACT_SOUND = 278, 277, 276
# ComputeBladeHitRect 5:5a1c: QuickDraw rectangles (top, left, bottom, right)
# at a5-0x372a and a5-0x3722, offset by the cell (tile 13 one column right).
UPPER_BLADE, LOWER_BLADE = (53, 37, 67, 91), (53, 73, 67, 142)


def blade_rect(phase):
    """GetScytheHitType 5:5e6c: only phases 2, 16 and 17 can cut."""
    if phase == 2:
        return UPPER_BLADE[:2] + LOWER_BLADE[2:]
    return {16: UPPER_BLADE, 17: LOWER_BLADE}.get(phase)


@dataclass
class Scythes:
    foreground: dict = field(default_factory=dict)
    active: set = field(default_factory=set)

    @staticmethod
    def halves(terrain, tile):
        """The (room, cell) keys of tile 13 and of tile 12 to its left."""
        if tile.kind == 12:
            tile = terrain.tile(tile.room, tile.column + 1, tile.row)
        left = terrain.tile(tile.room, tile.column - 1, tile.row)
        return ((tile.room, tile.row * 10 + tile.column),
                (left.room, left.row * 10 + left.column))

    def trigger(self, terrain, motion, state):
        """5:57bc for a living Prince or guard, then TriggerScythe 5:5fde."""
        if state.actor_type in (7, 8, 11):
            return False
        # Not more than 30 pixels above the row's floor (native Y >= row * 120 + 76).
        if floor_y(motion.row) + state.current_y < motion.row * 120 + 76:
            return False
        column = character_column(state.target_x)
        tile = terrain.tile(motion.room, column, motion.row)
        # Native X (port X + 207) beyond the column's left edge (207 + 51 * column) + 28.
        if tile.room is None or tile.kind not in SCYTHE_TILES or state.target_x <= column * 51 + 28:
            return False
        key, _partner = self.halves(terrain, tile)
        if terrain.tile(key[0], key[1] % 10, key[1] // 10).foreground & 0x1f:
            return False
        self.active.add(key)
        return True

    def advance(self, terrain):
        """AnimScythe 5:4584 for each running trap; returns its sounds."""
        cues = []
        for key in sorted(self.active):
            tile = terrain.tile(key[0], key[1] % 10, key[1] // 10)
            value = tile.foreground & 255
            phase = value & 0x1f
            if phase >= 19:
                value &= 0xe0
                self.active.discard(key)
            else:
                value += 1
                if phase == 0:
                    cues.append(START_SOUND)
                elif phase == 15:
                    cues.append(RETRACT_SOUND)
                elif phase >= 16 and value & 0xc0 == 0x40:
                    value |= 0x80
            for half in self.halves(terrain, tile):
                self.foreground[half] = value
        return tuple(cues)

    def cut(self, terrain, motion, state, bounds):
        """CheckScytheHit 5:588a: the first scythe cell of columns -1..+1.

        `bounds` is the inclusive character rectangle. Returns True when the
        blade cuts; the trap is then bloodied.
        """
        if state.actor_type not in (0, 2) or state.selected_sequence_id == 44:
            return False
        column = character_column(state.target_x)
        for current in (column - 1, column, column + 1):
            tile = terrain.tile(motion.room, current, motion.row)
            if tile.room is None or tile.kind not in SCYTHE_TILES:
                continue
            rect = blade_rect(tile.foreground & 0x1f)
            if rect is None or 267 <= state.action <= 271:
                return False
            top, left, bottom, right = rect
            dx = (tile.column + (tile.kind == 13)) * 51
            dy = tile.row * 120
            if state.actor_type:
                bottom -= 10
            if not (left + dx <= bounds[2] and bounds[0] < right + dx
                    and top + dy <= bounds[3] and bounds[1] < bottom + dy):
                return False
            for half in self.halves(terrain, tile):
                self.foreground[half] = tile.foreground & 255 | 0x40
            return True
        return False
