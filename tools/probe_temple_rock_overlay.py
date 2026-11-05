"""Run native CheckBarr and CheckCollide1 with a real sliding rock in the bank.

Two connected frames from cold banks at every tile-25 cell of levels 10-13:
GetSlideRockOnRoomRow, GetSlideRockDetData, GetSlideRockBarrDist, the three
sweeps, history and the contact scan all execute natively. Supplied: the
working actor, body edges/height, MOB records and the rock's X for each
frame. Collide 4:5738 is a recorded no-op boundary. Float timer 0 excludes
4:50da. Out of scope: Collide's response, ShapeBounds, ATMSlideRock's own
motion and FrameAdv. Faces whose history transfer leaves the ten-word banks
are counted apart: they are native memory quirks, not reference cases.
"""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_collision_banks import banks_reference, column_reference
from tools.probe_temple_collision_decision import (NativeTempleCollisionDecision,
                                                   decision_reference)
from tools.probe_temple_collision_history import TABLES
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_distance import NEIGHBOR_SLOTS
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import COLD_CACHE, StandingCellReader

BANK = 0xb0000
HALF = 12


def fixture(room, row, native, facing, armed, velocity, mode=0, sequence_mode=0):
    actor = bytearray(actor_fixture(room, row, column_reference(native)[0], facing, mode))
    for offset, value in ((4, native), (6, row * 120 + 106), (8, 0), (10, 15), (18, velocity),
                          (26, armed), (28, -1), (30, 3), (40, 2), (42, 20), (46, 94),
                          (52, sequence_mode)):
        put_actor(actor, offset, value)
    return bytes(actor)


def rock_cells(levels):
    for number in range(10, 14):
        level = levels[1999 + number]['data']
        rooms = struct.unpack_from('>H', level, 0x2180)[0]
        for index in range(rooms * 30):
            if struct.unpack_from('>H', level, index * 2)[0] == 25:
                room, cell = divmod(index, 30)
                yield number, level, room + 1, cell // 10, cell % 10


