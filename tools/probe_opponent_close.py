"""Execute the original OpponentClose 4:13a4 against skeleton.opponent_path_clear.

The opponent proximity check 4:14c6 (FrameAdv 2:624a) asks 4:13a4 whether a
dormant opponent may wake: same row, within the given column range of the
Prince, and every cell from the Prince's column to the opponent's IsFloor
3:4da6, not IsImpassable 3:4de2 (type 10 excepted) and not a gate that the
collision 4:5b0e blocks (4:1486) for the opponent's stored body.

Native: 4:13a4, ReadCell 4:27ee (room links, GetUndefineCellId), IsFloor/
IsSpace/IsWall/IsImpassable and 4:5b0e. Supplied: the bank lookup 6:3642
returns a record whose shake timer (+0x1e) is zero, so IsExitChasingSkel
4:17aa is not reached. The opponent's words are fixtures.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from pop2.desert_state import DesertState
from pop2.mac_resources import parse_resource_fork
from pop2.sequence_runtime import SequenceState
from pop2.skeleton import opponent_path_clear
from pop2.terrain import LevelMap
from tools.probe_prince_turn import (BOTTOM, COLUMN, ROOM, ROW, SEQUENCE, TOP, TYPE,
                                     NativePrinceTurn, gate_cells)


class NativeOpponentClose(NativePrinceTurn):
    RANGES = {**NativePrinceTurn.RANGES,
              3: NativePrinceTurn.RANGES[3] + ((0x4de2, 0x4e20),),
              4: NativePrinceTurn.RANGES[4] + ((0x13a4, 0x14b2),)}
    SUPPLIED = {}
    RECORD = 0xc0000

    def dispatch(self, cpu, address, size, user):
        if address == self.address(6, 0x3642):
            self.services['bank_record'] += 1
            cpu.mem_write(self.RECORD, bytes(64))
            cpu.reg_write(self.registers['d0'], self.RECORD)
            stack = cpu.reg_read(self.registers['a7'])
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])
            return
        super().dispatch(cpu, address, size, user)


ALIVE, SPECIAL, SHADOW = -0x503a, -0x5022, -0x50ca


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    machine = NativeOpponentClose(parse_resource_fork(raw))
    levels = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL']
    digest, totals, clear, mismatches = hashlib.sha256(), Counter(), Counter(), Counter()
    examples, services = {}, Counter()

    def case(label, level, environment, room, row, own, other, reach, actor=4, sequence=88,
             top=150, height=57, phase=None):
        machine.reset(level)
        machine.jumps = []
        for field, value in ((ROOM, room + 1), (ROW, row), (COLUMN, own), (TYPE, actor),
                             (SEQUENCE, sequence), (TOP, top), (BOTTOM, top + height),
                             (ALIVE, 0), (SPECIAL, 0), (SHADOW, 0)):
            machine.put_word(field, value)
        native = machine.call(4, 0x13a4, (0, other, row, reach))
        services.update(machine.services)
        terrain = LevelMap(level)
        if environment == 1:
            terrain.desert = DesertState(gate=phase or 0)
        state = SequenceState(sequence, actor_type=actor, level_kind=environment)
        port = int(abs(own - other) <= reach and opponent_path_clear(
            terrain, room, row, other, own, (0, top, 0, top + height - 1), state))
        digest.update(struct.pack('>B', native))
        totals[label] += 1
        clear[label] += native
        if native != port:
            key = (label, environment)
            mismatches[key] += 1
            examples.setdefault(key, dict(level=struct.unpack_from('>H', level, 0x218a)[0],
                                          room=room, row=row, own=own, other=other,
                                          reach=reach, actor=actor, sequence=sequence,
                                          top=top, height=height, phase=phase,
                                          native=native, port=port))

    for resource, entry in sorted(levels.items()):
        level = entry['data']
        environment = struct.unpack_from('>H', level, 0x2186)[0]
        rooms = struct.unpack_from('>H', level, 0x2180)[0]
        # Terrain sweep: every room and row, the opponent's column -1..10 and
        # the Prince's -2..11; reaches 4/5/8, types 4 and 10.
        index = 0
        for room in range(rooms):
            for row in range(3):
                for own in range(-1, 11):
                    for other in range(-2, 12):
                        actor = (4, 4, 10)[index % 3]
                        case('terrain', level, environment, room, row, own, other,
                             (4, 5, 8)[index // 3 % 3], actor=actor)
                        index += 1
        # Gate sweep: a gate between the two; phases and body heights.
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
                for own, other in ((column, column - 2), (column + 2, column), (column, column),
                                   (column - 1, column + 1)):
                    for top, height, sequence, actor in ((150, 57, 88, 4), (100, 120, 88, 4),
                                                         (200, 30, 88, 4), (150, 57, 68, 4),
                                                         (150, 79, 106, 10)):
                        case('gate', patched, environment, room, row, own, other, 8, actor=actor,
                             sequence=sequence, top=top, height=height, phase=phase)
        print(resource, environment, dict(totals), dict(mismatches), flush=True)
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(cases=dict(totals), clear=dict(clear),
                mismatches={f'{label} env {env}': count for (label, env), count in mismatches.items()},
                examples={f'{label} env {env}': value for (label, env), value in examples.items()},
                services=dict(services),
                result_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['Bank lookup 6:3642: a zeroed record (shake timer +0x1e = 0)'],
                fixtures=['LEVL 2000-2013 as stored (gate sweep patches the phase: desert five'
                          ' low bits 0-20, elsewhere the low byte 0-252 step 9)',
                          'Opponent words: room, row, column, type 4/10, selected sequence,'
                          ' clipped top/bottom; ALIVE 0, a5-0x5022 0, a5-0x50ca 0'],
                exclusions=['The shake-timer branch (IsExitChasingSkel 4:17aa)',
                            'The 4:14c6 caller (reach selection, the wake itself)',
                            'The ALIVE / a5-0x5022 / a5-0x50ca / row preconditions'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('cases', 'clear', 'mismatches', 'examples',
                                                   'services')}))


if __name__ == '__main__':
    main()
