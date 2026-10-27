"""Recover unarmed4:589e through actual alignment, animation and Kid reload.

Type0 actor and caller admission are supplied. Armed reactions, Collide's
outer correction/tile/rock decisions, wall spacing, body generation and full
FrameAdv remain excluded. Resource/Memory Manager services and original
SEQS/FRAM/AFRM handle bindings are prepared explicitly; animation executes.
"""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_ground_bump import (
    NativeTempleGroundBump, bump_clip_reference, ground_bump_reference,
)
from tools.probe_temple_kid_frames import kid_frame_reference
from tools.probe_temple_slide_rock_update import actor_word


def air_collision_reference(actor, sequences, frames, attachments, *, available=True,
                            floating=False, metadata=bytes(range(18)), remainder=79, mark=73):
    if (len(actor) != 62 or actor_word(actor, 8) != 0 or actor_word(actor, 26) != 0
            or actor_word(actor, 2) not in (-1, 0)):
        raise ValueError('Expected a complete unarmed type0 actor')
    row, y = actor_word(actor, 14), actor_word(actor, 6)
    if row * 120 + 106 - y >= 30:
        result = ground_bump_reference(actor, sequences, frames, attachments,
                                       available=available, floating=floating)
        return dict(result, events=[('ground',)] + result['events'])
    working, events = bytearray(actor), [('align',)]
    #31fa's -33 applies to actor TYPES7/8, not movement modes7/8.
    put_actor(working, 6, row * 120 + 106)

    def move(dx):
        put_actor(working, 4, actor_word(working, 4) + (dx if actor_word(working, 2) == 0 else -dx))

    def result(load=False, changed_mark=mark):
        if load:
            loaded = kid_frame_reference(bytes(working), frames, attachments)
            return dict(actor=loaded['actor'], metadata=loaded['metadata'], remainder=loaded['remainder'],
                        mark=changed_mark, events=events + [('frame',)])
        return dict(actor=bytes(working), metadata=metadata, remainder=remainder, mark=changed_mark, events=events)

    # The signed50 threshold is checked before ALIVE or pending health.
    if actor_word(working, 20) >= 50:
        move(-17)
        return result(load=True)
    put_actor(working, 20, 0)
    if actor_word(working, 28) == 0:
        return result()
    pose = actor_word(working, 10) & 65535
    if 246 <= pose <= 261:
        move(-5)
        put_actor(working, 24, 0)
        put_actor(working, 16, 0)
        selected = 121
    elif actor_word(working, 30) + actor_word(working, 34) > 0:
        selected = 46 if pose in (24, 25, 40, 41, 42) or 102 <= pose <= 106 else 47
    else:
        return result()
    events.append(('resource', selected))
    if available:
        for offset, value in ((36, 0), (38, selected), (40, selected)):
            put_actor(working, offset, value)
    clip = bump_clip_reference(bytes(working), sequences, floating=floating)
    working = bytearray(clip['actor'])
    events.extend(clip['events'])
    return result(load=True, changed_mark=1)


