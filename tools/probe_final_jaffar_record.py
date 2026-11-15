"""Compare the CODE 9:03c8 copy constructor with the port's copy record.

9:0202 (admission) and 9:03c8 (constructor), FirstInRow 4:322a and
GetOppInfoIdx 6:3642 run natively on the original LEVL 2013. Supplied
endpoints, which only record their arguments: Rnd 17:6e06 (the case's
draws), the palette-bank helpers 6:40f6/6:41dc, 4:31fa, 4:34e2, SetSeq
6:0006, 4:2c0c, AddSound 5:4d84 and 4:4a46. Drawing, sound, resource loading
and the record's later animation are excluded.
"""

import argparse
from itertools import product
from pathlib import Path
import struct

from pop2.final_jaffars import APPEAR_SEQUENCE, SHIMMER_SOUND, SKILL, next_jaffar_spawn
from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules

ROOM = 3
COUNT = 0x20e6 + ROOM * 0xc0
RECORDS = 0x21a6 + (ROOM - 1) * 0xc0 + 2
RECORD_SIZE = 0x26


class Draws:
    def __init__(self, values):
        self.values = list(values)
        self.stops = []

    def randrange(self, stop):
        self.stops.append(stop)
        return self.values.pop(0)


class NativeJaffarRecord(NativeRules):
    RANGES = {
        4: ((0x322a, 0x3262),),
        6: ((0x3642, 0x36de),),
        9: ((0x0202, 0x0290), (0x03c8, 0x0514)),
    }
    SUPPLIED = {
        (17, 0x6e06): 'rnd', (6, 0x40f6): 'palette_bank', (6, 0x41dc): 'palette_load',
        (4, 0x31fa): 'set_floor', (4, 0x34e2): 'char_4_34e2', (6, 0x0006): 'set_sequence',
        (4, 0x2c0c): 'char_4_2c0c', (5, 0x4d84): 'add_sound', (4, 0x4a46): 'char_4_4a46',
    }

    def reset(self, level):
        super().reset(level)
        self.draws = []
        self.calls = []

    def dispatch(self, cpu, address, size, user):
        key = divmod(address - self.CODE_BASE, 0x10000)
        service = self.SUPPLIED.get(key)
        if service in ('rnd', 'palette_bank', 'set_sequence', 'add_sound'):
            stack = cpu.reg_read(self.registers['a7'])
            self.calls.append((service, struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]))
        elif service is not None:
            self.calls.append((service, None))
        super().dispatch(cpu, address, size, user)
        if service == 'rnd':
            cpu.reg_write(self.registers['d0'], self.draws.pop(0))


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2013]['data']
    if (len(level), struct.unpack_from('>H', level, 0x2186)[0],
            struct.unpack_from('>H', level, COUNT)[0]) != (18890, 6, 0):
        raise ValueError('Unexpected preserved final-level header or room-3 count')
    machine = NativeJaffarRecord(executable)
    compared = 0
    for count, player_row, first_row, boost, life, palette_slot in product(
            (0, 1), (0, 1, 2), (1, 2), (0, 1), (0, 1, 2), (0, 2)):
        data = bytearray(level)
        struct.pack_into('>H', data, COUNT, count)
        machine.reset(data)
        machine.put_word(-0x51e0, 2)
        machine.put_word(-0x51fa, first_row)
        machine.put_word(-0x50c4, player_row)
        machine.put_word(-0x4f88, palette_slot)
        machine.put_word(-0x5098, -1)
        values = ((0,) if count else ()) + (boost, life)
        machine.draws = list(values)
        machine.call(9, 0x0202, (count,))
        draws = Draws(values)
        spawn = next_jaffar_spawn(count, 2, first_row, player_row, draws)
        record = RECORDS + count * RECORD_SIZE
        words = struct.unpack_from('>17h', machine.level_bytes(len(level)), record)
        if spawn is None:
            wanted = (count, words, machine.calls)
            actual = (struct.unpack_from('>H', machine.level_bytes(len(level)), COUNT)[0],
                      struct.unpack_from('>17h', level, record),
                      [('rnd', stop - 1) for stop in draws.stops])
        else:
            facing = 0 if spawn.facing_right else -1
            actual = (struct.unpack_from('>H', machine.level_bytes(len(level)), COUNT)[0],
                      words[0], words[1], words[2], words[3], words[6], words[7], words[8],
                      words[9], words[10], words[13], words[16],
                      machine.word(-0x5056), machine.word(-0x5054), machine.word(-0x5052),
                      machine.word(-0x504a), machine.word(-0x5048), machine.word(-0x5040),
                      machine.word(-0x5036), machine.word(-0x5038), machine.word(-0x5034),
                      machine.word(-0x503a), machine.word(-0x503e), machine.word(-0x503c),
                      machine.word(-0x5098), machine.calls)
            calls = [('rnd', stop - 1) for stop in draws.stops[:-1]]
            if not palette_slot:
                calls += [('palette_bank', 3), ('palette_load', None)]
            calls += [('rnd', draws.stops[-1] - 1), ('set_floor', None), ('char_4_34e2', None),
                      ('set_sequence', APPEAR_SEQUENCE), ('char_4_2c0c', None),
                      ('add_sound', SHIMMER_SOUND), ('char_4_4a46', None)]
            wanted = (count + 1, spawn.cell, spawn.native_x, facing, SKILL,
                      palette_slot, count, 0, spawn.life, 0, spawn.life, spawn.row,
                      count, facing, spawn.native_x, spawn.column, spawn.row, ROOM,
                      spawn.life, spawn.life, spawn.life, -1, 1, 0, count, calls)
        if actual != wanted:
            raise AssertionError((count, player_row, first_row, boost, life, palette_slot,
                                  actual, wanted))
        compared += 1
    return compared


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', default='../PoP2-Mac-Code-Recovery')
    args = parser.parse_args()
    print(f'{run_probe(args.recovery)} original CODE 9:03c8 copy-record cases agree')
