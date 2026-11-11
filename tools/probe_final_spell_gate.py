"""Bounded Macintosh CODE 9:0760 probe for the room-2 Jaffar spell gate.

The original CODE 9 executes in Unicorn. Restoring the saved Prince record
(CODE 4:4b02) and the full NIS/reset continuation (CODE 9:071a) are supplied
endpoints. The probe checks admission only, not the scene or resulting state.
"""

import argparse
from itertools import product
from pathlib import Path

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class NativeSpellGate(NativeRules):
    RANGES = {9: ((0x0760, 0x0874),)}
    SUPPLIED = {(4, 0x4b02): 'restore_saved_prince',
                (9, 0x071a): 'play_nis5_and_reset'}


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2013]['data']
    machine = NativeSpellGate(program)
    checked = 0
    for room, right, animation in product((1, 2, 3), (485, 486, 487), (0, 4, 5)):
        machine.reset(level)
        machine.put_word(-0x50bc, room)
        machine.put_word(-0x3566, right)
        machine.put_word(-0x50c2, animation)
        machine.put_word(-0x50ca, 0)  # Exclude the independent room-5 branch.
        machine.call(9, 0x0760)
        expected = int(room == 2 and right <= 486 and animation != 4)
        if (machine.services['restore_saved_prince'], machine.services['play_nis5_and_reset']) != (expected, expected):
            raise AssertionError((room, right, animation, machine.services, expected))
        checked += 1
    return checked


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', default='../PoP2-Mac-Code-Recovery')
    args = parser.parse_args()
    print(f'{run_probe(args.recovery)} original CODE 9 spell-gate cases agree')
