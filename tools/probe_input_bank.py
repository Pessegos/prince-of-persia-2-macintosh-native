"""Execute the original input-bank sample/reset/save/remap instructions."""

import argparse
from itertools import product
import json
from pathlib import Path

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules
from tools.reference_input_bank import InputBank


FIELDS = (-0x3488, -0x3486, -0x3484, -0x3482, -0x3480)


class NativeInputBank(NativeRules):
    RANGES = {4: ((0x3dfe, 0x3e6e), (0x3e84, 0x3f42))}
    SUPPLIED = {}


class NativeResetGates(NativeRules):
    RANGES = {6: ((0x0560, 0x07e0),),
              4: ((0x3e3a, 0x3e4e), (0x47a0, 0x48e8))}
    SUPPLIED = {}


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    program = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2004]['data']
    machine = NativeInputBank(program)
    samples = clears = saved = remaps = 0

    def put(bank):
        for field, value in zip(FIELDS, bank.words()):
            machine.put_word(field, value)

    def read():
        return InputBank(*(machine.word(field) for field in FIELDS))

    def check(expected, label):
        if read() != expected or machine.services:
            raise AssertionError((label, read(), expected, dict(machine.services)))

    banks = [InputBank(*directions, modifier) for directions in product((-1, 0, 1), repeat=4)
             for modifier in (-2, -1, 0, 1, 2)]
    for bank in banks:
        for horizontal, vertical, modifier in product((-1, 0, 1), (-1, 0, 1), (-2, -1, 0)):
            machine.reset(level)
            put(bank)
            for offset, value in ((-0x3498, horizontal), (-0x3496, vertical), (-0x3494, modifier)):
                machine.put_word(offset, value)
            machine.call(4, 0x3e84)
            check(bank.sample(horizontal, vertical, modifier), ('sample', bank, horizontal, vertical, modifier))
            samples += 1
        put(bank)
        result = machine.call(4, 0x3e3a)
        check(bank.clear_directions(), ('clear', bank))
        if result != 1:
            raise AssertionError(('clear return', result))
        clears += 1
        put(bank)
        machine.call(4, 0x3e50)
        put(InputBank())
        machine.call(4, 0x3e60)
        check(bank, ('save/restore', bank))
        saved += 1
        for facing_right, inverted in product((False, True), repeat=2):
            put(bank)
            machine.put_word(-0x3498, -1)
            machine.put_word(-0x3496, 1)
            if facing_right:
                machine.call(4, 0x3dfe)
            if inverted:
                machine.call(4, 0x3e1c)
            check(bank.remap(facing_right=facing_right, inverted=inverted), ('remap', bank))
            remaps += 1
    gates = 0
    reset_machine = NativeResetGates(program)
    for mode, sequence, pose, facing, modifier in product(
            (0, 1, 3, 4, 5, 9), (3, 4, 49, 27, 110), (26, 27, 44), (0, -1), (-2, -1, 0, 1, 2)):
        reset_machine.reset(level)
        for field, value in zip(FIELDS, (-1, -1, -1, -1, modifier)):
            reset_machine.put_word(field, value)
        for field, value in ((-0x503a, -1), (-0x503c, 0), (-0x504e, 0),
                              (-0x5046, mode), (-0x502e, sequence),
                              (-0x504c, pose), (-0x5054, facing)):
            reset_machine.put_word(field, value)
        reset_machine.call(6, 0x0560)
        cleared = mode in (4, 5, 9) or sequence in (27, 110) or pose in (26, 44)
        expected = (0, 0, 0, 0, modifier) if cleared else (-1, -1, -1, -1, modifier)
        actual = tuple(reset_machine.word(field) for field in FIELDS)
        if actual != expected or reset_machine.services:
            raise AssertionError(('GenCtrl reset', mode, sequence, pose, actual, expected))
        gates += 1
    return {'sample_cases': samples, 'clear_cases': clears, 'save_restore_cases': saved,
            'remap_cases': remaps, 'mismatches': 0, 'external_services': [],
            'genctrl_reset_cases': gates,
            'scope': 'Actual 4:3e84-3f42, 3e3a, 3e50/3e60, 3dfe/3e1c. Raw axes '
                     'and modifier supplied after ReadKeyboard. Actual unarmed live-player '
                     'GenCtrl reset gates (level5, poses26/27/44), including IsDeadPos. '
                     'Excludes OS key mapping, other GenCtrl action/geometry decisions '
                     'and full FrameAdv.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
