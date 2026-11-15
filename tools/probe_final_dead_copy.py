"""Compare CODE 9:00e2 (FinlCheckDeadOpp) with the port's dead-copy step.

The original LEVL 2013 and CODE 9 execute in Unicorn, with ReadCell
4:26e2-29c0, FirstInRow 4:322a and the room loader 5:0004 run natively.
Supplied endpoints: Rnd 17:6e06 (returns the case's draw), TriggerFlask
5:1ce8, the cell redraw 5:18f0, SetSeq 6:0006 and AddSound 5:4d84. Each
records its arguments; their own writes, animation and sound are excluded.
"""

import argparse
from itertools import product
from pathlib import Path
import struct

from pop2.final_jaffars import (
    VANISH_SEQUENCE, dead_copy_step, drop_foreground,
)
from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules

ROOM = 3
OWN, OTHER = 1, 0


class Draws:
    def __init__(self, value):
        self.value = value
        self.stops = []

    def randrange(self, stop):
        self.stops.append(stop)
        return self.value


class NativeDeadCopy(NativeRules):
    RANGES = {
        **NativeRules.RANGES,
        9: ((0x00e2, 0x01ec),),
    }
    SUPPLIED = {
        (17, 0x6e06): 'rnd', (5, 0x1ce8): 'trigger_flask', (5, 0x18f0): 'redraw',
        (6, 0x0006): 'set_sequence', (5, 0x4d84): 'add_sound',
    }

    def reset(self, level):
        super().reset(level)
        self.roll = 0
        self.calls = []

    def dispatch(self, cpu, address, size, user):
        relative = address - self.CODE_BASE
        key = divmod(relative, 0x10000)
        service = self.SUPPLIED.get(key)
        if service is not None:
            stack = cpu.reg_read(self.registers['a7'])
            count = 2 if service == 'trigger_flask' else 1
            self.calls.append((service, struct.unpack(f'>{count}h', cpu.mem_read(stack + 4, 2 * count))))
        super().dispatch(cpu, address, size, user)
        if service == 'rnd':
            cpu.reg_write(self.registers['d0'], self.roll)


def expected_calls(step, alive_before, roll_drawn):
    calls = []
    if roll_drawn:
        calls.append(('rnd', (2,)))
    if step.drop:
        calls += [('trigger_flask', (ROOM, step.cell)), ('redraw', (step.cell,))]
    if step.vanish:
        calls += [('set_sequence', (VANISH_SEQUENCE,)), ('add_sound', (243,))]
    return calls


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    original = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2013]['data']
    if (len(original), struct.unpack_from('>H', original, 0x2186)[0]) != (18890, 6):
        raise ValueError('Unexpected preserved final-level header')
    machine = NativeDeadCopy(executable)
    cases = []
    for row, column, kind, objects, roll, pending in product(
            (0, 1, 2), range(10), (0, 1, 10), (0, 3, 4), (0, 1, 2), (0, 1)):
        cases.append((6, pending, 0, row, column, kind, objects, roll, OWN))
    for alive, pending, selected, target in product(
            (0, 5, 7, 50, 95, 96, 97, 140), (0, 1), (0, 239), (OWN, OTHER)):
        cases.append((alive, pending, selected, 2, 5, 1, 0, 1, target))
    compared = 0
    for alive, pending, selected, row, column, kind, objects, roll, target in cases:
        level = bytearray(original)
        cell = row * 10 + column
        struct.pack_into('>H', level, (ROOM - 1) * 60 + cell * 2, kind)
        machine.reset(level)
        machine.roll = roll
        for offset, value in ((-0x503a, alive), (-0x503e, pending), (-0x502e, selected),
                              (-0x5040, ROOM), (-0x5048, row), (-0x504a, column),
                              (-0x43e6, objects), (-0x5056, OWN), (-0x5098, target)):
            machine.put_word(offset, value)
        machine.call(9, 0x00e2)
        draws = Draws(roll)
        step = dead_copy_step(alive, pending, selected, kind, objects, row, column, draws)
        expected_level = bytearray(original)
        struct.pack_into('>H', expected_level, (ROOM - 1) * 60 + cell * 2, kind)
        if step.drop:
            struct.pack_into('>H', expected_level, (ROOM - 1) * 60 + step.cell * 2, 10)
            struct.pack_into('>H', expected_level, 0x780 + (ROOM - 1) * 120 + step.cell * 4,
                             drop_foreground(step.drop))
        expected_target = -1 if step.vanish and target == OWN else target
        actual = (machine.word(-0x503a), machine.calls, machine.word(-0x5098),
                  machine.level_bytes(len(original)) == bytes(expected_level))
        wanted = (step.alive, expected_calls(step, alive, bool(draws.stops)),
                  expected_target, True)
        if actual != wanted or draws.stops not in ([], [3]):
            raise AssertionError((alive, pending, selected, row, column, kind, objects, roll,
                                  target, actual, wanted))
        compared += 1
    return compared, dict(machine.services)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', default='../PoP2-Mac-Code-Recovery')
    args = parser.parse_args()
    compared, _services = run_probe(args.recovery)
    print(f'{compared} original CODE 9:00e2 dead-copy cases agree')
