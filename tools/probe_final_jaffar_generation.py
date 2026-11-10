"""Compare CODE 9:0202's admission and position with the port's rule.

The original LEVL and CODE 9 execute in Unicorn. Only Rnd(17:6e06) and the
9:03c8 record constructor are supplied. The latter records its arguments;
the constructor's writes, animation, sound and drawing are excluded here.
"""

import argparse
from itertools import product
from pathlib import Path
import struct

from pop2.final_jaffars import next_jaffar_spawn
from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class Draws:
    def __init__(self, values):
        self.values = iter(values)
        self.stops = []

    def randrange(self, stop):
        self.stops.append(stop)
        return next(self.values)


class NativeJaffarCheck(NativeRules):
    RANGES = {9: ((0x0202, 0x0290),)}
    SUPPLIED = {(17, 0x6e06): 'rnd', (9, 0x03c8): 'record_constructor'}

    def reset(self, level):
        super().reset(level)
        self.draws = None
        self.spawn = None
        self.stops = []

    def dispatch(self, cpu, address, size, user):
        stack = cpu.reg_read(self.registers['a7'])
        if address == self.address(17, 0x6e06):
            stop = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            self.stops.append(stop)
        elif address == self.address(9, 0x03c8):
            self.spawn = struct.unpack('>2h', cpu.mem_read(stack + 4, 4))
        super().dispatch(cpu, address, size, user)
        if address == self.address(17, 0x6e06):
            cpu.reg_write(self.registers['d0'], next(self.draws))


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2013]['data']
    if (len(level), struct.unpack_from('>2H', level, 0x2186)[0],
            struct.unpack_from('>H', level, 0x218a)[0],
            struct.unpack_from('>H', level, 0x2326)[0]) != (18890, 6, 14, 0):
        raise ValueError('Unexpected preserved final-level header or room-3 count')
    machine = NativeJaffarCheck(executable)
    compared = 0
    for count, sequence, first_row, player_row, gate, boost in product(
            (0, 1, 2), (2, 238), (0, 1), (0, 1, 2), (0, 1, 19), (0, 1)):
        machine.reset(level)
        machine.put_word(-0x51e0, sequence)
        machine.put_word(-0x51fa, first_row)
        machine.put_word(-0x50c4, player_row)
        machine.draws = iter((gate, boost)) if count else iter((boost,))
        machine.call(9, 0x0202, (count,))
        expected_rng = Draws((gate, boost, 0) if count else (boost, 0))
        expected = next_jaffar_spawn(count, sequence, first_row, player_row, expected_rng)
        position = None if expected is None else (expected.row, expected.column)
        native_stops = [stop - 1 for stop in expected_rng.stops[:len(machine.stops)]]
        if machine.spawn != position or machine.stops != native_stops:
            raise AssertionError((count, sequence, first_row, player_row, gate, boost,
                                  machine.spawn, machine.stops, position, expected_rng.stops))
        compared += 1
    return compared


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', default='../PoP2-Mac-Code-Recovery')
    args = parser.parse_args()
    print(f'{run_probe(args.recovery)} original CODE 9 admission cases agree')
