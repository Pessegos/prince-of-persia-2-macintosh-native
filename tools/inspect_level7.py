"""Inventory later-level dependencies without enabling them in the game.

Reads a local, unmodified recovery directory. Reports are research artifacts,
not imported scenery programs or claims of native gameplay equivalence.
"""

import argparse
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import struct

from pop2.level_data import LevelDefinition
from pop2.mac_resources import parse_resource_fork
from pop2.terrain import LevelMap
from tools.extract_enemy_profiles import expand_a5_data


DIRECTIONS = ('left', 'right', 'up', 'down')


def resource_filename(a5_data, table_offset, index):
    """Decode a six-byte file-table entry's A5-relative Pascal name pointer."""
    entry = len(a5_data) + table_offset + index * 6
    if index < 0 or entry < 0 or entry + 6 > len(a5_data):
        raise ValueError('File table index is out of bounds')
    pointer = struct.unpack_from('>i', a5_data, entry + 2)[0]
    address = len(a5_data) + pointer
    if pointer >= 0 or address < 0 or address >= len(a5_data):
        raise ValueError('Invalid A5-relative filename pointer')
    end = address + 1 + a5_data[address]
    if end > len(a5_data):
        raise ValueError('Truncated Pascal filename')
    return a5_data[address + 1:end].decode('mac_roman').rsplit(':', 1)[-1]


def inventory_level(data, number=7):
    level = LevelDefinition.decode(number, data)
    terrain = LevelMap(data)
    reachable = {level.start_room}
    pending = deque(reachable)
    while pending:
        room = pending.popleft()
        for direction in DIRECTIONS:
            neighbor = terrain.neighbor(room, direction)
            if neighbor is not None and neighbor not in reachable:
                reachable.add(neighbor)
                pending.append(neighbor)
    tiles = Counter()
    rooms = []
    for room in range(32):
        cells = []
        for cell in range(30):
            tile = terrain.tile(room, cell % 10, cell // 10)
            tiles[tile.kind] += 1
            cells.append(dict(cell=cell, kind=tile.kind, foreground=tile.foreground,
                              background=tile.background))
        offset = 0x20e6 + (room + 1) * 0xc0
        count = struct.unpack_from('>H', data, offset)[0]
        if count > 5:
            raise ValueError('Invalid generator record count')
        records = [list(struct.unpack_from('>19h', data, offset + 2 + index * 38))
                   for index in range(count)]
        custom = any(cell['foreground'] & 0xc000 for cell in cells)
        rooms.append(dict(room=room + 1, reachable=room in reachable,
                          links={direction: neighbor + 1 if neighbor is not None else None
                                 for direction in DIRECTIONS
                                 for neighbor in (terrain.neighbor(room, direction),)},
                          custom_resource=3975 + (room + 1) * 25 if custom else None,
                          generator_records=records, cells=cells))
    return dict(
        level=number, resource_id=level.resource_id, environment=level.kind,
        level_sha256=hashlib.sha256(data).hexdigest(),
        start=dict(room=level.start_room + 1, cell=level.start_tile,
                   port_facing=level.facing, port_x=level.start_x),
        opponent_set=level.opponent_type,
        checkpoints=[dict(slot=point.slot, room=point.room + 1, cell=point.tile)
                     for point in level.checkpoints],
        reachable_rooms=sorted(room + 1 for room in reachable),
        tile_counts={str(kind): count for kind, count in sorted(tiles.items())},
        rooms=rooms,
    )


def inspect(recovery, number=7):
    directory = Path(recovery) / 'resource_forks'
    program = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    report = inventory_level(prince['LEVL'][1999 + number]['data'], number)
    a5_data = expand_a5_data(program)
    # OpenLevelRsrcFile 3:51fa, LoadOppSet 3:5f58.
    scenery = resource_filename(a5_data, -0x4724, report['environment'])
    opponents = resource_filename(a5_data, -0x464a, report['opponent_set'])
    report['dependencies'] = dict(scenery=scenery, opponents=opponents,
                                  prince_palette=25000 + report['environment'])
    for label, filename in (('scenery', scenery), ('opponents', opponents)):
        resources = parse_resource_fork((directory / (filename + '.bin')).read_bytes())
        report[label + '_resources'] = {
            kind: dict(count=len(entries), ids=sorted(entries))
            for kind, entries in resources.items() if kind.strip('\x00')}
    custom_ids = set(report['scenery_resources'].get('CUST', {}).get('ids', ()))
    report['missing_custom_resources'] = sorted(
        {room['custom_resource'] for room in report['rooms']
         if room['custom_resource'] is not None} - custom_ids)
    report['scope'] = ('Resource/header inventory only; generator words are raw records, '
                       'not decoded special-actor semantics. No renderer or simulation runs.')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--level', type=int, choices=(6, 7, 8, 9), default=7)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.source, args.level)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in (
        'level', 'environment', 'start', 'opponent_set', 'checkpoints',
        'dependencies', 'reachable_rooms', 'tile_counts', 'missing_custom_resources')}, indent=2))


if __name__ == '__main__':
    main()
