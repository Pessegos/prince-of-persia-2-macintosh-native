"""Recover original GroundBump with real sequence execution and Kid frame reload.

Type0 actor, SEQS2/45/229 handles and Kid FRAM/AFRM binding are prepared inputs.
JumpSeq, AnimChar, relative movement and LoadFrame/supporting column execute.
Resource Manager, hGetSequence and Memory Manager handle traps
are supplied. No ShapeBounds, collision admission, full response caller,
physical reachability, sound playback or complete FrameAdv/gameplay.
"""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules
from tools.probe_temple_gate_actor_clip import NativeGateActorClip, put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_kid_frames import (
    FRAME_RANGES, bind_frames, install_frames, kid_frame_reference, verify_frames,
)
from tools.probe_temple_slide_rock_update import actor_word


def bump_clip_reference(actor, sequences, *, floating=False):
    """One-pose interpreter; -10 links only while floating and is not audio."""
    working = bytearray(actor)
    sequence, cursor = actor_word(actor, 38), actor_word(actor, 36)
    events = [('animate', sequence, cursor), ('sequence', sequence),
              ('handle', 'HGetState'), ('handle', 'HLock')]
    for _ in range(12):
        if sequence not in sequences or not 0 <= cursor < len(sequences[sequence]):
            raise ValueError('Unprepared first-pose clip')
        op = sequences[sequence][cursor]
        cursor += 1
        put_actor(working, 36, cursor)
        if op >= 0:
            put_actor(working, 10, op)
            events.append(('handle', 'HSetState'))
            return dict(actor=bytes(working), events=events)
        if op not in (-7, -6, -5, -10):
            raise ValueError(f'Opcode outside the bounded bump slice:{op}')
        value = sequences[sequence][cursor]
        cursor += 1
        put_actor(working, 36, cursor)
        if op == -7:
            put_actor(working, 16, value)
        elif op == -6:
            put_actor(working, 6, actor_word(working, 6) + value)
        elif op == -5:
            put_actor(working, 4, actor_word(working, 4)
                      + (value if actor_word(working, 2) == 0 else -value))
        elif floating:
            sequence, cursor = value, 0
            put_actor(working, 38, sequence)
            put_actor(working, 36, 0)
            events.extend((('handle', 'HSetState'), ('sequence', sequence),
                           ('handle', 'HGetState'), ('handle', 'HLock')))
    raise ValueError('Bounded bump slice did not produce a pose')


def ground_bump_reference(actor, sequences, frames, attachments, *, available=True, floating=False):
    if len(actor) != 62 or actor_word(actor, 8) != 0 or actor_word(actor, 2) not in (-1, 0):
        raise ValueError('Expected a complete type0 actor')
    working, events = bytearray(actor), []
    put_actor(working, 4, actor_word(actor, 4) + (10 if actor_word(actor, 2) == -1 else -10))
    if actor_word(actor, 16) == 4:
        put_actor(working, 18, 0)
    else:
        events.append(('resource', 45))
        if available:
            for offset, value in ((36, 0), (38, 45), (40, 45)):
                put_actor(working, offset, value)
        clip = bump_clip_reference(bytes(working), sequences, floating=floating)
        working, events = bytearray(clip['actor']), events + clip['events']
    mark = 1
    loaded = kid_frame_reference(bytes(working), frames, attachments)
    events.append(('frame',))
    return dict(actor=loaded['actor'], metadata=loaded['metadata'], remainder=loaded['remainder'],
                mark=mark, events=events)


