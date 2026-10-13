"""Export native level-three scenery drawing commands during asset import."""

import json
import struct

from pop2.mac_resources import parse_resource_fork
from pop2.terrain import LevelMap
from tools.extract_enemy_profiles import expand_a5_data


def recover_room(program, caverns, level, room_id=0, prince=None):
    from unicorn import Uc, UC_ARCH_M68K, UC_MODE_BIG_ENDIAN, UC_HOOK_CODE
    from unicorn.m68k_const import (
        UC_CPU_M68K_M68000, UC_M68K_REG_A5, UC_M68K_REG_A7,
        UC_M68K_REG_A0, UC_M68K_REG_D0, UC_M68K_REG_PC,
    )

    resources = parse_resource_fork(program)
    artwork = parse_resource_fork(caverns)
    flasks = parse_resource_fork(prince) if prince is not None else None
    data = expand_a5_data(resources)
    cpu = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
    cpu.ctl_set_cpu_model(UC_CPU_M68K_M68000)
    cpu.mem_map(0, 0x1000000)
    a5, stack, end, info, pieces, lev = 0x80000, 0xf0000, 0xff000, 0x90000, 0x91000, 0xa0000
    bases = {segment: 0x100000 + segment * 0x10000 for segment in resources['CODE'] if segment}
    for segment, base in bases.items():
        cpu.mem_write(base, resources['CODE'][segment]['data'])
    cpu.mem_write(a5 - len(data), data)
    cpu.mem_write(pieces, artwork['PIEC'][3500]['data'])
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

    table_offset = struct.unpack_from('>i', data, len(data) - 0x4aea + 3 * 4)[0]
    dispatch = 0x92000
    for kind in range(45):
        pointer = struct.unpack_from('>i', data, len(data) + table_offset + kind * 4)[0]
        put_long(dispatch + kind * 4, target(pointer) if pointer else 0)
    put_long(a5 - 0x4aae, dispatch)
    put_long(a5 - 0x4f8c, info)
    put_long(a5 - 0x4b9e, pieces)
    put_long(a5 - 0x5014, lev)
    put_long(a5 - 0x4ab2, 0)  # No actor-specific gate peeling in a static scene.
    # DoCleanCut 2:608c-6096 builds scenery with full-room repaint enabled.
    # Per-cell redraws change the overlap order of adjacent exit pieces.
    put_word(a5 - 0x4832, 1)
    put_word(a5 - 0x4fc2, room_id + 1)
    for offset in (0x4600, 0x4fec):
        cpu.mem_write(a5 - offset, struct.pack('>4h', 0, 0, 365, 510))
    terrain = LevelMap(level)
    commands = []
    command_kinds = []
    torches = []
    layer = 'back'
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
        history.append(hex(address))
        del history[:-15]
        if not 0x110000 <= address < 0x300000:
            raise ValueError(f'Invalid cavern call: {history}')
        opcode = bytes(cpu.mem_read(address, 2))
        sp = cpu.reg_read(UC_M68K_REG_A7)
        if opcode == b'\x4e\xad':
            displacement = word(address + 2)
            destination = target(displacement)
            put_long(sp - 4, address + 4)
            cpu.reg_write(UC_M68K_REG_A7, sp - 4)
            cpu.reg_write(UC_M68K_REG_PC, destination)
            return
        segment = (address - 0x100000) // 0x10000
        offset = address - bases.get(segment, address)
        result = None
        if opcode == b'\x4e\x90' and segment == 8 and offset == 0x176c:
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
        if opcode == b'\x4e\x90' and segment == 8 and offset in (0x1ca4, 0x1752, 0x1f86):
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
            library = fields[0]
            if library not in (1, 4):
                raise ValueError(f'Unsupported cavern shape library {library}')
            shape = (3000 if library == 1 else 3500) + fields[12]
            source = flasks if library == 1 else artwork
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
                if library == 4 and 3581 <= shape <= 3589:
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
        elif segment == 3 and offset == 0x2324:
            result = 0
        elif segment == 5 and offset == 0x08c4:
            # PieceRightId 5:0904 advances the requested column before lookup.
            result = terrain.tile(room_id, word(sp + 4) + 1, word(sp + 6)).kind
        elif segment == 3 and offset == 0x26e4:
            result = 0
        if result is not None:
            cpu.reg_write(UC_M68K_REG_D0, result)
            cpu.reg_write(UC_M68K_REG_PC, long(sp))
            cpu.reg_write(UC_M68K_REG_A7, sp + 4)
        elif opcode[0] & 0xf0 == 0xa0:
            raise ValueError(f'Unexpected Macintosh trap in cavern renderer {segment}:{offset:x}')

    cpu.hook_add(UC_HOOK_CODE, hook)
    for draw_row in (2, 1, 0, -1):
        for draw_column in range(10):
            for layer, entry, draw_pass in (('back', 0x1ff4, 0), ('back', 0x1ff4, 5),
                                            ('front', 0x2598, 1)):
                # GetCells 5:0abe-0ac8 copies fullclip during DoCleanCut;
                # ComputeClipRect is only used for subsequent dirty cells.
                # RedrawCellFast 3:1c64-1d38 visits bottom-up, then the border.
                cpu.mem_write(a5 - 0x4600, bytes(cpu.mem_read(a5 - 0x4fec, 8)))
                put_word(a5 - 0x45f8, draw_column)
                put_word(a5 - 0x45f6, draw_row)
                tile, previous = (terrain.tile(room_id, draw_column, draw_row),
                                  terrain.tile(room_id, draw_column - 1, draw_row))
                put_word(a5 - 0x4814, tile.kind)
                put_long(a5 - 0x4818, (tile.foreground << 16) | tile.background)
                put_word(a5 - 0x49d6, previous.kind)
                put_long(a5 - 0x49d4, (previous.foreground << 16) | previous.background)
                for col in range(11):
                    below = terrain.tile(room_id, col - 1, draw_row + 1)
                    put_word(a5 - 0x4a84 + col * 6, below.kind)
                    put_long(a5 - 0x4a82 + col * 6, (below.foreground << 16) | below.background)
                cpu.reg_write(UC_M68K_REG_A5, a5)
                cpu.reg_write(UC_M68K_REG_A0, 0)
                cpu.reg_write(UC_M68K_REG_A7, stack)
                put_long(stack, end)
                put_word(stack + 4, draw_pass)
                try:
                    cpu.emu_start(bases[3] + entry, end, count=200000)
                except Exception as error:
                    pc = cpu.reg_read(UC_M68K_REG_PC)
                    raise ValueError(f'Cavern renderer failed at {pc:#x}, {layer} {draw_column},{draw_row}: {history}') from error
                if cpu.reg_read(UC_M68K_REG_PC) != end:
                    raise ValueError('Cavern drawing did not complete')
    # DumpTable 3:2c1e-2c68 paints back-wall records (kind 0) before
    # floor/pillar bodies, regardless of their admission order.
    ordered = sorted(zip(commands, command_kinds),
                     key=lambda item: (item[0][0] == 'front', item[1] != 0 if item[0][0] == 'back' else False))
    return {'version': 1, 'level': 3, 'room': room_id,
            'commands': [command for command, _kind in ordered], 'torches': torches}


