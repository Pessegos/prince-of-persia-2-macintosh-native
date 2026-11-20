"""Run the original CheckGateInFore against the port's gate peel.

DrawForeImg 3:2598 calls CheckGateInFore 3:26e4 (3:25aa) for each marked
cell before that cell's front pieces. When the cell's left tile is a gate
(a5-0x49d6 kind 4, 3:2706-270e) and the Kid stands on the same row in the
gate's column or the one before it (3:2722-274a), not hanging (modes 2/6,
3:274c-275a), it draws the environment's movable gate (a5-0x4ab2, set from
a5-0x4ace by SetPrinceLevelSpecPtrs 3:5da8: 8:1f40 caves, 7:2ac2 ruins,
10:0976 temple) once more in the front pass (mode 2, 3:28ec-2910), clipped
to the cell and the character's object rectangle (GetObjTableType 3:3e7c,
3:28be-28d8). So the moving stone covers a character standing at it.
The Kid is tested first; the room's opponents (a5-0x5208, type 11 skipped)
only when he does not match, and only the first match counts.

The port keeps each gate's positioned stone (`CavernRoom.gate_occlusion`,
keyed by the gate's tile) and adds the stones of the character's column and
the next one to his mask (`CavernRoom.gate_peel`). Here the original runs
for every gate room of the imported levels 3-13, every gate at rest and at
a sample of its heights (one gate at a time), with the Kid in each column
from three before to two after each gate of that row, the object rectangle
the whole screen, and every cell of the row redrawn; the port's covers for
the same column and row are compared with the stones the original draws:

- `missing`: stone pixels the original draws over the Kid that the port's
  covers lack.
- `extra`: port cover pixels the original does not draw.

`--modes` also runs modes 0-7 at the gate's own column, and the crushed
actions 264-266. Those take 3:2922 instead: only in the caves, and it only
draws the gate's front pieces (S08_2112 in mode 1) that the cell's own front
pass draws anyway, so the original peels no stone over a crushed Kid. The
port keeps the stones of his row in front during its DOS-inspired crush
presentation (`pop2.gate_crush`, sequence 118): a deliberate exception,
counted apart (`crushed_*`), not a failure.

`--drawing` compares the gates' own back pieces instead: for every gate
state above, the port's `pressure_drawing_commands` against the original
room drawn with those level words (stones on screen: shape, X, bottom and
visible clip). One slot can draw a stone twice: level 12 room 4's cell 0
draws its gate's stone and the left room's (1:9), level 11 rooms 8 and 9 a
row-2 gate's and the room below's (3:9). Earlier imports keyed both by
(layer, shape, library, slot), so the second stone moved with the first
and had no record of its own; the export now adds X and tile row to such a
key. With an earlier import those gates' states are counted apart
(`old_export_states`), not compared.

Both sides use the port's SHAP alpha. Not covered: the opponents' branch
(3:2768-283c, which looks up the next slot's type word in the object
table), several characters at once and the full-repaint clip (a5-0x4832
set, 3:28a4-28bc).
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

import numpy as np

from pop2.caverns import (SCENERY_LEVELS, cavern_command_sprite, cavern_room, clipped_sprite, room_assets,
                          scenery_available, scenery_resource)
from pop2.terrain import LevelMap
from tools.extract_caverns import CavernRecovery, recover_room
from tools.probe_foreground_cells import SIZE, pressure_phase, pressure_states, probe_level, probed_rooms

LEVELS = tuple(number for number in sorted(n for numbers in SCENERY_LEVELS.values() for n in numbers)
               if number <= 13)
SCREEN = (0, 0, 365, 510)
# (level, room, gate room, gate cell): a gate whose stone shares its slot's
# key with another's in imports before the X/row key, and the other gate.
SHARED_SLOT = {(12, 4, 4, 0): (1, 9), (11, 8, 9, 29): (3, 9), (11, 9, 9, 29): (3, 9)}


def old_export(number, room, record, records):
    """An import from before shared slot keys carried X and tile row."""
    other = SHARED_SLOT.get((number, room, record['room'], record['cell']))
    return other is not None and not any((r['room'], r['cell']) == other for r in records)


def paint(commands, art):
    covered = np.zeros(SIZE, bool)
    for command in commands:
        decoded = clipped_sprite(cavern_command_sprite(command, *art), command)
        if decoded is None:
            continue
        sprite, (x, y) = decoded
        alpha = np.asarray(sprite.getchannel('A')) > 0
        top, left = max(0, y), max(0, x)
        bottom, right = min(SIZE[0], y + sprite.height), min(SIZE[1], x + sprite.width)
        if top < bottom and left < right:
            covered[top:bottom, left:right] |= alpha[top - y:bottom - y, left - x:right - x]
    return covered


def port_peel(room_art, column, row, crushed=False):
    covered = np.zeros(SIZE, bool)
    for cover, (x, y) in room_art.gate_peel(column, row, crushed):
        alpha = np.asarray(cover) > 0
        top, left = max(0, y), max(0, x)
        bottom, right = min(SIZE[0], y + alpha.shape[0]), min(SIZE[1], x + alpha.shape[1])
        if top < bottom and left < right:
            covered[top:bottom, left:right] |= alpha[top - y:bottom - y, left - x:right - x]
    return covered


def gate_tiles(terrain, room, records):
    """(column, row) of the room's gate records in this room's terms."""
    tiles = []
    for record in records:
        if record['kind'] != 4:
            continue
        column, row = record['cell'] % 10, record['cell'] // 10
        if record['room'] == room:
            tiles.append((column, row))
        elif record['room'] == terrain.neighbor(room, 'left'):
            tiles.append((column - 10, row))
        elif record['room'] == terrain.neighbor(room, 'right'):
            tiles.append((column + 10, row))
    return tiles


def native_peel(machine, sources, level, room, kid, art):
    executable, scenery, prince = sources
    result = recover_room(executable, scenery, level, room, prince, _machine=machine, cell_redraw=True,
                          only={(kid[1], column, 1) for column in range(10)},
                          gate_peel={'kid': kid, 'objects': [(2, 0, SCREEN)]})
    return paint(result['peel'], art)


def run_probe(source, levels=LEVELS, rooms=None, modes=False):
    directory = Path(source) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = (directory / 'Prince.rsrc.bin').read_bytes()
    digest, totals = hashlib.sha256(), Counter()
    results = {}
    for number in levels:
        if not scenery_available(number):
            continue
        level = probe_level(number, prince)
        terrain = LevelMap(level)
        scenery = (directory / f'{scenery_resource(number)}.bin').read_bytes()
        program = room_assets(number, 0)[0]
        sources = executable, scenery, prince
        with CavernRecovery(executable, scenery, prince) as machine:
            for room in probed_rooms(number, program, rooms):
                records = program.get('pressure_plates', {}).get('rooms', {}).get(str(room), ())
                tiles = gate_tiles(terrain, room, records)
                if not tiles:
                    continue
                _program, resources, palette, shapes = room_assets(number, room)
                art = resources, palette, shapes
                rest = [pressure_phase(record['kind'], record['foreground']) for record in records]
                states = [(None, None, tuple(rest))]
                for index, record in enumerate(records):
                    if record['kind'] != 4:
                        continue
                    for word in pressure_states(record):
                        phases = tuple(pressure_phase(4, word) if other == index else value
                                       for other, value in enumerate(rest))
                        states.append((record, word, phases))
                for record, word, phases in states:
                    if record is not None and old_export(number, room, record, records):
                        totals['old_export_states'] += 1
                        continue
                    mutable = bytearray(level)
                    if record is not None:
                        struct.pack_into('>H', mutable, 0x780 + record['room'] * 120 + record['cell'] * 4, word)
                    room_art = cavern_room(room, animated=True, level_number=number, pressure_key=phases)
                    cases = []
                    kids = sorted({(0, row, column, 0) for gate_column, row in tiles
                                   for column in range(gate_column - 3, gate_column + 3)})
                    if modes:
                        kids += sorted({(action, row, gate_column, mode) for gate_column, row in tiles
                                        for mode in range(8) for action in (0, 264, 265, 266)
                                        if mode == 0 or action == 0} - set(kids))
                    for kid in kids:
                        action, row, column, mode = kid
                        native = native_peel(machine, sources, bytes(mutable), room, kid, art)
                        port = (port_peel(room_art, column, row, 264 <= action <= 266)
                                if mode not in (2, 6) else np.zeros(SIZE, bool))
                        missing, extra = int((native & ~port).sum()), int((port & ~native).sum())
                        if 264 <= action <= 266:
                            totals['crushed_kids'] += 1
                            totals['crushed_native_pixels'] += int(native.sum())
                            totals['crushed_port_pixels'] += int(port.sum())
                            continue
                        totals['kids'] += 1
                        totals['peeled'] += int(native.any())
                        totals['native_pixels'] += int(native.sum())
                        totals['missing_pixels'] += missing
                        totals['extra_pixels'] += extra
                        digest.update(struct.pack('>6h', number, room, *kid))
                        digest.update(np.packbits(native).tobytes())
                        if missing or extra:
                            cases.append(dict(kid=list(kid), missing=missing, extra=extra))
                    totals['states'] += 1
                    if cases:
                        key = f'{number}:{room}' + ('' if record is None else
                                                    f":{record['room']}:{record['cell']}={phases}")
                        results[key] = cases
    return dict(totals=dict(totals), cases=results, native_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(), scope=__doc__)


def on_screen(commands, shapes):
    return Counter((c[1], c[2], c[3], max(0, c[6][0]), max(0, c[6][1]), min(365, c[6][2]), min(510, c[6][3]))
                   for c in commands if c[0] == 'back' and c[1] in shapes
                   and max(0, c[6][0]) < min(365, c[6][2]) and max(0, c[6][1]) < min(510, c[6][3]))


def run_drawing_probe(source, levels=LEVELS, rooms=None):
    """Each gate's back pieces at rest and at a sample of heights, one gate
    at a time: the port's pressure commands against the original room."""
    from pop2.caverns import pressure_drawing_commands
    from tools.extract_pressure_plates import CHANGED_SHAPES

    directory = Path(source) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = (directory / 'Prince.rsrc.bin').read_bytes()
    totals, results = Counter(), {}
    for number in levels:
        if not scenery_available(number):
            continue
        level = probe_level(number, prince)
        environment = struct.unpack_from('>H', level, 0x2186)[0]
        shapes = set(CHANGED_SHAPES[environment][4])
        scenery = (directory / f'{scenery_resource(number)}.bin').read_bytes()
        if number in SCENERY_LEVELS[2]:
            # Level 13 room 4 draws Kid.rsrc SHAP 4077 (extract_caverns KID_LIBRARY).
            scenery = scenery, (directory / 'Kid.rsrc.bin').read_bytes()
        program = room_assets(number, 0)[0]
        with CavernRecovery(executable, scenery, prince) as machine:
            for room in probed_rooms(number, program, rooms):
                records = program.get('pressure_plates', {}).get('rooms', {}).get(str(room), ())
                if not any(record['kind'] == 4 for record in records):
                    continue
                resources = room_assets(number, room)[1]
                commands = program['rooms'][str(room)]
                commands = commands['commands'] if isinstance(commands, dict) else commands
                rest = [pressure_phase(record['kind'], record['foreground']) for record in records]
                for index, record in enumerate(records):
                    if record['kind'] != 4:
                        continue
                    if old_export(number, room, record, records):
                        totals['old_export_states'] += len(pressure_states(record))
                        continue
                    for word in pressure_states(record):
                        mutable = bytearray(level)
                        struct.pack_into('>H', mutable, 0x780 + record['room'] * 120 + record['cell'] * 4, word)
                        phases = tuple(pressure_phase(4, word) if other == index else value
                                       for other, value in enumerate(rest))
                        port = on_screen(pressure_drawing_commands(commands, records, phases, resources), shapes)
                        native = on_screen(recover_room(executable, scenery, bytes(mutable), room, prince,
                                                        _machine=machine)['commands'], shapes)
                        totals['states'] += 1
                        if port != native:
                            totals['different_states'] += 1
                            results[f"{number}:{room}:{record['room']}:{record['cell']}={phases[index]}"] = dict(
                                port=[list(key) for key in port - native],
                                native=[list(key) for key in native - port])
    return dict(totals=dict(totals), cases=results, executable_sha256=hashlib.sha256(executable).hexdigest(),
                scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='The original recovery folder')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--level', type=int, action='append', help='Only these levels (repeatable)')
    parser.add_argument('--modes', action='store_true', help='Also modes 0-7 and the crushed actions')
    parser.add_argument('--drawing', action='store_true', help="The gates' own back pieces per state")
    args = parser.parse_args()
    levels = tuple(args.level) if args.level else LEVELS
    report = (run_drawing_probe(args.source, levels) if args.drawing
              else run_probe(args.source, levels, modes=args.modes))
    text = json.dumps(report, indent=1) + '\n'
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(json.dumps(report['totals']))
    for key, cases in report['cases'].items():
        print(key, cases[:6], f'... {len(cases)}' if len(cases) > 6 else '')
    if any(report['totals'].get(key) for key in ('missing_pixels', 'extra_pixels', 'different_states')):
        raise SystemExit(1)
