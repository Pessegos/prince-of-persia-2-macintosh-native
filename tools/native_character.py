"""The original's per-character drawing setup, run on the executable.

SetupKid/SetupOpponent (3:0eec-0f72, 3:0d18-0da6) prepare a character for
the frame: GetCharEdges 4:5cbc gives its rectangle (a5-0x502c: top,
left, bottom + 1, right + 1) and the rows and columns it spans, QuickFloor
2:697e marks the floor cells (MarkFloor 5:1846, with that rectangle) and
the climb's half cells (MarkHalf 5:18ac) that RedrawCell repaints over it,
ClipChar 4:4146 gives its drawing clip (a5-0x34bc), and MarkBufsForRect
5:19f8 marks the cells its rectangle covers for a front redraw (MarkFRedraw
5:1990). `NativeCharacter.frame` runs these routines for one character and
returns what they marked; tools.probe_actor_cover draws the marked cells.

Supplied, not run: the shape's size (17:673a returns the port sprite's
height and width), the drawn anchor and bottom (a5-0x34c4/-0x34c2, from
the port's image bounds) and the character's fields.
"""

import struct

from unicorn import UC_ARCH_M68K, UC_HOOK_CODE, UC_MODE_BIG_ENDIAN, Uc
from unicorn.m68k_const import UC_CPU_M68K_M68000, UC_M68K_REG_A5, UC_M68K_REG_A7, UC_M68K_REG_D0, UC_M68K_REG_PC

from pop2.mac_resources import parse_resource_fork
from tools.extract_caverns import (EMPTY_RECT, EMPTY_RECT_CODE, SECT_RECT, SECT_RECT_CODE, UNION_RECT,
                                   UNION_RECT_CODE)
from tools.extract_enemy_profiles import expand_a5_data

# The current character's fields (a5 displacements); the Kid's saved copy
# is 0x7c lower (a5-0x50d0 facing .. a5-0x50a2 rectangle right).
CHARACTER = {'facing': -0x5054, 'x': -0x5052, 'y': -0x5050, 'type': -0x504e, 'action': -0x504c,
             'column': -0x504a, 'row': -0x5048, 'mode': -0x5046, 'room': -0x5040,
             'sequence': -0x5030, 'selected': -0x502e}
KID_COPY = 0x7c
RECT = -0x502c


