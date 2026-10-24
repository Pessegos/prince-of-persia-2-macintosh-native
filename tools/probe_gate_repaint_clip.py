"""Check the native dirty-cell clip used by ordinary gate repaints, not full cuts."""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules
from tools.probe_temple_trapdoor_presentation import intersect_rect


class NativeCellClip(NativeRules):
    RANGES = {5: ((0x0162, 0x01cc),)}
    SUPPLIED = {}
    INTERSECTION, RECT = 0xc3800, 0xc4000

    def dispatch(self, cpu, address, size, user):
        if address != self.INTERSECTION:
            return super().dispatch(cpu, address, size, user)
        stack = cpu.reg_read(self.registers['a7'])
        destination, output, first, second = struct.unpack('>4I', cpu.mem_read(stack, 16))
        first = struct.unpack('>4h', cpu.mem_read(first, 8))
        second = struct.unpack('>4h', cpu.mem_read(second, 8))
        rect = intersect_rect(first, second)
        cpu.mem_write(output, struct.pack('>4h', *rect))
        cpu.mem_write(stack + 16, bytes((int(rect != (0, 0, 0, 0)), 0)))
        cpu.reg_write(self.registers['a7'], stack + 16)
        cpu.reg_write(self.registers['pc'], destination)


def run_probe(source):
    executable = (Path(source) / 'resource_forks/Prince of Persia 2.bin').read_bytes()
    machine = NativeCellClip(parse_resource_fork(executable))
    digest = hashlib.sha256()
    count = 0
    for row, column, viewport in product(range(3), range(10), (
            (0, 0, 365, 510), (17, 12, 364, 499), (250, 250, 300, 400))):
        machine.reset(bytes(0x2200))
        machine.put_word(-0x4fb0, 0)
        machine.cpu.mem_write(machine.A5 - 0x4fec, struct.pack('>4h', *viewport))
        machine.cpu.mem_write(machine.A5 - 0x1f58, struct.pack('>I', machine.INTERSECTION))
        machine.cpu.mem_write(machine.RECT - 8, bytes([0xa7]) * 24)
        machine.call(5, 0x0162, arg_bytes=struct.pack('>Ihh', machine.RECT, column, row))
        actual = struct.unpack('>4h', machine.cpu.mem_read(machine.RECT, 8))
        expected = intersect_rect((row * 120 + 5, column * 51,
                                   (row + 1) * 120 + 5, (column + 1) * 51), viewport)
        if (actual != expected
                or bytes(machine.cpu.mem_read(machine.RECT - 8, 8)) != bytes([0xa7]) * 8
                or bytes(machine.cpu.mem_read(machine.RECT + 8, 8)) != bytes([0xa7]) * 8):
            raise AssertionError((row, column, viewport, actual, expected))
        digest.update(struct.pack('>2h4h4h', row, column, *viewport, *actual))
        count += 1
    return dict(comparisons=count, mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                outputs_sha256=digest.hexdigest(),
                supplied=['SectRect callback via A5-1f58, including Pascal cleanup',
                          'Viewport, ordinary-cell inputs and A5-4fb0=0'],
                scope='Full ComputeClipRect5:0162-01cc with original DATA column/row tables. '
                      'Rows0..2, columns0..9, three viewports. Confirms top=row*120+5 '
                      'before viewport intersection. Not full FrameAdv, dirty admission, '
                      'native rasterization, special row0 flag or whole-game visual parity.')


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
