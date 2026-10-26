"""Execute full temple CheckBarr with native history, limits and three row sweeps.

Body edges/height, working actor and previous-frame banks/row are fixtures.
The real rock queries/overlays execute against an explicitly empty MOB bank.
Float timer0 excludes the separate ceiling helper4:50da. No endpoint stubs,
ShapeBounds, nonempty rocks, Collide response, gate caller or outer FrameAdv.
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
from tools.probe_temple_collision_history import TABLES, history_reference
from tools.probe_temple_collision_sweep import NativeTempleCollisionSweep, sweep_reference
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import COLD_CACHE, StandingCellReader
from tools.probe_temple_slide_rock_update import actor_word


def column_reference(native_x):
    argument = signed_word(native_x - 22)
    dividend = argument - 4 + (65536 if 0 <= argument < 4 else 0)
    quotient = abs(dividend) // 51 * (-1 if dividend < 0 else 1)
    return quotient - 4 - int(argument < 0), dividend - quotient * 51


def banks_reference(actor, edges, tables, reader, previous, *, current=71, first=7,
                    last=8, anchor=73, remainder=79, height=74):
    if len(actor) != 62 or len(edges) != 2 or not 0 <= actor_word(actor, 14) <= 2:
        raise ValueError('Outside the bounded temple CheckBarr domain')
    output = dict(tables={name: list(bank) for name, bank in tables.items()}, current=current,
                  previous=previous, first=first, last=last, anchor=anchor, remainder=remainder,
                  hit_low=-1, hit_high=-1, rock_queries=[])
    mode, source = actor_word(actor, 16), actor_word(actor, 40)
    room, row = actor_word(actor, 22), actor_word(actor, 14)
    rocks = bool(reader.level[0x2191])
    if mode == 7 or source in (70, 78):
        if mode == 7 and rocks:
            output['rock_queries'].append((room, row))
        return output
    if rocks:
        output['rock_queries'].append((room, row))
    output['current'] = row
    output['tables'] = history_reference(actor, row, previous, tables)['tables']
    output['previous'] = row
    right_col, _ = column_reference(edges[1])
    left_col, remainder = column_reference(edges[0])
    first, last = signed_word(left_col - 2), min(right_col + 4, 11)
    if not -2 <= first <= 11 or not -2 <= last <= 11:
        raise ValueError('Generated span outside the separately tested sweep/table domain')
    output.update(first=first, last=last, remainder=remainder)
    for name, offset in (('current', 0), ('lower', 1), ('upper', -1)):
        swept = sweep_reference(actor, row + offset, first, last, edges,
                                output['tables'][name + '_tags'],
                                output['tables'][name + '_masks'], reader, height=height)
        output['tables'][name + '_tags'] = swept['tags']
        output['tables'][name + '_masks'] = swept['masks']
        output['anchor'] = swept['anchor']
    if rocks:
        output['rock_queries'].extend((room, row + offset) for offset in (0, 1, -1))
    for column in range(9, -1, -1):
        tag = output['tables']['current_tags'][column]
        if tag == 65535 or tag != output['tables']['history_tags'][column]:
            continue
        before = output['tables']['history_masks'][column]
        after = output['tables']['current_masks'][column]
        if not before & 15 and after & 15:
            output['hit_low'] = column
        if not before & 240 and after & 240:
            output['hit_high'] = column
    return output


class NativeTempleCollisionBanks(NativeTempleCollisionSweep):
    RANGES = dict(NativeTempleCollisionSweep.RANGES)
    RANGES[4] += ((0x4e34, 0x50cc), (0x5152, 0x52aa), (0x3ad6, 0x3afa))
    RANGES[5] += ((0x48b0, 0x48de), (0x293c, 0x2996))
    RANGES[10] += ((0x190c, 0x1a8a), (0x1a9e, 0x1aea))
    RANGES[19] += ((0x2f72, 0x2f8a), (0x2ff0, 0x3008))

    def reset(self, level):
        super().reset(level)
        self.rock_queries = []

    def dispatch(self, cpu, address, size, user):
        if address == self.address(10, 0x1a9e):
            stack = cpu.reg_read(self.registers['a7'])
            self.rock_queries.append(struct.unpack('>2h', cpu.mem_read(stack + 4, 4)))
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    levels = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL']
    machine = NativeTempleCollisionBanks(parse_resource_fork(executable))
    counts, hits, digest = Counter(), Counter(), hashlib.sha256()
    mob_guard = bytes((index * 7 + 3) & 255 for index in range(512))

    def check(level, actor, edges, previous, pattern, label):
        room = actor_word(actor, 22)
        tables = {name: [room] * 10 if name.endswith('tags') else [pattern] * 10 for name in TABLES}
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, actor)
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(range(62)))
        machine.cpu.mem_write(machine.A5 - 0x448e, bytes(range(160)))
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', *COLD_CACHE))
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', 0xb0000))
        machine.cpu.mem_write(0xb0000, mob_guard)
        machine.put_word(-0x4490, 0)
        for name, offset in TABLES.items():
            machine.cpu.mem_write(machine.A5 + offset, struct.pack('>10H', *tables[name]))
        for offset, value in ((-0x4fc2, room), (-0x357c, 71), (-0x357e, previous),
                              (-0x3580, 7), (-0x3582, 8), (-0x35fc, 73), (-0x481c, 79),
                              (-0x3578, 67), (-0x357a, 69), (-0x3564, edges[0]),
                              (-0x3566, edges[1]), (-0x3560, 74), (-0x36bc, 0), (-0x4fa6, 0)):
            machine.put_word(offset, value)
        reader = StandingCellReader(level, room)
        expected = banks_reference(actor, edges, tables, reader, previous)
        before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        machine.call(4, 0x4e34)
        for name, offset in TABLES.items():
            struct.pack_into('>10H', before, len(machine.data) + offset, *expected['tables'][name])
        for offset, name in ((-0x357c, 'current'), (-0x357e, 'previous'), (-0x3580, 'first'),
                             (-0x3582, 'last'), (-0x35fc, 'anchor'), (-0x481c, 'remainder'),
                             (-0x3578, 'hit_low'), (-0x357a, 'hit_high')):
            struct.pack_into('>h', before, len(machine.data) + offset, expected[name])
        struct.pack_into('>6h', before, len(machine.data) - 0x34b0, *reader.cache)
        if reader.pointer_room is not None:
            r = reader.pointer_room
            struct.pack_into('>II', before, len(machine.data) - 0x4824,
                             machine.LEVEL + 0x780 + (r - 1) * 120,
                             machine.LEVEL + (r - 1) * 60)
        after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        if (after != before or machine.services or machine.reads != reader.requests
                or machine.rock_queries != expected['rock_queries']
                or machine.level_bytes(len(level)) != level
                or bytes(machine.cpu.mem_read(0xb0000, 512)) != mob_guard):
            raise AssertionError(dict(label=label, actor=actor.hex(), edges=edges, previous=previous,
                expected=expected, reads=machine.reads, expected_reads=reader.requests,
                rock_queries=machine.rock_queries, changed=[(hex(i - len(machine.data)), a, b)
                for i, (a, b) in enumerate(zip(before, after)) if a != b]))
        counts[label] += 1
        hits['low' if expected['hit_low'] >= 0 else 'no_low'] += 1
        hits['high' if expected['hit_high'] >= 0 else 'no_high'] += 1
        digest.update(actor + struct.pack('>8h6h', *(expected[name] for name in (
                      'current', 'previous', 'first', 'last', 'anchor', 'remainder', 'hit_low', 'hit_high')),
                      *reader.cache))
        for bank in expected['tables'].values():
            digest.update(struct.pack('>10H', *bank))

    for number in range(10, 14):
        level = levels[1999 + number]['data']
        maximum = struct.unpack_from('>H', level, 0x2180)[0]
        for room, row, facing, velocity, edges, previous, pattern in product(
                range(1, maximum + 1), range(3), (-1, 0), (-1, 1),
                ((230, 260), (430, 475), (680, 720)), (0, 1, 2), (0, 255)):
            actor = bytearray(actor_fixture(room, row, column_reference(sum(edges) // 2)[0], facing, 0))
            for offset, value in ((4, sum(edges) // 2), (6, row * 120 + 106), (8, 0),
                                  (10, 15), (18, velocity), (28, -1), (30, 3), (40, 2), (52, 0)):
                put_actor(actor, offset, value)
            check(level, bytes(actor), edges, previous, pattern, 'declared_room_states')
    original = levels[2009]['data']
    for mode, source, flag in product((0, 4, 7), (2, 70, 78), (0, 1)):
        level = bytearray(original)
        level[0x2191] = flag
        actor = bytearray(actor_fixture(1, 1, 4, 0, mode))
        for offset, value in ((4, 460), (10, 15), (18, 1), (28, -1), (30, 3), (40, source), (52, 4)):
            put_actor(actor, offset, value)
        check(bytes(level), bytes(actor), (430, 475), 0, 0, 'entry_and_empty_rock_controls')
    return dict(comparisons=dict(counts), collision_flags=dict(hits), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                outputs_sha256=digest.hexdigest(), supplied=[], scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
