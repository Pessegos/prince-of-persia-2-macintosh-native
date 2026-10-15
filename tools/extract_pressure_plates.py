"""Bind portable pressure/gate drawing to the original per-room drawing commands."""

import struct

from pop2.terrain import LevelMap


def command_key(command):
    # Pressed/unpressed plates are the same drawing slot, with a different SHAP.
    shape = 3554 if command[1] == 3555 else command[1]
    return command[0], shape, *command[7:10]


def pressure_scenery(program, caverns, prince, level, base):
    from tools.extract_caverns import recover_room

    terrain = LevelMap(level)
    result = {'schema': 1, 'rooms': {}}
    for room in range(32):
        # A gate below the room can protrude through its lower drawing edge.
        visible = {(tile.room, tile.row * 10 + tile.column)
                   for row in range(-1, 4) for column in range(-1, 11)
                   if (tile := terrain.tile(room, column, row)).room is not None
                   and (tile.kind in (4, 5, 6, 34)
                        or tile.kind == 17 and tile.room != terrain.start_room)}
        before = base['rooms'][str(room)]
        records = []
        for source_room, cell in sorted(visible):
            tile = terrain.tile(source_room, cell % 10, cell // 10)
            mutable = bytearray(level)
            value = ((tile.foreground & 0xff00) | (79 if tile.kind == 17 else 184)
                     if tile.kind in (4, 17) else tile.foreground ^ 0x2000)
            struct.pack_into('>H', mutable, 0x780 + source_room * 120 + cell * 4, value)
            after = recover_room(program, caverns, bytes(mutable), room, prince)['commands']
            old, new = {command_key(c): c for c in before}, {command_key(c): c for c in after}
            if new.keys() - old.keys():
                raise ValueError('Unexpected new pressure/gate drawing slot')
            keys = [key for key in old if old[key] != new.get(key)]
            expected = {4: (3562, 3563), 17: (3566,)}.get(tile.kind, (3554,))
            if any(key[1] not in expected for key in keys):
                raise ValueError('Unsupported pressure/gate drawing dependency')
            if keys:
                records.append({'room': source_room, 'cell': cell, 'kind': tile.kind,
                                'foreground': tile.foreground, 'commands': keys})
        result['rooms'][str(room)] = records
    return result
