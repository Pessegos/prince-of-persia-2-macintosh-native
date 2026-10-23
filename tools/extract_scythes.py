"""Bind the ruins' scythe drawing (tiles 12/13) to the original room drawing."""

from difflib import SequenceMatcher
import json
import struct

from pop2.scythes import SCYTHE_STATES
from pop2.terrain import LevelMap


def scythe_pairs(terrain):
    """Each scythe as ((room, cell) of its tile 13, (room, cell) of its tile 12).

    TriggerScythe 5:5fde keeps the state on tile 13; AnimScythe 5:4584 copies
    its low byte to tile 12, the cell to its left.
    """
    pairs = []
    for room in range(32):
        for cell in range(30):
            tile = terrain.tile(room, cell % 10, cell // 10)
            if tile.kind != 13:
                continue
            left = terrain.tile(room, tile.column - 1, tile.row)
            if left.room is None or left.kind != 12:
                raise ValueError('Unsupported scythe without its left half')
            pairs.append(((room, cell), (left.room, left.row * 10 + left.column)))
    return pairs


def command_patch(base, commands):
    """Removed commands and insertions anchored after a base command."""
    keys = [json.dumps(command) for command in base]
    matcher = SequenceMatcher(None, keys, [json.dumps(command) for command in commands],
                              autojunk=False)
    remove, insert = [], []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ('replace', 'delete'):
            remove.extend(base[i1:i2])
        if tag in ('replace', 'insert'):
            insert.append([base[i1 - 1] if i1 else None, commands[j1:j2]])
    return {'remove': remove, 'insert': insert}


def scythe_scenery(program, caverns, prince, level, base, progress=lambda _text: None, *, recover=None):
    from tools.extract_caverns import recover_room
    recover = recover or recover_room

    terrain = LevelMap(level)
    pairs = scythe_pairs(terrain)
    result = {'schema': 1, 'scythes': [[*key, *partner] for key, partner in pairs], 'rooms': {}}
    for room in range(32):
        visible = {(tile.room, tile.row * 10 + tile.column)
                   for row in range(-1, 4) for column in range(-1, 11)
                   if (tile := terrain.tile(room, column, row)).room is not None}
        shown = [index for index, (key, partner) in enumerate(pairs) if {key, partner} & visible]
        if not shown:
            continue
        if len(shown) > 1:
            raise ValueError('Unsupported room with several scythes')
        key, partner = pairs[shown[0]]
        patches, states = [], {}
        for value in SCYTHE_STATES[1:]:
            progress(f'Ruins scythes: room {room + 1}/32, state {value:#x}')
            mutable = bytearray(level)
            for source_room, cell in (key, partner):
                offset = 0x780 + source_room * 120 + cell * 4
                foreground = struct.unpack_from('>H', mutable, offset)[0]
                struct.pack_into('>H', mutable, offset, (foreground & 0xff00) | value)
            patch = {
                'commands': command_patch(base['rooms'][str(room)],
                                          recover(program, caverns, bytes(mutable), room, prince)['commands']),
                'floor_redraw': command_patch(base['floor_redraw'][str(room)],
                                              recover(program, caverns, bytes(mutable), room, prince,
                                                      floor_redraw=True)['commands'])}
            if patch not in patches:
                patches.append(patch)
            states[str(value)] = patches.index(patch)
        if any(any(part.values()) for patch in patches for part in patch.values()):
            # A neighbour's scythe only counts when its drawing reaches this room.
            result['rooms'][str(room)] = {'scythe': shown[0], 'states': states, 'patches': patches}
    return result
