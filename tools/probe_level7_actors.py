"""Probe original special-kind selection, controller dispatch and head locking."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class NativeActorHeaders(NativeRules):
    RANGES = {
        6: ((0x2bca, 0x2c12), (0x3642, 0x36de), (0x4eb6, 0x4f04)),
        7: ((0x16b8, 0x16f6),),
    }
    SUPPLIED = {}


def run_probe(recovery):
    from unicorn.m68k_const import UC_M68K_REG_A3

    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(program_bytes)
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    level = prince['LEVL'][2006]['data']
    machine = NativeActorHeaders(program)
    kind_to_actor = {5: 7, 6: 8, 8: 11}
    kind_counts, actor_counts = Counter(), Counter()
    mapping_cases = []
    lock_cases = 0
    missing_cases = 0

    for room in range(1, 33):
        offset = 0x20e6 + room * 0xc0
        count = struct.unpack_from('>H', level, offset)[0]
        for slot in range(count):
            record = offset + 2 + slot * 38
            kind = struct.unpack_from('>h', level, record + 0x18)[0]
            machine.reset(level)
            machine.cpu.reg_write(UC_M68K_REG_A3, machine.LEVEL + record)
            machine.call(6, 0x2bca, stop=(6, 0x2c12))
            actor = machine.word(-0x504e)
            if actor != kind_to_actor[kind] or machine.level_bytes(len(level)) != level:
                raise AssertionError(f'Unexpected kind conversion in room {room}, slot {slot}')
            kind_counts[kind] += 1
            actor_counts[actor] += 1

            callback = (7, 0x1824 if actor == 11 else 0x1324)
            machine.reset(level)
            machine.put_word(-0x504e, actor)
            machine.call(6, 0x4eb6, stop=callback)
            mapping_cases.append(dict(room=room, slot=slot, kind=kind, actor=actor,
                                      controller=f'{callback[0]}:{callback[1]:04x}'))

            if actor not in (7, 8):
                continue
            for mode in (-1, 0, 1, 2, 3, 4):
                for life in (-1, 0, 4):
                    supplied = bytearray(level)
                    struct.pack_into('>h', supplied, record + 0x1c, mode)
                    struct.pack_into('>h', supplied, record + 0x1a, life)
                    machine.reset(supplied)
                    result = machine.call(7, 0x16b8, (room, slot))
                    if result != int(mode == 3):
                        raise AssertionError(f'Unexpected head-lock predicate: {room}/{slot}/{mode}/{life}')
                    if machine.level_bytes(len(level)) != supplied:
                        raise AssertionError('Head-lock predicate changed level records')
                    lock_cases += 1
        machine.reset(level)
        if machine.call(7, 0x16b8, (room, count)) != 0:
            raise AssertionError('Missing record reported locked')
        missing_cases += 1

    machine.reset(level)
    if machine.call(7, 0x16b8, (0, 0)) != 0:
        raise AssertionError('Room zero reported locked')
    missing_cases += 1
    if machine.services:
        raise AssertionError('Unexpected supplied service in actor probe')

    return dict(
        level=7, executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        level_sha256=hashlib.sha256(level).hexdigest(),
        original_records=len(mapping_cases), kind_counts=dict(kind_counts),
        actor_counts=dict(actor_counts), cases=mapping_cases,
        locked_predicate_cases=lock_cases, missing_record_controls=missing_cases,
        mismatches=0, supplied_services=[],
        scope=('Original InitOpps kind selector only (6:2bca to before 6:2c12), '
               'AutoCtrl dispatch only (6:4eb6 to before the actual controller), '
               'and IsHeadLockedOn 7:16b8 including original GetOppInfoIdx. '
               'A3, actor type and mode/life controls are supplied. '
               'No full initialization, controller body, animation, AI cadence, '
               'collision or record lifecycle equivalence claim.'),
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
