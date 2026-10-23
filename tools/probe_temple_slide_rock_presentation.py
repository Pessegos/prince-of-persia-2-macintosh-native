"""Validate native slide-rock presentation, object-queue writes and record restoration."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_slide_rock_geometry import NativeSlideRockGeometry, TempleCellReader, span_reference
from tools.probe_temple_slide_rock_motion import trunc_div
from tools.probe_temple_trapdoor_presentation import intersect_rect


VIEW_FIELDS = dict(current=-0x4fc2, right=-0x4fc0, left=-0x4fbe, below=-0x4fbc,
                   above=-0x4fba, below_right=-0x4fb8, below_left=-0x4fb6,
                   above_right=-0x4fb4, above_left=-0x4fb2)
CAPACITY = 128
STORAGE_SIZE = 32 + CAPACITY * 28


def view_for(room, relation):
    if relation not in (*VIEW_FIELDS, 'unrelated'):
        raise ValueError('Unknown supplied view relation')
    view = dict.fromkeys(VIEW_FIELDS, 0)
    view['current'] = room % 32 + 1
    if relation != 'unrelated':
        view[relation] = room
    return view


def first_in_row(row):
    return row * 10 if row >= 0 else (row + 1) * 10 - 1


def mob_rect_reference(mob, heights, widths, view):
    x, y, room, _, _, kind, _, _ = mob
    rect = tuple(map(signed_word, (y - heights[kind], x, y + 1, x + widths[kind])))
    if room == view['current']:
        return rect, None
    horizontal = any(room == view[name] for name in (
        'right', 'left', 'below_right', 'below_left', 'above_right', 'above_left'))
    below = any(room == view[name] for name in ('below', 'below_right', 'below_left'))
    above = any(room == view[name] for name in ('above', 'above_right', 'above_left'))
    # Both original horizontal branches pass -510, including the "left" branch.
    dx, dy = (-510 if horizontal else 0), (-365 if below else 365 if above else 0)
    if dx or dy:
        shifted = tuple(signed_word(value + (dy if index % 2 == 0 else dx))
                        for index, value in enumerate(rect))
        return shifted, ('offset', dy, dx, rect, shifted)
    return (0, 0, 0, 0), None


def presentation_reference(mob, reader, view, visible, heights, widths, decorations,
                           clip, storage, *, count=0, screen_cell=-1234):
    if (len(mob) != 8 or mob[5] != 6 or not 1 <= mob[2] <= 32 or not 0 <= mob[6] <= 2
            or not -16 <= mob[0] <= 561 or len(heights) != 14 or len(widths) != 14
            or len(decorations) != 3 or len(storage) != STORAGE_SIZE
            or not 0 <= count < CAPACITY
            or any(not -32768 <= value <= 32767 for value in (*mob, *heights, *widths))):
        raise ValueError('Outside the bounded type-6 presentation domain')
    state, h, w, data = list(mob), list(heights), list(widths), bytearray(storage)
    events = []

    def finish():
        return dict(mob=tuple(state), heights=tuple(h), widths=tuple(w), storage=bytes(data),
                    count=count, screen_cell=screen_cell, events=events)

    def rectangle():
        rect, offset = mob_rect_reference(state, h, w, view)
        if offset is not None:
            events.append(offset)
        clipped = intersect_rect(rect, clip)
        events.append(('intersect', rect, tuple(clip), clipped))
        return clipped

    def add_object():
        nonlocal count
        if count >= CAPACITY:
            raise ValueError('Object append exceeds the supplied research buffer')
        kind = state[5]
        events.append(('object', count, state[1], tuple(state), screen_cell, h[kind], w[kind]))
        rect = rectangle()
        start = 16 + count * 28
        fields = {0: state[0], 2: state[1], 4: 4, 6: state[7], 8: 0,
                  12: kind | 0x80, 22: 0, 24: 0, 26: -1}
        for offset, value in fields.items():
            struct.pack_into('>h', data, start + offset, signed_word(value))
        struct.pack_into('>4h', data, start + 14, *rect)
        count += 1

    def strip():
        nonlocal screen_cell
        phase = (state[0] & 7) >> 1
        while state[0] < state[7]:
            screen_cell = first_in_row(state[6]) + trunc_div(state[0]) + int(state[5] == 8)
            add_object()
            struct.pack_into('>h', data, 16 + (count - 1) * 28 + 24, phase)
            state[0] = signed_word(state[0] + 36)

    if state[3] == -1:
        return finish()
    y = signed_word(state[1] - 5)
    computed_row = trunc_div(y, 120) - int(y <= 0)
    column = trunc_div(state[0])
    screen_cell = (computed_row * 10 + column
                   if 0 <= computed_row < 3 and 0 <= column < 10 else 30)
    events.append(('visibility', state[2], screen_cell))
    if not visible:
        return finish()
    saved_height = h[7]
    filled = span_reference(state, -1, 82, reader)
    if not filled:
        original_y, original_width = state[1], w[6]
        state[1] = signed_word(state[1] - 112)
        w[6] = signed_word(min(w[6], state[7] - state[0]))
        state[0] = signed_word(state[0] + 8)
        h[6] = 19
        events.append(('redraw', 2, tuple(state), screen_cell, h[6], w[6]))
        rect = rectangle()
        events.append(('redraw_sink', 0x3ba, rect, -1))
        state[1], state[0], w[6], h[6] = original_y, mob[0], original_width, saved_height
    else:
        h[6], h[7] = 109, 111
    state[5] = 7
    add_object()
    original_x, original_y = state[0], state[1]
    state[0] = signed_word(state[0] + 51)
    if state[0] < (state[7] & 65535):
        screen_cell = first_in_row(computed_row) + trunc_div(state[0])
        state[1], state[5] = signed_word(state[1] - 2), 6
        add_object()
    for kind, (dx, dy) in zip((8, 8, 9), decorations):
        state[0] = signed_word(original_x + dx)
        if state[0] < (state[7] & 65535):
            state[1], state[5] = signed_word(original_y + dy), kind
            strip()
    state[0], state[1], state[5] = original_x, original_y, 6
    h[6] = h[7] = saved_height
    return finish()


class NativeSlideRockPresentation(NativeSlideRockGeometry):
    RANGES = NativeSlideRockGeometry.RANGES | {
        4: NativeSlideRockGeometry.RANGES[4] + ((0x29d8, 0x2a62), (0x3afa, 0x3b24)),
        5: NativeSlideRockGeometry.RANGES[5] + ((0x307c, 0x3126), (0x32f6, 0x3566)),
        10: NativeSlideRockGeometry.RANGES[10] + ((0x13ca, 0x1644),),
    }
    BANK, OBJECTS, INTERSECT = 0xb0010, 0xc4000, 0xc3800

    def __init__(self, program):
        super().__init__(program)
        self.default_heights = struct.unpack_from('>14h', self.data, len(self.data) - 0x4518)
        self.default_widths = struct.unpack_from('>14h', self.data, len(self.data) - 0x44fc)
        self.decorations = tuple((
            struct.unpack_from('>h', self.data, len(self.data) - dx)[0],
            struct.unpack_from('>h', self.data, len(self.data) - dy)[0])
            for dx, dy in ((0x286e, 0x2870), (0x286a, 0x286c), (0x2866, 0x2868)))
        self.branches = Counter()

    def reset(self, level):
        super().reset(level)
        self.events = []
        self.visible = False
        self.cpu.mem_write(self.A5 - 0x4cb2, struct.pack('>I', self.OBJECTS))
        self.cpu.mem_write(self.A5 - 0x1f58, struct.pack('>I', self.INTERSECT))
        self.put_word(-0x4826, 0)

    def mob(self):
        return struct.unpack('>8h', self.cpu.mem_read(self.A5 - 0x44a6, 16))

    def dimensions(self):
        return (struct.unpack('>14h', self.cpu.mem_read(self.A5 - 0x4518, 28)),
                struct.unpack('>14h', self.cpu.mem_read(self.A5 - 0x44fc, 28)))

    def dispatch(self, cpu, address, size, user):
        stack = cpu.reg_read(self.registers['a7'])
        if address == self.INTERSECT:
            destination, output, first, second = struct.unpack('>4I', cpu.mem_read(stack, 16))
            first = struct.unpack('>4h', cpu.mem_read(first, 8))
            second = struct.unpack('>4h', cpu.mem_read(second, 8))
            rect = intersect_rect(first, second)
            self.events.append(('intersect', first, second, rect))
            cpu.mem_write(output, struct.pack('>4h', *rect))
            cpu.mem_write(stack + 16, bytes((int(rect != (0, 0, 0, 0)), 0)))
            cpu.reg_write(self.registers['a7'], stack + 16)
            cpu.reg_write(self.registers['pc'], destination)
            return
        if address == self.address(5, 0x33d0):
            if bytes(cpu.mem_read(address, 2)) != b'\xa8\xa8':
                raise AssertionError('Unexpected instruction at OffsetRect trap')
            dy, dx, pointer = struct.unpack('>hhI', cpu.mem_read(stack, 8))
            before = struct.unpack('>4h', cpu.mem_read(pointer, 8))
            after = tuple(signed_word(value + (dy if index % 2 == 0 else dx))
                          for index, value in enumerate(before))
            self.events.append(('offset', dy, dx, before, after))
            cpu.mem_write(pointer, struct.pack('>4h', *after))
            cpu.reg_write(self.registers['a7'], stack + 8)
            cpu.reg_write(self.registers['pc'], address + 2)
            return
        if address in (self.address(5, 0x346a), self.address(5, 0x33fa)):
            mob = self.mob()
            h, w = self.dimensions()
            if address == self.address(5, 0x346a):
                count = self.word(-0x4826)
                if not 0 <= count < CAPACITY:
                    raise AssertionError('Native append exceeded supplied object-buffer budget')
                y = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
                self.events.append(('object', count, y, mob, self.word(-0x34c8), h[mob[5]], w[mob[5]]))
            else:
                how = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
                self.events.append(('redraw', how, mob, self.word(-0x34c8), h[mob[5]], w[mob[5]]))
        if address in (self.address(5, 0x3960), self.address(5, 0x19f8)):
            if address == self.address(5, 0x3960):
                self.events.append(('visibility', *struct.unpack('>2h', cpu.mem_read(stack + 4, 4))))
                cpu.reg_write(self.registers['d0'], int(self.visible))
            else:
                callback, pointer, flag = struct.unpack('>IIh', cpu.mem_read(stack + 4, 10))
                self.events.append(('redraw_sink', callback - self.A5,
                                    struct.unpack('>4h', cpu.mem_read(pointer, 8)), flag))
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], destination)
            return
        for offset, label in ((0x14be, 'upper_band_gap'), (0x1520, 'upper_band_filled'),
                              (0x1582, 'trailing_type6'), (0x13ee, 'decoration_tile')):
            if address == self.address(10, offset):
                self.branches[label] += 1
        super().dispatch(cpu, address, size, user)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeSlideRockPresentation(parse_resource_fork(executable))
    counts = Counter()
    objects_appended = 0
    digest = hashlib.sha256()
    level_hashes = {}
    guard = bytes((i * 19 + 5) % 256 for i in range(512))
    object_canary = bytes((i * 13 + 3) % 256 for i in range(STORAGE_SIZE))
    actors = bytes((i * 29 + 11) % 256 for i in range(62))
    default_clip = (-1000, -1000, 2000, 2000)

    def check(level, mob, relation, visible, label, *, heights=None, widths=None,
              clip=default_clip, driver=False, count=3):
        nonlocal objects_appended
        view = view_for(mob[2], relation)
        reader = TempleCellReader(level, view['current'])
        heights = machine.default_heights if heights is None else heights
        widths = machine.default_widths if widths is None else widths
        expected = presentation_reference(mob, reader, view, visible, heights, widths,
                                           machine.decorations, clip, object_canary, count=count)
        machine.reset(level)
        machine.visible = visible
        for key, value in view.items():
            machine.put_word(VIEW_FIELDS[key], value)
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *mob))
        machine.cpu.mem_write(machine.A5 - 0x4518, struct.pack('>14h', *heights))
        machine.cpu.mem_write(machine.A5 - 0x44fc, struct.pack('>14h', *widths))
        machine.cpu.mem_write(machine.A5 - 0x4fec, struct.pack('>4h', *clip))
        machine.put_word(-0x4826, count)
        machine.put_word(-0x34c8, -1234)
        machine.cpu.mem_write(machine.OBJECTS - 16, object_canary)
        machine.cpu.mem_write(machine.A5 - 0x5056, actors)
        machine.cpu.mem_write(machine.A5 - 0x50d2, actors)
        bank = bytearray(guard)
        bank[16:32] = struct.pack('>8h', *mob)
        machine.cpu.mem_write(machine.BANK - 16, bytes(bank))
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
        machine.put_word(-0x4490, 1)
        machine.call(5, 0x307c) if driver else machine.call(10, 0x1456)
        actual = dict(mob=machine.mob(), heights=machine.dimensions()[0], widths=machine.dimensions()[1],
                      storage=bytes(machine.cpu.mem_read(machine.OBJECTS - 16, STORAGE_SIZE)),
                      count=machine.word(-0x4826), screen_cell=machine.word(-0x34c8), events=machine.events)
        if (actual != expected or machine.reads != reader.requests or machine.cache() != reader.cache
                or machine.level_bytes(len(level)) != level or machine.word(-0x4490) != 1
                or bytes(machine.cpu.mem_read(machine.BANK - 16, 512)) != bank
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != actors
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != actors or machine.services):
            different = {key: (actual[key], expected[key]) for key in expected
                         if actual[key] != expected[key] and key != 'storage'}
            raise AssertionError(dict(label=label, mob=mob, relation=relation, visible=visible,
                                      different=different, storage_diff=actual['storage'] != expected['storage'],
                                      reads=machine.reads, expected_reads=reader.requests))
        if actual['mob'] != mob:
            raise AssertionError('Presentation changed the persistent rock record')
        counts[label] += 1
        objects_appended += actual['count'] - count
        digest.update(actual['storage'] + struct.pack('>8h14h14h2h', *actual['mob'],
                      *actual['heights'], *actual['widths'], actual['count'], actual['screen_cell']))
        digest.update(json.dumps((actual['events'], machine.reads)).encode('ascii'))

    for number in range(10, 14):
        level = prince['LEVL'][1999 + number]['data']
        level_hashes[str(number)] = hashlib.sha256(level).hexdigest()
        for room, cell in product(range(1, 33), range(30)):
            if struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0] != 25:
                continue
            row, column = divmod(cell, 10)
            anchor = column * 51
            positions = sorted({0, anchor, max(0, anchor - 2), max(0, anchor - 16),
                                max(0, anchor - 52), max(0, anchor - 83)})
            for x, mark, visible, driver in product(positions, (-1, 0, 1), (False, True), (False, True)):
                check(level, (x, 116 + row * 120, room, mark, -2, 6, row, anchor),
                      'current', visible, 'actual_anchor_presentations', driver=driver)
            for relation, visible in product((*VIEW_FIELDS, 'unrelated'), (False, True)):
                if relation == 'unrelated' and visible:
                    continue
                check(level, (max(0, anchor - 83), 116 + row * 120, room, 0, 2, 6, row, anchor),
                      relation, visible, 'view_projection_controls')

    level = prince['LEVL'][2009]['data']
    for tile, x, anchor, mark, driver in product((0, 1), range(8), (0, 153), (-1, 0, 1), (False, True)):
        supplied = bytearray(level)
        for cell in range(30):
            struct.pack_into('>H', supplied, cell * 2, tile)
        check(supplied, (x, 236, 1, mark, 100, 6, 1, anchor), 'current', True,
              'band_phase_and_deletion_controls', driver=driver)
    for height6, height7, width6, y, anchor, clip in product(
            (131, 132), (132, 133), (20, 82), (5, 6, 125, 236), (-1, 0, 83),
            ((0, 0, 365, 510), (1000, 1000, 1100, 1100))):
        heights, widths = list(machine.default_heights), list(machine.default_widths)
        heights[6], heights[7], widths[6] = height6, height7, width6
        check(level, (0, y, 1, 0, 0, 6, 1, anchor), 'current', True,
              'dimension_clip_and_row_controls', heights=heights, widths=widths, clip=clip)
    if set(machine.branches) != {'upper_band_gap', 'upper_band_filled', 'trailing_type6', 'decoration_tile'}:
        raise AssertionError('A declared native presentation branch was not reached')
    return dict(
        cases=dict(counts), native_objects_appended=objects_appended,
        native_branches=dict(machine.branches), mismatches=0,
        outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
        level_hashes=level_hashes, heights=machine.default_heights, widths=machine.default_widths,
        decorations=machine.decorations,
        supplied=[
            '5:3960 visibility boolean; queried room/cell recorded',
            '5:19f8 redraw-queue sink: records callback/rectangle/flag, no redraw list mutation',
            'SectRect callback via A5-1f58: supplied rectangle intersection and Pascal cleanup',
            'OffsetRect trap5:33d0: supplied signed rectangle translation and Pascal cleanup',
        ],
        scope=('Full ATMSlideRock10:1456, decoration loop10:13ca, native geometry, '
               'IndexCell/GetRow/FirstInRow, MarkMobRedraw5:33fa, AddMobObj5:346a '
               'and ComputeMobRect5:32f6; direct and actual ATMLoose/type6 dispatch. '
               'Raw28-byte object writes/count/tail guards, events, restored mob/bank, '
               'dimension tables, cache and unchanged level/actors compared. '
               'No SHAP cache or pixel/resource-loading service needed at this queue stage. '
               'Supplied view/visibility/clip/dimensions; no raster rendering, real visibility '
               'admission, FrameAdv, motion/death cadence, object-capacity safety or saves claim.'),
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
