"""Execute temple gate TROB steps with sound/drawing/LoadKid/relief endpoints supplied."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules
from tools.probe_temple_plate_release import NativePlateRelease


CLOSE_STEPS = (0, 0, 0, 20, 40, 60, 80, 100, 120)
OPEN_STEPS = (-1, -4, 4, 4)


def gate_animation_reference(foreground, phase, relief=False, relief_countdown=1234):
    if not 0 <= foreground <= 65535 or phase not in range(-1, 9):
        raise ValueError('Expected foreground word and bounded temple gate phase -1..8')
    position = foreground & 255
    output_phase, output_foreground, events = phase, foreground, []

    def redraw():
        events.append(('redraw', output_foreground, output_phase))

    def stop():
        nonlocal output_phase
        output_phase = -1
        events.extend((('sound', 0x112), ('load_kid',)))

    if phase >= 4:
        output_phase = min(8, phase + 1)
        position -= CLOSE_STEPS[output_phase]
        if position <= 0:
            position = 0
            events.append(('relief_check',))
            if relief:
                relief_countdown = 4
            events.append(('sound', 0x113))
            output_phase = -1
    elif phase >= 0:
        if position == 255:
            stop()
        else:
            position += OPEN_STEPS[phase]
            if phase <= 1:
                if position <= 0:
                    position = 0
                    stop()
                elif position < 184:
                    events.append(('sound', 0x110))
                    output_phase = 1
            elif position < 184:
                if position & 7 == 0:
                    events.append(('sound', 0x110))
            elif phase == 2:
                redraw()
                position, output_phase = 237, 0
                events.append(('sound', 0x111))
            else:
                position = 255
                stop()
    if phase >= 0:
        output_foreground = ((foreground & 0xff00) + position) & 65535
    if position <= 184:
        redraw()
    return dict(foreground=output_foreground, phase=output_phase, relief_countdown=relief_countdown, events=events)


class NativeGateAnimation(NativeRules):
    RANGES = NativePlateRelease.RANGES | {
        4: ((0x322a, 0x3262),),
        5: NativePlateRelease.RANGES[5] + ((0x0d8a, 0x0da2), (0x14a8, 0x152e),
                                         (0x153c, 0x15a2), (0x41aa, 0x445c)),
    }
    SUPPLIED = {(5, 0x3828): 'gate_sound', (5, 0x0fe6): 'gate_redraw',
                (4, 0x4b02): 'load_kid', (5, 0x4766): 'relief_check'}

    def reset(self, level):
        super().reset(level)
        self.events = []
        self.relief = False

    def dispatch(self, cpu, address, size, user):
        if address == self.address(5, 0x3828):
            stack = cpu.reg_read(self.registers['a7'])
            self.events.append(('sound', struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]))
        elif address == self.address(5, 0x0fe6):
            self.events.append(('redraw', self.word(-0x4818) & 65535, self.word(-0x43ea)))
        elif address == self.address(4, 0x4b02):
            self.events.append(('load_kid',))
        elif address == self.address(5, 0x4766):
            self.events.append(('relief_check',))
        super().dispatch(cpu, address, size, user)
        if address == self.address(5, 0x4766) and (5, 0x4766) in self.SUPPLIED:
            cpu.reg_write(self.registers['d0'], int(self.relief))


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(executable)
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeGateAnimation(program)
    if 0x0d0c + struct.unpack_from('>h', program['CODE'][5]['data'], 0x0d0e)[0] != 0x0d8a:
        raise ValueError('Unexpected native type4 TROB dispatch')
    inventory = []
    for number in range(10, 14):
        level = resources['LEVL'][1999 + number]['data']
        if struct.unpack_from('>3h', level, 0x2186)[::2] != (2, number):
            raise ValueError('Expected a temple header')
        for room in range(1, struct.unpack_from('>h', level, 0x2180)[0] + 1):
            for cell in range(30):
                if struct.unpack_from('>h', level, (room - 1) * 60 + cell * 2)[0] == 4:
                    inventory.append((number, level, room, cell))
    if len(inventory) != 41:
        raise ValueError('Expected41 header-admitted original temple gate cells')
    machine.reset(inventory[0][1])
    if (tuple(machine.word(-0x45ee + i * 2) for i in range(9)) != CLOSE_STEPS
            or tuple(machine.word(-0x45dc + i * 2) for i in range(4)) != OPEN_STEPS):
        raise ValueError('Unexpected native gate-step DATA tables')
    counts, services, outcomes, digest = Counter(), Counter(), Counter(), hashlib.sha256()
    current = bytearray((i * 11 + 3) % 256 for i in range(62))
    saved = bytearray((i * 7 + 17) % 256 for i in range(62))
    struct.pack_into('>h', current, 16, 0)
    struct.pack_into('>h', saved, 22, 0)
    bank = bytes((i * 19 + 7) % 256 for i in range(160))
    cache = struct.pack('>6h', 11, 13, 17, 19, 23, 29)

    def compare(original, room, cell, foreground, phase, relief, label):
        level = bytearray(original)
        offset = 0x780 + (room - 1) * 120 + cell * 4
        struct.pack_into('>H', level, offset, foreground)
        state = gate_animation_reference(foreground, phase, relief)
        expected_level = bytearray(level)
        struct.pack_into('>H', expected_level, offset, state['foreground'])
        machine.reset(level)
        machine.relief = relief
        machine.cpu.mem_write(machine.A5 - 0x43ee, struct.pack('>4h', cell, room, phase, 4))
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(current))
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(saved))
        machine.cpu.mem_write(machine.A5 - 0x448e, bank)
        machine.cpu.mem_write(machine.A5 - 0x34b0, cache)
        machine.put_word(-0x4fc2, room)
        machine.put_word(-0x43e6, 19)
        machine.put_word(-0x4490, 17)
        machine.put_word(-0x4f9e, 4321)
        machine.put_word(-0x5008, 1234)
        machine.call(5, 0x0cd6, (0,))
        actual = dict(foreground=machine.word(-0x4818) & 65535, phase=machine.word(-0x43ea),
                      relief_countdown=machine.word(-0x5008), events=machine.events)
        expected_services = Counter({'sound': 'gate_sound', 'redraw': 'gate_redraw',
                                     'load_kid': 'load_kid', 'relief_check': 'relief_check'}[e[0]]
                                    for e in state['events'])
        if (actual != state or machine.services != expected_services
                or machine.level_bytes(len(level)) != expected_level
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != current
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != saved
                or bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)) != bank
                or bytes(machine.cpu.mem_read(machine.A5 - 0x34b0, 12)) != cache
                or machine.word(-0x43e6) != 19 or machine.word(-0x4490) != 17
                or machine.word(-0x4f9e) != 4321
                or struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x43ee, 8)) !=
                    (cell, room, state['phase'], 4)):
            raise AssertionError(dict(label=label, source=(room, cell), input=(foreground, phase, relief),
                                      actual=actual, expected=state, services=machine.services))
        counts[label] += 1
        services.update(machine.services)
        outcomes[f'phase_{state["phase"]}'] += 1
        digest.update(bytes(expected_level))
        digest.update(json.dumps([actual, machine.services]).encode('ascii'))

    for number, level, room, cell in inventory:
        foreground = struct.unpack_from('>H', level, 0x780 + (room - 1) * 120 + cell * 4)[0]
        for phase, relief in product(range(-1, 9), (False, True)):
            compare(level, room, cell, foreground, phase, relief, 'original-gate-anchor')
    _number, level, room, cell = inventory[0]
    for position, phase, relief in product(range(256), range(-1, 9), (False, True)):
        compare(level, room, cell, position, phase, relief, 'supplied-all-position-bytes')
    for high, position, phase, relief in product((0x300, 0xff00), (0, 1, 60, 120, 183, 184, 185, 237, 255),
                                                 range(-1, 9), (False, True)):
        compare(level, room, cell, high | position, phase, relief, 'supplied-decoration')
    return dict(cases=dict(counts), original_gates=len(inventory), mismatches=0, services=dict(services),
                outcomes=dict(outcomes), outputs_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                level_sha256={str(n): hashlib.sha256(resources['LEVL'][1999 + n]['data']).hexdigest()
                              for n in range(10, 14)},
                supplied_services=['5:3828 gate sound request', '5:0fe6 redraw request',
                                   '4:4b02 LoadKid: supplied no-op', '5:4766 level4 relief check: supplied bool'],
                scope='Native AnimTrob type4/temple5:41aa gate motion, real DATA step tables and StopGate body '
                      'with non-hanging supplied actors. LoadKid and level4 relief return are supplied; '
                      'true is a forced branch control, not a reachable temple relief result. No real crush '
                      'consequences, actor hanging reactions, bank compaction, audio/drawing, '
                      'full FrameAdv, pixels, saves or temple integration.')


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
