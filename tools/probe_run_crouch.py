"""Check original running Down selection before JumpSeq, not standing descent."""

import argparse
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class RunningControls(NativeRules):
    RANGES = {6: ((0x11e4, 0x1274),), 4: ((0x3e3a, 0x3e4e),)}
    SUPPLIED = {}


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    program = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    levels = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL']
    machine = RunningControls(program)
    count = crouches = brakes = 0
    for number, room, action, facing, forward in product(
            (3, 4, 5), range(1, 33), range(4, 15), (0, -1), (False, True)):
        machine.reset(levels[1999 + number]['data'])
        for offset, value in ((-0x5040, room), (-0x504c, action), (-0x5054, facing),
                              (-0x3488, -1 if forward else 0), (-0x3486, 0),
                              (-0x3484, 0), (-0x3482, -1)):
            machine.put_word(offset, value)
        # Execute the actual running handler and ClearControls. Stop on
        # JumpSeq entry: its stack argument is observed, not supplied.
        machine.call(6, 0x11e4, stop=(6, 0x0006))
        stack = machine.cpu.reg_read(machine.registers['a7'])
        selected = struct.unpack('>H', machine.cpu.mem_read(stack + 4, 2))[0]
        expected = 13 if not forward and action in (7, 11) else 26
        if selected != expected or machine.services:
            raise AssertionError((number, room, action, facing, forward, selected, expected))
        count += 1
        crouches += selected == 26
        brakes += selected == 13
    return {'cases': count, 'crouches': crouches, 'brakes': brakes, 'mismatches': 0,
            'external_services': [], 'stop': 'JumpSeq 6:0006 entry; inspect its stack argument',
            'scope': 'Actual running handler 6:11e4-1274 and ClearControls 4:3e3a-3e4e. '
                     'Relative keyboard inputs supplied after directional mapping: no backward '
                     'or Up, Down held, Forward held/released. Excludes JumpSeq execution, '
                     'animation playback, standing descent and full FrameAdv.'}


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
