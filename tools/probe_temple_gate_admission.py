"""Compare native gate admission with independent height and real Kid-bound models."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_kid_frames import kid_frame_reference, verify_frames
from tools.probe_temple_slide_rock_update import actor_word
from tools.probe_temple_sprite_bounds import (
    BOUND_WORDS, CELL_WORDS, NativeTempleSpriteBounds, bounds_reference,
    drawing_reference, shape_sizes,
)


def admission_reference(actor, foreground, environment=2):
    """4:5b0e returns blocked, not permitted; visible height is a signed word."""
    if len(actor) != 62 or not 0 <= foreground <= 65535 or environment not in (1, 2, 3, 4):
        raise ValueError('Expected a complete actor, unsigned foreground and known environment')
    if environment == 1:
        return int((foreground & 31) < 19)
    kind = actor_word(actor, 8)
    if kind == 1 or actor_word(actor, 40) == 68:
        return 0
    height = signed_word(actor_word(actor, 46) - actor_word(actor, 42))
    height = signed_word(height + {7: 46, 8: 33}.get(kind, 0))
    return int(2 * ((foreground & 255) // 4) + 11 < height + 13)


class NativeTempleGateAdmission(NativeTempleSpriteBounds):
    RANGES = dict(NativeTempleSpriteBounds.RANGES)
    RANGES[4] += ((0x5b0e, 0x5ba8),)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    kid_bytes = (directory / 'Kid.rsrc.bin').read_bytes()
    kid = parse_resource_fork(kid_bytes)
    frames, attachments, sizes = kid['FRAM'][25001]['data'], kid['AFRM'][25001]['data'], shape_sizes(kid)
    machine = NativeTempleGateAdmission(parse_resource_fork(executable), frames, attachments, sizes)
    counts, outcomes, digest = Counter(), Counter(), hashlib.sha256()
    level = prince['LEVL'][2009]['data']

    def compare(actor, foreground, environment, label):
        expected = admission_reference(actor, foreground, environment)
        machine.put_word(-0x34ae, foreground)
        before = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        actual = machine.call(4, 0x5b0e)
        after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        if actual != expected or after != before or machine.services:
            raise AssertionError(dict(label=label, actor=actor.hex(), foreground=foreground,
                                      actual=actual, expected=expected, environment=environment))
        counts[label] += 1
        outcomes[f'{label}:{actual}'] += 1
        digest.update(actor + struct.pack('>3H', foreground, environment, actual))

    # Every low byte, exceptional kinds/source, signed subtraction and addition.
    rectangles = ((0, 0), (0, 1), (0, 34), (0, 48), (0, 124), (0, 125),
                  (0, 32767), (0, -32768), (-32768, 32767), (32767, -32768))
    for environment in (1, 2, 3, 4):
        fixture = bytearray(level)
        struct.pack_into('>h', fixture, 0x2186, environment)
        machine.reset(fixture)
        for kind, source, (top, bottom), low in product((0, 1, 7, 8, 11), (9, 68), rectangles, range(256)):
            actor = bytearray(actor_fixture(1, 1, 4, -1, 2))
            for offset, value in ((8, kind), (40, source), (42, top), (46, bottom)):
                put_actor(actor, offset, value)
            machine.cpu.mem_write(machine.A5 - 0x5056, bytes(actor))
            foreground = low | (0x8100 if low & 1 else 0)
            compare(bytes(actor), foreground, environment, 'direct')
        if machine.level_bytes(len(fixture)) != fixture:
            raise AssertionError('Gate admission changed the supplied level')

    # Feed actual LoadFrame/SetupSword/GetCharEdges output into the real predicate.
    drawing = struct.pack('>10h', -1, 53, 59, -1, 2, 61, 67, 71, 73, 79)
    bounds, cells = (101, 103, 107, 109, 113, 127, 131), (137, 139, 149, 151)
    positions = ((400, 110), (400, 0), (200, 110), (740, 500))
    canaries = ((-0x50d2, bytes(range(62))), (-0x34b0, bytes(range(12))),
                (-0x448e, bytes(range(160))))
    for pose, facing, (x, y) in product(range(352), (-1, 0), positions):
        actor = bytearray(actor_fixture(1, 1, 4, facing, 2))
        for offset, value in ((4, x), (6, y), (10, pose), (26, 0), (40, 9)):
            put_actor(actor, offset, value)
        loaded = kid_frame_reference(actor, frames, attachments)
        drawn = drawing_reference(loaded['actor'], loaded['metadata'], drawing)
        expected = bounds_reference(loaded['actor'], loaded['metadata'], drawn, sizes, bounds, cells,
                                    loaded['remainder'])
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(actor))
        machine.cpu.mem_write(machine.A5 - 0x34c6, drawing)
        for offset, data in canaries:
            machine.cpu.mem_write(machine.A5 + offset, data)
        for offsets, values in ((BOUND_WORDS, bounds), (CELL_WORDS, cells)):
            for offset, value in zip(offsets, values):
                machine.put_word(offset, value)
        machine.call(4, 0x2a72)
        machine.call(3, 0x0ac8)
        machine.call(4, 0x5cbc)
        actual = dict(actor=bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)),
                      bounds=tuple(machine.word(o) for o in BOUND_WORDS),
                      cells=tuple(machine.word(o) for o in CELL_WORDS),
                      remainder=machine.word(-0x481c), services=machine.bound_events)
        if (actual != expected or bytes(machine.cpu.mem_read(machine.A5 - 0x34c6, 20)) != drawn
                or bytes(machine.cpu.mem_read(machine.A5 - 0x521a, 18)) != loaded['metadata']):
            raise AssertionError(dict(inputs=(pose, facing, x, y), actual=actual, expected=expected))
        height = signed_word(actor_word(expected['actor'], 46) - actor_word(expected['actor'], 42))
        threshold = max(0, min(255, ((height + 3) // 2) * 4))
        for foreground in sorted({0, 255, max(0, threshold - 1), threshold, min(255, threshold + 1)}):
            compare(expected['actor'], foreground, 2, 'real_kid_bounds')
        for offset, data in canaries:
            # Only the supplied foreground word is permitted to change in the cache.
            current = bytes(machine.cpu.mem_read(machine.A5 + offset, len(data)))
            if offset == -0x34b0:
                current = current[:2] + data[2:4] + current[4:]
            if current != data:
                raise AssertionError('Unrelated actor/cache/bank canary changed')
        if machine.level_bytes(len(level)) != level:
            raise AssertionError('Bound/predicate chain changed level bytes')
        verify_frames(machine)
    return dict(comparisons=sum(counts.values()), cases=dict(counts), outcomes=dict(outcomes), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                kid_sha256=hashlib.sha256(kid_bytes).hexdigest(), outputs_sha256=digest.hexdigest(),
                supplied=['Prepared Kid FRAM/AFRM/library handles and initial actor/drawing state',
                          'SHAP header dimensions and explicit half-open SectRect callback'],
                scope='Real4:5b0e with signed visible-rectangle height and environment controls; '
                      'real type0 frame/drawing/bounds composition. No cell lookup, contact response, '
                      'barrier caller, physical reachability, world loop or runtime changes.')


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
