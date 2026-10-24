"""Recover native plate timer updates and TROB compaction with a redraw sink."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


def signed_word(value):
    return (value + 32768) % 65536 - 32768


def animate_record(level, record, index):
    cell, room, phase, kind = record
    if not 1 <= room <= 32 or not 0 <= cell < 30:
        raise ValueError('Expected an in-range raw room/cell')
    if kind not in (1, 5, 6, 34):
        raise ValueError('Only plate kinds and a default-kind control are covered')
    result = bytearray(level)
    offset = 0x780 + (room - 1) * 120 + cell * 4
    foreground, tail = struct.unpack_from('>2H', result, offset)
    raw_kind = struct.unpack_from('>H', result, (room - 1) * 60 + cell * 2)[0]
    events = [('visit', index, *record)]
    if kind == 1:
        phase = -1
    elif phase >= 0:
        timer_offset = 0x1680 + (foreground & 255) * 10 + 4
        timer = struct.unpack_from('>h', result, timer_offset)[0]
        if timer >= 31:
            phase = -1
        else:
            struct.pack_into('>h', result, timer_offset, signed_word(timer - 1))
            if timer < 2:
                phase = -1
                events.append(('redraw', room, cell, foreground, signed_word(timer - 1)))
                foreground &= ~0x2000
    struct.pack_into('>H', result, offset, foreground)
    return dict(level=bytes(result), scratch=(cell, room, phase, kind),
                os=struct.pack('>3H', foreground, tail, raw_kind), events=events)


def animate_bank(state):
    if len(state['trobs']) > 20:
        raise ValueError('Native TROB capacity is20')
    state = dict(state)
    storage = bytearray(state['trob_storage'])
    updated = []
    for index, record in enumerate(state['trobs']):
        result = animate_record(state['level'], record, index)
        state.update(level=result['level'], scratch=result['scratch'], os=result['os'],
                     events=state['events'] + result['events'])
        updated.append(result['scratch'])
        struct.pack_into('>h', storage, index * 8 + 4, result['scratch'][2])
    surviving = [record for record in updated if record[2] >= 0]
    if len(surviving) != len(updated):
        for index, record in enumerate(surviving):
            struct.pack_into('>4h', storage, index * 8, *record)
    return dict(state, trobs=tuple(surviving), trob_storage=bytes(storage))


def initial_state(level, trobs):
    storage = bytearray((i * 19 + 7) % 256 for i in range(160))
    if len(trobs) > 20:
        raise ValueError('Native TROB capacity is20')
    for i, record in enumerate(trobs):
        struct.pack_into('>4h', storage, i * 8, *record)
    return dict(level=bytes(level), trobs=tuple(trobs), trob_storage=bytes(storage),
                scratch=(41, 43, 47, 53), os=bytes((11, 13, 17, 19, 23, 29)), events=[])


class NativePlateRelease(NativeRules):
    RANGES = {5: ((0x0004, 0x0066), (0x0c38, 0x0d0c), (0x0d72, 0x0d78),
                  (0x0e10, 0x0e2a), (0x2278, 0x22a6), (0x22b8, 0x22ee),
                  (0x2554, 0x25a8), (0x29a8, 0x29dc))}
    SUPPLIED = {(5, 0x0f38): 'plate_redraw'}
    CACHE = struct.pack('>6h', 11, 13, 17, 19, 23, 29)
    ACTOR = bytes((i * 11 + 3) % 256 for i in range(62))
    MOB = bytes((i * 7 + 13) % 256 for i in range(22))

    def reset(self, level):
        super().reset(level)
        self.events = []

    def dispatch(self, cpu, address, size, user):
        if address == self.address(5, 0x0cd6):
            stack = cpu.reg_read(self.registers['a7'])
            index = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            record = struct.unpack('>4h', cpu.mem_read(self.A5 - 0x43ee, 8))
            self.events.append(('visit', index, *record))
        elif address == self.address(5, 0x0f38):
            cell, room, _phase, _kind = struct.unpack('>4h', cpu.mem_read(self.A5 - 0x43ee, 8))
            foreground = self.word(-0x4818) & 65535
            timer = struct.unpack('>h', cpu.mem_read(self.LEVEL + 0x1680 + (foreground & 255) * 10 + 4, 2))[0]
            self.events.append(('redraw', room, cell, foreground, timer))
        super().dispatch(cpu, address, size, user)

    def load_state(self, state):
        self.reset(state['level'])
        self.cpu.mem_write(self.A5 - 0x448e, state['trob_storage'])
        self.put_word(-0x43e6, len(state['trobs']))
        self.cpu.mem_write(self.A5 - 0x43ee, struct.pack('>4h', *state['scratch']))
        self.cpu.mem_write(self.A5 - 0x4818, state['os'])
        self.cpu.mem_write(self.A5 - 0x34b0, self.CACHE)
        self.cpu.mem_write(self.A5 - 0x5056, self.ACTOR)
        self.cpu.mem_write(self.A5 - 0x50d2, self.ACTOR)
        self.cpu.mem_write(self.A5 - 0x44a6, self.MOB)
        self.put_word(-0x4490, 17)
        self.put_word(-0x439e, 1234)
        self.put_word(-0x4f9e, 4321)

    def snapshot(self, size):
        count = self.word(-0x43e6)
        if not 0 <= count <= 20:
            raise AssertionError(('Invalid native TROB count', count))
        return dict(level=self.level_bytes(size),
                    trobs=tuple(struct.unpack('>4h', self.cpu.mem_read(self.A5 - 0x448e + i * 8, 8))
                                for i in range(count)),
                    trob_storage=bytes(self.cpu.mem_read(self.A5 - 0x448e, 160)),
                    scratch=struct.unpack('>4h', self.cpu.mem_read(self.A5 - 0x43ee, 8)),
                    os=bytes(self.cpu.mem_read(self.A5 - 0x4818, 6)), events=self.events)

    def assert_state(self, expected, context):
        actual = self.snapshot(len(expected['level']))
        if actual != expected:
            raise AssertionError(dict(context=context,
                                      differences={key: (actual[key], expected[key]) for key in expected
                                                   if actual[key] != expected[key]}))
        services = Counter({'plate_redraw': sum(event[0] == 'redraw' for event in expected['events'])})
        if (self.services != +services or self.word(-0x4490) != 17
                or bytes(self.cpu.mem_read(self.A5 - 0x34b0, 12)) != self.CACHE
                or bytes(self.cpu.mem_read(self.A5 - 0x5056, 62)) != self.ACTOR
                or bytes(self.cpu.mem_read(self.A5 - 0x50d2, 62)) != self.ACTOR
                or bytes(self.cpu.mem_read(self.A5 - 0x44a6, 22)) != self.MOB
                or self.word(-0x439e) != 1234 or self.word(-0x4f9e) != 4321):
            raise AssertionError(('Services or canaries differ', context, self.services))
        return actual


def plate_inventory(resources):
    result = []
    for number in range(10, 14):
        level = resources['LEVL'][1999 + number]['data']
        if struct.unpack_from('>3h', level, 0x2186)[::2] != (2, number):
            raise ValueError('Inconsistent temple resource header')
        for room in range(1, struct.unpack_from('>h', level, 0x2180)[0] + 1):
            for cell in range(30):
                kind = struct.unpack_from('>h', level, (room - 1) * 60 + cell * 2)[0]
                if kind in (5, 6, 34):
                    result.append((number, level, room, cell, kind))
    return result


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(executable)
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativePlateRelease(program)
    inventory = plate_inventory(resources)
    if len(inventory) != 68:
        raise ValueError(('Unexpected admitted plate inventory', len(inventory)))
    code = program['CODE'][5]['data']
    dispatch = {kind: 0x0d0c + struct.unpack_from('>h', code, 0x0d0e + (kind - 4) * 2)[0]
                for kind in (5, 6, 34)}
    if set(dispatch.values()) != {0x0d72}:
        raise ValueError(('Unexpected native plate jump targets', dispatch))
    counts, services, digest = Counter(), Counter(), hashlib.sha256()

    def check(state, label, context):
        machine.assert_state(state, context)
        counts[label] += 1
        services.update(machine.services)
        digest.update(state['level'] + state['trob_storage'] + state['os'])
        digest.update(json.dumps([state['scratch'], len(state['trobs']), state['events']]).encode('ascii'))

    for number, original, room, cell, kind in inventory:
        offset = 0x780 + (room - 1) * 120 + cell * 4
        foreground = struct.unpack_from('>H', original, offset)[0]
        for timer, phase, depressed in product(
                (-32768, -1, 0, 1, 2, 5, 30, 31, 32, 32767), (-32768, -1, 0, 1, 32767), (False, True)):
            level = bytearray(original)
            struct.pack_into('>h', level, 0x1680 + (foreground & 255) * 10 + 4, timer)
            struct.pack_into('>H', level, offset, (foreground & ~0x2000) | (0x2000 if depressed else 0))
            record = (cell, room, phase, kind)
            state = initial_state(level, (record,))
            state['scratch'] = record
            machine.load_state(state)
            result = animate_record(state['level'], record, 3)
            expected = dict(state, **result)
            machine.call(5, 0x0cd6, (3,))
            check(expected, 'original_plate_dispatch', (number, room, cell, timer, phase, depressed))

    # Supplied bank topology isolates compaction and per-record shared-clock updates.
    for number in range(10, 14):
        original = resources['LEVL'][1999 + number]['data']
        for count, timer, scenario in product((0, 1, 2, 5, 20), (0, 1, 2, 5, 31, 32),
                                              ('distinct', 'shared-clock', 'all-dead', 'default-kind')):
            level = bytearray(original)
            records = []
            for i in range(count):
                cell, room = i % 10 + 10, i // 10 + 1
                kind = 34 if i % 3 == 0 else (5 if i % 3 == 1 else 6)
                if scenario == 'default-kind' and i % 2 == 0:
                    kind = 1
                phase = -1 if scenario == 'all-dead' or (scenario == 'distinct' and i % 3 == 0) else 1
                index = 240 if scenario == 'shared-clock' else 220 + i
                struct.pack_into('>H', level, (room - 1) * 60 + cell * 2, 6)
                struct.pack_into('>2H', level, 0x780 + (room - 1) * 120 + cell * 4, 0xa000 | index, 0x5a00 + i)
                struct.pack_into('>h', level, 0x1680 + index * 10 + 4, timer)
                records.append((cell, room, phase, kind))
            state = initial_state(level, records)
            machine.load_state(state)
            for step in range(8):
                state = dict(state, events=[])
                machine.events, machine.services = [], Counter()
                state = animate_bank(state)
                machine.call(5, 0x0c38)
                check(state, 'persistent_bank_compaction', (number, count, timer, scenario, step))

    return dict(cases=dict(counts), mismatches=0, services=dict(services),
                inventory=[(number, room, cell, kind) for number, _, room, cell, kind in inventory],
                dispatch_targets={str(kind): f'5:{target:04x}' for kind, target in dispatch.items()},
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
                level_hashes={str(n): hashlib.sha256(resources['LEVL'][1999 + n]['data']).hexdigest()
                              for n in range(10, 14)},
                supplied_services=['5:0f38 RedrawPlate: record scratch room/cell, OS foreground and timer; return0'],
                scope=('Native plate body5:2554 through AnimTrob and AnimTrobs, original room/OS/link reads '
                       'and writes, phase writeback and stable compaction. All68 header-admitted original '
                       'plate sources in direct dispatch; supplied multi-record banks across four original '
                       'headers include kind34/default controls and shared timers. No actor pressure or '
                       'Trigger calls, target activation/reversal, gate animation, real redraw, FrameAdv '
                       'cadence or save/reset equivalence claimed.'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
