"""Trace the level-12 birdhead's fall and impact pressure in the Macintosh CODE."""

import argparse
from pathlib import Path
import struct

from pop2.coordinates import native_x, scene_x
from pop2.mac_resources import parse_resource_fork
from tools.probe_room26_gate import NativeRoom26
from tools.probe_ruins_runtime import WORKING


class NativeRoom18(NativeRoom26):
    RANGES = dict(NativeRoom26.RANGES)
    RANGES[4] += ((0x3196, 0x322a), (0x35ba, 0x3686), (0x3982, 0x3a70),
                  (0x3a92, 0x3ac8), (0x3f44, 0x40a0), (0x4b16, 0x4e32), (0x5e6e, 0x5eac))
    RANGES[5] += ((0x1202, 0x127c),)
    RANGES[6] += ((0x00a6, 0x049e), (0x472a, 0x4864))
    SUPPLIED = NativeRoom26.SUPPLIED | {
        (4, 0x37ca): 'no catch', (5, 0x5252): 'stop cue', (10, 0x2036): 'no sliding rock',
    }

    def dispatch(self, cpu, address, size, user):
        if address in (self.address(4, 0x37ca), self.address(5, 0x5252), self.address(10, 0x2036)):
            self.skip(cpu, 0)
            return
        super().dispatch(cpu, address, size, user)

    def trace(self, level, x, *, early_cut=False):
        self.reset(level)
        self.put_word(-0x4fc2, 20)
        self.put_word(-0x4fc4, 20)
        self.call(3, 0x1ab0, stop=(3, 0x1c3c))
        self.cpu.mem_write(self.A5 - 0x5056, bytes(62))
        for key, value in dict(x=native_x(x), y=226, pose=170, facing=-1, life=2, alive=-1,
                               actor=2, room=20, row=1, armed=1,
                               sequence=227, selected=65, cursor=1).items():
            self.put_word(WORKING[key], value)
        self.put_word(-0x5046, 1)
        self.put_word(-0x5092, 0)
        self.put_word(-0x508c, 0)
        self.put_word(-0x50d0, 0)
        self.call(4, 0x2a72)
        self.call(6, 0x51f2)
        assert self.word(WORKING['pose']) == 172 and self.word(-0x5034) == -1
        for _ in range(24):
            for routine in (0x2c0c, 0x341a, 0x3464, 0x2a72):
                self.call(4, routine)
            self.call(5, 0x1202)
            if early_cut and self.word(WORKING['room']) == 20 and self.word(WORKING['row']) == 3:
                # Counterfactual: apply the original 365-pixel Cut during flight.
                self.put_word(WORKING['room'], self.call(6, 0x472a))
            if self.word(WORKING['pose']) == 185:
                break
        else:
            raise AssertionError('No landing in 24 frames')
        cached_column = self.word(WORKING['column'])
        self.call(5, 0x127e)
        state = self.level_bytes(len(level))
        source = struct.unpack_from('>H', state, 0x780 + 17 * 120 + 27 * 4)[0]
        timer = struct.unpack_from('>h', state, 0x1680 + 179 * 10 + 4)[0]
        if early_cut:
            room = self.word(WORKING['room'])
        else:
            room = self.call(6, 0x472a)
        self.call(4, 0x2a72)
        return (room, self.word(WORKING['row']), scene_x(self.word(WORKING['x'])),
                cached_column, self.word(WORKING['column']), source, timer)


def run_probe(source):
    forks = source / 'resource_forks'
    program, prince, birdhead = (parse_resource_fork((forks / name).read_bytes()) for name in
                                ('Prince of Persia 2.bin', 'Prince.rsrc.bin', 'Birdhead.rsrc.bin'))
    level = prince['LEVL'][2011]['data']
    assert tuple(struct.unpack_from('>h', level, offset)[0] for offset in
                 (0x2186, 0x218a, 0x21a4)) == (2, 12, 7)
    machine = NativeRoom18(program, birdhead, prince['SEQS'])
    for x in (345, 348, 349):
        assert machine.trace(level, x) == (18, 2, 400, 7, 6, 0x20b3, 5)
        assert machine.trace(level, x, early_cut=True) == (18, 1, 448, 8, 7, 0xb3, 0)
    assert machine.trace(level, 350) == (18, 1, 448, 8, 7, 0xb3, 0)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    run_probe(parser.parse_args().source)
    print('Four native landings and three midair-cut controls passed.')
