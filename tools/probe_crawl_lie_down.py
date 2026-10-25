"""Run the original CheckBarr 4:4e34 / CheckCollide1 4:54da / Collide on the
Prince's lie-down frames (SEQS 125) beside level six's crevice in native
room 18, facing left, to show what the original does at frame 259.

Kid FRAM/AFRM 25001 and the actual SHAP sizes are installed; SectRect,
DrawOppMeter and AnimChar are supplied as in tools/probe_ruins_runtime.py.
"""

import argparse
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import supporting_column
from tools.probe_ruins_runtime import WORKING, NativeRuinsBarrier


class NativePrinceCollision(NativeRuinsBarrier):
    RANGES = {
        **NativeRuinsBarrier.RANGES,
        3: NativeRuinsBarrier.RANGES[3] + ((0x4e7c, 0x4ea2),),
        4: NativeRuinsBarrier.RANGES[4] + ((0x4e34, 0x5700), (0x5738, 0x5868), (0x5868, 0x589c),
                                          (0x589e, 0x5a6e), (0x5a70, 0x5ade), (0x3982, 0x39fa),
                                          (0x2c0c, 0x3050), (0x305e, 0x308a)),
        19: NativeRuinsBarrier.RANGES[19] + ((0x2f72, 0x3060),),
    }
    KID_FRAMES, KID_ATTACHMENTS = 0xb4000, 0xb8000

    def __init__(self, program, head, sequences, kid):
        super().__init__(program, head, sequences)
        self.cpu.mem_write(self.HANDLES + 16, struct.pack('>II', self.KID_FRAMES, self.KID_ATTACHMENTS))
        self.cpu.mem_write(self.KID_FRAMES, kid['FRAM'][25001]['data'])
        self.cpu.mem_write(self.KID_ATTACHMENTS, kid['AFRM'][25001]['data'])
        base = struct.unpack_from('>H', kid['SHPL'][25001]['data'])[0]
        self.sizes = {rid - base + 1: struct.unpack_from('>hH', item['data'], 4)
                      for rid, item in kid['SHAP'].items()}
        self.selected = []

    def reset(self, level):
        super().reset(level)
        self.cpu.mem_write(self.A5 - 0x3472, struct.pack('>I', self.HANDLES + 16))
        self.cpu.mem_write(self.A5 - 0x3476, struct.pack('>I', self.HANDLES + 20))

    def dispatch(self, cpu, address, size, user):
        if address == self.address(6, 0x0006):
            self.selected.append(self.argument(cpu))
        super().dispatch(cpu, address, size, user)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program, prince, head, kid = (parse_resource_fork((directory / name).read_bytes()) for name in
                                  ('Prince of Persia 2.bin', 'Prince.rsrc.bin', 'Head.rsrc.bin',
                                   'Kid.rsrc.bin'))
    level = prince['LEVL'][2005]['data']
    machine = NativePrinceCollision(program, head, prince['SEQS'], kid)
    frames = kid['FRAM'][25001]['data']
    room, row = 18, 1
    machine.reset(level)
    machine.cpu.mem_write(machine.A5 - 0x5056, bytes(62))
    machine.put_word(-0x4fc2, room)
    links = struct.unpack_from('>4H', level, 0x2080 + (room - 1) * 8)
    for offset, linked in zip((-0x4fc0, -0x4fbe, -0x4fba, -0x4fbc), links):
        machine.put_word(offset, linked)
    steps = []
    # GenCtrl 6:0af8-0b24 puts the Prince 34 past the crevice's right edge
    # (scene X 85); SEQS 125 then shows 109, 260 (X + 2) and 259 (X - 5).
    for scene_x, pose in ((85, 109), (87, 260), (82, 259)):
        column, _remainder = supporting_column(scene_x + 207, -1, frames[pose * 10:pose * 10 + 10])
        for name, value in dict(slot=0, facing=-1, x=scene_x + 207, y=row * 120 + 106, actor=0,
                                pose=pose, column=column, row=row, room=room, armed=0, alive=-1,
                                life=3, sequence=125, selected=125).items():
            machine.put_word(WORKING[name], value)
        machine.selected.clear()
        machine.call(4, 0x2a72)
        machine.call(3, 0x0ac8)
        machine.call(4, 0x5cbc)
        machine.call(4, 0x4e34)
        machine.call(4, 0x54da)
        steps.append(dict(pose=pose, left_edge=machine.word(-0x3564) - 207,
                          image_height=machine.word(-0x3560), x_after=machine.word(WORKING['x']) - 207,
                          selected=machine.selected[:]))
    return dict(steps=steps, scope='Native collision on the left-facing lie-down at level six '
                                  'native room 18, row 1, crevice column 0.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    for step in run_probe(args.source)['steps']:
        print(step)


if __name__ == '__main__':
    main()
