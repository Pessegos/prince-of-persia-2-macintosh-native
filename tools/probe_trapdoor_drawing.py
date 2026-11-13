"""Original DrawObjTrapDoor command lists, with AddMid recorded as an endpoint.

Phase and projected MOB X/Y are supplied. The original phase/frame selection
and piece calls execute; AddMid is recorded, not rendered. Its inclusive Y
argument is converted to the exclusive bottom stored by 3:0302-030c. No
QuickDraw pixels, dirty-cell ordering, actor order or full FrameAdv is run.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from pop2.caverns import trapdoor_drawing_commands
from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class NativeTrapDoorDrawing(NativeRules):
    RANGES = {10: ((0x26ea, 0x2790),)}
    SUPPLIED = {(3, 0x01e6): 'add_mid'}

    def reset(self, level):
        super().reset(level)
        self.commands = []

    def dispatch(self, cpu, address, size, user):
        if address == self.address(3, 0x01e6):
            stack = cpu.reg_read(self.registers['a7'])
            library, shape, x, y, mode = struct.unpack('>5h', cpu.mem_read(stack + 4, 10))
            if library != 4:
                raise AssertionError('Unexpected shape library')
            self.commands.append(['back', 3500 + shape, x, y + 1, mode])
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    prince_bytes = (forks / 'Prince.rsrc.bin').read_bytes()
    temple_bytes = (forks / 'Temple.rsrc.bin').read_bytes()
    prince = parse_resource_fork(prince_bytes)
    temple = parse_resource_fork(temple_bytes)
    if struct.unpack_from('>H', temple['SHPL'][3500]['data'])[0] != 3501:
        raise AssertionError('Unexpected temple shape-library base')
    machine = NativeTrapDoorDrawing(parse_resource_fork(executable))
    mapping = struct.unpack_from('>18h', machine.data, len(machine.data) - 0x2866)
    frames = [struct.unpack_from('>3h', machine.data, len(machine.data) - 0x2842 + index * 6)
              for index in range(5)]
    counts, examples = Counter(), {}
    digest = hashlib.sha256()
    for number in (10, 11, 12, 13):
        level = prince['LEVL'][1999 + number]['data']
        if (struct.unpack_from('>H', level, 0x2186)[0] != 2
                or struct.unpack_from('>H', level, 0x218a)[0] != number):
            raise AssertionError('Wrong temple level/environment header')
        for room in range(32):
            for cell in range(30):
                if struct.unpack_from('>H', level, room * 60 + cell * 2)[0] != 26:
                    continue
                counts['locations'] += 1
                row, column = divmod(cell, 10)
                for flags in (0, 64):
                    for phase in range(1, 17):
                        shape, dx, dy = frames[mapping[phase]]
                        x, y = column * 51 + dx, (row + 1) * 120 + 5 + dy
                        machine.reset(level)
                        machine.put_word(-0x34c4, x)
                        machine.put_word(-0x34c2, y)
                        machine.put_word(-0x34c0, flags | phase)
                        machine.call(10, 0x26ea, (138,))
                        expected = list(trapdoor_drawing_commands(3500 + shape, x, y))
                        if (machine.commands != expected
                                or machine.level_bytes(len(level)) != level
                                or machine.services != Counter(add_mid=len(expected))):
                            raise AssertionError((number, room + 1, cell, flags, phase,
                                                  machine.commands, expected))
                        counts['comparisons'] += 1
                        counts['commands'] += len(expected)
                        counts['flat_poses'] += int(shape == 28)
                        examples.setdefault(str(shape), machine.commands)
                        digest.update(json.dumps(machine.commands).encode('ascii'))
    return dict(counts=dict(counts), mismatches=0, examples=examples, scope=__doc__,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                prince_sha256=hashlib.sha256(prince_bytes).hexdigest(),
                temple_sha256=hashlib.sha256(temple_bytes).hexdigest(),
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
