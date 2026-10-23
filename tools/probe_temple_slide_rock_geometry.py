"""Validate original sliding-rock span predicates and real temple cell traversal."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_slide_rock_motion import trunc_div


class TempleCellReader:
    """Independent bounded ReadCell model, including cached normalized coordinates."""

    def __init__(self, level, view_room):
        if (len(level) < 0x218c or struct.unpack_from('>H', level, 0x2186)[0] != 2
                or not 0 <= view_room <= 32):
            raise ValueError('Expected a temple fixture and a bounded view room')
        self.level = level
        self.view_room = view_room
        self.requests = []
        # Native order: kind, foreground, cell index, room, column, row.
        self.cache = (0, 0, 0, 0, -32768, -32768)

    def link(self, room, direction):
        target = struct.unpack_from('>H', self.level, 0x2080 + (room - 1) * 8 + direction * 2)[0]
        if not 0 <= target <= 32:
            raise ValueError('Neighbor link outside the bounded room domain')
        return target

    def resolve(self, room, column, row, depth=0):
        if depth > 32:
            raise ValueError('Cell traversal outside the bounded recursion domain')
        candidate, adjustment = room, 0
        if column < 0 or column >= 10:
            direction, adjustment = (0, 10) if column < 0 else (1, -10)
            if room:
                candidate = self.link(room, direction)
                if candidate:
                    room, column, row = self.resolve(candidate, column + adjustment, row, depth + 1)
                    adjustment = 0
        # The original tries vertical traversal even after a missing horizontal
        # link. A diagonal request can therefore find a different viable path.
        if room and (row < 0 or row >= 3):
            direction, delta = (2, 3) if row < 0 else (3, -3)
            candidate = self.link(room, direction)
            room, column, row = self.resolve(candidate, column, row + delta, depth + 1)
        if candidate == 0:
            room = 0
        if not 0 <= column < 10:
            column += adjustment
        return room, column, row

    def read(self, room, column, row):
        if not 0 <= room <= 32 or not -2 <= column <= 12 or not -1 <= row <= 3:
            raise ValueError('Cell request outside the tested geometry domain')
        request = (room, column, row)
        self.requests.append(request)
        if self.cache[3:] == request:
            resolved_room, resolved_column, resolved_row = request
            index = self.cache[2]
        else:
            resolved_room, resolved_column, resolved_row = self.resolve(*request)
            # Native FirstInRow has a distinct negative-row sentinel convention.
            first = resolved_row * 10 if resolved_row >= 0 else (resolved_row + 1) * 10 - 1
            index = first + resolved_column
        maximum = struct.unpack_from('>H', self.level, 0x2180)[0]
        if 1 <= resolved_room <= maximum:
            if not 0 <= index < 30:
                raise ValueError('Resolved live cell is outside the bounded room domain')
            kind = struct.unpack_from('>h', self.level, (resolved_room - 1) * 60 + index * 2)[0]
            foreground = struct.unpack_from('>h', self.level,
                                            0x780 + (resolved_room - 1) * 120 + index * 4)[0]
        else:
            number = struct.unpack_from('>H', self.level, 0x218a)[0]
            kind = 0 if number == 13 and self.view_room in (4, 13) else 20
            foreground = 0
        self.cache = (kind, foreground, index, resolved_room, resolved_column, resolved_row)
        return kind


def span_reference(mob, row_offset, length, reader):
    """True iff all visited tiles are neither IsSpace nor the slide-rock marker."""
    if (len(mob) != 8 or any(not -32768 <= word <= 32767 for word in mob)
            or not 1 <= mob[2] <= 32 or not 0 <= mob[6] <= 2
            or not -16 <= mob[0] <= 561 or row_offset not in (-1, 0, 1)
            or not -2 <= length <= 82):
        raise ValueError('Outside the bounded span-predicate domain')
    x, anchor = mob[0], mob[7] & 65535
    first = trunc_div(x + 2)
    distance = signed_word(min(length, anchor - x))
    last = trunc_div(x + distance)
    row = mob[6] + row_offset
    for column in range(first, last + 1):
        kind = reader.read(mob[2], column, row)
        if kind in (0, 9, 27, 47, 49, 25):
            return False
    return True


def stop_predicate_reference(mob, reader):
    return (span_reference(mob, -1, 51, reader)
            and span_reference(mob, 0, 51, reader))


class NativeSlideRockGeometry(NativeRules):
    RANGES = {
        3: ((0x4eb2, 0x4ee4),),
        4: ((0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x322a, 0x3262)),
        5: ((0x0004, 0x0066),),
        10: ((0x1656, 0x1680), (0x1ca4, 0x1d40)),
        19: ((0x4bb0, 0x4bb6), (0x4bd0, 0x4bf4), (0x4bfe, 0x4c4c)),
    }
    SUPPLIED = {}

    def reset(self, level):
        super().reset(level)
        self.reads = []
        for offset in (-0x34b0, -0x34ae, -0x34ac):
            self.put_word(offset, 0)

    def dispatch(self, cpu, address, size, user):
        if address == self.address(4, 0x27ee):
            stack = cpu.reg_read(self.registers['a7'])
            self.reads.append(struct.unpack('>3h', cpu.mem_read(stack + 4, 6)))
        super().dispatch(cpu, address, size, user)

    def cache(self):
        return struct.unpack('>6h', self.cpu.mem_read(self.A5 - 0x34b0, 12))


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeSlideRockGeometry(parse_resource_fork(executable))
    counts, outcomes = Counter(), Counter()
    digest = hashlib.sha256()
    level_hashes = {}
    actors = bytes((i * 23 + 7) % 256 for i in range(62))
    guard = bytes((i * 13 + 11) % 256 for i in range(512))

    def prepare(level, view_room, mob):
        machine.reset(level)
        machine.put_word(-0x4fc2, view_room)
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *mob))
        machine.cpu.mem_write(machine.A5 - 0x5056, actors)
        machine.cpu.mem_write(machine.A5 - 0x50d2, actors)
        machine.cpu.mem_write(0xb0000, guard)

    def compare(level, mob, reader, actual, expected, label):
        if (actual != expected or machine.reads != reader.requests
                or machine.cache() != reader.cache or machine.services
                or machine.level_bytes(len(level)) != level
                or bytes(machine.cpu.mem_read(machine.A5 - 0x44a6, 16)) != struct.pack('>8h', *mob)
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != actors
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != actors
                or bytes(machine.cpu.mem_read(0xb0000, 512)) != guard):
            raise AssertionError(dict(label=label, mob=mob, actual=actual, expected=expected,
                                      native_reads=machine.reads, reads=reader.requests,
                                      native_cache=machine.cache(), cache=reader.cache))
        counts[label] += 1
        outcomes[f'{label}:{actual}'] += 1
        digest.update(struct.pack('>h6h', actual, *machine.cache()))
        digest.update(json.dumps(machine.reads).encode('ascii'))

    def check_span(level, mob, offset, length, view_room, label):
        reader = TempleCellReader(level, view_room)
        expected = int(span_reference(mob, offset, length, reader))
        prepare(level, view_room, mob)
        actual = machine.call(10, 0x1ca4, (offset, length))
        compare(level, mob, reader, actual, expected, label)

    for number in range(10, 14):
        level = prince['LEVL'][1999 + number]['data']
        if struct.unpack_from('>H', level, 0x218a)[0] != number:
            raise ValueError('Inconsistent temple fixture')
        level_hashes[str(number)] = hashlib.sha256(level).hexdigest()
        # Native ReadCell cold and repeated reads, including all normal columns,
        # neighboring columns/rows and the level13 undefined-cell view variants.
        views = (1, 4, 13) if number == 13 else (1,)
        for view, room, col, row in product(views, range(33), range(-1, 11), range(-1, 4)):
            reader = TempleCellReader(level, view)
            mob = (51, 236, max(1, room), 0, 2, 6, 1, 459)
            prepare(level, view, mob)
            for _ in range(2):
                expected = reader.read(room, col, row)
                actual = signed_word(machine.call(4, 0x27ee, (room, col, row)))
                compare(level, mob, reader, actual, expected,
                        'room_zero_cell_controls' if room == 0 else 'cell_cold_and_repeat')
        # Both-row predicate across every ordinary cell position in every room.
        for room, row, col in product(range(1, 33), range(3), range(10)):
            mob = (col * 51, 116 + row * 120, room, 0, 2, 6, row, 459)
            reader = TempleCellReader(level, room)
            expected = int(stop_predicate_reference(mob, reader))
            prepare(level, room, mob)
            actual = machine.call(10, 0x1656)
            compare(level, mob, reader, actual, expected, 'all_cell_stop_predicates')
        for room, cell in product(range(1, 33), range(30)):
            if struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0] != 25:
                continue
            row, column = divmod(cell, 10)
            anchor = column * 51
            positions = sorted(set(range(-16, anchor + 3, 7))
                               | {0, 1, 2, max(0, anchor - 16), anchor, anchor + 2})
            for x, (offset, length) in product(positions, ((-1, 51), (0, 51), (-1, 82))):
                check_span(level, (x, 116 + row * 120, room, 0, 2, 6, row, anchor),
                           offset, length, room, 'original_anchor_spans')

    level = prince['LEVL'][2009]['data']
    topologies = {
        'no_links': (),
        'horizontal': ((1, 0, 2), (1, 1, 3)),
        'vertical': ((1, 2, 2), (1, 3, 3)),
        'horizontal_first_corner': ((1, 0, 2), (2, 2, 3), (1, 2, 4), (4, 0, 5)),
        'vertical_fallback_corner': ((1, 2, 2), (2, 0, 3)),
    }
    for links in topologies.values():
        supplied = bytearray(level)
        for room in range(1, 6):
            supplied[0x2080 + (room - 1) * 8:0x2080 + room * 8] = bytes(8)
            for cell in range(30):
                struct.pack_into('>H', supplied, (room - 1) * 60 + cell * 2, 10 + room)
        for room, direction, target in links:
            struct.pack_into('>H', supplied, 0x2080 + (room - 1) * 8 + direction * 2, target)
        for column, row in product((-2, -1, 0, 4, 9, 10, 12), range(-1, 4)):
            reader = TempleCellReader(supplied, 1)
            mob = (51, 236, 1, 0, 2, 6, 1, 459)
            prepare(supplied, 1, mob)
            expected = reader.read(1, column, row)
            actual = signed_word(machine.call(4, 0x27ee, (1, column, row)))
            compare(supplied, mob, reader, actual, expected, 'cell_topology_controls')
    supplied = bytearray(level)
    struct.pack_into('>H', supplied, 0x2180, 1)
    struct.pack_into('>H', supplied, 0x2080, 2)
    reader = TempleCellReader(supplied, 1)
    mob = (51, 236, 1, 0, 2, 6, 1, 459)
    prepare(supplied, 1, mob)
    expected = reader.read(1, -1, 1)
    actual = signed_word(machine.call(4, 0x27ee, (1, -1, 1)))
    compare(supplied, mob, reader, actual, expected, 'maximum_room_gate')
    for x, anchor, offset, length in product(
            (-16, 0, 1, 2, 49, 50, 51, 52, 459, 508, 509, 510, 511, 561),
            (-1, 0, 1, 51, 459, 561), (-1, 0, 1), (-2, -1, 0, 1, 2, 50, 51, 52, 82)):
        check_span(level, (x, 236, 28, 0, 2, 6, 1, anchor),
                   offset, length, 28, 'span_numeric_boundaries')

    # All raw kinds, short-circuit at each visited position and an outside-band control.
    for kind in (*range(64), 0x8000, 0xffff, 0x7fff):
        supplied = bytearray(level)
        for cell in range(20):
            struct.pack_into('>H', supplied, cell * 2, kind)
        reader = TempleCellReader(supplied, 1)
        mob = (0, 236, 1, 0, 2, 6, 1, 459)
        expected = int(stop_predicate_reference(mob, reader))
        prepare(supplied, 1, mob)
        actual = machine.call(10, 0x1656)
        compare(supplied, mob, reader, actual, expected, 'raw_kind_controls')
    for row, column, kind in product((0, 1), (0, 1, 2), (0, 9, 25, 27, 47, 49)):
        supplied = bytearray(level)
        for cell in range(20):
            struct.pack_into('>H', supplied, cell * 2, 1)
        struct.pack_into('>H', supplied, (row * 10 + column) * 2, kind)
        reader = TempleCellReader(supplied, 1)
        mob = (0, 236, 1, 0, 2, 6, 1, 459)
        expected = int(stop_predicate_reference(mob, reader))
        prepare(supplied, 1, mob)
        actual = machine.call(10, 0x1656)
        compare(supplied, mob, reader, actual, expected, 'short_circuit_controls')

    return dict(
        cases=dict(counts), outcomes=dict(outcomes), mismatches=0,
        outputs_sha256=digest.hexdigest(), level_hashes=level_hashes,
        executable_sha256=hashlib.sha256(executable).hexdigest(), supplied_services=[],
        scope=('Native10:1ca4 span predicate and10:1656 two-row predicate with '
               'native ReadCell/normalization/cache, IsSpace and signed division. '
               'Full level, actors, mob and unrelated bank guards unchanged. '
               'Supplied view rooms, mob records and bounded counterfactual level '
               'copies; original resource files are read-only. No motion/controller, '
               'rendering, actor collision, elapsed timing, saves or temple playability claim.'),
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
