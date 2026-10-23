"""Compare original HeadAddOpponent with an isolated research reference."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


def initialization_reference(words, working):
    record = list(words)
    state = dict(working)
    sounds = []
    if record[12] == 0:
        record[12] = 5
        state['actor'] = 7
        state['y'] = state['row'] * 120 + 73
    if state['actor'] == 11:
        if state['alive'] < 0:
            if record[14] <= 0:
                record[4], record[5], record[14] = 170, 0, -1
            else:
                record[4], record[5] = 175, 0
                state['special'] = 6
            state['armed'] = 1
            sounds.append(128)
        else:
            state['armed'] = 0
    else:
        state['x'] = state['column'] * 51 + 207 + 47
        state['facing'] = -1
        record[4], record[5], record[14] = 130, 0, 0
        state['armed'] = 0
    return record, state, sounds


class NativeInitialization(NativeRules):
    RANGES = {4: ((0x31fa, 0x3228),), 5: ((0x48b0, 0x48dc),), 7: ((0x0574, 0x0636),)}
    SUPPLIED = {}
    FIELDS = dict(actor=-0x504e, row=-0x5048, column=-0x504a, alive=-0x503a,
                  x=-0x5052, y=-0x5050, facing=-0x5054, armed=-0x503c, special=-0x5022)

    def dispatch(self, cpu, address, size, user):
        if address == self.address(5, 0x4d84):
            stack = cpu.reg_read(self.registers['a7'])
            self.sounds.append(struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0])
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], destination)
            return
        super().dispatch(cpu, address, size, user)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(program_bytes)
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    level = prince['LEVL'][2006]['data']
    machine = NativeInitialization(program)
    cases, sounds = Counter(), Counter()
    digest = hashlib.sha256()
    for room in range(1, 33):
        base = 0x20e6 + room * 0xc0
        count = struct.unpack_from('>H', level, base)[0]
        for slot in range(count):
            offset = base + 2 + slot * 38
            original = struct.unpack_from('>19h', level, offset)
            actor = {5: 7, 6: 8, 8: 11}[original[12]]
            machine.reset(level)
            machine.call(5, 0x48b0, (original[1],))
            column = machine.cpu.reg_read(machine.registers['d0']) & 65535
            column = column - 65536 if column >= 32768 else column
            for alive in (-1, 0, 1):
                for mode in (-1, 0, 1, 3):
                    words = list(original)
                    words[14] = mode
                    supplied = bytearray(level)
                    struct.pack_into('>19h', supplied, offset, *words)
                    initial = dict(actor=actor, row=original[0] // 10, column=column, alive=alive,
                                   x=original[1], y=333, facing=original[2], armed=9, special=4)
                    machine.reset(supplied)
                    for name, value in initial.items():
                        machine.put_word(machine.FIELDS[name], value)
                    machine.sounds = []
                    machine.call(7, 0x0574, arg_bytes=struct.pack('>I', machine.LEVEL + offset))
                    expected_words, expected_state, expected_sounds = initialization_reference(words, initial)
                    actual_level = machine.level_bytes(len(level))
                    expected_level = bytearray(supplied)
                    struct.pack_into('>19h', expected_level, offset, *expected_words)
                    actual_state = {name: machine.word(address) for name, address in machine.FIELDS.items()}
                    if (actual_level != expected_level or actual_state != expected_state
                            or machine.sounds != expected_sounds):
                        raise AssertionError(dict(room=room, slot=slot, alive=alive, mode=mode,
                                                  native=actual_state, expected=expected_state))
                    cases[str(actor)] += 1
                    sounds.update(machine.sounds)
                    digest.update(actual_level)
    # A separate supplied kind-zero record exercises the native fallback.
    for row in range(3):
        supplied = bytearray(level)
        offset = 0x20e6 + 7 * 0xc0 + 2
        words = list(struct.unpack_from('>19h', supplied, offset))
        words[12] = 0
        struct.pack_into('>19h', supplied, offset, *words)
        initial = dict(actor=11, row=row, column=4, alive=-1, x=411,
                       y=333, facing=0, armed=9, special=4)
        machine.reset(supplied)
        for name, value in initial.items():
            machine.put_word(machine.FIELDS[name], value)
        machine.sounds = []
        machine.call(7, 0x0574, arg_bytes=struct.pack('>I', machine.LEVEL + offset))
        expected_words, expected_state, expected_sounds = initialization_reference(words, initial)
        expected_level = bytearray(supplied)
        struct.pack_into('>19h', expected_level, offset, *expected_words)
        if (machine.level_bytes(len(level)) != expected_level
                or {name: machine.word(address) for name, address in machine.FIELDS.items()} != expected_state
                or machine.sounds != expected_sounds):
            raise AssertionError('Kind-zero fallback differs')
        cases['supplied_kind_zero'] += 1
    return dict(level=7, cases=dict(cases), mismatches=0, requested_sounds=dict(sounds),
                outputs_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
                scope=('Full original 7:0574 with original 4:31fa fallback and 5:48b0 column '
                       'calculation. Only AddSound is intercepted to record cue 128. '
                       'Working state is supplied; mode and ALIVE combinations are controls, '
                       'not proof of reachability. No full InitOpps, animation, playback or AI cadence.'))


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
