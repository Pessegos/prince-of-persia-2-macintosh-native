"""Execute the original special-actor frame loader against Head.rsrc data."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


def head_frame_index(actor, pose, frame_count=141):
    if actor not in (7, 8, 11):
        raise ValueError('Only the tested head and serpent actor types are supported')
    if type(pose) is not int or not 149 <= pose < 149 + frame_count:
        raise ValueError('Pose outside the tested Head FRAM domain')
    return pose - 149 + (43 if actor == 8 and pose <= 181 else 0)


class NativeHeadFrames(NativeRules):
    RANGES = {4: ((0x2a8e, 0x2bac),)}
    SUPPLIED = {}
    HANDLES, FRAMES, ATTACHMENTS = 0xb0000, 0xb1000, 0xb2000

    def __init__(self, program, head):
        super().__init__(program)
        self.cpu.mem_write(self.HANDLES, struct.pack('>II', self.FRAMES, self.ATTACHMENTS))
        self.cpu.mem_write(self.FRAMES, head['FRAM'][750]['data'])
        self.cpu.mem_write(self.ATTACHMENTS, head['AFRM'][750]['data'])

    def reset(self, level):
        super().reset(level)
        self.cpu.mem_write(self.A5 - 0x347a, struct.pack('>I', self.HANDLES))
        self.cpu.mem_write(self.A5 - 0x347e, struct.pack('>I', self.HANDLES + 4))

    def frame_bytes(self):
        return bytes(self.cpu.mem_read(self.A5 - 0x5212, 10))

    def attachment_bytes(self):
        return bytes(self.cpu.mem_read(self.A5 - 0x521a, 8))


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(program_bytes)
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    head_bytes = (directory / 'Head.rsrc.bin').read_bytes()
    head = parse_resource_fork(head_bytes)
    frame_data, attachments = head['FRAM'][750]['data'], head['AFRM'][750]['data']
    if len(frame_data) % 10 or len(attachments) % 8:
        raise ValueError('Misaligned Head frame/attachment data')
    machine = NativeHeadFrames(program, head)
    counts = Counter()
    digest = hashlib.sha256()
    for actor in (7, 8, 11):
        for pose in range(149, 149 + len(frame_data) // 10):
            index = head_frame_index(actor, pose, len(frame_data) // 10)
            expected = frame_data[index * 10:(index + 1) * 10]
            if len(expected) != 10:
                raise ValueError('Reference frame index outside resource')
            attachment = struct.unpack_from('>h', expected, 2)[0]
            expected_attachment = attachments[attachment * 8:(attachment + 1) * 8]
            if len(expected_attachment) != 8:
                raise ValueError('Reference attachment index outside resource')
            machine.reset(prince['LEVL'][2006]['data'])
            machine.put_word(-0x504e, actor)
            machine.put_word(-0x504c, pose)
            machine.call(4, 0x2a8e)
            if (machine.frame_bytes() != expected
                    or machine.attachment_bytes() != expected_attachment):
                raise AssertionError(f'Native frame mismatch: actor {actor}, pose {pose}')
            counts[str(actor)] += 1
            digest.update(machine.frame_bytes() + machine.attachment_bytes())
    base = struct.unpack_from('>H', head['SHPL'][750]['data'])[0]
    shape_ids = {base + struct.unpack_from('>h', frame_data, index)[0]
                 for index in range(0, len(frame_data), 10)
                 if struct.unpack_from('>h', frame_data, index)[0] >= 0}
    missing = sorted(shape_ids - set(head['SHAP']))
    if missing:
        raise AssertionError(f'Head frames reference absent shapes: {missing}')
    return dict(
        level=7, cases=dict(counts), mismatches=0,
        frame_records=len(frame_data) // 10, attachment_records=len(attachments) // 8,
        referenced_shapes=len(shape_ids), missing_shapes=missing,
        outputs_sha256=digest.hexdigest(), head_sha256=hashlib.sha256(head_bytes).hexdigest(),
        executable_sha256=hashlib.sha256(program_bytes).hexdigest(), supplied_services=[],
        scope=('Full original LoadFrame 4:2a8e and actual FRAM/AFRM 750. '
               'All poses 149..289 for actor types 7/8/11 are supplied directly. '
               'Resource handles are installed by the harness. No sequence reachability, '
               'palette selection, shape rasterization, animation or controller claim.'),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
