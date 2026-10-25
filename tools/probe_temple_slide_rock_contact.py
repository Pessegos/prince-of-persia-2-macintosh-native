"""Execute original slide-rock contact, native health writes and first animation step."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_slide_rock_geometry import TempleCellReader, stop_predicate_reference
from tools.probe_temple_slide_rock_motion import motion_reference, trunc_div
from tools.probe_temple_slide_rock_update import (
    NativeSlideRockUpdate, actor_word, crush_admission_reference,
)


def put_actor(actor, offset, value):
    struct.pack_into('>h', actor, offset, signed_word(value))


def character_column(value):
    coordinate = signed_word(value - 22)
    # 5:48b0 sign-extends BEFORE subtracting four from only the low word.
    dividend = (coordinate & ~65535) | ((coordinate - 4) & 65535)
    quotient = trunc_div(dividend)
    return signed_word(quotient - 4 - int(coordinate < 0)), dividend - quotient * 51


def align_y(actor):
    value = actor_word(actor, 14) * 120 + 106
    return signed_word(value - (33 if actor_word(actor, 8) in (7, 8) else 0))


def animate_reference(actor, sequences, events):
    """Independent first-frame interpreter for this body's four selected clips."""
    sequence, cursor = actor_word(actor, 38), actor_word(actor, 36)
    events.extend((('animate', sequence, cursor), ('sequence', sequence)))
    if sequence not in sequences:
        return
    words = sequences[sequence]
    events.extend((('handle', 'HGetState'), ('handle', 'HLock')))
    for _ in range(32):
        if not 0 <= cursor < len(words):
            raise ValueError('Sequence cursor outside the prepared first-frame domain')
        op = words[cursor]
        cursor += 1
        if op >= 0:
            put_actor(actor, 10, op)
            put_actor(actor, 36, cursor)
            events.append(('handle', 'HSetState'))
            return
        if op in (-7, -5):
            if cursor >= len(words):
                raise ValueError('Truncated first-frame operand')
            operand = words[cursor]
            cursor += 1
            if op == -7:
                put_actor(actor, 16, operand)
            else:
                put_actor(actor, 4, actor_word(actor, 4)
                          + (operand if actor_word(actor, 2) == 0 else -operand))
        elif op == -19:
            put_actor(actor, 6, align_y(actor))
        else:
            raise ValueError(f'Opcode outside the first-frame reference domain: {op}')
    raise ValueError('First-frame reference instruction limit exceeded')


def contact_reference(mob, actor, width, reader, sequences, *, death_method=12345, remainder=-1234):
    if (len(mob) != 8 or len(actor) != 62 or any(not -32768 <= x <= 32767 for x in mob)
            or not 0 <= mob[0] <= 561 or not -1 <= width <= 32
            or actor_word(actor, 8) not in (0, 2, 4, 7, 8)
            or not 0 <= actor_word(actor, 14) <= 2):
        raise ValueError('Outside the bounded contact-body domain; actor1 conversion is excluded')
    result = bytearray(actor)
    events = []
    sequence = None
    if actor_word(result, 16) == 5:
        return dict(actor=bytes(result), events=events, death_method=death_method, remainder=remainder)
    facing = actor_word(result, 2)
    if actor_word(result, 4) - 229 > mob[0]:
        put_actor(result, 4, mob[0] + 223 - (width if facing == -1 else 0))
    foot = signed_word(actor_word(result, 4) - 12 - (width if facing == 0 else 0))
    column, remainder = character_column(foot)
    kind = reader.read(actor_word(result, 22), column, actor_word(result, 14))
    solid = (2, 4, 7, 20, 25, 43)
    if kind in solid:
        if not -2 <= column <= 12:
            raise ValueError('Native X-table lookup outside the verified table range')
        put_actor(result, 4, 258 + column * 51 + 12 + (width + 6 if facing == 0 else 0))
        if kind != 2:
            if mob[4] == 100:
                if actor_word(result, 28) < 0:
                    # The caller passes the actor's entire life word to DecLifePts.
                    life = actor_word(result, 30)
                    if actor_word(result, 34) > -life:
                        put_actor(result, 34, -life)
                    put_actor(result, 28, 0)
                put_actor(result, 10, 185)
            else:
                distance = signed_word(mob[0] - 18)
                column = trunc_div(distance)
                second = reader.read(actor_word(result, 22), column, actor_word(result, 14))
                if second in solid and distance - trunc_div(distance) * 51 < 46:
                    if actor_word(result, 28) < 0:
                        events.append(('sound', 193))
                    if actor_word(result, 8) == 0:
                        death_method = 13
                put_actor(result, 52, 4)
                sequence = 71
    elif actor_word(result, 28) < 0:
        if actor_word(result, 26) == 1:
            put_actor(result, 26, 0)
            sequence = 93
        else:
            sequence = 47 if facing == 0 else 48
    else:
        put_actor(result, 4, actor_word(result, 4) - 12)
    if sequence is not None:
        put_actor(result, 6, align_y(result))
        put_actor(result, 20, 0)
        events.append(('resource', sequence))
        if sequence in sequences:
            put_actor(result, 38, sequence)
            put_actor(result, 40, sequence)
            put_actor(result, 36, 0)
        animate_reference(result, sequences, events)
    return dict(actor=bytes(result), events=events, death_method=death_method, remainder=remainder)


