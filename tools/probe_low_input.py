"""Execute low/prone GenCtrl, including actual JumpSeq selection and saved-bank flow."""

import argparse
from dataclasses import replace
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules
from tools.probe_player_input import NativePlayerInput, POISON
from tools.reference_input_bank import InputBank
from tools.reference_low_input import LowContext, LowResult, crouch_entry, low_control, sampled_low_tick


class NativeLowInput(NativePlayerInput):
    RANGES = {**NativePlayerInput.RANGES,
              6: NativePlayerInput.RANGES[6] + ((0x0006, 0x0098), (0x07ee, 0x0b58),
                                                (0x0e8e, 0x0f56), (0x1068, 0x10e2))}
    SUPPLIED = {key: value for key, value in NativePlayerInput.SUPPLIED.items()
                if key not in ((6, 0x0006), (6, 0x0e8e))}
    SUPPLIED.update({(17, 0x330e): 'resource', (6, 0x1350): 'pickup',
                     (4, 0x5baa): 'gate', (5, 0x5f1a): 'scythe',
                     (4, 0x35a6): 'here', (4, 0x3a48): 'behind',
                     (4, 0x39fc): 'ahead', (4, 0x3b30): 'ahead_column',
                     (4, 0x27ee): 'low_cell', (7, 0x3404): 'reveal',
                     (8, 0x14ae): 'carpet', (4, 0x5eae): 'low_distance',
                     (3, 0x4eb2): 'gap'})

    def __init__(self, program, sequences):
        super().__init__(program)
        self.sequence_ids = set(sequences)

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        service = self.SUPPLIED.get((segment, offset))
        if service in ('resource', 'pickup', 'gate', 'scythe', 'here', 'behind',
                       'ahead', 'ahead_column', 'low_cell', 'reveal', 'carpet',
                       'low_distance', 'gap') and address != self.stop_at:
            c = self.context
            value = 0
            if service == 'resource':
                stack = cpu.reg_read(self.registers['a7'])
                kind, sequence = struct.unpack('>4sh', cpu.mem_read(stack + 4, 6))
                if kind != b'SEQS':
                    raise AssertionError(('resource type', kind))
                self.requests.append(sequence)
                value = int(sequence in self.sequence_ids and sequence not in c.missing_sequences) * 0xbc000
            elif service == 'pickup':
                self.pickup_checked = True
                value = int(c.pickup)
            elif service == 'reveal':
                self.revealed = True
            elif service == 'carpet':
                self.carpet = True
            elif service == 'gap':
                # This block composes only ordinary Down's no-gap path.
                value = 0
            elif service == 'low_distance':
                value = c.distance
            elif service == 'low_cell':
                stack = cpu.reg_read(self.registers['a7'])
                room, column, row = struct.unpack('>3h', cpu.mem_read(stack + 4, 6))
                if room != c.room or row != 1 or column not in (c.column, c.column - 1):
                    raise AssertionError(('cell boundary', room, column, row, c))
                value = c.here_kind if column == c.column else c.left_kind
            else:
                value = {'gate': c.gate_blocked, 'scythe': c.scythe_blocked,
                         'here': c.here_kind, 'ahead': c.ahead_kind,
                         'behind': c.behind_kind, 'ahead_column': c.ahead_column}[service]
                if service in ('here', 'ahead', 'behind'):
                    self.put_word(-0x34ae, c.foreground)
            NativeRules.dispatch(self, cpu, address, size, user)
            cpu.reg_write(self.registers['d0'], int(value) & 0xffffffff)
            return
        super().dispatch(cpu, address, size, user)

    def low_fixture(self, level, bank, context):
        self.action_fixture(level, bank, {}, facing_right=context.facing_right,
                            warning=context.warning, pose=context.pose, x=context.x)
        self.context = context
        self.requests = []
        self.pickup_checked = self.revealed = self.carpet = False
        for field, value in ((-0x5046, context.mode), (-0x5030, context.sequence),
                             (-0x502e, context.selected), (-0x5032, context.cursor),
                             (-0x5040, context.room), (-0x504a, context.column), (-0x5048, 1)):
            self.put_word(field, value)
        self.cpu.mem_write(self.LEVEL + 0x218f, bytes((int(context.scythes_enabled),)))

    def result(self):
        return LowResult(self.bank(), self.word(-0x5052), self.word(-0x503e),
                         self.word(-0x5030), self.word(-0x502e), self.word(-0x5032),
                         tuple(self.requests), self.pickup_checked, self.revealed, self.carpet)

    def sampled_tick(self, axes, context, *, gate_matches=True):
        # Leave X, warning, selected sequence and cursor untouched between calls.
        self.context = context
        self.axes, self.record_status = axes, 0x1234
        self.events, self.reads, self.requests = [], 0, []
        self.pickup_checked = self.revealed = self.carpet = False
        self.restored_bank = self.recorded_bank = None
        self.services.clear()
        for field, value in ((-0x4f92, 3), (-0x4fd2, 3 if gate_matches else 2),
                             (-0x5040, context.room), (-0x504c, context.pose),
                             (-0x5046, context.mode), (-0x504a, context.column),
                             (-0x5054, 0 if context.facing_right else -1)):
            self.put_word(field, value)
        self.cpu.mem_write(self.LEVEL + 0x218f, bytes((int(context.scythes_enabled),)))
        self.put_bank(POISON)
        return self.call(4, 0x3cae)


