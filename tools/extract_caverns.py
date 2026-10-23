"""Export native level-three scenery drawing commands during asset import."""

import json
import struct
from difflib import SequenceMatcher
from itertools import product
from functools import lru_cache, partial
from math import prod

from pop2.caverns import SCENERY_LEVELS, entry_room, scenery_name
from pop2.crevices import CREVICE_TILE, hide_crevices
from pop2.mac_resources import parse_resource_fork
from pop2.terrain import LevelMap
from tools.extract_enemy_profiles import expand_a5_data
from pop2.loose_floors import cleared_below_cell, rubble_tile, space_foreground
from pop2.opponent_generation import EMPTY_TILES
from tools.extract_lava import lava_tables
from tools.extract_attract import jump_targets


SECT_RECT_7 = (0x1f2e, 0x1f8c, 0x2760, 0x2b1a)
UNION_RECT_7 = (0x1f48, 0x1fa2)
# Entries of each environment's piece-drawing table (a5-0x4aea + 4 * env):
# the caverns' table covers kinds 0-44, the ruins' kinds 0-23.
DRAW_KINDS = {3: 45, 4: 24}
# Shape libraries: 0 sword items and 1 flasks (Prince.rsrc), 4 scenery.
LIBRARY_BASE = {0: 1000, 1: 3000, 4: 3500}


@lru_cache(maxsize=1)
def recovery_inputs(program, caverns, prince):
    resources = parse_resource_fork(program)
    primitives = {(3, offset) for offset in (4, 0x29e2, 0x29b6, 0x2ac4, 0x06c4, 0x2324, 0x26e4, 0x2482, 0x2438)}
    primitives.update((5, offset) for offset in (0x21c, 0x230, 0x08c4, 0x1990))
    primitives.update((8, offset) for offset in (0x176c, 0x20a6, 0x1ca4, 0x1752, 0x1f86))
    # The ruins drawers (CODE 7) call the same SectRect (a5-0x1f58) and
    # UnionRect (a5-0x1f5c) glue.
    primitives.update((7, offset) for offset in SECT_RECT_7 + UNION_RECT_7)
    # Every OffsetRect trap (A8A8): bridge and custom-room pieces use it at
    # 8:07fe, 8:085a and 3:120a, besides 5:021c.
    for segment in (3, 5, 7, 8):
        code = resources['CODE'].get(segment, {}).get('data', b'')
        primitives.update((segment, offset) for offset in range(0, len(code) - 1, 2)
                          if code[offset:offset + 2] == b'\xa8\xa8')
    intercepts = {}
    # Native A5 calls use relocated jump-table stubs. Only modeled
    # services need instruction hooks; other traps fail in Unicorn.
    for segment, offset in sorted(primitives):
        code = resources['CODE'].get(segment, {}).get('data', b'')
        if offset + 2 <= len(code):
            intercepts[0x100000 + segment * 0x10000 + offset] = code[offset:offset + 2]
    return (resources, parse_resource_fork(caverns),
            parse_resource_fork(prince) if prince is not None else None,
            expand_a5_data(resources), intercepts)


class CavernRecovery:
    """Reuse compiled code, restoring working RAM and CPU state per draw."""

    def __init__(self, program, caverns, prince):
        from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
        from unicorn.m68k_const import UC_CPU_M68K_M68000

        resources, artwork, _flasks, data, intercepts = recovery_inputs(program, caverns, prince)
        self.cpu = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        self.cpu.ctl_set_cpu_model(UC_CPU_M68K_M68000)
        self.cpu.mem_map(0, 0x1000000)
        for segment, resource in resources['CODE'].items():
            if segment:
                self.cpu.mem_write(0x100000 + segment * 0x10000, resource['data'])
        for offset, destination in jump_targets(resources['CODE'][0]['data'], resources['CODE']):
            self.cpu.mem_write(0x80000 + offset, b'\x4e\xf9' + struct.pack('>I', 0x100000 + destination))
        self.cpu.mem_write(0x80000 - len(data), data)
        self.cpu.mem_write(0x91000, artwork['PIEC'][3500]['data'])
        self.initial_ram = bytes(self.cpu.mem_read(0, 0x100000))
        self.initial_cpu = self.cpu.context_save()
        self.callback = None
        self.closed = False
        self.handles = [self.cpu.hook_add(UC_HOOK_CODE, self.dispatch, begin=address, end=address)
                        for address in intercepts]

    def dispatch(self, cpu, address, size, user):
        self.callback(cpu, address, size, user)

    def reset(self):
        if self.closed:
            raise RuntimeError('Cavern recovery is closed')
        if self.callback is not None:
            raise RuntimeError('Cavern recovery is already drawing')
        self.cpu.context_restore(self.initial_cpu)
        self.cpu.mem_write(0, self.initial_ram)
        return self.cpu

    def close(self):
        if self.closed:
            return
        self.callback = None
        try:
            for handle in self.handles:
                self.cpu.hook_del(handle)
        finally:
            self.handles.clear()
            self.cpu.mem_unmap(0, 0x1000000)
            self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *_error):
        self.close()


