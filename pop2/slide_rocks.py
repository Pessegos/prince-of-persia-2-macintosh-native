"""Temple sliding rocks (tile 25, MOB type 6), recovered from CODE:10.

The rules follow Codex's native-checked reference models (tools/
probe_temple_slide_rock_*.py, docs/research/temple-slide-rock-*.md). Records
keep the native eight signed words (X, Y, one-based room, mark, control,
type 6, row, original X); X is room-local, without the 207 origin.
"""

from dataclasses import dataclass, field
import struct

SLIDE_ROCK_TILE = 25
# The native MOB bank holds 30 records (5:2914).
CAPACITY = 30
# IsSpace 3:4eb2 kinds and the rock marker stop the band scan 10:1ca4.
SCAN_STOPS = frozenset((0, 9, 27, 47, 49, SLIDE_ROCK_TILE))
EDGE_WALLS = frozenset((20, 2, 7, 25, 43, 4))
# IsWall 3:4ef2 kinds.
WALLS = frozenset((2, 7, 20, 25, 43))
# DATA a5-0x4518/-0x44fc: object heights and widths by MOB type.
HEIGHTS = (43, 0, 5, 31, 65, 79, 132, 132, 27, 27, 37, 37, 18, 0)
WIDTHS = (87, 0, 5, 91, 45, 33, 82, 82, 36, 36, 69, 57, 17, 0)
# The three decoration strips (types 8, 8, 9): offsets from the rock.
DECORATIONS = ((8, 79, -68), (8, 76, -37), (9, 66, -57))
MOVING_CUE, STOP_CUE, WALL_CUE = 192, 192, 18


def signed_word(value):
    return (value + 0x8000) % 0x10000 - 0x8000


