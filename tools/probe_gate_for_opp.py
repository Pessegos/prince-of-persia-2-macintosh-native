"""Execute the original CheckGateForOpp 4:5ffc against LevelMap.gate_for_opp.

FrameAdv 2:65fa calls CheckGateForOpp for every opponent after EnemyCollide.
With native ALIVE, the supporting cell (CurrentCell 4:35a6), the cell behind
(4:3a48) or the one ahead (4:39fc) must be a gate, not level eight's room 9
and not a type-12 actor, that the gate collision 4:5b0e blocks for the body.
The gate's barrier edges (GetLeftBarr/GetRightBarr 4:541a/547c, rebased to
the Kid room's left/right neighbour) must overlap the character edges; then
4:6202 pushes the body out by the nearer of the two barrier distances
(4:6562/6610), three pixels past the face (eleven for a skeleton).

Native: everything above with ReadCell, GetUndefineCellId, GetBarrCode,
AdjustRoom, the neighbour words from 3:1ab0-1c3c, AddCharX and the column
word from LoadFrame's 4:2a7c. Supplied: nothing; the character edges, width,
height and clipped top/bottom are fixtures (GetCharEdges 4:5cbc output,
which 4:5ffc reads but does not call).
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
from tools.probe_enemy_collide import ALIVE, WIDTH, NativeEnemyCollide
from tools.probe_gate_barriers import CAUTION, HEIGHT, LEFT, RIGHT
from tools.probe_prince_turn import (BOTTOM, FACING, FRAME_DX, FRAME_FLAGS, FRAMES, KID_ROOM,
                                     POSE, ROOM, ROW, SEQUENCE, TOP, TYPE, X, gate_cells)


class NativeGateForOpp(NativeEnemyCollide):
    RANGES = {segment: tuple(spans) for segment, spans in NativeEnemyCollide.RANGES.items()}
    RANGES[4] = RANGES[4] + ((0x5ffc, 0x60e2), (0x6202, 0x62ae), (0x541a, 0x546a),
                             (0x547c, 0x54c8))


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    machine = NativeGateForOpp(parse_resource_fork(raw))
    levels = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL']
    digest, totals, pushed, mismatches = hashlib.sha256(), Counter(), Counter(), Counter()
    examples, services = {}, Counter()

    def case(label, level, environment, room, row, x, facing, frame, phase=None, actor=2,
             alive=True, sequence=150, height=79, width=21):
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
                             (HEIGHT, height), (CAUTION, 0), (ALIVE, -1 if alive else 0)):
            machine.put_word(field, value)
        machine.call(3, 0x1ab0, stop=(3, 0x1c3c))
        machine.call(4, 0x2a7c)
        machine.call(4, 0x5ffc)
        native = machine.word(X) - NATIVE_X_ORIGIN
        services.update(machine.services)
        terrain = LevelMap(level)
        if environment == 1:
            terrain.desert = DesertState(gate=phase or 0)
        state = SequenceState(sequence, action=158, target_x=x, facing=int(facing),
                              actor_type=actor, level_kind=environment)
        record = SimpleNamespace(offset_x=frame[0], aux=frame[1])
        push = terrain.gate_for_opp(room, row, state, record, (left, top, right, bottom - 1),
                                    alive=alive)
        expected = x + (push or 0)
        digest.update(struct.pack('>h', native - x))
        totals[label] += 1
        pushed[label] += native != x
        if native != expected:
            key = (label, environment)
            mismatches[key] += 1
            if len(examples.setdefault(key, [])) < 4:
                examples[key].append(dict(level=struct.unpack_from('>H', level, 0x218a)[0],
                                          room=room, row=row, x=x, facing=facing, frame=frame,
                                          phase=phase, actor=actor, alive=alive,
                                          sequence=sequence, height=height, width=width,
                                          native=native, port=expected))

    for resource, entry in sorted(levels.items()):
        level = entry['data']
        environment = struct.unpack_from('>H', level, 0x2186)[0]
        rooms = struct.unpack_from('>H', level, 0x2180)[0]
        # Gate sweep: X across every gate cell and its neighbours, both
        # facings, FRAM fixtures, bodies, types 2/4/12, ALIVE; the phase
        # (desert five low bits 0-20, elsewhere the low byte step 9).
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
                for x in range(column * 51 - 70, column * 51 + 122, 5):
                    for facing in (True, False):
                        height, width = ((79, 21), (30, 21), (79, 45), (57, 13))[index % 4]
                        actor = (2, 4, 2, 4, 12)[index % 5]
                        case('gate', patched, environment, room, row, x, facing,
                             FRAMES[index % 3], phase, actor=actor, alive=index % 13 != 12,
                             sequence=(150, 68)[index % 7 == 6], height=height, width=width)
                        index += 1
        # Room-edge sweep: every room and row near both edges, where the
        # cells behind or ahead come from a neighbour (or a missing link).
        for room in range(rooms):
            for row in range(3):
                for x in (-60, -40, -20, -5, 5, 20, 480, 495, 505, 520, 540, 560):
                    for facing in (True, False):
                        case('edge', level, environment, room, row, x, facing, FRAMES[x % 3],
                             0, height=79, width=21)
        print(resource, environment, dict(totals), dict(mismatches), flush=True)
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(cases=dict(totals), pushed=dict(pushed),
                mismatches={f'{label} env {env}': count for (label, env), count in mismatches.items()},
                examples={f'{label} env {env}': value for (label, env), value in examples.items()},
                services=dict(services),
                result_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['None; the character edges, width, height and clipped top/bottom are'
                          ' fixtures (GetCharEdges 4:5cbc output)'],
                fixtures=['LEVL 2000-2013 as stored (gate sweep patches the phase: desert five'
                          ' low bits 0-20, elsewhere the low byte 0-252 step 9)',
                          'Opponent words: room (= the Kid room), row, facing, X, type 2/4/12,'
                          ' pose 158, selected sequence 150/68, ALIVE, clipped top/bottom, FRAM'
                          ' dx/flags, edges, width, height; caution word 0'],
                exclusions=['Opponents outside the Kid room',
                            'FrameAdv 2:6550-65da (which opponents reach the call)'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('cases', 'pushed', 'mismatches', 'examples',
                                                   'services')}))


if __name__ == '__main__':
    main()
