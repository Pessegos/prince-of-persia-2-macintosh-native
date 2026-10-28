"""Execute original unarmed routing, sampled traces and attack modifier consumption."""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_input_bank import FIELDS
from tools.probe_level7_rules import NativeRules
from tools.reference_input_bank import InputBank
from tools.reference_input_routes import sampled_route, unarmed_route


class NativeInputRoutes(NativeRules):
    RANGES = {4: ((0x3d96, 0x3f42), (0x47a0, 0x48e8)),
              6: ((0x0560, 0x07e0), (0x0c32, 0x0e34), (0x1014, 0x1066),
                  (0x11e4, 0x1274), (0x15b6, 0x15e8), (0x2780, 0x281c))}
    SUPPLIED = {(4, 0x2174): 'cell', (6, 0x1350): 'pickup', (6, 0x36f2): 'target',
                (6, 0x1e78): 'draw', (6, 0x10e4): 'turn', (6, 0x0e36): 'up',
                (6, 0x0e8e): 'down', (6, 0x1276): 'step', (6, 0x15ea): 'forward_jump',
                (6, 0x11a0): 'run', (6, 0x0006): 'sequence', (6, 0x1c14): 'run_jump'}

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        name = self.SUPPLIED.get((segment, offset))
        if name and address != self.stop_at:
            stack = cpu.reg_read(self.registers['a7'])
            event = (name,)
            if name in ('sequence', 'step', 'run_jump'):
                event += (struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0],)
            if name not in ('cell', 'pickup'):
                self.events.append(event)
            super().dispatch(cpu, address, size, user)
            if name == 'target':
                cpu.reg_write(self.registers['d0'], 65535)
            return
        super().dispatch(cpu, address, size, user)

    def fixture(self, level, bank, pose, mode=0, sequence=201, sword=0):
        self.reset(level)
        self.events = []
        self.cpu.mem_write(self.A5 - 0x5056, bytes(62))
        for field, value in ((-0x5056, 10), (-0x5040, 1), (-0x5038, 3), (-0x503a, -1),
                             (-0x503c, sword), (-0x504c, pose), (-0x5046, mode),
                             (-0x502e, sequence), (-0x5062, 0), (-0x5020, 0)):
            self.put_word(field, value)
        self.put_bank(bank)

    def put_bank(self, bank):
        for field, value in zip(FIELDS, bank.words()):
            self.put_word(field, value)

    def bank(self):
        return InputBank(*(self.word(field) for field in FIELDS))


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    raw_program = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(raw_program)
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2004]['data']
    assert struct.unpack_from('>H', level, 0x218a)[0] == 5
    machine = NativeInputRoutes(program)
    digest = hashlib.sha256()
    count = 0
    banks = [InputBank(*directions, modifier) for directions in product((-1, 0, 1), repeat=4)
             for modifier in (-2, -1, 0, 1, 2)]
    poses = (*range(1, 16), 26, 27, 44, *range(45, 53), 67, 68, 69, 110)
    for pose, bank in product(poses, banks):
        machine.fixture(level, bank, pose)
        machine.call(6, 0x0560)
        actual = machine.bank(), tuple(machine.events)
        expected = unarmed_route(bank, pose)
        if actual != expected:
            raise AssertionError(('route', pose, bank, actual, expected))
        digest.update(repr(actual).encode())
        count += 1
    for mode, sequence, bank in product((4, 5, 9), (201, 27, 110), banks):
        machine.fixture(level, bank, 15, mode, sequence)
        machine.call(6, 0x0560)
        assert (machine.bank(), tuple(machine.events)) == unarmed_route(bank, 15, mode=mode, sequence=sequence)
        count += 1
    for pose, bank in product((15, 50, 51, 52), banks):
        machine.fixture(level, bank, pose, sword=-1)
        machine.call(6, 0x0560)
        assert (machine.bank(), tuple(machine.events)) == unarmed_route(bank, pose, sword=-1)
        count += 1

    traces = {}
    # Poses are supplied: this proves controller/latch composition, not physics.
    patterns = {
        'released_ctrl': [((1, 0, -2), 8), ((0, 0, 0), 11), ((0, 0, 0), 50), ((0, 0, 0), 15)],
        'held_ctrl': [((1, 0, -2), 8), ((0, 0, -2), 11), ((0, 0, -2), 50), ((0, 0, -2), 15)],
        'forward_ctrl': [((1, 0, -2), p) for p in (8, 9, 10, 11, 12, 13, 14)],
        'second_press': [((1, 0, -2), 8), ((0, 0, 0), 11), ((0, 0, -2), 50)],
    }
    steps = 0
    for name, frames in patterns.items():
        for facing_right in (False, True):
            initial = InputBank(right=1) if facing_right else InputBank(left=1)
            machine.fixture(level, initial, frames[0][1])
            machine.put_word(-0x5054, 0 if facing_right else -1)
            expected_bank = initial
            trace = []
            for (horizontal, vertical, modifier), pose in frames:
                axes = (horizontal if facing_right else -horizontal, vertical, modifier)
                for field, value in zip((-0x3498, -0x3496, -0x3494), axes):
                    machine.put_word(field, value)
                machine.put_word(-0x504c, pose)
                machine.events = []
                machine.call(4, 0x3e84)
                machine.call(4, 0x3d96)
                expected_bank, expected_events = sampled_route(expected_bank, axes, pose, facing_right=facing_right)
                actual = machine.bank(), tuple(machine.events)
                if actual != (expected_bank, expected_events):
                    raise AssertionError(('trace', name, facing_right, pose, actual, expected_bank, expected_events))
                trace.append(dict(pose=pose, axes=axes, bank=actual[0].words(), events=actual[1]))
                steps += 1
            traces[f'{name}/{facing_right}'] = trace
    # Separate action-body boundary: execute DoStrike's actual modifier/reset
    # instructions, while JumpSeq remains a supplied animation request sink.
    attack_cases = 0
    for pose, enemy_type, bank in product((149, 150, 151, 157, 158, 161, 165, 170, 171), (0, 11), banks):
        machine.fixture(level, bank, pose)
        machine.put_word(-0x508c, enemy_type)
        machine.call(6, 0x2780)
        sequence = (66 if pose in (150, 161) else
                    (96 if enemy_type == 11 else 75) if pose in (157, 158, 165, 170, 171) else None)
        expected = (InputBank(modifier=2), (('sequence', sequence),)) if sequence else (bank, ())
        if (machine.bank(), tuple(machine.events)) != expected:
            raise AssertionError(('attack modifier', pose, enemy_type, bank, machine.bank(), machine.events))
        attack_cases += 1
    return dict(route_cases=count, sampled_trace_steps=steps, attack_modifier_cases=attack_cases,
                mismatches=0, traces=traces,
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw_program).hexdigest(),
                supplied=['Living unarmed Prince10/type0, pose/mode/sequence and relative latches',
                          'Action/geometry bodies as no-op call sinks; pickup=false, target=-1',
                          'Trace poses and raw sampled axes; no OS keyboard or animation advancement',
                          'Separate DoStrike type0 calls with supplied pose/opponent type and JumpSeq sink'],
                exclusions='No full FrameAdv/animation/geometry or weapon target admission; directional action sinks do not consume latches inside their own bodies.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'traces'}))


if __name__ == '__main__':
    main()
