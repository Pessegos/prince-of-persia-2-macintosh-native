"""Replace supplied LoadKid/relief endpoints with their original native bodies."""

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_gate_animation import NativeGateAnimation, gate_animation_reference


@dataclass(frozen=True)
class ReliefActor:
    room: int
    column: int
    row: int
    alive: int = -1


def relief_reference(level_number, countdown, room, cell, prince, opponents):
    if not 0 <= cell < 30 or not 0 <= room <= 32 or len(opponents) > 3:
        raise ValueError('Expected a bounded room/cell and at most three supplied opponents')
    if level_number != 4 or countdown == -2 or room == 0 or not opponents:
        return False
    row, column = divmod(cell, 10)
    if (room != prince.room or row != prince.row or abs(column - prince.column) >= 5):
        return False
    found = False
    for opponent in opponents:
        if opponent.row != row or opponent.room != prince.room or opponent.alive >= 0:
            continue
        far_side = opponent.column <= column if column < prince.column else opponent.column > column
        if not far_side:
            return False
        found = True
    return found


def relief_actor_bytes(actor, seed):
    data = bytearray((i * seed + 17) % 256 for i in range(62))
    for offset, value in ((12, actor.column), (14, actor.row), (22, actor.room), (28, actor.alive)):
        struct.pack_into('>h', data, offset, value)
    return bytes(data)


