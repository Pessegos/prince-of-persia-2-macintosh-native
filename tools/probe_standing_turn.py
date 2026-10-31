"""Execute the original standing-turn gate reserve 6:10f6-1158 against
LevelMap.standing_turn_offset.

The standing Backward handler 6:10e4 asks GetCellsInFront 4:39fc for the cell
ahead; when it is a gate (tile 4) for which the gate collision 4:5b0e blocks,
it moves the Kid back (AddCharX 4:2bae) until GetDist1 4:3a92 leaves 11 pixels
in the caverns (LEVL 0x2186 = 3), none at the throne (Kid room 9 of level
eight: the reserve is -100) and 6 elsewhere. It runs here from 6:10f6 to
6:1158 with its real helpers: GetCellsInFront, ReadCell 4:27ee
(GetUndefineCellId, room links), the gate collision, GetFCharX/GetDist1
4:3a72-3ac8, AddCharX and DIVS 5:48b0. The column word comes from LoadFrame's
own 4:2a7c. Nothing is supplied.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.coordinates import NATIVE_X_ORIGIN
from pop2.mac_resources import parse_resource_fork
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap
from tools.probe_level7_rules import NativeRules
from tools.probe_prince_turn import (BOTTOM, COLUMN, FACING, FRAME_DX, FRAME_FLAGS, FRAMES,
                                     KID_ROOM, POSE, ROOM, ROW, SEQUENCE, TOP, TYPE, X,
                                     gate_cells)


class NativeStandingTurn(NativeRules):
    RANGES = {
        4: ((0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x2a7c, 0x2a8c), (0x2bae, 0x2bcc),
            (0x322a, 0x3262), (0x39fc, 0x3a32), (0x3a72, 0x3ac8), (0x3ad6, 0x3aea),
            (0x5b0e, 0x5ba8)),
        5: ((0x0004, 0x0066), (0x48b0, 0x48dc)),
        6: ((0x10f6, 0x1158),),
    }
    SUPPLIED = {}


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    machine = NativeStandingTurn(parse_resource_fork(raw))
    levels = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL']
    digest, totals, moved, mismatches = hashlib.sha256(), Counter(), Counter(), Counter()
    examples = {}

    def case(label, level, environment, room, row, x, facing, frame, sequence=0, actor=0,
             top=148, bottom=227):
        machine.reset(level)
        for field, value in ((ROOM, room + 1), (ROW, row), (FACING, 0 if facing else -1),
                             (X, x + NATIVE_X_ORIGIN), (TYPE, actor), (POSE, 15),
                             (SEQUENCE, sequence), (TOP, top), (BOTTOM, bottom),
                             (FRAME_DX, frame[0]), (FRAME_FLAGS, frame[1]),
                             (KID_ROOM, room + 1)):
            machine.put_word(field, value)
        machine.call(4, 0x2a7c)
        machine.call(6, 0x10f6, stop=(6, 0x1158))
        native = machine.word(X) - NATIVE_X_ORIGIN
        state = SequenceState(sequence, action=15, target_x=x, facing=int(facing),
                              actor_type=actor, level_kind=environment)
        record = SimpleNamespace(offset_x=frame[0], aux=frame[1])
        expected = x + LevelMap(level).standing_turn_offset(room, row, state, record,
                                                            (0, top, 40, bottom - 1))
        digest.update(struct.pack('>h', native))
        totals[label] += 1
        moved[label] += native != x
        if native != expected:
            key = (label, environment)
            mismatches[key] += 1
            examples.setdefault(key, dict(level=struct.unpack_from('>H', level, 0x218a)[0],
                                          room=room, row=row, x=x, facing=facing, frame=frame,
                                          sequence=sequence, actor=actor, height=bottom - top,
                                          column=machine.word(COLUMN), native=native,
                                          port=expected))

    for resource, entry in sorted(levels.items()):
        level = entry['data']
        environment = struct.unpack_from('>H', level, 0x2186)[0]
        rooms = struct.unpack_from('>H', level, 0x2180)[0]
        # Terrain sweep: every room and row, X across and beyond the room.
        index = 0
        for room in range(rooms):
            for row in range(3):
                for x in range(-40, 560, 11):
                    for facing in (True, False):
                        case('terrain', level, environment, room, row, x, facing,
                             FRAMES[index % 3])
                        index += 1
        # Gate sweep: the gate one cell ahead of the supporting foot, every
        # remainder below 13 and a few beyond, across phases, body heights,
        # actor types 0/1 and sequence 68.
        phases = range(21) if environment == 1 else range(0, 256, 9)
        for room, cell in gate_cells(level, rooms):
            row, column = divmod(cell, 10)
            original = bytes(level[0x780 + room * 120 + cell * 4:][:2])
            for phase in phases:
                patched = bytearray(level)
                struct.pack_into('>H', patched, 0x780 + room * 120 + cell * 4,
                                 (original[0] << 8) | phase)
                for facing in (True, False):
                    contact = column - (1 if facing else -1)
                    for distance in (*range(13), 20, 40):
                        remainder = 50 - distance if facing else distance
                        x = contact * 51 + remainder - 207 + 26 + 4 * 51
                        for actor, sequence, height in ((0, 0, 79), (0, 68, 79),
                                                        (1, 0, 79), (0, 0, 30)):
                            case('gate', bytes(patched), environment, room, row, x, facing,
                                 (0, 0), sequence, actor, 148, 148 + height)
        print(resource, environment, dict(totals), dict(mismatches), flush=True)
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(cases=dict(totals), moved=dict(moved),
                mismatches={f'{label} env {env}': count for (label, env), count in mismatches.items()},
                examples={f'{label} env {env}': value for (label, env), value in examples.items()},
                result_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['Nothing; 6:10f6-1158 runs between its 3E3A/-503e prologue and the'
                          ' 1FB2 epilogue',
                          'LEVL 2000-2013 as stored (gate sweep patches the gate phase byte)',
                          'Character words: room, row, facing, X, type, pose 15, selected'
                          ' sequence, clipped body top/bottom, FRAM dx/flags; the Kid room equals'
                          ' the character room; column from LoadFrame 4:2a7c'],
                exclusions=['The rest of the Backward handler (6:10e4 prologue, 6:1158 onward:'
                            ' 1FB2, SEQS 5 selection)',
                            'Vertical room traversal (rows stay 0-2)'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('cases', 'moved', 'mismatches', 'examples')}))


if __name__ == '__main__':
    main()
