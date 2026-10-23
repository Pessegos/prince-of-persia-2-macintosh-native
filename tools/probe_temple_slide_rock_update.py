"""Connect original sliding-rock geometry, motion, crush admission and bank updates."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_slide_rock_geometry import (
    NativeSlideRockGeometry, TempleCellReader, stop_predicate_reference,
)
from tools.probe_temple_slide_rock_motion import NativeSlideRockMotion, motion_reference
from tools.probe_temple_slide_rock_trigger import trigger_reference


ACTOR_TAGS = {'5:3cee': 30001, '6:1a84': 30003, '10:1b04': 30005}


def actor_word(actor, offset):
    return struct.unpack_from('>h', actor, offset)[0]


def crush_admission_reference(mob, prince, width):
    if (len(mob) != 8 or len(prince) != 62 or not -32768 <= width <= 32767
            or any(not -32768 <= word <= 32767 for word in mob)):
        raise ValueError('Expected eight native words, a 62-byte actor and signed width')
    if mob[2] != actor_word(prince, 22) or mob[6] != actor_word(prince, 14):
        return False
    front = actor_word(prince, 4)
    if actor_word(prince, 2) != 0:
        front = signed_word(front + width)
    lower = signed_word(mob[0] + 223)
    return actor_word(prince, 52) == 4 or lower < front < lower + 25


def actor_effects_reference(prince, working, events):
    inputs = []
    for event in events:
        if event[0] != 'actor':
            continue
        inputs.append(prince)
        working = bytearray(prince)
        tag = ACTOR_TAGS[event[1]]
        struct.pack_into('>h', working, 0, tag)
        struct.pack_into('>h', working, 60, tag + 1)
        prince = working = bytes(working)
    return prince, working, inputs


def update_reference(mob, reader, prince, working, width, *, cue193_on=False, pending=-1):
    if len(prince) != 62 or len(working) != 62:
        raise ValueError('Expected 62-byte actor buffers')

    def filled_at(x):
        return stop_predicate_reference((x, *mob[1:]), reader)

    left = reader.link(mob[2], 0)
    result = motion_reference(mob, left, filled=filled_at, tiles=reader.read,
                              cue193_on=cue193_on, pending=pending,
                              prince=tuple(actor_word(prince, i) for i in (10, 12, 14)))
    moved_prince, _, _ = actor_effects_reference(prince, working, result['events'])
    if crush_admission_reference(result['mob'], moved_prince, width):
        result['events'].append(('actor', '10:1b04'))
    prince, working, inputs = actor_effects_reference(prince, working, result['events'])
    result.update(prince=prince, working=working, actor_inputs=inputs,
                  phases=[('motion', tuple(mob)), ('crush', result['mob'])])
    return result


class NativeSlideRockUpdate(NativeSlideRockMotion):
    RANGES = {
        3: NativeSlideRockGeometry.RANGES[3] + NativeSlideRockMotion.RANGES[3],
        4: NativeSlideRockGeometry.RANGES[4] + NativeSlideRockMotion.RANGES[4],
        5: ((0x0004, 0x0066), (0x2914, 0x2b0e), (0x4970, 0x49a0)),
        10: ((0x1656, 0x1680), (0x16f6, 0x176e), (0x1a9e, 0x1ae8),
             (0x1ca4, 0x1d40), (0x1d5c, 0x1fa6), (0x2152, 0x2246)),
        19: NativeSlideRockMotion.RANGES[19],
    }
    ENDPOINTS = {key: value for key, value in NativeSlideRockMotion.ENDPOINTS.items()
                 if key not in ((10, 0x1656), (4, 0x27ee))} | {(10, 0x1b04): '10:1b04'}
    ACTOR_TAGS = ACTOR_TAGS
    BANK = 0xb0010

    def reset(self, level):
        super().reset(level)
        self.reads, self.phases = [], []
        self.checked_events = 0
        for offset in (-0x34b0, -0x34ae, -0x34ac):
            self.put_word(offset, 0)

    def dispatch(self, cpu, address, size, user):
        if address == self.address(10, 0x1656):
            self.events.append(('filled', self.word(-0x44a6)))
        elif address == self.address(4, 0x27ee):
            stack = cpu.reg_read(self.registers['a7'])
            args = struct.unpack('>3h', cpu.mem_read(stack + 4, 6))
            self.reads.append(args)
            caller = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            if caller in (self.address(10, 0x1e5c), self.address(10, 0x1edc)):
                self.events.append(('cell', *args))
        elif address in (self.address(10, 0x1d5c), self.address(10, 0x16f6)):
            self.phases.append(('motion' if address == self.address(10, 0x1d5c) else 'crush', self.mob()))
        super().dispatch(cpu, address, size, user)

    def cache(self):
        return struct.unpack('>6h', self.cpu.mem_read(self.A5 - 0x34b0, 12))


def make_prince(*, room=1, row=1, x=430, facing=0, frame=0, column=0, mode=0, actor_kind=0):
    actor = bytearray((index * 7 + 13) % 256 for index in range(62))
    for offset, value in ((2, facing), (4, x), (8, actor_kind), (10, frame), (12, column),
                          (14, row), (22, room), (52, mode)):
        struct.pack_into('>h', actor, offset, value)
    return bytes(actor)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince_fork = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeSlideRockUpdate(parse_resource_fork(executable))
    counts, effects = Counter(), Counter()
    digest = hashlib.sha256()
    working_initial = bytes((i * 17 + 7) % 256 for i in range(62))
    canary = bytes((i * 29 + 3) % 256 for i in range(512))
    scratch_initial = (17, 19, 23, 29, 31, 37, 41, 43)
    level_hashes = {}

    def prepare(level, view, prince, width, bank=()):
        machine.reset(level)
        machine.put_word(-0x4fc2, view)
        machine.put_word(-0x3570, width)
        machine.put_word(-0x439e, 192)
        machine.cpu.mem_write(machine.A5 - 0x50d2, prince)
        machine.cpu.mem_write(machine.A5 - 0x5056, working_initial)
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *scratch_initial))
        storage = bytearray(canary)
        for index, mob in enumerate(bank):
            storage[16 + index * 16:32 + index * 16] = struct.pack('>8h', *mob)
        machine.cpu.mem_write(machine.BANK - 16, bytes(storage))
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
        machine.put_word(-0x4490, len(bank))
        return storage

    def check(level, reader, expected, storage, count, label):
        if (machine.mob() != expected['mob'] or machine.events != expected['events']
                or machine.phases != expected['phases']
                or machine.actor_inputs != expected['actor_inputs']
                or machine.reads != reader.requests or machine.cache() != reader.cache
                or machine.word(-0x439e) != expected['pending']
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != expected['prince']
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != expected['working']
                or bytes(machine.cpu.mem_read(machine.BANK - 16, 512)) != storage
                or machine.word(-0x4490) != count or machine.level_bytes(len(level)) != level
                or machine.services):
            raise AssertionError(dict(label=label, actual=machine.mob(), expected=expected['mob'],
                                      events=machine.events, expected_events=expected['events'],
                                      reads=machine.reads, expected_reads=reader.requests,
                                      phases=machine.phases, expected_phases=expected['phases']))
        counts[label] += 1
        effects.update(event[1] for event in expected['events'][machine.checked_events:]
                       if event[0] == 'actor')
        machine.checked_events = len(expected['events'])
        digest.update(struct.pack('>8h6hh', *machine.mob(), *machine.cache(), count))
        digest.update(storage + expected['prince'] + expected['working'])
        digest.update(json.dumps((machine.events, machine.reads, machine.phases)).encode('ascii'))

    level = prince_fork['LEVL'][2009]['data']
    for x, delta, facing, width, mode, same_room, same_row in product(
            (-32768, 0, 204, 32540, 32760, 32767), (-1, 0, 1, 24, 25, 26),
            (-1, 0, 1), (-1, 0, 12, 22), (-1, 0, 4, 5), (False, True), (False, True)):
        lower = signed_word(x + 223)
        actor_x = signed_word(lower + delta - (width if facing else 0))
        prince = make_prince(room=28 if same_room else 27, row=1 if same_row else 2,
                             x=actor_x, facing=facing, mode=mode)
        mob = (x, 236, 28, 0, 2, 6, 1, 459)
        reader = TempleCellReader(level, 28)
        storage = prepare(level, 28, prince, width)
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *mob))
        events = [('actor', '10:1b04')] if crush_admission_reference(mob, prince, width) else []
        prince, working, inputs = actor_effects_reference(prince, working_initial, events)
        expected = dict(mob=mob, events=events, phases=[('crush', mob)], pending=192,
                        prince=prince, working=working, actor_inputs=inputs)
        machine.call(10, 0x16f6)
        check(level, reader, expected, storage, 0, 'crush_admission')

    for room, control, mark in product((0, 28), (-2, 0, 100), (-1, 0, 1)):
        mob = (204, 236, room, mark, control, 6, 1, 459)
        prince = make_prince(room=room, row=1, x=440)
        reader = TempleCellReader(level, 28)
        storage = prepare(level, 28, prince, 22)
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *mob))
        events = [('actor', '10:1b04')]
        prince, working, inputs = actor_effects_reference(prince, working_initial, events)
        expected = dict(mob=mob, events=events, phases=[('crush', mob)], pending=192,
                        prince=prince, working=working, actor_inputs=inputs)
        machine.call(10, 0x16f6)
        check(level, reader, expected, storage, 0, 'crush_ignored_control_mark')

    supplied = bytearray(level)
    struct.pack_into('>H', supplied, 20, 2)  # room1,row1,column0
    for mark, frame, row, room in ((1, 0, 1, 1), (0, 87, 2, 1), (0, 99, 2, 2)):
        x = 58 if mark else 65
        mob = (x, 236, 1, mark, -2, 6, 1, 459)
        prince = make_prince(room=room, row=row, x=x + 235, frame=frame, column=1)
        reader = TempleCellReader(supplied, 1)
        storage = prepare(supplied, 1, prince, 22)
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *mob))
        expected = update_reference(mob, reader, prince, working_initial, 22, pending=192)
        machine.call(5, 0x2afa)
        check(supplied, reader, expected, storage, 0, 'actor_endpoint_order_controls')

    for number in range(10, 14):
        original = prince_fork['LEVL'][1999 + number]['data']
        level_hashes[str(number)] = hashlib.sha256(original).hexdigest()
        for room, cell in product(range(1, 33), range(30)):
            if struct.unpack_from('>H', original, (room - 1) * 60 + cell * 2)[0] != 25:
                continue
            row, col = divmod(cell, 10)
            positions = sorted({0, 1, 2, 6, 31, 51, max(0, col * 51 - 16), col * 51, col * 51 + 2})
            for x, control, mark in product(positions, (-3, -2, -1, 0, 2, 7, 8, 9, 100), (-1, 0, 1)):
                mob = (x, 116 + row * 120, room, mark, control, 6, row, col * 51)
                prince = make_prince(room=room, row=row, x=x + 235, mode=4 if x == 31 else 0)
                reader = TempleCellReader(original, room)
                storage = prepare(original, room, prince, 22)
                machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *mob))
                expected = update_reference(mob, reader, prince, working_initial, 22, pending=192)
                machine.call(5, 0x2afa)
                check(original, reader, expected, storage, 0, 'actual_anchor_updates')

    def bank_step(level, reader, bank, prior, storage):
        events, phases, inputs = [], [], []
        updated = []
        prince, working, pending = prior['prince'], prior['working'], prior['pending']
        scratch = prior['mob']
        for index, mob in enumerate(bank):
            if mob[5] == 6:
                step = update_reference(mob, reader, prince, working, 22, pending=pending)
                prince, working, pending = step['prince'], step['working'], step['pending']
                scratch = step['mob']
                events.extend(step['events'])
                phases.extend(step['phases'])
                inputs.extend(step['actor_inputs'])
            elif mob[5] == 1:
                scratch = mob
            else:
                raise ValueError('Mixed-bank probe covers only native types1 and6')
            updated.append(scratch)
            storage[16 + index * 16:32 + index * 16] = struct.pack('>8h', *scratch)
        survivors = tuple(mob for mob in updated if mob[3] != -1)
        for index, mob in enumerate(survivors):
            storage[16 + index * 16:32 + index * 16] = struct.pack('>8h', *mob)
        expected = dict(mob=scratch, events=prior['events'] + events,
                        phases=prior['phases'] + phases,
                        actor_inputs=prior['actor_inputs'] + inputs,
                        prince=prince, working=working, pending=pending)
        machine.call(5, 0x29e8)
        if machine.word(-0x4492) != len(bank):
            raise AssertionError('Native bank iterator did not visit the supplied count')
        return survivors, expected

    for count in (0, 1, 3, 30):
        bank = tuple((204 if i % 3 else 0, 236, 28, -1 if i % 3 == 1 else 0,
                      -2 if i % 2 else 2, 6 if i % 4 else 1, 1, 459) for i in range(count))
        prince = make_prince(room=28, row=1, x=440)
        storage = prepare(level, 28, prince, 22, bank)
        reader = TempleCellReader(level, 28)
        prior = dict(mob=scratch_initial, events=[], phases=[], actor_inputs=[],
                     prince=prince, working=working_initial, pending=192)
        bank, expected = bank_step(level, reader, bank, prior, storage)
        check(level, reader, expected, storage, len(bank), 'mixed_bank_compaction')

    traces = []
    for number in range(10, 14):
        original = prince_fork['LEVL'][1999 + number]['data']
        for room, cell in product(range(1, 33), range(30)):
            if struct.unpack_from('>H', original, (room - 1) * 60 + cell * 2)[0] != 25:
                continue
            for view_changes in (False, True):
                prince = make_prince(room=room % 32 + 1, row=cell // 10, x=430)
                storage = prepare(original, room, prince, 22)
                reader = TempleCellReader(original, room)
                bank = ()
                prior = dict(mob=scratch_initial, events=[], phases=[], actor_inputs=[],
                             prince=prince, working=working_initial, pending=192)
                snapshots = []
                for cycle in range(160):
                    if view_changes and cycle in (40, 80, 120):
                        reader.view_room = {40: 4, 80: 13, 120: room % 32 + 1}[cycle]
                        machine.put_word(-0x4fc2, reader.view_room)
                        snapshots.append(dict(cycle=cycle, view=reader.view_room, bank=bank))
                    if cycle in (0, 8, 64, 72):
                        how = 1 if cycle in (0, 64) else 2
                        trigger = trigger_reference(room, cell, how, bank)
                        if trigger['scratch'] is not None:
                            reader.read(room, cell % 10, cell // 10)
                            prior['mob'] = trigger['scratch']
                        bank = trigger['bank']
                        for index, mob in enumerate(bank):
                            storage[16 + index * 16:32 + index * 16] = struct.pack('>8h', *mob)
                        machine.call(10, 0x2152, (room, cell, how))
                        check(original, reader, prior, storage, len(bank), 'connected_trigger')
                        snapshots.append(dict(cycle=cycle, how=how, bank=bank))
                    bank, prior = bank_step(original, reader, bank, prior, storage)
                    check(original, reader, prior, storage, len(bank), 'connected_bank_update')
                    if cycle in (0, 8, 63, 64, 72, 159):
                        snapshots.append(dict(cycle=cycle, bank=bank))
                traces.append(dict(level=number, room=room, cell=cell, snapshots=snapshots,
                                   view_changes=view_changes, final=bank, updates=160))
    return dict(
        cases=dict(counts), actor_endpoint_occurrences=dict(effects), traces=traces,
        mismatches=0, outputs_sha256=digest.hexdigest(), level_hashes=level_hashes,
        executable_sha256=hashlib.sha256(executable).hexdigest(),
        supplied=[
            '5:5252 StopSound,5:4d84 AddSound: record requests without audio side effects',
            '5:52c8 PrinceSndOn: supplied cue193 false throughout',
            '5:3cee,6:1a84,10:1b04: record actor admission, tag first/last working-actor words',
            'Trigger calls and bank-update cadence/view rooms/actor fixtures are supplied, not FrameAdv',
        ],
        scope=('Real geometry/cache+motion10:1d5c+crush admission10:16f6, type6 '
               'dispatcher5:2afa, MakeRubble5:29e8 iteration/writeback/compaction and '
               'TriggerSlideRock10:2152 connected across all12 original marker cells. '
               'Actor reaction BODY10:1b04 and movement actor effects are supplied, '
               'not native damage/death/animation. Entire levels, bank/tail guards, '
               'actors, ordered endpoints/reads, cache, scratch/count/phase order compared. '
               'No presentation, full-frame scheduling, file save/load/restart or campaign claim.'),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'traces'}, indent=2))


if __name__ == '__main__':
    main()
