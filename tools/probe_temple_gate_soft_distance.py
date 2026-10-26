"""Execute the temple's general4:5eae contact-distance selector.

Real ReadCell, barrier classification/geometry, signed column/remainder and
floor/space predicates run without supplied endpoints. Actor/body bounds,
cached frame dx/flags and visible-room slots are fixtures. No animation,
overlap-bank construction, floor physics or outer FrameAdv is executed.
"""

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
from tools.probe_temple_gate_admission import admission_reference
from tools.probe_temple_gate_distance import NEIGHBOR_SLOTS, NativeTempleGateDistance
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import COLD_CACHE, StandingCellReader
from tools.probe_temple_slide_rock_update import actor_word


FACE_OFFSETS = (0, 40, 0, -22, 3, 18, 8, 0, 16)
BACK_OFFSETS = (0, 0, 50, -22, 0, 0, 16, 0, 24)
SPACES = frozenset((0, 9, 27, 47, 49))
MOBILE = frozenset((11, 12, 13, 15, 23, 24, 26))


def soft_distance_reference(actor, reader, edges, metadata, view, neighbors,
                            *, height=74, anchor=73, remainder=79, bars=0, distance_kind=71):
    if (len(actor) != 62 or actor_word(actor, 2) not in (-1, 0) or len(edges) != 2
            or len(metadata) != 2 or len(neighbors) != 6 or bars not in (0, 1)):
        raise ValueError('Outside the bounded temple selector domain')
    room, column, row = (actor_word(actor, offset) for offset in (22, 12, 14))
    facing = actor_word(actor, 2)

    def category(kind):
        if kind == 2:
            return 3 if reader.cache[1] & 255 < 3 and bars else 4
        if kind in (20, 25):
            return 4
        if kind == 7:
            return 2 if height <= 34 else 4
        return {4: 1, 12: 6}.get(kind, 0)

    def face_distance(kind, col):
        nonlocal anchor
        if kind == 4 and not admission_reference(actor, reader.cache[1] & 65535, 2):
            return -1
        if not -2 <= col <= 11:
            raise ValueError('Native anchor table outside tested -2..11 domain')
        anchor = signed_word(229 + col * 51)
        if room != view:
            if room in neighbors[:3]:
                anchor = signed_word(anchor - 510)
            elif room in neighbors[3:]:
                anchor = signed_word(anchor + 510)
        barrier = category(kind)
        if not barrier:
            return -1
        if facing == -1:
            return signed_word(edges[0] - signed_word(anchor + 50 - BACK_OFFSETS[barrier]))
        return signed_word(signed_word(anchor + FACE_OFFSETS[barrier]) - edges[1])

    def foot_distance():
        nonlocal remainder
        dx, flags = metadata
        shift = signed_word(dx - (flags & 63))
        x = signed_word(actor_word(actor, 4) + (shift if facing == 0 else -shift))
        argument = signed_word(x - 22)
        # 5:48b8 extends first, then SUBQ.W changes only the low word.
        # For arguments0..3 the dividend is65532..65535, not-4..-1.
        dividend = argument - 4 + (65536 if 0 <= argument < 4 else 0)
        quotient = abs(dividend) // 51 * (-1 if dividend < 0 else 1)
        remainder = dividend - quotient * 51
        return signed_word(remainder if facing == -1 else 50 - remainder)

    def finish(distance, reason):
        return dict(distance=signed_word(distance), reason=reason, anchor=anchor, remainder=remainder)

    def barrier_result(distance):
        return finish(distance, 1) if distance < 51 else finish(42, 2)

    def sloped(kind):
        if kind == 24 and facing == -1:
            distance = foot_distance()
            return finish(distance + (-17 if column == reader.cache[4] else 34), distance_kind)
        if kind == 23 and facing == 0:
            distance = foot_distance()
            return finish(distance + (-33 if column == reader.cache[4] else 18), distance_kind)
        return finish(42, 2)

    kind = reader.read(room, column, row)
    if category(kind):
        distance = face_distance(kind, column)
        if distance >= 0:
            return barrier_result(distance)
    if kind in (23, 24):
        return sloped(kind)
    forward = column + (-1 if facing == -1 else 1)
    kind = reader.read(room, forward, row)
    if category(kind):
        distance = face_distance(kind, forward)
        if distance >= 0:
            return barrier_result(distance)
    if (kind in SPACES or kind in MOBILE or kind == 30) and kind not in (23, 24):
        return finish(foot_distance(), 0)
    if kind in (6, 22, 2, 34):
        distance = foot_distance()
        return finish(distance - 1, 0) if distance else finish(42, 2)
    if kind in (23, 24):
        return sloped(kind)
    return finish(42, 2)


