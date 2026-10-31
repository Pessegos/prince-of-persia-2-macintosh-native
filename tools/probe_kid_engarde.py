"""Execute the original DoKidEngarde 6:1f04 against LevelMap.combat_draw_offset.

DoEngarde 6:1e78 calls DoKidEngarde for the Kid. It refuses the draw (-1) at
poses 246-261, in the desert and in level fourteen's rooms 1-2; otherwise,
when the cell ahead is not IsFloor 3:4da6, is a loose floor or a gate that
4:5b0e blocks (or, facing right, the Kid stands in such a gate's cell), it
refuses when the cell behind (4:3a48) is obstructed the same way or the
sequence mode a5-0x5022 (SEQS -21) is 4, and else reserves 56 pixels with
GetBarrDistances 4:5eae (AddCharX 4:2bae) before SEQS 55.

Everything runs natively (CurrentCell, ReadCell, the gate collision, the
whole 4:5eae and GetSlideRockX 5:21f6 outside the temple). Supplied: the
draw sound 5:4d84 (recorded) and, in the temple only, TempGetSlideRockX
10:20fe (no rock: 0).
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
from tools.probe_gate_barriers import (CAUTION, HEIGHT, LEFT, NEIGHBOR_SLOTS, RIGHT,
                                       NativeGateBarriers, merged_ranges)
from tools.probe_prince_turn import (BOTTOM, COLUMN, FACING, FRAME_DX, FRAME_FLAGS, FRAMES,
                                     KID_ROOM, POSE, ROOM, ROW, SEQUENCE, TOP, TYPE, X,
                                     gate_cells)


class NativeKidEngarde(NativeGateBarriers):
    RANGES = merged_ranges(NativeGateBarriers)
    RANGES[4] = RANGES[4] + ((0x35a6, 0x35ba), (0x3a48, 0x3a70))
    RANGES[5] = RANGES[5] + ((0x21f6, 0x2224),)
    RANGES[6] = RANGES.get(6, ()) + ((0x1f04, 0x2154),)
    SUPPLIED = {(5, 0x4d84): 'sound', (10, 0x20fe): 'slide_rock'}


MODE, SWORD_STATE = -0x5022, -0x503c


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    machine = NativeKidEngarde(parse_resource_fork(raw))
    levels = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL']
    digest, totals, refused, moved, mismatches = (hashlib.sha256(), Counter(), Counter(),
                                                   Counter(), Counter())
    examples, services = {}, Counter()

    def case(label, level, environment, room, row, x, facing, frame, phase=None, pose=15,
             mode=0, sequence=0, height=79, width=10):
        top, bottom = 148, 148 + height
        left, right = x - width, x + width
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', 0, 0, 0, 0, -32768, -32768))
        for field, value in ((ROOM, room + 1), (ROW, row), (FACING, 0 if facing else -1),
                             (X, x + NATIVE_X_ORIGIN), (TYPE, 0), (POSE, pose),
                             (SEQUENCE, sequence), (TOP, top), (BOTTOM, bottom),
                             (FRAME_DX, frame[0]), (FRAME_FLAGS, frame[1]),
                             (KID_ROOM, room + 1), (LEFT, left + NATIVE_X_ORIGIN),
                             (RIGHT, right + 1 + NATIVE_X_ORIGIN), (HEIGHT, height),
                             (CAUTION, 0), (MODE, mode), (SWORD_STATE, 1)):
            machine.put_word(field, value)
        for slot in NEIGHBOR_SLOTS:
            machine.put_word(slot, 0)
        machine.call(4, 0x2a7c)
        result = struct.unpack('>h', struct.pack('>H', machine.call(6, 0x1f04)))[0]
        native = (result, machine.word(X) - NATIVE_X_ORIGIN)
        services.update(machine.services)
        terrain = LevelMap(level)
        if environment == 1:
            terrain.desert = DesertState(gate=phase or 0)
        state = SequenceState(sequence, action=pose, target_x=x, facing=int(facing),
                              actor_type=0, level_kind=environment)
        state.sequence_mode = mode
        record = SimpleNamespace(offset_x=frame[0], aux=frame[1])
        offset = terrain.combat_draw_offset(room, row, state, record, (left, top, right, bottom - 1))
        expected = (-1, x) if offset is None else (55, x + (offset if facing else -offset))
        digest.update(struct.pack('>hh', *native))
        totals[label] += 1
        refused[label] += native[0] == -1
        moved[label] += native[1] != x
        if native != expected:
            key = (label, environment)
            mismatches[key] += 1
            examples.setdefault(key, dict(level=struct.unpack_from('>H', level, 0x218a)[0],
                                          room=room, row=row, x=x, facing=facing, frame=frame,
                                          phase=phase, pose=pose, mode=mode, sequence=sequence,
                                          height=height, column=machine.word(COLUMN),
                                          native=native, port=expected))

    for resource, entry in sorted(levels.items()):
        level = entry['data']
        environment = struct.unpack_from('>H', level, 0x2186)[0]
        rooms = struct.unpack_from('>H', level, 0x2180)[0]
        # Terrain sweep: every room and row, X across and beyond the room,
        # both facings; a few cases at poses 246/261/262 and in mode 4.
        index = 0
        for room in range(rooms):
            for row in range(3):
                for x in range(-40, 560, 9):
                    for facing in (True, False):
                        pose, mode = ((15, 0), (15, 4), (246, 0), (261, 0), (262, 0),
                                      (15, 2), (15, 0))[index % 7]
                        case('terrain', level, environment, room, row, x, facing,
                             FRAMES[index % 3], pose=pose, mode=mode)
                        index += 1
        # Gate sweep: the supporting cell is the gate, one behind it or one
        # ahead of it; phases, body heights, sequence 68.
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
                    for shift in (-1, 0, 1):
                        contact = column + (shift if facing else -shift)
                        for remainder in (3, 25, 47):
                            x = contact * 51 + remainder + 26 - NATIVE_X_ORIGIN + 4 * 51
                            for sequence, height in ((0, 79), (68, 79), (0, 30)):
                                case('gate', patched, environment, room, row, x, facing,
                                     FRAMES[index % 3], phase, sequence=sequence, height=height,
                                     width=(10, 22)[index % 2])
                                index += 1
        print(resource, environment, dict(totals), dict(mismatches), flush=True)
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(cases=dict(totals), refused=dict(refused), moved=dict(moved),
                mismatches={f'{label} env {env}': count for (label, env), count in mismatches.items()},
                examples={f'{label} env {env}': value for (label, env), value in examples.items()},
                services=dict(services),
                result_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['Draw sound 5:4d84 (recorded only)',
                          'TempGetSlideRockX 10:20fe in the temple: 0 (no sliding rock)'],
                fixtures=['LEVL 2000-2013 as stored (gate sweep patches the phase: desert five'
                          ' low bits 0-20, elsewhere the low byte 0-252 step 9)',
                          'Kid words: room, row, facing, X, type 0, pose, mode a5-0x5022,'
                          ' sequence 0/68, clipped top/bottom (heights 79/30), FRAM dx/flags,'
                          ' collision edges X -/+ 10 or 22; the Kid room equals the character'
                          ' room; column from LoadFrame 4:2a7c'],
                exclusions=['The temple sliding-rock branch (GetSlideRockX nonzero)',
                            'Type-1 actors and the level-14 type-1 branch (S09_2674)',
                            'The a5-0x503c sword-state word (written, not compared)',
                            'DoEngarde 6:1e78 and its callers (GenCtrl admission)'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('cases', 'refused', 'moved', 'mismatches',
                                                   'examples', 'services')}))


if __name__ == '__main__':
    main()
