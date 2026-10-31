"""Execute the original EnemyCollide 4:62b0 against LevelMap.enemy_collide.

FrameAdv 2:65f6 calls EnemyCollide for every opponent after Move, instead
of the Kid's CheckBarr/CheckCollide1. For an ordinary opponent (not the
heads 7/8, whose 7:0b6e branch probe_ruins_runtime covers) it needs
animation state a5-0x5046 = 1, native ALIVE, the sword drawn and a selected
sequence other than 58. It takes the supporting cell (CurrentCell 4:35a6) or
the one ahead (4:39fc) when IsWall 3:4ef2 or the gate collision 4:5b0e holds,
asks CheckCollide 4:5654 (crevices 4:5ade), measures both barrier distances
(4:6562/6610 with GetBarrCode 4:52bc and AdjustRoom 4:56e6), pushes the body
out (AddCharX 4:2bae) and selects SEQS 64 (out of a gate) or 65.

Native: everything above, ReadCell with its room links, the neighbour words
from 3:1ab0-1c3c and the column word from LoadFrame's 4:2a7c. Supplied: the drawing setup 3:0ac8 and GetCharEdges
4:5cbc (the edges, width, height and clipped top/bottom are written as
fixtures before the call), JumpSeq 6:0006 (records the sequence), AnimChar
4:2c0c and LoadFrame 4:2a72 (inert).
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
from tools.probe_gate_barriers import CAUTION, HEIGHT, LEFT, RIGHT, merged_ranges
from tools.probe_kid_engarde import NativeKidEngarde
from tools.probe_prince_turn import (BOTTOM, COLUMN, FACING, FRAME_DX, FRAME_FLAGS, FRAMES,
                                     KID_ROOM, POSE, ROOM, ROW, SEQUENCE, TOP, TYPE, X,
                                     gate_cells)


class NativeEnemyCollide(NativeKidEngarde):
    RANGES = merged_ranges(NativeKidEngarde)
    RANGES[3] = RANGES[3] + ((0x1ab0, 0x1c3c),)
    RANGES[4] = RANGES[4] + ((0x62b0, 0x6550), (0x6610, 0x6694), (0x5654, 0x56d4),
                             (0x56e6, 0x5728), (0x5ade, 0x5b0c), (0x5c76, 0x5cba))
    SUPPLIED = {(3, 0x0ac8): 'draw_setup', (4, 0x5cbc): 'edges', (6, 0x0006): 'jump',
                (4, 0x2c0c): 'animate', (4, 0x2a72): 'load_frame'}

    def dispatch(self, cpu, address, size, user):
        if divmod(address - self.CODE_BASE, 0x10000) == (6, 0x0006):
            stack = cpu.reg_read(self.registers['a7'])
            self.jumps.append(struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0])
        super().dispatch(cpu, address, size, user)


ANIMATION, ALIVE, ARMED, WIDTH = -0x5046, -0x503a, -0x503c, -0x3562
BARRIER_KINDS = (2, 7, 20, 25, 43, 4, 10, 12)


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    machine = NativeEnemyCollide(parse_resource_fork(raw))
    levels = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL']
    digest, totals, responses, mismatches = hashlib.sha256(), Counter(), Counter(), Counter()
    examples, services = {}, Counter()

    def case(label, level, environment, room, row, x, facing, frame, phase=None, actor=2,
             animation=1, alive=True, armed=True, sequence=150, height=79, width=21):
        top, bottom = 148, 148 + height
        left, right = x - width // 2, x - width // 2 + width - 1
        machine.reset(level)
        machine.jumps = []
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', 0, 0, 0, 0, -32768, -32768))
        for field, value in ((ROOM, room + 1), (ROW, row), (FACING, 0 if facing else -1),
                             (X, x + NATIVE_X_ORIGIN), (TYPE, actor), (POSE, 158),
                             (SEQUENCE, sequence), (TOP, top), (BOTTOM, bottom),
                             (FRAME_DX, frame[0]), (FRAME_FLAGS, frame[1]),
                             (KID_ROOM, room + 1), (LEFT, left + NATIVE_X_ORIGIN),
                             (RIGHT, right + 1 + NATIVE_X_ORIGIN), (WIDTH, width),
                             (HEIGHT, height), (CAUTION, 0), (ANIMATION, animation),
                             (ALIVE, -1 if alive else 0), (ARMED, 1 if armed else 0)):
            machine.put_word(field, value)
        # 3:1ab0-1c3c fills the Kid room's eight neighbours (AdjustRoom 4:56e6).
        machine.call(3, 0x1ab0, stop=(3, 0x1c3c))
        machine.call(4, 0x2a7c)
        machine.call(4, 0x62b0)
        native = (tuple(machine.jumps), machine.word(X) - NATIVE_X_ORIGIN)
        services.update(machine.services)
        terrain = LevelMap(level)
        if environment == 1:
            terrain.desert = DesertState(gate=phase or 0)
        state = SequenceState(sequence, action=158, target_x=x, facing=int(facing),
                              actor_type=actor, level_kind=environment,
                              animation_state=animation)
        record = SimpleNamespace(offset_x=frame[0], aux=frame[1])
        result = terrain.enemy_collide(room, row, state, record, (left, top, right, bottom - 1),
                                       alive=alive, armed=armed)
        expected = ((), x) if result is None else ((result[1],), x + result[0])
        digest.update(struct.pack('>hh', native[0][0] if native[0] else -1, native[1]))
        totals[label] += 1
        responses[f'{label} {native[0][0] if native[0] else "none"}'] += 1
        if native != expected:
            key = (label, environment)
            mismatches[key] += 1
            examples.setdefault(key, dict(level=struct.unpack_from('>H', level, 0x218a)[0],
                                          room=room, row=row, x=x, facing=facing, frame=frame,
                                          phase=phase, actor=actor, animation=animation,
                                          alive=alive, armed=armed, sequence=sequence,
                                          height=height, width=width,
                                          column=machine.word(COLUMN), native=native,
                                          port=expected))

    for resource, entry in sorted(levels.items()):
        level = entry['data']
        environment = struct.unpack_from('>H', level, 0x2186)[0]
        rooms = struct.unpack_from('>H', level, 0x2180)[0]
        # Barrier sweep: the supporting cell or the one ahead is a barrier
        # kind; X across it in steps of 3, both facings, three FRAM dx/flags,
        # body widths/heights; every 11th case varies the preconditions.
        variants = ((1, True, True, 150, 2), (0, True, True, 150, 2), (5, True, True, 150, 4),
                    (1, False, True, 150, 2), (1, True, False, 150, 2), (1, True, True, 58, 2),
                    (1, True, True, 150, 11), (1, True, True, 64, 4), (1, True, True, 150, 5),
                    (1, True, True, 150, 6), (1, True, True, 216, 4))
        index = 0
        for room in range(rooms):
            for row in range(3):
                for column in range(10):
                    kind = struct.unpack_from('>H', level, room * 60 + (row * 10 + column) * 2)[0]
                    if kind not in BARRIER_KINDS:
                        continue
                    for x in range(column * 51 - 60, column * 51 + 112, 3):
                        for facing in (True, False):
                            animation, alive, armed, sequence, actor = (
                                variants[index // 11 % 11] if index % 11 == 10 else
                                variants[0][:4] + ((2, 4, 5)[index % 3],))
                            height, width = ((79, 21), (30, 21), (79, 45), (34, 13),
                                             (35, 29))[index % 5]
                            case('barrier', level, environment, room, row, x, facing,
                                 FRAMES[index % 3], actor=actor, animation=animation,
                                 alive=alive, armed=armed, sequence=sequence,
                                 height=height, width=width)
                            index += 1
        # Gate sweep: desert phases 0-20, elsewhere the low byte step 9.
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
                for x in range(column * 51 - 40, column * 51 + 92, 6):
                    for facing in (True, False):
                        height, width = ((79, 21), (30, 21), (79, 45))[index % 3]
                        case('gate', patched, environment, room, row, x, facing,
                             FRAMES[index % 3], phase, sequence=(150, 68)[index % 7 == 6],
                             height=height, width=width)
                        index += 1
        print(resource, environment, dict(totals), dict(mismatches), flush=True)
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(cases=dict(totals), responses=dict(sorted(responses.items())),
                mismatches={f'{label} env {env}': count for (label, env), count in mismatches.items()},
                examples={f'{label} env {env}': value for (label, env), value in examples.items()},
                services=dict(services),
                result_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['Drawing setup 3:0ac8 and GetCharEdges 4:5cbc: inert; their outputs'
                          ' (edges, width, height, clipped top/bottom) are fixtures',
                          'JumpSeq 6:0006: records the sequence; AnimChar 4:2c0c, LoadFrame'
                          ' 4:2a72: inert'],
                fixtures=['LEVL 2000-2013 as stored (gate sweep patches the phase: desert five'
                          ' low bits 0-20, elsewhere the low byte 0-252 step 9)',
                          'Opponent words: room (= the Kid room), row, facing, X, type 2/4/5/6/11,'
                          ' pose 158, selected sequence, animation state, ALIVE, armed,'
                          ' clipped top/bottom, FRAM dx/flags, edges, width, height;'
                          ' caution word 0; column from LoadFrame 4:2a7c'],
                exclusions=['The heads (types 7/8) and HeadEnemyCollide 7:0b6e',
                            'Opponents outside the Kid room (AdjustRoom by a5-0x4fc2)',
                            'The caution word a5-0x36bc set (type 3 for tile 2)',
                            'FrameAdv 2:6550-65da (which opponents reach the call)'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('cases', 'responses', 'mismatches',
                                                   'examples', 'services')}))


if __name__ == '__main__':
    main()
