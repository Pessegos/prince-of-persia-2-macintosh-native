"""Execute native GateBarrToStandUp with real cell traversal and original tables."""

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
from tools.probe_temple_slide_rock_geometry import NativeSlideRockGeometry, TempleCellReader
from tools.probe_temple_slide_rock_update import actor_word


COLD_CACHE = (0, 0, 0, 0, -32768, -32768)


class StandingCellReader(TempleCellReader):
    """Track ReadCell's two room-base pointers, including undefined-read retention."""

    def __init__(self, level, view_room):
        super().__init__(level, view_room)
        self.pointer_room = None

    def read(self, room, column, row):
        kind = super().read(room, column, row)
        maximum = struct.unpack_from('>H', self.level, 0x2180)[0]
        if 1 <= self.cache[3] <= maximum:
            self.pointer_room = self.cache[3]
        return kind


def standing_reference(actor, reader):
    """First gate wins; the closed and fully raised positions do not block standing."""
    if len(actor) != 62 or actor_word(actor, 2) not in (-1, 0):
        raise ValueError('Expected a complete actor in a native facing')
    room, column, row = (actor_word(actor, offset) for offset in (22, 12, 14))
    number = struct.unpack_from('>H', reader.level, 0x218a)[0]
    if room == 9 and number == 8:
        return 0
    facing = actor_word(actor, 2)
    # These native tables are opposite: GetCellsInFront(1), then FrontCell.
    behind = -1 if facing == -1 else 1
    for col in (column, column + behind, column - behind):
        if reader.read(room, col, row) == 4:
            break
    else:
        return 0
    position = reader.cache[1] & 255
    if not 0 < position < 184:
        return 0
    anchor = signed_word(signed_word(actor_word(actor, 4) + (10 if facing == -1 else -10)) - 22)
    resolved_column = reader.cache[4]
    if not 0 <= resolved_column <= 9:
        raise ValueError('Gate must resolve to a bounded live cell')
    return int(226 + resolved_column * 51 <= anchor <= 264 + resolved_column * 51)


