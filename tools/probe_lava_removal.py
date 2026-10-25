"""Check native lava's removal marker and the UpdateOppInfo removal branch."""

import argparse
from itertools import product
import json
from pathlib import Path

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class LavaRemoval(NativeRules):
    RANGES = {8: ((0x353a, 0x354c),), 6: ((0x30b0, 0x30d8), (0x32d8, 0x32e0))}
    SUPPLIED = {}


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    program = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    levels = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL']
    machine = LavaRemoval(program)
    cases = 0
    for number, room, facing in product((3, 4, 5), range(1, 33), (0, -1)):
        machine.reset(levels[1999 + number]['data'])
        for offset, value in ((-0x5040, room), (-0x5054, facing), (-0x504e, 4),
                              (-0x5022, 0), (-0x502e, 115), (-0x5056, 0)):
            machine.put_word(offset, value)
        # Enter after the lava pool/cue/JumpSeq setup, execute its actual
        # common marker writes, and stop before velocity/damage handling.
        machine.call(8, 0x353a, stop=(8, 0x354c))
        if machine.word(-0x5022) != 5:
            raise AssertionError((number, room, facing, 'missing lava marker'))
        # A dead/hidden marker must reach removal, not record capture. Stop
        # on RemoveOppInfo entry; no actor-bank removal service is supplied.
        machine.call(6, 0x30b0, stop=(6, 0x3462))
        if machine.services:
            raise AssertionError(machine.services)
        cases += 1
    return {'cases': cases, 'mismatches': 0, 'external_services': [],
            'scope': 'Actual lava common marker writes 8:353a-3548 and '
                     'UpdateOppInfo 6:30b0-30d4/32d8-32e0, stopping on '
                     'RemoveOppInfo 6:3462. Controlled actor type4/facing/room, '
                     'sequence115. Excludes lava contact/pool lookup, animation, '
                     'damage, bank removal execution and complete room transition.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