class NativeTempleAirCollision(NativeTempleGroundBump):
    RANGES = dict(NativeTempleGroundBump.RANGES)
    RANGES[4] += ((0x31fa, 0x3228), (0x589e, 0x5916), (0x59b6, 0x5a60))

    def dispatch(self, cpu, address, size, user):
        stack = cpu.reg_read(self.registers['a7'])
        if address in (self.address(17, 0x330e), self.address(4, 0x3098)):
            if address == self.address(17, 0x330e):
                kind, number = struct.unpack('>4sh', cpu.mem_read(stack + 4, 6))
                if kind != b'SEQS' or number not in (45, 46, 47, 121):
                    raise AssertionError('Unexpected air-response resource request')
                self.events.append(('resource', number))
                available = self.available
            else:
                number = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
                self.events.append(('sequence', number))
                available = True
            self.return_value(self.sequences[number][0] if available else 0)
            return
        if address == self.address(4, 0x31fa):
            self.events.append(('align',))
        elif address == self.address(4, 0x5868):
            self.events.append(('ground',))
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    kid = parse_resource_fork((forks / 'Kid.rsrc.bin').read_bytes())
    raw = {number: prince['SEQS'][number]['data'] for number in (2, 45, 46, 47, 121, 229)}
    sequences = {number: struct.unpack('>' + str(len(data) // 2) + 'h', data) for number, data in raw.items()}
    frames = kid['FRAM'][25001]['data']
    level = prince['LEVL'][2009]['data']
    counts, outcomes, digest = Counter(), Counter(), hashlib.sha256()
    for attachment_id in (25001, 25201):
        attachments = kid['AFRM'][attachment_id]['data']
        machine = NativeTempleAirCollision(parse_resource_fork(executable), raw, frames, attachments)

        def check(label, *, pose=15, facing=0, vy=49, available=True, floating=False,
                  row=1, mode=0, height=0, x=460, alive=-1, hp=3, pending=0):
            actor = bytearray(actor_fixture(1, row, 4, facing, mode))
            for offset, value in ((4, x), (6, row * 120 + 106 - height), (8, 0), (10, pose),
                                  (18, 5), (20, vy), (26, 0), (28, alive), (30, hp), (34, pending),
                                  (36, 0), (38, 2), (40, 2)):
                put_actor(actor, offset, value)
            actor = bytes(actor)
            expected = air_collision_reference(actor, sequences, frames, attachments,
                                               available=available, floating=floating)
            machine.reset(level)
            machine.available = available
            machine.cpu.mem_write(machine.A5 - 0x5056, actor)
            machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(range(62)))
            machine.cpu.mem_write(machine.A5 - 0x448e, bytes(range(160)))
            machine.cpu.mem_write(machine.A5 - 0x34b0, bytes(range(12)))
            machine.cpu.mem_write(machine.A5 - 0x521a, bytes(range(18)))
            machine.put_word(-0x481c, 79)
            machine.put_word(-0x4f9e, 73)
            machine.put_word(-0x4fa6, int(floating))
            before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
            machine.call(4, 0x589e, (facing,))
            before[len(machine.data) - 0x5056:len(machine.data) - 0x5056 + 62] = expected['actor']
            before[len(machine.data) - 0x521a:len(machine.data) - 0x521a + 18] = expected['metadata']
            for offset, name in ((-0x481c, 'remainder'), (-0x4f9e, 'mark')):
                struct.pack_into('>h', before, len(machine.data) + offset, expected[name])
            after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
            if (after != before or machine.events != expected['events'] or machine.services
                    or machine.level_bytes(len(level)) != level):
                raise AssertionError(dict(label=label, attachment=attachment_id, actor=actor.hex(),
                    expected=expected, events=machine.events, changed=[(hex(i - len(machine.data)), a, b)
                    for i, (a, b) in enumerate(zip(before, after)) if a != b]))
            machine.verify_resources()
            counts[f'{attachment_id}:{label}'] += 1
            outcomes[f"source{actor_word(expected['actor'], 40)}:mark{expected['mark']}"] += 1
            digest.update(expected['actor'] + expected['metadata'] + struct.pack('>2h', expected['remainder'], expected['mark']))
            digest.update(json.dumps(expected['events']).encode('ascii'))

        for pose, facing, vy, available in product(range(352), (-1, 0), (-1, 49, 50), (False, True)):
            check('all_pose_thresholds', pose=pose, facing=facing, vy=vy, available=available)
        for row, mode, vy, facing in product((-1, 0, 1, 2, 3), (0, 7, 8), (49, 50), (-1, 0)):
            check('alignment_modes', row=row, mode=mode, vy=vy, facing=facing)
        for pose, (hp, pending), facing in product((23, 24, 25, 26, 39, 40, 41, 42, 43, 101, 102, 106, 107, 245, 246, 261, 262),
                ((3, 0), (1, -1), (0, 1), (32767, 1), (-32768, -1), (0, 0)), (-1, 0)):
            check('pose_health_edges', pose=pose, hp=hp, pending=pending, facing=facing)
        for height, mode, facing, available, floating in product((29, 30, 31), (0, 4), (-1, 0), (False, True), (False, True)):
            check('ground_redirect', height=height, mode=mode, facing=facing, available=available, floating=floating)
        for x, facing, mode, vy, alive, pose in product((-32768, 22, 460, 32767), (-1, 0), (0, 7, 8), (-1, 49, 50), (0, -1), (24, 246)):
            check('word_alive_controls', x=x, facing=facing, mode=mode, vy=vy, alive=alive, pose=pose)
    return dict(comparisons=dict(counts), outcomes=dict(outcomes), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(), outputs_sha256=digest.hexdigest(),
                supplied=['unarmed type0 actor and caller admission', 'original Kid FRAM25001 and AFRM25001/25201',
                          'SEQS Resource Manager present/missing', 'prepared sequence handles',
                          'HGetState/HLock/HSetState'], scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
