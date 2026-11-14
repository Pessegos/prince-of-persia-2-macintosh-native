"""Execute the temple exit's pose-dependent front-table promotion.

Original DrawTempExitMovable, ResetNextBFItem, ResetNextBFItemWithPrevInfo
and TransferBFItemMidFields execute. AddNextBFItemToTable is a supplied
shape-header/viewport admission and table-counter endpoint, not rasterization.
The caller supplies its BF item, pass, pose, cell, foreground and PIEC binding.
Back pass 0, dirty-buffer scheduling, ClipChar and full FrameAdv are excluded.
"""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class NativeExitForeground(NativeRules):
    RANGES = {3: ((0x29e2, 0x2b92),), 10: ((0x0562, 0x0698), (0x0772, 0x0846))}
    SUPPLIED = {}
    FRONT, BACK, PIECES = 0xc5000, 0xc7000, 0xc9000

    def __init__(self, program, artwork):
        super().__init__(program)
        self.artwork = artwork
        self.commands = []

    def dispatch(self, cpu, address, size, user):
        if address != self.address(3, 4):
            return super().dispatch(cpu, address, size, user)
        pointer = struct.unpack('>I', cpu.mem_read(self.A5 - 0x4f8c, 4))[0]
        admitted = False
        if pointer:
            fields = struct.unpack('>19h', cpu.mem_read(pointer, 38))
            if fields[0] != 4:
                raise AssertionError(('Unexpected shape library', fields))
            shape = 3500 + fields[12]
            width, height = struct.unpack_from('>hH', self.artwork['SHAP'][shape]['data'], 4)
            x = fields[7] * 51 + fields[13]
            bottom = (fields[8] + 1) * 120 + 5 + fields[14]
            clip = (max(0, bottom - height), max(0, x), min(365, bottom), min(510, x + width))
            admitted = clip[0] < clip[2] and clip[1] < clip[3]
            if admitted:
                front = fields[5] in (1, 2)
                self.commands.append(['front' if front else 'back', shape, x, bottom,
                                      fields[3], fields[8], list(clip), fields[7]])
                count = -0x482c if front else -0x482e
                self.put_word(count, self.word(count) + 1)
                cpu.mem_write(pointer + 30, struct.pack('>4h', *clip))
                cpu.mem_write(self.A5 - 0x4f8c, bytes(4))
        cpu.reg_write(self.registers['d0'], int(admitted))
        stack = cpu.reg_read(self.registers['a7'])
        destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
        cpu.reg_write(self.registers['a7'], stack + 4)
        cpu.reg_write(self.registers['pc'], destination)

    def fixture(self, level, row, column, pose, draw_pass, foreground):
        self.reset(level)
        self.commands.clear()
        self.cpu.mem_write(self.FRONT, bytes(0x2000))
        self.cpu.mem_write(self.BACK, bytes(0x2000))
        self.cpu.mem_write(self.PIECES, self.artwork['PIEC'][3500]['data'])
        for offset, pointer in ((-0x4ca6, self.FRONT), (-0x4ca2, self.BACK),
                                (-0x4b9e, self.PIECES), (-0x4f8c, 0)):
            self.cpu.mem_write(self.A5 + offset, struct.pack('>I', pointer))
        for offset, value in ((-0x482c, 0), (-0x482e, 0), (-0x45f8, column),
                              (-0x45f6, row), (-0x50c8, pose)):
            self.put_word(offset, value)
        self.call(3, 0x29e2, (draw_pass,))
        pointer = struct.unpack('>I', self.cpu.mem_read(self.A5 - 0x4f8c, 4))[0]
        self.cpu.mem_write(pointer + 14, struct.pack('>5H', column, row, 17, foreground, 0))


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    artwork = parse_resource_fork((forks / 'Temple.rsrc.bin').read_bytes())
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    level = prince['LEVL'][2009]['data']
    if struct.unpack_from('>H', level, 0x2186)[0] != 2:
        raise AssertionError('Expected original level 10 temple header')
    machine = NativeExitForeground(parse_resource_fork(executable), artwork)
    digest, count, promoted = hashlib.sha256(), 0, 0
    width, height = struct.unpack_from('>hH', artwork['SHAP'][3579]['data'], 4)
    if struct.unpack_from('>3h', artwork['PIEC'][3500]['data'], 0x47c) != (79, -11, -27):
        raise AssertionError('Unexpected original temple exit PIEC')
    for row, column, pose, draw_pass, foreground in product(
            range(3), range(10), range(216, 228), (1, 2, 5), (0, 1, 79, 255)):
        machine.fixture(level, row, column, pose, draw_pass, foreground)
        machine.call(10, 0x0562)
        frames = [command for command in machine.commands if command[1] == 3579]
        expected = []
        if draw_pass == 5:
            front = 217 <= pose <= 226
            x, bottom = column * 51 - 11, (row + 1) * 120 + 5 - 27
            expected = [['front' if front else 'back', 3579, x, bottom, 16, row,
                         [max(0, bottom - height), max(0, x), min(365, bottom), min(510, x + width)],
                         column]]
            promoted += int(front)
        if frames != expected:
            raise AssertionError(((row, column, pose, draw_pass, foreground), frames, expected))
        digest.update(json.dumps([row, column, pose, draw_pass, foreground, frames]).encode('ascii'))
        count += 1
    return dict(comparisons=count, promoted=promoted, mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                artwork_sha256=hashlib.sha256((forks / 'Temple.rsrc.bin').read_bytes()).hexdigest(),
                outputs_sha256=digest.hexdigest(), scope=__doc__)


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
