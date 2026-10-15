"""Cavern projectile traps recovered from Macintosh CODE:5/8."""

from dataclasses import dataclass, field

from pop2.opponent_generation import EMPTY_TILES, WALL_TILES
from pop2.terrain import floor_contact_x, floor_edge_distance, stone_gate_blocks


@dataclass
class Dart:
    room: int
    x: int
    y: int
    row: int
    dx: int = 27
    dy: int = -19

    def hits(self, bounds):
        # CheckDartHit 8:2ecc-2f6e uses a 9x7 rectangle and a separate
        # swept test. Actor bounds use exclusive QuickDraw bottom/right.
        left, top, right, bottom = bounds
        x, y = self.x + 13, self.y
        overlap = x < right and x + 9 > left and y - 7 < bottom and y > top
        swept = (x >= left and top - 3 <= y and bottom - 3 >= y - 7
                 and x - self.dx < right and y - self.dy < bottom)
        return overlap or swept


@dataclass
class Darts:
    projectiles: list = field(default_factory=list)

    def spawn(self, room, cell):
        # TriggerDart 5:4a54-4ad6; DATA column/row tables are 51*n/125+120*n.
        row, column = divmod(cell, 10)
        self.projectiles.append(Dart(room, column * 51 + 40, row * 120 + 95, row))

    def advance(self, terrain, view_room, bounds, state):
        cues = []
        for dart in self.projectiles:
            if dart.dy in (-3, -1):
                dart.dy = -1
                continue
            x, y = dart.x + dart.dx, dart.y + dart.dy
            # MobDart rebases a projectile from the visible left/lower
            # neighbor only. Leaving the viewport does not follow every link.
            for crossed, direction, incoming, amount in (
                    (x > 510, 'right', 'left', -510),
                    (y < 5, 'up', 'down', 365)):
                if not crossed:
                    continue
                if dart.room == terrain.neighbor(view_room, incoming):
                    dart.room = view_room
                    if direction == 'right':
                        x += amount
                    else:
                        y += amount
                else:
                    if terrain.neighbor(dart.room, direction) is None:
                        cues.append(67)
                    dart.dy = -3
            if dart.dy == -3:
                continue
            column = x // 51
            if y <= dart.row * 120 + 5:
                dart.row -= 1
                blocked = terrain.tile(dart.room, column, dart.row).kind not in EMPTY_TILES
            elif column != dart.x // 51:
                tile = terrain.tile(dart.room, column, dart.row)
                blocked = (tile.kind in WALL_TILES or tile.kind == 4
                           and stone_gate_blocks(tile.foreground, bounds, state))
            else:
                blocked = False
            if blocked:
                dart.dy = -3
                cues.append(67)
            dart.x, dart.y = x, y
        self.projectiles[:] = [dart for dart in self.projectiles if dart.dy != -1]
        return tuple(cues)

    def contacts(self, room, state, bounds):
        # SEQS:79's crouch poses are immune; an ordinary crouch is not.
        if 108 <= state.action <= 112 and state.source_sequence_id == 79:
            return ()
        left, top, right, bottom = bounds
        rectangle = max(0, left), max(0, top), min(510, right + 1), min(365, bottom + 1)
        hits = []
        index = 0
        while True:
            # GetMobTypeItem numbers only active entries. Consuming one
            # renumbers the bank before CheckDartHit asks for the next index.
            active = [dart for dart in self.projectiles if dart.dy != -1]
            if index >= len(active):
                break
            dart = active[index]
            index += 1
            if dart.room == room and dart.dy != -1 and dart.hits(rectangle):
                dart.dy = -1
                hits.append(dart)
        return tuple(hits)


def dart_death(terrain, motion, state, record):
    """8:3178-31c8: supported death or a forward fall at the ledge."""
    from pop2.opponent_generation import character_column

    contact = floor_contact_x(state.target_x, state.facing, record)
    direction = 1 if state.facing else -1
    behind = terrain.tile(motion.room, character_column(contact) - direction, motion.row)
    distance = floor_edge_distance(contact, state.facing)
    if behind.kind not in EMPTY_TILES and distance >= 6:
        return (98 if state.actor_type == 0 and 246 <= state.action <= 261 else 85), 0
    return 18, (distance - 63) * direction
