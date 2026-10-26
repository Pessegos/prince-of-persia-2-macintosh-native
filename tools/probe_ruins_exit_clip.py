"""Compare host exit-door clipping against native4:416a-420c and original DATA.

Direct entry after visibility/body setup; actor/column and initialized DATA
pointers are supplied. Actual ReadCell/GetBlockRect execute. QuickDraw
OffsetRect/SectRect are supplied, not native rasterization or full ClipChar.
"""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.caverns import cavern_exit_clip
from pop2.mac_resources import parse_resource_fork
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap
from tools.probe_gate_repaint_clip import NativeCellClip
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import COLD_CACHE


class NativeExitClip(NativeCellClip):
    RANGES = {4: ((0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x322a, 0x3262), (0x416a, 0x420c)),
              5: ((0x0004, 0x0066), (0x01e2, 0x024e))}

    def dispatch(self, cpu, address, size, user):
        if address == self.address(5, 0x021c):
            stack = cpu.reg_read(self.registers['a7'])
            dy, dx, pointer = struct.unpack('>hhI', cpu.mem_read(stack, 8))
            rect = struct.unpack('>4h', cpu.mem_read(pointer, 8))
            cpu.mem_write(pointer, struct.pack('>4h', *(signed_word(v + (dx if i & 1 else dy))
                                                       for i, v in enumerate(rect))))
            cpu.reg_write(self.registers['a7'], stack + 8)
            cpu.reg_write(self.registers['pc'], address + 2)
            return
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    from unicorn.m68k_const import UC_M68K_REG_A6

    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    machine = NativeExitClip(parse_resource_fork(executable))
    digest, count = hashlib.sha256(), 0
    rects = {}
    for number in range(3, 10):
        original = prince['LEVL'][1999 + number]['data']
        environment = struct.unpack_from('>H', original, 0x2186)[0]
        pointer = struct.unpack_from('>i', machine.data, len(machine.data) - 0x452c + environment * 4)[0]
        rects[environment] = struct.unpack_from('>4h', machine.data, len(machine.data) + pointer)
        for row, column, tile, pose, y, kind, facing in product(range(3), range(10), (16, 17),
                (216, 217, 226, 227), (-24, -25, -42), (0, 2), (0, 1)):
            level = bytearray(original)
            cell = row * 10 + column
            struct.pack_into('>H', level, cell * 2, tile)
            struct.pack_into('>H', level, 0x780 + cell * 4, 79)
            actor = bytearray(actor_fixture(1, row, column, -1 if facing == 0 else 0, 0))
            for offset, value in ((4, column * 51 + 25 + 207), (6, row * 120 + 106 + y),
                                  (8, kind), (10, pose)):
                put_actor(actor, offset, value)
            machine.reset(level)
            machine.cpu.mem_write(machine.A5 - 0x5056, bytes(actor))
            machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(range(62)))
            machine.cpu.mem_write(machine.A5 - 0x448e, bytes(range(160)))
            machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', *COLD_CACHE))
            machine.cpu.mem_write(machine.A5 - 0x34bc, struct.pack('>4h', 0, 0, 365, 510))
            machine.cpu.mem_write(machine.A5 - 0x4fec, struct.pack('>4h', 0, 0, 365, 510))
            machine.cpu.mem_write(machine.A5 - 0x1f58, struct.pack('>I', machine.INTERSECTION))
            machine.cpu.mem_write(machine.A5 - 0x452c + environment * 4,
                                   struct.pack('>I', machine.A5 + pointer))
            # Entry416a is inside ClipChar's LINK frame, after its supplied
            # visibility/bounds prefix. Keep stack locals separate from args.
            machine.cpu.reg_write(UC_M68K_REG_A6, machine.STACK - 0x100)
            state = SequenceState(70, actor_type=kind, action=pose, facing=facing,
                                  target_x=column * 51 + 25, current_y=y, level_kind=environment)
            expected = cavern_exit_clip(LevelMap(bytes(level)), 0, row, state,
                                         SimpleNamespace(offset_x=0, aux=0))
            before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
            takes_branch = kind == 0 and 217 <= pose <= 226 and y < -24
            machine.call(4, 0x416a, stop=(4, 0x441e if takes_branch else 0x4210))
            if expected is not None:
                struct.pack_into('>h', before, len(machine.data) - 0x34bc, expected[0])
                struct.pack_into('>h', before, len(machine.data) - 0x34b6, expected[1])
            if takes_branch:
                struct.pack_into('>6h', before, len(machine.data) - 0x34b0,
                                 tile, 79, cell, 1, column, row)
                struct.pack_into('>II', before, len(machine.data) - 0x4824,
                                 machine.LEVEL + 0x780, machine.LEVEL)
            after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
            if after != before or machine.level_bytes(len(level)) != level or machine.services:
                raise AssertionError(dict(number=number, row=row, column=column, tile=tile,
                    pose=pose, y=y, actor=kind, expected=expected,
                    changed=[(hex(i - len(machine.data)), a, b)
                             for i, (a, b) in enumerate(zip(before, after)) if a != b]))
            digest.update(bytes(actor) + struct.pack('>4h', *(expected or (-1, -1)), environment, tile))
            count += 1
    return dict(comparisons=count, mismatches=0, data_rectangles=rects,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                outputs_sha256=digest.hexdigest(),
                supplied=['Initialized DATA pointers and ClipChar A6 frame',
                          'QuickDraw OffsetRect/SectRect'], scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