class NativeCharacter:
    def __init__(self, program, level):
        self.resources = parse_resource_fork(program)
        cpu = self.cpu = Uc(UC_ARCH_M68K, UC_MODE_BIG_ENDIAN)
        cpu.ctl_set_cpu_model(UC_CPU_M68K_M68000)
        cpu.mem_map(0, 0x1000000)
        self.a5, self.stack, self.end = 0x80000, 0xf0000, 0xff000
        self.bases = {segment: 0x100000 + segment * 0x10000 for segment in self.resources['CODE'] if segment}
        for segment, base in self.bases.items():
            cpu.mem_write(base, self.resources['CODE'][segment]['data'])
        self.data = expand_a5_data(self.resources)
        self.level = level
        self.size = (1, 1)
        cpu.hook_add(UC_HOOK_CODE, self.hook)
        self.marks = []

    def reset(self):
        cpu = self.cpu
        cpu.mem_write(self.a5 - len(self.data), self.data)
        cpu.mem_write(0xa0000, self.level)
        self.put_long(-0x5014, 0xa0000)
        # Shape table 2 (the Kid's) is not the background set (a5-0x4a88),
        # so its sizes come from 17:673a.
        self.put_long(-0x4a98 + 8, 0xb0000)
        self.put_long(-0x4a88, 0xb1000)
        cpu.mem_write(self.a5 - 0x4fec, struct.pack('>4h', 0, 0, 365, 510))
        cpu.mem_write(self.a5 - 0x196c, struct.pack('>4h', 0, 0, 0, 0))
        # ClipChar's rectangle table a5-0x452c (4:41e6, indexed by the
        # level's environment word 0x2186) holds a5-relative pointers for
        # environments 2-4 that the loader relocates.
        for index in (2, 3, 4):
            pointer = struct.unpack_from('>i', self.data, len(self.data) - 0x452c + 4 * index)[0]
            self.put_long(-0x452c + 4 * index, (self.a5 + pointer) & 0xffffffff)
        # The trap glue the routines call through a5-0x1f60/-0x1f5c/-0x1f58.
        for address, code, displacement in ((EMPTY_RECT, EMPTY_RECT_CODE, -0x1f60),
                                             (UNION_RECT, UNION_RECT_CODE, -0x1f5c),
                                             (SECT_RECT, SECT_RECT_CODE, -0x1f58)):
            cpu.mem_write(address, code)
            self.put_long(displacement, address)

    def put_word(self, displacement, value):
        self.cpu.mem_write(self.a5 + displacement, struct.pack('>H', value & 65535))

    def put_long(self, displacement, value):
        self.cpu.mem_write(self.a5 + displacement, struct.pack('>I', value))

    def word(self, displacement):
        return struct.unpack('>h', self.cpu.mem_read(self.a5 + displacement, 2))[0]

    def rect(self, displacement):
        return struct.unpack('>4h', self.cpu.mem_read(self.a5 + displacement, 8))

    def target(self, pointer):
        jump = self.resources['CODE'][0]['data']
        offset, opcode, segment, trap = struct.unpack_from('>4H', jump, 16 + pointer - 0x22)
        if opcode != 0x3f3c or trap != 0xa9f0:
            raise ValueError('Unsupported jump table entry')
        return self.bases[segment] + offset + 4

    def _return(self, sp, value=None):
        cpu = self.cpu
        if value is not None:
            cpu.reg_write(UC_M68K_REG_D0, value)
        cpu.reg_write(UC_M68K_REG_PC, struct.unpack('>I', cpu.mem_read(sp, 4))[0])
        cpu.reg_write(UC_M68K_REG_A7, sp + 4)

    def hook(self, cpu, address, size, user):
        opcode = bytes(cpu.mem_read(address, 2))
        sp = cpu.reg_read(UC_M68K_REG_A7)
        segment = (address - 0x100000) // 0x10000
        offset = address - self.bases.get(segment, address)

        def long(at):
            return struct.unpack('>I', cpu.mem_read(at, 4))[0]

        def word(at):
            return struct.unpack('>h', cpu.mem_read(at, 2))[0]

        if opcode == b'\x4e\xad':  # jsr d16(a5): the jump table, resolved here.
            destination = self.target(word(address + 2))
            cpu.mem_write(sp - 4, struct.pack('>I', address + 4))
            cpu.reg_write(UC_M68K_REG_A7, sp - 4)
            cpu.reg_write(UC_M68K_REG_PC, destination)
            return
        if segment == 17 and offset == 0x673a:  # The shape's size.
            cpu.mem_write(long(sp + 10), struct.pack('>4h', self.size[0], self.size[1], 0, 0))
            self._return(sp, 1)
            return
        if segment == 5 and offset == 0x1846:  # MarkFloor(cell, rect)
            self.marks.append(('floor', word(sp + 4), struct.unpack('>4h', cpu.mem_read(long(sp + 6), 8))))
            self._return(sp)
            return
        if segment == 5 and offset == 0x18ac:  # MarkHalf(cell)
            self.marks.append(('half', word(sp + 4), None))
            self._return(sp)
            return
        if segment == 5 and offset == 0x1990:  # MarkFRedraw(cell, rect)
            self.marks.append(('front', word(sp + 4), struct.unpack('>4h', cpu.mem_read(long(sp + 6), 8))))
            self._return(sp)
            return
        if opcode == b'\xa8\xa8':  # OffsetRect(rect, dh, dv)
            dy, dx, pointer = struct.unpack('>hhI', cpu.mem_read(sp, 8))
            top, left, bottom, right = struct.unpack('>4h', cpu.mem_read(pointer, 8))
            cpu.mem_write(pointer, struct.pack('>4h', top + dy, left + dx, bottom + dy, right + dx))
            cpu.reg_write(UC_M68K_REG_A7, sp + 8)
            cpu.reg_write(UC_M68K_REG_PC, address + 2)
            return
        if opcode == b'\xa8\xae':  # EmptyRect(r): Boolean
            top, left, bottom, right = struct.unpack('>4h', cpu.mem_read(long(sp), 8))
            cpu.mem_write(sp + 4, bytes([int(bottom <= top or right <= left), 0]))
            cpu.reg_write(UC_M68K_REG_A7, sp + 4)
            cpu.reg_write(UC_M68K_REG_PC, address + 2)
            return
        if opcode == b'\xa8\xa6':  # EqualRect(r1, r2): Boolean
            equal = cpu.mem_read(long(sp), 8) == cpu.mem_read(long(sp + 4), 8)
            cpu.mem_write(sp + 8, bytes([int(equal), 0]))
            cpu.reg_write(UC_M68K_REG_A7, sp + 8)
            cpu.reg_write(UC_M68K_REG_PC, address + 2)
            return
        if opcode[0] & 0xf0 == 0xa0:
            raise RuntimeError(f'Unexpected trap {segment}:{offset:04x}')

    def execute(self, segment, offset, arguments=b''):
        cpu = self.cpu
        cpu.reg_write(UC_M68K_REG_A5, self.a5)
        cpu.reg_write(UC_M68K_REG_A7, self.stack)
        cpu.mem_write(self.stack, struct.pack('>I', self.end) + arguments)
        cpu.emu_start(self.bases[segment] + offset, self.end, count=400000)
        if cpu.reg_read(UC_M68K_REG_PC) != self.end:
            raise RuntimeError(f'{segment}:{offset:04x} did not return')

    def frame(self, fields, anchor, bottom, size, *, kid=True):
        """Run GetCharEdges, QuickFloor, ClipChar and MarkBufsForRect for a
        character with these `fields` (CHARACTER names; `room` one-based),
        drawn from X `anchor` (a5-0x34c4) and bottom Y `bottom` with a shape
        of `size` (height, width). Returns a dict: 'rect' (a5-0x502c), 'rows'
        (top, bottom: a5-0x34a0/-0x349e), 'columns' (a5-0x34a4/-0x34a2),
        'clip' (a5-0x34bc), 'viewable' and 'marks' [(kind, cell, rect)]."""
        self.reset()
        self.size = size
        self.marks = []
        for name, displacement in CHARACTER.items():
            self.put_word(displacement, fields.get(name, 0))
            if kid:
                self.put_word(displacement - KID_COPY, fields.get(name, 0))
        self.put_word(-0x34c0, 0)
        self.put_word(-0x34be, 2)
        self.put_word(-0x34c4, anchor)
        self.put_word(-0x34c2, bottom)
        self.put_word(-0x34c6, fields.get('facing', 0))
        for displacement in (-0x521a, -0x503c):
            self.put_word(displacement, 0)
        # The sequence's mode word (+0x34), which IsCharNonViewable 4:471e
        # tests (4, 5, 6, 7, 10 and 12 hide the character).
        self.put_word(-0x5022, fields.get('sequence_mode', 0))
        # The displayed room (a5-0x4fc2), which GetUndefineCellId 4:28b6
        # tests for a cell past a missing link (ReadCell from ClipChar).
        self.put_word(-0x4fc2, fields.get('room', 0))
        self.execute(4, 0x5cbc)
        if kid:
            self.cpu.mem_write(self.a5 + RECT - KID_COPY, bytes(self.cpu.mem_read(self.a5 + RECT, 8)))
        self.execute(2, 0x697e)
        self.execute(4, 0x4146)
        self.execute(4, 0x471e)
        hidden = self.cpu.reg_read(UC_M68K_REG_D0) & 0xffff
        viewable = fields.get('mode', 0) != 9 and not hidden
        if viewable:
            self.execute(5, 0x19f8, struct.pack('>IIH', self.target(0x3da), self.a5 + RECT,
                                                 self.word(-0x5056)))
        return {'rect': self.rect(RECT), 'rows': (self.word(-0x34a0), self.word(-0x349e)),
                'columns': (self.word(-0x34a4), self.word(-0x34a2)), 'clip': self.rect(-0x34bc),
                'viewable': viewable, 'marks': list(self.marks)}
