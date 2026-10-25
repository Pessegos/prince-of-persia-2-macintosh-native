"""Validate original temple sliding-rock lookup/activation without movement."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


def trigger_reference(room, cell, how, bank):
    if not 1 <= room <= 32 or not 0 <= cell < 30 or len(bank) > 30:
        raise ValueError('Input outside the tested room/cell/capacity domain')
    if not -32768 <= how <= 32767 or any(
            len(record) != 8 or any(not -32768 <= word <= 32767 for word in record)
            for record in bank):
        raise ValueError('Expected signed native words and eight-word records')
    result = [tuple(record) for record in bank]
    row, column = divmod(cell, 10)
    selected = next((index for index, record in enumerate(result)
                     if record[5] == 6 and record[3] != -1
                     and record[2] == room and record[6] == row), None)
    scratch = None
    appended = False
    if selected is not None:
        record = list(result[selected])
        if how == 1 and record[4] >= 0 and record[4] != 100:
            record[4] = -2
        elif how == 2 and record[4] == -2:
            record[4] = 2
        result[selected] = tuple(record)
    elif how == 1:
        x = column * 51
        scratch = (x, 116 + row * 120, room, 0, -2, 6, row, x)
        if len(result) < 30:
            result.append(scratch)
            appended = True
    return dict(bank=tuple(result), selected=selected, scratch=scratch, appended=appended)


class NativeSlideRockTrigger(NativeRules):
    RANGES = {
        4: ((0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x322a, 0x3262)),
        5: ((0x0004, 0x0066), (0x2914, 0x2994), (0x4970, 0x49a0)),
        10: ((0x1a9e, 0x1ae8), (0x2152, 0x2246)),
    }
    SUPPLIED = {}
    BANK = 0xb0010


def bank_cases(room, row):
    other_room = room % 32 + 1
    other_row = (row + 1) % 3
    filler = (17, 19, other_room, 0, 23, 10, other_row, 29)
    for count in (0, 1, 29, 30):
        yield f'absent-{count}', (filler,) * count
    states = (-32768, -3, -2, -1, 0, 1, 2, 99, 100, 101, 32767)
    for state, mark in product(states, (-2, -1, 0, 1)):
        record = (37, 41, room, mark, state, 6, row, 43)
        yield f'existing-{state}-{mark}', (filler, record)
    match = (53, 59, room, 0, 2, 6, row, 61)
    second = (67, 71, room, 0, 1, 6, row, 73)
    wrong_row = (79, 83, room, 0, 2, 6, other_row, 89)
    wrong_room = (97, 101, other_room, 0, 2, 6, row, 103)
    removed = (107, 109, room, -1, 2, 6, row, 113)
    yield 'first-match', (match, second)
    yield 'matching-after-other-row', (wrong_row, match)
    yield 'matching-after-other-room', (wrong_room, match)
    yield 'matching-after-removed', (removed, match)
    yield 'removed-and-missing', (removed,)
    yield 'full-search-without-match', (wrong_room,) * 30
    yield 'match-at-last-slot', (wrong_room,) * 29 + (match,)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(executable)
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeSlideRockTrigger(program)
    counts = Counter()
    digest = hashlib.sha256()
    locations, level_hashes = [], {}
    canary = bytes((index * 37 + 11) % 256 for index in range(512))
    scratch = bytes(range(16))
    actor = bytes((index * 11 + 3) % 256 for index in range(62))
    for number in range(10, 14):
        level = prince['LEVL'][1999 + number]['data']
        if (struct.unpack_from('>H', level, 0x2186)[0] != 2
                or struct.unpack_from('>H', level, 0x218a)[0] != number):
            raise ValueError('Inconsistent temple level fixture')
        level_hashes[str(number)] = hashlib.sha256(level).hexdigest()
        for room in range(1, 33):
            for cell in range(30):
                if struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0] != 25:
                    continue
                locations.append(dict(level=number, room=room, cell=cell))
                for (label, bank), how in product(
                        bank_cases(room, cell // 10), (-32768, -1, 0, 1, 2, 3, 32767)):
                    machine.reset(level)
                    machine.cpu.mem_write(machine.A5 - 0x5056, actor)
                    machine.cpu.mem_write(machine.A5 - 0x44a6, scratch)
                    initial = bytearray(canary)
                    for index, record in enumerate(bank):
                        start = 16 + index * 16
                        initial[start:start + 16] = struct.pack('>8h', *record)
                    machine.cpu.mem_write(machine.BANK - 16, bytes(initial))
                    machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
                    machine.put_word(-0x4490, len(bank))
                    expected = trigger_reference(room, cell, how, bank)
                    expected_bank = bytearray(initial)
                    for index, record in enumerate(expected['bank']):
                        start = 16 + index * 16
                        expected_bank[start:start + 16] = struct.pack('>8h', *record)
                    expected_scratch = (scratch if expected['scratch'] is None else
                                        struct.pack('>8h', *expected['scratch']))
                    machine.call(10, 0x2152, (room, cell, how))
                    actual_bank = bytes(machine.cpu.mem_read(machine.BANK - 16, 512))
                    actual_scratch = bytes(machine.cpu.mem_read(machine.A5 - 0x44a6, 16))
                    if (actual_bank != expected_bank or actual_scratch != expected_scratch
                            or machine.word(-0x4490) != len(expected['bank'])
                            or machine.level_bytes(len(level)) != level
                            or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != actor
                            or machine.services):
                        raise AssertionError(dict(level=number, room=room, cell=cell,
                                                  bank_case=label, how=how))
                    counts['trigger'] += 1
                    counts['existing_selected'] += expected['selected'] is not None
                    counts['appended'] += expected['appended']
                    counts['full_capacity_rejected'] += (
                        expected['scratch'] is not None and not expected['appended'])
                    counts['existing_mutated'] += (
                        expected['selected'] is not None and expected['bank'] != bank)
                    digest.update(actual_bank + actual_scratch
                                  + struct.pack('>h', len(expected['bank'])))
    return dict(
        cases=dict(counts), locations=locations, mismatches=0,
        outputs_sha256=digest.hexdigest(), level_hashes=level_hashes,
        executable_sha256=hashlib.sha256(executable).hexdigest(), supplied_services=[],
        scope=('Full TriggerSlideRock 10:2152 including row lookup 10:1a9e, '
               'GetMobTypeItem 5:293c, cell read 5:4970/4:27ee and append 5:2914. '
               'All 12 original type-25 cells with supplied how words and banks. '
               'Compares entire level, working actor, count, bank/canaries and scratch. '
               'No supplied native services. In-range cells only: the constructor '
               'X>510/right-neighbor branch is not reached or certified. '
               'No TriggerObject admission, movement, rendering, collision, actual '
               'controller scheduling, save/load or full-level solvability claim.'),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
