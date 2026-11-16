"""Compare level 14's defeat and the room-11 laugh with the original CODE.

Two original pieces run in Unicorn over LEVL 2013 (environment 6, level 14):

- GenCtrl 6:0780-07a2 with 9:0062, for a dead type-0 Kid: every ALIVE
  count 0-12, native room 1-14 and rebirth bank (a5-0x5018 zero or not),
  against `final_magic.defeat_moves` and the defeat constants. Supplied,
  recording their arguments: SetSeq 6:0006 and AnimChar 4:2c0c. The type-1
  shadow's branch (6:07a2 -> 4:2338) is outside this probe; so is a level
  other than 14 (the header is the preserved one).
- InitOpps 6:2d64-2d9e, the fresh-record sequence, for actor types 0-9 but
  10 (handled before 6:2d64) and SEQS 0-255, against
  `opponent_records.fresh_sequence`. Supplied: AddSound 5:4d84 (recorded).
  The routine's caller and the record's other fields are excluded.
"""

import argparse
from itertools import product
from pathlib import Path
import struct

from pop2.coordinates import TILE_WIDTH
from pop2.final_magic import (
    COLLAPSE_SEQUENCE, DEFEAT_COLUMN, DEFEAT_FRAMES, DEFEAT_ROOM, DEFEAT_ROW, defeat_moves)
from pop2.mac_resources import parse_resource_fork
from pop2.opponent_records import fresh_sequence
from tools.probe_level7_rules import NativeRules

CHAR = -0x5056
X, Y, TYPE, COLUMN, ROW, ROOM, ALIVE = (CHAR + 4, CHAR + 6, CHAR + 8, CHAR + 0xc, CHAR + 0xe,
                                        CHAR + 0x16, CHAR + 0x1c)
VIEW_ROOM, REBIRTH = -0x4fc4, -0x5018
RECORD = 0xc0000
NATIVE_ORIGIN = 207


class NativeDefeat(NativeRules):
    RANGES = {
        **NativeRules.RANGES,
        6: ((0x0780, 0x07a2), (0x2d64, 0x2da0)),
        9: ((0x0062, 0x00c6),),
    }
    SUPPLIED = {(6, 0x0006): 'select', (4, 0x2c0c): 'animate', (5, 0x4d84): 'sound'}
    ARGUMENTS = {'select': 1, 'sound': 1}

    def reset(self, level):
        super().reset(level)
        self.calls = []

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        service = self.SUPPLIED.get((segment, offset))
        if service is not None:
            count = self.ARGUMENTS.get(service, 0)
            stack = cpu.reg_read(self.registers['a7'])
            self.calls.append((service, *struct.unpack(f'>{count}h', cpu.mem_read(stack + 4, 2 * count))))
        super().dispatch(cpu, address, size, user)


def probe_defeat(machine, level):
    compared = moved = 0
    for alive, room, rebirth in product(range(13), range(1, 15), (False, True)):
        machine.reset(level)
        for offset, value in ((TYPE, 0), (ALIVE, alive), (ROOM, room), (VIEW_ROOM, room),
                              (X, 300), (Y, 200), (COLUMN, 3), (ROW, 0)):
            machine.put_word(offset, value)
        machine.cpu.mem_write(machine.A5 + REBIRTH, struct.pack('>I', 0x9000 if rebirth else 0))
        machine.call(6, 0x0780, stop=(6, 0x07da))
        wanted = defeat_moves(alive, rebirth, room - 1)
        if wanted:
            expected = ([('select', COLLAPSE_SEQUENCE)] + [('animate',)] * DEFEAT_FRAMES,
                        DEFEAT_ROOM + 1, DEFEAT_ROOM + 1, DEFEAT_COLUMN, DEFEAT_ROW,
                        DEFEAT_COLUMN * TILE_WIDTH + NATIVE_ORIGIN, DEFEAT_ROW * 120 + 112)
            moved += 1
        else:
            expected = ([], room, room, 3, 0, 300, 200)
        actual = (machine.calls, machine.word(VIEW_ROOM), machine.word(ROOM),
                  machine.word(COLUMN), machine.word(ROW), machine.word(X), machine.word(Y))
        if actual != expected:
            raise AssertionError(('6:0780/9:0062', alive, room, rebirth, actual, expected))
        compared += 1
    return compared, moved


def probe_fresh_sequence(machine, level):
    from unicorn.m68k_const import UC_M68K_REG_A3

    compared = laughs = 0
    for actor_type, sequence in product((0, 1, 2, 3, 4, 5, 6, 7, 8, 9), range(256)):
        machine.reset(level)
        machine.put_word(-0x504e, actor_type)
        machine.cpu.mem_write(RECORD, bytes(0x20))
        machine.cpu.mem_write(RECORD + 8, struct.pack('>H', sequence))
        machine.cpu.reg_write(UC_M68K_REG_A3, RECORD)
        machine.call(6, 0x2d64, stop=(6, 0x2da0))
        native = (struct.unpack('>h', machine.cpu.mem_read(RECORD + 8, 2))[0],
                  [call[1] for call in machine.calls if call[0] == 'sound'])
        port_sequence, sound = fresh_sequence(actor_type, sequence)
        wanted = (port_sequence, [] if sound is None else [sound])
        if native != wanted:
            raise AssertionError(('6:2d64', actor_type, sequence, native, wanted))
        laughs += bool(wanted[1])
        compared += 1
    return compared, laughs


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2013]['data']
    if struct.unpack_from('>HHH', level, 0x2186) != (6, 5, 14):
        raise ValueError('Unexpected preserved final-level header')
    machine = NativeDefeat(executable)
    defeat, moved = probe_defeat(machine, level)
    fresh, laughs = probe_fresh_sequence(machine, level)
    return {'6:0780/9:0062': defeat, 'moved': moved, '6:2d64': fresh, 'laughs': laughs}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', default='../PoP2-Mac-Code-Recovery')
    args = parser.parse_args()
    print(f'Original level-14 defeat and fresh records agree: {run_probe(args.recovery)}')
