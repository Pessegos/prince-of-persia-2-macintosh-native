"""Trace level-13 music admission in the original executable with a supplied audio device."""

import argparse
import json
from itertools import product
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class NativeTempleAmbient(NativeRules):
    RANGES = {
        4: ((0x29d8, 0x2a62), (0x322a, 0x3262), (0x47a0, 0x48e8), (0x4b02, 0x4b14)),
        5: ((0x4d58, 0x4d76), (0x4df8, 0x4dfe), (0x4e0c, 0x4e42), (0x4e76, 0x4e9a),
            (0x4f92, 0x5110), (0x5122, 0x51f2), (0x530a, 0x5378), (0x5388, 0x573a)),
        6: ((0x2392, 0x24ac), (0x3d28, 0x3df4), (0x3fc8, 0x405a)),
        10: ((0x27a6, 0x27b8),),
    }
    SUPPLIED = {}
    RECORD = -0x3738

    def reset(self, level):
        super().reset(level)
        self.playing, self.requests = None, []
        for table in (-0x40fe, -0x40e2):
            pointer = self.A5 + table + 2 * 4
            offset, = struct.unpack('>i', self.cpu.mem_read(pointer, 4))
            self.cpu.mem_write(pointer, struct.pack('>I', self.A5 + offset))
        self.put_word(-0x439e, -1)
        self.put_word(-0x439c, -1)
        self.put_word(-0x4398, 0)
        self.put_word(-0x524a, 0)

    def dispatch(self, cpu, address, size, user):
        key = divmod(address - self.CODE_BASE, 0x10000)
        if key not in ((5, 0x52c8), (5, 0x5292), (16, 0x201e), (17, 0x6e06)):
            return super().dispatch(cpu, address, size, user)
        stack = cpu.reg_read(self.registers['a7'])
        arg, resource = struct.unpack('>2h', cpu.mem_read(stack + 4, 4))
        if key == (5, 0x52c8):
            cpu.reg_write(self.registers['d0'], int(arg == self.playing))
        elif key == (17, 0x6e06):
            cpu.reg_write(self.registers['d0'], 0)  # First member of the inclusive range.
        else:
            self.playing = arg if key == (5, 0x5292) else resource - 0x2618
            self.requests.append(self.playing)
        cpu.reg_write(self.registers['a7'], stack + 4)
        cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])

    def setup(self, level, room, *, actor=0, hp=3, row=1, column=9, alert=0,
              pending=False, guard_row=1, alive=-1, points=True):
        self.reset(level)
        self.cpu.mem_write(self.A5 - 0x5208, bytes(5 * 62))
        for address, value in ((-0x4fc2, room), (-0x50bc, room), (-0x50b6, -1),
                               (-0x50ca, actor), (-0x50b4, hp), (-0x50c8, 15),
                               (-0x50c4, row), (-0x50c6, column), (-0x5200, 2),
                               (-0x51fa, guard_row), (-0x51f0, int(pending)),
                               (-0x51ec, alive), (-0x51d6, alert)):
            self.put_word(address, value)
        self.cpu.mem_write(self.LEVEL + 0x20e6 + room * 0xc0, b'\x00\x01')
        if not points:
            self.cpu.mem_write(self.LEVEL + 0x3986 + room * 0x44, b'\x00\x00')

    def ambient(self, cue, group, *, busy=True):
        self.playing = cue if busy else None
        self.cpu.mem_write(self.A5 + self.RECORD, struct.pack('>3h', 1, group, cue))
        self.call(5, 0x4f92, arg_bytes=struct.pack('>I', self.A5 + self.RECORD))
        return struct.unpack('>2h', self.cpu.mem_read(self.A5 + self.RECORD + 2, 4))


def run_probe(source):
    directory = source / 'resource_forks'
    executable = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2012]['data']
    assert struct.unpack_from('>3h', level, 0x2186)[::2] == (2, 13)
    machine = NativeTempleAmbient(executable)
    fixtures = 0
    for room, busy, alert, guard_row, alive, pending, points in product(
            (2, 32), (False, True), (0, 1), (0, 1), (-1, 5, 6, 7), (False, True), (False, True)):
        machine.setup(level, room, alert=alert, pending=pending, guard_row=guard_row,
                      alive=alive, points=points)
        fighting = alive < 0 and alert > 0
        hold = points or (guard_row == 1 and pending and alive < 7)
        wants_combat = fighting and not busy
        if busy and (fighting or hold):
            expected = (2, 234)
        else:
            expected = (2, 232) if wants_combat else (1, 216)
        actual = machine.ambient(234, 2, busy=busy)
        assert actual == expected, (room, busy, alert, guard_row, alive, pending, points, actual, expected)
        fixtures += 1

    for room, actor, hp in product((2, 4, 29), (0, 1), (2, 3)):
        machine.setup(level, room, actor=actor, hp=hp)
        # A playing exploration song survives the room cut; then select from
        # the new room and avoid repeating cue 216 if still in group 1.
        assert machine.ambient(216, 1) == (1, 216)
        if room == 2:
            expected = (1, 217)
        else:
            expected = (-1, 252 if (room, actor, hp) == (4, 1, 3) else 253)
        assert machine.ambient(216, 1, busy=False) == expected
        fixtures += 1

    machine.setup(level, 2, alert=1)
    assert machine.ambient(189, -1) == (-1, 189)
    machine.call(10, 0x27a6)
    machine.call(5, 0x5122)
    assert machine.requests == [292] and machine.word(machine.RECORD + 2) == -1
    assert machine.ambient(292, -1) == (-1, 292)
    assert machine.ambient(292, -1, busy=False) == (2, 232)
    return dict(fixtures=fixtures, inscription_entry=machine.requests[0],
                supplied=['Sound status and playback (5:52c8/5292, 16:201e)', 'Rnd=0 (17:6e06)',
                          'LEVL 2012, saved Prince and supplied ordinary guard bank/status'],
                excluded=['Mac Sound Manager timing', 'full FrameAdv and guard movement'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    print(json.dumps(run_probe(parser.parse_args().source), indent=2))
