"""Bound native gate-side contact for the room3 run/closing-plate report.

Original LoadFrame/SetupSword/GetCharEdges and warm CheckBarr/CheckCollide1
execute. Actor poses/X and the final gate foreground are supplied snapshots,
not native running or pressure-controller execution. Inherits the explicit
shape-header/SectRect/no-op Collide services, empty rocks and zero float timer
from probe_vertical_jump_gate_contact. No complete FrameAdv or pixel proof.
"""

import argparse
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.mac_resources import parse_resource_fork
from pop2.terrain import LevelMap
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_kid_frames import verify_frames
from tools.probe_vertical_jump_gate_contact import NativeVerticalJumpContact


class NativeGatePassage(NativeVerticalJumpContact):
    def sample_run(self, x, pose, facing, *, sequence=1, room=3, row=1):
        actor = bytearray(62)
        bottom = row * 120 + 106
        for offset, value in ((2, 0 if facing else -1), (4, x + 207), (6, bottom),
                              (10, pose), (14, row), (16, int(pose != 15)),
                              (22, room), (26, 0), (28, -1), (40, sequence)):
            put_actor(actor, offset, value)
        self.cpu.mem_write(self.A5 - 0x5056, bytes(actor))
        self.call(4, 0x2a72)
        self.call(3, 0x0ac8)
        self.call(4, 0x5cbc)
        bounds = (self.word(-0x3564) - 207 + facing, self.word(-0x356c),
                  self.word(-0x3566) - 207 - (1 if facing else 2),
                  bottom + struct.unpack_from('>h', self.frame_data, pose * 10 + 6)[0])
        self.call(4, 0x4e34)
        self.responses = []
        self.call(4, 0x54da)
        verify_frames(self)
        return bounds, list(self.responses)


def run_probe(source):
    forks = source / 'resource_forks'
    files = {name: (forks / name).read_bytes() for name in
             ('Prince of Persia 2.bin', 'Kid.rsrc.bin', 'Prince.rsrc.bin')}
    executable, kid, prince = files.values()
    original = parse_resource_fork(prince)['LEVL'][2011]['data']
    if (struct.unpack_from('>H', original, 0x2186)[0] != 2
            or struct.unpack_from('>H', original, 0x218a)[0] != 12
            or struct.unpack_from('>H', original, 2 * 60 + 18 * 2)[0] != 4):
        raise AssertionError('Unexpected level12 room3 gate fixture')
    machine = NativeGatePassage(parse_resource_fork(executable), parse_resource_fork(kid))
    offset = 0x780 + 2 * 120 + 18 * 4
    state = SimpleNamespace(actor_type=0, source_sequence_id=1)
    samples = comparisons = controls = 0
    digest = hashlib.sha256()
    # Actual rightward running trace; mirrored snapshots supply the other facing.
    path = ((445, 15), (449, 2), (453, 3), (462, 4), (472, 5),
            (479, 6), (492, 7), (502, 8), (516, 9))
    for facing in (0, 1):
        for final in (0, 24, 60, 124, 180, 184):
            level = bytearray(original)
            machine.prepare(level, 3, 1)
            previous = None
            passages = ()
            for index, (x, pose) in enumerate(path):
                x = x if facing else 950 - x
                phase = final if index == len(path) - 1 else 184
                struct.pack_into('>H', level, offset, phase)
                machine.cpu.mem_write(machine.LEVEL + offset, struct.pack('>H', phase))
                bounds, events = machine.sample_run(x, pose, facing)
                if events:
                    raise AssertionError(('false native front collision', facing, phase, x, pose, events))
                if previous:
                    terrain = LevelMap(level)
                    passages = terrain.gate_passage_history(2, 1, bounds, previous[1], passages, state)
                    corrected = terrain.wall_correction(2, previous[0], x, bounds,
                        previous[1], facing, 1, state, gate_passages=passages)
                    if corrected != x:
                        raise AssertionError(('port pushed runner back', facing, phase, x, corrected))
                    comparisons += 1
                digest.update(repr((facing, phase, x, pose, bounds, events)).encode('ascii'))
                previous = x, bounds
                samples += 1
            if machine.level_bytes(len(level)) != level or machine.services:
                raise AssertionError('Unexpected level mutation or supplied service')
        # Genuine front crossing at closed gate still invokes Collide.
        level = bytearray(original)
        machine.prepare(level, 3, 1)
        before_x, x = (445, 479) if facing else (505, 471)
        before, events = machine.sample_run(before_x, 15, facing)
        if events:
            raise AssertionError(('unexpected primer collision', events))
        bounds, events = machine.sample_run(x, 6, facing)
        corrected = LevelMap(level).wall_correction(2, before_x, x, bounds, before, facing, 1, state)
        if corrected == x or events != [('collide', corrected - x, -1 if facing else 0)]:
            raise AssertionError(('front crossing was lost', facing, bounds, events, corrected))
        controls += 1
    return {'native_samples': samples, 'port_comparisons': comparisons,
            'front_crossing_controls': controls, 'mismatches': 0,
            'outputs_sha256': digest.hexdigest(),
            'inputs_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in files.items()},
            'scope': __doc__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
