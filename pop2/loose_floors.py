"""Loose-floor controllers recovered from Macintosh CODE:5."""

from dataclasses import dataclass, field
import struct

from pop2.opponent_generation import EMPTY_TILES, character_column
from pop2.terrain import floor_contact_x, floor_edge_distance, floor_y


def pressure_tile(terrain, motion, state, record):
    """CheckPress supporting-foot/pose eligibility, shared by floors and plates."""
    if state.actor_type in (10, 11):
        return None
    column = character_column(floor_contact_x(state.target_x, state.facing, record))
    above = 87 <= state.action <= 99 or 135 <= state.action < 141
    grounded = state.animation_state < 2 or state.animation_state in (5, 7, 8)
    if not (above or grounded):
        return None
    tile = terrain.tile(motion.room, column, motion.row - 1)
    if not above:
        if state.action == 79 and tile.kind in (11, 15):
            return tile
        if not record.aux & 0x40:
            return None
        tile = terrain.tile(motion.room, column, motion.row)
    if floor_y(motion.row) + state.current_y < motion.row * 120 + 95:
        return None
    return tile


def space_foreground(value, environment=3):
    # MakeSpace 5:2698-26b6 keeps the native decoration bits.
    return (value & (0x3080 if environment == 2 else 0x0f80)) | 3


def rubble_tile(kind, foreground):
    # MakeRubble 5:2c36-2f2c, ordinary cavern surfaces.
    if kind in (19, 32):
        return 32, foreground
    if kind == 1:
        return 14, foreground
    if kind in (2, 5, 6, 10, 33, 34):
        return 14, 0
    if kind in (12, 13):
        return kind, foreground | 0x20
    return kind, foreground


def cleared_below_cell(terrain, room, cell):
    # ClearCaveBelowFloor (8:39b8) uses a strict >30 room crossing.
    cell += 10
    if cell > 30:
        room, cell = terrain.neighbor(room, 'down'), cell - 30
    elif cell == 30:
        room, cell = room + 1, 0
    return (room, cell) if room is not None and room < 32 else None


@dataclass
class FallingFloor:
    room: int | None
    column: int
    row: int
    y: int
    velocity: int = 0
    mob_type: int = 0

    @property
    def x(self):
        return self.column * 51

    @property
    def size(self):
        # ComputeMobRect 5:32f6, DATA a5-0x4518/-0x44fc.
        return (91, 31) if self.mob_type == 3 else (87, 43)