def contact_update_reference(mob, prince, working, width, reader, sequences, *,
                             death_method=12345, remainder=-1234, pending=192):
    moved = motion_reference(
        mob, reader.link(mob[2], 0),
        filled=lambda x: stop_predicate_reference((x, *mob[1:]), reader), tiles=reader.read,
        pending=pending, prince=tuple(actor_word(prince, i) for i in (10, 12, 14)))
    if any(event[0] == 'actor' for event in moved['events']):
        raise ValueError('This connected corpus excludes other movement actor-reaction bodies')
    contacts = []
    if crush_admission_reference(moved['mob'], prince, width):
        contacts.append(prince)
        contact = contact_reference(moved['mob'], prince, width, reader, sequences,
                                    death_method=death_method, remainder=remainder)
        prince = working = contact['actor']
        moved['events'].extend(contact['events'])
        death_method, remainder = contact['death_method'], contact['remainder']
    return dict(mob=moved['mob'], prince=prince, working=working, events=moved['events'],
                phases=[('motion', tuple(mob)), ('crush', moved['mob'])],
                contacts=contacts, actor_inputs=[], pending=moved['pending'],
                death_method=death_method, remainder=remainder)


class NativeSlideRockContact(NativeSlideRockUpdate):
    RANGES = NativeSlideRockUpdate.RANGES | {
        4: NativeSlideRockUpdate.RANGES[4] + (
            (0x2bae, 0x2bcc), (0x2c0c, 0x3050), (0x305e, 0x308a),
            (0x3196, 0x31e2), (0x31fa, 0x3228), (0x34f2, 0x3596), (0x3ad6, 0x3aea)),
        5: NativeSlideRockUpdate.RANGES[5] + ((0x48b0, 0x48dc),),
        6: ((0x0006, 0x0098),),
        10: NativeSlideRockUpdate.RANGES[10] + ((0x1b04, 0x1ca2),),
    }
    ENDPOINTS = {key: value for key, value in NativeSlideRockUpdate.ENDPOINTS.items()
                 if key not in ((10, 0x1b04), (5, 0x3cee), (6, 0x1a84))}
    BRANCH_CHECKS = {
        0x1b12: 'not_action_five', 0x1b30: 'clamp_x', 0x1b88: 'solid_first_tile',
        0x1bca: 'terminal_life_decrement', 0x1bd8: 'terminal_pose185',
        0x1c34: 'crush_sound193', 0x1c40: 'set_death_method13', 0x1c4a: 'mode_four',
        0x1c52: 'non_solid_first_tile', 0x1c72: 'disarm',
        0x1c7c: 'nonliving_x_minus_twelve', 0x1c88: 'sequence_common',
    }

    def __init__(self, program, sequences):
        super().__init__(program)
        self.handles = {}
        self.sequence_bytes = {}
        pointer = 0xc2000
        for index, (number, data) in enumerate(sorted(sequences.items())):
            handle = 0xc0000 + index * 4
            self.handles[number] = handle
            self.sequence_bytes[number] = (handle, pointer, data)
            self.cpu.mem_write(handle, struct.pack('>I', pointer))
            self.cpu.mem_write(pointer, data)
            pointer += len(data)
        if pointer >= 0xd0000:
            raise ValueError('Prepared sequence budget exceeded')
        self.contact_branches = Counter()

    def reset(self, level):
        super().reset(level)
        self.contacts = []
        self.available = set(self.handles)

    def dispatch(self, cpu, address, size, user):
        stack = cpu.reg_read(self.registers['a7'])
        if address == self.address(10, 0x1b04):
            self.contacts.append(bytes(cpu.mem_read(self.A5 - 0x5056, 62)))
        if address == self.address(10, 0x1bb0) and self.word(-0x34b0) == 2:
            self.contact_branches['first_tile_two'] += 1
        relative = address - self.CODE_BASE
        segment, offset = divmod(relative, 0x10000)
        if segment == 10 and offset in self.BRANCH_CHECKS:
            self.contact_branches[self.BRANCH_CHECKS[offset]] += 1
        if address == self.address(4, 0x2c0c):
            self.events.append(('animate', self.word(-0x5030), self.word(-0x5032)))
        if address in (self.address(17, 0x330e), self.address(4, 0x3098)):
            if address == self.address(17, 0x330e):
                kind, number = struct.unpack('>4sh', cpu.mem_read(stack + 4, 6))
                if kind != b'SEQS':
                    raise AssertionError('Unexpected resource type')
                self.events.append(('resource', number))
            else:
                number = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
                self.events.append(('sequence', number))
            value = self.handles[number] if number in self.available else 0
            cpu.reg_write(self.registers['d0'], value)
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], destination)
            return
        traps = {0x2c32: ('HGetState', b'\xa0\x69'), 0x2c42: ('HLock', b'\xa0\x29'),
                 0x3048: ('HSetState', b'\xa0\x6a')}
        if segment == 4 and offset in traps:
            name, opcode = traps[offset]
            if bytes(cpu.mem_read(address, 2)) != opcode:
                raise AssertionError('Unexpected instruction at a supplied handle trap')
            self.events.append(('handle', name))
            cpu.reg_write(self.registers['d0'], 0)
            cpu.reg_write(self.registers['pc'], address + 2)
            return
        super().dispatch(cpu, address, size, user)

    def verify_sequences(self):
        for handle, pointer, data in self.sequence_bytes.values():
            if (bytes(self.cpu.mem_read(handle, 4)) != struct.pack('>I', pointer)
                    or bytes(self.cpu.mem_read(pointer, len(data))) != data):
                raise AssertionError('Prepared read-only sequence/handle was modified')


