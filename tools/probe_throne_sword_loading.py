"""Bound the native distinction between logical and loaded throne swords.

Executes the post-vision initializer and physical pickup/LoadSwordSet with
supplied working actor, resource handles, file traps and cell-change service.
No PlayNIS, complete FrameAdv, resource-manager or raster equivalence claim.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class SwordLoading(NativeRules):
    RANGES = {3: ((0x5a4e, 0x5b18), (0x5b2a, 0x5b5e), (0x5e7e, 0x5eaa), (0x6408, 0x6448)),
              4: ((0x31fa, 0x3228),), 6: ((0x152c, 0x1554),), 7: ((0x391c, 0x395c),)}
    SUPPLIED = {}

    def service_return(self, value=0):
        stack = self.cpu.reg_read(self.registers['a7'])
        target = struct.unpack('>I', self.cpu.mem_read(stack, 4))[0]
        self.cpu.reg_write(self.registers['d0'], value)
        self.cpu.reg_write(self.registers['a7'], stack + 4)
        self.cpu.reg_write(self.registers['pc'], target)

    def dispatch(self, cpu, address, size, user):
        stack = cpu.reg_read(self.registers['a7'])
        if address == self.address(4, 0x4b02):
            self.events.append(('supplied working Prince',))
            self.service_return()
            return
        if address in (self.address(6, 0x0006), self.address(4, 0x406c)):
            value = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            self.events.append(('sequence' if address == self.address(6, 0x0006) else 'cell change', value))
            self.service_return()
            return
        if address == self.address(17, 0x330e):
            kind, resource = struct.unpack('>4sh', cpu.mem_read(stack + 4, 6))
            self.events.append(('resource', kind.decode('ascii'), resource))
            self.service_return(0xb0000)
            return
        if address == self.address(17, 0x65ac):
            resource = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            self.events.append(('shape list', resource))
            self.service_return(0xb0010)
            return
        if address == self.address(3, 0x508a):
            resource, base = struct.unpack('>2h', cpu.mem_read(stack + 4, 4))
            self.events.append(('palette', resource, base))
            self.service_return(1)
            return
        if self.address(3, 0x5a4e) <= address <= self.address(3, 0x5b5e):
            opcode = struct.unpack('>H', cpu.mem_read(address, 2))[0]
            if opcode in (0xa049, 0xa04a, 0xa994, 0xa998):
                if opcode == 0xa994:
                    cpu.mem_write(stack, struct.pack('>H', 77))
                elif opcode == 0xa998:
                    cpu.reg_write(self.registers['a7'], stack + 2)
                self.events.append(('resource trap', hex(opcode)))
                cpu.reg_write(self.registers['pc'], address + 2)
                return
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    level = prince['LEVL'][2007]['data']
    assert struct.unpack_from('>H', level, 0x218a)[0] == 8
    assert struct.unpack_from('>H', level, 8 * 60 + 25 * 2)[0] == 22
    machine = SwordLoading(parse_resource_fork(executable))
    traces = []
    for facing in (-1, 0):
        for life in (1, 6):
            machine.reset(level)
            machine.events = []
            machine.cpu.mem_write(machine.A5 - 0x3476, struct.pack('>I', 0xb0000))
            machine.cpu.mem_write(machine.A5 - 0x4a98, bytes(4))
            for offset, value in ((-0x500a, 2), (-0x46da, 2), (-0x504e, 0),
                                  (-0x5054, facing), (-0x5048, 2), (-0x5036, 6),
                                  (-0x5038, life), (-0x4fc2, 9)):
                machine.put_word(offset, value)
            machine.call(7, 0x391c, stop=(7, 0x395c))
            after_vision = [machine.word(offset) for offset in (-0x500a, -0x46da, -0x4ff4)]
            assert after_vision == [1, 2, 1], after_vision
            assert machine.level_bytes(len(level)) == level
            assert machine.events == [('supplied working Prince',), ('sequence', 231)]
            machine.put_word(-0x34ae, 1)  # Actual throne sword foreground &3.
            machine.call(6, 0x152c, stop=(6, 0x1554))
            after_pickup = [machine.word(offset) for offset in (-0x500a, -0x46da)]
            assert after_pickup == [1, 1], after_pickup
            for event in (('sequence', 91), ('cell change', -1), ('resource', 'AFRM', 25001),
                          ('shape list', 1000), ('palette', 1004, 240)):
                assert event in machine.events, (event, machine.events)
            traces.append(dict(facing=facing, life=life, after_vision=after_vision,
                               after_pickup=after_pickup, events=machine.events))
    return dict(traces=traces, mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(), scope=__doc__,
                supplied=['Working Prince at wake entry; logical and loaded sword2',
                          'JumpSeq and ChangeCell effects recorded; actual SEQS/cell effects excluded',
                          'Synthetic resource handles; GetCurResFile/UseResFile, ReleaseResource/HNoPurge',
                          'GetResource, LoadShapeList and PoPSetPalette recorded'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"{len(report['traces'])} native wake/pickup traces; zero mismatches")


if __name__ == '__main__':
    main()
