"""Execute original neck alignment with real Head metadata and sprite dimensions."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


def neck_alignment(metadata, width, actor, facing, prince_facing, prince_point):
    if actor not in (7, 8) or facing not in (-1, 0) or prince_facing not in (-1, 0):
        raise ValueError('Only tested head types and native facings are supported')
    if prince_point is None:
        return None
    dy, dx = metadata
    if facing == prince_facing:
        dx = -dx - width - (17 if actor == 7 else 25)
    if actor == 8:
        dx += 10
    if facing == 0:
        dx = -dx
    x, y = prince_point[0] + dx, prince_point[1] + dy
    return dict(screen_x=x, screen_y=y, native_x=x + 207)


class NativeNeckAlignment(NativeRules):
    RANGES = {3: ((0x3e7c, 0x3ec4),), 7: ((0x0006, 0x00e0),)}
    SUPPLIED = {}
    HANDLE, METADATA, OBJECTS = 0xb3000, 0xb4000, 0xb7000

    def __init__(self, program, head):
        super().__init__(program)
        self.cpu.mem_write(self.HANDLE, struct.pack('>I', self.METADATA))
        self.cpu.mem_write(self.METADATA, head['\0\0\0\0'][755]['data'])
        base = struct.unpack_from('>H', head['SHPL'][750]['data'])[0]
        self.sizes = {rid - base + 1: struct.unpack_from('>hH', item['data'], 4)
                      for rid, item in head['SHAP'].items()}

    def dispatch(self, cpu, address, size, user):
        if address in (self.address(7, 0x0028), self.address(7, 0x00cc)):
            self.services['handle_lock_or_unlock'] += 1
            cpu.reg_write(self.registers['pc'], address + 2)
            return
        if address == self.address(17, 0x673a):
            stack = cpu.reg_read(self.registers['a7'])
            index = struct.unpack('>h', cpu.mem_read(stack + 8, 2))[0]
            point = struct.unpack('>I', cpu.mem_read(stack + 10, 4))[0]
            width, height = self.sizes[index]
            cpu.mem_write(point, struct.pack('>2h', height, width))
            self.services['actual_shap_size'] += 1
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], destination)
            return
        super().dispatch(cpu, address, size, user)

    def configure(self, level, actor, facing, prince_facing, index, sprite, point, present=True):
        self.reset(level)
        self.cpu.mem_write(self.A5 - 0x2c8a, struct.pack('>I', self.HANDLE))
        self.cpu.mem_write(self.A5 - 0x4cb2, struct.pack('>I', self.OBJECTS))
        # A nonmatching slot precedes the Prince to exercise native lookup.
        objects = bytearray(56)
        struct.pack_into('>4h', objects, 0, 999, 999, 2, 0)
        struct.pack_into('>h', objects, 0x0c, 1)
        struct.pack_into('>4h', objects, 28, point[0], point[1], 2, index)
        struct.pack_into('>h', objects, 28 + 0x0c, 0)
        self.cpu.mem_write(self.OBJECTS, bytes(objects))
        for offset, value in ((-0x4826, 2 if present else 1), (-0x504e, actor),
                              (-0x5054, facing), (-0x50d0, prince_facing),
                              (-0x34c0, sprite), (-0x34c4, -999),
                              (-0x34c2, -999), (-0x5052, -999)):
            self.put_word(offset, value)

    def result(self):
        return dict(screen_x=self.word(-0x34c4), screen_y=self.word(-0x34c2),
                    native_x=self.word(-0x5052))


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(program_bytes)
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    head_bytes = (directory / 'Head.rsrc.bin').read_bytes()
    head = parse_resource_fork(head_bytes)
    metadata = head['\0\0\0\0'][755]['data']
    if len(metadata) % 4:
        raise ValueError('Misaligned neck metadata')
    machine = NativeNeckAlignment(program, head)
    level = prince['LEVL'][2006]['data']
    cases, services = Counter(), Counter()
    digest = hashlib.sha256()
    for index in range(len(metadata) // 4):
        item = struct.unpack_from('>2h', metadata, index * 4)
        for actor, facing, prince_facing, sprite, point in product(
                (7, 8), (-1, 0), (-1, 0), (0, 33), ((100, 200), (280, 160))):
            machine.configure(level, actor, facing, prince_facing, index, sprite, point)
            machine.call(7, 0x0006)
            expected = neck_alignment(item, machine.sizes[sprite + 1][0], actor,
                                      facing, prince_facing, point)
            if machine.result() != expected:
                raise AssertionError(dict(index=index, actor=actor, facing=facing,
                                          prince_facing=prince_facing, sprite=sprite,
                                          native=machine.result(), expected=expected))
            if machine.level_bytes(len(level)) != level:
                raise AssertionError('Neck alignment changed the level resource')
            cases['alignment'] += 1
            services.update(machine.services)
            digest.update(struct.pack('>3h', *expected.values()))
    for actor, facing, prince_facing in product((7, 8), (-1, 0), (-1, 0)):
        machine.configure(level, actor, facing, prince_facing, 0, 0, (100, 200), False)
        machine.call(7, 0x0006)
        if machine.result() != dict(screen_x=-999, screen_y=-999, native_x=-999) or machine.services:
            raise AssertionError('Missing Prince object should leave alignment unchanged')
        cases['missing_prince_object'] += 1
    return dict(
        level=7, metadata_entries=len(metadata) // 4, cases=dict(cases), mismatches=0,
        services=dict(services), outputs_sha256=digest.hexdigest(),
        executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        head_sha256=hashlib.sha256(head_bytes).hexdigest(),
        supplied=['Movable handle HLock/HUnlock are inert',
                  'GetImgSize returns actual Head SHAP header dimensions',
                  'Drawn-object list, facing and current head sprite are supplied'],
        scope=('Full original AlignHeadOnKidNeck 7:0006 and native object lookup 3:3e7c, '
               'all original 755 metadata entries, two actual head sprite dimensions. '
               'No neck-event reachability, object production, actual shape rasterization, '
               'bite/damage or AI timing claim.'),
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
