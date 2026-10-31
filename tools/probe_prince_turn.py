"""Execute the original Prince sword turn 6:26b8 against LevelMap.combat_turn_offset.

DoTurn's Prince branch (6:2638 -> 6:26b8) refuses the turn in level five's
room 10 while the bridge breaks, else reserves 84 pixels before a wall, a gap
or a blocking gate one or two cells behind the new facing, moves X (AddCharX)
and calls JumpSeq(127). It runs here with its real helpers: GetCellsInFront
4:39fc, ReadCell 4:27ee (GetUndefineCellId, room links), IsFloor 3:4da6, the
gate collision 4:5b0e, GetFCharX/GetDist1 4:3a72-3ac8 and AddCharX 4:2bae.
The column word comes from LoadFrame's own 4:2a7c. Only JumpSeq 6:0006 is
supplied (it records the sequence).
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


class NativePrinceTurn(NativeRules):
    RANGES = {
        3: ((0x4da6, 0x4dd4), (0x4eb2, 0x4ee4), (0x4ef2, 0x4f24)),
        4: ((0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x2a7c, 0x2a8c), (0x2bae, 0x2bcc),
            (0x322a, 0x3262), (0x39fc, 0x3a32), (0x3a72, 0x3ac8), (0x3ad6, 0x3aea),
            (0x5b0e, 0x5ba8)),
        5: ((0x0004, 0x0066), (0x48b0, 0x48dc)),
        6: ((0x26b8, 0x277e),),
    }
    SUPPLIED = {(6, 0x0006): 'jump'}

    def dispatch(self, cpu, address, size, user):
        if divmod(address - self.CODE_BASE, 0x10000) == (6, 0x0006):
            stack = cpu.reg_read(self.registers['a7'])
            self.jumps.append(struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0])
        super().dispatch(cpu, address, size, user)


# Word fields of the character copy (a5-0x5056) and the Kid's room.
ROOM, COLUMN, ROW, FACING, X = -0x5040, -0x504a, -0x5048, -0x5054, -0x5052
TYPE, POSE, SEQUENCE, TOP, BOTTOM = -0x504e, -0x504c, -0x502e, -0x502c, -0x5028
FRAME_DX, FRAME_FLAGS, KID_ROOM, BREAKING = -0x520e, -0x520a, -0x4fc2, -0x3130
FRAMES = ((0, 0), (12, 0x45), (-7, 2))


def gate_cells(level, rooms):
    for room in range(rooms):
        for cell in range(30):
            if struct.unpack_from('>H', level, room * 60 + cell * 2)[0] == 4:
                yield room, cell


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    machine = NativePrinceTurn(parse_resource_fork(raw))
    levels = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL']
    digest, totals, moved, mismatches = hashlib.sha256(), Counter(), Counter(), Counter()
    examples = {}

    def case(label, level, environment, room, row, x, facing, frame, sequence=227, pose=158,
             actor=0, top=20, bottom=110, breaking=0):
        machine.reset(level)
        machine.jumps = []
        for field, value in ((ROOM, room + 1), (ROW, row), (FACING, 0 if facing else -1),
                             (X, x + NATIVE_X_ORIGIN), (TYPE, actor), (POSE, pose),
                             (SEQUENCE, sequence), (TOP, top), (BOTTOM, bottom),
                             (FRAME_DX, frame[0]), (FRAME_FLAGS, frame[1]),
                             (KID_ROOM, room + 1), (BREAKING, breaking)):
            machine.put_word(field, value)
        machine.call(4, 0x2a7c)
        machine.call(6, 0x26b8)
        native = (tuple(machine.jumps), machine.word(X) - NATIVE_X_ORIGIN)
        number = struct.unpack_from('>H', level, 0x218a)[0]
        if number == 5 and room == 9 and breaking > 0:
            expected = ((), x)
        else:
            state = SequenceState(sequence, action=pose, target_x=x, facing=int(facing),
                                  actor_type=actor, level_kind=environment)
            record = SimpleNamespace(offset_x=frame[0], aux=frame[1])
            offset = LevelMap(level).combat_turn_offset(room, row, state, record,
                                                        (0, top, 40, bottom - 1))
            expected = ((127,), x + (offset if facing else -offset))
        digest.update(struct.pack('>hh', len(native[0]), native[1]))
        totals[label] += 1
        moved[label] += native[1] != x
        if native != expected:
            key = (label, environment)
            mismatches[key] += 1
            examples.setdefault(key, dict(level=number, room=room, row=row, x=x, facing=facing,
                                          frame=frame, sequence=sequence, pose=pose, actor=actor,
                                          height=bottom - top, native=native, port=expected))

    for resource, entry in sorted(levels.items()):
        level = entry['data']
        environment = struct.unpack_from('>H', level, 0x2186)[0]
        number = struct.unpack_from('>H', level, 0x218a)[0]
        rooms = struct.unpack_from('>H', level, 0x2180)[0]
        # Terrain sweep: every room and row, X across and beyond the room,
        # both facings; the variants cycle the 94/207 allowances, the frame
        # and (level five) the breaking-bridge word.
        index = 0
        for room in range(rooms):
            for row in range(3):
                for x in range(-40, 560, 7):
                    for facing in (True, False):
                        sequence, pose = ((227, 158), (94, 158), (227, 207), (94, 207))[index % 4]
                        breaking = (0, 1, -1)[index % 3] if number == 5 and room == 9 else 0
                        case('terrain', level, environment, room, row, x, facing,
                             FRAMES[index % 3], sequence, pose, breaking=breaking)
                        index += 1
        # Gate sweep: a tile-4 cell one or two columns ahead, across gate
        # phases, body heights, actor types 0/1 and sequence 68.
        for room, cell in gate_cells(level, rooms):
            row, column = divmod(cell, 10)
            original = bytes(level[0x780 + room * 120 + cell * 4:][:2])
            for phase in range(0, 256, 9):
                patched = bytearray(level)
                struct.pack_into('>H', patched, 0x780 + room * 120 + cell * 4,
                                 (original[0] << 8) | phase)
                for facing in (True, False):
                    for ahead in (1, 2):
                        contact = column - (ahead if facing else -ahead)
                        for remainder in (3, 25, 47):
                            x = contact * 51 + remainder - 207 + 26 + 4 * 51
                            for actor, sequence, height in ((0, 227, 60), (0, 227, 90),
                                                            (0, 68, 90), (1, 227, 90),
                                                            (0, 227, 120)):
                                case('gate', bytes(patched), environment, room, row, x, facing,
                                     (0, 0), sequence, 158, actor, 20, 20 + height)
        print(resource, number, environment, dict(totals), dict(mismatches), flush=True)
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(cases=dict(totals), moved=dict(moved),
                mismatches={f'{label} env {env}': count for (label, env), count in mismatches.items()},
                examples={f'{label} env {env}': value for (label, env), value in examples.items()},
                result_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['JumpSeq 6:0006 (records the sequence)',
                          'LEVL 2000-2013 as stored (gate sweep patches the gate phase byte)',
                          'Character words: room, row, facing, X, type, pose, selected sequence,'
                          ' clipped body top/bottom, FRAM dx/flags; the Kid room equals the'
                          ' character room; column from LoadFrame 4:2a7c'],
                exclusions=['The callers (automatic turn 6:2638 from SwordCtrl, voluntary turn)',
                            'Opponent turn branches of 6:2638 (types 7/8/10/others)',
                            'Vertical room traversal (rows stay 0-2)'])


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
