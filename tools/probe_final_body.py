"""Compare the shadow lying down on the body with the original CODE 4.

The original 4:1f1e (the shadow's Down near the body) and its distance
IsShadowBlinkOn 4:24b2 run in Unicorn over LEVL 2013, against
`Final.crouch_sequence` and `final_magic.body_distance` on a minimal scene.

Supplied: GetKidIdxAsOpp 4:2442 (slot 0), the record load 4:3286 and its
restore 4:3312 (the probe writes the body into the opponent record
a5-0x5094 itself) and AddCharX 4:2bae (X + n along the facing). Compared:
the return (SEQS 71 or none), the shadow's X and facing. Excluded: the
native Y - 1 (a port exception, see the ledger), the copy into the saved
Prince record and the cleared a5-0x503e.
"""

import argparse
from collections import Counter
from pathlib import Path
import random
import struct
from types import SimpleNamespace

from pop2.final_magic import Body, FinalMagic
from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules

CHAR, OPP = -0x5056, -0x5094
NATIVE_ORIGIN = 207


class NativeBody(NativeRules):
    RANGES = {
        **NativeRules.RANGES,
        4: (*NativeRules.RANGES[4], (0x1f1e, 0x1fb2), (0x24b2, 0x250a)),
    }
    SUPPLIED = {(4, 0x2442): 'slot', (4, 0x3286): 'load', (4, 0x3312): 'restore',
                (4, 0x2bae): 'add_x'}

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        service = self.SUPPLIED.get((segment, offset))
        step = None
        if service == 'add_x':
            stack = cpu.reg_read(self.registers['a7'])
            step = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
        super().dispatch(cpu, address, size, user)
        if step is not None:
            value = self.word(CHAR + 4) + (-step if self.word(CHAR + 2) else step)
            cpu.reg_write(self.registers['d0'], value & 65535)


def native_facing(port):
    return 0 if port else -1


def port_crouch(shadow, body, shadow_row, body_row):
    from pop2.environments import Final

    state = SimpleNamespace(**vars(shadow))
    magic = FinalMagic(shadow=True, body=Body(SimpleNamespace(**vars(body)), 3, body_row))
    scene = SimpleNamespace(
        room_id=3, game=SimpleNamespace(caverns=SimpleNamespace(final_magic=magic)),
        sequence_state=state, terrain_motion=SimpleNamespace(row=shadow_row),
        player_x=state.target_x, step_cautious=True)
    sequence = Final(scene).crouch_sequence()
    return sequence, state.target_x, state.facing


def run_probe(recovery, count=6000, seed=7):
    directory = Path(recovery) / 'resource_forks'
    executable = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2013]['data']
    if struct.unpack_from('>HHH', level, 0x2186) != (6, 5, 14):
        raise ValueError('Unexpected preserved final-level header')
    machine = NativeBody(executable)
    draw = random.Random(seed)
    outcomes = Counter()
    for _ in range(count):
        body_x = draw.randrange(20, 490)
        shadow = SimpleNamespace(target_x=body_x + draw.randrange(-70, 71),
                                 facing=draw.choice((0, 1)),
                                 action=draw.choice((15, 15, 109, 185, 2)))
        body = SimpleNamespace(target_x=body_x, facing=draw.choice((0, 1)), action=185)
        shadow_row = draw.randrange(3)
        body_row = shadow_row if draw.random() < 0.85 else draw.randrange(3)
        machine.reset(level)
        for base, actor, row in ((CHAR, shadow, shadow_row), (OPP, body, body_row)):
            for offset, value in ((2, native_facing(actor.facing)),
                                  (4, actor.target_x + NATIVE_ORIGIN), (0xa, actor.action),
                                  (0xe, row), (8, 1 if base == CHAR else 0)):
                machine.put_word(base + offset, value)
        returned = machine.call(4, 0x1f1e)
        native = ({71: 71, 65535: None}[returned], machine.word(CHAR + 4) - NATIVE_ORIGIN,
                  1 if machine.word(CHAR + 2) == 0 else 0)
        wanted = port_crouch(shadow, body, shadow_row, body_row)
        if native != wanted:
            raise AssertionError(('4:1f1e', vars(shadow), vars(body), shadow_row, body_row,
                                  native, wanted))
        outcomes['lie down' if native[0] else 'too far'] += 1
        outcomes['turned'] += native[0] is not None and shadow.facing != body.facing
    return count, dict(outcomes)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', default='../PoP2-Mac-Code-Recovery')
    parser.add_argument('--count', type=int, default=6000)
    args = parser.parse_args()
    print(f'Original lie-down cases agree: {run_probe(args.recovery, args.count)}')
