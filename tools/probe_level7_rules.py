"""Execute bounded original level-seven entry and crevice-rule probes.

Only visibility/redraw services are supplied. Resource bytes and the detailed
report remain local; this tool is not part of the game's runtime or importer.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.extract_attract import jump_targets
from tools.extract_enemy_profiles import expand_a5_data


class NativeRules:
    A5, LEVEL, STACK, END = 0x80000, 0xa0000, 0xf0000, 0xff000
    CODE_BASE = 0x100000
    RANGES = {
        2: ((0x00e8, 0x017e), (0x5d98, 0x5e36)),
        4: ((0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x322a, 0x3262), (0x39fc, 0x3a32)),
        5: ((0x0004, 0x0066), (0x4e0c, 0x4e42)),
        7: ((0x3328, 0x33ec), (0x3404, 0x355a)),
    }
    SUPPLIED = {(5, 0x3960): 'visibility', (5, 0x1936): 'redraw'}

    def __init__(self, program):
        from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
        from unicorn.m68k_const import (
            UC_CPU_M68K_M68000, UC_M68K_REG_A2, UC_M68K_REG_A5, UC_M68K_REG_A7,
            UC_M68K_REG_D0, UC_M68K_REG_D3, UC_M68K_REG_PC,
        )

        self.registers = dict(a2=UC_M68K_REG_A2, a5=UC_M68K_REG_A5, a7=UC_M68K_REG_A7,
                              d0=UC_M68K_REG_D0, d3=UC_M68K_REG_D3, pc=UC_M68K_REG_PC)
        self.cpu = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        self.cpu.ctl_set_cpu_model(UC_CPU_M68K_M68000)
        self.cpu.mem_map(0, 0x1000000)
        for segment, resource in program['CODE'].items():
            if segment:
                self.cpu.mem_write(self.address(segment, 0), resource['data'])
        self.stubs = set()
        for offset, target in jump_targets(program['CODE'][0]['data'], program['CODE']):
            address = self.A5 + offset
            self.stubs.add(address)
            self.cpu.mem_write(address, b'\x4e\xf9' + struct.pack('>I', self.CODE_BASE + target))
        self.data = expand_a5_data(program)
        self.initial_context = self.cpu.context_save()
        self.stop_at = self.END
        self.services = Counter()
        self.reached = False
        self.failure = None
        self.hook = self.cpu.hook_add(UC_HOOK_CODE, self.dispatch)

    @classmethod
    def address(cls, segment, offset):
        return cls.CODE_BASE + segment * 0x10000 + offset

    def put_word(self, offset, value):
        self.cpu.mem_write(self.A5 + offset, struct.pack('>H', value & 65535))

    def word(self, offset):
        return struct.unpack('>h', self.cpu.mem_read(self.A5 + offset, 2))[0]

    def reset(self, level):
        self.cpu.context_restore(self.initial_context)
        self.cpu.mem_write(self.A5 - len(self.data), self.data)
        self.cpu.mem_write(self.LEVEL, bytes(level))
        self.cpu.mem_write(self.A5 - 0x5014, struct.pack('>I', self.LEVEL))
        self.put_word(-0x34aa, 0)
        self.put_word(-0x34a8, -32768)
        self.put_word(-0x34a6, -32768)
        self.cpu.reg_write(self.registers['a5'], self.A5)
        self.cpu.reg_write(self.registers['a2'], self.LEVEL)
        self.services.clear()
        self.reached = False
        self.failure = None

    def dispatch(self, cpu, address, size, _user):
        if address == self.stop_at:
            self.reached = True
            cpu.emu_stop()
            return
        relative = address - self.CODE_BASE
        segment, offset = divmod(relative, 0x10000)
        service = self.SUPPLIED.get((segment, offset))
        if service is not None:
            self.services[service] += 1
            cpu.reg_write(self.registers['d0'], 0)
            stack = cpu.reg_read(self.registers['a7'])
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], destination)
        elif (address not in self.stubs
              and not any(low <= offset <= high for low, high in self.RANGES.get(segment, ()))):
            self.failure = f'Unexpected native instruction at {segment}:{offset:04x}'
            cpu.emu_stop()

    def call(self, segment, offset, args=(), stop=None, *, arg_bytes=None):
        if arg_bytes is not None and args:
            raise ValueError('Supply either word arguments or explicit stack bytes')
        self.reached = False
        self.failure = None
        self.stop_at = self.END if stop is None else self.address(*stop)
        arguments = (arg_bytes if arg_bytes is not None else
                     b''.join(struct.pack('>H', value & 65535) for value in args))
        self.cpu.mem_write(self.STACK, struct.pack('>I', self.END)
                           + arguments)
        self.cpu.reg_write(self.registers['a7'], self.STACK)
        self.cpu.emu_start(self.address(segment, offset), 0, count=50000)
        if self.failure or not self.reached:
            pc = self.cpu.reg_read(self.registers['pc'])
            raise RuntimeError(self.failure or f'Native probe did not reach stop (PC {pc:x})')
        return self.cpu.reg_read(self.registers['d0']) & 65535

    def level_bytes(self, size):
        return bytes(self.cpu.mem_read(self.LEVEL, size))


def read_cell(level, room, column, row):
    """Independent narrow ReadCell model: horizontal neighbors, in-range row."""
    if not 0 <= row < 3:
        raise ValueError('This reference model excludes vertical room traversal')
    while room and not 0 <= column < 10:
        side = 0 if column < 0 else 2
        room = struct.unpack_from('>H', level, 0x2080 + (room - 1) * 8 + side)[0]
        column += 10 if side == 0 else -10
    if not room:
        return None
    cell = row * 10 + column
    kind = struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0]
    foreground = 0x780 + (room - 1) * 120 + cell * 4
    return kind, foreground


def reference_scan(level, room, column, row, reveal):
    result = bytearray(level)
    # The original searches a whole row, extending past its edge near a join.
    first, limit = min(column - 2, 0), max(column + 3, 10)
    found = None
    for current in range(first, limit):
        tile = read_cell(level, room, current, row)
        if tile is not None and tile[0] == 7:
            found = current
            break
    if found is None:
        return bytes(result)
    first = found
    while (tile := read_cell(level, room, first - 1, row)) is not None and tile[0] == 7:
        first -= 1
        if first < -640:
            raise ValueError('Cyclic crevice row is outside the probe scope')
    for current in range(first, 641):
        tile = read_cell(level, room, current, row)
        if tile is None or tile[0] != 7:
            return bytes(result)
        foreground = struct.unpack_from('>H', level, tile[1])[0]
        value = foreground | 0x80 if reveal else foreground & 0xff7f
        struct.pack_into('>H', result, tile[1], value)
    raise ValueError('Cyclic crevice row is outside the probe scope')


def reference_front(level, room, column, row, facing, selected):
    tile = read_cell(level, room, column + (-1 if facing == -1 else 1), row)
    if (selected == 17 or tile is None or tile[0] != 7
            or struct.unpack_from('>H', level, tile[1])[0] & 3 == 3):
        return bytes(level)
    return reference_scan(level, room, column, row, True)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(program_bytes)
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    level = prince['LEVL'][2006]['data']
    machine = NativeRules(program)
    totals, changed = Counter(), Counter()
    digest = hashlib.sha256()

    def check(actual, expected, label):
        if actual != expected:
            raise AssertionError(f'Native/reference difference: {label}')
        totals[label[0]] += 1
        changed[label[0]] += actual != level
        digest.update(actual)

    for room in range(1, 33):
        for row in range(3):
            for column in range(10):
                for reveal in (0, 1):
                    machine.reset(level)
                    machine.call(7, 0x332a, (reveal, room, column, row))
                    check(machine.level_bytes(len(level)),
                          reference_scan(level, room, column, row, reveal),
                          ('scan', room, column, row, reveal))
                for facing in (-1, 0):
                    for selected in (5, 17):
                        machine.reset(level)
                        for offset, value in ((-0x5040, room), (-0x504a, column),
                                              (-0x5048, row), (-0x5054, facing),
                                              (-0x502e, selected)):
                            machine.put_word(offset, value)
                        machine.call(7, 0x3404)
                        check(machine.level_bytes(len(level)),
                              reference_front(level, room, column, row, facing, selected),
                              ('front', room, column, row, facing, selected))
    print('Original crevice scan/front probes passed', flush=True)

    for room in range(1, 33):
        for cell in range(30):
            kind = struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0]
            if kind != 7:
                continue
            for facing in (-1, 0):
                column = cell % 10 - (-1 if facing == -1 else 1)
                if not 0 <= column < 10:
                    continue
                supplied = bytearray(level)
                foreground = 0x780 + (room - 1) * 120 + cell * 4
                value = struct.unpack_from('>H', supplied, foreground)[0]
                struct.pack_into('>H', supplied, foreground, value | 3)
                machine.reset(supplied)
                for offset, value in ((-0x5040, room), (-0x504a, column),
                                      (-0x5048, cell // 10), (-0x5054, facing),
                                      (-0x502e, 5)):
                    machine.put_word(offset, value)
                machine.call(7, 0x3404)
                actual = machine.level_bytes(len(level))
                if actual != bytes(supplied):
                    raise AssertionError('Foreground low-bits-3 gate did not reject reveal')
                totals['supplied_low_bits_3'] += 1

    machine.reset(level)
    machine.call(7, 0x3328)
    assert machine.level_bytes(len(level)) == level
    assert not machine.services

    machine.reset(level)
    machine.call(2, 0x5d98, stop=(2, 0x5e36))
    entry_sequence = machine.cpu.reg_read(machine.registers['d3']) & 65535
    assert entry_sequence == 5
    machine.reset(level)
    end_song = machine.call(5, 0x4e0c)
    assert end_song == 124

    for resume in (0, 1):
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5018, struct.pack('>I', resume))
        for offset in (-0x521c, -0x4ff0, -0x50bc):
            machine.put_word(offset, 0)
        assert machine.call(2, 0x00e8) == 0

    return dict(
        level=7, executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        level_sha256=hashlib.sha256(level).hexdigest(), cases=dict(totals),
        cases_changing_level=dict(changed), mismatches=0, outputs_sha256=digest.hexdigest(),
        entry_sequence=entry_sequence, end_song=end_song,
        entry_nis_gate=dict(fresh=0, resumed=0), named_change_crevices_entry='Immediate RTS',
        supplied_services=['5:3960 visibility returns 0', '5:1936 redraw returns without drawing'],
        scope=('Original routines 7:332a and 7:3404 on all 960 actual level cells, '
               'both reveal values / facings and selected SEQS 5/17. Additional '
               'counterfactual low-bits-3 foreground rejection controls. Native ReadCell, '
               'CalcBlue, row and direction tables execute; reference decoder is independent '
               'of port LevelMap. Selected fields and actor positions are supplied. '
               'Entry selector stops before JumpSeq. No controller reachability, art, '
               'enemy AI, complete entry/exit, scene playback or frame timing claim.'),
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
