"""Compare every signed native X with runtime column and foot-edge arithmetic.

Executes4:3ad6/GetCharCol,4:3aa0/GetDist1 and5:48b0 without endpoint
stubs. X and facing are supplied; only the division-remainder A5 word may
change. No frame/foot-offset loading, cell access, controller or FrameAdv.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from pop2.opponent_generation import character_column
from pop2.ruins_ai import column_remainder
from pop2.terrain import floor_edge_distance
from tools.probe_level7_rules import NativeRules
from tools.probe_level7_sequence_selection import signed_word


class NativeColumns(NativeRules):
    RANGES = {4: ((0x3aa0, 0x3aca), (0x3ad6, 0x3afa)), 5: ((0x48b0, 0x48de),)}
    SUPPLIED = {}


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    levels = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL']
    machine = NativeColumns(parse_resource_fork(executable))
    counts, mismatches, digest = Counter(), [], hashlib.sha256()
    for x in range(-32768, 32768):
        machine.reset(levels[2009]['data'])
        machine.put_word(-0x481c, 79)
        before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        column = signed_word(machine.call(4, 0x3ad6, (x,)))
        remainder = machine.word(-0x481c)
        struct.pack_into('>h', before, len(machine.data) - 0x481c, remainder)
        if bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data))) != before:
            raise AssertionError('Column call mutated other A5 fields')
        distances = []
        for facing in (-1, 0):
            machine.put_word(-0x5054, facing)
            before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
            distances.append(signed_word(machine.call(4, 0x3aa0, (x,))))
            struct.pack_into('>h', before, len(machine.data) - 0x481c, remainder)
            if bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data))) != before:
                raise AssertionError('Distance call mutated other A5 fields')
        scene_x = x - 207
        native = (column, remainder, *distances)
        port = (character_column(scene_x), column_remainder(scene_x),
                floor_edge_distance(scene_x, 0), floor_edge_distance(scene_x, 1))
        if native != port:
            counts['mismatch'] += 1
            if len(mismatches) < 40:
                mismatches.append(dict(native_x=x, native=native, port=port))
        else:
            counts['match'] += 1
        if machine.services or machine.level_bytes(len(levels[2009]['data'])) != levels[2009]['data']:
            raise AssertionError('Native calls changed the level or supplied a service')
        digest.update(struct.pack('>5h', x, *native))
    return dict(coordinates=65536, calls=196608, cases=dict(counts), examples=mismatches,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                outputs_sha256=digest.hexdigest(), supplied=[], scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--allow-mismatch', action='store_true', help='Record a pre-fix baseline')
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    if report['cases'].get('mismatch') and not args.allow_mismatch:
        raise SystemExit(1)
