"""Execute the original GetBarrDistances 4:5eae at every gate against LevelMap.step_boundary.

The Kid's step distance (4:5eae) classifies the supporting cell and the one
ahead (4:52bc) and measures a barrier with GetBarrDistFromFace 4:6562, which
first asks the gate collision 4:5b0e whether a gate blocks at all. Everything
runs natively: CurrentCell/ReadCell (room links, GetUndefineCellId), the
barrier class, IsFloor/IsSpace/IsWall, GetDist1/GetCharCol with DIVS 5:48b0,
AdjustRoom 4:56e6 and the column word from LoadFrame's 4:2a7c. Nothing is
supplied. Body edges, clipped top/bottom, FRAM dx/flags and the caution word
a5-0x36bc are fixtures.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.coordinates import NATIVE_X_ORIGIN
from pop2.desert_state import DesertState
from pop2.mac_resources import parse_resource_fork
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap
from tools.probe_prince_turn import (BOTTOM, COLUMN, FACING, FRAME_DX, FRAME_FLAGS, FRAMES,
                                     KID_ROOM, ROOM, ROW, SEQUENCE, TOP, TYPE, X,
                                     NativePrinceTurn, gate_cells)
from tools.probe_temple_gate_soft_distance import NativeTempleSoftDistance


def merged_ranges(*classes):
    ranges = {}
    for cls in classes:
        for segment, spans in cls.RANGES.items():
            ranges[segment] = tuple(sorted(set(ranges.get(segment, ())) | set(spans)))
    return ranges


class NativeGateBarriers(NativeTempleSoftDistance):
    RANGES = merged_ranges(NativeTempleSoftDistance, NativePrinceTurn)
    SUPPLIED = {}


# Outputs: the collision edges, the barrier anchor and the reason word.
LEFT, RIGHT, HEIGHT, CAUTION, REASON = -0x3564, -0x3566, -0x3560, -0x36bc, -0x3576
UNWRITTEN = 71
NEIGHBOR_SLOTS = (-0x4fc0, -0x4fb4, -0x4fb8, -0x4fbe, -0x4fb2, -0x4fb6)


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    machine = NativeGateBarriers(parse_resource_fork(raw))
    levels = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL']
    digest, totals, barriers, mismatches = hashlib.sha256(), Counter(), Counter(), Counter()
    examples, categories, unwritten = {}, Counter(), Counter()

    def case(level, environment, room, row, x, facing, frame, phase, sequence, height,
             width, caution):
        top, bottom = 20, 20 + height
        left, right = x - width, x + width
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', 0, 0, 0, 0, -32768, -32768))
        for field, value in ((ROOM, room + 1), (ROW, row), (FACING, 0 if facing else -1),
                             (X, x + NATIVE_X_ORIGIN), (TYPE, 0), (SEQUENCE, sequence),
                             (TOP, top), (BOTTOM, bottom), (FRAME_DX, frame[0]),
                             (FRAME_FLAGS, frame[1]), (KID_ROOM, room + 1),
                             (LEFT, left + NATIVE_X_ORIGIN), (RIGHT, right + 1 + NATIVE_X_ORIGIN),
                             (HEIGHT, height), (CAUTION, caution), (REASON, UNWRITTEN)):
            machine.put_word(field, value)
        for slot in NEIGHBOR_SLOTS:
            machine.put_word(slot, 0)
        machine.call(4, 0x2a7c)
        distance = struct.unpack('>h', struct.pack('>H', machine.call(4, 0x5eae)))[0]
        native = (distance, machine.word(REASON))
        if machine.services:
            raise AssertionError(dict(machine.services))
        terrain = LevelMap(level)
        if environment == 1:
            terrain.desert = DesertState(gate=phase)
        state = SequenceState(sequence, action=158, target_x=x, facing=bool(facing),
                              actor_type=0, level_kind=environment)
        record = SimpleNamespace(offset_x=frame[0], aux=frame[1])
        boundary = terrain.step_boundary(room, row, state, record, (left, top, right, bottom - 1),
                                         cautious=bool(caution))
        port = (boundary.clearance, boundary.barrier_type)
        digest.update(struct.pack('>hh', *native))
        number = struct.unpack_from('>H', level, 0x218a)[0]
        totals[environment] += 1
        barriers[environment] += native[1] == 1
        if native[1] == UNWRITTEN and boundary.tile_kind in (23, 24):
            # The slope branches 4:5fa2/5fc6 leave the reason word as it
            # was; the port reports 0. Only the distance is compared.
            unwritten[environment] += 1
            native = (native[0], port[1])
        if native != port:
            mismatches[environment] += 1
            categories[f'env {environment} native {native[1]} port {port[1]}'] += 1
            examples.setdefault(environment, dict(
                level=number, room=room, row=row, x=x, facing=facing, frame=frame,
                phase=phase, sequence=sequence, height=height, width=width,
                caution=caution, column=machine.word(COLUMN), native=native, port=port))

    for resource, entry in sorted(levels.items()):
        level = entry['data']
        environment = struct.unpack_from('>H', level, 0x2186)[0]
        rooms = struct.unpack_from('>H', level, 0x2180)[0]
        # The desert's phase runs 0-20 (18:067c); elsewhere the low byte.
        phases = range(21) if environment == 1 else range(0, 256, 9)
        for room, cell in gate_cells(level, rooms):
            row, column = divmod(cell, 10)
            offset = 0x780 + room * 120 + cell * 4
            original = struct.unpack_from('>H', level, offset)[0]
            for phase in phases:
                patched = bytearray(level)
                mask = 0xffe0 if environment == 1 else 0xff00
                struct.pack_into('>H', patched, offset, (original & mask) | phase)
                patched = bytes(patched)
                index = 0
                for facing in (True, False):
                    # The supporting cell is the gate itself or one behind it.
                    for back in (0, 1):
                        contact = column - (back if facing else -back)
                        for remainder in (3, 25, 47):
                            x = contact * 51 + remainder + 26 - NATIVE_X_ORIGIN + 4 * 51
                            for sequence, height in ((227, 60), (227, 90), (68, 90), (227, 120)):
                                for width in (10, 22):
                                    case(patched, environment, room, row, x, facing,
                                         FRAMES[index % 3], phase, sequence, height, width,
                                         index % 2)
                                    index += 1
        print(resource, environment, dict(totals), dict(mismatches), flush=True)
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(cases={f'env {env}': count for env, count in totals.items()},
                barrier_results={f'env {env}': count for env, count in barriers.items()},
                mismatches={f'env {env}': count for env, count in mismatches.items()},
                examples={f'env {env}': value for env, value in examples.items()},
                categories=dict(categories),
                slope_reason_unwritten={f'env {env}': count for env, count in unwritten.items()},
                result_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['None: every executed instruction is original'],
                fixtures=['LEVL 2000-2013 as stored, the gate phase patched (desert: five low'
                          ' bits 0-20; elsewhere the low byte, 0-252 in steps of 9)',
                          'Kid words: room, row, facing, X, type 0, sequence 227/68, clipped'
                          ' top/bottom (heights 60/90/120), FRAM dx/flags; Kid room equals the'
                          ' character room; column from LoadFrame 4:2a7c',
                          'Collision edges a5-0x3564/-0x3566 (X -/+ 10 or 22), height'
                          ' a5-0x3560, caution a5-0x36bc 0/1, neighbor-room slots 0'],
                exclusions=['The callers (DoStepFwd 6:1276, GenCtrl, GetEdgeDistance users)',
                            'Collision-bank construction (CheckBarr) and the CheckCollide'
                            ' response; only its 4:5b0e decision is shared with 6562',
                            'Cells other than the gate and the one behind it',
                            'The reason word after a slope (23/24) result: native leaves it'
                            ' unwritten, the port reports 0; distances still compared'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
