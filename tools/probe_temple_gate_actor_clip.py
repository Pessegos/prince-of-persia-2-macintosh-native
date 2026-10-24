"""Follow original temple gate hanging reactions through native actor clip updates."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_gate_hanging import NativeGateHanging, actor_fixture
from tools.probe_temple_gate_hanging_animation import hanging_animation_reference
from tools.probe_temple_slide_rock_update import actor_word


def put_actor(actor, offset, value):
    struct.pack_into('>h', actor, offset, signed_word(value))


def clip_reference(actor, sequences, *, vertical=False):
    """Bounded AnimChar model; vertical opts into relative Y and operand-free row decrement."""
    if len(actor) != 62 or actor_word(actor, 8) != 0:
        raise ValueError('Expected a complete type0 actor')
    result = bytearray(actor)
    sequence, cursor = actor_word(result, 38), actor_word(result, 36)
    events = [('animate', sequence, cursor), ('sequence', sequence)]
    if sequence not in sequences:
        return dict(actor=bytes(result), events=events)
    events.extend((('handle', 'HGetState'), ('handle', 'HLock')))
    for _ in range(32):
        words = sequences[sequence]
        if not 0 <= cursor < len(words):
            raise ValueError('Sequence cursor outside the bounded clip domain')
        op = words[cursor]
        cursor += 1
        put_actor(result, 36, cursor)
        if op >= 0:
            put_actor(result, 10, op)
            events.append(('handle', 'HSetState'))
            return dict(actor=bytes(result), events=events)
        if op == -3 and vertical:
            put_actor(result, 14, actor_word(result, 14) - 1)
            continue
        if op not in ((-7, -6, -5, -1) if vertical else (-7, -5, -1)):
            raise ValueError(f'Opcode outside the bounded clip domain: {op}')
        if cursor >= len(words):
            raise ValueError('Truncated clip operand')
        operand = words[cursor]
        cursor += 1
        put_actor(result, 36, cursor)
        if op == -7:
            put_actor(result, 16, operand)
        elif op == -5:
            delta = operand if actor_word(result, 2) == 0 else -operand
            put_actor(result, 4, actor_word(result, 4) + delta)
        elif op == -6:
            put_actor(result, 6, actor_word(result, 6) + operand)
        else:
            # AnimChar's link updates the active sequence, not JumpSeq's source.
            if operand not in sequences or operand == 11:
                raise ValueError('Missing link or context-dependent sequence11 is excluded')
            sequence, cursor = operand, 0
            put_actor(result, 38, sequence)
            put_actor(result, 36, cursor)
            events.extend((('handle', 'HSetState'), ('sequence', sequence),
                           ('handle', 'HGetState'), ('handle', 'HLock')))
    raise ValueError('Bounded clip instruction limit exceeded')


class NativeGateActorClip(NativeGateHanging):
    RANGES = NativeGateHanging.RANGES | {
        4: NativeGateHanging.RANGES[4] + ((0x2bae, 0x2bcc), (0x2c0c, 0x3050), (0x305e, 0x308a)),
    }
    SUPPLIED = {key: value for key, value in NativeGateHanging.SUPPLIED.items()
                if key != (17, 0x330e)}
    HANDLE_TRAPS = {
        0x2c32: ('HGetState', b'\xa0\x69'), 0x2c42: ('HLock', b'\xa0\x29'),
        0x2ed2: ('HSetState', b'\xa0\x6a'), 0x2eea: ('HGetState', b'\xa0\x69'),
        0x2efa: ('HLock', b'\xa0\x29'), 0x3048: ('HSetState', b'\xa0\x6a'),
    }

    def __init__(self, program, sequences):
        super().__init__(program)
        self.sequence_bytes = {}
        pointer = 0xc2000
        for index, (number, data) in enumerate(sorted(sequences.items())):
            handle = 0xc0000 + index * 4
            self.sequence_bytes[number] = (handle, pointer, data)
            self.cpu.mem_write(handle, struct.pack('>I', pointer))
            self.cpu.mem_write(pointer, data)
            pointer += len(data)
        if pointer >= 0xd0000:
            raise ValueError('Prepared sequence budget exceeded')

    def return_value(self, value):
        stack = self.cpu.reg_read(self.registers['a7'])
        self.cpu.reg_write(self.registers['d0'], value)
        self.cpu.reg_write(self.registers['a7'], stack + 4)
        self.cpu.reg_write(self.registers['pc'], struct.unpack('>I', self.cpu.mem_read(stack, 4))[0])

    def dispatch(self, cpu, address, size, user):
        stack = cpu.reg_read(self.registers['a7'])
        if address in (self.address(17, 0x330e), self.address(4, 0x3098)):
            if address == self.address(17, 0x330e):
                kind, number = struct.unpack('>4sh', cpu.mem_read(stack + 4, 6))
                if (kind, number) != (b'SEQS', 47):
                    raise AssertionError('Unexpected JumpSeq resource request')
                self.events.append(('resource', number))
                exists = self.available
            else:
                number = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
                self.events.append(('sequence', number))
                exists = True
            if number not in self.sequence_bytes:
                raise AssertionError(f'Unprepared sequence request: {number}')
            self.return_value(self.sequence_bytes[number][0] if exists else 0)
            return
        if address == self.address(4, 0x2c0c):
            self.events.append(('animate', self.word(-0x5030), self.word(-0x5032)))
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        if segment == 4 and offset in self.HANDLE_TRAPS:
            name, opcode = self.HANDLE_TRAPS[offset]
            if bytes(cpu.mem_read(address, 2)) != opcode:
                raise AssertionError('Unexpected handle trap opcode')
            self.events.append(('handle', name))
            cpu.reg_write(self.registers['d0'], 0)
            cpu.reg_write(self.registers['pc'], address + 2)
            return
        super().dispatch(cpu, address, size, user)

    def verify_sequences(self):
        for handle, pointer, data in self.sequence_bytes.values():
            if (bytes(self.cpu.mem_read(handle, 4)) != struct.pack('>I', pointer)
                    or bytes(self.cpu.mem_read(pointer, len(data))) != data):
                raise AssertionError('Original sequence bytes or supplied handle were modified')


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    raw = {n: resources['SEQS'][n]['data'] for n in (2, 9, 47, 210)}
    sequences = {n: struct.unpack('>' + str(len(data) // 2) + 'h', data) for n, data in raw.items()}
    if sequences[9][:3] != (-7, 2, 91) or sequences[9][3:] != (-1, 210):
        raise ValueError('Unexpected hanging fixture clip9')
    machine = NativeGateActorClip(parse_resource_fork(executable), raw)
    counts, outcomes, events, services, digest = Counter(), Counter(), Counter(), Counter(), hashlib.sha256()
    cache = struct.pack('>6h', 11, 13, 17, 19, 23, 29)
    bank = bytes((i * 17 + 3) % 256 for i in range(160))
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
        raise ValueError('Expected all41 original temple gate anchors')

    for number, original, room, cell in inventory:
        row, column = divmod(cell, 10)
        for (position, phase), facing, actor_room, available, x in product(
                ((3, 1), (60, 4), (180, 3)), (-1, 0), (0, room), (False, True),
                (-32760, 207 + column * 51, 32760)):
            prince = bytearray(actor_fixture(actor_room, row + 1, column, facing, 2))
            for offset, value in ((4, x), (6, row * 120 + 110), (10, 91), (28, -1),
                                  (30, 3), (34, 0), (36, 3), (38, 9), (40, 9)):
                put_actor(prince, offset, value)
            initial = bytes(prince)
            working = bytes((i * 7 + 19) % 256 for i in range(62))
            expected = hanging_animation_reference(position, phase, initial, working, room, cell, available)
            prince, working = expected['prince'], expected['working']
            level = bytearray(original)
            offset = 0x780 + (room - 1) * 120 + cell * 4
            struct.pack_into('>H', level, offset, position)
            expected_level = bytearray(level)
            struct.pack_into('>H', expected_level, offset, expected['foreground'])
            machine.reset(level)
            machine.available = available
            machine.cpu.mem_write(machine.A5 - 0x5056, bytes((i * 7 + 19) % 256 for i in range(62)))
            machine.cpu.mem_write(machine.A5 - 0x50d2, initial)
            machine.cpu.mem_write(machine.A5 - 0x34b0, cache)
            machine.cpu.mem_write(machine.A5 - 0x448e, bank)
            machine.cpu.mem_write(machine.A5 - 0x43ee, struct.pack('>4h', cell, room, phase, 4))
            machine.put_word(-0x4fc2, room)
            machine.put_word(-0x5008, 4321)
            expected_events = list(expected['events'])

            def compare(label):
                actual_prince = bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62))
                actual_working = bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62))
                service_names = {'sound': 'gate_sound', 'redraw': 'gate_redraw', 'audio': 'audio_request'}
                expected_services = Counter(service_names[e[0]] for e in expected_events if e[0] in service_names)
                if (actual_prince != prince or actual_working != working or machine.events != expected_events
                        or machine.services != expected_services
                        or machine.level_bytes(len(level)) != expected_level
                        or bytes(machine.cpu.mem_read(machine.A5 - 0x34b0, 12)) != cache
                        or bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)) != bank
                        or struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x43ee, 8)) !=
                            (cell, room, expected['phase'], 4)
                        or machine.word(-0x5008) != 4321):
                    raise AssertionError(dict(label=label, anchor=(number, room, cell),
                                              inputs=(position, phase, facing, actor_room, available, x),
                                              native_actor=struct.unpack('>31h', actual_working),
                                              expected_actor=struct.unpack('>31h', working),
                                              actual_events=machine.events, expected_events=expected_events,
                                              actual_services=machine.services, expected_services=expected_services))
                machine.verify_sequences()
                counts[label] += 1
                digest.update(actual_prince + actual_working + bytes(expected_level))
                digest.update(json.dumps(expected_events).encode('ascii'))

            machine.call(5, 0x0cd6, (0,))
            compare('gate')
            selected = actor_word(prince, 38) == 47
            outcomes['selected47' if selected else 'kept_hang9'] += 1
            for step in range(8):
                machine.call(4, 0x4b02)
                working = prince
                expected_events.append(('load_kid',))
                compare('load_kid')
                animated = clip_reference(working, sequences)
                working = animated['actor']
                expected_events.extend(animated['events'])
                machine.call(4, 0x2c0c)
                compare('animate')
                outcomes[f'active{actor_word(working, 38)}_mode{actor_word(working, 16)}'] += 1
                if selected and step == 3:
                    if (actor_word(working, 38), actor_word(working, 40), actor_word(working, 16),
                            actor_word(working, 4)) != (2, 47, 0, signed_word(x + 16)):
                        raise AssertionError('Selected47 must reach idle without changing its selected source')
                # This is an inline copy fragment, not a callable function:
                # stop before StopGate's unrelated stack-frame epilogue.
                machine.call(5, 0x1516, stop=(5, 0x1528))
                prince = working
                expected_events.append(('save_kid',))
                compare('save_kid')
            events.update(e[0] for e in expected_events)
            services.update(machine.services)
    return dict(cases=dict(counts), traces=counts['gate'], outcomes=dict(outcomes), events=dict(events),
                services=dict(services), mismatches=0, outputs_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                sequence_sha256={str(n): hashlib.sha256(data).hexdigest() for n, data in raw.items()},
                level_sha256={str(n): hashlib.sha256(resources['LEVL'][1999 + n]['data']).hexdigest()
                              for n in range(10, 14)},
                supplied_services=['5:3828 gate cue request', '5:0fe6 redraw request', '5:4d84 audio request',
                                   '17:330e JumpSeq47 existence/missing control and prepared resource handle',
                                   '4:3098 hGetSequence prepared handles for original SEQS2/9/47/210',
                                   'Memory Manager HGetState/HLock/HSetState, returning state0'],
                scope='Native type4 gate -> StopGate/LoadKid/JumpSeq47/copyback followed by8 supplied '
                      'LoadKid/AnimChar/inline5:1516-1526 copyback updates, stopped before its epilogue. '
                      'Full actor bytes, gate/cache/bank invariants and '
                      'event order checked at each call. Supplied type0 hanging fixture, facing/room/X '
                      'and availability controls, all41 anchors. No full FrameAdv/GenCtrl/physics, '
                      'reachable actor placements, fall/collision/death, audio/pixels, saves or runtime integration.')


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
