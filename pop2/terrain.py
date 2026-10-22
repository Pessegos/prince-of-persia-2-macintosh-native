"""LEVL rooftop geometry and the recovered ordinary-character fall rules."""

from dataclasses import dataclass
import struct

from pop2.opponent_generation import character_column, EMPTY_TILES, WALL_TILES
from pop2.mac_input import StepBoundary
from pop2.harbor import SHIP_CLIMB_SEQUENCE, SHIP_ROOM, WATER_ROOMS


TILE_WIDTH = 51
TILE_HEIGHT = 120
ROOM_WIDTH = 510
ROOM_HEIGHT = 365
FLOOR_OFFSET = 106
GRAVITY = 6
MAX_FALL_SPEED = 63
VOID_DEATH_Y = 730
DOWN_CUT_Y = 440


def floor_y(row):
    # SetCharFloor, CODE:4 0x31fa.
    return row * TILE_HEIGHT + FLOOR_OFFSET


def character_row(y):
    # GetRow, CODE:4 0x3afa: DIVS truncates towards zero.
    value = y - 5
    return (abs(value) // TILE_HEIGHT * (-1 if value < 0 else 1)
            - int(value <= 0))


def floor_contact_x(x, facing, record):
    # GetFCharX, CODE:4 0x3a72, then GetCharCol 0x3ad6. FRAM's lower
    # six flag bits locate the supporting foot, not the sprite's anchor.
    offset = record.offset_x - (record.aux & 0x3f)
    return x + offset * (1 if facing else -1)


def floor_edge_distance(contact_x, facing):
    # GetDist1 (4:3aa0) uses GetCharCol's signed DIVS remainder (5:48b0).
    numerator = contact_x + 181
    quotient = abs(numerator) // TILE_WIDTH * (-1 if numerator < 0 else 1)
    remainder = numerator - quotient * TILE_WIDTH
    return 50 - remainder if facing else remainder


def stone_gate_blocks(foreground, bounds, state=None):
    # Gate collision 4:5b0e-5ba2 uses the viewport-clipped body rectangle
    # and quarter-phase steps, not a fixed open/closed threshold.
    actor = state.actor_type if state is not None else 0
    if actor == 1 or (state is not None and state.source_sequence_id == 68):
        return False
    height = max(0, min(365, bounds[3] + 1) - max(0, bounds[1]))
    height += {7: 46, 8: 33}.get(actor, 0)
    return ((foreground & 255) >> 2) * 2 + 11 < height + 13


@dataclass(frozen=True)
class Tile:
    kind: int
    foreground: int = 0
    background: int = 0
    room: int | None = None
    column: int = 0
    row: int = 0


