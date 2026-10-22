"""Probe original trap-door phase advancement, separately from drawing/restoration."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules
from tools.probe_level7_sequence_selection import signed_word


def advance_reference(mob, cue197_on, cue198_on):
    result = list(mob)
    queries, sounds = [], []
    if result[3] != -1:
        if result[7] & 31 <= 16:
            result[7] = signed_word(result[7] + 1)
        queries.append(197)
        if not cue197_on:
            queries.append(198)
            if not cue198_on:
                sounds.append(198)
    return tuple(result), queries, sounds


class NativeTrapDoorAdvance(NativeRules):
    RANGES = {5: ((0x29e8, 0x2b0e),), 10: ((0x24fa, 0x253e),)}
    SUPPLIED = {}
    BANK = 0xb0010

    def reset(self, level):
        super().reset(level)
        self.queries, self.sounds = [], []
        self.audio = {197: False, 198: False}

    def dispatch(self, cpu, address, size, user):
        if address in (self.address(5, 0x52c8), self.address(5, 0x4d84)):
            stack = cpu.reg_read(self.registers['a7'])
            cue = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            if address == self.address(5, 0x52c8):
                self.queries.append(cue)
                cpu.reg_write(self.registers['d0'], int(self.audio[cue]))
            else:
                self.sounds.append(cue)
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], destination)
            return
        super().dispatch(cpu, address, size, user)

    def mob(self):
        return struct.unpack('>8h', self.cpu.mem_read(self.A5 - 0x44a6, 16))


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    level = prince['LEVL'][2009]['data']
    if (struct.unpack_from('>H', level, 0x2186)[0], struct.unpack_from('>H', level, 0x218a)[0]) != (2, 10):
        raise ValueError('Inconsistent temple fixture')
    machine = NativeTrapDoorAdvance(parse_resource_fork(program_bytes))
    phases = (0, 1, 10, 11, 16, 17, 31, 32, 64, 65, 75, 80, 81, 95, 32752, -32768)
    counts = Counter()
    digest = hashlib.sha256()
    canary = bytes((i * 13 + 7) % 256 for i in range(512))
    for phase, deleted, on197, on198, bank_driver in product(
            phases, (-1, 0, 2), (False, True), (False, True), (False, True)):
        initial = (204, 245, 1, deleted, 0, 10, 1, phase)
        expected, queries, sounds = advance_reference(initial, on197, on198)
        machine.reset(level)
        machine.audio = {197: on197, 198: on198}
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *initial))
        machine.cpu.mem_write(machine.BANK - 16, canary)
        machine.cpu.mem_write(machine.BANK, struct.pack('>8h', *initial))
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
        machine.put_word(-0x4490, 1)
        expected_bank = bytearray(machine.cpu.mem_read(machine.BANK - 16, 512))
        if bank_driver:
            expected_bank[16:32] = struct.pack('>8h', *expected)
        machine.call(5, 0x29e8) if bank_driver else machine.call(10, 0x24fa)
        if (machine.mob() != expected or machine.queries != queries or machine.sounds != sounds
                or machine.level_bytes(len(level)) != level
                or machine.word(-0x4490) != (0 if bank_driver and deleted == -1 else 1)
                or bytes(machine.cpu.mem_read(machine.BANK - 16, 512)) != expected_bank):
            raise AssertionError(dict(initial=initial, bank_driver=bank_driver,
                                      actual=machine.mob(), expected=expected,
                                      queries=machine.queries, sounds=machine.sounds))
        counts['bank_driver' if bank_driver else 'direct'] += 1
        digest.update(struct.pack('>8h', *machine.mob()))
    for count in (0, 1, 3, 30):
        mobs = [(204, 245, 1, -1 if i % 3 == 1 else 0, 0, 10, 1, 75 if i % 3 == 2 else 1)
                for i in range(count)]
        expected = [advance_reference(mob, False, False) for mob in mobs]
        machine.reset(level)
        machine.cpu.mem_write(machine.BANK - 16, canary)
        for index, mob in enumerate(mobs):
            machine.cpu.mem_write(machine.BANK + index * 16, struct.pack('>8h', *mob))
        expected_bank = bytearray(machine.cpu.mem_read(machine.BANK - 16, 512))
        for index, (mob, _queries, _sounds) in enumerate(expected):
            expected_bank[16 + index * 16:32 + index * 16] = struct.pack('>8h', *mob)
        survivors = [mob for mob, _queries, _sounds in expected if mob[3] != -1]
        for index, mob in enumerate(survivors):
            expected_bank[16 + index * 16:32 + index * 16] = struct.pack('>8h', *mob)
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
        machine.put_word(-0x4490, count)
        machine.call(5, 0x29e8)
        if (bytes(machine.cpu.mem_read(machine.BANK - 16, 512)) != expected_bank
                or machine.word(-0x4490) != len(survivors)
                or machine.queries != [cue for _mob, cues, _sounds in expected for cue in cues]
                or machine.sounds != [cue for _mob, _queries, cues in expected for cue in cues]):
            raise AssertionError('Native bank iteration/rejection/canaries differ')
        counts['bank_capacity_controls'] += 1
    traces = []
    for initial_phase in (1, 75):
        machine.reset(level)
        machine.audio[197] = True
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', 204, 245, 1, 0, 0, 10, 1, initial_phase))
        trace = [initial_phase]
        for _ in range(20):
            machine.call(10, 0x24fa)
            trace.append(machine.mob()[7])
        expected = initial_phase
        expected_trace = [expected]
        for _ in range(20):
            expected += int(expected & 31 <= 16)
            expected_trace.append(expected)
        if trace != expected_trace or machine.mob()[3] != 0:
            raise AssertionError('Advance-only sequence unexpectedly restored/deleted itself')
        traces.append(dict(initial=initial_phase, phases=trace,
                           updates_to_low_phase17=next(i for i, value in enumerate(trace) if value & 31 == 17)))
        counts['advance_only_traces'] += 1
    return dict(
        cases=dict(counts), traces=traces, mismatches=0,
        outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        level_sha256=hashlib.sha256(level).hexdigest(),
        supplied=['5:52c8 PrinceSndOn supplied independently for cues197/198',
                  '5:4d84 AddSound records request without playback/state updates'],
        scope=('Full 10:24fa advance helper, plus original MakeRubble 5:29e8 bank '
               'iterator/type10 dispatch and deleted-entry compaction. '
               'Supplied mob records/audio outcomes; full bank and guards compared. No ATM '
               'presentation/restoration, real sound queue, full-frame ordering '
               'or millisecond/game-tick timing equivalence claim.'),
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
