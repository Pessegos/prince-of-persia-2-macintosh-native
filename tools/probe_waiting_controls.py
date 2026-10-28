"""Compare production directional-bank/ready routing directly with original code."""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path

from pop2.mac_input import DirectionalInput, standing_input_request
from pop2.mac_resources import parse_resource_fork
from tools.probe_input_bank import FIELDS, NativeInputBank
from tools.probe_input_routes import NativeInputRoutes
from tools.probe_level7_rules import NativeRules


class NativeUpChoice(NativeInputRoutes):
    RANGES = {**NativeInputRoutes.RANGES,
              6: NativeInputRoutes.RANGES[6] + ((0x0e36, 0x0e8c), (0x1600, 0x1610))}
    SUPPLIED = {key: value for key, value in NativeInputRoutes.SUPPLIED.items() if key != (6, 0x0e36)}
    SUPPLIED.update({(4, 0x35a6): 'nonexit_cell', (4, 0x3a48): 'nonexit_cell',
                     (4, 0x39fc): 'nonexit_cell', (6, 0x1600): 'vertical_up'})

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        if self.SUPPLIED.get((segment, offset)) == 'nonexit_cell' and address != self.stop_at:
            NativeRules.dispatch(self, cpu, address, size, user)
            cpu.reg_write(self.registers['d0'], 1)
            return
        super().dispatch(cpu, address, size, user)


class NativeUpPrefix(NativeUpChoice):
    SUPPLIED = {key: value for key, value in NativeUpChoice.SUPPLIED.items() if key != (6, 0x1600)}


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    raw = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(raw)
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2004]['data']
    sampler, router = NativeInputBank(program), NativeInputRoutes(program)
    up_choice, up_prefix = NativeUpChoice(program), NativeUpPrefix(program)
    banks = [DirectionalInput(*directions, modifier)
             for directions in product((-1, 0, 1), repeat=4) for modifier in (-2, -1, 0, 1, 2)]
    counts, digest = {}, hashlib.sha256()

    def check(label, actual, expected):
        if actual != expected:
            raise AssertionError((label, actual, expected))
        counts[label] = counts.get(label, 0) + 1
        digest.update(repr((label, actual)).encode())

    def put(bank):
        for field, value in zip(FIELDS, bank.words()):
            sampler.put_word(field, value)

    def read():
        return tuple(sampler.word(field) for field in FIELDS)

    for bank in banks:
        sampler.reset(level)
        for axes in product((-1, 0, 1), (-1, 0, 1), (-2, -1, 0)):
            put(bank)
            for field, value in zip((-0x3498, -0x3496, -0x3494), axes):
                sampler.put_word(field, value)
            sampler.call(4, 0x3e84)
            check('production-sample', read(), bank.sample(*axes).words())
        put(bank)
        sampler.call(4, 0x3e3a)
        check('production-clear', read(), bank.clear_directions().words())
        for facing, inverted in product((False, True), repeat=2):
            put(bank)
            if facing:
                sampler.call(4, 0x3dfe)
            if inverted:
                sampler.call(4, 0x3e1c)
            check('production-remap', read(), bank.remap(facing_right=facing, inverted=inverted).words())

    events = {'turn': (('turn',),), 'run': (('run',),), 'step': (('step', 0),),
              'up': (('up',),), 'down': (('down',),), 'forward_jump': (('forward_jump',),),
              'turn_run': (('sequence', 43),), 'draw': (('draw',), ('target',)), None: ()}
    for bank, pose, mode, sequence, sword in product(
            banks, (15, *range(45, 53)), (0, 5), (2, 27), (False, True)):
        router.fixture(level, bank, pose, mode=mode, sequence=sequence, sword=0 if sword else -1)
        router.call(6, 0x0560)
        expected, request = standing_input_request(bank, pose, mode=mode, sequence=sequence, sword=sword)
        check('production-ready', (router.bank().words(), tuple(router.events)),
              (expected.words(), events[request]))
    for bank in banks:
        up_choice.fixture(level, bank, 15)
        up_choice.call(6, 0x0e36)
        check('up-choice', (up_choice.bank().words(), tuple(up_choice.events)),
              (bank.words(), (('forward_jump',),) if bank.left else (('vertical_up',),)))
        up_prefix.fixture(level, bank, 15)
        up_prefix.call(6, 0x1600, stop=(4, 0x3ff8))
        check('vertical-up-prefix', up_prefix.bank().words(), bank.consume('up', clear=True).words())
    return dict(cases=counts, total=sum(counts.values()), mismatches=0,
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                actual=['Production sampling/clear/remap and standing/turn request selection vs original instructions',
                        'Original Up forward/vertical choice and DoJumpUp consumption prefix before geometry'],
                supplied=['Raw keyboard axes, live type0 Prince level5 context, pose/mode/sequence/sword state',
                          'Geometry/pickup/target and action bodies are supplied sinks, as in probe_input_routes',
                          'Up choice supplies no exit cells; vertical prefix stops before 4:3ff8 terrain lookup'],
                exclusions='Not whole scene/animation/FrameAdv parity; host repeat/chord policies and family handoff are scene regressions, not native proof')


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
