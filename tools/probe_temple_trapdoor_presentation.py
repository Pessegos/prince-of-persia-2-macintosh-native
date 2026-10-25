"""Probe native trap-door presentation/restoration with prepared image-cache headers."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_trapdoors import NativeTempleTrapDoors


VIEW_FIELDS = dict(current=-0x4fc2, above=-0x4fba, below=-0x4fbc,
                   right=-0x4fc0, left=-0x4fbe)


def trunc_divide(value, divisor):
    return abs(value) // divisor * (-1 if value < 0 else 1)


def view_for(room, relation):
    if relation not in (*VIEW_FIELDS, 'unrelated'):
        raise ValueError('Unknown supplied view relationship')
    view = dict(current=room % 32 + 1, above=0, below=0, right=0, left=0)
    if relation != 'unrelated':
        view[relation] = room
    return view


def project(mob, view):
    x, y, room = mob[:3]
    if room != view['current']:
        for relation, dx, dy in (('above', 0, 364), ('below', 0, -364),
                                 ('right', -510, 0), ('left', 510, 0)):
            if room == view[relation]:
                x, y, room = x + dx, y + dy, view['current']
                break
    return x, y, room


def intersect_rect(first, second):
    top, left = max(first[0], second[0]), max(first[1], second[1])
    bottom, right = min(first[2], second[2]), min(first[3], second[3])
    return (top, left, bottom, right) if top < bottom and left < right else (0, 0, 0, 0)


def presentation_reference(level, mob, view, visible, pending_cue, mapping, frames, clip):
    if visible and mob[2] != view['current']:
        raise ValueError('Visible neighboring-room drawing is outside this probe domain')
    phase = mob[7] & 31
    if phase == 0:
        raise ValueError('Phase zero is outside the valid presentation-table domain')
    result, state = bytearray(level), list(mob)
    x, y, room = project(mob, view)
    column, row = trunc_divide(x, 51), trunc_divide(y, 120)
    screen_cell = row * 10 + column if 0 <= row < 3 and 0 <= column < 10 else 30
    sounds, resets = [], []
    if phase > 16:
        state[3] = -1
        original_cell = mob[6] * 10 + trunc_divide(mob[0], 51)
        tile = (mob[2] - 1) * 60 + original_cell * 2
        foreground = 0x780 + (mob[2] - 1) * 120 + original_cell * 4
        struct.pack_into('>H', result, tile, 26)
        value = struct.unpack_from('>H', result, foreground)[0] & 0xff00
        struct.pack_into('>H', result, foreground, value)
        resets.append(198)
        sounds.append(27)
        if pending_cue == 198:
            pending_cue = -1
    frame = frames[mapping[min(phase, 17)]]
    shape, dx, dy, width, height = frame
    sizes, redraw, rectangles, draws = [], [], [], []
    dimensions = (91, 92)
    if visible:
        sizes.append(shape - 1)
        temporary = list(state)
        temporary[0], temporary[1] = x + dx, mob[1] + dy
        dimensions = (height + 1, max(width + 1, column * 51 + 77 - temporary[0]))
        redraw.append(0)
        if state[3] != -1:
            rectangle = (temporary[1] - dimensions[0], temporary[0] + 25,
                         temporary[1] + 1, temporary[0] + dimensions[1])
            rectangles.append(intersect_rect(rectangle, clip))
            draws.append(dict(y=y + dy, mob=tuple(temporary), dimensions=dimensions))
    return dict(level=bytes(result), mob=tuple(state), pending_cue=pending_cue,
                screen_cell=screen_cell, visibility=[(room, mob[6] * 10 + column)],
                sounds=sounds, resets=resets, sizes=sizes, redraw=redraw,
                dimensions=dimensions, rectangles=rectangles, draws=draws)


class NativeTrapDoorPresentation(NativeTempleTrapDoors):
    RANGES = {
        3: ((0x533a, 0x53fe),),
        4: NativeTempleTrapDoors.RANGES[4] + ((0x29d8, 0x2a62),),
        5: NativeTempleTrapDoors.RANGES[5] + ((0x307c, 0x3126), (0x32f6, 0x33e6)),
        10: NativeTempleTrapDoors.RANGES[10] + ((0x225c, 0x24e8),),
    }
    SHAPE_INFO, HANDLES, HEADERS, INTERSECT = 0xb1000, 0xb2000, 0xb3000, 0xb8000

    def __init__(self, program, temple):
        super().__init__(program)
        self.mapping = struct.unpack_from('>18h', self.data, len(self.data) - 0x2866)
        self.frames = []
        self.cpu.mem_write(self.SHAPE_INFO, bytes(0x1000))
        base = struct.unpack_from('>H', temple['SHPL'][3500]['data'])[0]
        for index in range(5):
            shape, dx, dy = struct.unpack_from('>3h', self.data, len(self.data) - 0x2842 + index * 6)
            header = temple['SHAP'][base + shape - 1]['data'][:8]
            width, height = struct.unpack_from('>2H', header, 4)
            self.frames.append((shape, dx, dy, width, height))
            handle, cached = self.HANDLES + (shape - 1) * 4, self.HEADERS + (shape - 1) * 8
            self.cpu.mem_write(cached, header)
            self.cpu.mem_write(handle, struct.pack('>I', cached))
            self.cpu.mem_write(self.SHAPE_INFO + 8 + (shape - 1) * 10 + 6, struct.pack('>I', handle))
        if any(not 0 <= index < len(self.frames) for index in self.mapping[1:]):
            raise ValueError('Unexpected trap-door frame mapping')

    def reset(self, level):
        super().reset(level)
        self.visibility, self.resets, self.sizes, self.rectangles, self.draws = [], [], [], [], []
        self.visible = False
        self.cpu.mem_write(self.A5 - 0x4a88, struct.pack('>I', self.SHAPE_INFO))
        self.cpu.mem_write(self.A5 - 0x1f58, struct.pack('>I', self.INTERSECT))

    def dispatch(self, cpu, address, size, user):
        if address == self.address(3, 0x533a):
            stack = cpu.reg_read(self.registers['a7'])
            self.sizes.append(struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0])
        if address == self.INTERSECT:
            stack = cpu.reg_read(self.registers['a7'])
            destination, output, first, second = struct.unpack('>4I', cpu.mem_read(stack, 16))
            rect = intersect_rect(struct.unpack('>4h', cpu.mem_read(first, 8)),
                                  struct.unpack('>4h', cpu.mem_read(second, 8)))
            cpu.mem_write(output, struct.pack('>4h', *rect))
            cpu.mem_write(stack + 16, bytes((int(rect != (0, 0, 0, 0)), 0)))
            cpu.reg_write(self.registers['a7'], stack + 16)
            cpu.reg_write(self.registers['pc'], destination)
            return
        if address in (self.address(5, 0x3960), self.address(5, 0x5252),
                       self.address(5, 0x19f8), self.address(5, 0x346a)):
            stack = cpu.reg_read(self.registers['a7'])
            if address == self.address(5, 0x3960):
                self.visibility.append(struct.unpack('>2h', cpu.mem_read(stack + 4, 4)))
                cpu.reg_write(self.registers['d0'], int(self.visible))
            elif address == self.address(5, 0x5252):
                self.resets.append(struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0])
            elif address == self.address(5, 0x19f8):
                callback, rectangle, flag = struct.unpack('>IIh', cpu.mem_read(stack + 4, 10))
                if callback != self.A5 + 0x3ba or flag != -1:
                    raise AssertionError('Unexpected redraw callback/flag')
                self.rectangles.append(struct.unpack('>4h', cpu.mem_read(rectangle, 8)))
            else:
                y = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
                self.draws.append(dict(y=y, mob=self.mob(), dimensions=self.dimensions()))
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], destination)
            return
        super().dispatch(cpu, address, size, user)

    def mob(self):
        return struct.unpack('>8h', self.cpu.mem_read(self.A5 - 0x44a6, 16))

    def dimensions(self):
        return self.word(-0x4504), self.word(-0x44e8)

    def configure(self, level, mob, view, visible, pending_cue, clip):
        self.reset(level)
        self.cpu.mem_write(self.A5 - 0x44a6, struct.pack('>8h', *mob))
        self.cpu.mem_write(self.A5 - 0x4fec, struct.pack('>4h', *clip))
        self.put_word(-0x4504, 91)
        self.put_word(-0x44e8, 92)
        self.put_word(-0x439e, pending_cue)
        for name, value in view.items():
            self.put_word(VIEW_FIELDS[name], value)
        self.visible = visible


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    temple_bytes = (directory / 'Temple.rsrc.bin').read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeTrapDoorPresentation(parse_resource_fork(program_bytes), parse_resource_fork(temple_bytes))
    counts = Counter()
    digest = hashlib.sha256()
    clip = (-1000, -1000, 2000, 2000)
    scenarios = [('current', True), *[(relation, False) for relation in (*VIEW_FIELDS, 'unrelated')]]
    for number in range(10, 14):
        level = prince['LEVL'][1999 + number]['data']
        for room in range(1, 33):
            for cell in range(30):
                if struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0] != 26:
                    continue
                for phase, high, (relation, visible), pending in product(
                        range(1, 32), (0, 64), scenarios, (-1, 198)):
                    supplied = bytearray(level)
                    struct.pack_into('>H', supplied, (room - 1) * 60 + cell * 2, 0)
                    struct.pack_into('>H', supplied, 0x780 + (room - 1) * 120 + cell * 4, 0xa581)
                    row, column = divmod(cell, 10)
                    mob = (column * 51, (row + 1) * 120 + 5, room, 0, 0, 10, row, high + phase)
                    view = view_for(room, relation)
                    machine.configure(supplied, mob, view, visible, pending, clip)
                    expected = presentation_reference(supplied, mob, view, visible, pending,
                                                      machine.mapping, machine.frames, clip)
                    machine.call(10, 0x225c)
                    actual = dict(level=machine.level_bytes(len(level)), mob=machine.mob(),
                                  pending_cue=machine.word(-0x439e), screen_cell=machine.word(-0x34c8),
                                  visibility=machine.visibility, sounds=machine.sounds, resets=machine.resets,
                                  sizes=machine.sizes, redraw=machine.redraw, dimensions=machine.dimensions(),
                                  rectangles=machine.rectangles, draws=machine.draws)
                    if actual != expected:
                        different = {key: (actual[key], expected[key]) for key in expected
                                     if actual[key] != expected[key] and key != 'level'}
                        raise AssertionError(dict(level=number, room=room, cell=cell, phase=high + phase,
                                                  relation=relation, visible=visible, different=different,
                                                  level_diff=actual['level'] != expected['level']))
                    counts['presentation'] += 1
                    counts['visible_current_room'] += visible
                    counts['terminal_restore'] += phase > 16
                    digest.update(actual['level'] + struct.pack('>8h', *actual['mob']))
    return dict(
        cases=dict(counts), mismatches=0, outputs_sha256=digest.hexdigest(),
        executable_sha256=hashlib.sha256(program_bytes).hexdigest(),
        temple_sha256=hashlib.sha256(temple_bytes).hexdigest(),
        supplied=['5:3960 visibility result supplied, request checked',
                  '5:5252 sound reset and5:4d84 sound request recorded, no playback',
                  '5:33fa/19f8 redraw and5:346a object draw recorded, no rendering',
                  'A5-1f58 SectRect callback: supplied rectangle intersection/Pascal stack cleanup',
                  'Prepared image-cache items/handles with actual Temple SHAP header bytes'],
        scope=('Full ATMTrapDoor10:225c, native IndexCell1/FirstInRow, cached '
               'GetBGSetImgSize and current-room ComputeMobRect. Low phases1..31 with '
               'upperbit0/64; actual door locations, supplied object/view/visibility/pending '
               'cue state. All relations tested invisible; only current room drawn. No pixels, '
               'resource loading, visible-neighbor rectangle offsets, animation advancement, '
               'full-frame scheduling, collision or campaign equivalence claim.'),
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