class NativeTempleSoftDistance(NativeTempleGateDistance):
    RANGES = dict(NativeTempleGateDistance.RANGES)
    RANGES[3] += ((0x4de2, 0x4e32), (0x4eb2, 0x4f24))
    RANGES[4] += ((0x35a6, 0x35ba), (0x3a72, 0x3aca), (0x3ad6, 0x3afa), (0x5eae, 0x5ffc))
    RANGES[5] += ((0x48b0, 0x48de),)


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    levels = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL']
    machine = NativeTempleSoftDistance(parse_resource_fork(executable))
    counts, reasons, digest = Counter(), Counter(), hashlib.sha256()
    machine.reset(levels[2009]['data'])
    for offset, values in ((-0x3620, FACE_OFFSETS), (-0x360e, BACK_OFFSETS)):
        if tuple(machine.word(offset + 2 * index) for index in range(9)) != values:
            raise AssertionError('Original barrier offset table differs from the model')
    if tuple(machine.word(-0x4b88 + 2 * col) for col in range(-2, 12)) != tuple(
            207 + col * 51 for col in range(-2, 12)):
        raise AssertionError('Original column table differs from the model')

    def check(level, actor, edges, metadata, label, *, height=74, bars=0):
        room = actor_word(actor, 22)
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, actor)
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(range(62)))
        machine.cpu.mem_write(machine.A5 - 0x448e, bytes(range(160)))
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', *COLD_CACHE))
        for offset, value in ((-0x4fc2, room), (-0x35fc, 73), (-0x3576, 71),
                              (-0x481c, 79), (-0x3564, edges[0]), (-0x3566, edges[1]),
                              (-0x3560, height), (-0x520e, metadata[0]),
                              (-0x520a, metadata[1]), (-0x36bc, bars)):
            machine.put_word(offset, value)
        for offset in NEIGHBOR_SLOTS:
            machine.put_word(offset, 0)
        reader = StandingCellReader(level, room)
        expected = soft_distance_reference(actor, reader, edges, metadata, room, (0,) * 6,
                                           height=height, bars=bars)
        before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        actual = signed_word(machine.call(4, 0x5eae))
        struct.pack_into('>6h', before, len(machine.data) - 0x34b0, *reader.cache)
        for offset, name in ((-0x35fc, 'anchor'), (-0x3576, 'reason'), (-0x481c, 'remainder')):
            struct.pack_into('>h', before, len(machine.data) + offset, expected[name])
        if reader.pointer_room is not None:
            r = reader.pointer_room
            struct.pack_into('>II', before, len(machine.data) - 0x4824,
                             machine.LEVEL + 0x780 + (r - 1) * 120,
                             machine.LEVEL + (r - 1) * 60)
        after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        if (actual != expected['distance'] or after != before or machine.services
                or machine.reads != reader.requests or machine.level_bytes(len(level)) != level):
            raise AssertionError(dict(label=label, actor=actor.hex(), edges=edges, metadata=metadata,
                                      actual=actual, expected=expected, reads=machine.reads,
                                      expected_reads=reader.requests,
                                      changed=[(hex(i - len(machine.data)), a, b)
                                               for i, (a, b) in enumerate(zip(before, after)) if a != b]))
        counts[label] += 1
        reasons[str(expected['reason'])] += 1
        digest.update(actor + struct.pack('>10h', actual, expected['reason'], expected['anchor'],
                                         expected['remainder'], *reader.cache))

    for number in range(10, 14):
        level = levels[1999 + number]['data']
        maximum = struct.unpack_from('>H', level, 0x2180)[0]
        for room, cell, facing, (dx, flags), delta in product(
                range(1, maximum + 1), range(30), (-1, 0), ((0, 0), (8, 0x40), (-8, 0x7f)),
                (-25, 0, 51)):
            row, col = divmod(cell, 10)
            actor = bytearray(actor_fixture(room, row, col, facing, 0))
            x = 229 + col * 51 + delta
            for offset, value in ((4, x), (42, 20), (46, 94), (40, 9)):
                put_actor(actor, offset, value)
            check(level, bytes(actor), (x - 15, x + 15), (dx, flags), 'declared_room_cells')
    original = levels[2009]['data']
    for x, facing in product((22, 23, 24, 25, -32746, -32745, -32744, -32743), (-1, 0)):
        level = bytearray(original)
        for col, kind in ((4, 1), (3 if facing == -1 else 5, 0)):
            struct.pack_into('>H', level, (10 + col) * 2, kind)
        actor = bytearray(actor_fixture(1, 1, 4, facing, 0))
        for offset, value in ((4, x), (40, 9), (42, 20), (46, 94)):
            put_actor(actor, offset, value)
        check(bytes(level), bytes(actor), (signed_word(x - 15), signed_word(x + 15)),
              (0, 0), 'word_subtraction_boundaries')
    for here, ahead, facing, foreground, x, bars, height in product(
            (1, 4, 23, 24), (0, 1, 2, 4, 6, 7, 11, 12, 13, 15, 20, 22, 23, 24, 25, 26, 30, 34),
            (-1, 0), (0, 1, 96, 184, 0x8100), (26, 229, 460, -32768, 32767), (0, 1), (34, 74)):
        level = bytearray(original)
        front_col = 3 if facing == -1 else 5
        for col, kind in ((4, here), (front_col, ahead)):
            cell = 10 + col
            struct.pack_into('>H', level, cell * 2, kind)
            struct.pack_into('>H', level, 0x780 + cell * 4, foreground)
        actor = bytearray(actor_fixture(1, 1, 4, facing, 0))
        for offset, value in ((4, x), (42, 20), (46, 20 + height), (40, 9)):
            put_actor(actor, offset, value)
        check(bytes(level), bytes(actor), (signed_word(x - 15), signed_word(x + 15)),
              (8, 0x7f), 'tile_and_signed_controls', bars=bars, height=height)
    return dict(comparisons=dict(counts), distance_kinds=dict(reasons), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                outputs_sha256=digest.hexdigest(), supplied=[], scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
