"""Execute the original MobDart 8:2f98 against Darts.advance.

One update of a cavern dart: the viewport rebase from the Kid room's left
or lower neighbour (else retired, with the impact sound 67 when that room
link is missing), the row above when Y reaches row*120+5 (IsSpace 3:4eb2),
and, crossing a column, IsWall 3:4ef2 or a gate that 4:5b0e blocks (8:30fc).

Native: MobDart, ReadCell 4:27ee (room links, GetUndefineCellId), IsSpace,
IsWall, 4:5b0e and the neighbour words from 3:1ab0-1c3c. Supplied: AddSound
5:4d84 (recorded). The dart's mob words and the body that 4:5b0e reads
(clipped top/bottom, type, selected sequence) are fixtures.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from pop2.darts import Dart, Darts
from pop2.mac_resources import parse_resource_fork
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap
from tools.probe_prince_turn import (BOTTOM, KID_ROOM, SEQUENCE, TOP, TYPE, NativePrinceTurn,
                                     gate_cells)


class NativeMobDart(NativePrinceTurn):
    RANGES = {**NativePrinceTurn.RANGES,
              3: NativePrinceTurn.RANGES[3] + ((0x1ab0, 0x1c3c),),
              8: ((0x2f98, 0x312a),)}
    SUPPLIED = {(5, 0x4d84): 'sound'}

    def dispatch(self, cpu, address, size, user):
        if address == self.address(5, 0x4d84):
            stack = cpu.reg_read(self.registers['a7'])
            self.sounds.append(struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0])
        super().dispatch(cpu, address, size, user)


MOB_X, MOB_Y, MOB_ROOM, MOB_DY, MOB_DX, MOB_ROW = -0x44a6, -0x44a4, -0x44a2, -0x44a0, -0x449e, -0x449a


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    machine = NativeMobDart(parse_resource_fork(raw))
    levels = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL']
    digest, totals, outcomes, mismatches = hashlib.sha256(), Counter(), Counter(), Counter()
    examples = {}

    def case(label, level, view, room, x, y, row, dy=-19, top=150, height=79, sequence=0):
        machine.reset(level)
        machine.sounds = []
        for field, value in ((KID_ROOM, view + 1), (TYPE, 0), (SEQUENCE, sequence), (TOP, top),
                             (BOTTOM, top + height), (MOB_X, x), (MOB_Y, y),
                             (MOB_ROOM, room + 1), (MOB_DY, dy), (MOB_DX, 27), (MOB_ROW, row)):
            machine.put_word(field, value)
        machine.call(3, 0x1ab0, stop=(3, 0x1c3c))
        machine.call(8, 0x2f98)
        native = (machine.word(MOB_X), machine.word(MOB_Y), machine.word(MOB_ROOM) - 1,
                  machine.word(MOB_ROW), machine.word(MOB_DY), tuple(machine.sounds))
        darts = Darts([Dart(room, x, y, row, 27, dy)])
        dart = darts.projectiles[0]
        cues = darts.advance(LevelMap(level), view, (0, top, 0, top + height - 1),
                             SequenceState(sequence, actor_type=0, level_kind=3))
        port = (dart.x, dart.y, dart.room, dart.row, dart.dy, cues)
        digest.update(struct.pack('>5h', *native[:5]) + bytes(native[5]))
        totals[label] += 1
        outcomes[f'{label} dy {native[4]} sounds {len(native[5])}'] += 1
        if native != port:
            mismatches[label] += 1
            examples.setdefault(label, dict(level=struct.unpack_from('>H', level, 0x218a)[0],
                                            view=view, room=room, x=x, y=y, row=row, dy=dy,
                                            top=top, height=height, sequence=sequence,
                                            native=native, port=port))

    for resource, entry in sorted(levels.items()):
        level = entry['data']
        environment = struct.unpack_from('>H', level, 0x2186)[0]
        if environment != 3:
            continue  # TriggerDart's tile 33 occurs in the caverns only.
        rooms = struct.unpack_from('>H', level, 0x2180)[0]
        # Terrain sweep: every room, X 0..530, every row with Y at its
        # bottom, middle and just above row*120+5; the dart in the view room
        # or in its left/lower neighbour; the retiring velocities -3/-1.
        index = 0
        for view in range(rooms):
            links = struct.unpack_from('>4H', level, 0x2080 + view * 8)
            homes = [view] + [link - 1 for link in (links[0], links[3]) if link]
            for x in range(0, 531, 5):
                for row in range(3):
                    for y in (row * 120 + 95, row * 120 + 60, row * 120 + 24, row * 120 + 10):
                        room = homes[index % len(homes)]
                        dy = (-19, -19, -19, -19, -19, -19, -19, -3, -1)[index % 9]
                        case('terrain', level, view, room, x, y, row, dy)
                        index += 1
        # Gate sweep: the dart crosses into a gate's column; gate positions
        # and the body heights the gate collision compares.
        for room, cell in gate_cells(level, rooms):
            row, column = divmod(cell, 10)
            offset = 0x780 + room * 120 + cell * 4
            original = struct.unpack_from('>H', level, offset)[0]
            for phase in range(0, 256, 9):
                patched = bytearray(level)
                struct.pack_into('>H', patched, offset, (original & 0xff00) | phase)
                patched = bytes(patched)
                for x in range(column * 51 - 27, column * 51, 3):
                    for top, height, sequence in ((150, 79, 0), (100, 120, 0), (200, 30, 0),
                                                  (150, 79, 68)):
                        case('gate', patched, room, room, x, row * 120 + 60, row, top=top,
                             height=height, sequence=sequence)
        print(resource, environment, dict(totals), dict(mismatches), flush=True)
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(cases=dict(totals), outcomes=dict(sorted(outcomes.items())),
                mismatches=dict(mismatches), examples=examples,
                result_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['AddSound 5:4d84: recorded'],
                fixtures=['Cavern LEVL 2002-2004 as stored (gate sweep patches the low byte'
                          ' 0-252 step 9)',
                          'Mob words: X, Y, room, row, dx 27, dy -19/-3/-1; the Kid room is the'
                          ' view room; the dart in it or in its left/lower neighbour',
                          'Body read by 4:5b0e: type 0, sequence 0/68, clipped top/bottom'],
                exclusions=['Which character copy 4:5b0e sees when the mob animator calls'
                            ' MobDart (no shipped dart trajectory reaches a gate)',
                            'The mob animator, CheckDartHit 8:2e82 and the drawing'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('cases', 'outcomes', 'mismatches', 'examples')}))


if __name__ == '__main__':
    main()
