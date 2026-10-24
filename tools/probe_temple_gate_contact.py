"""Recover native gate-contact routing with real cells, admission and JumpSeq50."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_admission import admission_reference
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import COLD_CACHE, NativeTempleGateStanding, StandingCellReader
from tools.probe_temple_slide_rock_update import actor_word


SEQUENCE_HANDLE = 0xc0000
OVERLAP_BANKS = (-0x355e, -0x354a)


class ContactCellReader(StandingCellReader):
    """Cave controls allow only live, in-room reads; undefined cave tiles are excluded."""

    def __init__(self, level, view_room):
        environment = struct.unpack_from('>H', level, 0x2186)[0]
        self.cave_control = environment == 3
        if self.cave_control:
            # The inherited temple constructor validates its environment. Only
            # initialization uses this copy; every actual lookup sees the input.
            temple_header = bytearray(level)
            struct.pack_into('>H', temple_header, 0x2186, 2)
            super().__init__(temple_header, view_room)
            self.level = level
        else:
            super().__init__(level, view_room)

    def read(self, room, column, row):
        maximum = struct.unpack_from('>H', self.level, 0x2180)[0]
        if self.cave_control and not (1 <= room <= maximum and 0 <= column <= 9 and 0 <= row <= 2):
            raise ValueError('Undefined or traversed cave controls are outside this probe')
        return super().read(room, column, row)


def contact_reference(actor, reader, overlap, distance, *, sequence_available=True, mark=73):
    if (len(actor) != 62 or actor_word(actor, 2) not in (-1, 0)
            or len(overlap) != 2 or any(len(bank) != 10 for bank in overlap)
            or not -32768 <= distance <= 32767):
        raise ValueError('Outside the bounded gate-contact fixture domain')
    result = bytearray(actor)
    events = []
    room, column, row = (actor_word(actor, offset) for offset in (22, 12, 14))
    current = reader.read(room, column, row)

    def finish():
        return dict(actor=bytes(result), events=events, mark=mark)

    if actor_word(actor, 28) >= 0 or actor_word(actor, 40) == 118:
        return finish()
    step = 1 if actor_word(actor, 2) == -1 else -1
    if current != 4:
        for col in (column + step, column - step):
            if reader.read(room, col, row) == 4:
                break
        else:
            return finish()
    number = struct.unpack_from('>H', reader.level, 0x218a)[0]
    if reader.cache[3] == 9 and number == 8:
        return finish()
    col, foreground = reader.cache[4], reader.cache[1] & 65535
    if not 0 <= col <= 9:
        raise ValueError('Gate must resolve to a live column')
    if (overlap[0][col] & overlap[1][col]) != 255:
        return finish()
    environment = struct.unpack_from('>H', reader.level, 0x2186)[0]
    if not admission_reference(actor, foreground, environment):
        return finish()
    if actor_word(actor, 10) != 109 and foreground != 0 and actor_word(actor, 26) != 1:
        if actor_word(actor, 40) != 50:
            events.append(('resource', 50))
            if sequence_available:
                for offset, value in ((36, 0), (38, 50), (40, 50)):
                    put_actor(result, offset, value)
            events.append(('distance',))
            if distance < 25:
                delta = signed_word(distance - 25)
                if actor_word(actor, 2) == -1:
                    delta = signed_word(-delta)
                put_actor(result, 4, actor_word(actor, 4) + delta)
    elif environment == 3 and foreground & 255 and actor_word(actor, 26) != 1:
        events.append(('cave_contact',))
    else:
        if actor_word(actor, 8) != 1:
            mark = 1
        events.append(('eject',))
    return finish()


class NativeTempleGateContact(NativeTempleGateStanding):
    RANGES = dict(NativeTempleGateStanding.RANGES)
    RANGES[4] += ((0x35a6, 0x35b8), (0x5a70, 0x5a7e), (0x5b0e, 0x5ba8), (0x60e4, 0x61ec))
    RANGES[6] = ((0x0006, 0x0098),)

    def reset(self, level):
        super().reset(level)
        self.events, self.distance, self.sequence_available = [], 25, True

    def dispatch(self, cpu, address, size, user):
        supplied = {(4, 0x5eae): 'distance', (4, 0x6202): 'eject', (6, 0x2ac8): 'cave_contact'}
        key = divmod(address - self.CODE_BASE, 0x10000)
        if key == (17, 0x330e) or key in supplied:
            stack = cpu.reg_read(self.registers['a7'])
            if key == (17, 0x330e):
                kind, number = struct.unpack('>4sh', cpu.mem_read(stack + 4, 6))
                if (kind, number) != (b'SEQS', 50):
                    raise AssertionError('Unexpected contact sequence lookup')
                self.events.append(('resource', number))
                value = SEQUENCE_HANDLE if self.sequence_available else 0
            else:
                name = supplied[key]
                self.events.append((name,))
                value = self.distance if name == 'distance' else 0
            cpu.reg_write(self.registers['d0'], value & 0xffffffff)
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])
            return
        super().dispatch(cpu, address, size, user)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeTempleGateContact(parse_resource_fork(executable))
    counts, outcomes, events, digest = Counter(), Counter(), Counter(), hashlib.sha256()
    sequence = prince['SEQS'][50]['data']
    sequence_fixture = struct.pack('>I', SEQUENCE_HANDLE + 4) + sequence
    machine.cpu.mem_write(SEQUENCE_HANDLE, sequence_fixture)

    def check(level, actor, overlap, distance, available, label):
        machine.reset(level)
        machine.distance, machine.sequence_available = distance, available
        machine.put_word(-0x4fc2, actor_word(actor, 22))
        machine.put_word(-0x4f9e, 73)
        machine.cpu.mem_write(machine.A5 - 0x5056, actor)
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(range(62)))
        machine.cpu.mem_write(machine.A5 - 0x448e, bytes(range(160)))
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', *COLD_CACHE))
        for offset, bank in zip(OVERLAP_BANKS, overlap):
            machine.cpu.mem_write(machine.A5 + offset, struct.pack('>10H', *bank))
        before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        reader = ContactCellReader(level, actor_word(actor, 22))
        expected = contact_reference(actor, reader, overlap, distance, sequence_available=available)
        machine.call(4, 0x60e4)
        before[len(machine.data) - 0x5056:len(machine.data) - 0x5056 + 62] = expected['actor']
        struct.pack_into('>h', before, len(machine.data) - 0x4f9e, expected['mark'])
        struct.pack_into('>6h', before, len(machine.data) - 0x34b0, *reader.cache)
        if reader.pointer_room is not None:
            room = reader.pointer_room
            struct.pack_into('>II', before, len(machine.data) - 0x4824,
                             machine.LEVEL + 0x780 + (room - 1) * 120,
                             machine.LEVEL + (room - 1) * 60)
        after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        if (after != before or machine.events != expected['events'] or machine.reads != reader.requests
                or machine.level_bytes(len(level)) != level or machine.services
                or bytes(machine.cpu.mem_read(SEQUENCE_HANDLE, len(sequence_fixture))) != sequence_fixture):
            raise AssertionError(dict(label=label, actor=actor.hex(), events=machine.events, expected=expected,
                                      reads=machine.reads, expected_reads=reader.requests,
                                      changed=[(hex(i - len(machine.data)), a, b)
                                               for i, (a, b) in enumerate(zip(before, after)) if a != b]))
        counts[label] += 1
        outcome = 'eject' if ('eject',) in expected['events'] else (
            'cave_contact' if ('cave_contact',) in expected['events'] else (
                'select50' if ('resource', 50) in expected['events'] else 'no_response'))
        outcomes[outcome] += 1
        events.update(e[0] for e in expected['events'])
        digest.update(bytes(level) + expected['actor'] + struct.pack('>h6h', expected['mark'], *reader.cache))
        digest.update(json.dumps((reader.requests, expected['events'])).encode('ascii'))

    gates = 0
    for number in range(10, 14):
        original = prince['LEVL'][1999 + number]['data']
        for room, cell in product(range(1, 33), range(30)):
            if struct.unpack_from('>h', original, (room - 1) * 60 + cell * 2)[0] != 4:
                continue
            gates += 1
            row, column = divmod(cell, 10)
            for facing, relative_col, foreground, source, armed, (pose, distance), available in product(
                    (-1, 0), (-1, 0, 1), (0, 1, 96, 100, 0x8100), (9, 50, 118), (0, 1),
                    ((1, -1), (1, 24), (1, 25), (109, 26)), (True, False)):
                level = bytearray(original)
                struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, foreground)
                actor = bytearray(actor_fixture(room, row, column + relative_col, facing, 0))
                for offset, value in ((4, column * 51 + 258), (10, pose), (26, armed), (28, -1),
                                      (40, source), (42, 20), (46, 68)):
                    put_actor(actor, offset, value)
                overlap = ((255,) * 10, (255,) * 10)
                check(level, bytes(actor), overlap, distance, available, 'original_gate_anchors')

    # Isolate early exits, exact overlap equality, priority, and cave-only routing.
    for environment, number, room, alive, kind, pair, source, pose, foreground in product(
            (2, 3), (8, 10), (8, 9), (-1, 0, 1), (0, 1),
            ((255, 255), (511, 511), (511, 255), (127, 255)), (9, 68, 118), (1, 109), (0, 1)):
        level = bytearray(prince['LEVL'][2009]['data'])
        struct.pack_into('>H', level, 0x2186, environment)
        struct.pack_into('>H', level, 0x218a, number)
        struct.pack_into('>H', level, (room - 1) * 60 + 14 * 2, 4)
        struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + 14 * 4, foreground)
        actor = bytearray(actor_fixture(room, 1, 4, -1, 0))
        for offset, value in ((4, 462), (8, kind), (10, pose), (26, 0), (28, alive),
                              (40, source), (42, 20), (46, 68)):
            put_actor(actor, offset, value)
        check(level, bytes(actor), ((pair[0],) * 10, (pair[1],) * 10), 24, True, 'routing_controls')
    for facing, gate_positions, distance in product((-1, 0), ((0, 100), (100, 0), (1, 1)),
                                           (-32768, -1, 24, 25, 26, 32767)):
        level = bytearray(prince['LEVL'][2009]['data'])
        level[:60] = bytes(60)
        for col, foreground in zip((3, 5), gate_positions):
            struct.pack_into('>H', level, (10 + col) * 2, 4)
            struct.pack_into('>H', level, 0x780 + (10 + col) * 4, foreground)
        actor = bytearray(actor_fixture(1, 1, 4, facing, 0))
        for offset, value in ((4, 462), (10, 1), (26, 0), (28, -1), (40, 9), (42, 20), (46, 68)):
            put_actor(actor, offset, value)
        check(level, bytes(actor), ((255,) * 10, (255,) * 10), distance, True, 'neighbor_priority')
    for number in (8, 10):
        level = bytearray(prince['LEVL'][2009]['data'])
        struct.pack_into('>H', level, 0x218a, number)
        struct.pack_into('>H', level, 0x2080 + 7 * 8 + 2, 9)
        struct.pack_into('>H', level, 7 * 60 + 19 * 2, 0)
        struct.pack_into('>H', level, 8 * 60 + 10 * 2, 4)
        struct.pack_into('>H', level, 0x780 + 8 * 120 + 10 * 4, 1)
        actor = bytearray(actor_fixture(8, 1, 9, -1, 0))
        for offset, value in ((4, 717), (10, 1), (26, 0), (28, -1), (40, 9), (42, 20), (46, 68)):
            put_actor(actor, offset, value)
        check(level, bytes(actor), ((255,) * 10, (255,) * 10), 24, True, 'resolved_room9')
    return dict(comparisons=sum(counts.values()), original_gate_anchors=gates, cases=dict(counts),
                outcomes=dict(outcomes), events=dict(events), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                sequence50_sha256=hashlib.sha256(sequence).hexdigest(), outputs_sha256=digest.hexdigest(),
                supplied=['17:330e SEQS50 lookup (original handle fixture or controlled missing resource)',
                          '4:5eae distance fixture;4:6202 ejection and6:2ac8 cave response log-only',
                          'Two10-word overlap banks and visible actor rectangle are supplied'],
                scope='Actual CheckGateForKid, current/front/opposite reads, admission, JumpSeq50 '
                      'and contact mark4:5a70. No distance/ejection internals, overlap construction, '
                      'AnimChar, crush damage/death, world loop or runtime changes.')


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
