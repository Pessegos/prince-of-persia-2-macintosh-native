"""Bounded native loose-floor impact position and immediate shelf checks.

The impact slice starts after damage/trigger admission (6:0236-0260); actor
row/velocity are supplied and no arithmetic helper is replaced. The shelf
check runs 7:36a0 and actual MakeSpace/MOB allocation, supplying only redraw
and object drawing services. Full FrameAdv, pressure admission, damage,
subsequent debris motion and pixels are excluded.
"""

import argparse
import json
from pathlib import Path
import struct

from pop2.cavern_state import CavernState
from pop2.loose_floors import FallingFloor
from pop2.mac_resources import parse_resource_fork
from pop2.terrain import LevelMap, floor_y
from tools.probe_level7_rules import NativeRules


class Loose(NativeRules):
    RANGES = {**NativeRules.RANGES, 6: ((0x0236, 0x0260),),
              7: ((0x36a0, 0x373e),), 5: NativeRules.RANGES[5] + (
                  (0x2606, 0x2702), (0x2914, 0x293c))}
    SUPPLIED = {(5, 0x33fa): 'draw-object', (4, 0x1898): 'redraw-cell'}


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    program = parse_resource_fork((forks / 'Prince of Persia 2.bin').read_bytes())
    levels = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL']
    machine, positions = Loose(program), 0
    for row in range(3):
        for velocity in range(1, 64):
            machine.reset(levels[2005]['data'])
            machine.put_word(-0x5048, row)
            machine.put_word(-0x5042, velocity)
            machine.call(6, 0x0236, stop=(6, 0x0260))
            if (machine.word(-0x5042), machine.word(-0x5050)) != (
                    velocity // 2, floor_y(row) + 6):
                raise AssertionError((row, velocity))
            positions += 1
    level = levels[2006]['data']
    machine.reset(level)
    machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', 0xb4000))
    machine.put_word(-0x4490, 0)
    machine.put_word(-0x4fc2, 32)
    machine.call(4, 0x27ee, (32, 2, 2))
    machine.call(7, 0x36a0)
    terrain = LevelMap(level)
    terrain.caverns = CavernState()
    loose = terrain.caverns.loose
    loose.break_shelf(terrain, terrain.tile(31, 2, 2), 31)
    native_tile = struct.unpack_from('>H', machine.level_bytes(len(level)), 31 * 60 + 22 * 2)[0]
    mob = struct.unpack('>8h', machine.cpu.mem_read(0xb4000, 16))
    block = loose.falling[0]
    if native_tile != 0 or mob != (block.x, block.y, block.room + 1,
                                  block.velocity, 0, block.mob_type, block.row, 0):
        raise AssertionError((native_tile, mob, block))
    if block != FallingFloor(31, 2, 2, 365, 0, 3):
        raise AssertionError(block)
    return dict(impact_positions=positions, room32_shelves=1,
                supplied=dict(machine.services), scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_probe(args.source), indent=2))
