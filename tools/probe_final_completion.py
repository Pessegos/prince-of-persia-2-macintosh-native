"""Probe CODE 2's final NIS/Hall-of-Fame handoff after level fourteen.

PlayNIS and HallOfFameDialog are supplied endpoints. This checks their call
order/arguments and the caller's next-level/tree state, not either scene,
the score table, persistence, or the outer restart loop.
"""

import argparse
from itertools import product
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class NativeCompletion(NativeRules):
    RANGES = {2: ((0x4596, 0x45de),)}
    SUPPLIED = {(2, 0x0298): 'play_nis', (2, 0x1f2c): 'hall_of_fame'}

    def dispatch(self, cpu, address, size, user):
        if address in (self.address(2, 0x0298), self.address(2, 0x1f2c)):
            stack = cpu.reg_read(self.registers['a7'])
            argument = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            name = 'nis' if address == self.address(2, 0x0298) else 'hall'
            self.events.append((name, argument))
            if name == 'hall' and self.supplied_next_level is not None:
                self.put_word(-0x4faa, self.supplied_next_level)
        super().dispatch(cpu, address, size, user)


def run_probe(recovery):
    from unicorn.m68k_const import UC_M68K_REG_D4

    directory = Path(recovery) / 'resource_forks'
    program = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2013]['data']
    if (len(level), struct.unpack_from('>h', level, 0x218a)[0]) != (18890, 14):
        raise ValueError('Unexpected preserved final LEVL')
    machine = NativeCompletion(program)
    checked = 0
    for next_level, minutes, dialog_next in product((15, 16), (0, 20, 60), (None, 1)):
        machine.reset(level)
        machine.events = []
        machine.supplied_next_level = dialog_next
        machine.put_word(-0x4fce, minutes)
        machine.put_word(-0x4faa, next_level)
        machine.put_word(-0x27d2, 9)
        machine.cpu.reg_write(UC_M68K_REG_D4, next_level)
        machine.call(2, 0x4596, stop=(2, 0x45f6))
        expected_events = [('nis', 11), ('hall', minutes)] if minutes else []
        expected_next = (dialog_next or 0) if minutes else 0
        actual_next = machine.cpu.reg_read(UC_M68K_REG_D4) & 65535
        if (machine.events != expected_events or actual_next != expected_next
                or machine.word(-0x4faa) != expected_next
                or machine.word(-0x27d2) != (-1 if minutes else 9)):
            raise AssertionError((next_level, minutes, dialog_next, machine.events,
                                  actual_next, machine.word(-0x4faa), machine.word(-0x27d2)))
        checked += 1
    return checked


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', default='../PoP2-Mac-Code-Recovery')
    args = parser.parse_args()
    print(f'{run_probe(args.recovery)} original final-completion handoff cases agree')
