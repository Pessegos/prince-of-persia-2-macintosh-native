"""Validate type0 frame metadata and supporting columns from original Kid resources."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules
from tools.probe_level7_sequence_selection import supporting_column
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_slide_rock_update import actor_word


FRAME_HANDLES, FRAME_DATA, ATTACHMENT_DATA = 0xd0000, 0xd1000, 0xd3000
FRAME_RANGES = {4: ((0x2a72, 0x2bcc), (0x3a72, 0x3a90), (0x3ad6, 0x3aea)), 5: ((0x48b0, 0x48dc),)}


def install_frames(machine, frames, attachments):
    if len(frames) % 10 or len(attachments) % 8 or len(frames) > 0x2000 or len(attachments) > 0x1000:
        raise ValueError('Expected bounded10-byte frame and8-byte attachment tables')
    machine.frame_data, machine.attachment_data = bytes(frames), bytes(attachments)
    machine.cpu.mem_write(FRAME_HANDLES, struct.pack('>II', FRAME_DATA, ATTACHMENT_DATA))
    machine.cpu.mem_write(FRAME_DATA, bytes(frames))
    machine.cpu.mem_write(ATTACHMENT_DATA, bytes(attachments))


def bind_frames(machine):
    for offset, handle in ((-0x347a, FRAME_HANDLES), (-0x347e, FRAME_HANDLES + 4),
                            (-0x3472, FRAME_HANDLES), (-0x3476, FRAME_HANDLES + 4)):
        machine.cpu.mem_write(machine.A5 + offset, struct.pack('>I', handle))


def verify_frames(machine):
    if (bytes(machine.cpu.mem_read(FRAME_HANDLES, 8)) != struct.pack('>II', FRAME_DATA, ATTACHMENT_DATA)
            or bytes(machine.cpu.mem_read(FRAME_DATA, len(machine.frame_data))) != machine.frame_data
            or bytes(machine.cpu.mem_read(ATTACHMENT_DATA, len(machine.attachment_data))) != machine.attachment_data):
        raise AssertionError('Original frame data or prepared frame handles modified')


def kid_frame_reference(actor, frames, attachments):
    if len(actor) != 62 or actor_word(actor, 8) != 0 or actor_word(actor, 2) not in (-1, 0):
        raise ValueError('Only complete type0 actors in the two native facings are bounded')
    pose = actor_word(actor, 10)
    if not 0 <= pose < len(frames) // 10:
        raise ValueError('Pose outside the prepared Kid frame bank')
    frame = frames[pose * 10:(pose + 1) * 10]
    index = struct.unpack_from('>h', frame, 2)[0]
    if not 0 <= index < len(attachments) // 8:
        raise ValueError('Attachment index outside the prepared bank')
    column, remainder = supporting_column(actor_word(actor, 4), actor_word(actor, 2), frame)
    working = bytearray(actor)
    put_actor(working, 12, column)
    return dict(actor=bytes(working), metadata=attachments[index * 8:(index + 1) * 8] + frame, remainder=remainder)


class NativeKidFrameSupport(NativeRules):
    RANGES, SUPPLIED = FRAME_RANGES, {}

    def __init__(self, program, frames, attachments):
        super().__init__(program)
        install_frames(self, frames, attachments)

    def reset(self, level):
        super().reset(level)
        bind_frames(self)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    kid_bytes = (directory / 'Kid.rsrc.bin').read_bytes()
    kid = parse_resource_fork(kid_bytes)
    frames = kid['FRAM'][25001]['data']
    if len(frames) != 3520:
        raise ValueError('Expected352 original Kid frames')
    counts, digest = Counter(), hashlib.sha256()
    saved, cache, bank = bytes(range(62)), bytes(range(12)), bytes((i * 19 + 7) % 256 for i in range(160))
    xs = (-32768, -1, 0, 21, 22, 23, 25, 26, 207, 249, 250, 257, 258, 259, 717, 32767)
    for attachment_id in (25001, 25201):
        attachments = kid['AFRM'][attachment_id]['data']
        machine = NativeKidFrameSupport(parse_resource_fork(executable), frames, attachments)
        for pose, facing, x in product(range(352), (-1, 0), xs):
            actor = bytearray(actor_fixture(3, 7, 123, facing, 2))
            for offset, value in ((4, x), (6, 777), (10, pose)):
                put_actor(actor, offset, value)
            expected = kid_frame_reference(actor, frames, attachments)
            machine.reset(resources['LEVL'][2009]['data'])
            machine.cpu.mem_write(machine.A5 - 0x5056, bytes(actor))
            machine.cpu.mem_write(machine.A5 - 0x50d2, saved)
            machine.cpu.mem_write(machine.A5 - 0x34b0, cache)
            machine.cpu.mem_write(machine.A5 - 0x448e, bank)
            machine.cpu.mem_write(machine.A5 - 0x521a, bytes(range(18)))
            machine.call(4, 0x2a72)
            if (bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != expected['actor']
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x521a, 18)) != expected['metadata']
                    or machine.word(-0x481c) != expected['remainder'] or machine.services
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != saved
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x34b0, 12)) != cache
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)) != bank
                    or machine.level_bytes(len(resources['LEVL'][2009]['data'])) != resources['LEVL'][2009]['data']):
                raise AssertionError(dict(inputs=(attachment_id, pose, facing, x), expected=expected,
                                          actor=struct.unpack('>31h', machine.cpu.mem_read(machine.A5 - 0x5056, 62)),
                                          remainder=machine.word(-0x481c)))
            verify_frames(machine)
            counts[f'AFRM{attachment_id}'] += 1
            digest.update(expected['actor'] + expected['metadata'] + struct.pack('>h', expected['remainder']))
    return dict(cases=dict(counts), comparisons=sum(counts.values()), mismatches=0, outputs_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(), kid_sha256=hashlib.sha256(kid_bytes).hexdigest(),
                frame_sha256=hashlib.sha256(frames).hexdigest(),
                attachment_sha256={str(n): hashlib.sha256(kid['AFRM'][n]['data']).hexdigest() for n in (25001, 25201)},
                supplied_services=[],
                scope='Actual type0 LoadFrame4:2a72/2a8e, AddCharX/GetFCharX/GetCharCol and signed DIVS '
                      'with original352 Kid frames and two separately supplied AFRM bindings. Prepared handles '
                      'installed, no Resource Manager selection policy. No GetCharEdges, shape dimensions/rendering, '
                      'foot Y/row calculation, actor animation, physical reachability, full FrameAdv or runtime changes.')


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
