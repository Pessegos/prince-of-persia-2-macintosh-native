"""Execute original keyboard sampling + OnAlert frame by frame for Ctrl tap patterns.

Each frame runs the modifier/directional update 4:3e84-3f42 on the raw Ctrl
state, then OnAlert 6:24bc with its action bodies (DoStrike 6:2780 and
ClearControls 4:3e3a among them). An accepted strike restarts the supplied
pose list of SEQS 75 (151..157, then the guard pose 158; the order the port
checks against the original capture). The result is the number of swings
each Ctrl pattern produces; `tests.test_armed_input` replays the same
patterns through the port's key callbacks and animation ticks.
"""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_armed_consumption import NativeArmedBodies
from tools.reference_armed_input import armed_action
from tools.reference_input_bank import InputBank

ATTACK_POSES = (151, 152, 153, 154, 155, 156, 157)
GUARD_POSE = 158
FRAMES = 10


def closed_form(pattern):
    """The rule the probe checks: a strike starts at frame 0; the next one
    starts at the first gate frame (7 = pose 157, then guard frames) where
    Ctrl is held after having been released at some earlier frame. A press
    released again before the gate is cancelled (4:3f38 writes 0)."""
    starts = [0]
    for frame in range(7, len(pattern)):
        if pattern[frame] and 0 in pattern[1:frame]:
            starts.append(frame)
            break
    return tuple(starts)


def reference_swings(pattern, bank=InputBank(modifier=2)):
    """Swing start frames for one raw-Ctrl pattern (1 = held), from guard."""
    poses, starts = [], []
    queue = []
    for frame, held in enumerate(pattern):
        pose = queue.pop(0) if queue else GUARD_POSE
        poses.append(pose)
        bank = bank.sample(0, 0, -2 if held else 0)
        bank, events = armed_action(bank, pose, fight=1, distance=40)
        if ('sequence', 75) in events:
            starts.append(frame)
            queue = list(ATTACK_POSES)
    return tuple(starts), tuple(poses)


def patterns():
    # The first press is at frame 0 (from the guard pose with the previous
    # Ctrl released: modifier 0); every later frame is held or released.
    for rest in product((0, 1), repeat=FRAMES - 1):
        yield (1, *rest)


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    path = directory / 'Prince of Persia 2.bin'
    raw = path.read_bytes()
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2004]['data']
    assert struct.unpack_from('>H', level, 0x218a)[0] == 5
    machine = NativeArmedBodies(parse_resource_fork(raw))
    machine.distance, machine.opponent = 40, 1
    digest, count, steps, double_taps = hashlib.sha256(), 0, 0, 0
    by_swings = {}
    for pattern in patterns():
        bank, queue, starts = InputBank(), [], []
        for frame, held in enumerate(pattern):
            pose = queue.pop(0) if queue else GUARD_POSE
            machine.fixture(level, bank, pose, sword=1)
            machine.put_word(-0x508a, 0)
            for offset, value in ((-0x3498, 0), (-0x3496, 0), (-0x3494, -2 if held else 0)):
                machine.put_word(offset, value)
            machine.call(4, 0x3e84)
            machine.events = []
            machine.call(6, 0x24bc)
            bank = machine.bank()
            if ('sequence', 75) in machine.events:
                starts.append(frame)
                queue = list(ATTACK_POSES)
            steps += 1
        expected = reference_swings(pattern, InputBank())[0]
        if tuple(starts) != expected or expected != closed_form(pattern):
            raise AssertionError((pattern, starts, expected))
        digest.update(repr((pattern, tuple(starts))).encode())
        key = f'{len(starts)} swing(s)'
        by_swings[key] = by_swings.get(key, 0) + 1
        if pattern[1:7].count(1) and 0 in pattern[1:7] and not any(pattern[7:]):
            double_taps += len(starts) == 1
        count += 1
    if path.read_bytes() != raw:
        raise AssertionError('Read-only original changed')
    return dict(patterns=count, frames=steps, mismatches=0, swing_histogram=by_swings,
                second_tap_released_before_gate_single_swing=double_taps,
                result_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(raw).hexdigest(),
                supplied=['Living armed Prince (type 0, ALIVE), LEVL2004 header, no opponent pose',
                          'Pose per frame: guard 158, SEQS 75 = 151..157 after each accepted strike',
                          'JumpSeq 6:0006 records the sequence; OppToFight/distance supplied'],
                exclusions=['No outer SwordCtrl routing, FrameAdv, terrain or opponent',
                            'One keyboard sample per frame: a tap shorter than a frame is not modelled'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