def recover_room(program, caverns, level, room_id=0, prince=None, climb_action=None,
                 floor_redraw=False, *, _machine=None, _native_scene=False):
    if _machine is None:
        with CavernRecovery(program, caverns, prince) as machine:
            return recover_room(program, caverns, level, room_id, prince, climb_action,
                                floor_redraw, _machine=machine, _native_scene=_native_scene)

    from unicorn.m68k_const import (
        UC_M68K_REG_A5, UC_M68K_REG_A7,
        UC_M68K_REG_A0, UC_M68K_REG_D0, UC_M68K_REG_PC,
    )

    resources, artwork, flasks, data, intercepts = recovery_inputs(program, caverns, prince)
    cpu = _machine.reset()
    a5, stack, end, info, pieces, lev = 0x80000, 0xf0000, 0xff000, 0x90000, 0x91000, 0xa0000
    bases = {segment: 0x100000 + segment * 0x10000 for segment in resources['CODE'] if segment}
    cpu.mem_write(lev, level)

    def put_word(address, value):
        cpu.mem_write(address, struct.pack('>H', value & 65535))

    def put_long(address, value):
        cpu.mem_write(address, struct.pack('>I', value))

    def word(address):
        return struct.unpack('>h', cpu.mem_read(address, 2))[0]

    def long(address):
        return struct.unpack('>I', cpu.mem_read(address, 4))[0]

    jump = resources['CODE'][0]['data']

    def target(pointer):
        offset, opcode, segment, trap = struct.unpack_from('>4H', jump, 16 + pointer - 0x22)
        if opcode != 0x3f3c or trap != 0xa9f0 or segment not in bases:
            raise ValueError('Unsupported cavern jump table')
        return bases[segment] + offset + 4

    environment = struct.unpack_from('>H', level, 0x2186)[0]
    if environment not in DRAW_KINDS:
        raise ValueError(f'Unsupported scenery environment {environment}')
    table_offset = struct.unpack_from('>i', data, len(data) - 0x4aea + environment * 4)[0]
    dispatch = 0x92000
    for kind in range(DRAW_KINDS[environment]):
        pointer = struct.unpack_from('>i', data, len(data) + table_offset + kind * 4)[0]
        put_long(dispatch + kind * 4, target(pointer) if pointer else 0)
    put_long(a5 - 0x4aae, dispatch)
    put_long(a5 - 0x4f8c, info)
    put_long(a5 - 0x4b9e, pieces)
    put_long(a5 - 0x5014, lev)
    # LoadCustomRoomData 3:1378-13d6 locks CUST room*25+3975 at a5-0x4c9e for
    # customized rooms (foreground bits 0xc000, IsCustomizedRoom 3:1310).
    customized = any(struct.unpack_from('>H', level, 0x780 + room_id * 120 + cell * 4)[0] & 0xc000
                     for cell in range(30))
    custom = (artwork['CUST'].get(3975 + (room_id + 1) * 25)
              if artwork is not None and customized else None)
    if custom is not None:
        cpu.mem_write(0x94000, custom['data'])
        put_long(a5 - 0x4c9e, 0x94000)
    put_long(a5 - 0x4ab2, 0)  # No actor-specific gate peeling in a static scene.
    # DoCleanCut 2:608c-6096 builds scenery with full-room repaint enabled.
    # Per-cell redraws change the overlap order of adjacent exit pieces.
    put_word(a5 - 0x4832, int(climb_action is None and not floor_redraw))
    put_word(a5 - 0x4fc2, room_id + 1)
    if climb_action is not None:
        if not 135 <= climb_action <= 144:
            raise ValueError('DrawHalf requires a native climbing pose')
        put_word(a5 - 0x50c8, climb_action)
    for offset in (0x4600, 0x4fec):
        cpu.mem_write(a5 - offset, struct.pack('>4h', 0, 0, 365, 510))
    terrain = LevelMap(level)
    commands = []
    command_kinds = []
    torches = []
    history = []
    previous_items = {}
    back_items = []
    back_rect = None

    def reset_item(draw_pass, previous=False):
        cpu.mem_write(info, bytes(38))
        for index, value in ((0, 4), (1, word(a5 - 0x45f8)), (2, word(a5 - 0x45f6)),
                             (3, 16), (5, draw_pass)):
            put_word(info + index * 2, value)
        if previous:
            table = 'front' if draw_pass in (1, 2) else 'back'
            cpu.mem_write(info + 14, previous_items[table][14:24])
        put_long(a5 - 0x4f8c, info)

    def hook(cpu, address, size, _user):
        nonlocal back_rect
        opcode = intercepts[address]
        history.append(hex(address))
        del history[:-15]
        sp = cpu.reg_read(UC_M68K_REG_A7)
        segment = (address - 0x100000) // 0x10000
        offset = address - bases.get(segment, address)
        result = None
        if opcode == b'\xa8\xa8':  # OffsetRect(rect, dh, dv)
            dy, dx, rect_pointer = word(sp), word(sp + 2), long(sp + 4)
            top, left, bottom, right = struct.unpack('>4h', cpu.mem_read(rect_pointer, 8))
            cpu.mem_write(rect_pointer, struct.pack('>4h', top + dy, left + dx, bottom + dy, right + dx))
            cpu.reg_write(UC_M68K_REG_A7, sp + 8)
            cpu.reg_write(UC_M68K_REG_PC, address + 2)
            return
        if opcode == b'\x4e\x90' and (segment == 8 and offset == 0x176c
                                      or segment == 7 and offset in UNION_RECT_7):
            out, first, second = (long(sp + i) for i in (0, 4, 8))
            r1 = struct.unpack('>4h', cpu.mem_read(first, 8))
            r2 = struct.unpack('>4h', cpu.mem_read(second, 8))
            rect = [min(r1[0], r2[0]), min(r1[1], r2[1]), max(r1[2], r2[2]), max(r1[3], r2[3])]
            cpu.mem_write(out, struct.pack('>4h', *rect))
            if out == 0x93000 + 30 and back_rect is not None:
                back_rect[:] = rect
            cpu.reg_write(UC_M68K_REG_A7, sp + 12)
            cpu.reg_write(UC_M68K_REG_PC, address + 2)
            return
        if opcode == b'\x4e\x90' and segment == 8 and offset == 0x20a6:
            top, left, bottom, right = struct.unpack('>4h', cpu.mem_read(long(sp), 8))
            cpu.mem_write(sp + 4, bytes([int(top >= bottom or left >= right), 0]))
            cpu.reg_write(UC_M68K_REG_A7, sp + 4)
            cpu.reg_write(UC_M68K_REG_PC, address + 2)
            return
        if (opcode == b'\x4e\x90'
                and (segment == 8 and offset in (0x1ca4, 0x1752, 0x1f86)
                     or segment == 7 and offset in SECT_RECT_7
                     or segment == 5 and offset == 0x230 or segment == 3 and offset == 0x2482)):
            out, first, second = (long(sp + i) for i in (0, 4, 8))
            r1 = struct.unpack('>4h', cpu.mem_read(first, 8))
            r2 = struct.unpack('>4h', cpu.mem_read(second, 8))
            rect = (max(r1[0], r2[0]), max(r1[1], r2[1]), min(r1[2], r2[2]), min(r1[3], r2[3]))
            cpu.mem_write(out, struct.pack('>4h', *rect))
            cpu.mem_write(sp + 12, bytes([int(rect[0] < rect[2] and rect[1] < rect[3]), 0]))
            cpu.reg_write(UC_M68K_REG_A7, sp + 12)
            cpu.reg_write(UC_M68K_REG_PC, address + 2)
            return
        if segment == 3 and offset == 4 and not long(a5 - 0x4f8c):
            result = 0
        elif segment == 3 and offset == 4:
            fields = struct.unpack('>19h', cpu.mem_read(info, 38))
            draw_column, draw_row = word(a5 - 0x45f8), word(a5 - 0x45f6)
            layer = 'front' if fields[5] in (1, 2) else 'back'
            library = fields[0]
            if library not in LIBRARY_BASE:
                raise ValueError(f'Unsupported cavern shape library {library}')
            shape = LIBRARY_BASE[library] + fields[12]
            source = flasks if library in (0, 1) else artwork
            if source is None or shape not in source['SHAP']:
                raise ValueError(f'Missing library {library} shape {shape}')
            width, height = struct.unpack_from('>hH', source['SHAP'][shape]['data'], 4)
            x, bottom = fields[7] * 51 + fields[13], (fields[8] + 1) * 120 + 5 + fields[14]
            clip = list(struct.unpack('>4h', cpu.mem_read(a5 - 0x4600, 8)))
            result = int(max(x, clip[1]) < min(x + width, clip[3])
                         and max(bottom - height, clip[0]) < min(bottom, clip[2]))
            if result:
                rect = [max(bottom - height, clip[0]), max(x, clip[1]),
                        min(bottom, clip[2]), min(x + width, clip[3])]
                commands.append([layer, shape, x, bottom, fields[3], fields[8], rect, library,
                                 draw_column, draw_row])
                command_kinds.append(fields[9])
                if environment == 3 and library == 4 and 3581 <= shape <= 3589:
                    tile = terrain.tile(room_id, fields[7], fields[8])
                    torches.append({'room': tile.room, 'cell': tile.row * 10 + tile.column,
                                    'foreground': tile.foreground, 'command': commands[-1]})
                table = 'front' if fields[5] in (1, 2) else 'back'
                previous_items[table] = bytes(cpu.mem_read(info, 38))
                if table == 'back':
                    # GetBackTableImgRow 3:06c4 searches admitted BF records
                    # by shape, source column and row, not rendered coordinates.
                    back_items.append((shape, fields[1], fields[2], rect))
                put_long(a5 - 0x4f8c, 0)
        elif segment == 3 and offset == 0x29e2:
            reset_item(word(sp + 4))
            result = 0
        elif segment == 3 and offset == 0x29b6:
            if not long(a5 - 0x4f8c):
                reset_item(word(sp + 4))
            result = 0
        elif segment == 3 and offset == 0x2ac4:
            reset_item(word(sp + 4), previous=True)
            result = 0
        elif segment == 3 and offset == 0x06c4:
            shape, column, row = (word(sp + i) for i in (4, 6, 8))
            match = next((item for item in back_items
                          if item[:3] == (3500 + shape, column, row)), None)
            result = 0
            if match is not None:
                result = 0x93000
                back_rect = match[3]
                cpu.mem_write(result + 30, struct.pack('>4h', *match[3]))
        elif segment == 3 and offset == 0x2438:
            # DrawCustomRoomImg 3:2438-2580: a CUST record of this pass, clipped
            # by a5-0x4600, becomes a back (passes 0/5/11) or front item.
            index, draw_pass = word(sp + 4), word(sp + 6)
            base = long(a5 - 0x4c9e)
            record = base + 30 + index * 32
            shape_index, bottom, x, record_pass, mode, hidden = (
                word(record + i * 2) for i in range(6))
            if base and hidden != -1 and record_pass == draw_pass:
                shape = struct.unpack('>H', cpu.mem_read(base + 2, 2))[0] + shape_index
                if shape not in artwork['SHAP']:
                    raise ValueError(f'Missing custom cavern shape {shape}')
                width, height = struct.unpack_from('>hH', artwork['SHAP'][shape]['data'], 4)
                clip = list(struct.unpack('>4h', cpu.mem_read(a5 - 0x4600, 8)))
                rect = [max(bottom - height, clip[0]), max(x, clip[1]),
                        min(bottom, clip[2]), min(x + width, clip[3])]
                if rect[0] < rect[2] and rect[1] < rect[3]:
                    layer = 'back' if draw_pass in (0, 5, 11) else 'front'
                    commands.append([layer, shape, x, bottom, mode, word(a5 - 0x45f6), rect, 4,
                                     word(a5 - 0x45f8), word(a5 - 0x45f6)])
                    command_kinds.append(word(info + 0x12) if long(a5 - 0x4f8c) else 0)
            result = 0
        elif segment == 3 and offset == 0x2324 and not long(a5 - 0x4c9e):
            # DrawCustomRoomImgs runs natively only for a loaded CUST room.
            result = 0
        elif segment == 5 and offset == 0x08c4:
            # PieceRightId 5:0904 advances the requested column before lookup.
            result = terrain.tile(room_id, word(sp + 4) + 1, word(sp + 6)).kind
        elif segment == 3 and offset == 0x26e4:
            result = 0
        elif segment == 5 and offset == 0x1990 and (climb_action is not None or floor_redraw):
            result = 0  # Dirty-buffer bookkeeping does not emit shape commands.
        if result is not None:
            cpu.reg_write(UC_M68K_REG_D0, result)
            cpu.reg_write(UC_M68K_REG_PC, long(sp))
            cpu.reg_write(UC_M68K_REG_A7, sp + 4)
        elif opcode[0] & 0xf0 == 0xa0:
            raise ValueError(f'Unexpected Macintosh trap in cavern renderer {segment}:{offset:x}')

    _machine.callback = hook

    def execute(segment, entry, argument=None):
        cpu.reg_write(UC_M68K_REG_A5, a5)
        cpu.reg_write(UC_M68K_REG_A0, 0)
        cpu.reg_write(UC_M68K_REG_A7, stack)
        put_long(stack, end)
        if argument is not None:
            put_word(stack + 4, argument)
        try:
            cpu.emu_start(bases[segment] + entry, end, count=1000000 if _native_scene else 200000)
        except Exception as error:
            pc = cpu.reg_read(UC_M68K_REG_PC)
            raise ValueError(f'Cavern renderer failed at {pc:#x}: {history}') from error
        if cpu.reg_read(UC_M68K_REG_PC) != end:
            raise ValueError('Cavern drawing did not complete')

    passes = (('back', 0x1ff4, 0), ('back', 0x1ff4, 5), ('front', 0x2598, 1))
    if custom is not None:
        # RedrawCell 3:1d24-1d2e adds back pass 11 for a loaded CUST room.
        passes = passes[:2] + (('back', 0x1ff4, 11),) + passes[2:]
    if climb_action is not None:
        passes = (('front', 0x3480, 2),)
    elif floor_redraw:
        passes = (('front', 0x371c, 2),)
    try:
        # Room setup 3:1ab0 supplies the upper-room ID used by cavern
        # decorations beneath loose floors, including first-row foreground.
        execute(3, 0x1ab0)
        if _native_scene:
            if climb_action is not None or floor_redraw:
                raise ValueError('The whole-scene audit requires a full repaint')
            execute(3, 0x1c64)
        for draw_row in (() if _native_scene else (2, 1, 0, -1)):
            if draw_row == -1:
                # RedrawCellFast 3:1cb6-1cda draws the upper room's last row,
                # with the current room below it. Missing rooms use GetCells'
                # scenery default (floor 1), not GetBlock's collision wall 20.
                above = terrain.neighbor(room_id, 'up')
                put_word(a5 - 0x4fc2, above + 1 if above is not None else 0)
                execute(3, 0x1ab0)
                put_word(a5 - 0x4fba, room_id + 1)
                execute(5, 0x0b50)
                put_word(a5 - 0x45f6, 2)
                execute(5, 0x026a)
                execute(5, 0x03bc)
            for draw_column in range(10):
                put_word(a5 - 0x45f8, draw_column)
                put_word(a5 - 0x45f6, draw_row)
                if draw_row == -1:
                    # Obtain the native border cell/neighbor records; dirty clips
                    # remain supplied by the export pass below.
                    repaint = word(a5 - 0x4832)
                    put_word(a5 - 0x4832, 1)
                    execute(5, 0x0a4c)
                    put_word(a5 - 0x4832, repaint)
                else:
                    tile, previous = (terrain.tile(room_id, draw_column, draw_row),
                                      terrain.tile(room_id, draw_column - 1, draw_row))
                    put_word(a5 - 0x4814, tile.kind)
                    put_long(a5 - 0x4818, (tile.foreground << 16) | tile.background)
                    previous_foreground = previous.foreground
                    if custom is not None and draw_column == 0:
                        # 5:0bbc-0be2: a CUST room hides the left room's last
                        # column (0xc000), except rows 1-2 of CUST kind 0x1f.
                        if int.from_bytes(custom['data'][:2], 'big') == 0x1f and draw_row in (1, 2):
                            previous_foreground &= 0x3fff
                        else:
                            previous_foreground |= 0xc000
                    put_word(a5 - 0x49d6, previous.kind)
                    put_long(a5 - 0x49d4, (previous_foreground << 16) | previous.background)
                    for col in range(11):
                        below = terrain.tile(room_id, col - 1, draw_row + 1)
                        put_word(a5 - 0x4a84 + col * 6, below.kind)
                        put_long(a5 - 0x4a82 + col * 6, (below.foreground << 16) | below.background)
                for layer, entry, draw_pass in passes:
                    # GetCells 5:0abe-0ac8 copies fullclip during DoCleanCut;
                    # ComputeClipRect is only used for subsequent dirty cells.
                    # RedrawCellFast 3:1c64-1d38 visits bottom-up, then the border.
                    cpu.mem_write(a5 - 0x4600, bytes(cpu.mem_read(a5 - 0x4fec, 8)))
                    if floor_redraw:
                        # GetCells/ComputeClipRect supplies the dirty cell clip;
                        # RedrawCell intersects it with QuickFloor's actor rect.
                        cpu.mem_write(a5 - 0x4600, struct.pack('>4h',
                                      max(0, draw_row * 120 + 5), draw_column * 51,
                                      (draw_row + 1) * 120 + 5, (draw_column + 1) * 51))
                    execute(3, entry, draw_pass)
    finally:
        _machine.callback = None
    # DumpTable 3:2c1e-2c68 paints back-wall records (kind 0) before
    # floor/pillar bodies, regardless of their admission order.
    ordered = sorted(zip(commands, command_kinds),
                     key=lambda item: (item[0][0] == 'front', item[1] != 0 if item[0][0] == 'back' else False))
    return {'version': 1, 'level': struct.unpack_from('>H', level, 0x218a)[0], 'room': room_id,
            'commands': [command for command, _kind in ordered], 'torches': torches}


