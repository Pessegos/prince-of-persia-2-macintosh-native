"""Trace the original level-11 room-26 fatal hit and closing plate."""

import argparse
from pathlib import Path
import struct

from pop2.coordinates import native_x, scene_x
from pop2.mac_resources import parse_resource_fork
from tools.probe_ruins_runtime import NativeRuinsAnimation, NativeRuinsHead, WORKING
from tools.probe_temple_mixed_plate_links import NativeMixedPlateLinks


class NativeRoom26(NativeRuinsAnimation):
    RANGES = NativeRuinsAnimation.RANGES | {
        3: NativeRuinsAnimation.RANGES[3] + ((0x1ab0, 0x1c3c), (0x4e7c, 0x4ea2)),
        4: NativeRuinsAnimation.RANGES[4] + NativeMixedPlateLinks.RANGES[4]
        + ((0x0154, 0x02cc), (0x3b30, 0x3b86), (0x3ff8, 0x400e)),
        5: NativeRuinsAnimation.RANGES[5] + NativeMixedPlateLinks.RANGES[5]
        + ((0x127e, 0x13dc), (0x252e, 0x2552)),
        6: NativeRuinsAnimation.RANGES[6] + ((0x04aa, 0x0560), (0x406e, 0x40da)),
    }
    SUPPLIED = {(5, 0x0f38): 'redraw'}

    def dispatch(self, cpu, address, size, user):
        if address == self.address(6, 0x04aa):
            # Execute corpse alignment, bypassing the ruins probe's stub.
            NativeRuinsHead.dispatch(self, cpu, address, size, user)
            return
        super().dispatch(cpu, address, size, user)

    def place(self, level, *, x, pose, facing, life, alive):
        self.reset(level)
        self.put_word(-0x4fc2, 26)
        self.call(3, 0x1ab0, stop=(3, 0x1c3c))
        self.cpu.mem_write(self.A5 - 0x5056, bytes(62))
        for field, value in dict(x=native_x(x), y=226, pose=pose, facing=facing, life=life,
                                 alive=alive, actor=2, room=26, row=1, armed=1,
                                 sequence=227, selected=65, cursor=1).items():
            self.put_word(WORKING[field], value)
        self.put_word(-0x5046, 1)
        self.put_word(-0x5092, ~facing)
        self.put_word(-0x508c, 0)
        self.put_word(-0x50d0, ~facing)
        self.call(4, 0x2a72)

    def hit_frames(self, level, *, x, facing, life):
        self.place(level, x=x, pose=158, facing=facing, life=life, alive=-1)
        self.call(6, 0x51f2)
        frames = [(scene_x(self.word(WORKING['x'])), self.word(WORKING['pose']))]
        if self.word(WORKING['selected']) == 85:
            self.put_word(WORKING['alive'], 0)
            for _ in range(5):
                for routine in (0x2c0c, 0x341a, 0x3464, 0x2a72):
                    self.call(4, routine)
                frames.append((scene_x(self.word(WORKING['x'])), self.word(WORKING['pose'])))
        return frames

    def press_close(self, level, pose, alive):
        self.place(level, x=465, pose=pose, facing=-1, life=0, alive=alive)
        self.put_word(-0x43e6, 1)
        self.cpu.mem_write(self.A5 - 0x448e, struct.pack('>4h', 19, 26, 2, 4))
        self.call(5, 0x127e)
        updated = self.level_bytes(len(level))
        source = struct.unpack_from('>H', updated, 0x780 + 25 * 120 + 18 * 4)[0]
        timer = struct.unpack_from('>h', updated, 0x1680 + 0x49 * 10 + 4)[0]
        return self.word(WORKING['column']), self.word(-0x448a), source, timer


def run_probe(source):
    directory = source / 'resource_forks'
    program, prince, birdhead = (parse_resource_fork((directory / name).read_bytes()) for name in
                                ('Prince of Persia 2.bin', 'Prince.rsrc.bin', 'Birdhead.rsrc.bin'))
    level = prince['LEVL'][2010]['data']
    assert tuple(struct.unpack_from('>h', level, offset)[0] for offset in
                 (0x2186, 0x218a, 0x21a4)) == (2, 11, 7)
    machine = NativeRoom26(program, birdhead, prince['SEQS'])
    expected = [(467, 179), (466, 180), (463, 181), (457, 182), (449, 183), (465, 185)]
    opened = bytearray(level)
    struct.pack_into('>H', opened, 0x780 + 25 * 120 + 19 * 4, 255)
    for fixture, x in ((level, 481), (level, 455), (opened, 481)):
        assert machine.hit_frames(fixture, x=x, facing=-1, life=1) == expected
    assert machine.hit_frames(level, x=481, facing=0, life=1)[0] == (454, 179)
    assert machine.hit_frames(level, x=481, facing=-1, life=2) == [(491, 172)]
    assert machine.hit_frames(level, x=365, facing=-1, life=1)[0] == (392, 179)

    for pose in (182, 185):
        for alive in (-1, 0, 1, 2, 5, 7):
            phase = 2 if pose == 185 and alive >= 2 else 4
            assert machine.press_close(level, pose, alive) == (8, phase, 0x2049, 5 if alive < 0 else 31)
    return expected


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    print('Native death frames:', run_probe(parser.parse_args().source))
    print('Six hit cases and twelve closing-plate cases passed.')
