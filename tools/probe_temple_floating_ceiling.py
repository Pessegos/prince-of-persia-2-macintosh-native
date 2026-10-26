"""Execute the floating ceiling helper4:50da and its real CheckBarr caller.

Original ReadCell, IsSpace, relative X adjustment and JumpSeq229 execute.
Only Resource Manager lookup is supplied (present/missing). Actor/body,
previous banks/row and empty MOB bank are fixtures; no AnimChar, frame/body
refresh, nonempty rocks, collision response or complete FrameAdv/gameplay.
"""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_collision_banks import NativeTempleCollisionBanks, banks_reference
from tools.probe_temple_collision_history import TABLES
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import COLD_CACHE, StandingCellReader
from tools.probe_temple_slide_rock_update import actor_word


SEQUENCE_HANDLE = 0xc0000


def ceiling_reference(actor, height, reader, *, available=True):
    if len(actor) != 62 or actor_word(actor, 8) != 0 or actor_word(actor, 2) not in (-1, 0):
        raise ValueError('Expected a full type0 Prince actor')
    result, events = bytearray(actor), []
    row = actor_word(actor, 14)
    top = signed_word(actor_word(actor, 6) - height)
    if row * 120 - 8 <= top:
        return dict(actor=bytes(result), events=events)
    tile = reader.read(actor_word(actor, 22), actor_word(actor, 12), row - 1)
    if tile in (0, 9, 27, 47, 49):
        return dict(actor=bytes(result), events=events)
    put_actor(result, 4, actor_word(actor, 4) + (6 if actor_word(actor, 2) == -1 else -6))
    put_actor(result, 18, 0)
    events.append(('resource', 229))
    if available:
        for offset, value in ((36, 0), (38, 229), (40, 229)):
            put_actor(result, offset, value)
    return dict(actor=bytes(result), events=events)


