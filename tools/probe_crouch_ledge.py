"""Execute native standing Down and the ensuing fall entry against real cells."""

import argparse
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_controller_geometry import MOB_BANK
from tools.probe_temple_frame_progression import NativeTempleFrameProgression
from tools.probe_temple_kid_frames import verify_frames


class NativeCrouchLedge(NativeTempleFrameProgression):
    RANGES = dict(NativeTempleFrameProgression.RANGES)
    RANGES[4] += ((0x35ba, 0x3686), (0x3982, 0x3a70), (0x3a92, 0x3ac8),
                  (0x3f44, 0x40a0), (0x4b16, 0x4e32), (0x5e6e, 0x5eac))
    RANGES[5] += ((0x1202, 0x127c),)
    RANGES[6] += ((0x0e8e, 0x0f56), (0x1068, 0x10e2))
    ENDPOINTS = {target: name for target, name in NativeTempleFrameProgression.ENDPOINTS.items()
                 if target != (5, 0x1202)}

    def start(self, level, room, row, x, facing):
        self.reset(level)
        self.cpu.mem_write(self.A5 - 0x5056, bytes(62))
        self.cpu.mem_write(self.A5 - 0x4496, struct.pack('>I', MOB_BANK))
        for offset, value in (
            (-0x5056, 10), (-0x5054, facing), (-0x5052, x + 207),
            (-0x5050, row * 120 + 106), (-0x504c, 15), (-0x5048, row),
            (-0x5040, room), (-0x502e, 2), (-0x5030, 2),
            (-0x4fc2, room), (-0x4490, 0), (-0x3482, -1),
        ):
            self.put_word(offset, value)
        self.call(4, 0x2a72)

    def pose(self):
        return (self.word(-0x502e), self.word(-0x504c), self.word(-0x5052) - 207,
                self.word(-0x5050), self.word(-0x5048))

    def tick(self):
        for operation in (0x2c0c, 0x341a, 0x3464, 0x2a72):
            self.call(4, operation)
        self.call(5, 0x1202)


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    program = parse_resource_fork((forks / 'Prince of Persia 2.bin').read_bytes())
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    kid = parse_resource_fork((forks / 'Kid.rsrc.bin').read_bytes())
    sequences = {n: prince['SEQS'][n]['data'] for n in (2, 7, 49, 50, 117, 214)}
    machine = NativeCrouchLedge(program, sequences, kid['FRAM'][25001]['data'],
                                kid['AFRM'][25001]['data'])
    cases = []
    for kind, number, room, row, facing, positions, fall_x in (
        (2, 11, 32, 1, 0, range(223, 229), 248),
        (3, 4, 3, 2, -1, range(225, 231), 205),
    ):
        level = prince['LEVL'][1999 + number]['data']
        if struct.unpack_from('>3H', level, 0x2186)[::2] != (kind, number):
            raise ValueError('Unexpected LEVL header')
        for x in positions:
            falls = x not in (223, 230)
            cases.append((level, room, row, facing, x, falls, fall_x))
    # The forward tile may stop this branch even at the same foot distance.
    blocked = bytearray(cases[0][0])
    struct.pack_into('>H', blocked, 31 * 60 + 2 * 14, 20)
    cases.append((blocked, 32, 1, 0, 224, False, 0))

    for level, room, row, facing, x, falls, fall_x in cases:
        direction = -1 if facing == -1 else 1
        y = row * 120 + 106
        machine.start(level, room, row, x, facing)
        machine.call(6, 0x0e8e)
        expected = (2, 15, x + direction * 15, y, row) if falls else (50, 15, x, y, row)
        if machine.pose() != expected or machine.word(-0x3482) != 1:
            raise AssertionError(('standing Down', room, x, machine.pose(), expected))
        machine.tick()
        expected = (7, 102, fall_x, y + 19, row + 1) if falls else (50, 107, x + direction * 3, y, row)
        if machine.pose() != expected or machine.services:
            raise AssertionError(('first frame', room, x, machine.pose(), expected, machine.services))
        verify_frames(machine)
        machine.verify_sequences()

    # Exactly five pixels from the edge, the Prince crouches. Supply the
    # normal accepted release action and run its entire rise into the fall.
    machine.start(prince['LEVL'][2010]['data'], 32, 1, 223, 0)
    machine.call(6, 0x0e8e)
    for _ in range(3):
        machine.tick()
    if machine.pose() != (50, 109, 239, 226, 1):
        raise AssertionError(('held crouch', machine.pose()))
    machine.call(6, 0x0006, (49,))
    for pose, x in enumerate((242, 244, 246, 251, 251, 254, 246), 110):
        machine.tick()
        if machine.pose() != (49, pose, x, 226, 1):
            raise AssertionError(('crouch rise', pose, machine.pose()))
    machine.tick()
    if machine.pose() != (7, 102, 249, 245, 2) or machine.services:
        raise AssertionError(('fall after rise', machine.pose(), machine.services))
    verify_frames(machine)
    machine.verify_sequences()
    return len(cases) + 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    print(f'{run_probe(args.source)} native standing Down cases matched')
