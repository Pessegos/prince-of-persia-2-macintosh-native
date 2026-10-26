"""Execute Collide's bounded grounded path through real bump/animation/frame reload.

Actor, correction/side and current-cell cache are fixtures. Actual ReadCell,
IsWall/IsSpace and empty-MOB rock intersection execute; GroundBump, JumpSeq,
AnimChar and Kid LoadFrame are real. Resource/Memory Manager boundaries and
FRAM/AFRM handles are supplied. Other airborne and still-wall-after-bump paths are
explicitly excluded, as are ShapeBounds, admission and complete FrameAdv.
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
from tools.probe_temple_collision_decision import NativeTempleCollisionDecision
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import COLD_CACHE, StandingCellReader
from tools.probe_temple_ground_bump import NativeTempleGroundBump, ground_bump_reference
from tools.probe_temple_slide_rock_update import actor_word


WALLS = frozenset((2, 7, 20, 25))
SPACES = frozenset((0, 9, 27, 47, 49))


class ResponseBoundary(ValueError):
    """A valid native path intentionally excluded from this bounded proof."""


def collision_reference(actor, delta, side, reader, sequences, frames, attachments,
                        *, available=True, floating=False, metadata=bytes(range(18)),
                        remainder=79, mark=73):
    if len(actor) != 62 or actor_word(actor, 8) != 0 or side not in (-1, 0):
        raise ValueError('Expected a complete type0 actor and native contact side')
    result = dict(actor=actor, events=[], metadata=metadata, remainder=remainder, mark=mark,
                  rock_queries=[])
    if actor_word(actor, 28) >= 0 or actor_word(actor, 10) in (242, 243):
        return result
    working = bytearray(actor)
    put_actor(working, 4, actor_word(actor, 4) + delta)
    tile = reader.cache[0]
    if tile in WALLS:
        _, _, _, room, column, row = reader.cache
        if room == 0:
            raise ResponseBoundary('undefined-room wall correction')
        offset = 2 if actor_word(actor, 40) == 75 else 1
        tile = reader.read(room, column + (-offset if side == -1 else offset), row)
    if tile in WALLS:
        raise ResponseBoundary('post-bump wall spacing')
    events, rock_queries = [], []
    if tile in SPACES:
        # IsSpace true enters the temple rock test. Its real empty-bank
        # result0 chooses GroundBump; do not invert this branch by intuition.
        rock_queries.append((reader.cache[3], reader.cache[5]))
    else:
        events.append(('air_entry',))
        if actor_word(actor, 26) == 1 or actor_word(actor, 14) * 120 + 106 - actor_word(actor, 6) < 30:
            raise ResponseBoundary('other airborne response')
    bumped = ground_bump_reference(bytes(working), sequences, frames, attachments,
                                   available=available, floating=floating)
    return dict(bumped, events=events + [('ground',)] + bumped['events'], rock_queries=rock_queries)


class NativeTempleGroundCollision(NativeTempleGroundBump):
    RANGES = {segment: NativeTempleGroundBump.RANGES.get(segment, ())
              + NativeTempleCollisionDecision.RANGES.get(segment, ())
              for segment in NativeTempleGroundBump.RANGES.keys() | NativeTempleCollisionDecision.RANGES.keys()}
    RANGES[3] += ((0x4ef2, 0x4f24),)
    RANGES[4] += ((0x5738, 0x585a), (0x589e, 0x58de), (0x5a5a, 0x5a60))
    RANGES[10] += ((0x2036, 0x20ea),)

    def reset(self, level):
        super().reset(level)
        self.reads, self.rock_queries = [], []

    def dispatch(self, cpu, address, size, user):
        stack = cpu.reg_read(self.registers['a7'])
        if address == self.address(4, 0x27ee):
            self.reads.append(struct.unpack('>3h', cpu.mem_read(stack + 4, 6)))
        elif address == self.address(10, 0x1a9e):
            self.rock_queries.append(struct.unpack('>2h', cpu.mem_read(stack + 4, 4)))
        elif address == self.address(4, 0x5868):
            self.events.append(('ground',))
        elif address == self.address(4, 0x589e):
            self.events.append(('air_entry',))
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    kid = parse_resource_fork((forks / 'Kid.rsrc.bin').read_bytes())
    frames, attachments = kid['FRAM'][25001]['data'], kid['AFRM'][25001]['data']
    raw = {n: prince['SEQS'][n]['data'] for n in (2, 45, 229)}
    sequences = {n: struct.unpack('>' + str(len(data) // 2) + 'h', data) for n, data in raw.items()}
    machine = NativeTempleGroundCollision(parse_resource_fork(executable), raw, frames, attachments)
    counts, excluded, digest = Counter(), Counter(), hashlib.sha256()
    mob_guard = bytes((i * 7 + 3) & 255 for i in range(512))

    def check(level, actor, delta, side, available, floating, label):
        room, column, row = (actor_word(actor, o) for o in (22, 12, 14))
        reader = StandingCellReader(level, room)
        reader.read(room, column, row)
        reader.requests.clear()
        try:
            expected = collision_reference(actor, delta, side, reader, sequences, frames, attachments,
                                            available=available, floating=floating)
        except ResponseBoundary as error:
            excluded[str(error)] += 1
            return
        machine.reset(level)
        machine.available = available
        machine.cpu.mem_write(machine.A5 - 0x5056, actor)
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(range(62)))
        machine.cpu.mem_write(machine.A5 - 0x448e, bytes(range(160)))
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', *COLD_CACHE))
        machine.cpu.mem_write(machine.A5 - 0x521a, bytes(range(18)))
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', 0xb0000))
        machine.cpu.mem_write(0xb0000, mob_guard)
        for offset, value in ((-0x4fc2, room), (-0x4490, 0), (-0x481c, 79), (-0x4f9e, 73),
                              (-0x4fa6, int(floating)), (-0x3564, 430), (-0x3566, 475)):
            machine.put_word(offset, value)
        machine.call(4, 0x27ee, (room, column, row))
        machine.reads.clear()
        before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        try:
            machine.call(4, 0x5738, (delta, side))
        except RuntimeError as error:
            raise AssertionError(dict(label=label, actor=actor.hex(), delta=delta, side=side,
                expected=expected, native_cache=struct.unpack('>6h',
                machine.cpu.mem_read(machine.A5 - 0x34b0, 12)), reads=machine.reads)) from error
        before[len(machine.data) - 0x5056:len(machine.data) - 0x5056 + 62] = expected['actor']
        before[len(machine.data) - 0x521a:len(machine.data) - 0x521a + 18] = expected['metadata']
        for offset, name in ((-0x481c, 'remainder'), (-0x4f9e, 'mark')):
            struct.pack_into('>h', before, len(machine.data) + offset, expected[name])
        struct.pack_into('>6h', before, len(machine.data) - 0x34b0, *reader.cache)
        if reader.pointer_room is not None:
            r = reader.pointer_room
            struct.pack_into('>II', before, len(machine.data) - 0x4824,
                             machine.LEVEL + 0x780 + (r - 1) * 120,
                             machine.LEVEL + (r - 1) * 60)
        after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        if (after != before or machine.events != expected['events'] or machine.services
                or machine.reads != reader.requests or machine.rock_queries != expected['rock_queries']
                or machine.level_bytes(len(level)) != level
                or bytes(machine.cpu.mem_read(0xb0000, 512)) != mob_guard):
            raise AssertionError(dict(label=label, actor=actor.hex(), delta=delta, side=side,
                expected=expected, events=machine.events, reads=machine.reads,
                expected_reads=reader.requests, rocks=machine.rock_queries,
                changed=[(hex(i - len(machine.data)), a, b)
                         for i, (a, b) in enumerate(zip(before, after)) if a != b]))
        machine.verify_resources()
        counts[label] += 1
        digest.update(expected['actor'] + expected['metadata'] + struct.pack('>h6h',
                      expected['remainder'], *reader.cache))
        digest.update(json.dumps(expected['events']).encode('ascii'))

    for number in range(10, 14):
        level = prince['LEVL'][1999 + number]['data']
        maximum = struct.unpack_from('>H', level, 0x2180)[0]
        for room, cell in product(range(1, maximum + 1), range(30)):
            tile = struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0]
            if tile not in WALLS | {4, 12}:
                continue
            row, column = divmod(cell, 10)
            for facing, side, mode, floating, available in product((-1, 0), (-1, 0),
                                                                  (0, 4), (False, True), (False, True)):
                actor = bytearray(actor_fixture(room, row, column, facing, mode))
                for offset, value in ((4, 229 + column * 51), (6, row * 120 + 76), (8, 0),
                                      (10, 15), (18, 5), (26, 0), (28, -1), (30, 3), (36, 0), (38, 2), (40, 2)):
                    put_actor(actor, offset, value)
                check(level, bytes(actor), -2 if side == -1 else 53, side,
                      available, floating, 'declared_barrier_grounded_states')
    original = prince['LEVL'][2009]['data']
    for source, alive, pose, side, facing, delta in product((2, 75), (-1, 0), (15, 242, 243),
            (-1, 0), (-1, 0), (-32768, -25, 0, 25, 32767)):
        level = bytearray(original)
        for cell in range(10, 20):
            struct.pack_into('>H', level, cell * 2, 0)
        struct.pack_into('>H', level, 14 * 2, 20)
        actor = bytearray(actor_fixture(1, 1, 4, facing, 0))
        for offset, value in ((4, 460), (6, 226), (8, 0), (10, pose), (18, 5), (26, 0), (28, alive),
                              (30, 3), (36, 0), (38, 2), (40, source)):
            put_actor(actor, offset, value)
        check(bytes(level), bytes(actor), signed_word(delta), side, True, False, 'early_and_word_controls')
    return dict(comparisons=dict(counts), excluded_states=dict(excluded), mismatches=0,
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
