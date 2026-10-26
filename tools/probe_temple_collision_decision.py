"""Recover CheckCollide1 selection/admission, alone and after real CheckBarr.

Actor/body, prior banks/row and displayed-room slots are supplied. ReadCell,
predicates, span geometry, history, three sweeps and empty-MOB rock queries
execute natively. Collide4:5738 is a recorded, no-op response boundary: no
movement/animation/damage response, nonempty rocks, ShapeBounds or FrameAdv.
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
from tools.probe_temple_collision_banks import NativeTempleCollisionBanks, banks_reference
from tools.probe_temple_collision_history import TABLES
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_admission import admission_reference
from tools.probe_temple_gate_distance import NEIGHBOR_SLOTS, adjusted_anchor_reference
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_soft_distance import FACE_OFFSETS, BACK_OFFSETS
from tools.probe_temple_gate_standing import COLD_CACHE, StandingCellReader
from tools.probe_temple_slide_rock_update import actor_word


def decision_reference(actor, edges, tags, hit_low, hit_high, reader, *, height=74,
                       bars=0, anchor=73, neighbors=(0,) * 6, view=None):
    if (len(actor) != 62 or actor_word(actor, 2) not in (-1, 0) or len(tags) != 10
            or any(not -1 <= hit <= 9 for hit in (hit_low, hit_high))):
        raise ValueError('Outside the bounded CheckCollide1 domain')
    events, rock_queries = [], []
    result = dict(events=events, rock_queries=rock_queries, anchor=anchor)
    kind, mode, pose = (actor_word(actor, o) for o in (8, 16, 10))
    if mode in (2, 6) or 135 <= (pose & 65535) < 145:
        return result
    # A low-side candidate owns the decision, even if its facing/admission
    # rejects it. There is no retry of the other side in this invocation.
    if hit_low >= 0:
        column, side = hit_low, -1
        if actor_word(actor, 26) != 1 and actor_word(actor, 2) == -1:
            return result
    elif hit_high >= 0:
        column, side = hit_high, 0
        if actor_word(actor, 26) != 1 and actor_word(actor, 2) == 0:
            return result
    else:
        return result
    row = actor_word(actor, 14)
    if row < 0:
        row = signed_word(row + 3)
    if row >= 3:
        row = signed_word(row - 3)
    tile = reader.read(tags[column], column, row)
    foreground = reader.cache[1] & 65535
    if tile == 7:
        blocked = kind in (7, 8) or height > 34 or foreground & 3 == 3
    elif tile == 10:
        blocked = False
    elif tile == 4:
        blocked = bool(admission_reference(actor, foreground, 2))
    elif tile == 12:
        blocked = kind not in (1, 7, 8, 11) and height > 48 and 3 <= foreground & 31 <= 15
    else:
        blocked = True
    if not blocked or kind == 11:
        return result
    _, _, _, room, normalized, row = reader.cache
    anchor = adjusted_anchor_reference(signed_word(229 + 51 * normalized), room,
                                      reader.view_room if view is None else view, neighbors)
    result['anchor'] = anchor
    # The second query reuses normalized coordinates, not the original tag
    # and requested column. Geometry is still raw classification, not admission.
    tile = reader.read(room, normalized, row)
    if tile == 2:
        barrier = 3 if reader.cache[1] & 255 < 3 and bars else 4
    elif tile in (20, 25):
        barrier = 4
    elif tile == 7:
        barrier = 2 if height <= 34 else 4
    else:
        barrier = {4: 1, 12: 6}.get(tile, 0)
    edge = (signed_word(anchor + FACE_OFFSETS[barrier]) if barrier else 921) if side == -1 else (
            signed_word(anchor + 50 - BACK_OFFSETS[barrier]) if barrier else 0)
    if reader.level[0x2191] and (edge >= 921 if side == -1 else edge <= 0):
        rock_queries.append((reader.cache[3], reader.cache[5]))
        edge = 921 if side == -1 else 0  # actual empty-MOB lookup fallback
    events.append(('collide', signed_word(edge - edges[1 if side == -1 else 0]), side))
    return result


class NativeTempleCollisionDecision(NativeTempleCollisionBanks):
    RANGES = dict(NativeTempleCollisionBanks.RANGES)
    RANGES[4] += ((0x54da, 0x5640), (0x5654, 0x56d4), (0x5ade, 0x5b0c), (0x5c76, 0x5cba))
    RANGES[5] += ((0x5fa0, 0x5fc4),)
    RANGES[10] += ((0x180e, 0x18f2),)

    def reset(self, level):
        super().reset(level)
        self.responses = []

    def dispatch(self, cpu, address, size, user):
        if address == self.address(4, 0x5738):
            stack = cpu.reg_read(self.registers['a7'])
            delta, side = struct.unpack('>2h', cpu.mem_read(stack + 4, 4))
            self.responses.append(('collide', delta, side))
            self.services['collide_response'] += 1
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['d0'], 0)
            cpu.reg_write(self.registers['pc'], destination)
            return
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    levels = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL']
    machine = NativeTempleCollisionDecision(parse_resource_fork(executable))
    counts, outcomes, digest = Counter(), Counter(), hashlib.sha256()
    mob_guard = bytes((index * 7 + 3) & 255 for index in range(512))

    def check(level, actor, edges, flags, label, *, height=74, bars=0, compose=False, pattern=0):
        room = actor_word(actor, 22)
        tables = {name: [room] * 10 if name.endswith('tags') else [pattern] * 10 for name in TABLES}
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, actor)
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(range(62)))
        machine.cpu.mem_write(machine.A5 - 0x448e, bytes(range(160)))
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', *COLD_CACHE))
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', 0xb0000))
        machine.cpu.mem_write(0xb0000, mob_guard)
        machine.put_word(-0x4490, 0)
        for offset in NEIGHBOR_SLOTS:
            machine.put_word(offset, 0)
        for name, offset in TABLES.items():
            machine.cpu.mem_write(machine.A5 + offset, struct.pack('>10H', *tables[name]))
        for offset, value in ((-0x4fc2, room), (-0x357c, 71), (-0x357e, 1),
                              (-0x3580, 7), (-0x3582, 8), (-0x35fc, 73), (-0x481c, 79),
                              (-0x3578, flags[0]), (-0x357a, flags[1]), (-0x3564, edges[0]),
                              (-0x3566, edges[1]), (-0x3560, height), (-0x36bc, bars), (-0x4fa6, 0)):
            machine.put_word(offset, value)
        reader = StandingCellReader(level, room)
        before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        rock_queries, anchor = [], 73
        if compose:
            bank_result = banks_reference(actor, edges, tables, reader, 1, height=height)
            machine.call(4, 0x4e34)
            tables, anchor = bank_result['tables'], bank_result['anchor']
            flags = bank_result['hit_low'], bank_result['hit_high']
            rock_queries.extend(bank_result['rock_queries'])
            for name, offset in TABLES.items():
                struct.pack_into('>10H', before, len(machine.data) + offset, *tables[name])
            for offset, name in ((-0x357c, 'current'), (-0x357e, 'previous'), (-0x3580, 'first'),
                                 (-0x3582, 'last'), (-0x481c, 'remainder'),
                                 (-0x3578, 'hit_low'), (-0x357a, 'hit_high')):
                struct.pack_into('>h', before, len(machine.data) + offset, bank_result[name])
        expected = decision_reference(actor, edges, tables['current_tags'], *flags, reader,
                                      height=height, bars=bars, anchor=anchor)
        rock_queries.extend(expected['rock_queries'])
        machine.call(4, 0x54da)
        struct.pack_into('>h', before, len(machine.data) - 0x35fc, expected['anchor'])
        struct.pack_into('>6h', before, len(machine.data) - 0x34b0, *reader.cache)
        if reader.pointer_room is not None:
            r = reader.pointer_room
            struct.pack_into('>II', before, len(machine.data) - 0x4824,
                             machine.LEVEL + 0x780 + (r - 1) * 120,
                             machine.LEVEL + (r - 1) * 60)
        after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        if (after != before or machine.responses != expected['events']
                or machine.services != Counter(collide_response=len(expected['events']))
                or machine.reads != reader.requests or machine.rock_queries != rock_queries
                or machine.level_bytes(len(level)) != level
                or bytes(machine.cpu.mem_read(0xb0000, 512)) != mob_guard):
            raise AssertionError(dict(label=label, actor=actor.hex(), flags=flags, expected=expected,
                actual_events=machine.responses, reads=machine.reads, expected_reads=reader.requests,
                rocks=machine.rock_queries, expected_rocks=rock_queries,
                changed=[(hex(i - len(machine.data)), a, b)
                         for i, (a, b) in enumerate(zip(before, after)) if a != b]))
        counts[label] += 1
        outcomes['response' if expected['events'] else 'no_response'] += 1
        digest.update(actor + struct.pack('>h6h', expected['anchor'], *reader.cache))
        digest.update(json.dumps(expected['events']).encode('ascii'))

    original = levels[2009]['data']
    for tile, foreground, kind, height, facing, armed, flags in product(
            range(50), (0, 3, 12, 184), (0, 1, 7, 8, 11), (34, 74), (-1, 0), (0, 1),
            ((-1, -1), (4, -1), (-1, 4), (4, 4))):
        level = bytearray(original)
        level[0x2191] = int(foreground == 12)
        struct.pack_into('>H', level, 14 * 2, tile)
        struct.pack_into('>H', level, 0x780 + 14 * 4, foreground)
        actor = bytearray(actor_fixture(1, 1, 4, facing, 0))
        for offset, value in ((8, kind), (10, 15), (26, armed), (40, 2), (42, 20), (46, 20 + height)):
            put_actor(actor, offset, value)
        check(bytes(level), bytes(actor), (430, 475), flags, 'controlled_tile_decisions', height=height)
    for mode, pose, facing, armed, flags, row in product(
            (0, 2, 6, 7), (134, 135, 144, 145, -1), (-1, 0), (0, 1),
            ((4, -1), (-1, 4), (4, 4)), (-1, 3)):
        level = bytearray(original)
        struct.pack_into('>H', level, 4 * 2, 20)
        struct.pack_into('>H', level, 24 * 2, 20)
        actor = bytearray(actor_fixture(1, row, 4, facing, mode))
        for offset, value in ((8, 0), (10, pose), (26, armed)):
            put_actor(actor, offset, value)
        check(bytes(level), bytes(actor), (430, 475), flags, 'mode_pose_row_controls')
    for number in range(10, 14):
        level = levels[1999 + number]['data']
        maximum = struct.unpack_from('>H', level, 0x2180)[0]
        for room, row, facing, armed, pattern, edges in product(range(1, maximum + 1), range(3),
                (-1, 0), (0, 1), (0, 255), ((230, 260), (430, 475), (680, 720))):
            actor = bytearray(actor_fixture(room, row, 4, facing, 0))
            for offset, value in ((4, sum(edges) // 2), (6, row * 120 + 106), (8, 0), (10, 15),
                                  (18, 1), (26, armed), (28, -1), (30, 3), (40, 2), (42, 20), (46, 94)):
                put_actor(actor, offset, value)
            check(level, bytes(actor), edges, (7, 8), 'native_banks_composition',
                  compose=True, pattern=pattern)
    return dict(comparisons=dict(counts), outcomes=dict(outcomes), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                outputs_sha256=digest.hexdigest(), supplied=['Collide4:5738 recorded no-op response'],
                scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