class NativeTempleFloatingCeiling(NativeTempleCollisionBanks):
    RANGES = dict(NativeTempleCollisionBanks.RANGES)
    RANGES[4] += ((0x50da, 0x5150),)
    RANGES[6] = ((0x0006, 0x0098),)

    def reset(self, level):
        super().reset(level)
        self.events, self.available = [], True

    def dispatch(self, cpu, address, size, user):
        if address == self.address(17, 0x330e):
            stack = cpu.reg_read(self.registers['a7'])
            resource, number = struct.unpack('>4sh', cpu.mem_read(stack + 4, 6))
            if (resource, number) != (b'SEQS', 229):
                raise AssertionError('Unexpected ceiling sequence resource')
            self.events.append(('resource', number))
            cpu.reg_write(self.registers['d0'], SEQUENCE_HANDLE if self.available else 0)
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])
            return
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    levels = prince['LEVL']
    machine = NativeTempleFloatingCeiling(parse_resource_fork(executable))
    sequence = struct.pack('>I', SEQUENCE_HANDLE + 4) + prince['SEQS'][229]['data']
    machine.cpu.mem_write(SEQUENCE_HANDLE, sequence)
    counts, outcomes, digest = Counter(), Counter(), hashlib.sha256()
    mob_guard = bytes((i * 7 + 3) & 255 for i in range(512))

    def check(level, actor, height, available, label, *, compose=False, floating=1, pattern=255):
        room = actor_word(actor, 22)
        machine.reset(level)
        machine.available = available
        machine.cpu.mem_write(machine.A5 - 0x5056, actor)
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(range(62)))
        machine.cpu.mem_write(machine.A5 - 0x448e, bytes(range(160)))
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', *COLD_CACHE))
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', 0xb0000))
        machine.cpu.mem_write(0xb0000, mob_guard)
        tables = {name: [room] * 10 if name.endswith('tags') else [pattern] * 10 for name in TABLES}
        for name, offset in TABLES.items():
            machine.cpu.mem_write(machine.A5 + offset, struct.pack('>10H', *tables[name]))
        for offset, value in ((-0x4fc2, room), (-0x4490, 0), (-0x357c, 71), (-0x357e, 1),
                              (-0x3580, 7), (-0x3582, 8), (-0x35fc, 73), (-0x481c, 79),
                              (-0x3578, 67), (-0x357a, 69), (-0x3564, 430),
                              (-0x3566, 475), (-0x3560, height), (-0x36bc, 0), (-0x4fa6, floating)):
            machine.put_word(offset, value)
        reader = StandingCellReader(level, room)
        before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        expected, rock_queries = dict(actor=actor, events=[]), []
        if compose:
            banks = banks_reference(actor, (430, 475), tables, reader, 1, height=height)
            rock_queries = banks['rock_queries']
            for name, offset in TABLES.items():
                struct.pack_into('>10H', before, len(machine.data) + offset, *banks['tables'][name])
            for offset, name in ((-0x357c, 'current'), (-0x357e, 'previous'), (-0x3580, 'first'),
                                 (-0x3582, 'last'), (-0x35fc, 'anchor'), (-0x481c, 'remainder'),
                                 (-0x3578, 'hit_low'), (-0x357a, 'hit_high')):
                struct.pack_into('>h', before, len(machine.data) + offset, banks[name])
            if floating and actor_word(actor, 16) == 4 and banks['hit_low'] == banks['hit_high'] == -1:
                expected = ceiling_reference(actor, height, reader, available=available)
        else:
            expected = ceiling_reference(actor, height, reader, available=available)
        machine.call(4, 0x4e34 if compose else 0x50da)
        before[len(machine.data) - 0x5056:len(machine.data) - 0x5056 + 62] = expected['actor']
        struct.pack_into('>6h', before, len(machine.data) - 0x34b0, *reader.cache)
        if reader.pointer_room is not None:
            r = reader.pointer_room
            struct.pack_into('>II', before, len(machine.data) - 0x4824,
                             machine.LEVEL + 0x780 + (r - 1) * 120,
                             machine.LEVEL + (r - 1) * 60)
        after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        if (after != before or machine.events != expected['events'] or machine.services
                or machine.reads != reader.requests or machine.rock_queries != rock_queries
                or machine.level_bytes(len(level)) != level
                or bytes(machine.cpu.mem_read(0xb0000, 512)) != mob_guard
                or bytes(machine.cpu.mem_read(SEQUENCE_HANDLE, len(sequence))) != sequence):
            raise AssertionError(dict(label=label, actor=actor.hex(), height=height,
                expected=expected, events=machine.events, reads=machine.reads,
                expected_reads=reader.requests, changed=[(hex(i - len(machine.data)), a, b)
                for i, (a, b) in enumerate(zip(before, after)) if a != b]))
        counts[label] += 1
        outcomes['sequence_requested' if expected['events'] else 'no_bump'] += 1
        digest.update(actor + expected['actor'] + struct.pack('>6h', *reader.cache))
        digest.update(json.dumps(expected['events']).encode('ascii'))

    for number in range(10, 14):
        level = levels[1999 + number]['data']
        maximum = struct.unpack_from('>H', level, 0x2180)[0]
        for room, cell, facing, delta in product(range(1, maximum + 1), range(30), (-1, 0), (-1, 0, 1)):
            row, column = divmod(cell, 10)
            actor = bytearray(actor_fixture(room, row, column, facing, 4))
            for offset, value in ((4, 229 + column * 51), (6, row * 120 - 8 + 74 + delta),
                                  (8, 0), (18, 5), (36, 7), (38, 2), (40, 2)):
                put_actor(actor, offset, value)
            check(level, bytes(actor), 74, True, 'declared_room_head_positions')
        for room, facing, floating, mode, source, available in product(range(1, maximum + 1),
                (-1, 0), (0, 1), (0, 4), (2, 70), (False, True)):
            actor = bytearray(actor_fixture(room, 1, 4, facing, mode))
            for offset, value in ((4, 460), (6, 185), (8, 0), (18, 5), (36, 7), (38, 2), (40, source)):
                put_actor(actor, offset, value)
            check(level, bytes(actor), 74, available, 'native_caller_controls',
                  compose=True, floating=floating)
    original = levels[2009]['data']
    for tile, height, delta, facing, available in product(range(50), (34, 74), (-1, 0, 1),
                                                        (-1, 0), (False, True)):
        level = bytearray(original)
        struct.pack_into('>H', level, 4 * 2, tile)
        actor = bytearray(actor_fixture(1, 1, 4, facing, 4))
        for offset, value in ((4, 460), (6, 112 + height + delta), (8, 0),
                              (18, 5), (36, 7), (38, 2), (40, 2)):
            put_actor(actor, offset, value)
        check(bytes(level), bytes(actor), height, available, 'tile_and_lookup_controls')
    for y, height, facing, available in product((-32768, -32760, 32767), (34, 74, 32767),
                                               (-1, 0), (False, True)):
        actor = bytearray(actor_fixture(1, 1, 4, facing, 4))
        for offset, value in ((4, 460), (6, y), (8, 0), (18, 5), (36, 7), (38, 2), (40, 2)):
            put_actor(actor, offset, value)
        check(original, bytes(actor), height, available, 'signed_head_controls')
    for source, floating, pattern, available in product((2, 70), (0, 1), (0, 255), (False, True)):
        level = bytearray(original)
        struct.pack_into('>H', level, 14 * 2, 4)
        struct.pack_into('>H', level, 0x780 + 14 * 4, 0)
        struct.pack_into('>H', level, 4 * 2, 1)
        actor = bytearray(actor_fixture(1, 1, 4, 0, 4))
        for offset, value in ((4, 460), (6, 185), (8, 0), (18, 5), (36, 7), (38, 2), (40, source)):
            put_actor(actor, offset, value)
        check(bytes(level), bytes(actor), 74, available, 'contact_suppression_controls',
              compose=True, floating=floating, pattern=pattern)
    return dict(comparisons=dict(counts), outcomes=dict(outcomes), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                outputs_sha256=digest.hexdigest(), supplied=['SEQS229 Resource Manager present/missing'],
                scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
