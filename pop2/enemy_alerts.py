"""Ordinary alert path scan from Macintosh CODE:2 6f76-70ce."""

from pop2.opponent_generation import EMPTY_TILES, OBSTACLE_TILES, WALL_TILES


def alert_path_mode(tile_at, guard_column, player_column, level_kind, floating=False):
    low, high = sorted((guard_column, player_column))
    # 2:6fc2-6fce excludes a gate at the right endpoint, then skips
    # the scan entirely if its endpoints meet.
    if low < high and tile_at(high).kind == 4:
        high -= 1
    if low >= high:
        return 3
    for column in range(low, high + 1):
        tile = tile_at(column)
        if tile.kind in WALL_TILES:
            return 0
        if floating:
            # CheckAlert 2:704c-7068: for the flaming sword (type 10) gaps,
            # obstacles and closed gates neither limit nor block it.
            continue
        if (tile.kind in EMPTY_TILES | OBSTACLE_TILES
                or tile.kind == 4 and tile.foreground & 255 < 104):
            # 2:7084-709c uses GetBlock's room-normalized column.
            if (level_kind == 3 and tile.kind == 24
                    and player_column >= tile.column and guard_column >= tile.column):
                continue
            return 1
    return 3
