"""Native room3 tap/stop side-contact trace and isolated ordinary-gate audit.

Native evidence uses supplied room3 poses/X/gate phases, original Kid frame
and SHAP headers, warm CheckBarr/CheckCollide1, supplied SectRect and no-op
Collide. No native controller, full contact response, room cut or pixels.
The port audit uses actual ordinary gate anchors from all levels but clears
other tiles and supplies self-links to isolate gate sides. It is neither a
whole-room gameplay trace nor independent native proof at those anchors.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.mac_resources import parse_resource_fork
from pop2.terrain import LevelMap
from tools.probe_temple_gate_passage import NativeGatePassage


# X remains in room3 coordinates after the port camera cut at pose55.
PATH = ((445, 15, 0, 184), (449, 2, 1, 184), (453, 3, 1, 184),
        (462, 4, 1, 184), (472, 5, 1, 184), (479, 6, 1, 184),
        (492, 7, 1, 184), (492, 53, 13, 184), (493, 54, 13, 124),
        (520, 55, 13, 64), (526, 56, 13, 4), (526, 49, 13, 0),
        (525, 50, 13, 0), (525, 51, 13, 0), (525, 52, 13, 0), (525, 15, 13, 0))


def audit_anchors(prince, traces):
    counts, failures = Counter(), []
    for number in range(1, 15):
        original = prince['LEVL'][1999 + number]['data']
        environment = struct.unpack_from('>H', original, 0x2186)[0]
        if environment not in (2, 3, 4):
            continue
        original_map = LevelMap(original)
        for room in range(32):
            for cell in range(30):
                row, column = divmod(cell, 10)
                tile = original_map.tile(room, column, row)
                if tile.kind != 4:
                    continue
                if original_map.throne_gate(room, tile):
                    counts['excluded_throne'] += 1
                    continue
                counts[f'environment{environment}_gates'] += 1
                # Explicit isolated fixture: other tiles/floors/room boundaries
                # must not be mistaken for an additional gate-side contact.
                level = bytearray(original)
                level[:0x780] = struct.pack('>960H', *([1] * 960))
                struct.pack_into('>H', level, room * 60 + cell * 2, 4)
                struct.pack_into('>2H', level, 0x2080 + room * 8, room + 1, room + 1)
                terrain = LevelMap(level)
                for facing, trace in traces.items():
                    history, previous = (), None
                    for x, pose, sequence, phase, body in trace:
                        dx, dy = (column - 8) * 51, (row - 1) * 120
                        x += dx
                        bounds = (body[0] + dx, body[1] + dy, body[2] + dx, body[3] + dy)
                        state = SimpleNamespace(actor_type=0, source_sequence_id=sequence)
                        struct.pack_into('>H', level, 0x780 + room * 120 + cell * 4, phase)
                        if previous:
                            history = terrain.gate_passage_history(room, row, bounds, previous[1], history, state)
                            corrected = terrain.wall_correction(room, previous[0], x, bounds,
                                previous[1], facing, row, state, gate_passages=history)
                            if corrected != x:
                                failures.append((number, room + 1, cell, facing, pose, x, corrected))
                            counts['port_comparisons'] += 1
                        previous = x, bounds
    return dict(counts=counts, failures=failures)


def run_probe(source):
    forks = source / 'resource_forks'
    files = {name: (forks / name).read_bytes() for name in
             ('Prince of Persia 2.bin', 'Kid.rsrc.bin', 'Prince.rsrc.bin')}
    executable, kid, prince_bytes = files.values()
    prince = parse_resource_fork(prince_bytes)
    original = prince['LEVL'][2011]['data']
    if (struct.unpack_from('>H', original, 0x2186)[0] != 2
            or struct.unpack_from('>H', original, 0x218a)[0] != 12
            or struct.unpack_from('>H', original, 2 * 60 + 18 * 2)[0] != 4):
        raise AssertionError('Wrong original room3 fixture')
    machine = NativeGatePassage(parse_resource_fork(executable), parse_resource_fork(kid))
    traces, samples, comparisons = {}, 0, 0
    for facing in (0, 1):
        level = bytearray(original)
        terrain = LevelMap(level)
        machine.prepare(level, 3, 1)
        previous, history, trace = None, (), []
        for x, pose, sequence, phase in PATH:
            x = x if facing else 950 - x
            offset = 0x780 + 2 * 120 + 18 * 4
            struct.pack_into('>H', level, offset, phase)
            machine.cpu.mem_write(machine.LEVEL + offset, struct.pack('>H', phase))
            bounds, events = machine.sample_run(x, pose, facing, sequence=sequence)
            if events:
                raise AssertionError(('native false side contact', facing, pose, events))
            state = SimpleNamespace(actor_type=0, source_sequence_id=sequence)
            if previous:
                history = terrain.gate_passage_history(2, 1, bounds, previous[1], history, state)
                corrected = terrain.wall_correction(2, previous[0], x, bounds,
                    previous[1], facing, 1, state, gate_passages=history)
                if corrected != x:
                    raise AssertionError(('port false side contact', facing, pose, corrected, x))
                comparisons += 1
            trace.append((x, pose, sequence, phase, bounds))
            previous = x, bounds
            samples += 1
        if machine.level_bytes(len(level)) != level or machine.services:
            raise AssertionError('Unexpected level/service mutation')
        traces[facing] = trace
    audit = audit_anchors(prince, traces)
    if audit['failures']:
        raise AssertionError(audit['failures'][:8])
    return {'native_samples': samples, 'native_port_comparisons': comparisons,
            'anchor_audit': dict(audit['counts']), 'mismatches': 0, 'traces': traces,
            'inputs_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
            'scope': __doc__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print({key: report[key] for key in ('native_samples', 'native_port_comparisons', 'anchor_audit', 'mismatches')})


if __name__ == '__main__':
    main()