def extract_caverns(program, caverns, prince, output, progress=lambda _text: None, *, level_number=3):
    with CavernRecovery(program, caverns, prince) as machine:
        recover = partial(recover_room, _machine=machine)
        _extract_caverns(program, caverns, prince, output, progress, recover, level_number=level_number)


def _extract_caverns(program, caverns, prince, output, progress, recover, *, level_number=3):
    from pop2.level_data import LevelDefinition

    definition = LevelDefinition.read(parse_resource_fork(prince), level_number)
    if level_number not in SCENERY_LEVELS.get(definition.kind, ()):
        raise ValueError(f'Unsupported cavern scenery level {level_number}')
    level = definition.data
    if definition.kind == 4:
        level = hide_crevices(level)
    scenes = {}
    for room in range(32):
        progress(f'Cavern scenery: room {room + 1}/32')
        scenes[str(room)] = recover(program, caverns, level, room, prince)
    result = {'version': 15, 'level': level_number,
              'rooms': {room: scene['commands'] for room, scene in scenes.items()},
              'torches': {room: scene['torches'] for room, scene in scenes.items()}}
    result['climb_redraw'], result['floor_redraw'] = {}, {}
    for room in range(32):
        progress(f'Cavern climbing layers: room {room + 1}/32')
        result['climb_redraw'][str(room)] = recover_climbing(program, caverns, prince, level, room, recover)
        result['floor_redraw'][str(room)] = recover(
            program, caverns, level, room, prince, floor_redraw=True)['commands']
    terrain = LevelMap(level)
    if definition.kind == 3:
        result['lava'] = lava_tables(program, caverns)
        result['lava']['rooms'] = lava_room_records(result, terrain)
    # FirstFrame 2:5f62 scans for the first exit-right tile in the start room.
    entry = entry_room(level_number, terrain.start_room)
    cell = next((cell for cell in range(30)
                 if terrain.tile(entry, cell % 10, cell // 10).kind == 17), None)
    if cell is not None:
        frames = exit_closing_frames(parse_resource_fork(program))
        mutable = bytearray(level)
        offset = 0x780 + entry * 120 + cell * 4
        foreground = struct.unpack_from('>H', level, offset)[0] & 0xff00
        for frame in frames:
            progress('Cavern entrance animation...')
            struct.pack_into('>H', mutable, offset, foreground | frame['phase'])
            frame['commands'] = recover(program, caverns, bytes(mutable), entry, prince)['commands']
        result['entry_exit'] = {'room': entry, 'cell': cell, 'frames': frames}
    if level_number == 7:
        # SetKidDefaults 2:5eda: leaving level six at column >= 6 starts in
        # native room 4 (cell 25) with room 32's door shut.
        upper = definition.with_ruins_entry(2)
        level_upper = hide_crevices(upper.data)
        frames = exit_closing_frames(parse_resource_fork(program))
        mutable = bytearray(level_upper)
        offset = 0x780 + upper.start_room * 120 + upper.start_tile * 4
        foreground = struct.unpack_from('>H', level_upper, offset)[0] & 0xff00
        for frame in frames:
            progress('Ruins upper entrance animation...')
            struct.pack_into('>H', mutable, offset, foreground | frame['phase'])
            frame['commands'] = recover(program, caverns, bytes(mutable), upper.start_room, prince)['commands']
        result['alternate_entry'] = {'room': upper.start_room, 'cell': upper.start_tile, 'frames': frames}
    result['loose_floors'] = extract_loose_floor_scenery(program, caverns, prince, level, result,
                                                       progress, recover=recover)
    from tools.extract_pressure_plates import pressure_scenery

    result['pressure_plates'] = pressure_scenery(program, caverns, prince, level, result,
                                               progress, recover=recover)
    if definition.kind == 4:
        from tools.extract_scythes import scythe_scenery

        result['scythes'] = scythe_scenery(program, caverns, prince, level, result,
                                           progress, recover=recover)
    progress('Saving prepared cavern scenery...')
    name = scenery_name(level_number)
    (output / name).write_text(json.dumps(result) + '\n', encoding='ascii')


def clip_climbing(commands, rect):
    result = []
    for command in commands:
        column, row = command[8:10]
        clip = list(command[6])
        clip[0] = max(clip[0], row * 120 + rect[0])
        clip[3] = min(clip[3], column * 51 + rect[3])
        if clip[0] < clip[2] and clip[1] < clip[3]:
            copied = list(command)
            copied[6] = clip
            result.append(copied)
    return result


def recover_climbing(program, caverns, prince, level, room, recover):
    resources, _art, _flasks, data, _intercepts = recovery_inputs(program, caverns, prince)
    bounds = {action: struct.unpack_from('>4h', data, len(data) - 0x4b46 + (action - 135) * 8)
              for action in range(135, 145)}
    outer = (min(rect[0] for rect in bounds.values()), min(rect[1] for rect in bounds.values()),
             max(rect[2] for rect in bounds.values()), max(rect[3] for rect in bounds.values()))
    source = next((action for action, rect in bounds.items() if rect == outer and action != 141), None)
    code = resources['CODE'].get(8, {}).get('data', b'')
    # ComputeHalfRect 3:3690-36fc changes only the top/right bounds here.
    # Preserve the native kind-6 bottom extension from the source command.
    # DrawCaveLoose 8:25fa has a separate pose-141 branch: execute it natively.
    if (source is None or any(rect[1:3] != outer[1:3] for rect in bounds.values())
            or code[0x25fa:0x2600] != b'\x0c\x6d\x00\x8d\xaf\x38'):
        return {str(action): recover(program, caverns, level, room, prince, action)['commands']
                for action in bounds}
    commands = recover(program, caverns, level, room, prince, source)['commands']
    return {str(action): (recover(program, caverns, level, room, prince, action)['commands']
                          if action == 141 else clip_climbing(commands, rect))
            for action, rect in bounds.items()}


def lava_room_records(program, terrain):
    rooms = {}
    for room, commands in program['rooms'].items():
        records, seen = [], set()
        for command in commands:
            if command[1] != 3614:
                continue
            x, bottom, row = command[2], command[3], command[5]
            tile = terrain.tile(int(room), x // 51, row)
            key = tile.room, tile.row * 10 + tile.column, x, bottom
            if tile.kind != 23 or key in seen:
                continue
            seen.add(key)
            records.append({'room': tile.room, 'cell': key[1], 'x': x, 'bottom': bottom})
        rooms[room] = records
    return rooms


def loose_floor_cells(terrain):
    """Native loose cells and the surfaces their falling slabs can modify."""
    cells, struck = {}, set()
    for room in range(32):
        for cell in range(30):
            tile = terrain.tile(room, cell % 10, cell // 10)
            if tile.kind != 11:
                continue
            cells[room, cell] = ((11, tile.foreground),
                                 (11, (tile.foreground & 0xfff0) | 1),
                                 (0, space_foreground(tile.foreground)))
            visited = set()
            for below_row in range(tile.row + 1, tile.row + 97):
                below = terrain.tile(room, tile.column, below_row)
                key = below.room, below.row * 10 + below.column
                if below.room is None or key in visited:
                    break
                visited.add(key)
                if below.kind == 11:
                    struck.add(key)
                    continue
                if below.kind in EMPTY_TILES:
                    continue
                before = below.kind, below.foreground
                after = rubble_tile(*before)
                if before != after:
                    cells[key] = (before, after)
                break
    for key in struck:
        cells[key] += (cells[key][2],)  # Collision removal does not clear below.
    for room in range(32):
        for cell in range(30):
            tile = terrain.tile(room, cell % 10, cell // 10)
            if tile.kind == CREVICE_TILE and struct.unpack_from('>H', terrain.level, 0x2186)[0] == 4:
                # A ruins crevice: covered, or revealed by 7:332a (bit 0x80).
                cells[room, cell] = ((CREVICE_TILE, tile.foreground & 0xff7f),
                                     (CREVICE_TILE, tile.foreground | 0x80))
    return cells


def crevice_groups(terrain):
    # Every contiguous tile-7 run (through horizontal links): 7:332a always
    # changes a whole run.
    groups = set()
    for room in range(32):
        for cell in range(30):
            column, row = cell % 10, cell // 10
            if terrain.tile(room, column, row).kind != CREVICE_TILE:
                continue
            start = column
            while start > column - 640 and terrain.tile(room, start - 1, row).kind == CREVICE_TILE:
                start -= 1
            run = []
            while len(run) < 640 and (tile := terrain.tile(room, start, row)).kind == CREVICE_TILE:
                key = tile.room, tile.row * 10 + tile.column
                if key in run:
                    break
                run.append(key)
                start += 1
            groups.add(tuple(sorted(run)))
    return sorted(groups)


def encode_delta(base, commands):
    """Store a command list as slices of `base` plus the commands it lacks."""
    keys = [json.dumps(command) for command in base]
    matcher = SequenceMatcher(None, keys, [json.dumps(command) for command in commands],
                              autojunk=False)
    items = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            items.append([i1, i2])
        elif tag in ('replace', 'insert'):
            items.extend(commands[j1:j2])
    return items


def compact_variant(base, room, variant):
    # Level six's room 20 alone has 7,775 loose-floor variants; whole command
    # lists would make a 110 MB export. Variants differ in a few commands.
    key = str(room)
    result = {'commands': encode_delta(base['rooms'][key], variant['commands']),
              'floor_redraw': encode_delta(base['floor_redraw'][key], variant['floor_redraw']),
              'climb_redraw': {action: encode_delta(base['climb_redraw'][key].get(action, []), items)
                               for action, items in variant['climb_redraw'].items()}}
    if 'entry_frames' in variant:
        result['entry_frames'] = [encode_delta(frame['commands'], items) for frame, items
                                  in zip(base['entry_exit']['frames'], variant['entry_frames'])]
    return result


def extract_loose_floor_scenery(program, caverns, prince, level, base, progress=lambda _text: None,
                               *, recover=None):
    recover = recover or recover_room
    terrain = LevelMap(level)
    # The ruins' exports store variants as deltas; the caverns keep full lists.
    compact = struct.unpack_from('>H', level, 0x2186)[0] != 3
    choices = loose_floor_cells(terrain)
    data = expand_a5_data(parse_resource_fork(program))
    if compact:
        # The ruins' loose drawer 7:2bd6-2c1a picks its shake image from one
        # of two tables by the column's parity (a5-0x2c66 even, -0x2c7e odd).
        shifts = [list(struct.unpack_from('>13h', data, len(data) - offset)) for offset in (0x2c66, 0x2c7e)]
    else:
        offsets = struct.unpack_from('>13h', data, len(data) - 0x2f30)
        # DrawCaveLoose 8:24dc/257c applies the original two table lookups.
        shifts = [offsets[index] for index in offsets]
    clears = {key: below for key in choices if choices[key][0][0] == 11
              and (below := cleared_below_cell(terrain, *key)) is not None}
    result = {'shifts': shifts, 'cells': {f'{room}:{cell}': values
                                         for (room, cell), values in choices.items()}, 'rooms': {}}
    for room in range(32):
        visible = {(tile.room, tile.row * 10 + tile.column)
                   for row in range(-1, 4) for column in range(-1, 11)
                   if (tile := terrain.tile(room, column, row)).room is not None}
        keys = sorted(visible & choices.keys())
        keys = sorted(set(keys) | {key for key, below in clears.items() if below in visible})
        if not keys:
            continue
        variants = {}
        total = prod(len(choices[key]) for key in keys) - 1
        groups = [tuple(keys.index(key) for key in group if key in keys)
                  for group in crevice_groups(terrain) if set(group) & set(keys)]
        for number, indices in enumerate(product(*(range(len(choices[key])) for key in keys))):
            if not any(indices):
                continue
            if any(len({indices[index] for index in group}) > 1 for group in groups):
                continue  # 7:332a reveals a whole run at once.
            progress(f'Cavern floor variants: room {room + 1}/32, variant {number}/{total}')
            mutable = bytearray(level)
            for key, index in zip(keys, indices):
                kind, foreground = choices[key][index]
                source_room, source_cell = key
                struct.pack_into('>H', mutable, source_room * 60 + source_cell * 2, kind)
                struct.pack_into('>H', mutable, 0x780 + source_room * 120 + source_cell * 4, foreground)
            for key, index in zip(keys, indices):
                if index == 2 and key in clears:
                    target_room, target_cell = clears[key]
                    offset = 0x780 + target_room * 120 + target_cell * 4
                    foreground = struct.unpack_from('>H', mutable, offset)[0]
                    struct.pack_into('>H', mutable, offset, foreground & 0xf0ff)
            variant = {'commands': recover(program, caverns, bytes(mutable), room, prince)['commands']}
            variant['floor_redraw'] = recover(program, caverns, bytes(mutable), room, prince,
                                                   floor_redraw=True)['commands']
            variant['climb_redraw'] = recover_climbing(program, caverns, prince, bytes(mutable), room, recover)
            entry = base.get('entry_exit')
            if entry is not None and room == entry['room']:
                variant['entry_frames'] = []
                offset = 0x780 + room * 120 + entry['cell'] * 4
                foreground = struct.unpack_from('>H', level, offset)[0] & 0xff00
                for frame in entry['frames']:
                    struct.pack_into('>H', mutable, offset, foreground | frame['phase'])
                    variant['entry_frames'].append(recover(program, caverns, bytes(mutable),
                                                               room, prince)['commands'])
            if compact:
                variant = compact_variant(base, room, variant)
            variants[''.join(map(str, indices))] = variant
        result['rooms'][str(room)] = {'cells': keys, 'variants': variants}
        if compact:
            result['rooms'][str(room)]['delta'] = True
    return result


def exit_closing_frames(resources):
    data = expand_a5_data(resources)
    # CloseExit 5:25d0 sets 79/state 4. ATMExit 5:15da reads the next
    # state-indexed decrement, stopping with effect 20 only on underflow.
    phase, state = 79, 4
    frames = [{'phase': phase, 'sounds': []}]
    while state < 31:
        state += 1
        decrement = struct.unpack_from('>h', data, len(data) - 0x45fc + state * 2)[0]
        if decrement < 0:
            raise ValueError('Invalid native exit closing decrement')
        phase -= decrement
        frames.append({'phase': max(0, phase), 'sounds': [20] if phase < 0 else []})
        if phase < 0:
            return frames
    raise ValueError('Native exit closure did not terminate')
