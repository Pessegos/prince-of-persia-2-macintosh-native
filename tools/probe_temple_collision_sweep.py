"""Recover the native4:536a row sweep into ten-word room tags/overlap masks.

ReadCell, barrier classification and both span-edge helpers execute without
endpoint stubs. Span limits, row, actor room, body edges/height, bars flag and
old output tables are supplied. No CheckBarr history/min/max generation,
sliding-rock overlay, ShapeBounds, gate response or outer FrameAdv.
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
from tools.probe_temple_gate_distance import NativeTempleGateDistance
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_soft_distance import FACE_OFFSETS, BACK_OFFSETS
from tools.probe_temple_gate_standing import COLD_CACHE, StandingCellReader
from tools.probe_temple_slide_rock_update import actor_word


def sweep_reference(actor, row, first, last, edges, tags, masks, reader, *, height=74, bars=0):
    if (len(actor) != 62 or len(tags) != 10 or len(masks) != 10 or len(edges) != 2
            or not -2 <= first <= 11 or not -2 <= last <= 11 or not -1 <= row <= 3):
        raise ValueError('Outside the bounded row-sweep domain')
    result_tags, result_masks = list(tags), list(masks)
    anchor = signed_word(229 + first * 51)
    room = actor_word(actor, 22)

    def category(kind):
        if kind == 2:
            return 3 if reader.cache[1] & 255 < 3 and bars else 4
        if kind in (20, 25):
            return 4
        if kind == 7:
            return 2 if height <= 34 else 4
        return {4: 1, 12: 6}.get(kind, 0)

    for column in range(first, last + 1):
        kind = reader.read(room, column, row)
        barrier = category(kind)
        left = signed_word(anchor + FACE_OFFSETS[barrier]) if barrier else 921
        kind = reader.read(room, column, row)
        barrier = category(kind)
        right = signed_word(anchor + 50 - BACK_OFFSETS[barrier]) if barrier else 0
        value = (0x0f if left < edges[1] else 0) | (0xf0 if right > edges[0] else 0)
        normalized = reader.cache[4]
        if not 0 <= normalized <= 9:
            raise ValueError('Sweep output index outside its ten-word bank')
        result_tags[normalized] = reader.cache[3] & 65535
        result_masks[normalized] = value
        anchor = signed_word(anchor + 51)
    return dict(tags=result_tags, masks=result_masks, anchor=anchor)


class NativeTempleCollisionSweep(NativeTempleGateDistance):
    RANGES = dict(NativeTempleGateDistance.RANGES)
    RANGES[4] += ((0x536a, 0x5408), (0x541a, 0x546c), (0x547c, 0x54ca))


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    levels = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL']
    machine = NativeTempleCollisionSweep(parse_resource_fork(executable))
    counts, values, digest = Counter(), Counter(), hashlib.sha256()
    machine.reset(levels[2009]['data'])
    if machine.word(-0x4b6c) != 921:
        raise AssertionError('Original empty left-edge sentinel differs')
    if tuple(machine.word(-0x4b88 + col * 2) for col in range(-2, 12)) != tuple(
            207 + col * 51 for col in range(-2, 12)):
        raise AssertionError('Original column anchors differ')

    def check(level, actor, row, first, last, edges, height, bars, label):
        tags = [0xa000 + col for col in range(10)]
        masks = [0xb000 + col for col in range(10)]
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, actor)
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(range(62)))
        machine.cpu.mem_write(machine.A5 - 0x448e, bytes(range(160)))
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', *COLD_CACHE))
        for offset, value in ((-0x4fc2, actor_word(actor, 22)), (-0x3580, first),
                              (-0x3582, last), (-0x3564, edges[0]), (-0x3566, edges[1]),
                              (-0x3560, height), (-0x36bc, bars), (-0x35fc, 73)):
            machine.put_word(offset, value)
        for offset, bank in ((-0x35aa, tags), (-0x354a, masks)):
            machine.cpu.mem_write(machine.A5 + offset, struct.pack('>10H', *bank))
        reader = StandingCellReader(level, actor_word(actor, 22))
        expected = sweep_reference(actor, row, first, last, edges, tags, masks, reader,
                                    height=height, bars=bars)
        before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        machine.call(4, 0x536a, arg_bytes=struct.pack('>hII', row,
                     machine.A5 - 0x35aa, machine.A5 - 0x354a))
        struct.pack_into('>10H', before, len(machine.data) - 0x35aa, *expected['tags'])
        struct.pack_into('>10H', before, len(machine.data) - 0x354a, *expected['masks'])
        struct.pack_into('>h', before, len(machine.data) - 0x35fc, expected['anchor'])
        struct.pack_into('>6h', before, len(machine.data) - 0x34b0, *reader.cache)
        if reader.pointer_room is not None:
            r = reader.pointer_room
            struct.pack_into('>II', before, len(machine.data) - 0x4824,
                             machine.LEVEL + 0x780 + (r - 1) * 120,
                             machine.LEVEL + (r - 1) * 60)
        after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        if (after != before or machine.services or machine.reads != reader.requests
                or machine.level_bytes(len(level)) != level):
            raise AssertionError(dict(label=label, row=row, first=first, last=last, edges=edges,
                expected=expected, reads=machine.reads, expected_reads=reader.requests,
                changed=[(hex(i - len(machine.data)), a, b)
                         for i, (a, b) in enumerate(zip(before, after)) if a != b]))
        counts[label] += 1
        values.update(expected['masks'])
        digest.update(actor + struct.pack('>3h20Hh6h', row, first, last,
                      *expected['tags'], *expected['masks'], expected['anchor'], *reader.cache))
    for number in range(10, 14):
        level = levels[1999 + number]['data']
        maximum = struct.unpack_from('>H', level, 0x2180)[0]
        for room, row, (first, last), edges, height, bars in product(
                range(1, maximum + 1), range(-1, 4), ((0, 9), (-2, 1), (8, 11), (5, 4)),
                ((230, 260), (430, 475), (680, 720)), (34, 74), (0, 1)):
            actor = actor_fixture(room, 1, 4, -1, 0)
            check(level, actor, row, first, last, edges, height, bars, 'declared_room_rows')
    original = levels[2009]['data']
    for kind, foreground, edges, height, bars in product(range(50), (0, 1, 184, 0x8100),
            ((473, 483), (472, 484), (483, 500), (450, 473), (483, 473),
             (-32768, 32767), (32767, -32768)), (34, 74), (0, 1)):
        level = bytearray(original)
        struct.pack_into('>H', level, 14 * 2, kind)
        struct.pack_into('>H', level, 0x780 + 14 * 4, foreground)
        actor = bytearray(actor_fixture(1, 1, 4, -1, 0))
        put_actor(actor, 8, 11)  # Sweep itself does not filter serpent actors.
        check(bytes(level), bytes(actor), 1, 4, 4, edges, height, bars, 'tile_and_boundary_controls')
    return dict(comparisons=dict(counts), mask_values=dict(values), mismatches=0,
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