class LevelMap:
    def __init__(self, level):
        self.level = level
        self.start_room = struct.unpack_from(">H", level, 0x2198)[0] - 1
        self.start_tile = struct.unpack_from(">H", level, 0x219a)[0]
        self.desert = None
        self.caverns = None

    def neighbor(self, room, direction):
        offset = {"left": 0, "right": 2, "up": 4, "down": 6}[direction]
        value = struct.unpack_from(">H", self.level, 0x2080 + room * 8 + offset)[0]
        return value - 1 if value else None

    def allows_down_cut(self, room, actor_type=0):
        # CutChar 6:4c90-4cd2 vetoes these native rooms before following
        # their lower LEVL links. NPCs use Cut (6:472a), without this veto.
        # Room IDs here are zero-based.
        if actor_type not in (0, None):
            return True
        kind = struct.unpack_from(">H", self.level, 0x2186)[0]
        blocked = {5: (10,), 6: (2, 4)}
        return room not in blocked.get(kind, ())

    def tile(self, room, column, row):
        # Same vertical-before-horizontal link traversal as GetBlock/Cut.
        while not 0 <= column < 10 or not 0 <= row < 3:
            if row < 0:
                direction, row = "up", row + 3
            elif row >= 3:
                direction, row = "down", row - 3
            elif column < 0:
                direction, column = "left", column + 10
            else:
                direction, column = "right", column - 10
            room = self.neighbor(room, direction)
            if room is None:
                # GetUndefineCellId 4:28e8 returns air for rooftop levels.
                level_kind = struct.unpack_from(">H", self.level, 0x2186)[0]
                return Tile(0 if level_kind == 5 else 20)
        index = row * 10 + column
        kind = struct.unpack_from(">H", self.level, room * 60 + index * 2)[0]
        fg, bg = struct.unpack_from(">2H", self.level, 0x780 + room * 120 + index * 4)
        if self.caverns is not None:
            kind = self.caverns.loose.tiles.get((room, index), (kind, fg))[0]
            kind = self.caverns.potions.tiles.get((room, index), (kind, fg))[0]
            fg = self.caverns.foreground(room, index, fg)
        if kind == 4 and self.desert is not None:
            fg = (fg & 0xff00) | (104 if self.desert.exit_open else 0)
        elif kind == 30 and self.desert is not None and room == 0 and row == 1 and 2 <= column <= 7:
            stone = self.desert.stones[column - 2]
            fg = (fg & 0xfe00) | stone.phase | (stone.delay << 4)
        return Tile(kind, fg, bg, room, column, row)

    def supports(self, room, column, row):
        tile = self.tile(room, column, row)
        return tile.room is not None and tile.kind not in EMPTY_TILES

    def step_clearance(self, room, row, x, direction):
        # Existing NPC patrol bounds; player caution uses step_boundary below.
        column = character_column(x)
        for distance in range(0, 12):
            col = column + direction * distance
            tile = self.tile(room, col, row)
            if tile.room is None or tile.kind in EMPTY_TILES | WALL_TILES:
                edge = col * TILE_WIDTH if direction > 0 else (col + 1) * TILE_WIDTH
                return max(0, (edge - x) * direction)
        return ROOM_WIDTH

    def run_jump_offset(self, room, row, state):
        # DoRunJump (6:1c50-1d3a) aligns takeoff to the next obstruction.
        # A late Prince jump is rejected; it does not acquire extra range.
        direction = 1 if state.facing else -1
        look = state.target_x + 13 * direction
        column = character_column(look)
        clear = 0
        for ahead in (1, 2):
            tile = self.tile(room, column + direction * ahead, row)
            blocked = (tile.kind in WALL_TILES | EMPTY_TILES
                       or tile.kind in {15, 26, 12, 13}
                       or (tile.kind == 4 and (tile.foreground & 255) < 104))
            if blocked:
                break
            clear += 1
        if clear == 2:
            return 0
        reserve = 48 if state.actor_type == 0 else 75
        adjustment = floor_edge_distance(look, state.facing) + clear * TILE_WIDTH - reserve
        if not -31 <= adjustment < 15:
            if adjustment < 0 and state.actor_type == 0:
                return None
            adjustment = -13
        return (13 + adjustment) * direction

    def step_boundary(self, room, row, state, record, bounds, *, cautious=False):
        # GetBarrDistances (4:5eae): inspect the supporting foot's tile and
        # its immediate neighbor, not a geometric edge or a whole-room scan.
        contact = floor_contact_x(state.target_x, state.facing, record)
        column = character_column(contact)
        direction = 1 if state.facing else -1
        current = self.tile(room, column, row)
        ahead = self.tile(room, column + direction, row)
        distance = floor_edge_distance(contact, state.facing)
        for col, tile in ((column, current), (column + direction, ahead)):
            # GetBarrierType/DistToBarrier; c944 enables type 3 for tile 2.
            stone_gate = (tile.kind == 4 and struct.unpack_from('>H', self.level, 0x2186)[0] == 3
                          and stone_gate_blocks(tile.foreground, bounds, state))
            if tile.kind in WALL_TILES | {12} or stone_gate:
                barrier = (5 if stone_gate else 6 if tile.kind == 12 else
                           3 if cautious and tile.kind == 2 and (tile.foreground & 255) < 3 else 4)
                left_offset = {3: -22, 4: 3, 5: 18, 6: 8}[barrier]
                right_offset = {3: -22, 4: 0, 5: 0, 6: 16}[barrier]
                # GetCharEdges / QuickDraw uses an exclusive right edge;
                # Pillow's last sprite column is inclusive.
                barrier_distance = (col * TILE_WIDTH + 22 + left_offset - (bounds[2] + 1)
                                    if state.facing else
                                    bounds[0] - (col * TILE_WIDTH + 72 - right_offset))
                if barrier_distance >= 0:
                    return StepBoundary(barrier_distance,
                                        1 if barrier_distance < 51 else 2, tile.kind)
            if tile.kind in (23, 24):
                # 4:5fa2/5fc6 use opposite offsets inside/approaching the tile.
                if (tile.kind == 24 and not state.facing) or (tile.kind == 23 and state.facing):
                    same_column = col == column
                    if tile.kind == 24:
                        distance += -17 if same_column else 34
                    else:
                        distance += -33 if same_column else 18
                    return StepBoundary(distance, tile_kind=tile.kind)
                return StepBoundary(42, 2, tile.kind)
        kind = ahead.kind
        if kind in EMPTY_TILES | {11, 15, 26, 12, 13, 30}:
            return StepBoundary(distance, tile_kind=kind)
        if kind in (2, 6, 22, 34) and distance:
            return StepBoundary(distance - 1, tile_kind=kind)
        # Ordinary clear floor returns 42 before DoStepFwd reserves four.
        return StepBoundary(42, 2, kind)

    def standing_turn_offset(self, room, row, state, record, bounds):
        # Standing Backward 6:10f6-1154 reserves eleven foot-space pixels
        # before a blocking cavern gate, before SEQS:5 changes facing.
        if state.level_kind != 3:
            return 0
        direction = 1 if state.facing else -1
        contact = floor_contact_x(state.target_x, state.facing, record)
        ahead = self.tile(room, character_column(contact) + direction, row)
        if ahead.kind != 4 or not stone_gate_blocks(ahead.foreground, bounds, state):
            return 0
        return min(0, floor_edge_distance(contact, state.facing) - 11) * direction

    def combat_turn_offset(self, room, row, state, record, bounds=None):
        # DoTurn, CODE:6 0x26dc-0x276c. A gate cell is a barrier only when
        # the gate collision 4:5b0e blocks the current body (0x26f6/0x2720).
        contact_x = floor_contact_x(state.target_x, state.facing, record)
        column = character_column(contact_x)
        direction = 1 if state.facing else -1
        allowance = None
        for ahead in (1, 2):
            tile = self.tile(room, column + direction * ahead, row)
            kind = tile.kind
            gate = (kind == 4 and bounds is not None and state.level_kind == 3
                    and stone_gate_blocks(tile.foreground, bounds, state))
            if kind in EMPTY_TILES | WALL_TILES or gate:
                allowance = (ahead - 1) * TILE_WIDTH
                break
        if allowance is None:
            return 0
        if state.source_sequence_id == 94:
            allowance += 22
        elif state.action == 207:
            allowance += TILE_WIDTH
        distance = floor_edge_distance(contact_x, state.facing) + allowance
        return min(0, distance - 84)

    def combat_draw_offset(self, room, row, state, record, bounds):
        # DrawSword, CODE:6 0x2072-0x2122 reserves 56 pixels before a
        # gap OR a solid barrier, using GetBarrDistances (4:5eae).
        contact_x = floor_contact_x(state.target_x, state.facing, record)
        column = character_column(contact_x)
        direction = 1 if state.facing else -1
        if (self.tile(room, column, row).kind in EMPTY_TILES | WALL_TILES
                or self.tile(room, column + direction, row).kind not in EMPTY_TILES | WALL_TILES):
            return 0
        return min(0, self.step_boundary(room, row, state, record, bounds).clearance - 56)

    def align_fall(self, room, row, state, record):
        # CODE:4 4b16 runs after advancing the floor row, before the fall pose.
        # The source keeps the old supporting column until LoadFrame (4:2a72).
        direction = 1 if state.facing else -1
        contact = floor_contact_x(state.target_x, state.facing, record)
        column = character_column(contact)
        current_above = self.tile(room, column, row - 1).kind
        ahead_above = self.tile(room, column + direction, row - 1).kind
        behind_above = self.tile(room, column - direction, row - 1).kind
        if (self.tile(room, column + direction, row).kind in WALL_TILES
                or current_above not in EMPTY_TILES or ahead_above not in EMPTY_TILES):
            distance = floor_edge_distance(contact, state.facing)
            if distance <= 17:
                dx = (distance - 20) * direction
                state.target_x += dx
                contact += dx
        if (self.tile(room, column - direction, row).kind in WALL_TILES
                or current_above not in EMPTY_TILES or behind_above not in EMPTY_TILES):
            distance = floor_edge_distance(contact, state.facing)
            if distance >= 34:
                state.target_x += (distance - 31) * direction
        if current_above not in EMPTY_TILES or ahead_above not in EMPTY_TILES:
            state.current_y = max(state.current_y, -FLOOR_OFFSET)
        state.current_x = state.target_x

    def ledge(self, room, row, x, facing):
        direction = 1 if facing else -1
        column = character_column(x)
        for col in range(column - 1, column + 2):
            if (self.supports(room, col, row)
                    and self.tile(room, col, row).kind not in WALL_TILES
                    and self.tile(room, col + direction, row).kind in EMPTY_TILES):
                edge = (col + 1) * TILE_WIDTH if direction > 0 else col * TILE_WIDTH
                if edge - 12 <= x <= edge + 8:
                    return edge
        return None

    def descend_ledge(self, room, row, state, record):
        # StairClimbing 6:0ece-0f46: empty behind, floor under the foot,
        # distance >=11. The Prince backs down while facing the building.
        contact = floor_contact_x(state.target_x, state.facing, record)
        column = character_column(contact)
        direction = 1 if state.facing else -1
        current = self.tile(room, column, row)
        behind = self.tile(room, column - direction, row)
        distance = floor_edge_distance(contact, state.facing)
        if (behind.room is not None and behind.kind in EMPTY_TILES
                and current.kind not in EMPTY_TILES | WALL_TILES
                and distance >= 11):
            return (distance - 38) * direction
        return None

    def upper_ledge(self, room, row, state, record):
        # DoJumpUp 6:1610-1682 / 1bbe: current upper tile must be empty
        # and its forward neighbor must offer a real ledge.
        contact = floor_contact_x(state.target_x, state.facing, record)
        column = character_column(contact)
        direction = 1 if state.facing else -1
        above = self.tile(room, column, row - 1)
        ahead = self.tile(room, column + direction, row - 1)
        if (above.room is not None and ahead.room is not None
                and above.kind in EMPTY_TILES
                and ahead.kind not in EMPTY_TILES | WALL_TILES):
            return (floor_edge_distance(contact, state.facing) - 21) * direction
        return None

    def back_ledge_jump(self, room, row, state, record):
        # DoJumpUp 6:1684-16be tests space BEHIND the upper foot when
        # the forward test failed. DoJumpBack/High then align SEQS:24/16.
        contact = floor_contact_x(state.target_x, state.facing, record)
        column = character_column(contact)
        direction = 1 if state.facing else -1
        space = self.tile(room, column - direction, row - 1)
        ledge = self.tile(room, column, row - 1)
        if (space.room is None or ledge.room is None or space.kind not in EMPTY_TILES
                or ledge.kind in EMPTY_TILES | WALL_TILES
                or ledge.kind in (11, 15) and ledge.foreground & 15):
            return None
        environment = struct.unpack_from('>H', self.level, 0x2186)[0]
        if (environment == 2 and not space.foreground & 128
                or environment == 5 and room == 14 and row != 0):
            return None
        distance = floor_edge_distance(contact, state.facing)
        if distance < 24:
            return None
        if self.tile(room, column - direction, row).kind in EMPTY_TILES:
            return 16, (distance - 41) * direction
        backward = (distance - 51) * direction
        aligned = floor_edge_distance(contact + backward, state.facing)
        if aligned == 51:
            aligned = 0
        return 24, backward + (aligned - 21) * direction

    def exit_door(self, room, row, state, record):
        # Up handler 6:0e36: current, behind, then ahead; not the entry room.
        if room == self.start_room or state.actor_type != 0:
            return None
        column = character_column(floor_contact_x(state.target_x, state.facing, record))
        direction = 1 if state.facing else -1
        for col in (column, column - direction, column + direction):
            tile = self.tile(room, col, row)
            if tile.kind == 17:
                return tile if tile.foreground & 255 >= 79 else None
        return None

    def vertical_jump(self, room, row, state, record, bounds):
        # DoJumpUp's ordinary fallback (6:1774-187c) tests the supporting
        # foot eight pixels forward before choosing low SEQS:14 / high 28.
        direction = 1 if state.facing else -1
        boundary = self.step_boundary(room, row, state, record, bounds)
        offset = ((boundary.clearance - 10) * direction
                  if boundary.clearance < 6 and boundary.barrier_type == 1 else 0)
        contact = floor_contact_x(state.target_x + offset + 8 * direction, state.facing, record)
        column = character_column(contact)
        if self.tile(room, column, row - 1).kind in EMPTY_TILES:
            return 28, offset
        environment = struct.unpack_from('>H', self.level, 0x2186)[0]
        # These exceptions are in the native selector, not port-specific
        # protections. Keep the rooftop boat and later temple branches.
        if environment == 5 and room == 14:
            return 28, offset
        cached_column = character_column(floor_contact_x(state.target_x, state.facing, record))
        if environment == 6 and room == 6 and (row != 2 or cached_column not in (2, 6)):
            return 28, offset
        if environment == 6 and room == 7 and (row != 2 or 0 <= cached_column <= 4):
            return 28, offset
        return 14, offset

    def nearby_gate(self, room, row, state, record, *, behind_first=False):
        column = character_column(floor_contact_x(state.target_x, state.facing, record))
        direction = 1 if state.facing else -1
        for offset in ((0, -1, 1) if behind_first else (0, 1, -1)):
            col = column + offset * direction
            tile = self.tile(room, col, row)
            if tile.kind == 4:
                return tile, col
        return None

    def gate_blocks_rise(self, room, row, state, record):
        # GateBarrToStandUp 4:5baa-5c56 tests an anchor band, not body height.
        if state.level_kind != 3:
            return False
        gate = self.nearby_gate(room, row, state, record)
        if gate is None:
            return False
        tile, column = gate
        anchor = state.target_x - 10 * (1 if state.facing else -1) - 22
        return (0 < tile.foreground & 255 < 184
                and column * TILE_WIDTH + 19 <= anchor <= column * TILE_WIDTH + 57)

    def wall_supported_hang(self, room, row, state, record):
        # GenCtrl 6:1920-1968 uses GetBlock under the supporting foot.
        column = character_column(floor_contact_x(state.target_x, state.facing, record))
        tile = self.tile(room, column, row)
        # 6:1926 bypasses IsWall in mode 6: SEQS:25 must finish its six
        # settling poses and hold 91 at -23, rather than restarting at 92.
        return ((state.animation_state != 6 and tile.kind in WALL_TILES)
                or (tile.kind == 4 and not state.facing))

    def climb_sequence(self, room, row, state, record):
        # GenCtrl 6:19d4-1a50 uses the upper supporting tile, not a body
        # overlap. A low gate selects the failed climb (73), then SEQS:11.
        column = character_column(floor_contact_x(state.target_x, state.facing, record))
        tile = self.tile(room, column, row - 1)
        threshold = 30 if state.level_kind == 3 and not state.facing else 12
        if (tile.kind == 4 and state.actor_type != 1
                and (tile.foreground & 255) >> 2 < threshold
                and (not state.facing or state.level_kind == 3)):
            return 73
        return 10

    def release_ledge(self, room, row, state, record, *, next_action=None):
        # GenCtrl's release helper (6:1a84-1b7c), ordinary rooftop tiles.
        # A floor behind the hanging foot uses SEQS:11, not a free fall.
        column = character_column(floor_contact_x(state.target_x, state.facing, record))
        direction = 1 if state.facing else -1
        current = self.tile(room, column, row).kind
        behind = self.tile(room, column - direction, row).kind
        if current in EMPTY_TILES and behind in EMPTY_TILES:
            # DoJumpHang 6:1b7e previews AnimChar: the same/decreasing pose
            # releases toward the ledge (99), an increasing pose away (23).
            return (99 if next_action is not None and next_action <= state.action else 23), 0
        non_floor = EMPTY_TILES | WALL_TILES
        non_landable = non_floor | {11, 15, 26, 12, 13, 23, 24, 6, 34}
        current_floor, behind_floor = current not in non_landable, behind not in non_landable
        if not current_floor and not behind_floor:
            if behind not in non_floor and current in WALL_TILES:
                behind_floor = True
            elif current not in non_floor and behind in WALL_TILES:
                current_floor = True
        if current in WALL_TILES:
            return (11 if behind_floor else 23), -23 * direction
        if behind_floor and not current_floor:
            return 11, -12 * direction
        if current_floor and not behind_floor:
            return 11, 10 * direction
        return (11 if current_floor and behind_floor else 23), 0

    def forced_opponent_tumble(self, room, row, state, record):
        # DoOppTumbleSeq 4:0160-0198: rooftop rooms 16/19, or an empty
        # tile BEHIND a left-facing guard (GetCellsBehind, 4:3a48).
        column = character_column(floor_contact_x(state.target_x, state.facing, record))
        direction = 1 if state.facing else -1
        return room in (15, 18) or (not state.facing and
                                   self.tile(room, column - direction, row).kind in EMPTY_TILES)

    def align_flat_death(self, room, row, state, record):
        # CheckStab 6:5524-5558 and corpse alignment 6:04aa-055a, after
        # the first SEQS:85 pose has loaded its own supporting foot.
        direction = 1 if state.facing else -1
        contact = floor_contact_x(state.target_x, state.facing, record)
        column = character_column(contact)
        if self.tile(room, column, row).kind in EMPTY_TILES | {11, 15, 26}:
            state.target_x -= 36 * direction
            contact = floor_contact_x(state.target_x, state.facing, record)
            column = character_column(contact)
        distance = floor_edge_distance(contact, state.facing)
        neighbor = column + (direction if distance < 32 else -direction)
        if distance != 32 and self.tile(room, neighbor, row).kind in EMPTY_TILES:
            state.target_x += (distance - 32) * direction
        state.current_x = state.target_x

    def landing_offset(self, room, row, state, record):
        # HitFloor 6:02ba-0310 reserves native distance 32 before loading
        # the landing pose when the forward cell cannot receive a landing.
        if state.actor_type in (7, 8):
            return 0
        contact = floor_contact_x(state.target_x, state.facing, record)
        column = character_column(contact)
        if self.tile(room, column, row).kind in (23, 24):
            return 0
        direction = 1 if state.facing else -1
        ahead = self.tile(room, column + direction, row).kind
        impassable = {11, 15, 26, 12, 13, 23, 24}
        distance = floor_edge_distance(contact, state.facing)
        return ((distance - 32) * direction
                if distance <= 30 and ahead in EMPTY_TILES | impassable else 0)

    def fatal_hit_fall_offset(self, room, row, state, record, supporting_column=None):
        # CheckStab 6:5428-54b2 tests the struck pose before loading death.
        # A supported foot can still tip backward over an adjacent empty cell.
        if state.actor_type in (6, 7, 8, 11):
            return None
        contact = floor_contact_x(state.target_x, state.facing, record)
        column = (character_column(contact) if supporting_column is None else supporting_column)
        distance = floor_edge_distance(contact, state.facing)
        if self.tile(room, column, row).kind in EMPTY_TILES:
            return distance - 12
        direction = 1 if state.facing else -1
        if (self.tile(room, column - direction, row).kind in EMPTY_TILES
                and distance >= 6):
            return distance - 12 - TILE_WIDTH
        return None

    def catch_ledge(self, room, row, state, record, harbor=None):
        # Falling 6:011e-0132 / Catch 4:37ca: velocity <60 and feet within
        # [-48,+3] of the lower floor. Catch 4:3882-3894 extends the
        # 17-pixel look-behind by seven after the toward-ledge release (99).
        if state.vertical_velocity >= 60 or not -48 <= state.current_y <= 3:
            return False
        direction = 1 if state.facing else -1
        look_behind = 24 if state.source_sequence_id == 99 else 17
        trial_x = state.target_x - look_behind * direction
        column = character_column(floor_contact_x(trial_x, state.facing, record))
        above = self.tile(room, column, row - 1)
        ahead = self.tile(room, column + direction, row - 1)
        ordinary = (above.room is not None and ahead.room is not None
                    and above.kind in EMPTY_TILES and ahead.kind not in EMPTY_TILES | WALL_TILES
                    # IsLedge 4:3fa4-3fc0: a shut gate has no left-facing grip.
                    and not (ahead.kind == 4 and not state.facing and not ahead.foreground & 255))
        ship = harbor is not None and harbor.can_grab_ship(room, row, trial_x)
        if not ordinary and not ship:
            return False
        state.target_x = trial_x
        state.current_x = trial_x
        state.current_y = 0
        state.horizontal_velocity = state.vertical_velocity = 0
        return True

    def align_catch(self, room, row, state, record):
        # Catch 4:38da-3928 reloads FRAM after pose 80. Its foot can now
        # cross into the roof tile, requiring the native one-cell correction.
        contact = floor_contact_x(state.target_x, state.facing, record)
        column = character_column(contact)
        offset = floor_edge_distance(contact, state.facing) + 12
        if self.tile(room, column, row - 1).kind not in EMPTY_TILES | WALL_TILES:
            offset -= TILE_WIDTH
        if not state.facing and state.level_kind == 5 and room == 18:
            offset -= 42
        state.target_x += offset * (1 if state.facing else -1)
        state.current_x = state.target_x

    def align_wall(self, room, row, state, record):
        # CheckFloor -> CODE:4 3982: put the supporting foot out of a wall.
        contact = floor_contact_x(state.target_x, state.facing, record)
        column = character_column(contact)
        tile = self.tile(room, column, row)
        if (tile.room is None or tile.kind not in WALL_TILES
                or state.sequence_mode == 4 or state.actor_type == 11):
            return tile
        direction = 1 if state.facing else -1
        distance = floor_edge_distance(contact, state.facing)
        ahead = self.tile(room, column + direction, row)
        offset = distance - 51 if distance >= 18 or ahead.kind in WALL_TILES else distance + 18
        state.target_x += offset * direction
        state.current_x = state.target_x
        return self.tile(room, character_column(floor_contact_x(
            state.target_x, state.facing, record)), row)

    def wall_correction(self, room, old_x, new_x, bounds, old_bounds=None, facing=None,
                        physical_row=None, state=None):
        left, top, right, bottom = bounds
        delta = new_x - old_x
        old_left, _, old_right, _ = (old_bounds if old_bounds is not None else
                                    (left - delta, top, right - delta, bottom))
        if not delta and (old_left, old_right) == (left, right):
            return new_x
        corrected = new_x
        # CheckBarr's current-row buffer and CheckCollide1 (4:55fc-562e)
        # use the physical floor row, not every row overlapped by the art.
        rows = (range(character_row(top), character_row(bottom) + 1)
                if physical_row is None else (physical_row,))
        for row in rows:
            for col in range(-1, 11):
                tile = self.tile(room, col, row)
                desert_exit = (tile.kind == 4 and self.desert is not None
                               and not self.desert.exit_open)
                stone_gate = (tile.kind == 4 and struct.unpack_from('>H', self.level, 0x2186)[0] == 3
                              and (state is None or state.actor_type != 11)
                              and stone_gate_blocks(tile.foreground, bounds, state))
                if tile.kind not in WALL_TILES and not desert_exit and not stone_gate:
                    continue
                # GetLeftBarr/GetRightBarr, code 4, DATA c9e0/c9f2[barrier].
                barrier = (5 if stone_gate else 1 if desert_exit else
                           2 if tile.kind == 7 and bottom - top + 1 <= 34 else 4)
                # Tile 2's extended barrier (type 3) exists only while
                # DoStepFwd queries clearance with c944 set, not in Collide.
                left_offset, right_offset = {1: (40, 0), 2: (0, 50), 3: (-22, -22),
                                             4: (3, 0), 5: (18, 0)}[barrier]
                wall_left = col * TILE_WIDTH + 22 + left_offset
                wall_right = col * TILE_WIDTH + 72 - right_offset
                # CheckBarr 4:4f8a-4fb4 only raises a gate side collision
                # when that edge's mask changes. Already underneath it,
                # leave crouching/crushing to CheckGateForKid instead.
                if stone_gate:
                    if facing != 0 and old_right + 1 <= wall_left < right + 1:
                        corrected = min(corrected, new_x + wall_left - right - 1)
                    elif facing != 1 and left < wall_right <= old_left:
                        corrected = max(corrected, new_x + wall_right - left)
                    continue
                # A landing/foot alignment may already overlap the barrier.
                # Keep outward recovery legal, but do not require a clean
                # previous edge before stopping further inward movement.
                if facing != 0 and right > old_right and old_left < wall_left <= right:
                    corrected = min(corrected, new_x + wall_left - right - 1)
                # GetColDetData 4:53c4 uses wall_right > char_left.
                # Equal edges are touching, not a wall collision.
                elif facing != 1 and left < old_left and left < wall_right < old_right:
                    corrected = max(corrected, new_x + wall_right - left)
        return corrected


