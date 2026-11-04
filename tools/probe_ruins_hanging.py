"""Check original ordinary clip tops and CheckFloor's falling-catch scheduling.

ClipChar runs through its shared body, stopping before environment hooks.
Shape dimensions, SectRect and visible-actor admission are supplied. The
CheckFloor probe executes its dispatcher with floor/Catch/Falling as sinks.
Neither slice is full animation, physics, rasterization or an input replay.
"""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.caverns import cavern_clip_top
from pop2.mac_resources import parse_resource_fork
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap, falling_catch_scheduled, floor_y
from tools.probe_level7_rules import NativeRules
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_sprite_bounds import NativeTempleSpriteBounds, shape_sizes


CLIP_RANGES = {3: ((0x4da6, 0x4f24),),
               4: ((0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x322a, 0x3262),
                   (0x4146, 0x43de), (0x4432, 0x4500)),
               5: ((0x0004, 0x0066),)}


class NativeOrdinaryClip(NativeTempleSpriteBounds):
    RANGES = {segment: NativeTempleSpriteBounds.RANGES.get(segment, ()) + CLIP_RANGES.get(segment, ())
              for segment in NativeTempleSpriteBounds.RANGES.keys() | CLIP_RANGES.keys()}
    SUPPLIED = {(4, 0x471e): 'visible_actor'}


class NativeCatchSchedule(NativeRules):
    RANGES = {5: ((0x1202, 0x127c),)}
    SUPPLIED = {(4, 0x35ba): 'floor', (4, 0x37ca): 'catch', (6, 0x00a6): 'falling'}


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    raw = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(raw)
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    kid = parse_resource_fork((directory / 'Kid.rsrc.bin').read_bytes())
    machine = NativeOrdinaryClip(program, kid['FRAM'][25001]['data'],
                                 kid['AFRM'][25001]['data'], shape_sizes(kid))
    count, digest, examples = 0, hashlib.sha256(), []
    poses = ((79, 0), (80, 3), *((pose, 2) for pose in range(87, 100)),
             *((pose, 1) for pose in range(135, 145)))
    for number, room, row, facing, (pose, mode), x in product(
            range(6, 10), (3, 7), (1, 2), (0, 1), poses, (108, 122, 230)):
        level = bytearray(prince['LEVL'][1999 + number]['data'])
        if struct.unpack_from('>3h', level, 0x2186)[::2] != (4, number):
            raise ValueError('Expected original Ruins header')
        if number == 6 and room == 3:
            for cell in (12, 13, 22, 23):
                struct.pack_into('>H', level, room * 60 + cell * 2, 0)
                struct.pack_into('>H', level, 0x780 + room * 120 + cell * 4, 3)
        actor = bytearray(62)
        for offset, value in ((2, 0 if facing else -1), (4, x + 207), (6, floor_y(row)),
                              (10, pose), (14, row), (16, mode), (22, room + 1),
                              (24, -1), (38, 210), (40, 210)):
            put_actor(actor, offset, value)
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(actor))
        machine.call(4, 0x2a72)
        machine.call(3, 0x0ac8)
        machine.call(4, 0x5cbc)
        top, left, bottom, right = struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x502c, 8))
        bounds = left, top, right - 1, bottom - 1
        state = SequenceState(210, action=pose, animation_state=mode, actor_type=0,
                              level_kind=4, facing=facing, target_x=x)
        clip = cavern_clip_top(LevelMap(level), room, row, state, bounds)
        machine.call(4, 0x4146, stop=(4, 0x43e2))
        actual = machine.word(-0x34bc)
        expected = max(0, top - 1, clip)
        if actual != expected or machine.level_bytes(len(level)) != level:
            raise AssertionError((number, room, row, facing, pose, x, bounds, actual, expected))
        if number == 6 and row == 2 and ((room, facing, x, pose) in
                ((3, 0, 122, 79), (3, 0, 122, 80), (3, 0, 122, 91), (7, 1, 230, 87))):
            examples.append(dict(room=room, facing=facing, pose=pose, x=x,
                                 bounds=bounds, clip_top=clip, native_top=actual))
        digest.update(struct.pack('>10h', number, room, row, facing, pose, x, *bounds))
        digest.update(struct.pack('>h', actual))
        count += 1

    schedule = NativeCatchSchedule(program)
    scheduled = 0
    level = prince['LEVL'][2005]['data']
    for mode, pose, velocity in product(range(10), (79, 80, 81, 91, 99, 101, 102, 105, 106, 107, 135), (0, 1)):
        schedule.reset(level)
        for offset, value in ((-0x504e, 0), (-0x5046, mode), (-0x504c, pose), (-0x5042, velocity)):
            schedule.put_word(offset, value)
        schedule.call(5, 0x1202)
        actual = bool(schedule.services['catch'] or schedule.services['falling'])
        state = SequenceState(99, action=pose, animation_state=mode, vertical_velocity=velocity)
        if actual != falling_catch_scheduled(state):
            raise AssertionError((mode, pose, velocity, schedule.services))
        digest.update(bytes((mode, pose, velocity, int(actual))))
        scheduled += 1
    if (directory / 'Prince of Persia 2.bin').read_bytes() != raw:
        raise AssertionError('Original executable changed')
    return dict(clip_cases=count, schedule_cases=scheduled, mismatches=0, examples=examples,
                executable_sha256=hashlib.sha256(raw).hexdigest(), outputs_sha256=digest.hexdigest(),
                supplied=['Original Kid frame/attachment bindings and SHAP header dimensions',
                          'SectRect and visible-actor admission (IsCharNonViewable returns zero)',
                          'Actor fixtures; level6 room3 loose cells12,13,22,23 cleared',
                          'CheckFloor floor/Catch/Falling endpoints are inert routing sinks'],
                exclusions=['ClipChar environment hooks after4:43e2, native rasterization and visibility',
                            'Non-player actors, entry/exit poses and full collision/animation/FrameAdv',
                            'Scheduling sinks do not execute Catch geometry or Falling'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
