"""Bounded native throne-grille foreground checks; original files stay read-only.

The displayed-room drawing branch7:2b22-2b4a calls7:383a for this special
gate. The latter temporarily promotes CUST record6. Its DrawCustomImg
endpoint is recorded, not rasterized. CheckGateInFore3:2722-2764 runs with
supplied actor row/column/mode and piece column9/row2; no services execute
in that selector. Full drawing lists, QuickDraw and FrameAdv are excluded.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class NativeThroneForeground(NativeRules):
    RANGES = {3: ((0x2722, 0x2764),), 7: ((0x383a, 0x3862),)}
    SUPPLIED = {(3, 0x2438): 'draw_custom'}
    CUSTOM = 0xc0000

    def dispatch(self, cpu, address, size, user):
        if address == self.address(3, 0x2438):
            stack = cpu.reg_read(self.registers['a7'])
            self.draws.append((struct.unpack('>2h', cpu.mem_read(stack + 4, 4)),
                               struct.unpack('>6h', cpu.mem_read(self.CUSTOM + 222, 12))))
        super().dispatch(cpu, address, size, user)


def foreground_probe(source):
    from unicorn.m68k_const import UC_M68K_REG_A6

    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    ruins = parse_resource_fork((forks / 'Ruins.rsrc.bin').read_bytes())
    level, custom = prince['LEVL'][2007]['data'], ruins['CUST'][4200]['data']
    if struct.unpack_from('>3h', level, 0x2186)[::2] != (4, 8):
        raise AssertionError('Expected the original level-eight ruins header')
    machine = NativeThroneForeground(parse_resource_fork(executable))
    machine.reset(level)
    machine.draws = []
    machine.cpu.mem_write(machine.CUSTOM, custom)
    machine.cpu.mem_write(machine.A5 - 0x4c9e, struct.pack('>I', machine.CUSTOM))
    machine.call(7, 0x383a)
    expected = struct.unpack_from('>6h', custom, 222)
    promoted = (*expected[:3], 1, *expected[4:])
    if (machine.draws != [((6, 1), promoted)] or
            bytes(machine.cpu.mem_read(machine.CUSTOM, len(custom))) != custom):
        raise AssertionError('Native temporary front-pass promotion differs')
    selected, count = 0, 0
    for row in range(3):
        for column in range(10):
            for mode in range(10):
                machine.reset(level)
                machine.cpu.reg_write(UC_M68K_REG_A6, 0xe0000)
                for offset, value in ((-0x50c4, row), (-0x50c6, column), (-0x50c2, mode),
                                      (-0x45f8, 9), (-0x45f6, 2)):
                    machine.put_word(offset, value)
                actual = machine.call(3, 0x2722, stop=(3, 0x2764))
                wanted = row == 2 and column in (7, 8) and mode not in (2, 6)
                if bool(actual) != wanted or machine.services:
                    raise AssertionError((row, column, mode, actual, wanted))
                count += 1
                selected += bool(actual)
    return dict(selector_cases=count, promoted_cases=selected, custom_record=6,
                shape=struct.unpack_from('>H', custom, 2)[0] + expected[0],
                draw_arguments=[6, 1], original_pass=expected[3], restored=True,
                executable_sha256=hashlib.sha256(executable).hexdigest(), scope=__doc__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = foreground_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
