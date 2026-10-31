"""Execute the original opponent draw 4:4996 + DoEngarde 6:1e78 against the port.

GenCtrl's opponent branch 4:4996 acts at pose 166 on a draw request
(a5-0x3482 < 0): with a turn request (a5-0x3488 >= 0) it turns instead
(SEQS 80); otherwise, when the cell behind (GetCellBehind 4:3a48) is not
IsAdvancableId 6:5eca, AddCharX(8) moves the body forward, and DoEngarde
6:1e78 arms it, reserves eighteen pixels with GetBarrDistances 4:5eae
(0 < d < 18: AddCharX(d - 18)) and selects SEQS 90. The port is
`CombatEncounter._draw_guard_sword`.

Native: 4:4996, 4:3a48, ReadCell, IsAdvancableId with IsWall/IsImpassable/
IsSpace, AddCharX, the input clear 4:3e3a, DoEngarde, the whole 4:5eae (as in
probe_kid_engarde) and the column word 4:2a7c. Supplied: JumpSeq 6:0006
(recorded); the character edges, width, height and clipped top/bottom are
fixtures computed for the body before the call.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.combat import CombatEncounter
from pop2.coordinates import NATIVE_X_ORIGIN
from pop2.desert_state import DesertState
from pop2.mac_resources import parse_resource_fork
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap
from tools.probe_gate_barriers import CAUTION, HEIGHT, LEFT, NEIGHBOR_SLOTS, RIGHT
from tools.probe_kid_engarde import NativeKidEngarde
from tools.probe_prince_turn import (BOTTOM, FACING, FRAME_DX, FRAME_FLAGS, FRAMES, KID_ROOM,
                                     POSE, ROOM, ROW, SEQUENCE, TOP, TYPE, X, gate_cells)

DRAW, TURN, ARMED = -0x3482, -0x3488, -0x503c


class NativeOppEngarde(NativeKidEngarde):
    RANGES = {segment: tuple(spans) for segment, spans in NativeKidEngarde.RANGES.items()}
    RANGES[3] = RANGES[3] + ((0x4de2, 0x4e20),)
    RANGES[4] = RANGES[4] + ((0x4996, 0x49ee), (0x3e3a, 0x3e4e))
    RANGES[6] = RANGES[6] + ((0x1e78, 0x1ef4), (0x5eca, 0x5f5c))
    SUPPLIED = {}

    def dispatch(self, cpu, address, size, user):
        if divmod(address - self.CODE_BASE, 0x10000) == (6, 0x0006):
            stack = cpu.reg_read(self.registers['a7'])
            self.jumps.append(struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0])
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])
            return
        super().dispatch(cpu, address, size, user)


class PortEncounter:
    _draw_guard_sword = CombatEncounter._draw_guard_sword
    _guard_tile = CombatEncounter._guard_tile
    _supporting_column = CombatEncounter._supporting_column

    def __init__(self, level, terrain, record, bounds):
        self.level, self.terrain = level, terrain
        self.guard_art = SimpleNamespace(frames={i: record for i in range(512)},
                                         bounds=lambda _state, _floor: bounds)
        self.player_frames = None


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    machine = NativeOppEngarde(parse_resource_fork(raw))
    levels = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL']
    digest, totals, moved, mismatches = hashlib.sha256(), Counter(), Counter(), Counter()
    examples, services = {}, Counter()

    def case(label, level, environment, room, row, x, facing, frame, phase=None, actor=2,
             turn=False, height=79, width=10):
        top, bottom = 148, 148 + height
        left, right = x - width, x + width
        machine.reset(level)
        machine.jumps = []
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', 0, 0, 0, 0, -32768, -32768))
        for field, value in ((ROOM, room + 1), (ROW, row), (FACING, 0 if facing else -1),
                             (X, x + NATIVE_X_ORIGIN), (TYPE, actor), (POSE, 166),
                             (SEQUENCE, 77), (TOP, top), (BOTTOM, bottom),
                             (FRAME_DX, frame[0]), (FRAME_FLAGS, frame[1]),
                             (KID_ROOM, room + 1), (LEFT, left + NATIVE_X_ORIGIN),
                             (RIGHT, right + 1 + NATIVE_X_ORIGIN), (HEIGHT, height),
                             (CAUTION, 0), (DRAW, -1), (TURN, 0 if turn else -1), (ARMED, 0)):
            machine.put_word(field, value)
        for slot in NEIGHBOR_SLOTS:
            machine.put_word(slot, 0)
        machine.call(4, 0x2a7c)
        machine.call(4, 0x4996)
        native = (tuple(machine.jumps), machine.word(X) - NATIVE_X_ORIGIN, machine.word(ARMED))
        services.update(machine.services)
        if turn:
            expected = ((80,), x, 0)
        else:
            terrain = LevelMap(level)
            if environment == 1:
                terrain.desert = DesertState(gate=phase or 0)
            state = SequenceState(77, action=166, target_x=x, current_x=x, facing=int(facing),
                                  actor_type=actor, level_kind=environment)
            guard = SimpleNamespace(state=state, room=room, row=row, sword_drawn=False,
                                    selected_sequence=None)
            encounter = PortEncounter(level, terrain, SimpleNamespace(offset_x=frame[0],
                                                                      aux=frame[1]),
                                      (left, top, right, bottom - 1))
            encounter._draw_guard_sword(guard)
            expected = ((guard.selected_sequence,), state.target_x, int(guard.sword_drawn))
        digest.update(struct.pack('>hhh', native[0][0] if native[0] else -1, native[1] - x,
                                  native[2]))
        totals[label] += 1
        moved[label] += native[1] != x
        if native != expected:
            key = (label, environment)
            mismatches[key] += 1
            if len(examples.setdefault(key, [])) < 4:
                examples[key].append(dict(level=struct.unpack_from('>H', level, 0x218a)[0],
                                          room=room, row=row, x=x, facing=facing, frame=frame,
                                          phase=phase, actor=actor, turn=turn, height=height,
                                          native=native, port=expected))

    for resource, entry in sorted(levels.items()):
        level = entry['data']
        environment = struct.unpack_from('>H', level, 0x2186)[0]
        rooms = struct.unpack_from('>H', level, 0x2180)[0]
        index = 0
        # Terrain sweep: every room and row, X across the room in steps of
        # 7, both facings, three FRAM fixtures, types 2/4; every 17th case
        # carries a turn request.
        for room in range(rooms):
            for row in range(3):
                for x in range(-20, 530, 7):
                    for facing in (True, False):
                        case('terrain', level, environment, room, row, x, facing,
                             FRAMES[index % 3], actor=(2, 4)[index // 3 % 2],
                             turn=index % 17 == 16, height=(79, 57)[index // 6 % 2])
                        index += 1
        # Gate sweep: a gate behind or ahead across phases.
        phases = range(21) if environment == 1 else range(0, 256, 13)
        for room, cell in gate_cells(level, rooms):
            row, column = divmod(cell, 10)
            offset = 0x780 + room * 120 + cell * 4
            original = struct.unpack_from('>H', level, offset)[0]
            for phase in phases:
                patched = bytearray(level)
                mask = 0xffe0 if environment == 1 else 0xff00
                struct.pack_into('>H', patched, offset, (original & mask) | phase)
                patched = bytes(patched)
                for x in range(column * 51 - 80, column * 51 + 60, 6):
                    for facing in (True, False):
                        case('gate', patched, environment, room, row, x, facing,
                             FRAMES[index % 3], phase, height=(79, 30)[index % 2])
                        index += 1
        print(resource, environment, dict(totals), dict(mismatches), flush=True)
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(cases=dict(totals), moved=dict(moved),
                mismatches={f'{label} env {env}': count for (label, env), count in mismatches.items()},
                examples={f'{label} env {env}': value for (label, env), value in examples.items()},
                services=dict(services),
                result_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['JumpSeq 6:0006: recorded, no effect'],
                fixtures=['LEVL 2000-2013 as stored (gate sweep patches the phase: desert five'
                          ' low bits 0-20, elsewhere the low byte step 13)',
                          'Opponent words: room (= the Kid room), row, facing, X, type 2/4, pose'
                          ' 166, selected 77, clipped top/bottom, FRAM dx/flags, edges X +/- 10,'
                          ' height; draw request -1, turn request -1 (0 every 17th case);'
                          ' caution word 0; neighbour slots 0'],
                exclusions=['The decision to request the draw (AutoCtrl 4:04fc)',
                            'Edges recomputed after AddCharX(8): native keeps the fixtures'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('cases', 'moved', 'mismatches', 'examples',
                                                   'services')}))


if __name__ == '__main__':
    main()
