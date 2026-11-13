"""Original Kid bounds and warm CheckBarr/CheckCollide1 for the wall-jump report.

Pose/X/Y/facing and room globals are fixtures, not native controller execution.
Original LoadFrame, SetupSword, GetCharEdges, history, three sweeps, ReadCell,
gate admission and collision decision execute. Shape-size services return
preserved SHAP header dimensions; SectRect is supplied arithmetic. Collide
is a recorded no-op. Float timer0 and an empty MOB bank exclude floating
ceiling and nonempty rock behavior. No pixel or complete FrameAdv comparison.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.mac_resources import parse_resource_fork
from pop2.terrain import LevelMap
from tools.probe_temple_collision_decision import NativeTempleCollisionDecision
from tools.probe_temple_collision_history import TABLES
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_distance import NEIGHBOR_SLOTS
from tools.probe_temple_gate_standing import COLD_CACHE
from tools.probe_temple_kid_frames import FRAME_RANGES, bind_frames, install_frames, verify_frames
from tools.probe_temple_sprite_bounds import (
    BOUNDS_RANGES, bind_bounds, bounds_service, shape_sizes,
)


SITES = ((10, 9, 0, 351), (10, 9, 2, 351), (12, 3, 0, 453),
         (12, 16, 1, 453), (12, 17, 0, 351), (12, 17, 1, 351))


class NativeVerticalJumpContact(NativeTempleCollisionDecision):
    RANGES = {segment: NativeTempleCollisionDecision.RANGES.get(segment, ())
              + FRAME_RANGES.get(segment, ()) + BOUNDS_RANGES.get(segment, ())
              for segment in NativeTempleCollisionDecision.RANGES.keys()
              | FRAME_RANGES.keys() | BOUNDS_RANGES.keys()}

    def __init__(self, program, kid):
        super().__init__(program)
        install_frames(self, kid['FRAM'][25001]['data'], kid['AFRM'][25001]['data'])
        self.sizes = shape_sizes(kid)
        self.shape_available = True
        self.bound_events = []

    def reset(self, level):
        super().reset(level)
        bind_frames(self)
        bind_bounds(self)
        self.bound_events = []

    def dispatch(self, cpu, address, size, user):
        if not bounds_service(self, cpu, address):
            super().dispatch(cpu, address, size, user)

    def prepare(self, level, room, row):
        self.reset(level)
        self.cpu.mem_write(self.A5 - 0x34b0, struct.pack('>6h', *COLD_CACHE))
        self.cpu.mem_write(self.A5 - 0x4496, struct.pack('>I', 0xb0000))
        self.cpu.mem_write(0xb0000, bytes(512))
        self.put_word(-0x4490, 0)
        for name, offset in TABLES.items():
            values = [65535 if name.endswith('tags') else 0] * 10
            self.cpu.mem_write(self.A5 + offset, struct.pack('>10H', *values))
        for offset in NEIGHBOR_SLOTS:
            self.put_word(offset, 0)
        links = struct.unpack_from('>4H', level, 0x2080 + (room - 1) * 8)
        for offset, value in ((-0x4fc2, room), (-0x4fc0, links[0]), (-0x4fbe, links[1]),
                              (-0x4fbc, links[2]), (-0x4fba, links[3]),
                              (-0x357c, row), (-0x357e, row), (-0x4fa6, 0), (-0x36bc, 0)):
            self.put_word(offset, value)

    def sample(self, room, row, x, pose):
        actor = bytearray(62)
        # Native facing -1 is the port's facing0 (left), not native0.
        for offset, value in ((2, -1), (4, x + 207), (6, row * 120 + 106),
                              (10, pose), (14, row), (16, int(67 <= pose < 79)),
                              (22, room), (26, 0), (40, 14)):
            put_actor(actor, offset, value)
        self.cpu.mem_write(self.A5 - 0x5056, bytes(actor))
        self.call(4, 0x2a72)
        self.call(3, 0x0ac8)
        self.call(4, 0x5cbc)
        # Convert the original left-facing GetCharEdges width+1 rectangle
        # back to the port's inclusive sprite edges, without its decoder.
        bounds = (self.word(-0x3564) - 207, self.word(-0x356c),
                  self.word(-0x3566) - 207 - 2, row * 120 + 106
                  + struct.unpack_from('>h', self.frame_data, pose * 10 + 6)[0])
        self.call(4, 0x4e34)
        self.responses = []
        self.call(4, 0x54da)
        verify_frames(self)
        return bounds, list(self.responses)


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    kid_bytes = (forks / 'Kid.rsrc.bin').read_bytes()
    prince_bytes = (forks / 'Prince.rsrc.bin').read_bytes()
    prince = parse_resource_fork(prince_bytes)
    machine = NativeVerticalJumpContact(parse_resource_fork(executable), parse_resource_fork(kid_bytes))
    sequence = prince['SEQS'][14]['data']
    words = struct.unpack('>' + 'h' * (len(sequence) // 2), sequence)
    if words[:2] != (-7, 1) or words[2:13] != tuple(range(67, 78)) or words[13:16] != (-5, 13, 78):
        raise AssertionError('Unexpected original SEQS14 fixture')
    counts, traces = Counter(), []
    for number, room, row, x in SITES:
        original = prince['LEVL'][1999 + number]['data']
        if (struct.unpack_from('>H', original, 0x2186)[0] != 2
                or struct.unpack_from('>H', original, 0x218a)[0] != number):
            raise AssertionError('Wrong environment/level header')
        cell = row * 10 + (x + 17) // 51 - 1
        if struct.unpack_from('>H', original, (room - 1) * 60 + cell * 2)[0] != 4:
            raise AssertionError('Fixture does not have its expected gate')
        for phase in (0, 24, 60, 124, 180, 184):
            level = bytearray(original)
            struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, phase)
            machine.prepare(level, room, row)
            terrain = LevelMap(level)
            previous, previous_x, path = None, x, []
            for pose in (15, *range(67, 80)):
                at_x = x - 13 if pose >= 78 else x
                bounds, events = machine.sample(room, row, at_x, pose)
                if events:
                    raise AssertionError((number, room, row, x, phase, pose, events))
                if previous is not None:
                    state = SimpleNamespace(actor_type=0, source_sequence_id=14)
                    corrected = terrain.wall_correction(room - 1, previous_x, at_x, bounds, previous,
                                                         0, physical_row=row, state=state)
                    if corrected != at_x:
                        raise AssertionError(('port cancelled', number, room, row, phase, pose, corrected))
                    counts['port_comparisons'] += 1
                previous, previous_x = bounds, at_x
                counts['native_samples'] += 1
                path.append((pose, at_x, bounds[1]))
            if min(item[2] for item in path) != row * 120 - 18:
                raise AssertionError('Unexpected original jump apex')
            if (machine.level_bytes(len(level)) != level or machine.services
                    or bytes(machine.cpu.mem_read(0xb0000, 512)) != bytes(512)):
                raise AssertionError('Unexpected supplied service or resource/MOB mutation')
            traces.append(dict(level=number, room=room, row=row, gate_phase=phase, path=path))
    # Positive control: cross the front edge of a closed gate. The wall
    # behind it is cleared in this supplied synthetic level copy only.
    level = bytearray(prince['LEVL'][2011]['data'])
    struct.pack_into('>H', level, 2 * 60 + 9 * 2, 1)
    machine.prepare(level, 3, 0)
    previous, events = machine.sample(3, 0, 492, 15)
    if events:
        raise AssertionError(('control primer', events))
    bounds, events = machine.sample(3, 0, 483, 68)
    corrected = LevelMap(level).wall_correction(
        2, 492, 483, bounds, previous, 0, physical_row=0,
        state=SimpleNamespace(actor_type=0, source_sequence_id=14))
    if events != [('collide', corrected - 483, 0)] or corrected == 483:
        raise AssertionError(('real front contact lost', bounds, events, corrected))
    counts['control_native_samples'] = 2
    counts['control_port_comparisons'] = 1
    return dict(counts=dict(counts), mismatches=0, front_contact_control=events,
                traces=traces, executable_sha256=hashlib.sha256(executable).hexdigest(),
                kid_sha256=hashlib.sha256(kid_bytes).hexdigest(),
                prince_sha256=hashlib.sha256(prince_bytes).hexdigest(), scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(report['counts'], 'front-contact control:', report['front_contact_control'])
