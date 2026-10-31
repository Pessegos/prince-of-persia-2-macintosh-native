"""Execute the original bridge engagement test 8:02ae against pop2.bridge.

8:02ae decides whether a character in level five's bridge rooms presses
forward: the bridge skeleton's EnGarde/GenFight/OpponentClose and its
SwordCtrl turn ask it for the skeleton, and the Prince's automatic sword turn
(SwordCtrl 6:22de) asks it for the Prince. The test runs with its helpers
BridgeGetCharCol 8:0188, 8:0424 and IsBrgGateOpen 8:0458; only the trob
lookup 5:38a6 is supplied (none, or a trob of the given phase).
"""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.bridge import bridge_engage
from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class NativeBridgeEngage(NativeRules):
    RANGES = {8: ((0x0188, 0x01cc), (0x02ae, 0x033a), (0x0424, 0x048e))}
    SUPPLIED = {(5, 0x38a6): 'trob'}
    TROB = 0xc0000

    def dispatch(self, cpu, address, size, user):
        if divmod(address - self.CODE_BASE, 0x10000) == (5, 0x38a6):
            stack = cpu.reg_read(self.registers['a7'])
            self.lookups.append(struct.unpack('>hh', cpu.mem_read(stack + 4, 4)))
            super().dispatch(cpu, address, size, user)
            cpu.reg_write(self.registers['d0'], 0 if self.phase is None else self.TROB)
            return
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    program = parse_resource_fork(raw)
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2004]['data']
    assert struct.unpack_from('>H', level, 0x218a)[0] == 5
    machine = NativeBridgeEngage(program)
    digest, count, engaged = hashlib.sha256(), 0, 0
    # Native rooms 7/10/12 continue one another's columns; 1 is a control.
    for (room, column, facing, dx, opponent_room, opponent_column, sword, phase, tension_level,
         tension) in product(
            (1, 7, 10, 12), range(-1, 11), (0, -1), (-205, -204, -203, -1, 0, 1),
            (7, 10, 12), (-1, 0, 1, 2, 5, 6, 7, 9), (0, 1, 2), (None, 0, 1, 2, 3),
            (1, 2, 3), (19, 20)):
        machine.reset(level)
        machine.lookups, machine.phase = [], phase
        machine.cpu.mem_write(machine.TROB, bytes(8))
        if phase is not None:
            machine.cpu.mem_write(machine.TROB + 4, struct.pack('>h', phase))
        x, opponent_x = 300 + dx, 300
        for field, value in ((-0x5040, room), (-0x504a, column), (-0x5054, facing),
                             (-0x5052, x), (-0x507e, opponent_room),
                             (-0x5088, opponent_column), (-0x5090, opponent_x),
                             (-0x507a, sword), (-0x36a2, tension_level), (-0x36a0, tension)):
            machine.put_word(field, value)
        actual = machine.call(8, 0x02ae) != 0
        if machine.lookups not in ([], [(7, 13)]):
            raise AssertionError(('trob lookup', machine.lookups))
        expected = bridge_engage(room - 1, column, facing == 0, x, opponent_room - 1,
                                 opponent_column, opponent_x, sword == 1,
                                 phase in (0, 2), tension_level, tension)
        if actual != expected:
            raise AssertionError((room, column, facing, dx, opponent_room, opponent_column, sword,
                                  phase, tension_level, tension, actual, expected))
        digest.update(b'1' if actual else b'0')
        count += 1
        engaged += actual
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(cases=count, engaged=engaged, mismatches=0, result_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['LEVL2004 header (level 5); the character and opponent-copy words'
                          ' (room, column, facing, X, sword word) and the tension words'
                          ' a5-0x36a2/-0x36a0',
                          'Trob lookup 5:38a6 (room 7, cell 13): none or phase 0-3'],
                exclusions=['Callers (EnGarde, GenFight, OpponentClose, SwordCtrl) and how'
                            ' they fill the character/opponent copies'])


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