@dataclass
class TerrainMotion:
    room: int
    row: int
    falling: bool = False
    dead: bool = False
    smooth_landing: bool = False
    scream_played: bool = False
    hit_fall: bool = False
    sinking: bool = False
    lava_landing: bool = False
    gate_contact_bounds: tuple[int, int, tuple[int, int, int, int], tuple[int, int, int, int]] | None = None


@dataclass(frozen=True)
class TerrainEvent:
    kind: str
    damage: int = 0
    death_method: int | None = None


class RooftopPhysics:
    def __init__(self, level_map, frames=None):
        self.map = level_map
        self.frames = frames

    @staticmethod
    def select(runtime, sequence):
        runtime.state.select(sequence)
        runtime.next_frame()

    def cut_horizontal(self, motion, state, bounds):
        left, _top, right, _bottom = bounds
        if motion.falling:
            # CutChar (6:49ce) handles leaving below the viewport BEFORE X.
            # With no lower link it waits until Y >= 440 + sprite height.
            height = _bottom - _top + 1
            margin = height if self.map.neighbor(motion.room, "down") is None else 0
            if floor_y(motion.row) + state.current_y >= DOWN_CUT_Y + margin:
                return False
        # CODE:6 4a26-4a62 excludes these poses before testing either side.
        action = state.action
        if (110 <= action <= 119 or 135 <= action < 163
                or 166 <= action < 169 or state.animation_state == 7):
            return False
        # CutChar, CODE:6 0x4a72/0x4aee/0x4b6c/0x4bc6, scene X = native X - 207.
        # ca8e is LEFT and ca8c is the exclusive RIGHT edge, not vice versa.
        right += 1
        direction = None
        if (left <= -16 if not state.facing else right <= -1):
            direction = "left"
        elif (left >= 510 if not state.facing else right >= 525):
            direction = "right"
        if direction is None:
            return False
        # DesertFunc, rather than CutChar, owns the cave exit and the
        # far-right shore. Their extra LEVL rooms are not camera targets.
        if state.level_kind == 1 and ((motion.room == 0 and direction == "left")
                                     or (motion.room == 2 and direction == "right")):
            return False
        # CutChar 6:4c26-4c48 keeps native room 15 visible on its right exit.
        # RoofMakeWaterTestRect handles the offscreen death separately.
        if direction == "right" and motion.room == 14 and state.level_kind == 5:
            return False
        room = self.map.neighbor(motion.room, direction)
        if room is None:
            return False
        if motion.falling:
            # CODE:6 4dac checks the neighbor's entry tile; pose 102 uses row-1.
            row = motion.row - int(state.action == 102)
            if 0 <= row < 3:
                tile = self.map.tile(room, 0 if direction == "right" else 9, row)
                if tile.kind in WALL_TILES and tile.kind != 7:
                    return False
        dx = ROOM_WIDTH if direction == "left" else -ROOM_WIDTH
        state.current_x += dx
        state.target_x += dx
        motion.room = room
        return True

    def cut_up(self, motion, state):
        # CutChar 6:4994-49ca tests the floor-relative actor Y, not the
        # sprite top. Falling modes 3/4/5 must not select an upper room.
        absolute_y = floor_y(motion.row) + state.current_y
        level_number = struct.unpack_from('>H', self.map.level, 0x218a)[0]
        if (absolute_y >= 19 or state.animation_state in (3, 4, 5)
                or state.source_sequence_id == 70
                or (level_number == 5 and motion.room == 2)):
            return False
        room = self.map.neighbor(motion.room, "up")
        if room is None:
            return False
        motion.room = room
        # Player Cut 6:48da-48ea adds 360 and recomputes GetRow.
        absolute_y += 3 * TILE_HEIGHT
        motion.row = character_row(absolute_y)
        state.current_y = absolute_y - floor_y(motion.row)
        return True

    def cut_down(self, motion, state):
        # CutChar 6:49ce-4a22 selects down at Y >= 440; the player
        # rebase at 6:48f2 subtracts 360, unlike the NPC Cut's 365.
        absolute_y = floor_y(motion.row) + state.current_y
        if (absolute_y < DOWN_CUT_Y or state.source_sequence_id == 70
                or not self.map.allows_down_cut(motion.room, state.actor_type)):
            return False
        room = self.map.neighbor(motion.room, "down")
        if room is None:
            return False
        motion.smooth_landing = (motion.room == 11 and room == 14
                                 and state.actor_type == 0 and state.level_kind == 5)
        motion.room = room
        absolute_y -= 3 * TILE_HEIGHT
        motion.row = character_row(absolute_y)
        state.current_y = absolute_y - floor_y(motion.row)
        return True

    def start_fall(self, motion, runtime):
        state = runtime.state
        contact = (floor_contact_x(state.target_x, state.facing, self.frames[state.action])
                   if self.frames is not None else state.target_x)
        # Retain the cause across SEQS links into the shared free-fall loop.
        motion.hit_fall = state.source_sequence_id in (74, 94, 183)
        # StartFall, CODE:4 0x4cbe-0x4d90, ordinary unarmed rooftop subset.
        sequence = {9: 7, 13: 19, 26: 18, 44: 21}.get(state.action, 7)
        if state.action == 81:
            state.current_y += 24
        elif 81 < state.action < 86:
            sequence = 19
        elif 150 <= state.action < 180:
            if state.actor_type == 2:
                sequence = 83 if state.source_sequence_id in (86, 67, 108, 94) else 82
            else:
                sequence = 95 if state.action == 153 or state.source_sequence_id in (56, 94) else 81
        elif state.actor_type == 2 and state.sequence_id == 100:
            sequence = 186
        motion.row += 1
        state.current_y -= TILE_HEIGHT
        if self.frames is not None:
            self.map.align_fall(motion.room, motion.row, state, self.frames[state.action])
        if state.level_kind == 1:
            # StartFall 4:4d94-4db2: desert falls select SEQS:27, method 8.
            motion.sinking = True
            motion.falling = False
            motion.hit_fall = False
            if self.map.desert is not None:
                cues = self.map.desert.fall_into_sand(character_column(contact))
                state.sound_events.extend(cues)
            self.select(runtime, 27)
            return
        if (state.actor_type in (0, None) and self.floating()
                and state.source_sequence_id != 228):
            # StartFall 4:4db4-4dc8: a floating Prince falls with SEQS:228.
            sequence = 228
        motion.falling = True
        self.select(runtime, sequence)

    def floating(self):
        caverns = getattr(self.map, 'caverns', None)
        return caverns is not None and caverns.potions.floating

    def check_floor(self, motion, runtime, frame_flags, frame_record):
        # CheckFloor 4:35ba tests FRAM bit 0x40, including late climb poses.
        if not frame_flags & 0x40:
            return False
        state = runtime.state
        # CheckFloor 4:3638 / RoofClimbingIntoShip 23:12ba: the ship is
        # moving scenery, not a supporting tile in the level map.
        if (state.level_kind == 5 and motion.room == SHIP_ROOM
                and state.source_sequence_id == SHIP_CLIMB_SEQUENCE):
            return False
        contact = (floor_contact_x(state.target_x, state.facing, frame_record)
                   if frame_record is not None else state.target_x)
        tile = self.map.tile(motion.room, character_column(contact), motion.row)
        if frame_record is not None and tile.kind in WALL_TILES:
            tile = self.map.align_wall(motion.room, motion.row, state, frame_record)
        if tile.kind in EMPTY_TILES or (tile.kind == 30 and (tile.foreground & 15) < 2):
            self.start_fall(motion, runtime)
            return True
        return False

    def check_gate(self, motion, runtime, bounds, old_bounds, record, alive, sword_drawn,
                   contact_bounds=None, invulnerable=False):
        state = runtime.state
        if (not alive or state.actor_type not in (0, None) or state.level_kind != 3
                or state.source_sequence_id == 118 or record is None):
            return None
        # CheckBarr 4:4e46/4fce skips the ordinary collision-buffer update
        # during mode 7. CheckGateForKid still reads the last two masks.
        # A turning arm must not create contact that the standing body lacked.
        context = (motion.room, motion.row)
        if state.animation_state == 7:
            cached = motion.gate_contact_bounds
            if cached is None or cached[:2] != context:
                cached = (*context, old_bounds or bounds, old_bounds or bounds)
                motion.gate_contact_bounds = cached
            contact_bounds = cached[2:]
        else:
            contact_bounds = contact_bounds or (bounds, old_bounds or bounds)
            motion.gate_contact_bounds = (*context, *contact_bounds)
        gate = self.map.nearby_gate(motion.room, motion.row, state, record, behind_first=True)
        if gate is None:
            return None
        tile, column = gate
        left, right = column * TILE_WIDTH + 40, column * TILE_WIDTH + 72
        # CheckGateForKid 4:613c-616e requires both CheckBarr masks to be
        # 0xff: overlap on the previous frame as well as this one.
        if (not all(body[0] < right and left < body[2] + 1
                    for body in contact_bounds)
                or not stone_gate_blocks(tile.foreground, bounds, state)):
            return None
        if state.action != 109 and tile.foreground and not sword_drawn:
            if state.source_sequence_id == 50:
                return None
            # JumpSeq here does not run AnimChar until the next update.
            distance = self.map.step_boundary(motion.room, motion.row, state, record, bounds).clearance
            state.select(50)
            if distance < 25:
                state.target_x += (distance - 25) * (1 if state.facing else -1)
            state.current_x = state.target_x
            motion.falling = False
            return TerrainEvent("gate")
        if tile.foreground & 255 and not sword_drawn and not invulnerable:
            # CrushedByGate 6:2ac8 chooses SEQS:118 and removes 100 life.
            state.select(118)
            motion.dead, motion.falling = True, False
            return TerrainEvent("death", death_method=0)
        # A fully closed gate (or a drawn sword) ejects the actor to the
        # nearer side, rather than using the cavern crushing animation.
        front = left - (bounds[2] + 1) if state.facing else bounds[0] - right
        back = bounds[0] - right if state.facing else left - (bounds[2] + 1)
        offset = -(abs(front) + 3) if abs(front) < abs(back) else abs(back)
        state.target_x += offset * (1 if state.facing else -1)
        state.current_x = state.target_x
        return TerrainEvent("gate")

    def advance(self, motion, runtime, old_x, bounds, sword_drawn=False, protected=False,
                frame_flags=0x40, frame_record=None, bounds_for_state=None, cut_enabled=True,
                alive=True, old_bounds=None, catch_ledge=None, collision_bounds_for_state=None,
                invulnerable=False):
        state = runtime.state
        if motion.dead:
            return ()
        if protected:
            # Hanging poses have no floor flag. Late climb poses do, and a
            # disappearing slab must interrupt them before their idle link.
            if frame_record is not None:
                frame_flags = frame_record.aux
            if self.check_floor(motion, runtime, frame_flags, frame_record):
                return (TerrainEvent("fall"),)
            gate = self.check_gate(motion, runtime, bounds, old_bounds, frame_record, alive, sword_drawn,
                                   invulnerable=invulnerable)
            if gate is not None:
                return (gate,)
            # A held/climbing ledge bypasses free-fall physics, not CutChar.
            if (cut_enabled and state.actor_type in (0, None)
                    and (self.cut_up(motion, state) or self.cut_down(motion, state))):
                return (TerrainEvent("room"),)
            return ()
        if motion.sinking:
            # SEQS:27 owns every displacement; ordinary gravity must not run.
            if state.action == 185:
                motion.sinking = False
                motion.dead = True
                return (TerrainEvent("death", death_method=8),)
            return ()
        if not motion.falling:
            motion.scream_played = False
        landing_recovery = state.sequence_id in (17, 20, 117, 212, 49)
        if not motion.falling and not landing_recovery:
            motion.smooth_landing = False
        events = []
        if state.actor_type == 2 and state.level_kind == 5 and state.animation_state == 9:
            # FrameAdv 2:65da-6664 bypasses barriers/floors/room cuts for
            # rooftop tumbles. Move only adds gravity; row follows absolute Y.
            absolute_y = floor_y(motion.row) + state.current_y
            state.vertical_velocity = min(MAX_FALL_SPEED, state.vertical_velocity + GRAVITY)
            absolute_y += state.vertical_velocity
            motion.row = character_row(min(absolute_y, VOID_DEATH_Y))
            state.current_y = min(absolute_y, VOID_DEATH_Y) - floor_y(motion.row)
            state.current_x = state.target_x
            motion.falling = True
            if absolute_y > VOID_DEATH_Y:
                if motion.room in WATER_ROOMS:
                    # Move 4:36ae-36ec leaves the harbor death to RoofWatchOpps.
                    state.vertical_velocity = 0
                    state.animation_state = 1
                    return ()
                # Move 4:36a2-36ec freezes at 730 with pose 185. Do not
                # apply SEQS:22's +6 X offset to this direct native assignment.
                state.vertical_velocity = state.horizontal_velocity = 0
                state.animation_state, state.action = 1, 185
                state.selected_sequence_id = 22
                state.sequence_id, state.cursor = 22, len(runtime.sequences[22]) - 1
                motion.dead = True
                state.sound_events.append(7)
                return (TerrainEvent("death"),)
            return ()
        if motion.falling:
            # Falling 6:00ae-00f2 / AddKidScream 5:4b5a: one long-fall cue;
            # the Prince is silent over water, ordinary guards use cue 30.
            if state.vertical_velocity >= 59 and not motion.scream_played:
                motion.scream_played = True
                if state.actor_type == 0 and (state.level_kind != 5 or motion.room not in (14, 15, 18)):
                    state.sound_events.append(8)
                elif state.actor_type == 2 and state.vertical_velocity <= 63:
                    state.sound_events.append(30)
            before_x, before_y = state.target_x, state.current_y
            # Move, CODE:4 0x341a/0x3464: add gravity once per simulation frame.
            floating = self.floating()
            if state.animation_state in (4, 9):
                if floating:
                    # 4:342c-3444: the global float timer slows every faller.
                    state.vertical_velocity = min(8, state.vertical_velocity + 2)
                else:
                    state.vertical_velocity = min(MAX_FALL_SPEED, state.vertical_velocity + GRAVITY)
                if state.animation_state == 4:
                    # 4:34b2-34ca halves the floating Prince's horizontal step.
                    step = (state.horizontal_velocity >> 1 if floating and state.actor_type in (0, None)
                            else state.horizontal_velocity)
                    state.target_x += step * (1 if state.facing else -1)
            state.current_y += state.vertical_velocity
            if bounds_for_state is not None:
                bounds = bounds_for_state()
            else:
                dx, dy = state.target_x - before_x, state.current_y - before_y
                bounds = (bounds[0] + dx, bounds[1] + dy, bounds[2] + dx, bounds[3] + dy)
        # CheckBarr (4:4e46-4e60) bypasses selected SEQS:70/78, not
        # previous poses. JumpSeq writes this ID to A5-0x502e (6:0032).
        # CheckCollide1 (4:551a/5586) checks a rear barrier only with the sword drawn.
        collision_facing = None if sword_drawn else state.facing
        collision_bounds = (collision_bounds_for_state() if collision_bounds_for_state is not None
                            else bounds)
        # CheckBarr samples before Collide displaces/reloads the actor.
        # Its previous bank is the previous sample, not the corrected pose.
        cached = motion.gate_contact_bounds
        gate_contact = (collision_bounds,
                        cached[2] if cached is not None and cached[:2] == (motion.room, motion.row)
                        else old_bounds or collision_bounds)
        # Collide 4:5740-5746 returns before displacement or bump selection
        # for a dead actor. A death pose must never become a live wall bump.
        corrected = (state.target_x if not alive or state.animation_state == 7
                     or state.source_sequence_id in (70, 78) else
                     self.map.wall_correction(motion.room, old_x, state.target_x,
                                              collision_bounds, old_bounds, collision_facing,
                                              physical_row=motion.row, state=state))
        if corrected != state.target_x:
            delta = corrected - state.target_x
            state.current_x = state.target_x = corrected
            bounds = (bounds[0] + delta, bounds[1], bounds[2] + delta, bounds[3])
            collision_bounds = (collision_bounds[0] + delta, collision_bounds[1],
                                collision_bounds[2] + delta, collision_bounds[3])
            state.horizontal_velocity = 0
            # DOS-style recovery for the screen 7 -> 8 drop: retain barrier
            # correction, but do not replace the crouch/rise with GroundBump.
            if not motion.falling and not (motion.smooth_landing and landing_recovery):
                record = self.frames[state.action] if self.frames is not None else frame_record
                contact = (floor_contact_x(corrected, state.facing, record)
                           if record is not None else corrected)
                supported = self.map.supports(motion.room, character_column(contact), motion.row)
                # Collide 4:5826-584c / 589e: a low bump over solid floor
                # stays on that floor. GroundBump (45) is the empty/high case.
                if supported and (sword_drawn or state.current_y > -30):
                    action = state.action
                    state.current_y = state.vertical_velocity = 0
                    direction = 1 if state.facing else -1
                    sequence = ((64 if delta * direction < 0 else 65) if sword_drawn else
                                46 if action in (24, 25) or 40 <= action < 43
                                or 102 <= action <= 106 else 47)
                    self.select(runtime, sequence)
                    # Collide 4:5a3c-5a54 requests metal contact only for SEQS:64.
                    if sequence == 64:
                        state.sound_events.append(10)
                else:
                    self.select(runtime, 45)
                    motion.falling = True
                if bounds_for_state is not None:
                    previous_bounds = collision_bounds
                    bounds = bounds_for_state()
                    if not motion.falling:
                        # Collide reloads the response pose. Its wider body
                        # must not undo the barrier correction just applied.
                        response_x = state.target_x
                        corrected = self.map.wall_correction(
                            motion.room, response_x, response_x,
                            collision_bounds_for_state() if collision_bounds_for_state is not None else bounds,
                            previous_bounds,
                            collision_facing, physical_row=motion.row, state=state)
                        if corrected != response_x:
                            shift = corrected - response_x
                            state.current_x = state.target_x = corrected
                            bounds = (bounds[0] + shift, bounds[1],
                                      bounds[2] + shift, bounds[3])
            events.append(TerrainEvent("wall"))
        elif (state.animation_state == 4 and state.actor_type in (0, None) and alive
                and self.floating()):
            # CheckBarr 4:50b2-514e: with no barrier, a floating body whose top
            # is more than 8 pixels into the row above, under a non-space
            # cell, steps back 6 pixels, stops drifting and restarts SEQS:229.
            top = floor_y(motion.row) + state.current_y - (collision_bounds[3] - collision_bounds[1])
            above = self.map.tile(motion.room, character_column(state.target_x), motion.row - 1)
            if motion.row * TILE_HEIGHT - 8 > top and above.kind not in EMPTY_TILES:
                state.target_x -= 6 if state.facing else -6
                state.current_x = state.target_x
                state.horizontal_velocity = 0
                self.select(runtime, 229)
        record = self.frames[state.action] if self.frames is not None else frame_record
        gate = self.check_gate(motion, runtime, collision_bounds, old_bounds, record, alive,
                               sword_drawn, contact_bounds=gate_contact, invulnerable=invulnerable)
        if gate is not None:
            events.append(gate)
            return tuple(events)
        if (cut_enabled and state.actor_type in (0, None)
                and self.cut_up(motion, state)):
            events.append(TerrainEvent("room"))
        elif cut_enabled and self.cut_horizontal(motion, state, bounds):
            events.append(TerrainEvent("room"))
        if (cut_enabled and state.actor_type in (0, None)
                and self.cut_down(motion, state)):
            events.append(TerrainEvent("room"))

        if self.frames is not None:
            frame_record = self.frames[state.action]
        if frame_record is not None:
            frame_flags = frame_record.aux
        if not motion.falling:
            if self.check_floor(motion, runtime, frame_flags, frame_record):
                events.append(TerrainEvent("fall"))
            return tuple(events)

        # FrameAdv 2:6372-63a6 runs AnimChar/Move before Falling/Catch.
        # Catch must see this frame's displacement before the floor row advances.
        if catch_ledge is not None and catch_ledge():
            return tuple(events)

        # Falling 6:0156-0174 corrects the foot before comparing its height
        # with the next floor, not only after it has reached that floor.
        if frame_record is not None and state.sequence_id != 15:
            self.map.align_wall(motion.room, motion.row, state, frame_record)

        absolute_y = floor_y(motion.row) + state.current_y
        if absolute_y > VOID_DEATH_Y and (
            self.map.neighbor(motion.room, "down") is None
            or not self.map.allows_down_cut(motion.room, state.actor_type)
        ):
            state.current_y = VOID_DEATH_Y - floor_y(motion.row)
            if state.level_kind == 5 and motion.room in WATER_ROOMS and not invulnerable:
                state.vertical_velocity = 0
                state.animation_state = 1
                return tuple(events)
            state.vertical_velocity = state.horizontal_velocity = 0
            motion.dead = True
            self.select(runtime, 22)
            state.sound_events.append(7)
            events.append(TerrainEvent("death"))
            return tuple(events)

        if state.animation_state not in (4, 9):
            return tuple(events)
        while absolute_y > floor_y(motion.row):
            contact_x = (floor_contact_x(state.target_x, state.facing, frame_record)
                         if frame_record is not None else state.target_x)
            column = character_column(contact_x)
            tile = self.map.tile(motion.room, column, motion.row)
            if frame_record is not None and tile.kind in WALL_TILES:
                tile = self.map.align_wall(motion.room, motion.row, state, frame_record)
            if tile.room is not None and tile.kind not in EMPTY_TILES | WALL_TILES:
                velocity = state.vertical_velocity
                if (tile.kind in (23, 24) and self.map.caverns is not None
                        and state.actor_type in (0, 4, None) and not invulnerable):
                    # HitFloor 6:02aa-02b8/0326-0344 dispatches lava before
                    # impact damage, preserving the airborne death variant.
                    state.current_y = 0
                    motion.lava_landing = True
                    events.append(TerrainEvent('lava'))
                    break
                if tile.kind == 11 and self.map.caverns is not None and velocity:
                    # Falling 6:01ee-0260: strike the slab, halve velocity and
                    # remain airborne just above the current floor.
                    state.sound_events.extend(self.map.caverns.loose.trigger(tile, force=velocity))
                    state.vertical_velocity //= 2
                    state.current_y = -13
                    if not invulnerable and (velocity >= 63 or state.actor_type == 2):
                        events.append(TerrainEvent('damage', 100))
                    break
                # HitFloor 6:0348-0444 makes an ordinary NPC's >=50 fall
                # fatal; the Prince can survive 50..62 with one life lost.
                fatal = not alive or not invulnerable and velocity >= (50 if state.actor_type == 2 else 63)
                sequence = (22 if fatal else 20 if velocity >= 50
                            else 187 if state.actor_type == 2 and state.sequence_id == 186
                            else 63 if sword_drawn or state.actor_type == 2 else 17)
                if frame_record is not None:
                    state.target_x += self.map.landing_offset(
                        motion.room, motion.row, state, frame_record)
                state.current_y = 0
                state.horizontal_velocity = state.vertical_velocity = 0
                motion.falling = False
                motion.dead = fatal
                self.select(runtime, sequence)
                # HitFloor 6:039c/03fe/0436 distinguishes safe, hurt and fatal impacts.
                state.sound_events.append(7 if fatal else 13 if velocity >= 50 else 296)
                events.append(TerrainEvent("death" if motion.dead else "land",
                                           int(not invulnerable and not fatal and 50 <= velocity < 63)))
                break
            motion.row += 1
            state.current_y -= TILE_HEIGHT
            if motion.row >= 3:
                if state.actor_type in (0, None):
                    # The player's camera cut has its own Y threshold.
                    # Advancing a physical floor row must not change it.
                    break
                room = (self.map.neighbor(motion.room, "down")
                        if self.map.allows_down_cut(motion.room, state.actor_type) else None)
                if room is not None:
                    # Cut coordinates use the 365-pixel clip, not 360 tile pixels.
                    motion.smooth_landing = (motion.room == 11 and room == 14
                                             and state.actor_type == 0 and state.level_kind == 5)
                    motion.room = room
                    motion.row -= 3
                    state.current_y -= ROOM_HEIGHT - 3 * TILE_HEIGHT
                    absolute_y -= ROOM_HEIGHT
                    events.append(TerrainEvent("room"))
                else:
                    break
        state.current_x = state.target_x
        return tuple(events)
