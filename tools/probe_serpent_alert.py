"""Compare the original serpent alert LOS slice with the runtime.

Runs CODE2:6f0c-7100, after actor loading/pose admission and before the
next actor reload. Working/cached actor fields and a valid A6 local frame
are supplied; no LOS, tile or classification helper is stubbed. FrameAdv,
pose admission, controller scheduling and actor/resource loading are excluded.
Only rooms within the original LEVL room-count header are sampled.
"""

import argparse
import json
from pathlib import Path
import random
import struct
from types import SimpleNamespace

from unicorn.m68k_const import UC_M68K_REG_A6

from pop2.mac_resources import parse_resource_fork
from pop2.ruins_ai import PrinceView, RuinsCreatures
from pop2.terrain import LevelMap
from tools.probe_level7_rules import NativeRules


class NativeAlert(NativeRules):
    RANGES = {**NativeRules.RANGES, 2: ((0x6f0c, 0x7100),), 3: ((0x4da6, 0x4f24),)}
    SUPPLIED = {}


def run_probe(source, count=5000):
    forks = Path(source) / 'resource_forks'
    program = parse_resource_fork((forks / 'Prince of Persia 2.bin').read_bytes())
    levels = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL']
    machine, rng = NativeAlert(program), random.Random(3838)
    for _ in range(count):
        number = rng.choice((6, 7, 8, 9))
        level = levels[1999 + number]['data']
        room = rng.randrange(struct.unpack_from('>H', level, 0x2180)[0])
        row, column, prince_column = rng.randrange(3), rng.randrange(10), rng.randrange(10)
        mode, facing = rng.choice((1, 6)), rng.choice((0, -1))
        special, alive = rng.choice((0, 6, 9)), rng.choice((-1, -1, 0))
        prince_row = rng.choice((row, row, rng.randrange(3)))
        machine.reset(level)
        machine.cpu.reg_write(UC_M68K_REG_A6, 0xe0000)
        for offset, value in ((-0x4fc2, room + 1), (-0x504e, 11), (-0x5048, row),
                              (-0x504a, column), (-0x503a, -1), (-0x5054, 0),
                              (-0x5022, special), (-0x50bc, room + 1),
                              (-0x50b6, alive), (-0x50c4, prince_row),
                              (-0x50c6, prince_column), (-0x50c2, mode), (-0x50d0, facing)):
            machine.put_word(offset, value)
        machine.call(2, 0x6f0c, stop=(2, 0x7100))
        native = machine.word(-0x5024)
        creatures = RuinsCreatures()
        creatures.column = lambda actor, encounter: column
        actor = SimpleNamespace(state=SimpleNamespace(sequence_mode=special), row=row, room=room)
        prince = PrinceView(prince_column, prince_row, 400, 226, facing, 15,
                            room, alive, 3, False, 2, mode)
        actual = creatures.serpent_alert(actor, SimpleNamespace(terrain=LevelMap(level)), prince)
        if actual != native:
            raise AssertionError((number, room + 1, row, column, prince, special, native, actual))
    return dict(comparisons=count, mismatches=0, scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run_probe(args.source), indent=2))
