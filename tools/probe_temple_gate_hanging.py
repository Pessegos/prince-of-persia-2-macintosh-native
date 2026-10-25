"""Recover StopGate's hanging sequence selection and the separate hanging cue."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_gate_services import NativeGateServices
from tools.probe_temple_slide_rock_update import actor_word


def first_in_row(row):
    if not -1 <= row <= 3:
        raise ValueError('Only the bounded FirstInRow table indexes -1..3 are covered')
    return row * 10 if row >= 0 else -1


def validate_actor(actor, cell):
    if len(actor) != 62 or actor_word(actor, 8) != 0 or not 0 <= cell < 30:
        raise ValueError('Expected a full type0 actor and a gate cell0..29')


def stop_actor_reference(actor, cell, stopped_position, available=True):
    validate_actor(actor, cell)
    working = bytearray(actor)
    events = [('sound', 0x112), ('load_kid',)]
    above_cell = signed_word(first_in_row(actor_word(actor, 14) - 1) + actor_word(actor, 12))
    if (above_cell == cell and actor_word(actor, 2) == -1 and actor_word(actor, 16) == 2
            and stopped_position == 0):
        events.extend((('jump_seq', 47), ('resource', 47)))
        if available:
            for offset, value in ((36, 0), (38, 47), (40, 47)):
                struct.pack_into('>h', working, offset, value)
        events.append(('save_kid',))
    return dict(working=bytes(working), prince=bytes(working), events=events, phase=-1)


def hanging_cue_reference(actor, room, cell):
    validate_actor(actor, cell)
    if room != actor_word(actor, 22) or actor_word(actor, 16) not in (2, 6):
        return []
    actor_cell = signed_word(first_in_row(actor_word(actor, 14)) + actor_word(actor, 12))
    return [('audio', 29)] if actor_cell in (cell + 10, cell + 11) else []


class NativeGateHanging(NativeGateServices):
    RANGES = NativeGateServices.RANGES | {6: ((0x0006, 0x0098),)}
    SUPPLIED = NativeGateServices.SUPPLIED | {(17, 0x330e): 'resource_exists', (5, 0x4d84): 'audio_request'}

    def reset(self, level):
        super().reset(level)
        self.available = True

    def dispatch(self, cpu, address, size, user):
        stack = cpu.reg_read(self.registers['a7'])
        if address == self.address(6, 0x0006):
            sequence = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            if sequence != 47:
                raise AssertionError('Unexpected StopGate sequence request')
            self.events.append(('jump_seq', sequence))
        elif address == self.address(17, 0x330e):
            kind, sequence = struct.unpack('>4sh', cpu.mem_read(stack + 4, 6))
            if (kind, sequence) != (b'SEQS', 47):
                raise AssertionError('Unexpected resource lookup')
            self.events.append(('resource', sequence))
        elif address == self.address(5, 0x1516):
            self.events.append(('save_kid',))
        elif address == self.address(5, 0x4d84):
            self.events.append(('audio', struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]))
        super().dispatch(cpu, address, size, user)
        if address == self.address(17, 0x330e):
            # JumpSeq47/type0 tests only handle existence; it never dereferences it.
            cpu.reg_write(self.registers['d0'], 0xc0000 if self.available else 0)


def actor_fixture(room, row, column, facing, action):
    actor = bytearray((i * 11 + 5) % 256 for i in range(62))
    for offset, value in ((2, facing), (8, 0), (12, column), (14, row), (16, action),
                          (22, room), (36, 123), (38, 124), (40, 125)):
        struct.pack_into('>h', actor, offset, value)
    return bytes(actor)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    if not resources['SEQS'][47]['data']:
        raise ValueError('The original SEQS47 must exist')
    machine = NativeGateHanging(parse_resource_fork(executable))
    inventory = []
    for number in range(10, 14):
        level = resources['LEVL'][1999 + number]['data']
        if struct.unpack_from('>3h', level, 0x2186)[::2] != (2, number):
            raise ValueError('Expected original temple headers')
        for room in range(1, struct.unpack_from('>h', level, 0x2180)[0] + 1):
            for cell in range(30):
                if struct.unpack_from('>h', level, (room - 1) * 60 + cell * 2)[0] == 4:
                    inventory.append((number, level, room, cell))
    if len(inventory) != 41:
        raise ValueError('Expected41 original temple gate anchors')
    machine.reset(inventory[0][1])
    if tuple(machine.word(-0x350e + index * 2) for index in range(4)) != (0, 10, 20, 30):
        raise ValueError('Unexpected native FirstInRow DATA table')
    counts, events, services, digest = Counter(), Counter(), Counter(), hashlib.sha256()
    working = bytes((i * 7 + 19) % 256 for i in range(62))
    cache = struct.pack('>6h', 11, 13, 17, 19, 23, 29)
    bank = bytes((i * 17 + 3) % 256 for i in range(160))

    def compare(level, room, cell, actor, operation, position=0, available=True):
        machine.reset(level)
        machine.available = available
        machine.cpu.mem_write(machine.A5 - 0x5056, working)
        machine.cpu.mem_write(machine.A5 - 0x50d2, actor)
        machine.cpu.mem_write(machine.A5 - 0x34b0, cache)
        machine.cpu.mem_write(machine.A5 - 0x448e, bank)
        scratch = (cell, room, 7, 4)
        machine.cpu.mem_write(machine.A5 - 0x43ee, struct.pack('>4h', *scratch))
        machine.put_word(-0x5008, 4321)
        if operation == 'stop':
            expected = stop_actor_reference(actor, cell, position, available)
            machine.call(5, 0x14a8, (position,))
        elif operation == 'cue':
            expected = dict(working=working, prince=actor, events=hanging_cue_reference(actor, room, cell), phase=7)
            machine.call(5, 0x153c)
        else:
            raise ValueError('Unexpected gate helper operation')
        actual = dict(working=bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)),
                      prince=bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)),
                      events=machine.events, phase=machine.word(-0x43ea))
        service_names = {'sound': 'gate_sound', 'audio': 'audio_request', 'resource': 'resource_exists'}
        expected_services = Counter(service_names[event[0]] for event in expected['events'] if event[0] in service_names)
        if (actual != expected or machine.services != expected_services
                or machine.level_bytes(len(level)) != level
                or bytes(machine.cpu.mem_read(machine.A5 - 0x34b0, 12)) != cache
                or bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)) != bank
                or struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x43ee, 8)) !=
                    (cell, room, expected['phase'], 4) or machine.word(-0x5008) != 4321):
            raise AssertionError(dict(operation=operation, inputs=(room, cell, position, available),
                                      actual=actual, expected=expected, services=machine.services))
        counts[operation] += 1
        events.update(event[0] for event in expected['events'])
        services.update(machine.services)
        digest.update(level + actual['working'] + actual['prince'] + json.dumps(actual['events']).encode('ascii'))

    for _number, level, room, cell in inventory:
        row, column = divmod(cell, 10)
        for facing, action, delta, position, available, actor_room in product(
                (-1, 0, 1), (0, 2, 6), (-1, 0, 1), (0, 56, 255), (False, True), (0, room)):
            actor = actor_fixture(actor_room, row + 1, column + delta, facing, action)
            compare(level, room, cell, actor, 'stop', position, available)
        for action, delta, actor_room in product((0, 2, 6), (-1, 0, 1, 2), (0, room)):
            actor = actor_fixture(actor_room, row + 1, column + delta, 0, action)
            compare(level, room, cell, actor, 'cue')
    return dict(cases=dict(counts), events=dict(events), services=dict(services), mismatches=0,
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
                sequence47_sha256=hashlib.sha256(resources['SEQS'][47]['data']).hexdigest(),
                level_sha256={str(n): hashlib.sha256(resources['LEVL'][1999 + n]['data']).hexdigest()
                              for n in range(10, 14)},
                supplied_services=['5:3828 gate cue request', '5:4d84 audio request',
                                   '17:330e SEQS47 existence/non-null handle; missing-resource controls supplied'],
                scope='Native StopGate, LoadKid and JumpSeq47 selection/cursor reset plus separate5:153c '
                      'hanging cue admission, supplied type0 actors at all41 original gate anchors. '
                      'No AnimChar/clip execution, actual fall/collision/death, FrameAdv cadence, '
                      'full mixed lifetimes, sound playback, saves/reset or runtime integration.')


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
