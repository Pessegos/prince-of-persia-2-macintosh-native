"""Check the trap-door floor marks against original MarkBufsForRect instructions.

Original DATA supplies phases/offsets; original SHAP headers supply dimensions.
Projected rectangles and their viewport intersection are supplied, following
ATMTrapDoor10:2498-24c8's +25 left adjustment. MarkBufsForRect5:19f8-1b46,
GetCell4:29d8-2a62, its row table4:322a-3262 and division19:4bb0-4c4c execute. EmptyRect is a
supplied Pascal callback; MarkFloor5:1846 is recorded, not executed. This
checks marked cells, not native floor pixels, DrawObjs or full FrameAdv.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from pop2.caverns import trapdoor_floor_redraw_cells
from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class NativeFloorMarks(NativeRules):
    RANGES = {4: ((0x29d8, 0x2a62), (0x322a, 0x3262)), 5: ((0x19f8, 0x1b46),),
              19: ((0x4bb0, 0x4c4c),)}
    SUPPLIED = {}
    RECT, EMPTY = 0xb9000, 0xb9100

    def reset(self, level):
        super().reset(level)
        self.cells = []
        self.cpu.mem_write(self.A5 - 0x1f60, struct.pack('>I', self.EMPTY))

    def dispatch(self, cpu, address, size, user):
        if address in (self.EMPTY, self.address(5, 0x1846)):
            stack = cpu.reg_read(self.registers['a7'])
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            if address == self.EMPTY:
                pointer = struct.unpack('>I', cpu.mem_read(stack + 4, 4))[0]
                top, left, bottom, right = struct.unpack('>4h', cpu.mem_read(pointer, 8))
                cpu.mem_write(stack + 8, bytes((int(top >= bottom or left >= right), 0)))
                cpu.reg_write(self.registers['a7'], stack + 8)
                self.services['empty_rect'] += 1
            else:
                cell = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
                row, column = (-1, -cell - 1) if cell < 0 else divmod(cell, 10)
                self.cells.append((column, row))
                cpu.reg_write(self.registers['a7'], stack + 4)
                self.services['mark_floor'] += 1
            cpu.reg_write(self.registers['pc'], destination)
            return
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    originals = {name: (directory / name).read_bytes()
                 for name in ('Prince of Persia 2.bin', 'Prince.rsrc.bin', 'Temple.rsrc.bin')}
    prince = parse_resource_fork(originals['Prince.rsrc.bin'])
    temple = parse_resource_fork(originals['Temple.rsrc.bin'])
    machine = NativeFloorMarks(parse_resource_fork(originals['Prince of Persia 2.bin']))
    base = struct.unpack_from('>H', temple['SHPL'][3500]['data'])[0]
    if base != 3501:
        raise AssertionError('Unexpected temple shape-library base')
    mapping = struct.unpack_from('>18h', machine.data, len(machine.data) - 0x2866)
    frames = [struct.unpack_from('>3h', machine.data, len(machine.data) - 0x2842 + i * 6)
              for i in range(5)]
    counts, digest = Counter(), hashlib.sha256()
    for number in range(10, 14):
        level = prince['LEVL'][1999 + number]['data']
        if (struct.unpack_from('>H', level, 0x2186)[0],
                struct.unpack_from('>H', level, 0x218a)[0]) != (2, number):
            raise AssertionError('Wrong temple level/environment header')
        for room in range(32):
            for cell in range(30):
                if struct.unpack_from('>H', level, room * 60 + cell * 2)[0] != 26:
                    continue
                counts['locations'] += 1
                row, column = divmod(cell, 10)
                for phase in range(1, 17):
                    shape, dx, dy = frames[mapping[phase]]
                    width, height = struct.unpack_from('>2H', temple['SHAP'][base + shape - 1]['data'], 4)
                    for projection in (-364, 0, 364):
                        x, y = column * 51 + dx, (row + 1) * 120 + 5 + dy + projection
                        clip = (max(x, 0), max(y - height - 1, 0),
                                min(x + max(width + 1, column * 51 + 77 - x), 510), min(y + 1, 365))
                        left, top, right, bottom = clip
                        rectangle = ((top, left + 25, bottom, right)
                                     if left + 25 < right and top < bottom else (0, 0, 0, 0))
                        machine.reset(level)
                        machine.cpu.mem_write(machine.RECT, struct.pack('>4h', *rectangle))
                        machine.call(5, 0x19f8, arg_bytes=struct.pack('>IIh', machine.A5 + 0x3ba,
                                                                 machine.RECT, -1))
                        expected = list(trapdoor_floor_redraw_cells(clip))
                        if (machine.cells != expected or machine.level_bytes(len(level)) != level
                                or machine.services != Counter(empty_rect=1, mark_floor=len(expected))):
                            raise AssertionError((number, room + 1, cell, phase, projection,
                                                  machine.cells, expected))
                        counts['comparisons'] += 1
                        counts['marked_cells'] += len(expected)
                        digest.update(json.dumps(machine.cells).encode('ascii'))
    return dict(counts=dict(counts), mismatches=0, scope=__doc__,
                original_sha256={name: hashlib.sha256(data).hexdigest() for name, data in originals.items()},
                outputs_sha256=digest.hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(report['counts'], 'mismatches:', report['mismatches'])
