"""Execute final InitOpps typing/sequence and LoadFrame bank selection.

CheckLoadedOppSet, palette loading, Rnd and the room-11 sound are supplied endpoints.
FRAM/AFRM handles are supplied from preserved Kid/Guard resources. AnimChar,
Resource Manager loading, AI, combat and the full room-entry cycle are excluded.
"""

import argparse
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class NativeCloneFrames(NativeRules):
    RANGES = {6: ((0x2bca, 0x2c1c), (0x2d64, 0x2da0), (0x3972, 0x39f6)),
              4: ((0x2a8e, 0x2bac),)}
    SUPPLIED = {(3, 0x5278): 'check_loaded_opp_set', (5, 0x4d84): 'sound',
                (3, 0x508a): 'palette', (17, 0x6e06): 'rnd'}

    def dispatch(self, cpu, address, size, user):
        if address == self.address(3, 0x508a):
            stack = cpu.reg_read(self.registers['a7'])
            self.palettes.append(struct.unpack('>2h', cpu.mem_read(stack + 4, 4)))
        super().dispatch(cpu, address, size, user)


def run_probe(recovery):
    from unicorn.m68k_const import UC_M68K_REG_A3

    directory = Path(recovery) / 'resource_forks'
    program = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2013]['data']
    kid = parse_resource_fork((directory / 'Kid.rsrc.bin').read_bytes())
    guard = parse_resource_fork((directory / 'Guard.rsrc.bin').read_bytes())
    if (len(level), struct.unpack_from('>h', level, 0x2186)[0],
            struct.unpack_from('>h', level, 0x21a4)[0]) != (18890, 6, 0):
        raise ValueError('Unexpected final LEVL header')
    machine = NativeCloneFrames(program)
    checked = 0
    for room, count, actor_type, sequence, pose in ((6, 4, 6, 2, 15),
                                                   (10, 1, 2, 77, 166),
                                                   (11, 1, 6, 197, 297)):
        offset = 0x20e6 + room * 0xc0
        if struct.unpack_from('>h', level, offset)[0] != count:
            raise ValueError('Unexpected final opponent bank count')
        for slot in range(count):
            machine.reset(level)
            machine.palettes = []
            record = machine.LEVEL + offset + 2 + slot * 38
            machine.cpu.reg_write(UC_M68K_REG_A3, record)
            machine.put_word(-0x4fc2, room)
            machine.call(6, 0x2bca, stop=(6, 0x2c1c))
            if machine.word(-0x504e) != actor_type:
                raise AssertionError((room, slot, 'actor', machine.word(-0x504e)))
            machine.call(6, 0x2d64, stop=(6, 0x2da0))
            selected = struct.unpack('>h', machine.cpu.mem_read(record + 8, 2))[0]
            if selected != sequence:
                raise AssertionError((room, slot, 'sequence', selected))
            data_address = 0xb1000
            for index, (global_offset, resource, kind, resource_id) in enumerate((
                    (-0x3472, kid, 'FRAM', 25001), (-0x3476, kid, 'AFRM', 25001),
                    (-0x347a, guard, 'FRAM', 750), (-0x347e, guard, 'AFRM', 750))):
                handle = 0xb0000 + index * 4
                data = resource[kind][resource_id]['data']
                machine.cpu.mem_write(machine.A5 + global_offset, struct.pack('>I', handle))
                machine.cpu.mem_write(handle, struct.pack('>I', data_address))
                machine.cpu.mem_write(data_address, data)
                data_address += len(data) + 16
            machine.put_word(-0x504c, pose)
            machine.call(4, 0x2a8e)
            source, resource_id, index = ((kid, 25001, pose) if actor_type == 6
                                         else (guard, 750, pose - 149))
            frame = source['FRAM'][resource_id]['data'][index * 10:(index + 1) * 10]
            attachment = struct.unpack_from('>h', frame, 2)[0]
            aframe = source['AFRM'][resource_id]['data'][attachment * 8:(attachment + 1) * 8]
            if (bytes(machine.cpu.mem_read(machine.A5 - 0x5212, 10)) != frame
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x521a, 8)) != aframe):
                raise AssertionError((room, slot, 'frame bank'))
            if actor_type == 6:
                machine.call(6, 0x3972)
                if machine.palettes[-1] != (25008, 32):
                    raise AssertionError(('copy palette', machine.palettes))
            checked += 1
    return checked


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', default='../PoP2-Mac-Code-Recovery')
    args = parser.parse_args()
    print(f'{run_probe(args.recovery)} original final actor/sequence/frame-bank cases agree')
