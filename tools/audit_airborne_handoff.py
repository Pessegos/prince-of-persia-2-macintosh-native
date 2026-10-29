"""Compare actual late-jump host requests with bounded original bank traces.

Native poses/axes are supplied, with Up/Down action bodies as explicit sinks.
The host runs the real SEQS/terrain on a flat ruins platform. These are two
separate experiments, not an original/port FrameAdv lockstep replay.
"""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import struct
from unittest.mock import patch

from pop2.mac_resources import parse_resource_fork
from tools.probe_input_routes import NativeInputRoutes
from tools.reference_input_bank import InputBank
from tools.reference_input_routes import sampled_route


def schedule(order, late):
    poses = (27, 28, 29, 30, 31, 32, 33, 15) if late else (
        22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 15)
    axes = [(0, -1 if key == 'up' else 1, 0) for key in order]
    return [(pose, axes[index // 2] if index in (0, 2) else (0, 0, 0))
            for index, pose in enumerate(poses)]


def native_trace(machine, level, facing, order, late):
    bank, trace = InputBank(), []
    machine.fixture(level, bank, 27 if late else 22, mode=1, sequence=3)
    machine.put_word(-0x5040, 8)
    machine.put_word(-0x5048, 1)
    for pose, axes in schedule(order, late):
        mode = 0 if pose == 15 else 1
        for field, value in zip((-0x3498, -0x3496, -0x3494), axes):
            machine.put_word(field, value)
        for field, value in ((-0x5054, 0 if facing else -1), (-0x504c, pose),
                             (-0x5046, mode), (-0x502e, 2 if pose == 15 else 3)):
            machine.put_word(field, value)
        machine.events = []
        expected_bank, events = sampled_route(bank, axes, pose, facing_right=bool(facing),
                                              mode=mode, sequence=2 if pose == 15 else 3)
        machine.call(4, 0x3e84)
        machine.call(4, 0x3d96)
        actual = machine.bank(), tuple(machine.events)
        if actual != (expected_bank, events):
            raise AssertionError((facing, order, late, pose, actual, expected_bank, events))
        bank = expected_bank
        trace.append(dict(pose=pose, mode=mode, axes=axes, bank=bank.words(), requests=events))
    return trace


def host_trace(facing, order, late):
    # This fixture withdraws its Tk root, isolates saves through tests.__init__,
    # and disables scheduling. No physical keyboard/focus or live game is used.
    from tests.test_terrain import RooftopSceneTests

    fixture = RooftopSceneTests()
    fixture.setUp()
    scene, trace = fixture.scene, []

    def record(label):
        state = scene.sequence_state
        pending, bank = scene.pending_action, scene.directional_input
        trace.append(dict(label=label, pose=state.action, sequence=state.sequence_id,
                          selected_sequence=state.source_sequence_id,
                          room=scene.room_id, row=scene.terrain_motion.row,
                          x=state.target_x, pending=asdict(pending) if pending else None,
                          bank=bank.words() if bank is not None else None))

    try:
        scene.load_level(6)
        scene.peaceful = True
        scene.jump_to_room(7, 1, 450 if not facing else 260, facing)
        scene.in_animation_tick = True
        # Supplied valid in-progress jump entry; subsequent frames and terrain
        # run normally. This experiment is about handoff, not takeoff admission.
        scene.start_sequence(3)
        with patch.object(scene, 'render'):
            for _ in range(30):
                fixture.tick()
                if scene.action == (27 if late else 22):
                    break
            else:
                raise AssertionError('Jump did not reach the requested input window')
            record('before inputs')
            for key in order:
                scene.in_animation_tick = True
                if key == 'up':
                    scene.up_key(None)
                else:
                    scene.set_key_state(key, True)
                record(key + ' pressed')
                fixture.tick()
                scene.set_key_state(key, False)
                record(key + ' released')
                fixture.tick()
            for _ in range(16):
                fixture.tick()
                record('advance')
                if scene.sequence_state.sequence_id != 3:
                    break
            if scene.room_id != 7 or scene.terrain_motion.falling or scene.terrain_motion.dead:
                raise AssertionError('Host fixture left the intended flat platform')
        final_sequence = scene.sequence_state.sequence_id
        return dict(trace=trace, final_sequence=final_sequence,
                    choice={2: 'none', 28: 'up', 50: 'down'}.get(final_sequence, 'other'))
    finally:
        fixture.doCleanups()


def run_audit(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    program = parse_resource_fork(raw)
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2005]['data']
    assert struct.unpack_from('>H', level, 0x2186)[0] == 4
    assert struct.unpack_from('>H', level, 0x218a)[0] == 6
    machine = NativeInputRoutes(program)
    cases = []
    for late in (False, True):
        for facing in (0, 1):
            for order in (('up', 'down'), ('down', 'up')):
                native = native_trace(machine, level, facing, order, late)
                host = host_trace(facing, order, late)
                requests = native[-1]['requests']
                choice = requests[0][0] if requests else 'none'
                cases.append(dict(late=late, facing=facing, order=order, native=native,
                                  original_choice=choice, host=host, agrees=choice == host['choice']))
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed during audit')
    return dict(native_steps=sum(len(case['native']) for case in cases),
                native_model_mismatches=0, host_cases=len(cases),
                host_priority_differences=sum(not case['agrees'] for case in cases),
                executable_sha256=hashlib.sha256(raw).hexdigest(), cases=cases,
                supplied=['Native pose/mode/axes/sequence per step; living unarmed Prince',
                          'Native pickup/cell/Up/Down/animation services as route sinks',
                          'Host SEQS3 entry on actual level6 room8 flat platform'],
                exclusions=['No native animation, physics, FrameAdv, OS keyboard or live emulator',
                            'No full trace synchronization or whole input-queue parity claim',
                            'Running jump4, inverted controls, ledge/low/armed families not audited here'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_audit(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'cases'}))


if __name__ == '__main__':
    main()