def run_probe(source, *, x_step=17, offsets=range(-27, 28, 9)):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    levels = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL']
    machine = NativeTempleCollisionDecision(parse_resource_fork(executable))
    counts, outcomes, digest = Counter(), Counter(), hashlib.sha256()

    def prepare(level, room, row):
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(range(62)))
        machine.cpu.mem_write(machine.A5 - 0x448e, bytes(range(160)))
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', *COLD_CACHE))
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', BANK))
        machine.put_word(-0x4490, 1)
        for offset in NEIGHBOR_SLOTS:
            machine.put_word(offset, 0)
        for name, offset in TABLES.items():
            machine.cpu.mem_write(machine.A5 + offset, struct.pack('>10H', *(
                [65535] * 10 if name.endswith('tags') else [0] * 10)))
        for offset, value in ((-0x4fc2, room), (-0x357c, row), (-0x357e, row),
                              (-0x3580, 7), (-0x3582, 8), (-0x35fc, 73), (-0x481c, 79),
                              (-0x3578, 0), (-0x357a, 0), (-0x3560, 74), (-0x36bc, 0),
                              (-0x4fa6, 0)):
            machine.put_word(offset, value)

    def frame(actor, edges, mob, reader, state):
        """One native CheckBarr and CheckCollide1 against the references."""
        machine.cpu.mem_write(machine.A5 - 0x5056, actor)
        machine.cpu.mem_write(BANK, struct.pack('>8h', *mob))
        machine.put_word(-0x3564, edges[0])
        machine.put_word(-0x3566, edges[1])
        before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        banks = banks_reference(actor, edges, state['tables'], reader, state['previous'],
                                current=state['current'], first=state['first'],
                                last=state['last'], anchor=state['anchor'],
                                remainder=state['remainder'], mobs=(mob,))
        decision = decision_reference(actor, edges, banks['tables']['current_tags'],
                                      banks['hit_low'], banks['hit_high'], reader,
                                      anchor=banks['anchor'], mobs=(mob,))
        machine.responses.clear()
        machine.services.clear()
        machine.call(4, 0x4e34)
        machine.call(4, 0x54da)
        for name, offset in TABLES.items():
            struct.pack_into('>10H', before, len(machine.data) + offset, *banks['tables'][name])
        for offset, name in ((-0x357c, 'current'), (-0x357e, 'previous'), (-0x3580, 'first'),
                             (-0x3582, 'last'), (-0x3578, 'hit_low'), (-0x357a, 'hit_high')):
            struct.pack_into('>h', before, len(machine.data) + offset, banks[name])
        struct.pack_into('>h', before, len(machine.data) - 0x481c,
                         decision.get('remainder', banks['remainder']))
        struct.pack_into('>h', before, len(machine.data) - 0x35fc, decision['anchor'])
        struct.pack_into('>6h', before, len(machine.data) - 0x34b0, *reader.cache)
        if reader.pointer_room is not None:
            r = reader.pointer_room
            struct.pack_into('>II', before, len(machine.data) - 0x4824,
                             machine.LEVEL + 0x780 + (r - 1) * 120,
                             machine.LEVEL + (r - 1) * 60)
        after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        if (after != before or machine.responses != decision['events']
                or machine.reads != reader.requests
                or bytes(machine.cpu.mem_read(BANK, 16)) != struct.pack('>8h', *mob)):
            raise AssertionError(dict(actor=actor.hex(), edges=edges, mob=mob, banks=banks,
                                      decision=decision, responses=machine.responses,
                                      reads=machine.reads[-12:], expected=reader.requests[-12:],
                                      changed=[(hex(i - len(machine.data)), a, b)
                                               for i, (a, b) in enumerate(zip(before, after))
                                               if a != b]))
        state.update({key: banks[key] for key in ('tables', 'previous', 'current', 'first', 'last')})
        state.update(anchor=decision['anchor'], remainder=decision.get('remainder', banks['remainder']))
        digest.update(actor + struct.pack('>8h', *mob))
        digest.update(json.dumps([banks['hit_low'], banks['hit_high'], decision['events']]).encode())
        return decision['events']

    def trace(level, room, row, mobs, frames, facing, armed, label, *, mode=0, sequence_mode=0):
        prepare(level, room, row)
        reader = StandingCellReader(level, room)
        state = dict(tables={name: [65535] * 10 if name.endswith('tags') else [0] * 10
                             for name in TABLES},
                     previous=row, current=row, first=7, last=8, anchor=73, remainder=79)
        try:
            for index, (native, mob) in enumerate(zip(frames, mobs)):
                actor = fixture(room, row, native, facing, armed, frames[1] - frames[0],
                                mode, sequence_mode)
                events = frame(actor, (native - HALF, native + HALF + 1), mob, reader, state)
                if index:
                    outcomes['no_response' if not events else
                             'low_response' if events[0][2] == -1 else 'high_response'] += 1
        except ValueError:
            counts['outside_bank_domain'] += 1
            return
        counts[label] += 1

    for _number, level, room, row, column in rock_cells(levels):
        start = column * 51
        for x, control, step, offset, delta, facing, armed in product(
                range(start, 11, -x_step), (2, 100), (0, 2), offsets, (-5, 0, 5),
                (-1, 0), (0, 1)):
            for face in (x + 218, x + 279):
                anchor = face + offset
                mobs = ((x + step, 236, room, 0, control, 6, row, start),
                        (x, 236, room, 0, control, 6, row, start))
                trace(level, room, row, mobs, (anchor, anchor + delta), facing, armed,
                      'two_frame_traces')
    # Other rows, the pinned sequence mode and animation state 7 are controls.
    _number, level, room, row, column = next(rock_cells(levels))
    x = column * 51 - 40
    for rock_row, mode, sequence_mode in product((0, 1, 2), (0, 4, 7), (0, 4)):
        for offset in range(-30, 31, 6):
            mob = (x, 236, room, 0, 2, 6, rock_row, x)
            anchor = x + 218 + offset
            trace(level, room, row, (mob, mob), (anchor, anchor + 5), 0, 0,
                  'row_and_mode_controls', mode=mode, sequence_mode=sequence_mode)
    return dict(comparisons=dict(counts), outcomes=dict(outcomes), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                outputs_sha256=digest.hexdigest(),
                supplied=['Collide4:5738 recorded no-op response'], scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--x-step', type=int, default=17)
    parser.add_argument('--offset-step', type=int, default=9)
    args = parser.parse_args()
    report = run_probe(args.source, x_step=args.x_step,
                       offsets=range(-27, 28, args.offset_step))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