class NativeTempleGateStanding(NativeSlideRockGeometry):
    RANGES = dict(NativeSlideRockGeometry.RANGES)
    RANGES[4] += ((0x2bae, 0x2bcc), (0x39fc, 0x3a32), (0x3a48, 0x3a70), (0x5baa, 0x5c5e))


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeTempleGateStanding(parse_resource_fork(executable))
    counts, outcomes, reads, digest = Counter(), Counter(), Counter(), hashlib.sha256()
    levels = {n: prince['LEVL'][1999 + n]['data'] for n in range(10, 14)}
    saved, bank = bytes(range(62)), bytes(range(160))
    machine.reset(levels[10])
    if (tuple(machine.word(-0x4b98 + facing * 2) for facing in (-1, 0)) != (-1, 1)
            or tuple(machine.word(-0x4b94 + facing * 2) for facing in (-1, 0)) != (1, -1)
            or tuple(machine.word(-0x4b88 + column * 2) for column in range(11))
            != tuple(207 + column * 51 for column in range(11))):
        raise ValueError('Original direction/boundary tables differ from the independent model')

    def check(level, actor, label, *, warm=False):
        machine.reset(level)
        machine.put_word(-0x4fc2, actor_word(actor, 22))
        machine.cpu.mem_write(machine.A5 - 0x5056, actor)
        machine.cpu.mem_write(machine.A5 - 0x50d2, saved)
        machine.cpu.mem_write(machine.A5 - 0x448e, bank)
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', *COLD_CACHE))
        reader = StandingCellReader(level, actor_word(actor, 22))
        if warm:
            request = tuple(actor_word(actor, o) for o in (22, 12, 14))
            reader.read(*request)
            reader.requests.clear()
            machine.call(4, 0x27ee, request)
            machine.reads.clear()
        before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        expected = standing_reference(actor, reader)
        actual = machine.call(4, 0x5baa)
        struct.pack_into('>6h', before, len(machine.data) - 0x34b0, *reader.cache)
        if reader.pointer_room is not None:
            room = reader.pointer_room
            struct.pack_into('>II', before, len(machine.data) - 0x4824,
                             machine.LEVEL + 0x780 + (room - 1) * 120,
                             machine.LEVEL + (room - 1) * 60)
        after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        if (actual != expected or machine.cache() != reader.cache or machine.reads != reader.requests
                or after != before
                or machine.level_bytes(len(level)) != level or machine.services):
            raise AssertionError(dict(label=label, actor=actor.hex(), actual=actual, expected=expected,
                                      cache=machine.cache(), expected_cache=reader.cache,
                                      reads=machine.reads, expected_reads=reader.requests,
                                      changed=[(hex(i - len(machine.data)), a, b)
                                               for i, (a, b) in enumerate(zip(before, after)) if a != b]))
        counts[label] += 1
        outcomes[f'{label}:{actual}'] += 1
        reads[str(len(reader.requests))] += 1
        digest.update(bytes(level) + actor + struct.pack('>h6h', actual, *reader.cache))
        digest.update(json.dumps(reader.requests).encode('ascii'))

    gates = 0
    for number, original in levels.items():
        for room, cell in product(range(1, 33), range(30)):
            if struct.unpack_from('>h', original, (room - 1) * 60 + cell * 2)[0] != 4:
                continue
            gates += 1
            row, column = divmod(cell, 10)
            for facing, relative_col, position, relative_x in product(
                    (-1, 0), (-1, 0, 1), (0, 1, 4, 180, 183, 184, 255, 0x8101),
                    (237, 238, 239, 257, 258, 276, 277, 296, 297)):
                level = bytearray(original)
                struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, position)
                actor = bytearray(actor_fixture(room, row, column + relative_col, facing, 2))
                put_actor(actor, 4, column * 51 + relative_x)
                check(level, bytes(actor), 'original_gate_anchors', warm=relative_x == 258)

    # Explicit lookup priority, absent gates, room joins and the level8 exemption.
    original = levels[10]
    for topology in ('no_links', 'horizontal', 'vertical'):
        for gate_columns, positions, facing, column, row, x in product(
                ((), (0,), (4,), (5,), (6,), (4, 5), (4, 6), (9,)),
                ((0, 1), (1, 0), (183, 184)), (-1, 0), (-1, 0, 4, 5, 9, 10),
                (-1, 0, 1, 2, 3), (238, 258, 493, -32768, 32767)):
            level = bytearray(original)
            for room in range(1, 4):
                level[(room - 1) * 60:room * 60] = bytes(60)
                level[0x2080 + (room - 1) * 8:0x2080 + room * 8] = bytes(8)
                for gate, gate_row in product(gate_columns, range(3)):
                    cell = gate_row * 10 + gate
                    struct.pack_into('>h', level, (room - 1) * 60 + cell * 2, 4)
                    struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4,
                                     positions[int(gate == 5)])
            if topology == 'horizontal':
                struct.pack_into('>2H', level, 0x2080, 2, 3)
            elif topology == 'vertical':
                struct.pack_into('>2H', level, 0x2084, 2, 3)
            actor = bytearray(actor_fixture(1, row, column, facing, 2))
            put_actor(actor, 4, x)
            check(level, bytes(actor), 'controlled_traversal')

    for number, room in product((8, 10), (8, 9, 10)):
        level = bytearray(original)
        struct.pack_into('>H', level, 0x218a, number)
        struct.pack_into('>h', level, (room - 1) * 60 + 14 * 2, 4)
        struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + 14 * 4, 1)
        actor = bytearray(actor_fixture(room, 1, 4, -1, 2))
        put_actor(actor, 4, 4 * 51 + 238)
        check(level, bytes(actor), 'level8_room9_control')
    return dict(comparisons=sum(counts.values()), original_gate_anchors=gates, mismatches=0,
                cases=dict(counts), outcomes=dict(outcomes), read_counts=dict(reads),
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                level_sha256={str(n): hashlib.sha256(level).hexdigest() for n, level in levels.items()},
                outputs_sha256=digest.hexdigest(), supplied_services=[],
                scope='Actual4:5baa, ReadCell/normalization, GetCellsInFront(1), FrontCell and AddCharX '
                      'with original DATA tables. Original gate anchors plus controlled topology/position '
                      'and level8-number fixtures. No animation, physical reachability, caller/world loop '
                      'or runtime changes; closed-door handling belongs to other collision rules.')


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