class NativeGateServices(NativeGateAnimation):
    RANGES = NativeGateAnimation.RANGES | {
        4: NativeGateAnimation.RANGES[4] + ((0x4b02, 0x4b14),),
        5: NativeGateAnimation.RANGES[5] + ((0x4766, 0x489c),),
    }
    SUPPLIED = {key: value for key, value in NativeGateAnimation.SUPPLIED.items()
                if key not in ((4, 0x4b02), (5, 0x4766))}


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(executable)
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeGateServices(program)
    inventory = []
    for number in range(10, 14):
        level = resources['LEVL'][1999 + number]['data']
        if struct.unpack_from('>3h', level, 0x2186)[::2] != (2, number):
            raise ValueError('Expected original temple level headers')
        for room in range(1, struct.unpack_from('>h', level, 0x2180)[0] + 1):
            for cell in range(30):
                if struct.unpack_from('>h', level, (room - 1) * 60 + cell * 2)[0] == 4:
                    inventory.append((number, level, room, cell))
    if len(inventory) != 41:
        raise ValueError('Expected all41 original temple gate anchors')
    counts, outcomes, services, digest = Counter(), Counter(), Counter(), hashlib.sha256()
    current = bytes((i * 11 + 3) % 256 for i in range(62))
    unused_bank = bytes((i * 19 + 7) % 256 for i in range(186))
    cache = struct.pack('>6h', 11, 13, 17, 19, 23, 29)
    trobs = bytes((i * 23 + 5) % 256 for i in range(160))

    def compare_relief(original, number, countdown, room, cell, prince, opponents, label):
        level = bytearray(original)
        struct.pack_into('>h', level, 0x218a, number)
        if room:
            struct.pack_into('>h', level, 0x21a6 + (room - 1) * 192, len(opponents))
        bank = bytearray(unused_bank)
        for index, actor in enumerate(opponents):
            bank[index * 62:(index + 1) * 62] = relief_actor_bytes(actor, 7 + index * 2)
        saved = relief_actor_bytes(prince, 13)
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, current)
        machine.cpu.mem_write(machine.A5 - 0x50d2, saved)
        machine.cpu.mem_write(machine.A5 - 0x5208, bytes(bank))
        machine.cpu.mem_write(machine.A5 - 0x34b0, cache)
        machine.cpu.mem_write(machine.A5 - 0x448e, trobs)
        machine.cpu.mem_write(machine.A5 - 0x43ee, struct.pack('>4h', cell, room, 8, 4))
        machine.put_word(-0x5008, countdown)
        actual = machine.call(5, 0x4766)
        expected = int(relief_reference(number, countdown, room, cell, prince, opponents))
        if (actual != expected or machine.services or machine.events
                != [('relief_check',)] or machine.level_bytes(len(level)) != level
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != current
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != saved
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5208, 186)) != bank
                or bytes(machine.cpu.mem_read(machine.A5 - 0x34b0, 12)) != cache
                or bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)) != trobs
                or struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x43ee, 8)) != (cell, room, 8, 4)
                or machine.word(-0x5008) != countdown):
            raise AssertionError(dict(label=label, inputs=(number, countdown, room, cell, prince, opponents),
                                      actual=actual, expected=expected, services=machine.services))
        counts[label] += 1
        outcomes[f'relief_{actual}'] += 1
        digest.update(bytes(level) + saved + bank + struct.pack('>h', actual))

    for number, level, room, cell in inventory:
        row, column = divmod(cell, 10)
        prince = ReliefActor(room, column, row)
        for countdown, opponents in product((-2, -1, 4), ((), (ReliefActor(room, column + 1, row),))):
            compare_relief(level, number, countdown, room, cell, prince, opponents, 'original-temple-rejection')
    _number, level, _room, _cell = inventory[0]
    for gate, prince_column, opponent_column, alive in product(range(10), range(-5, 15), range(-1, 11), (-1, 0, 1)):
        compare_relief(level, 4, -1, 1, 10 + gate, ReliefActor(1, prince_column, 1),
                       (ReliefActor(1, opponent_column, 1, alive),), 'supplied-level4-boundaries')
    patterns = {
        'empty': (),
        'far': (ReliefActor(1, 0, 1), ReliefActor(1, 1, 1)),
        'near': (ReliefActor(1, 8, 1),),
        'far-then-near': (ReliefActor(1, 0, 1), ReliefActor(1, 8, 1)),
        'near-then-far': (ReliefActor(1, 8, 1), ReliefActor(1, 0, 1)),
        'dead-wrong-row-room': (ReliefActor(1, 0, 1, 0), ReliefActor(1, 0, 0), ReliefActor(2, 0, 1)),
        'ignored-then-far': (ReliefActor(1, 8, 1, 0), ReliefActor(1, 0, 1)),
    }
    for number, countdown, room, prince, opponents in product(
            (3, 4, 5, 10, 13), (-2, -1, 0, 4), (0, 1),
            (ReliefActor(1, 4, 1), ReliefActor(1, 4, 0), ReliefActor(2, 4, 1)), patterns.values()):
        compare_relief(level, number, countdown, room, 12, prince, opponents, 'supplied-admission-and-bank-order')

    saved = bytearray(relief_actor_bytes(ReliefActor(0, 4, 0), 13))
    # Explicitly exclude StopGate's hanging sequence and saved-actor reaction.
    struct.pack_into('>h', saved, 2, 0)
    struct.pack_into('>h', saved, 16, 0)
    saved = bytes(saved)
    for number, original, room, cell in inventory:
        for position, phase, countdown in product((0, 3, 60, 180, 255), (1, 2, 3, 4, 8), (-2, -1, 4)):
            level = bytearray(original)
            offset = 0x780 + (room - 1) * 120 + cell * 4
            struct.pack_into('>H', level, offset, position)
            expected = gate_animation_reference(position, phase, relief_countdown=countdown)
            expected_level = bytearray(level)
            struct.pack_into('>H', expected_level, offset, expected['foreground'])
            machine.reset(level)
            machine.cpu.mem_write(machine.A5 - 0x5056, current)
            machine.cpu.mem_write(machine.A5 - 0x50d2, saved)
            machine.cpu.mem_write(machine.A5 - 0x5208, unused_bank)
            machine.cpu.mem_write(machine.A5 - 0x34b0, cache)
            machine.cpu.mem_write(machine.A5 - 0x448e, trobs)
            machine.cpu.mem_write(machine.A5 - 0x43ee, struct.pack('>4h', cell, room, phase, 4))
            machine.put_word(-0x4fc2, room)
            machine.put_word(-0x5008, countdown)
            # Current mode is irrelevant after a real LoadKid; before it,
            # environment2 and saved room0 exclude actor-dependent branches.
            machine.call(5, 0x0cd6, (0,))
            actual = dict(foreground=machine.word(-0x4818) & 65535, phase=machine.word(-0x43ea),
                          relief_countdown=machine.word(-0x5008), events=machine.events)
            expected_current = saved if ('load_kid',) in expected['events'] else current
            expected_services = Counter({'sound': 'gate_sound', 'redraw': 'gate_redraw'}[event[0]]
                                        for event in expected['events'] if event[0] in ('sound', 'redraw'))
            if (actual != expected or machine.services != expected_services
                    or machine.level_bytes(len(level)) != expected_level
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != expected_current
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != saved
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x5208, 186)) != unused_bank
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x34b0, 12)) != cache
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)) != trobs
                    or struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x43ee, 8)) !=
                        (cell, room, expected['phase'], 4)):
                raise AssertionError(dict(gate=(number, room, cell), inputs=(position, phase, countdown),
                                          actual=actual, expected=expected, services=machine.services))
            counts['connected-gate-real-services'] += 1
            services.update(machine.services)
            digest.update(bytes(expected_level) + expected_current + json.dumps(actual).encode('ascii'))
    return dict(cases=dict(counts), outcomes=dict(outcomes), services=dict(services), mismatches=0,
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
                level_sha256={str(n): hashlib.sha256(resources['LEVL'][1999 + n]['data']).hexdigest()
                              for n in range(10, 14)},
                supplied_services=['5:3828 gate sound request', '5:0fe6 redraw request'],
                scope='Native relief predicate and connected temple gate motion with real LoadKid copy. '
                      'Level4 controls use a patched level-number/count field and supplied actor bank, '
                      'not a claim of original level4 gameplay coverage. Non-hanging actor states, '
                      'no full FrameAdv, sound/pixels, crushing consequences or runtime integration.')


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
