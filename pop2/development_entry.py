"""Safe cavern F3 entries, independent of the ordinary movement rules."""

from pop2.opponent_generation import EMPTY_TILES, WALL_TILES


STANDING_TILES = frozenset((1, 3, 8, 10, 14, 19, 32))


def cavern_entry(terrain, room, preferred_row=None):
    def open_tile(tile):
        return (tile.room is not None and tile.kind not in WALL_TILES | {12, 13, 23, 24}
                and not (tile.kind == 4 and tile.foreground & 255 < 184))

    # A floor marker can belong to a sealed decorative pocket. Follow local
    # air/floor space to a genuine room link; vertical travel needs an opening
    # in the upper cell, not a connection straight through solid floor.
    remaining = {(row, column) for row in range(3) for column in range(10)
                 if open_tile(terrain.tile(room, column, row))}
    accessible = set()
    while remaining:
        pending = [min(remaining)]
        component = set()
        exit_found = False
        while pending:
            cell = pending.pop()
            if cell not in remaining:
                continue
            remaining.remove(cell)
            component.add(cell)
            row, column = cell
            current = terrain.tile(room, column, row)
            for dy, dx in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                neighbor = terrain.tile(room, column + dx, row + dy)
                if not open_tile(neighbor):
                    continue
                upper = neighbor if dy < 0 else current
                if dy and upper.kind not in EMPTY_TILES | {11}:
                    continue
                if neighbor.room != room:
                    exit_found = True
                elif (row + dy, column + dx) in remaining:
                    pending.append((row + dy, column + dx))
        if exit_found:
            accessible.update(component)

    candidates = [(row, column) for row, column in accessible
                  if terrain.tile(room, column, row).kind in STANDING_TILES]
    if not candidates:
        raise ValueError("This room has no accessible standing floor for a dev warp")
    return min(candidates, key=lambda cell: (
        preferred_row is not None and cell[0] != preferred_row,
        terrain.tile(room, cell[1], cell[0]).kind != 1,
        abs(cell[1] - 5), cell[0], cell[1]))
