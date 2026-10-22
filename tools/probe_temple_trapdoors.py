"""Probe original temple trap-door triggering and mob creation, without animation."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


def trigger_reference(level, room, cell, actor_column, mob_count):
    if not 1 <= room <= 32 or not 0 <= cell < 30 or not 0 <= mob_count <= 30:
        raise ValueError('Input outside the tested native room/cell/capacity domain')
    result = bytearray(level)
    tile_offset = (room - 1) * 60 + cell * 2
    foreground_offset = 0x780 + (room - 1) * 120 + cell * 4
    if struct.unpack_from('>H', level, tile_offset)[0] != 26:
        raise ValueError('The probe supplies actual type-26 cells only')
    foreground = struct.unpack_from('>H', level, foreground_offset)[0]
    active = not bool(foreground & 0x40)
    cached_foreground = foreground
    mob = None
    if active:
        if actor_column != cell % 10:
            cached_foreground |= 0x40
        struct.pack_into('>H', result, tile_offset, 0)
        struct.pack_into('>H', result, foreground_offset, 0x81)
        row, column = divmod(cell, 10)
        mob = (column * 51, (row + 1) * 120 + 5, room, 0, 0, 10, row,
               75 if cached_foreground & 0x40 else 1)
    return dict(level=bytes(result), cached_foreground=cached_foreground,
                count=mob_count + int(active and mob_count < 30),
                scratch_mob=mob, appended=active and mob_count < 30,
                sounds=[197] if active else [], redraw=[0] if active else [])


class NativeTempleTrapDoors(NativeRules):
    RANGES = {
        4: ((0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x322a, 0x3262)),
        5: ((0x0004, 0x0066), (0x2914, 0x293a)),
        10: ((0x25aa, 0x26d4),),
    }
    SUPPLIED = {}
    BANK = 0xb0010

    def reset(self, level):
        super().reset(level)
        self.sounds, self.redraw = [], []

    def dispatch(self, cpu, address, size, user):
        requests = {(5, 0x4d84): self.sounds, (5, 0x33fa): self.redraw}
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        if (segment, offset) in requests:
            stack = cpu.reg_read(self.registers['a7'])
            value = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            requests[segment, offset].append(value)
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], destination)
            return
        super().dispatch(cpu, address, size, user)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(program_bytes)
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeTempleTrapDoors(program)
    counts = Counter()
    digest = hashlib.sha256()
    locations, level_hashes = [], {}
    canary = bytes((index * 37 + 11) % 256 for index in range(512))
    for number in range(10, 14):
        original = prince['LEVL'][1999 + number]['data']
        if (struct.unpack_from('>H', original, 0x2186)[0] != 2
                or struct.unpack_from('>H', original, 0x218a)[0] != number):
            raise ValueError('Inconsistent temple level fixture')
        level_hashes[str(number)] = hashlib.sha256(original).hexdigest()
        for room in range(1, 33):
            for cell in range(30):
                if struct.unpack_from('>H', original, (room - 1) * 60 + cell * 2)[0] != 26:
                    continue
                locations.append(dict(level=number, room=room, cell=cell))
                for foreground, relative_column, mob_count in product(
                        (0, 1, 63, 64, 65, 127, 128, 0x8000), (-1, 0, 1), (0, 1, 29, 30)):
                    supplied = bytearray(original)
                    struct.pack_into('>H', supplied, 0x780 + (room - 1) * 120 + cell * 4, foreground)
                    machine.reset(supplied)
                    machine.cpu.mem_write(machine.A5 - 0x5056, bytes(62))
                    actor_column = cell % 10 + relative_column
                    machine.put_word(-0x504a, actor_column)
                    machine.cpu.mem_write(machine.BANK - 16, canary)
                    machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
                    machine.put_word(-0x4490, mob_count)
                    initial_scratch = bytes(range(16))
                    machine.cpu.mem_write(machine.A5 - 0x44a6, initial_scratch)
                    if machine.call(4, 0x27ee, (room, cell % 10, cell // 10)) != 26:
                        raise AssertionError('Native ReadCell did not select the supplied trap door')
                    if machine.word(-0x34ac) != cell:
                        raise AssertionError('Native cached cell index differs')
                    working = bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62))
                    expected = trigger_reference(supplied, room, cell, actor_column, mob_count)
                    expected_bank = bytearray(canary)
                    expected_scratch = (initial_scratch if expected['scratch_mob'] is None else
                                        struct.pack('>8h', *expected['scratch_mob']))
                    if expected['appended']:
                        start = 16 + mob_count * 16
                        expected_bank[start:start + 16] = expected_scratch
                    machine.call(10, 0x25aa)
                    if (machine.level_bytes(len(original)) != expected['level']
                            or machine.word(-0x4490) != expected['count']
                            or (machine.word(-0x34ae) & 65535) != expected['cached_foreground']
                            or bytes(machine.cpu.mem_read(machine.A5 - 0x44a6, 16)) != expected_scratch
                            or bytes(machine.cpu.mem_read(machine.BANK - 16, 512)) != expected_bank
                            or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != working
                            or machine.sounds != expected['sounds'] or machine.redraw != expected['redraw']):
                        raise AssertionError(dict(level=number, room=room, cell=cell,
                                                  foreground=foreground, relative_column=relative_column,
                                                  mob_count=mob_count, sounds=machine.sounds,
                                                  redraw=machine.redraw))
                    counts['trigger'] += 1
                    counts['flag_rejection'] += expected['scratch_mob'] is None
                    counts['appended'] += expected['appended']
                    counts['capacity_rejection_after_mutation'] += (
                        expected['scratch_mob'] is not None and mob_count == 30)
                    digest.update(machine.level_bytes(len(original))
                                  + bytes(machine.cpu.mem_read(machine.BANK - 16, 512)) + expected_scratch)
    return dict(
        cases=dict(counts), locations=locations, mismatches=0,
        outputs_sha256=digest.hexdigest(), level_hashes=level_hashes,
        executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        supplied=['5:4d84 AddSound records cue, no audio playback',
                  '5:33fa MarkMobRedraw records argument, no drawing/redraw state'],
        scope=('Full TriggerTrapDoor 10:25aa, constructor 10:25e8 and native mob append '
               '5:2914 including its capacity limit. Native ReadCell/CalcBlue establish '
               'the cache and room pointers. Actual trap-door locations with supplied '
               'foreground/actor column/mob counts and canary-filled bank. No ATM animation, '
               'call-site admission, complete redraw, collision, live reachability or campaign claim.'),
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
