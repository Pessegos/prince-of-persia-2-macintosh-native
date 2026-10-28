"""Compare the production grounded-run selector with original GenCtrl instructions."""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_input import DirectionalInput, running_input_request
from pop2.mac_resources import parse_resource_fork
from tools.probe_input_routes import NativeInputRoutes


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    raw = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(raw)
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2004]['data']
    assert struct.unpack_from('>H', level, 0x218a)[0] == 5
    machine = NativeInputRoutes(program)
    banks = [DirectionalInput(*axes, modifier) for axes in product((-1, 0, 1), repeat=4)
             for modifier in (-2, -1, 0, 1, 2)]
    events = {None: (), 'forward_jump': (('forward_jump',),), 'brake': (('sequence', 13),),
              'reverse': (('sequence', 6),), 'running_jump': (('run_jump', 4),),
              'running_crouch': (('sequence', 26),)}
    digest, counts = hashlib.sha256(), {}

    def check(label, bank, pose, mode=0, sequence=201):
        machine.fixture(level, bank, pose, mode=mode, sequence=sequence)
        machine.call(6, 0x0560)
        result, request = running_input_request(bank, pose, mode=mode, sequence=sequence)
        actual = machine.bank().words(), tuple(machine.events)
        if actual != (result.words(), events[request]):
            raise AssertionError((bank, pose, mode, sequence, actual, result, request))
        digest.update(repr((label, actual)).encode())
        counts[label] = counts.get(label, 0) + 1

    for bank, pose in product(banks, (*range(1, 15), *range(53, 66))):
        check('production-run-routing', bank, pose)
    for bank, (mode, sequence) in product(banks, ((4, 201), (5, 201), (9, 201), (0, 27), (0, 110))):
        check('protected-clear', bank, 8, mode, sequence)
    return dict(cases=counts, total=sum(counts.values()), mismatches=0,
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                actual='Original GenCtrl router, startup reset and common Forward consumption vs production selector',
                supplied=['Living type0 Prince in level5, relative input bank, pose/mode/sequence',
                          'Action/geometry endpoints are no-op sinks, pickup=false and target=-1, as in probe_input_routes'],
                exclusions='No animation/geometry/FrameAdv proof; accepted run-jump consumption uses earlier action-body evidence and scene regressions; host chord/repeat tolerances are deliberate exceptions')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
