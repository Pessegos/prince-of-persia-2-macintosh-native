"""Bind portable pressure/gate drawing to the original per-room drawing commands."""

import struct

from pop2.terrain import LevelMap


# Drawing slots each mechanism may change, per LEVL environment. The ruins
# (levels 6-7) gate is SHAP 3542 and their exit 3547; a plate also lowers
# its 3552/3553 front piece by a pixel.
CHANGED_SHAPES = {
    3: {4: (3562, 3563), 17: (3566,), 27: (4051,), 33: (3591,)},
    4: {4: (3542,), 17: (3547,), 5: (3552, 3554), 6: (3553, 3554), 34: (3552, 3553, 3554)},
}


def command_key(command):
    # Pressed/unpressed plates are the same drawing slot, with a different SHAP.
    shape = 3554 if command[1] == 3555 else command[1]
    if 3591 <= shape <= 3593:
        shape = 3591
    if shape in (4052, 4053, 4064):
        shape = 4051  # Level five's ceiling bars (room 3 CUST records 1-4).
    return command[0], shape, *command[7:10]


def pressure_scenery(program, caverns, prince, level, base, progress=lambda _text: None, *, recover=None):
    from tools.extract_caverns import recover_room
    recover = recover or recover_room

    from pop2.caverns import entry_room

    terrain = LevelMap(level)
    entry = entry_room(struct.unpack_from('>H', level, 0x218a)[0], terrain.start_room)
    environment = struct.unpack_from('>H', level, 0x2186)[0]
    result = {'schema': 1, 'rooms': {}}
    for room in range(32):
        progress(f'Cavern buttons and doors: room {room + 1}/32')
        # A gate below the room can protrude through its lower drawing edge.
        visible = {(tile.room, tile.row * 10 + tile.column)
                   for row in range(-1, 4) for column in range(-1, 11)
                   if (tile := terrain.tile(room, column, row)).room is not None
                   and (tile.kind in (4, 5, 6, 27, 33, 34)
                        or tile.kind == 17 and tile.room != entry)}
        before = base['rooms'][str(room)]
        records = []
        for source_room, cell in sorted(visible):
            tile = terrain.tile(source_room, cell % 10, cell // 10)
            mutable = bytearray(level)
            if tile.kind in (4, 17):
                # DrawCaveGateMovable 8:1f92-1fb6 clamps phases >=184 to
                # the same height. Comparing an initially open gate with
                # 184 silently drops its binding. Probe the other endpoint;
                # an exit's corresponding fully open endpoint is 79.
                opened = 79 if tile.kind == 17 else 184
                value = (tile.foreground & 0xff00) | (
                    0 if (tile.foreground & 255) >= opened else opened)
            else:
                value = ((tile.foreground & 0xfff8) | 1 if tile.kind in (27, 33) else
                         tile.foreground ^ 0x2000)
            struct.pack_into('>H', mutable, 0x780 + source_room * 120 + cell * 4, value)
            after = recover(program, caverns, bytes(mutable), room, prince)['commands']
            old, new = {command_key(c): c for c in before}, {command_key(c): c for c in after}
            if new.keys() - old.keys():
                raise ValueError('Unexpected new pressure/gate drawing slot')
            keys = [key for key in old if old[key] != new.get(key)]
            expected = CHANGED_SHAPES[environment].get(tile.kind, (3554,))
            if any(key[1] not in expected for key in keys):
                raise ValueError('Unsupported pressure/gate drawing dependency')
            if keys:
                record = {'room': source_room, 'cell': cell, 'kind': tile.kind,
                          'foreground': tile.foreground, 'commands': keys}
                if environment != 3 and tile.kind in (5, 6, 34):
                    # Ruins plates move several pieces: keep the toggled
                    # state's exported commands rather than a SHAP rule.
                    record['toggled'] = [new[key] for key in keys]
                records.append(record)
        result['rooms'][str(room)] = records
    return result