@dataclass
class LooseFloors:
    tiles: dict = field(default_factory=dict)
    active: dict = field(default_factory=dict)
    falling: list = field(default_factory=list)
    cleared: set = field(default_factory=set)
    plate_events: list = field(default_factory=list)
    shake_events: list = field(default_factory=list)
    # Crevice cells revealed while their room was displayed: drawn as the
    # original's per-cell redraw until the room is entered again.
    redrawn: set = field(default_factory=set)

    def trigger(self, tile, force=False):
        if tile.room is None or tile.kind != 11:
            return ()
        key = tile.room, tile.row * 10 + tile.column
        if key not in self.active and len(self.active) >= 20:
            return ()
        value = tile.foreground & 0xffbf
        if force:
            value = (value & 0xfff0) | 11
        self.tiles[key] = 11, value
        self.active[key] = int(force)
        return (28,)

    def press(self, terrain, motion, state, record):
        tile = pressure_tile(terrain, motion, state, record)
        if tile is not None and tile.kind == 15:
            return self.break_shelf(terrain, tile, motion.room)
        return self.trigger(tile) if tile is not None else ()

    def break_shelf(self, terrain, tile, visible_room=None):
        # 7:36a0: type15 becomes space immediately, spawning a ruins MOB3
        # without the type11 warning/phase controller or cue28.
        if tile.room is None or tile.kind != 15:
            return ()
        key = tile.room, tile.row * 10 + tile.column
        self.tiles[key] = 0, space_foreground(tile.foreground)
        y = (tile.row + 1) * 120 + 5
        if (visible_room is not None and tile.row == 2
                and tile.room == terrain.neighbor(visible_room, 'down')):
            y += 5
        if len(self.falling) < 30:
            self.falling.append(FallingFloor(tile.room, tile.column, tile.row, y, mob_type=3))
        return ()

    def shake_row(self, terrain, room, row, state=None, motion=None, record=None):
        # ShakeEm 5:2876 and 27b4: a short warning, or a full collapse on
        # the third shake / when the actor is in the native nearby column.
        self.shake_events.append((room, row))
        sounds = []
        column = (character_column(floor_contact_x(state.target_x, state.facing, record))
                  if state is not None and record is not None else None)
        for col in range(10):
            tile = terrain.tile(room, col, row)
            if tile.kind == 15:
                self.break_shelf(terrain, tile, motion.room if motion is not None else None)
                continue
            if tile.kind == 26 and getattr(terrain, 'caverns', None) is not None:
                # 5:28c8: the temple's trap doors open (TriggerTrapDoor 10:25aa).
                sounds.extend(terrain.caverns.trapdoors.trigger(terrain, tile, column))
                continue
            if tile.room is None or tile.kind != 11 or tile.foreground & 15:
                continue
            key = tile.room, tile.row * 10 + tile.column
            if key in self.active or len(self.active) >= 20:
                continue
            count = ((tile.foreground & 0x30) >> 4) + 1
            nearby = (motion is not None and column == tile.column
                      and motion.row in (tile.row, tile.row - 1, 0, 2))
            value = tile.foreground
            if (not nearby and count != 3) or (state is not None and state.actor_type == 1):
                value = (value & 0xffcf) | (count << 4) | 0x40
            self.tiles[key] = 11, value
            self.active[key] = 1
            sounds.append(28)
        return tuple(sounds)

    def advance_tiles(self, terrain):
        # AnimLoose 5:446a: four warning phases, twelve collapse phases.
        for key, velocity in tuple(self.active.items()):
            room, cell = key
            tile = terrain.tile(room, cell % 10, cell // 10)
            value = (tile.foreground + 1) & 0xffff
            phase = value & 15
            if value & 0x40:
                if phase >= 4:
                    value &= 0xffb0
                    del self.active[key]
                self.tiles[key] = tile.kind, value
            elif phase < 12:
                self.tiles[key] = tile.kind, value
            else:
                self.tiles[key] = 0, space_foreground(value)
                below = cleared_below_cell(terrain, room, cell)
                if below is not None:
                    target = terrain.tile(below[0], below[1] % 10, below[1] // 10)
                    self.tiles[below] = target.kind, target.foreground & 0xf0ff
                self.cleared.add(key)
                if len(self.falling) < 30:
                    ruins = struct.unpack_from('>H', terrain.level, 0x2186)[0] == 4
                    self.falling.append(FallingFloor(room, cell % 10, cell // 10,
                                        (cell // 10 + 1) * 120 + (5 if ruins else 23),
                                        velocity, 3 if ruins else 0))
                del self.active[key]

    def advance_falling(self, terrain, state=None, motion=None, record=None):
        # MakeRubble 5:2b10: +8 gravity, terminal speed 64; room cut is 365.
        sounds, advanced, survivors, added = [], [], [], []
        for block in tuple(self.falling):
            if block.velocity < 60:
                block.velocity += 8
            block.y += block.velocity
            finished = False
            if block.room is None:
                finished = block.y >= 365 + block.size[1]
            elif block.y >= block.row * 120 + 120:
                tile = terrain.tile(block.room, block.column, block.row)
                if tile.kind == 11:
                    # 5:2f42 removes a struck loose floor and splits the
                    # falling slabs, with half velocity for both pieces.
                    self.tiles[tile.room, tile.row * 10 + tile.column] = (
                        0, space_foreground(tile.foreground))
                    block.velocity //= 2
                    added.append(FallingFloor(tile.room, tile.column, tile.row + 1,
                                 block.y + 6, block.velocity, block.mob_type))
                    block.row += 1
                elif tile.kind == 15:
                    count = len(self.falling)
                    self.break_shelf(terrain, tile, motion.room if motion is not None else None)
                    # The new shelf has not moved in this MakeRubble pass.
                    added.extend(self.falling[count:])
                    block.row += 1
                elif tile.kind in EMPTY_TILES:
                    block.row += 1
                else:
                    sounds.append(26)
                    sounds.extend(self.shake_row(terrain, block.room, block.row, state, motion, record))
                    if tile.kind in (5, 6, 34):
                        self.plate_events.append((tile.room, tile.row * 10 + tile.column, tile.kind))
                    self.tiles[tile.room, tile.row * 10 + tile.column] = rubble_tile(
                        tile.kind, tile.foreground)
                    block.y = block.row * 120 + 120
                    finished = True
                if block.row >= 3:
                    block.row = 0
                    block.y -= 365
                    block.room = terrain.neighbor(block.room, 'down')
            advanced.append(block)
            if not finished:
                survivors.append(block)
        for block in added:
            if block.row >= 3:
                block.row = 0
                block.y -= 365
                block.room = terrain.neighbor(block.room, 'down')
        self.falling = survivors + added
        return tuple(sounds), tuple(advanced)


def floor_hits_actor(block, motion, state, record, alive=True):
    # 5:3642 tests the native head height, physical row and supporting column.
    if not alive or block.room != motion.room or block.row != motion.row:
        return False
    height = 0 if state.actor_type == 11 else -38 if state.actor_type in (7, 8) else -57
    if block.y <= floor_y(motion.row) + state.current_y + height:
        return False
    contact = floor_contact_x(state.target_x, state.facing, record)
    column = character_column(contact)
    if block.column == column:
        return True
    if state.actor_type == 11:
        # 5:36e0-3762 also tests the serpent's adjacent body cells.
        distance = floor_edge_distance(contact, state.facing)
        forward = 1 if state.facing else -1
        return (block.column == column - forward and distance > 12
                or block.column == column + forward and distance < 6)
    return False


def crush_sequence(state, fatal):
    """Crushed6:28f0: excluded poses/modes, then the type-specific reaction."""
    if (5 <= state.action < 15 or state.action == 109
            or state.animation_state >= 2 and state.animation_state != 7
            or state.actor_type == 1):
        return None
    if not fatal:
        return 52
    return 146 if state.actor_type in (7, 8) else 169 if state.actor_type == 11 else 22
