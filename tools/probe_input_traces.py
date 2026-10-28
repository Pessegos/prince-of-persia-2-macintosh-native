"""Execute original routing plus action bodies, and persistent sampled input traces."""

import argparse
from dataclasses import asdict
import hashlib
from itertools import product
import json
from pathlib import Path

from tools.probe_input_actions import NativeInputActions
from tools.reference_input_bank import InputBank
from tools.reference_input_traces import composed_route, sampled_tick
from pop2.mac_resources import parse_resource_fork


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    raw = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(raw)
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2004]['data']
    machine = NativeInputActions(program)
    counts, digest = {'composed': 0, 'excluded_other_actions': 0, 'trace_steps': 0}, hashlib.sha256()

    def compare(expected, label):
        actual = (machine.bank(), tuple(machine.events), machine.word(-0x5052),
                  machine.word(-0x503e), machine.word(-0x36bc))
        events = (('sequence', expected.sequence),) if expected.sequence is not None else ()
        wanted = (expected.bank, events, expected.x, expected.warning, 0)
        if actual != wanted:
            raise AssertionError((label, actual, wanted))
        digest.update(repr(actual).encode())

    banks = [InputBank(*directions, modifier) for directions in product((-1, 0, 1), repeat=4)
             for modifier in (-2, -1, 0, 1, 2)]
    terrains = ({}, dict(barrier=1, distance=5, cells=(False, False), gap_distance=16,
                         ahead_kind=4, wall=True, wall_distance=6))
    poses = (*range(1, 16), 26, 27, 44, *range(45, 53), 67, 68, 69)
    for bank, facing, pose, terrain in product(banks, (False, True), poses, terrains):
        try:
            expected = composed_route(bank, pose, facing_right=facing, **terrain)
        except NotImplementedError:
            counts['excluded_other_actions'] += 1
            continue
        machine.action_fixture(level, bank, terrain, facing_right=facing, pose=pose)
        machine.call(6, 0x0560)
        compare(expected, ('composed', bank, facing, pose, terrain))
        counts['composed'] += 1

    # Raw axes and pose/mode/facing are supplied; banks, X and warning persist.
    # No sequence is automatically advanced, and no physics is fabricated.
    patterns = {
        'rejected_running_jump_retries_released_up': [
            (6, (1, -1, 0), 0, {}),
            (7, (1, 0, 0), 0, dict(cells=(False, False))),
            (8, (1, 0, 0), 0, {}), (44, (0, 0, 0), 0, {}),
            (50, (0, 0, 0), 0, {})],
        'backward_beats_up_and_discards_it': [
            (8, (-1, -1, 0), 0, {}), (45, (0, 0, 0), 0, {}),
            (50, (0, 0, 0), 0, {})],
        'jump_reset_discards_early_tap': [
            (20, (1, -1, 0), 0, {}), (26, (0, 0, 0), 0, {}),
            (50, (0, 0, 0), 0, {})],
        'tap_after_jump_reset_survives_to_standing': [
            (26, (0, 0, 0), 0, {}), (27, (1, -1, 0), 0, {}),
            (50, (0, 0, 0), 0, {})],
        'protected_recovery_discards_released_up': [
            (110, (0, -1, 0), 5, {}), (116, (0, 0, 0), 5, {}),
            (117, (0, 0, 0), 1, {}), (50, (0, 0, 0), 0, {})],
        'protected_recovery_rearms_held_up': [
            (110, (0, -1, 0), 5, {}), (116, (0, -1, 0), 5, {}),
            (117, (0, -1, 0), 1, {})],
        'blocked_run_consumes_step_then_keeps_running_hold': [
            (50, (1, 0, 0), 0, dict(barrier=1, distance=5)),
            (50, (1, 0, 0), 0, dict(barrier=1, distance=5)),
            (50, (1, 0, 0), 0, {}), (7, (0, 0, 0), 0, {})],
        'released_ctrl_does_not_bypass_braking': [
            (8, (1, 0, -2), 0, {}), (11, (0, 0, 0), 0, {}),
            (50, (0, 0, 0), 0, {})],
        'direction_reinterpreted_after_facing_flip': [
            (45, (-1, 0, 0), 0, {}), (48, (0, 0, 0), 0, {}),
            (50, (0, 0, 0), 0, {})],
    }
    traces = {}
    for name, frames in patterns.items():
        for facing in (False, True):
            # Start with a consumed Forward only for an ongoing run.
            bank = (InputBank(right=1) if facing else InputBank(left=1)) if frames[0][0] in (6, 8) else InputBank()
            machine.action_fixture(level, bank, {}, facing_right=facing)
            x, warning, trace = 400, 1, []
            for index, (pose, axes, mode, terrain) in enumerate(frames):
                tick_facing = not facing if name == 'direction_reinterpreted_after_facing_flip' and index else facing
                physical_axes = (axes[0] if tick_facing else -axes[0], axes[1], axes[2])
                for field, value in zip((-0x3498, -0x3496, -0x3494), physical_axes):
                    machine.put_word(field, value)
                machine.put_word(-0x504c, pose)
                machine.put_word(-0x5046, mode)
                machine.put_word(-0x5054, 0 if tick_facing else -1)
                machine.put_word(-0x3576, terrain.get('barrier', 0))
                machine.terrain, machine.reads, machine.events = terrain, 0, []
                expected = sampled_tick(bank, physical_axes, pose, mode=mode,
                                        x=x, warning=warning, facing_right=tick_facing, **terrain)
                machine.call(4, 0x3e84)
                machine.call(4, 0x3d96)
                compare(expected, ('trace', name, facing, pose, physical_axes))
                bank, x, warning = expected.bank, expected.x, expected.warning
                trace.append(dict(pose=pose, axes=physical_axes, mode=mode, facing_right=tick_facing,
                                  terrain=terrain, result=asdict(expected)))
                counts['trace_steps'] += 1
            traces[f'{name}/{facing}'] = trace
    return dict(cases=counts, mismatches=0, outputs_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(raw).hexdigest(), traces=traces,
                actual=['Native sample/remap/GenCtrl/actions/ClearControls/relative-X arithmetic'],
                supplied=['Level5 living type0 Prince, pose/mode/sequence/facing per tick',
                          'Terrain services and JumpSeq request sink; persistent bank/X/warning'],
                exclusions='Up/Down-only actions, draw/target and full animation/physics/FrameAdv/OS polling; matrices exclude unsupported actions explicitly')


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
