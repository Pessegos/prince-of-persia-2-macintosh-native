"""Execute original OnAlert with its armed action bodies: admission and consumption.

`tools/probe_armed_input.py` supplies the action bodies as sinks. Here
DoRetreat 6:1d6e, DoAdvance 6:1dda, DoStrike 6:2780, DoBlock 6:282a and
PutSwordAway 6:2592 run, with ClearControls 4:3e3a, so the resulting input
words and requested sequence are the original's. JumpSeq 6:0006 is a sink
recording the sequence; geometry/opponent services are supplied (below).
"""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_input_routes import NativeInputRoutes
from tools.reference_armed_input import armed_action
from tools.reference_input_bank import InputBank


class NativeArmedBodies(NativeInputRoutes):
    RANGES = {**NativeInputRoutes.RANGES,
              6: NativeInputRoutes.RANGES[6] + ((0x24bc, 0x2584), (0x1d6e, 0x1dca), (0x1dda, 0x1e68),
                                                (0x282a, 0x28ee), (0x2592, 0x25ec))}
    SUPPLIED = {**NativeInputRoutes.SUPPLIED,
                (7, 0x1266): 'special', (4, 0x2bae): 'recoil_x', (6, 0x2392): 'opponent',
                (6, 0x25ee): 'sheathe_tail', (4, 0x49ee): 'distance', (4, 0x2c0c): 'parry'}
    distance = 0
    opponent = 0

    def dispatch(self, cpu, address, size, user):
        name = self.SUPPLIED.get(divmod(address - self.CODE_BASE, 0x10000))
        super().dispatch(cpu, address, size, user)
        if address != self.stop_at and name in ('distance', 'opponent'):
            cpu.reg_write(self.registers['d0'], getattr(self, name) & 0xffff)
        if address != self.stop_at and name in ('special', 'recoil_x', 'sheathe_tail', 'parry'):
            self.events.append((name,))


POSES = (150, 151, 157, 158, 161, 165, 167, 168, 169, 170, 171)


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    program = parse_resource_fork(raw)
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2004]['data']
    assert struct.unpack_from('>H', level, 0x218a)[0] == 5
    machine = NativeArmedBodies(program)
    digest, count = hashlib.sha256(), 0
    banks = [InputBank(*axes, modifier) for axes in product((-1, 0, 1), repeat=4)
             for modifier in (-2, -1, 0, 1, 2)]
    # Opponent pose 0 (none in reach), 151/152/162 (strikes), 168; distance
    # below/above DoBlock's 74 and OppToFight with/without an opponent.
    for bank, pose, opponent_pose, distance, fight in product(
            banks, POSES, (0, 152, 153, 168), (40, 80), (0, 1)):
        machine.fixture(level, bank, pose, sword=1)
        machine.put_word(-0x508a, opponent_pose)
        machine.distance, machine.opponent = distance, fight
        machine.call(6, 0x24bc)
        actual = machine.bank(), tuple(dict.fromkeys(event for event in machine.events
                                                     if event[0] in ('sequence', 'parry')))
        expected = armed_action(bank, pose, opponent_pose=opponent_pose, distance=distance, fight=fight)
        if actual != expected:
            raise AssertionError((bank, pose, opponent_pose, distance, fight, actual, expected))
        digest.update(repr(actual).encode())
        count += 1
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(cases=count, mismatches=0, result_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['Living armed Prince (type 0, ALIVE), relative input words, pose,'
                          ' opponent pose a5-0x508a and LEVL2004 header',
                          'JumpSeq 6:0006 records the sequence; AddCharX 4:2bae, OppToFight'
                          ' 6:2392, distance 4:49ee and 4:2c0c are supplied; the sheathe'
                          ' tail 6:25ee (terrain/opponent sequence choice) is a sink'],
                exclusions=['No outer SwordCtrl/target/turn routing, keyboard sampling or timing',
                            'No animation, terrain or FrameAdv; actor types 1/7/8 excluded'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
