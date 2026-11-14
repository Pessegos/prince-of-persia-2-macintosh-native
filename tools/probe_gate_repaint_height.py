"""Compare live temple gate repaint commands with the preserved Macintosh code."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from pop2.caverns import cavern_assets, pressure_drawing_commands
from pop2.level_data import LevelDefinition
from pop2.mac_resources import parse_resource_fork
from tools.extract_caverns import CavernRecovery, recover_room


def run_probe(source):
    files = {name: (source / 'resource_forks' / name).read_bytes() for name in
             ('Prince of Persia 2.bin', 'Temple.rsrc.bin', 'Prince.rsrc.bin')}
    executable, temple, prince = files.values()
    levels = parse_resource_fork(prince)
    original_art = parse_resource_fork(temple)
    comparisons, gates = 0, set()
    digest = hashlib.sha256()
    with CavernRecovery(executable, temple, prince) as machine:
        for number in range(10, 14):
            level = LevelDefinition.read(levels, number).data
            if struct.unpack_from('>H', level, 0x2186)[0] != 2:
                raise AssertionError('Unexpected temple environment/header')
            if struct.unpack_from('>H', level, 0x218a)[0] != number:
                raise AssertionError('Unexpected level number')
            program, resources, *_ = cavern_assets(number)
            if resources['SHAP'][3576]['data'][:8] != original_art['SHAP'][3576]['data'][:8]:
                raise AssertionError('Imported gate SHAP header differs from the reference')
            for room, records in program['pressure_plates']['rooms'].items():
                room_id = int(room)
                for index, record in enumerate(records):
                    if record['kind'] != 4 or record['room'] != room_id:
                        continue
                    offset = 0x780 + room_id * 120 + record['cell'] * 4
                    initial = struct.unpack_from('>H', level, offset)[0]
                    if initial != record['foreground']:
                        raise AssertionError('Imported foreground differs from original LEVL')
                    keys = {('front', *key[1:]) for key in record['commands']}

                    def selected(commands):
                        return [c for c in commands if (c[0], c[1], *c[7:10]) in keys]

                    def visible(commands):
                        # Runtime clips to its 510x365 canvas; native commands
                        # may retain a negative top before rasterization.
                        return [[*c[:6], [max(0, c[6][0]), max(0, c[6][1]),
                                          min(365, c[6][2]), min(510, c[6][3])], *c[7:]]
                                for c in commands if max(0, c[6][0]) < min(365, c[6][2])
                                and max(0, c[6][1]) < min(510, c[6][3])]

                    sources = [('floor', program['floor_redraw'][room], {'floor_redraw': True})]
                    sources.extend((action, commands, {'climb_action': int(action)}) for action, commands
                                   in program['climb_redraw'][room].items() if selected(commands))
                    sources = [(name, commands, options) for name, commands, options in sources
                               if selected(commands)]
                    for name, commands, options in sources:
                        slots = {(c[9], c[8], 2) for c in selected(commands)}
                        for position in (0, 4, 92, 180, 184, 255):
                            mutable = bytearray(level)
                            struct.pack_into('>H', mutable, offset, (initial & 0xff00) | position)
                            phases = [min(r['foreground'] & 255, 184) // 4 if r['kind'] == 4 else
                                      min(r['foreground'] & 255, 79) if r['kind'] == 17 else
                                      r['foreground'] & 7 if r['kind'] in (27, 33) else
                                      int(bool(r['foreground'] & 0x2000)) for r in records]
                            phases[index] = min(position, 184) // 4
                            actual = selected(pressure_drawing_commands(commands, records, phases, resources))
                            native = selected(recover_room(executable, temple, bytes(mutable), room_id, prince,
                                _machine=machine, only=slots, **options)['commands'])
                            if visible(actual) != visible(native):
                                raise AssertionError((number, room_id + 1, record['cell'], name,
                                                      position, actual, native))
                            digest.update(json.dumps(actual).encode('ascii'))
                            comparisons += 1
                            gates.add((number, room_id + 1, record['cell']))
    if len(gates) != 41 or (12, 3, 18) not in gates:
        raise AssertionError('Incomplete temple gate coverage')
    return {'comparisons': comparisons, 'gates': len(gates), 'mismatches': 0,
            'outputs_sha256': digest.hexdigest(),
            'inputs_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
            'scope': 'Native DrawHalf3:3480 / DrawFloorBuf3:371c -> DrawTempGateMovable10:0976-0a44. '
                     'All imported own-room temple gates with front repaint commands; six supplied positions; '
                     'command clips normalized to the 510x365 viewport. '
                     'Original CODE, LEVL, PIEC, SHAP headers; same command-capture exporter as import. '
                     'Supplied per-cell traversal/dirty clips, resource handles, rectangle services, '
                     'shape-header lookup and recorded drawing endpoints; dirty bookkeeping inert. '
                     'No QuickDraw pixels, independent SHAP decoding, real actor admission, visible-neighbor '
                     'repaints or full FrameAdv proof.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
