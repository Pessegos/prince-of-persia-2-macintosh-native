"""Execute the ordinary saved player input wrapper, with keyboard/recording sinks."""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_input_actions import NativeInputActions
from tools.probe_level7_rules import NativeRules
from tools.reference_input_bank import InputBank
from tools.reference_player_input import player_input_tick


SAVED = (-0x3492, -0x3490, -0x348e, -0x348c, -0x348a)
POISON = InputBank(1, -1, 1, -1, 2)


class NativePlayerInput(NativeInputActions):
    RANGES = {**NativeInputActions.RANGES,
              4: NativeInputActions.RANGES[4] + ((0x3cae, 0x3d14),)}
    SUPPLIED = {**NativeInputActions.SUPPLIED,
                (2, 0x55d2): 'keyboard', (5, 0x6072): 'recording'}

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        service = self.SUPPLIED.get((segment, offset))
        if service in ('keyboard', 'recording') and address != self.stop_at:
            bank = self.bank()
            NativeRules.dispatch(self, cpu, address, size, user)
            if service == 'keyboard':
                self.restored_bank = bank
                for field, value in zip((-0x3498, -0x3496, -0x3494), self.axes):
                    self.put_word(field, value)
            else:
                self.recorded_bank = bank
                cpu.reg_write(self.registers['d0'], self.record_status)
            return
        super().dispatch(cpu, address, size, user)

    def save_bank(self, bank):
        for field, value in zip(SAVED, bank.words()):
            self.put_word(field, value)

    def saved_bank(self):
        return InputBank(*(self.word(field) for field in SAVED))

    def configure_tick(self, axes, *, gate_matches=True, room=1, sequence=201,
                       pose=20, facing_right=True, mode=0, record_status=0x1234):
        self.axes, self.record_status = axes, record_status
        self.events, self.reads = [], 0
        self.services.clear()
        self.restored_bank = self.recorded_bank = None
        for field, value in ((-0x4f92, 3), (-0x4fd2, 3 if gate_matches else 2),
                             (-0x5040, room), (-0x502e, sequence), (-0x504c, pose),
                             (-0x5046, mode), (-0x5054, 0 if facing_right else -1),
                             (-0x4ffe, 0), (-0x4fa8, 0)):
            self.put_word(field, value)


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    raw = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(raw)
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2004]['data']
    assert struct.unpack_from('>H', level, 0x2186)[0] == 3
    assert struct.unpack_from('>H', level, 0x218a)[0] == 5
    machine = NativePlayerInput(program)
    counts, digest = {'sample_wrapper': 0, 'gate_boundaries': 0, 'composed_wrapper': 0,
                      'excluded_other_actions': 0, 'persistent_steps': 0}, hashlib.sha256()

    def compare(saved, expected, result, label):
        action = expected.action
        events = (('sequence', action.sequence),) if action.sequence is not None else ()
        actual = (machine.restored_bank, machine.recorded_bank, machine.saved_bank(),
                  machine.bank(), tuple(machine.events), machine.word(-0x5052),
                  machine.word(-0x503e), machine.word(-0x4f96), result)
        wanted = (saved, action.bank, action.bank, action.bank, events, action.x,
                  action.warning, expected.countdown, expected.record_status)
        if actual != wanted or any(machine.services[name] != 1 for name in ('keyboard', 'recording')):
            raise AssertionError((label, actual, wanted))
        digest.update(repr(actual).encode())

    def check(bank, axes, pose=20, *, countdown=0, **context):
        expected = player_input_tick(bank, axes, pose, countdown=countdown, **context)
        machine.action_fixture(level, InputBank(), {}, facing_right=context.get('facing_right', True))
        machine.save_bank(bank)
        machine.put_bank(POISON)
        machine.put_word(-0x4f96, countdown)
        machine.configure_tick(axes, pose=pose, **context)
        result = machine.call(4, 0x3cae)
        compare(bank, expected, result, (bank, axes, pose, countdown, context))

    banks = [InputBank(*directions, modifier) for directions in product((-1, 0, 1), repeat=4)
             for modifier in (-2, -1, 0, 1, 2)]
    axes_values = tuple(product((-1, 0, 1), (-1, 0, 1), (-2, -1, 0)))
    for bank, axes, facing, enabled in product(banks, axes_values, (False, True), (False, True)):
        check(bank, axes, facing_right=facing, gate_matches=enabled)
        counts['sample_wrapper'] += 1
    for bank, axes, room, sequence, countdown, status in product(
            (InputBank(), InputBank(-1, -1, -1, -1, -2)), axes_values,
            (0, 1), (59, 201), (-32768, -1, 0, 1, 32767), (0, 0xbeef)):
        check(bank, axes, room=room, sequence=sequence, countdown=countdown, record_status=status)
        counts['gate_boundaries'] += 1
    for bank, axes, pose, facing, enabled in product(
            banks, ((0, 0, 0), (1, -1, 0)), (6, 7, 8, 26, 44, 48, 50),
            (False, True), (False, True)):
        try:
            check(bank, axes, pose, facing_right=facing, gate_matches=enabled)
        except NotImplementedError:
            counts['excluded_other_actions'] += 1
            continue
        counts['composed_wrapper'] += 1

    # A different actor may overwrite the working bank between player calls.
    # Poison it each time; saved player state must remain the sole authority.
    traces = {}
    for facing in (False, True):
        direction = 1 if facing else -1
        saved = InputBank()
        machine.action_fixture(level, InputBank(), {}, facing_right=facing)
        machine.save_bank(saved)
        machine.put_word(-0x4f96, 2)
        countdown, x, warning, frames = 2, 400, 1, []
        for pose, axes, enabled in ((20, (direction, -1, 0), True),
                                    (20, (0, 0, 0), False),
                                    (26, (0, 0, 0), False),
                                    (27, (direction, -1, 0), True),
                                    (50, (0, 0, 0), False)):
            machine.put_bank(POISON)
            machine.configure_tick(axes, pose=pose, facing_right=facing, gate_matches=enabled)
            expected = player_input_tick(saved, axes, pose, countdown=countdown, x=x,
                                         warning=warning, facing_right=facing, gate_matches=enabled)
            result = machine.call(4, 0x3cae)
            compare(saved, expected, result, ('persistent', facing, pose, axes, enabled))
            saved, countdown = expected.action.bank, expected.countdown
            x, warning = expected.action.x, expected.action.warning
            frames.append(dict(pose=pose, axes=axes, enabled=enabled, saved=saved.words(),
                               countdown=countdown, request=expected.action.sequence))
            counts['persistent_steps'] += 1
        traces[str(facing)] = frames
    return dict(cases=counts, mismatches=0, outputs_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(raw).hexdigest(), traces=traces,
                actual=['4:3cae-3d14 save/restore/gate/countdown, sampler/facing/router/action composition'],
                supplied=['ReadKeyboard raw axes/modifier and recording endpoint/result',
                          'Living type0 Prince, level5, pose/mode/facing/sequence and terrain services',
                          'JumpSeq request sink, ordinary vertical orientation, no special replay hook'],
                exclusions='No OS keyboard polling, full recording/demo implementation, death lifecycle, physical animation or FrameAdv')


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