def contact_actor(*, x=455, facing=0, row=1, room=1, action=0, alive=-1, armed=0,
                  actor=0, life=3, delta=-1):
    data = bytearray((i * 11 + 5) % 256 for i in range(62))
    for offset, value in ((2, facing), (4, x), (6, 231), (8, actor), (10, 15),
                          (12, 3), (14, row), (16, action), (20, 9), (22, room),
                          (26, armed), (28, alive), (30, life), (34, delta),
                          (36, 0), (38, 47), (40, 99), (52, 0)):
        put_actor(data, offset, value)
    return bytes(data)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince_fork_bytes = (directory / 'Prince.rsrc.bin').read_bytes()
    prince = parse_resource_fork(prince_fork_bytes)
    raw = {n: prince['SEQS'][n]['data'] for n in (47, 48, 71, 93)}
    sequences = {n: struct.unpack('>' + str(len(data) // 2) + 'h', data) for n, data in raw.items()}
    machine = NativeSlideRockContact(parse_resource_fork(executable), raw)
    counts, selections = Counter(), Counter()
    digest = hashlib.sha256()
    guard = bytes((i * 13 + 17) % 256 for i in range(512))
    other_actor = bytes((i * 23 + 7) % 256 for i in range(62))
    level_hashes = {}

    def prepare(level, view, mob, actor, width, *, wrapped=False, available=True):
        machine.reset(level)
        machine.put_word(-0x4fc2, view)
        machine.put_word(-0x3570, width)
        machine.put_word(-0x500e, 12345)
        machine.put_word(-0x481c, -1234)
        machine.put_word(-0x439e, 192)
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *mob))
        machine.cpu.mem_write(machine.A5 - 0x5056, other_actor if wrapped else actor)
        machine.cpu.mem_write(machine.A5 - 0x50d2, actor if wrapped else other_actor)
        machine.cpu.mem_write(machine.BANK - 16, guard)
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
        machine.put_word(-0x4490, 0)
        if not available:
            machine.available.clear()

    def check(level, mob, reader, actor, expected, label, *, wrapped=False, storage=guard,
              count=0, pending=192, phases=None, contacts=None, inputs=None):
        work = expected['actor']
        expected_prince = work if wrapped else other_actor
        if (machine.mob() != mob or machine.events != expected['events']
                or machine.phases != (phases or [])
                or machine.contacts != ([actor] if contacts is None else contacts)
                or machine.actor_inputs != (inputs or [])
                or machine.reads != reader.requests or machine.cache() != reader.cache
                or machine.word(-0x500e) != expected['death_method']
                or machine.word(-0x481c) != expected['remainder']
                or machine.word(-0x439e) != pending or machine.word(-0x4490) != count
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != work
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != expected_prince
                or bytes(machine.cpu.mem_read(machine.BANK - 16, 512)) != storage
                or machine.level_bytes(len(level)) != level or machine.services):
            raise AssertionError(dict(label=label, mob=mob, native_actor=list(
                struct.unpack('>31h', machine.cpu.mem_read(machine.A5 - 0x5056, 62))),
                actor=list(struct.unpack('>31h', work)), events=machine.events,
                expected_events=expected['events'], reads=machine.reads, expected_reads=reader.requests,
                native_remainder=machine.word(-0x481c), remainder=expected['remainder']))
        machine.verify_sequences()
        counts[label] += 1
        selections.update(event[1] for event in expected['events'][machine.checked_events:]
                          if event[0] == 'resource')
        machine.checked_events = len(expected['events'])
        digest.update(work + expected_prince + storage + struct.pack(
            '>8h6h3h', *mob, *machine.cache(), expected['death_method'], expected['remainder'], count))
        digest.update(json.dumps((machine.events, machine.reads)).encode('ascii'))

    level = prince['LEVL'][2009]['data']
    for value in (-32768, -32767, -53, -52, -51, -50, -1, 0, 1, 2, 3, 4,
                  20, 21, 22, 23, 24, 25, 26, 27, 28, 51, 207, 230, 450, 32767):
        machine.reset(level)
        machine.put_word(-0x481c, -1234)
        column, remainder = character_column(value)
        actual = signed_word(machine.call(4, 0x3ad6, (value,)))
        if actual != column or machine.word(-0x481c) != remainder or machine.services:
            raise AssertionError('Native mixed-word character-column arithmetic differs')
        counts['character_column'] += 1
        digest.update(struct.pack('>3h', value, column, remainder))

    def direct(level, mob, actor, width=22, *, label='contact', available=True, wrapped=False):
        if wrapped and not crush_admission_reference(mob, actor, width):
            raise ValueError('The copyback fixture must pass the separately tested contact gate')
        reader = TempleCellReader(level, mob[2])
        expected = contact_reference(mob, actor, width, reader, sequences if available else {})
        prepare(level, mob[2], mob, actor, width, wrapped=wrapped, available=available)
        machine.call(10, 0x16f6 if wrapped else 0x1b04)
        check(level, mob, reader, actor, expected, label, wrapped=wrapped,
              phases=[('crush', mob)] if wrapped else [])

    # Separate first/second columns3/4, including non-wall, tile2 and terminal paths.
    for first, second, control, facing, alive, armed, kind in product(
            (0, 1, 2, 4, 7, 20, 25, 43), (0, 1, 2, 4, 7, 20, 25, 43),
            (-2, 0, 100), (-1, 0), (-1, 0), (0, 1), (0, 4, 7, 8)):
        supplied = bytearray(level)
        struct.pack_into('>H', supplied, 26, first)
        struct.pack_into('>H', supplied, 28, second)
        mob = (225, 236, 1, 0, control, 6, 1, 459)
        actor = contact_actor(x=460, facing=facing, alive=alive, armed=armed, actor=kind)
        direct(supplied, mob, actor, label='controlled_tiles')
    for x, control, alive, delta, life in product(
            (0, 18, 19, 63, 64, 65, 68, 69, 204), (2, 100), (-1, 0), (-8, -3, 0), (0, 3)):
        supplied = bytearray(level)
        for cell in range(30):
            struct.pack_into('>H', supplied, cell * 2, 4)
        mob = (x, 236, 1, 0, control, 6, 1, 459)
        direct(supplied, mob, contact_actor(x=x + 235, alive=alive, delta=delta, life=life),
               label='remainder_and_health_boundaries')
    for width, x, facing, action in product((0, 12, 22, 32), (180, 448, 454, 455, 456, 1000),
                                           (-1, 0, 1), (0, 5)):
        mob = (225, 236, 1, 0, 2, 6, 1, 459)
        direct(level, mob, contact_actor(x=x, facing=facing, action=action), width,
               label='position_action_boundaries')
    for first, facing, armed in product((0, 4), (-1, 0), (0, 1)):
        supplied = bytearray(level)
        for cell in range(30):
            struct.pack_into('>H', supplied, cell * 2, first)
        mob = (225, 236, 1, 0, 2, 6, 1, 459)
        direct(supplied, mob, contact_actor(x=460, facing=facing, armed=armed),
               label='missing_sequence_controls', available=False)

    for number in range(10, 14):
        original = prince['LEVL'][1999 + number]['data']
        level_hashes[str(number)] = hashlib.sha256(original).hexdigest()
        for room, cell in product(range(1, 33), range(30)):
            if struct.unpack_from('>H', original, (room - 1) * 60 + cell * 2)[0] != 25:
                continue
            row, column = divmod(cell, 10)
            for x, control, facing, action, alive, armed in product(
                    (column * 51, max(0, column * 51 - 18)), (-2, 0, 100),
                    (-1, 0), (0, 5), (-1, 0, 1), (0, 1)):
                mob = (x, 116 + row * 120, room, 0, control, 6, row, column * 51)
                actor = contact_actor(x=x + 235, room=room, row=row, facing=facing,
                                      action=action, alive=alive, armed=armed)
                direct(original, mob, actor, label='original_anchor_contacts')

    for facing, first, armed in product((-1, 0), (0, 4), (0, 1)):
        supplied = bytearray(level)
        for cell in range(30):
            struct.pack_into('>H', supplied, cell * 2, first)
        mob = (225, 236, 1, 0, 2, 6, 1, 459)
        direct(supplied, mob, contact_actor(x=460 - (22 if facing else 0), facing=facing, armed=armed),
               label='native_crush_copyback', wrapped=True)

    traces = []
    for first, facing, armed in product((0, 4), (-1, 0), (0, 1)):
        supplied = bytearray(level)
        for cell in range(30):
            struct.pack_into('>H', supplied, cell * 2, first)
        mob = (58, 236, 1, 0, -2, 6, 1, 459)
        prince_actor = contact_actor(x=290 - (22 if facing else 0), facing=facing, armed=armed)
        prepare(supplied, 1, mob, prince_actor, 22, wrapped=True)
        storage = bytearray(guard)
        storage[16:32] = struct.pack('>8h', *mob)
        machine.cpu.mem_write(machine.BANK - 16, bytes(storage))
        machine.put_word(-0x4490, 1)
        reader = TempleCellReader(supplied, 1)
        working = other_actor
        death, remainder, pending = 12345, -1234, 192
        events, phases, contacts, inputs = [], [], [], []
        snapshots = []
        for cycle in range(6):
            step = contact_update_reference(mob, prince_actor, working, 22, reader, sequences,
                                            death_method=death, remainder=remainder, pending=pending)
            mob, prince_actor, working = step['mob'], step['prince'], step['working']
            death, remainder, pending = step['death_method'], step['remainder'], step['pending']
            events.extend(step['events'])
            phases.extend(step['phases'])
            contacts.extend(step['contacts'])
            inputs.extend(step['actor_inputs'])
            if prince_actor != working:
                raise AssertionError('This connected corpus expects contact or retained synchronized actors')
            storage[16:32] = struct.pack('>8h', *mob)
            machine.call(5, 0x29e8)
            expected = dict(actor=working, events=events, death_method=death, remainder=remainder)
            check(supplied, mob, reader, prince_actor, expected, 'connected_native_contact',
                  wrapped=True, storage=storage, count=1, pending=pending,
                  phases=phases, contacts=contacts, inputs=inputs)
            snapshots.append(dict(cycle=cycle, rock=mob, prince=tuple(
                actor_word(prince_actor, i) for i in (4, 6, 10, 16, 26, 28, 30, 34, 38, 40, 52)),
                death_method=death))
        traces.append(dict(tile=first, facing=facing, armed=armed, snapshots=snapshots))
    required = set(machine.BRANCH_CHECKS.values()) | {'first_tile_two'}
    if set(machine.contact_branches) != required:
        raise AssertionError('Declared contact branch coverage is incomplete')
    return dict(
        cases=dict(counts), native_branches=dict(machine.contact_branches),
        sequence_requests=dict(selections), traces=traces, mismatches=0,
        outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
        prince_fork_sha256=hashlib.sha256(prince_fork_bytes).hexdigest(), level_hashes=level_hashes,
        sequence_hashes={str(n): hashlib.sha256(data).hexdigest() for n, data in raw.items()},
        supplied=[
            '17:330e GetResource(SEQS) and4:3098 hGetSequence: prepared handles to actual raw clips47/48/71/93',
            'HGetState/HLock/HSetState: nonmoving prepared handles, zero state/error',
            '5:4d84/5252 sound requests recorded; cue193 query false in connected motion',
        ],
        scope=('Full contact10:1b04-1ca2, health/death primitives, JumpSeq and complete '
               'first AnimChar call with actual four selected clips; native geometry/cache. '
               'Direct bodies, native crush copyback and eight6-update bank traces. '
               'Actor1 conversion, other movement reactions5:3cee/6:1a84, other clips/opcodes, animation playout/cadence, '
               'life-delta application/death lifecycle, rendering and saves/restart are excluded.'),
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