class NativeTempleGroundBump(NativeRules):
    RANGES = dict(FRAME_RANGES)
    RANGES[4] += ((0x2c0c, 0x3050), (0x305e, 0x308a), (0x5868, 0x589c), (0x5a70, 0x5a7e))
    RANGES[6] = ((0x0006, 0x0098),)
    SUPPLIED = {}

    def __init__(self, program, sequences, frames, attachments):
        super().__init__(program)
        install_frames(self, frames, attachments)
        self.sequences = {}
        pointer = 0xc2000
        for i, (number, data) in enumerate(sorted(sequences.items())):
            handle = 0xc0000 + i * 4
            self.sequences[number] = (handle, pointer, data)
            self.cpu.mem_write(handle, struct.pack('>I', pointer))
            self.cpu.mem_write(pointer, data)
            pointer += len(data)

    def reset(self, level):
        super().reset(level)
        bind_frames(self)
        self.events, self.available = [], True

    def return_value(self, value):
        stack = self.cpu.reg_read(self.registers['a7'])
        self.cpu.reg_write(self.registers['d0'], value)
        self.cpu.reg_write(self.registers['a7'], stack + 4)
        self.cpu.reg_write(self.registers['pc'], struct.unpack('>I', self.cpu.mem_read(stack, 4))[0])

    def dispatch(self, cpu, address, size, user):
        stack = cpu.reg_read(self.registers['a7'])
        if address in (self.address(17, 0x330e), self.address(4, 0x3098)):
            if address == self.address(17, 0x330e):
                kind, number = struct.unpack('>4sh', cpu.mem_read(stack + 4, 6))
                if (kind, number) != (b'SEQS', 45):
                    raise AssertionError('Unexpected GroundBump sequence lookup')
                self.events.append(('resource', number))
                exists = self.available
            else:
                number = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
                self.events.append(('sequence', number))
                exists = True
            self.return_value(self.sequences[number][0] if exists else 0)
            return
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        if segment == 4 and offset in NativeGateActorClip.HANDLE_TRAPS:
            name, opcode = NativeGateActorClip.HANDLE_TRAPS[offset]
            if bytes(cpu.mem_read(address, 2)) != opcode:
                raise AssertionError('Unexpected handle trap opcode')
            self.events.append(('handle', name))
            cpu.reg_write(self.registers['d0'], 0)
            cpu.reg_write(self.registers['pc'], address + 2)
            return
        if address == self.address(4, 0x2c0c):
            self.events.append(('animate', self.word(-0x5030), self.word(-0x5032)))
        elif address == self.address(4, 0x2a72):
            self.events.append(('frame',))
        super().dispatch(cpu, address, size, user)

    def verify_resources(self):
        verify_frames(self)
        for handle, pointer, data in self.sequences.values():
            if (bytes(self.cpu.mem_read(handle, 4)) != struct.pack('>I', pointer)
                    or bytes(self.cpu.mem_read(pointer, len(data))) != data):
                raise AssertionError('Sequence fixture was modified')


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    kid = parse_resource_fork((forks / 'Kid.rsrc.bin').read_bytes())
    frames = kid['FRAM'][25001]['data']
    raw = {n: prince['SEQS'][n]['data'] for n in (2, 45, 229)}
    sequences = {n: struct.unpack('>' + str(len(data) // 2) + 'h', data) for n, data in raw.items()}
    counts, outcomes, digest = Counter(), Counter(), hashlib.sha256()
    for attachment_id in (25001, 25201):
        attachments = kid['AFRM'][attachment_id]['data']
        machine = NativeTempleGroundBump(parse_resource_fork(executable), raw, frames, attachments)
        level = prince['LEVL'][2009]['data']
        for pose, facing, mode, x, available, floating in product(range(352), (-1, 0), (0, 4),
                (-32768, 22, 460, 32767), (False, True), (False, True)):
            actor = bytearray(actor_fixture(1, 1, 4, facing, mode))
            for offset, value in ((4, x), (6, 226), (8, 0), (10, pose), (18, 5), (20, -4),
                                  (28, -1), (30, 3), (36, 0), (38, 2), (40, 2)):
                put_actor(actor, offset, value)
            machine.reset(level)
            machine.available = available
            machine.cpu.mem_write(machine.A5 - 0x5056, bytes(actor))
            machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(range(62)))
            machine.cpu.mem_write(machine.A5 - 0x448e, bytes(range(160)))
            machine.cpu.mem_write(machine.A5 - 0x34b0, bytes(range(12)))
            machine.cpu.mem_write(machine.A5 - 0x521a, bytes(range(18)))
            machine.put_word(-0x481c, 79)
            machine.put_word(-0x4f9e, 73)
            machine.put_word(-0x4fa6, int(floating))
            expected = ground_bump_reference(bytes(actor), sequences, frames, attachments,
                                             available=available, floating=floating)
            before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
            machine.call(4, 0x5868)
            before[len(machine.data) - 0x5056:len(machine.data) - 0x5056 + 62] = expected['actor']
            before[len(machine.data) - 0x521a:len(machine.data) - 0x521a + 18] = expected['metadata']
            for offset, name in ((-0x481c, 'remainder'), (-0x4f9e, 'mark')):
                struct.pack_into('>h', before, len(machine.data) + offset, expected[name])
            after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
            if (after != before or machine.events != expected['events'] or machine.services
                    or machine.level_bytes(len(level)) != level):
                raise AssertionError(dict(inputs=(attachment_id, pose, facing, mode, x, available, floating),
                    expected=expected, events=machine.events, changed=[(hex(i - len(machine.data)), a, b)
                    for i, (a, b) in enumerate(zip(before, after)) if a != b]))
            machine.verify_resources()
            counts[f'AFRM{attachment_id}'] += 1
            outcomes[f'mode{mode}:available{available}'] += 1
            digest.update(expected['actor'] + expected['metadata'] + struct.pack('>h', expected['remainder']))
            digest.update(json.dumps(expected['events']).encode('ascii'))
    return dict(comparisons=dict(counts), outcomes=dict(outcomes), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                outputs_sha256=digest.hexdigest(), supplied=['SEQS45 Resource Manager present/missing',
                'hGetSequence prepared handles', 'HGetState/HLock/HSetState'], scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
