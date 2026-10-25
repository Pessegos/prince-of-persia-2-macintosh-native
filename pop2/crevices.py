"""Ruins crevices (tile 7): hidden tunnels a crouching Prince reveals."""

import struct

CREVICE_TILE = 7
# Crawling (GenCtrl 6:07ee-0994, 6:0a4e-0b28): lie down, prone idle pose,
# crawl forward/back and stand up.
LIE_DOWN_SEQUENCE = 125
PRONE_IDLE_FRAME = 251
CRAWL_FORWARD_SEQUENCE, CRAWL_BACK_SEQUENCE = 122, 123
STAND_FROM_PRONE_SEQUENCE = 124


def hide_crevices(level):
    # InitState 3:5dce-5e04 clears foreground bit 0x80 of every tile 7, so
    # each crevice starts covered whatever the LEVL says.
    level = bytearray(level)
    for room in range(32):
        for cell in range(30):
            if struct.unpack_from('>H', level, room * 60 + cell * 2)[0] == CREVICE_TILE:
                offset = 0x780 + room * 120 + cell * 4
                struct.pack_into('>H', level, offset, struct.unpack_from('>H', level, offset)[0] & 0xff7f)
    return bytes(level)


def crevice_group(terrain, room, column, row):
    """7:332a's scan: the first tile-7 run of the row, as (room, cell) keys.

    It searches columns min(column - 2, 0) to max(column + 3, 10) - 1 through
    horizontal links, then walks left to the run's start.
    """
    def tile(current):
        found = terrain.tile(room, current, row)
        return found if found.room is not None and found.kind == CREVICE_TILE else None

    found = next((current for current in range(min(column - 2, 0), max(column + 3, 10))
                  if tile(current) is not None), None)
    if found is None:
        return ()
    while found > -640 and tile(found - 1) is not None:
        found -= 1
    cells = []
    while found < 640 and (crevice := tile(found)) is not None:
        key = crevice.room, crevice.row * 10 + crevice.column
        if key in cells:
            break
        cells.append(key)
        found += 1
    return tuple(cells)


def front_crevice_group(terrain, room, column, row, facing, selected):
    """RuinSetCreviceRevealed 7:3404: a crouching Prince facing a crevice."""
    front = terrain.tile(room, column + (1 if facing else -1), row)
    if selected == 17 or front.room is None or front.kind != CREVICE_TILE or front.foreground & 3 == 3:
        return ()
    return crevice_group(terrain, room, column, row)