def trunc_div(value, divisor=51):
    return (abs(value) // divisor) * (-1 if value < 0 else 1)


def object_shape(kind, phase=0):
    """DrawMob 10:1788: the scenery piece (SHAP 3500 + piece) of a type."""
    return 3500 + {6: 0x5d, 7: 0x54, 8: 0x59 + phase, 9: 0x55 + phase}[kind]


def face_column(candidate):
    """10:1d5c's obstacle column ahead of a rock at ``candidate`` X."""
    front = signed_word(candidate - 31)
    return trunc_div(front) - int(front <= 0)


@dataclass
class SlideRocks:
    bank: list = field(default_factory=list)
    sounds: list = field(default_factory=list)

    @staticmethod
    def kind(terrain, room, column, row):
        return terrain.tile(room - 1, column, row).kind

    def trigger(self, room, cell, mode):
        """TriggerObject 5:1fba-1fda -> TriggerSlideRock 10:2152.

        ``mode`` is the caller's (the plate kind): 5 resumes a rock waiting at
        control -2, anything else starts one."""
        how = 2 if mode == 5 else 1
        row, column = divmod(cell, 10)
        for index, record in enumerate(self.bank):
            if record[5] == 6 and record[3] != -1 and record[2] == room and record[6] == row:
                record = list(record)
                if how == 1 and record[4] >= 0 and record[4] != 100:
                    record[4] = -2
                elif how == 2 and record[4] == -2:
                    record[4] = 2
                self.bank[index] = tuple(record)
                return
        if how == 1 and len(self.bank) < CAPACITY:
            x = column * 51
            self.bank.append((x, 116 + row * 120, room, 0, -2, 6, row, x))

    def span(self, terrain, mob, row_offset, length):
        """10:1ca4: no IsSpace kind nor marker in the scanned columns."""
        x, anchor = mob[0], mob[7] & 0xffff
        distance = signed_word(min(length, anchor - x))
        for column in range(trunc_div(x + 2), trunc_div(x + distance) + 1):
            if self.kind(terrain, mob[2], column, mob[6] + row_offset) in SCAN_STOPS:
                return False
        return True

    def filled(self, terrain, mob, x):
        """10:1656: both bands, the row above first."""
        mob = (x, *mob[1:])
        return self.span(terrain, mob, -1, 51) and self.span(terrain, mob, 0, 51)

    def move(self, terrain, mob, prince=(0, 0, 0)):
        """Motion 10:1d5c for one record; returns (record, actor events)."""
        result, events = list(mob), []
        if result[4] in (0, 100):
            return tuple(result), events
        x = candidate = result[0]
        if result[4] == -2:
            candidate -= 2
        elif self.filled(terrain, result, x) and result[4] >= 8:
            result[4] = 0
            self.sounds.append(('stop', STOP_CUE))
        else:
            if self.filled(terrain, result, signed_word(x - 16)):
                self.sounds.append(('play', 191))
            candidate -= 2
            if result[4] <= 8:
                result[4] = signed_word(result[4] + 1)
        if candidate < 0:
            link = terrain.neighbor(result[2] - 1, 'left')
            result[2] = 0 if link is None else link + 1
            candidate += 510
        if result[2] == 0:
            result[3] = -1
            self.sounds.append(('stop', STOP_CUE))
            return tuple(result), events
        if result[4] in (0, 100):
            return tuple(result), events
        column = face_column(candidate)
        front_tile = self.kind(terrain, result[2], column, result[6])
        if result[3] == 1:
            result[3], result[4] = 0, 100
            result[1] = signed_word(result[1] + 1)
            result[0] = signed_word(candidate + 3)
            if front_tile == 2:
                events.append('5:3cee')
        else:
            old_column, new_column = trunc_div(x - 6), trunc_div(candidate - 6)
            if new_column != old_column or column != old_column:
                edge = self.kind(terrain, result[2], new_column, result[6])
                if (edge in EDGE_WALLS or front_tile == 2) and result[3] == 0:
                    result[3] = 1
                    result[1] = signed_word(result[1] - 1)
                    if front_tile != 2:
                        self.sounds.append(('play', WALL_CUE))
            frame, prince_column, prince_row = prince
            if (87 <= frame <= 99 and result[6] + 1 == prince_row
                    and prince_column == trunc_div(candidate - 12)):
                # 6:1a84: the hanging Prince below lets go.
                events.append('6:1a84')
        if result[4] == 100:
            self.sounds.append(('stop', STOP_CUE))
        else:
            result[0] = signed_word(candidate)
            if result[4] != 0:
                self.sounds.append(('play', MOVING_CUE))
        return tuple(result), events

    def update(self, terrain, prince=(0, 0, 0)):
        """The type-6 case of MakeRubble 5:2afa for every record, then the
        removed records are compacted. Returns [(record, actor events)]."""
        self.sounds.clear()
        moved = []
        for index, record in enumerate(self.bank):
            if record[5] != 6:
                continue
            record, events = self.move(terrain, record, prince)
            self.bank[index] = record
            moved.append((record, events))
        self.bank = [record for record in self.bank if record[3] != -1]
        return moved

    @staticmethod
    def crushes(mob, room, row, front, sequence_mode=0, facing=0, width=0):
        """CheckSlideRockCrush 10:16f6: the Prince's (native) front within
        the 24 pixels ahead of the rock's face, in its room and row. Facing
        left (native facing -1; ``facing`` is the port's 1 right / 0 left),
        the front is X plus the saved ShapeBounds width a5-0x3570."""
        if mob[2] != room or mob[6] != row:
            return False
        if not facing:
            front = signed_word(front + width)
        lower = signed_word(mob[0] + 223)
        return sequence_mode == 4 or lower < front < lower + 25

    @staticmethod
    def room_offsets(terrain, room):
        """ComputeMobRect 5:32f6's projection of the eight rooms around the
        native view ``room`` (a5-0x4fc0..-0x4fb2): every horizontal relation
        passes -510 (5:3364/3380 both load 0xfe02), above -365, below +365."""
        if terrain is None:
            return {room: (0, 0)}

        def link(native, side):
            if not native:
                return None
            linked = terrain.neighbor(native - 1, side)
            return None if linked is None else linked + 1

        left, right, up, down = (link(room, side) for side in ('left', 'right', 'up', 'down'))
        related = {left: (-510, 0), right: (-510, 0), up: (0, -365), down: (0, 365),
                   link(up, 'left') or link(left, 'up'): (-510, -365),
                   link(up, 'right') or link(right, 'up'): (-510, -365),
                   link(down, 'left') or link(left, 'down'): (-510, 365),
                   link(down, 'right') or link(right, 'down'): (-510, 365)}
        related.pop(None, None)
        related[room] = (0, 0)
        return related

    def objects(self, terrain, room):
        """ATMSlideRock 10:1456: drawn objects (type, x, y, phase, clip) of the
        rocks seen from native ``room``; x/y are view coordinates, y the
        bottom, clip the ComputeMobRect 5:32f6 rectangle (top, left, bottom,
        right). Rocks of neighbouring rooms are offset like their rectangle
        (the drawing position's projection is assumed to match it)."""
        drawn = []
        offsets = self.room_offsets(terrain, room)
        for mob in self.bank:
            if mob[5] != 6 or mob[3] == -1 or mob[2] not in offsets:
                continue
            shift_x, shift_y = offsets[mob[2]]
            start = len(drawn)
            heights = list(HEIGHTS)
            if terrain is not None and self.span(terrain, mob, -1, 82):
                # A filled upper band draws the body shorter (10:15a6).
                heights[6], heights[7] = 109, 111
            x, y, anchor = mob[0], mob[1], mob[7] & 0xffff

            def add(kind, at_x, at_y, phase=0):
                drawn.append((kind, at_x, at_y, phase,
                              (at_y - heights[kind], at_x, at_y + 1, at_x + WIDTHS[kind])))

            add(7, x, y)
            if x + 51 < anchor:
                add(6, x + 51, y - 2)
            for kind, dx, dy in DECORATIONS:
                strip = x + dx
                phase = (strip & 7) >> 1
                while strip < anchor:
                    add(kind, strip, y + dy, phase)
                    strip += 36
            if shift_x or shift_y:
                drawn[start:] = [(kind, x + shift_x, y + shift_y, phase,
                                  (top + shift_y, left + shift_x, bottom + shift_y, right + shift_x))
                                 for kind, x, y, phase, (top, left, bottom, right) in drawn[start:]]
        return drawn

    def edge(self, room, row):
        """GetSlideRockX 5:21f6/10:20fe: the first live rock's face in the
        room and row (native X), or 0."""
        for mob in self.bank:
            if mob[5] == 6 and mob[3] != -1 and mob[2] == room and mob[6] == row:
                return signed_word(mob[0] + 279)
        return 0

    def barrier_edge(self, level, room, row, x, facing, width):
        """GetSlideRockX 5:21f6 -> 10:20fe/180e as Collide 4:589e asks it:
        the first live rock's right edge (X + 279) in native ``room`` and
        row; a ``x`` left of it gets the rock's left edge, raised to the
        boundary of a wall or gate cell there (raw LEVL kind). ``facing`` is
        the port's (1 right); facing right (native 0), that boundary adds
        ``width``."""
        record = next((mob for mob in self.bank if mob[5] == 6 and mob[3] != -1
                       and mob[2] == room and mob[6] == row), None)
        if record is None:
            return 0
        edge = signed_word(record[0] + 279)
        if not edge or x >= edge:
            return edge
        edge = signed_word(record[0] + 223 - 5)
        before_divide = signed_word(signed_word(edge - 51) - 22)
        quotient = trunc_div(signed_word(before_divide - 4))
        column = signed_word(quotient - 4 - int(before_divide < 0))
        offset = (record[2] - 1) * 60 + (record[6] * 10 + column) * 2
        if 0 <= offset <= len(level) - 2:
            kind = struct.unpack_from('>h', level, offset)[0]
            if kind in WALLS or kind == 4:
                boundary = signed_word(258 + column * 51 + 39)
                if facing:
                    boundary = signed_word(boundary + width)
                edge = max(edge, boundary)
        return edge