def persistent_traces(machine, levels, digest):
    # Each tuple supplies pose/mode and relative raw axes at an input boundary.
    # It does not pretend to simulate AnimChar or establish physical reachability.
    traces = {
        'held-through-lower': (LowContext(sequence=50, selected=50), (
            (107, 5, 1, 1, -1, {}), (108, 5, 1, 1, -1, {}), (109, 1, 1, 1, -1, {}))),
        'released-before-last-reset': (LowContext(sequence=50, selected=50), (
            (107, 5, 1, 1, -1, {}), (108, 5, 0, 1, -1, {}), (109, 1, 0, 1, -1, {}))),
        'step-release-rise': (LowContext(), (
            (109, 1, 1, 1, -1, {}), (109, 1, 0, 0, -1, {}),
            (110, 5, 0, 0, -1, {}), (116, 5, 0, 0, -1, {}), (117, 1, 0, 0, -1, {}))),
        'crawl-release': (LowContext(sequence=122, selected=122, here_kind=7), (
            (251, 1, 1, 0, -1, {}), (252, 1, 0, 0, -1, {}), (251, 1, 0, 0, -1, {}))),
        'crawl-held': (LowContext(sequence=122, selected=122, here_kind=7), (
            (251, 1, 1, 0, -1, {}), (252, 1, 1, 0, -1, {}), (251, 1, 1, 0, -1, {}))),
        'stand-before-crawl': (LowContext(sequence=122, selected=122, ahead_kind=7), (
            (251, 1, 1, -1, 0, {}), (252, 1, 1, -1, 0, {}))),
        'rise-veto-then-clearance': (LowContext(gate_blocked=True), (
            (109, 1, 0, 1, 0, {}), (109, 1, 0, 0, 0, {}),
            (109, 1, 0, 0, 0, {'gate_blocked': False}))),
        'raw-gate-keeps-pending': (LowContext(pose=117), (
            (117, 1, 1, 1, -1, {}), (117, 1, 0, 0, 0, {'gate_matches': False}),
            (109, 1, 0, 0, 0, {'gate_matches': False}))),
    }
    outputs, steps = {}, 0
    for facing, level in product((False, True), (5, 6)):
        for name, (initial, samples) in traces.items():
            context = replace(initial, facing_right=facing, level=level, environment=3 if level == 5 else 4)
            saved, frames = InputBank(), []
            machine.low_fixture(levels[level], saved, context)
            machine.save_bank(saved)
            machine.put_word(-0x4f96, 0)
            for pose, mode, forward, vertical, modifier, external in samples:
                changes = dict(external)
                enabled = changes.pop('gate_matches', True)
                context = replace(context, pose=pose, mode=mode, **changes)
                axes = forward * (1 if facing else -1), vertical, modifier
                expected = sampled_low_tick(saved, axes, context, gate_matches=enabled)
                result = machine.sampled_tick(axes, context, gate_matches=enabled)
                actual = machine.result()
                if (actual != expected or machine.restored_bank != saved
                        or machine.recorded_bank != expected.bank or machine.saved_bank() != expected.bank
                        or result != 0x1234 or machine.services['keyboard'] != 1
                        or machine.services['recording'] != 1):
                    raise AssertionError(('persistent', name, facing, level, context, axes,
                                          actual, expected, machine.restored_bank, saved))
                digest.update(repr((name, actual)).encode())
                frames.append(dict(pose=pose, axes=axes, saved=actual.bank.words(),
                                   requests=actual.requests, selected=actual.selected, cursor=actual.cursor))
                saved = expected.bank
                context = replace(context, sequence=expected.sequence, selected=expected.selected,
                                  cursor=expected.cursor, x=expected.x, warning=expected.warning)
                steps += 1
            outputs[f'{name}/right={facing}/level={level}'] = frames
    return steps, outputs


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    raw = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(raw)
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    levels = {5: prince['LEVL'][2004]['data'], 6: prince['LEVL'][2005]['data']}
    for number, data in levels.items():
        assert struct.unpack_from('>H', data, 0x218a)[0] == number
        assert struct.unpack_from('>H', data, 0x2186)[0] == (3 if number == 5 else 4)
    machine = NativeLowInput(program, prince['SEQS'])
    assert {49, 79, 122, 123, 124, 125} <= machine.sequence_ids
    for column in range(10):
        machine.low_fixture(levels[5], InputBank(), LowContext())
        assert machine.word(-0x4b88 + column * 2) == 207 + 51 * column
    counts, digest = {}, hashlib.sha256()

    def check(bank, context, group='controller', *, direct=False, entry=None):
        machine.low_fixture(levels[context.level], bank, context)
        expected = crouch_entry(bank, context) if entry is not None else low_control(bank, context, controller=not direct)
        offset = entry if entry is not None else (0x099a if context.pose == 109 else 0x07ee) if direct else 0x0560
        machine.call(6, offset)
        actual = machine.result()
        if actual != expected:
            raise AssertionError((group, bank, context, actual, expected))
        counts[group] = counts.get(group, 0) + 1
        digest.update(repr(actual).encode())

    banks = [InputBank(*directions, modifier) for directions in product((-1, 0, 1), repeat=4)
             for modifier in (-2, -1, 0, 1, 2)]
    worlds = ({}, dict(gate_blocked=True), dict(ahead_kind=7), dict(ahead_kind=7, foreground=3),
              dict(ahead_kind=12), dict(pickup=True), dict(selected=111, sequence=111))
    for bank, facing, level, world in product(banks, (False, True), (5, 6), worlds):
        check(bank, LowContext(facing_right=facing, level=level, environment=3 if level == 5 else 4, **world))
    for bank, facing, level, pose, world in product(
            banks, (False, True), (5, 6), (246, 251, 261, 262, 263),
            ({}, dict(here_kind=7), dict(ahead_kind=12), dict(behind_kind=7), dict(behind_kind=13, scythe_blocked=True))):
        check(bank, LowContext(pose=pose, sequence=122, selected=122, facing_right=facing,
                               level=level, environment=3 if level == 5 else 4, **world), 'prone')
    boundary_banks = (InputBank(), InputBank(-1, -1, -1, -1, -2), InputBank(1, -1, 1, 1, 1))
    for bank, facing, x, column, blocked in product(
            boundary_banks, (False, True), (-32768, 400, 420, 421, 422, 457, 469, 479, 480, 481, 32767),
            (0, 4, 9), (False, True)):
        for kind in (7, 12, 13):
            check(bank, LowContext(facing_right=facing, x=x, ahead_column=column, ahead_kind=kind,
                                   scythes_enabled=True, scythe_blocked=blocked), 'alignment')
            check(bank, LowContext(pose=251, sequence=122, selected=122, facing_right=facing,
                                   x=x, column=column, behind_kind=kind, scythe_blocked=blocked), 'prone-boundary')
    for bank, mode, selected, pose in product(banks, (4, 5, 9), (117, 27, 110), (109, 110, 116, 117, 251)):
        check(bank, LowContext(mode=mode, selected=selected, pose=pose), 'protected-reset')
    for bank, sequence, here, left in product(boundary_banks, (17, 20, 111, 117), (1, 18), (1, 18)):
        check(bank, LowContext(room=3, sequence=sequence, selected=sequence,
                               here_kind=here, left_kind=left), 'carpet-priority')
    for bank, pose, selected, missing in product(
            boundary_banks, (109, 251), (117, 124), ((), (49, 79, 122, 123, 124, 125))):
        check(bank, LowContext(pose=pose, sequence=selected, selected=selected,
                               ahead_kind=7, missing_sequences=missing), 'resource-selection')
    for bank, facing, level in product(banks, (False, True), (5, 6)):
        context = LowContext(pose=15, facing_right=facing, level=level,
                              environment=3 if level == 5 else 4)
        for entry in (0x1068, 0x0e8e):
            check(bank, context, 'ordinary-crouch-entry', entry=entry)
    for bank, facing, kind, distance, missing in product(
            boundary_banks, (False, True), (1, 12, 13),
            (-32768, -1, 0, 7, 8, 9, 32767), ((), (50,))):
        context = LowContext(pose=15, facing_right=facing, level=6, environment=4,
                              ahead_kind=kind, distance=distance, missing_sequences=missing)
        for entry in (0x1068, 0x0e8e):
            check(bank, context, 'crouch-entry-boundary', entry=entry)
    counts['persistent-steps'], traces = persistent_traces(machine, levels, digest)
    return dict(cases=counts, total=sum(counts.values()), mismatches=0,
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                actual=['GenCtrl low/prone/reset, ordinary no-gap Down/crouch entry, ClearControls, relative X',
                        'Actual JumpSeq selection/cursor writes; saved-player wrapper and sampling in persistent traces'],
                supplied=['Level5/6 living Prince context and terrain/pickup/clearance/scythe decisions',
                          'Resource existence from real SEQS IDs; explicit missing-resource boundaries',
                          'Crevice reveal/carpet, raw keyboard and recording endpoints supplied; no physical animation advancement',
                          'Gap predicate is false for ordinary Down entry; ledge descent admission excluded'],
                traces=traces,
                exclusions='No full terrain reachability, actual pickup/carpet/reveal action, animation/FrameAdv or whole queue migration')


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
