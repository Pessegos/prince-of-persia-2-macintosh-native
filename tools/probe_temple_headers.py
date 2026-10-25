"""Probe temple entry selectors, custom-room flags and original actor-kind conversion."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


def temple_kind_reference(raw_kind):
    kind = raw_kind if raw_kind in (1, 3, 9, 10) else 7
    return kind, {1: 10, 3: 6, 7: 2, 9: 12, 10: 0}[kind]


def customized_reference(level, room):
    if not 1 <= room <= 32:
        raise ValueError('Only valid native rooms are covered')
    return any(struct.unpack_from('>H', level, 0x780 + (room - 1) * 120 + cell * 4)[0] & 0xc000
               for cell in range(30))


class NativeTempleHeaders(NativeRules):
    RANGES = {
        2: ((0x5d98, 0x5e36),),
        3: ((0x1310, 0x1362),),
        5: ((0x4e0c, 0x4e42),),
        6: ((0x2bca, 0x2c12),),
    }
    SUPPLIED = {}


def run_probe(recovery):
    from unicorn.m68k_const import UC_M68K_REG_A3

    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(program_bytes)
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeTempleHeaders(program)
    counts = Counter()
    results = []
    for number in range(10, 14):
        level = prince['LEVL'][1999 + number]['data']
        room = struct.unpack_from('>H', level, 0x2198)[0]
        if (struct.unpack_from('>H', level, 0x2186)[0] != 2
                or struct.unpack_from('>H', level, 0x218a)[0] != number
                or struct.unpack_from('>h', level, 0x21a4)[0] != 7):
            raise ValueError('Inconsistent original temple header')
        machine.reset(level)
        machine.put_word(-0x5052, 600)
        machine.put_word(-0x5040, room)
        machine.call(2, 0x5d98, stop=(2, 0x5e36))
        selected = machine.cpu.reg_read(machine.registers['d3']) & 65535
        x = machine.word(-0x5052)
        if (selected, x) != ((2, 430) if number == 10 else (5, 600)):
            raise AssertionError(f'Entry selector differs for temple level {number}')
        counts['entry_selector'] += 1
        machine.reset(level)
        if machine.call(5, 0x4e0c) != 187:
            raise AssertionError('Temple end-song selection differs')
        counts['end_song'] += 1
        custom_rooms, actors = [], []
        for current_room in range(1, 33):
            machine.reset(level)
            native = machine.call(3, 0x1310, (current_room,))
            if native != int(customized_reference(level, current_room)):
                raise AssertionError(f'Custom flag differs for {number}/{current_room}')
            if machine.level_bytes(len(level)) != level:
                raise AssertionError('Custom predicate changed the original level')
            counts['custom_room'] += 1
            if native:
                custom_rooms.append(current_room)
            base = 0x20e6 + current_room * 0xc0
            for slot in range(struct.unpack_from('>H', level, base)[0]):
                record = base + 2 + slot * 38
                original_kind = struct.unpack_from('>h', level, record + 0x18)[0]
                for supplied_kind in (original_kind, *range(12), -1, 100):
                    supplied = bytearray(level)
                    struct.pack_into('>h', supplied, record + 0x18, supplied_kind)
                    expected = bytearray(supplied)
                    expected_kind, expected_actor = temple_kind_reference(supplied_kind)
                    struct.pack_into('>h', expected, record + 0x18, expected_kind)
                    machine.reset(supplied)
                    machine.cpu.reg_write(UC_M68K_REG_A3, machine.LEVEL + record)
                    machine.call(6, 0x2bca, stop=(6, 0x2c12))
                    if (machine.word(-0x504e) != expected_actor
                            or machine.level_bytes(len(level)) != expected):
                        raise AssertionError(dict(level=number, room=current_room, slot=slot,
                                                  supplied_kind=supplied_kind))
                    counts['actor_selector'] += 1
                actors.append(dict(room=current_room, slot=slot, raw_kind=original_kind,
                                   actor=temple_kind_reference(original_kind)[1]))
        for flag in (0, 0x4000, 0x8000, 0xc000):
            supplied = bytearray(level)
            for cell in range(30):
                offset = 0x780 + (room - 1) * 120 + cell * 4
                value = struct.unpack_from('>H', supplied, offset)[0] & 0x3fff
                struct.pack_into('>H', supplied, offset, value)
            struct.pack_into('>H', supplied, 0x780 + (room - 1) * 120 + 29 * 4, flag)
            machine.reset(supplied)
            if machine.call(3, 0x1310, (room,)) != int(flag != 0):
                raise AssertionError('Custom high-bit control differs')
            counts['custom_bit_control'] += 1
        results.append(dict(level=number, entry_sequence=selected, selected_native_x=x,
                            custom_rooms=custom_rooms, actors=actors,
                            level_sha256=hashlib.sha256(level).hexdigest()))
    return dict(
        cases=dict(counts), levels=results, mismatches=0, supplied_services=[],
        executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        scope=('Original entry selector only, stopping before JumpSeq; full end-song and '
               'custom-room predicates; InitOpps kind selector only, stopping before resource '
               'loading. Actor pointer and counterfactual raw-kind/flag states supplied. '
               'No complete initialization, AI, CUST loading, cutscene, drawing or cadence claim.'),
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
