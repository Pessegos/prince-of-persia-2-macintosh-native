"""Bound native permanent-pressure setup independently of its PushPlate callee."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules
from tools.probe_temple_plate_release import plate_inventory


def permanent_pressure_reference(level, cache):
    if len(level) < 0x2080 or len(cache) != 6 or any(not -32768 <= v <= 32767 for v in cache):
        raise ValueError('Expected a complete link table and six signed cache words')
    index = cache[1] & 255
    result = bytearray(level)
    struct.pack_into('>h', result, 0x1680 + index * 10 + 4, 31)
    return dict(level=bytes(result), cache=tuple(cache), requests=[((cache[0], index), 31, tuple(cache))])


class NativePermanentPressure(NativeRules):
    RANGES = {5: ((0x22b8, 0x22ee), (0x252e, 0x2552))}
    SUPPLIED = {(5, 0x240c): 'push_request'}

    def reset(self, level):
        super().reset(level)
        self.requests = []

    def dispatch(self, cpu, address, size, user):
        if address == self.address(5, 0x240c):
            stack = cpu.reg_read(self.registers['a7'])
            args = struct.unpack('>2h', cpu.mem_read(stack + 4, 4))
            cache = struct.unpack('>6h', cpu.mem_read(self.A5 - 0x34b0, 12))
            timer = struct.unpack('>h', cpu.mem_read(self.LEVEL + 0x1680 + args[1] * 10 + 4, 2))[0]
            self.requests.append((args, timer, cache))
        super().dispatch(cpu, address, size, user)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativePermanentPressure(parse_resource_fork(executable))
    counts, digest = Counter(), hashlib.sha256()
    current = bytes((i * 11 + 3) % 256 for i in range(62))
    saved = bytes((i * 7 + 17) % 256 for i in range(62))
    mobs = bytes((i * 37 + 11) % 256 for i in range(512))
    trobs = bytes((i * 19 + 7) % 256 for i in range(160))

    def compare(level, cache, label):
        expected = permanent_pressure_reference(level, cache)
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', *cache))
        machine.cpu.mem_write(machine.A5 - 0x5056, current)
        machine.cpu.mem_write(machine.A5 - 0x50d2, saved)
        machine.cpu.mem_write(0xb0000, mobs)
        machine.cpu.mem_write(machine.A5 - 0x448e, trobs)
        machine.put_word(-0x4490, 17)
        machine.put_word(-0x43e6, 19)
        machine.put_word(-0x4f9e, 4321)
        machine.cpu.reg_write(machine.registers['d3'], 0x12345678)
        machine.call(5, 0x252e)
        actual = dict(level=machine.level_bytes(len(level)),
                      cache=struct.unpack('>6h', machine.cpu.mem_read(machine.A5 - 0x34b0, 12)),
                      requests=machine.requests)
        if (actual != expected or machine.services != Counter(push_request=1)
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != current
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != saved
                or bytes(machine.cpu.mem_read(0xb0000, 512)) != mobs
                or bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)) != trobs
                or machine.word(-0x4490) != 17 or machine.word(-0x43e6) != 19
                or machine.word(-0x4f9e) != 4321
                or machine.cpu.reg_read(machine.registers['d3']) != 0x12345678):
            raise AssertionError(dict(label=label, cache=cache, actual=actual, expected=expected,
                                      services=machine.services))
        counts[label] += 1
        digest.update(actual['level'])
        digest.update(json.dumps([actual['cache'], actual['requests']]).encode('ascii'))

    inventory = plate_inventory(resources)
    if len(inventory) != 68:
        raise ValueError('Expected68 original header-admitted temple plate markers')
    for _number, original, room, cell, kind in inventory:
        foreground = struct.unpack_from('>H', original, 0x780 + (room - 1) * 120 + cell * 4)[0]
        for timer, depressed_control in product((-32768, -1, 0, 1, 2, 30, 31, 32767), (False, True)):
            value = foreground ^ (0x2000 if depressed_control else 0)
            level = bytearray(original)
            struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, value)
            struct.pack_into('>h', level, 0x1680 + (value & 255) * 10 + 4, timer)
            signed_foreground = (value + 32768) % 65536 - 32768
            cache = (kind, signed_foreground, cell, room, cell % 10, cell // 10)
            compare(bytes(level), cache, 'supplied-depressed-flag' if depressed_control else 'original-marker')
    original = resources['LEVL'][2009]['data']
    for index, high, kind, timer in product((0, 1, 127, 128, 254, 255), (0, 0x2000, 0xff00),
                                           (-1, 0, 5, 6, 34, 32767), (0, 31)):
        level = bytearray(original)
        struct.pack_into('>h', level, 0x1680 + index * 10 + 4, timer)
        foreground = ((high | index) + 32768) % 65536 - 32768
        compare(bytes(level), (kind, foreground, 17, 19, -32768, -32768), 'supplied-cache-control')
    return dict(cases=dict(counts), original_sources=len(inventory), mismatches=0,
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
                level_sha256={str(n): hashlib.sha256(resources['LEVL'][1999 + n]['data']).hexdigest()
                              for n in range(10, 14)},
                supplied_services=['5:240c PushPlate: capture arguments/timer/cache, return0; body NOT executed'],
                scope='Full native5:252e permanent wrapper and5:22b8 timer setter. Cached cell supplied; '
                      'all68 original admitted plate markers plus explicit cache/kind controls. No CheckPress, '
                      'PushPlate effects, link traversal, admission of synthetic kinds, timer release, pixels '
                      'or runtime temple integration claimed.')


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