def extract_caverns(program, caverns, prince, output):
    level = parse_resource_fork(prince)['LEVL'][2002]['data']
    scenes = {str(room): recover_room(program, caverns, level, room, prince) for room in range(32)}
    result = {'version': 6, 'level': 3,
              'rooms': {room: scene['commands'] for room, scene in scenes.items()},
              'torches': {room: scene['torches'] for room, scene in scenes.items()}}
    terrain = LevelMap(level)
    # FirstFrame 2:5f62 scans for the first exit-right tile in the start room.
    cell = next((cell for cell in range(30)
                 if terrain.tile(terrain.start_room, cell % 10, cell // 10).kind == 17), None)
    if cell is not None:
        frames = exit_closing_frames(parse_resource_fork(program))
        mutable = bytearray(level)
        offset = 0x780 + terrain.start_room * 120 + cell * 4
        foreground = struct.unpack_from('>H', level, offset)[0] & 0xff00
        for frame in frames:
            struct.pack_into('>H', mutable, offset, foreground | frame['phase'])
            frame['commands'] = recover_room(program, caverns, bytes(mutable), terrain.start_room, prince)['commands']
        result['entry_exit'] = {'room': terrain.start_room, 'cell': cell, 'frames': frames}
    (output / 'caverns_entry.json').write_text(json.dumps(result) + '\n', encoding='ascii')


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
