"""Bounded native routing and actual vertical-jump landing input traces.

Native poses/terrain/action endpoints are supplied. Host scenes use actual
SEQS and scenery. This is not a synchronized native/host physics replay.
"""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct
from unittest.mock import patch

from pop2.mac_resources import parse_resource_fork
from tools.probe_input_routes import NativeInputRoutes
from tools.reference_input_bank import InputBank
from tools.reference_input_routes import sampled_route


def host_trace(sequence, facing, late, order, *, inverted=False):
    from tests.test_terrain import RooftopSceneTests

    fixture = RooftopSceneTests()
    fixture.setUp()
    scene, trace = fixture.scene, []

    def record(label):
        state, bank = scene.sequence_state, scene.directional_input
        trace.append(dict(label=label, sequence=state.sequence_id, pose=state.action,
                          mode=state.animation_state, x=state.target_x,
                          bank=bank.words() if bank else None))

    def key(name, pressed):
        physical = ('down' if name == 'up' else 'up') if inverted else name
        scene.in_animation_tick = True
        scene.set_key_state(physical, pressed)
        if getattr(scene, name + '_held') != pressed:
            raise AssertionError('Physical key did not reach the intended logical direction')
        record(name + (' pressed' if pressed else ' released'))

    def choice():
        state = scene.sequence_state
        if state.sequence_id in (14, 28) and state.action == 67:
            return 'up'
        if state.sequence_id in (26, 50):
            return 'down'
        if state.sequence_id in (2, 11) and state.action == 15:
            return 'none'
        return None

    try:
        with patch.object(scene, 'render'):
            scene.load_level(6)
            scene.peaceful = True
            scene.jump_to_room(7, 1, 300, facing)
            scene.game.caverns.potions.flip_timer = 100 if inverted else 0
            scene.sync_flipped_controls()
            scene.in_animation_tick = True
            # Supplied valid vertical takeoff, as in the preceding arc audit.
            scene.start_sequence(sequence)
            for _ in range(40):
                fixture.tick()
                if scene.action == (84 if late else 75):
                    break
            else:
                raise AssertionError('Vertical jump did not reach the requested window')
            record('before inputs')
            for name in order:
                key(name, True)
                fixture.tick()
                record('advance')
                key(name, False)
            for _ in range(35):
                if choice() is not None:
                    break
                fixture.tick()
                record('advance')
            else:
                raise AssertionError('Vertical jump did not return to a ready gate')
            if scene.room_id != 7 or scene.terrain_motion.dead or scene.terrain_motion.falling:
                raise AssertionError('Host left the intended flat platform')
            return dict(choice=choice(), trace=trace)
    finally:
        fixture.doCleanups()


def native_trace(machine, level, sequence, facing, late, order):
    poses = (84, 85, 15) if late else (*range(75, 80), 81, 82, 83, 84, 85, 15)
    bank, trace = InputBank(), []
    machine.fixture(level, bank, poses[0], mode=1, sequence=sequence)
    machine.put_word(-0x5040, 8)
    for index, pose in enumerate(poses):
        vertical = (-1 if order[index] == 'up' else 1) if index < 2 else 0
        axes = (0, vertical, 0)
        mode = 5 if pose == 83 else 0 if pose == 15 else 1
        current = 11 if pose >= 81 or pose == 15 else sequence
        for field, value in zip((-0x3498, -0x3496, -0x3494), axes):
            machine.put_word(field, value)
        for field, value in ((-0x5054, 0 if facing else -1), (-0x504c, pose),
                             (-0x5046, mode), (-0x502e, current)):
            machine.put_word(field, value)
        expected, events = sampled_route(bank, axes, pose, facing_right=bool(facing),
                                         mode=mode, sequence=current)
        machine.events = []
        machine.call(4, 0x3e84)
        machine.call(4, 0x3d96)
        if (machine.bank(), tuple(machine.events)) != (expected, events):
            raise AssertionError((sequence, facing, late, order, pose, machine.bank(), expected))
        bank = expected
        trace.append(dict(pose=pose, mode=mode, bank=bank.words(), requests=events))
    return trace


def run_audit(source):
    directory = Path(source) / 'resource_forks'
    executable = directory / 'Prince of Persia 2.bin'
    raw = executable.read_bytes()
    program = parse_resource_fork(raw)
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2005]['data']
    assert struct.unpack_from('>H', level, 0x2186)[0] == 4
    assert struct.unpack_from('>H', level, 0x218a)[0] == 6
    machine = NativeInputRoutes(program)
    cases = []
    for sequence, facing, late, order in product((14, 28), (0, 1), (False, True),
                                                (('up', 'down'), ('down', 'up'))):
        native = native_trace(machine, level, sequence, facing, late, order)
        host = host_trace(sequence, facing, late, order)
        events = native[-1]['requests']
        choice = events[0][0] if events else 'none'
        cases.append(dict(sequence=sequence, facing=facing, late=late, order=order,
                          native=native, host=host, agrees=host['choice'] == choice))
    if executable.read_bytes() != raw:
        raise AssertionError('Read-only original changed during audit')
    return dict(native_steps=sum(len(case['native']) for case in cases),
                native_model_mismatches=0, host_cases=len(cases),
                host_differences=sum(not case['agrees'] for case in cases), cases=cases,
                executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['Native poses/modes/sequences/axes; Up/Down/cell/pickup endpoints as sinks',
                          'Host selected vertical takeoff on actual level6 room8 flat platform'],
                exclusions=['No native animation/physics/FrameAdv or synchronized replay',
                            'No native ledge/climb/terrain action admission or whole input parity'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_audit(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'cases'}))


if __name__ == '__main__':
    main()
