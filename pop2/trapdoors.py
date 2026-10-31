"""Temple trap doors (tile 26, MOB type 10), recovered from CODE:10.

The rules follow Codex's native-checked reference models
(tools/probe_temple_trapdoor*.py, docs/research/temple-trapdoor*.md).
Records keep the native eight words (X, Y, one-based room, mark, 0, type 10,
row, phase word); X is room-local.
"""

from dataclasses import dataclass, field

TRAPDOOR_TILE = 26
CAPACITY = 30
OPEN_CUE, CLOSE_CUE = 197, 27
# 10:24fa requests the loop cue 198 while neither 197 nor 198 plays;
# 10:2328 stops it when a door closes.
LOOP_CUE = 198
# DATA a5-0x2866: animation record by low phase; a5-0x2842: the records'
# (shape, dx, dy), shapes numbered from Temple SHPL 3500's first (3501).
PHASE_FRAMES = (66, 0, 0, 1, 1, 1, 1, 2, 2, 3, 4, 0, 1, 2, 3, 4, 0, 4)
FRAMES = ((51, 11, 8), (52, 20, 12), (53, 7, 5), (54, 1, -6), (28, 1, 0))


@dataclass
class TrapDoors:
    bank: list = field(default_factory=list)
    # The last presentation's objects (not saved).
    drawn: list = field(default_factory=list)

    def trigger(self, terrain, tile, actor_column):
        """TriggerTrapDoor 10:25aa-26d4 for a tile-26 cell; returns cues.

        The floor becomes space (foreground 0x81) at once. A door away from
        the actor's supporting column starts at phase 75 (low phase 11)."""
        caverns = terrain.caverns
        if tile.room is None or tile.kind != TRAPDOOR_TILE or tile.foreground & 0x40:
            return ()
        cell = tile.row * 10 + tile.column
        caverns.loose.tiles[tile.room, cell] = 0, 0x81
        if len(self.bank) < CAPACITY:
            phase = 75 if actor_column != tile.column else 1
            self.bank.append((tile.column * 51, (tile.row + 1) * 120 + 5, tile.room + 1, 0, 0, 10,
                              tile.row, phase))
        return (OPEN_CUE,)

    def advance(self):
        """10:24fa through MakeRubble 5:29e8: low phases up to 16 advance;
        records marked -1 are compacted out. True when a door asked for the
        loop sound (every remaining record queries PrinceSndOn)."""
        self.bank = [record for record in self.bank if record[3] != -1]
        for index, record in enumerate(self.bank):
            if record[7] & 31 <= 16:
                self.bank[index] = (*record[:7], record[7] + 1)
        return bool(self.bank)

    def present(self, terrain):
        """ATMTrapDoor 10:225c: past low phase 16 the floor returns (tile 26,
        foreground low byte cleared) and the record is marked -1. Returns
        cues and the drawn (shape, x, y, clip) objects by port room."""
        cues, drawn = [], []
        for index, record in enumerate(self.bank):
            x, y, room, mark, _, _, row, word = record
            if mark == -1:
                continue
            phase = word & 31
            if phase > 16:
                self.bank[index] = (*record[:3], -1, *record[4:])
                key = room - 1, row * 10 + x // 51
                value = terrain.tile(key[0], key[1] % 10, row).foreground
                terrain.caverns.loose.tiles[key] = TRAPDOOR_TILE, value & 0xff00
                cues.append(CLOSE_CUE)
                continue
            shape, dx, dy = FRAMES[PHASE_FRAMES[phase]]
            drawn.append((room - 1, 3500 + shape, x + dx, y + dy, x))
        return tuple(cues), drawn
