"""Bound original type0 drawing setup and sprite collision edges, not rasterization."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word, supporting_column
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_kid_frames import NativeKidFrameSupport, kid_frame_reference, verify_frames
from tools.probe_temple_slide_rock_motion import trunc_div
from tools.probe_temple_slide_rock_update import actor_word


BOUNDS_RANGES = {3: ((0x0ac8, 0x0ba2),), 4: ((0x3afa, 0x3b24), (0x5cbc, 0x5e5c), (0x5e6e, 0x5eac))}
SECT_RECT = 0xe1000
LIBRARY, SPECIAL_LIBRARY = 0xe2000, 0xe2010
DEFAULT_RECT = (701, 709, 719, 727)
SCREEN_RECT = (0, 0, 365, 510)
BOUND_WORDS = tuple(range(-0x356c, -0x355e, 2))
CELL_WORDS = tuple(range(-0x34a4, -0x349c, 2))


def shape_sizes(kid):
    base = struct.unpack_from('>H', kid['SHPL'][25001]['data'])[0]
    return {number - base: struct.unpack_from('>hH', item['data'], 4)
            for number, item in kid['SHAP'].items() if number >= base}


def drawing_reference(actor, metadata, drawing):
    if len(actor) != 62 or len(metadata) != 18 or len(drawing) != 20 or actor_word(actor, 8) != 0:
        raise ValueError('Only complete type0 actor/metadata/drawing fixtures are bounded')
    result = bytearray(drawing)
    attachment_shape, frame_shape = struct.unpack_from('>h', metadata, 2)[0], struct.unpack_from('>h', metadata, 8)[0]
    if actor_word(actor, 10) and (frame_shape != -1 or attachment_shape != -1):
        dx, dy = struct.unpack_from('>2h', metadata, 12)
        facing = actor_word(actor, 2)
        values = {0: facing, 2: signed_word(actor_word(actor, 4) + (dx if facing == 0 else -dx) - 207),
                  4: signed_word(actor_word(actor, 6) + dy), 6: frame_shape, 8: 2, 18: actor_word(actor, 54)}
        for offset, value in values.items():
            struct.pack_into('>h', result, offset, value)
    return bytes(result)


def row_reference(y):
    adjusted = signed_word(y - 5)
    return trunc_div(adjusted, 120) - int(adjusted <= 0)


def bounds_reference(actor, metadata, drawing, sizes, bounds, cells, remainder,
                     *, default_rect=DEFAULT_RECT, screen=SCREEN_RECT, available=True):
    """Independent4:5cbc model, SHAP dimensions supplied from preserved headers."""
    if actor_word(actor, 8) != 0 or actor_word(actor, 2) not in (-1, 0):
        raise ValueError('Only the two type0 facings are bounded')
    working = bytearray(actor)
    struct.pack_into('>4h', working, 42, *default_rect)
    facing, x, y, shape, library = struct.unpack_from('>5h', drawing)
    services = []
    if shape == -1:
        return dict(actor=bytes(working), bounds=bounds, cells=cells, remainder=remainder, services=services)
    if library != 2:
        raise ValueError('Only the prepared Kid shape library is bounded')
    services.append(('shape_size', shape))
    if not available or shape not in sizes:
        return dict(actor=bytes(working), bounds=bounds, cells=cells, remainder=remainder, services=services)
    width, height = sizes[shape]
    extension = 0
    if actor_word(actor, 26) == 1 and struct.unpack_from('>h', metadata)[0]:
        extension = max(0, struct.unpack_from('>h', metadata, 4)[0] - 3)
    width_plus = signed_word(width + 1)
    left = signed_word(x + 207 - (width_plus if actor_word(actor, 2) == 0 else extension))
    total_width = signed_word(width_plus + extension)
    right = signed_word(left + total_width)
    top = min(365, signed_word(y - height + 1))
    values = (top, right, left, right, left, total_width, signed_word(height))
    rect = (top, x if actor_word(actor, 2) == -1 else signed_word(x - width),
            signed_word(y + 1), signed_word(x + width) if actor_word(actor, 2) == -1 else x)
    intersection = (max(rect[0], screen[0]), max(rect[1], screen[1]), min(rect[2], screen[2]), min(rect[3], screen[3]))
    services.append(('sect_rect', rect))
    if intersection[0] < intersection[2] and intersection[1] < intersection[3]:
        struct.pack_into('>4h', working, 42, *intersection)
    first_row, last_row = row_reference(top), row_reference(y)
    if last_row == -1:
        last_row = 3
    # GetCharEdges calls5:48b0 directly, without GetCharCol's -22 adjustment.
    first_column, _ = supporting_column(signed_word(left + 22), 0, bytes(10))
    last_column, remainder = supporting_column(signed_word(right + 22), 0, bytes(10))
    return dict(actor=bytes(working), bounds=values,
                cells=(max(0, first_column), min(9, last_column), first_row, last_row),
                remainder=remainder, services=services)


def bind_bounds(machine):
    machine.cpu.mem_write(machine.A5 - 0x1f58, struct.pack('>I', SECT_RECT))
    machine.cpu.mem_write(machine.A5 - 0x4a90, struct.pack('>I', LIBRARY))
    machine.cpu.mem_write(machine.A5 - 0x4a88, struct.pack('>I', SPECIAL_LIBRARY))
    machine.cpu.mem_write(machine.A5 - 0x196c, struct.pack('>4h', *DEFAULT_RECT))
    machine.cpu.mem_write(machine.A5 - 0x4fec, struct.pack('>4h', *SCREEN_RECT))


def bounds_service(machine, cpu, address):
    if address not in (SECT_RECT, machine.address(17, 0x673a), machine.address(3, 0x533a)):
        return False
    stack = cpu.reg_read(machine.registers['a7'])
    if address == SECT_RECT:
        destination, source, clip = struct.unpack('>3I', cpu.mem_read(stack + 4, 12))
        rect, screen = struct.unpack('>4h', cpu.mem_read(source, 8)), struct.unpack('>4h', cpu.mem_read(clip, 8))
        machine.bound_events.append(('sect_rect', rect))
        intersection = (max(rect[0], screen[0]), max(rect[1], screen[1]), min(rect[2], screen[2]), min(rect[3], screen[3]))
        valid = intersection[0] < intersection[2] and intersection[1] < intersection[3]
        cpu.mem_write(destination, struct.pack('>4h', *(intersection if valid else (0, 0, 0, 0))))
        cpu.mem_write(stack + 16, bytes((int(valid),)))
        cpu.reg_write(machine.registers['a7'], stack + 16)
    elif address in (machine.address(17, 0x673a), machine.address(3, 0x533a)):
        if address == machine.address(17, 0x673a):
            library, number, point = struct.unpack('>IhI', cpu.mem_read(stack + 4, 10))
            if library != LIBRARY:
                raise AssertionError('Unexpected shape library')
            shape = number - 1
        else:
            shape, point = struct.unpack('>hI', cpu.mem_read(stack + 4, 6))
        machine.bound_events.append(('shape_size', shape))
        valid = machine.shape_available and shape in machine.sizes
        if valid:
            width, height = machine.sizes[shape]
            cpu.mem_write(point, struct.pack('>2h', signed_word(height), width))
        cpu.reg_write(machine.registers['d0'], int(valid))
        cpu.reg_write(machine.registers['a7'], stack + 4)
    else:
        return False
    cpu.reg_write(machine.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])
    return True


class NativeTempleSpriteBounds(NativeKidFrameSupport):
    RANGES = {s: NativeKidFrameSupport.RANGES.get(s, ()) + BOUNDS_RANGES.get(s, ())
              for s in NativeKidFrameSupport.RANGES.keys() | BOUNDS_RANGES.keys()}

    def __init__(self, program, frames, attachments, sizes):
        super().__init__(program, frames, attachments)
        self.sizes = sizes
        self.bound_events = []
        self.shape_available = True

    def reset(self, level):
        super().reset(level)
        bind_bounds(self)
        self.bound_events = []

    def dispatch(self, cpu, address, size, user):
        if not bounds_service(self, cpu, address):
            super().dispatch(cpu, address, size, user)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    kid = parse_resource_fork((directory / 'Kid.rsrc.bin').read_bytes())
    frames, attachments, sizes = kid['FRAM'][25001]['data'], kid['AFRM'][25001]['data'], shape_sizes(kid)
    machine = NativeTempleSpriteBounds(parse_resource_fork(executable), frames, attachments, sizes)
    level = prince['LEVL'][2009]['data']
    counts, digest = Counter(), hashlib.sha256()
    drawing = struct.pack('>10h', -1, 53, 59, -1, 2, 61, 67, 71, 73, 79)
    initial_bounds, initial_cells = (101, 103, 107, 109, 113, 127, 131), (137, 139, 149, 151)
    saved, cache, bank = bytes(range(62)), bytes(range(12)), bytes(range(160))
    positions = ((207, -121), (258, 0), (400, 110), (717, 365), (740, 500), (-32768, 32767))
    for pose, facing, armed, (x, y), available, special in product(
            range(352), (-1, 0), (0, 1), positions, (False, True), (False, True)):
        actor = bytearray(actor_fixture(3, 1, 2, facing, 2))
        for offset, value in ((4, x), (6, y), (10, pose), (26, armed), (54, 83)):
            put_actor(actor, offset, value)
        loaded = kid_frame_reference(actor, frames, attachments)
        drawn = drawing_reference(loaded['actor'], loaded['metadata'], drawing)
        expected = bounds_reference(loaded['actor'], loaded['metadata'], drawn, sizes, initial_bounds, initial_cells,
                                    loaded['remainder'], available=available)
        machine.reset(level)
        machine.shape_available = available
        if special:
            machine.cpu.mem_write(machine.A5 - 0x4a88, struct.pack('>I', LIBRARY))
        for offset, data in ((-0x5056, bytes(actor)), (-0x50d2, saved), (-0x34b0, cache),
                             (-0x448e, bank), (-0x34c6, drawing)):
            machine.cpu.mem_write(machine.A5 + offset, data)
        for offsets, values in ((BOUND_WORDS, initial_bounds), (CELL_WORDS, initial_cells)):
            for offset, value in zip(offsets, values):
                machine.put_word(offset, value)
        machine.call(4, 0x2a72)
        machine.call(3, 0x0ac8)
        machine.call(4, 0x5cbc)
        actual = dict(actor=bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)),
                      bounds=tuple(machine.word(o) for o in BOUND_WORDS), cells=tuple(machine.word(o) for o in CELL_WORDS),
                      remainder=machine.word(-0x481c), services=machine.bound_events)
        if (actual != expected or bytes(machine.cpu.mem_read(machine.A5 - 0x34c6, 20)) != drawn
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != saved
                or bytes(machine.cpu.mem_read(machine.A5 - 0x34b0, 12)) != cache
                or bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)) != bank
                or bytes(machine.cpu.mem_read(machine.A5 - 0x521a, 18)) != loaded['metadata']
                or bytes(machine.cpu.mem_read(machine.A5 - 0x196c, 8)) != struct.pack('>4h', *DEFAULT_RECT)
                or bytes(machine.cpu.mem_read(machine.A5 - 0x4fec, 8)) != struct.pack('>4h', *SCREEN_RECT)
                or machine.level_bytes(len(level)) != level or machine.services):
            raise AssertionError(dict(inputs=(pose, facing, armed, x, y, available, special),
                                      actual=actual, expected=expected, drawing=drawn.hex()))
        verify_frames(machine)
        counts['available' if available else 'unavailable'] += 1
        counts['imageless' if struct.unpack_from('>h', drawn, 6)[0] == -1 else 'image'] += 1
        counts['special_library' if special else 'ordinary_library'] += 1
        digest.update(actual['actor'] + drawn + struct.pack('>12h', *actual['bounds'], *actual['cells'], actual['remainder']))
        digest.update(json.dumps(actual['services']).encode('ascii'))
    return dict(comparisons=sum(counts[k] for k in ('available', 'unavailable')), mismatches=0,
                cases=dict(counts), outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
                supplied=['17:673a/3:533a dimensions from original Kid SHAP headers or controlled failure',
                          'SectRect callback: explicit half-open intersection with supplied screen rectangle',
                          'Prepared Kid frame/attachment/library bindings, initial drawing/edge canaries'],
                scope='Actual type0 LoadFrame, SetupSword and GetCharEdges, including sword extent, clipping, row/column '
                      'and unavailable-image preservation. No resource loader, rasterization, contact/physics, world or runtime changes.')


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
