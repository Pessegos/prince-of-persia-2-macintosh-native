"""Compare level 14's moving-scenery trobs with pop2.final_scenery.

CODE 9's room-4 face 9:1b3a/1ba4, AnimFinlSpider 9:1bf0, DrawFinlSpider 9:1cba, AnimFinlCrystal
9:1e30, DrawFinlCrystal 9:1f5e, TriggerFinlCrystal 9:2068, AnimFinlGargoyle
9:20dc, DrawFinlGargoyle 9:2238 and TriggerFinlGargoyle 9:233a run in
Unicorn over the original A5 data and the room's original Final CUST
record. Supplied endpoints, which record their arguments: Rnd 17:6e06 (the
case's draw), the dirty-rectangle call 5:19f8, DrawCustomRoomImg 3:2438
(also the record's bottom, X and pass at the call), AddTrob 5:20a0 and the
OffsetRect trap A8A8 (applied). Drawing itself, the redraw buffers and the
trob list's bookkeeping are excluded.
"""

import argparse
from itertools import product
from pathlib import Path
import struct

from pop2.final_scenery import (
    crystal_image, crystal_step, face_images, face_step, invalidates, gargoyle_image, gargoyle_step, spider_images, spider_step,
    trigger,
)
from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules

CUST = 0xc0000
CELLS = 0xc8000
DRAW = 0xc9000
STATE = -0x4818


class Draws:
    def __init__(self, value):
        self.value = value
        self.stops = []

    def randrange(self, stop):
        self.stops.append(stop)
        return self.value


class NativeScenery(NativeRules):
    RANGES = {9: ((0x1b3a, 0x1ba2), (0x1ba4, 0x1bee), (0x1bf0, 0x1ca6), (0x1cba, 0x1d70), (0x1e30, 0x1f48), (0x1f5e, 0x2052),
                  (0x2068, 0x20c4), (0x20dc, 0x2222), (0x2238, 0x2324), (0x233a, 0x238e))}
    SUPPLIED = {(17, 0x6e06): 'rnd', (5, 0x19f8): 'dirty', (3, 0x2438): 'draw',
                (5, 0x20a0): 'add_trob'}

    def reset(self, level):
        super().reset(level)
        self.roll = 0
        self.calls = []

    def long(self, address):
        return struct.unpack('>I', self.cpu.mem_read(address, 4))[0]

    def dispatch(self, cpu, address, size, user):
        if bytes(cpu.mem_read(address, 2)) == b'\xa8\xa8':
            # OffsetRect(rect, dh, dv), Pascal order: dv is on top.
            stack = cpu.reg_read(self.registers['a7'])
            dv, dh = struct.unpack('>hh', cpu.mem_read(stack, 4))
            rect = struct.unpack('>I', cpu.mem_read(stack + 4, 4))[0]
            top, left, bottom, right = struct.unpack('>4h', cpu.mem_read(rect, 8))
            cpu.mem_write(rect, struct.pack('>4h', top + dv, left + dh, bottom + dv, right + dh))
            cpu.reg_write(self.registers['a7'], stack + 8)
            cpu.reg_write(self.registers['pc'], address + 2)
            return
        key = divmod(address - self.CODE_BASE, 0x10000)
        service = self.SUPPLIED.get(key)
        if service is not None:
            stack = cpu.reg_read(self.registers['a7'])
            if service == 'rnd':
                self.calls.append(('rnd', struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]))
            elif service == 'draw':
                index, draw_pass = struct.unpack('>hh', cpu.mem_read(stack + 4, 4))
                record = CUST + 30 + index * 32
                bottom, x, record_pass = struct.unpack('>3h', cpu.mem_read(record + 2, 6))
                self.calls.append(('draw', index, draw_pass, bottom, x, record_pass))
            elif service == 'add_trob':
                self.calls.append(('add_trob',) + struct.unpack('>4h', cpu.mem_read(stack + 4, 8)))
            else:
                self.calls.append((service,))
        super().dispatch(cpu, address, size, user)
        if service == 'rnd':
            cpu.reg_write(self.registers['d0'], self.roll)


def records(custom):
    count = struct.unpack_from('>H', custom, 28)[0]
    return [struct.unpack_from('>16h', custom, 30 + index * 32) for index in range(count)]


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2013]['data']
    final = parse_resource_fork((directory / 'Final.rsrc.bin').read_bytes())['CUST']
    custom = {room: final[4000 + room * 25]['data'] for room in (2, 3, 5, 6, 7)}
    if (len(level), struct.unpack_from('>H', level, 0x2186)[0]) != (18890, 6) or [
            struct.unpack_from('>h', custom[room], 0)[0] for room in (2, 3, 5, 6, 7)] != [25, 26, 28, 29, 30]:
        raise ValueError('Unexpected preserved final level or CUST rooms')
    machine = NativeScenery(executable)
    compared = 0

    def prepare(room, word, paused=0, objects=1, draw_pass=1):
        machine.reset(level)
        machine.cpu.mem_write(CUST, custom[room])
        machine.cpu.mem_write(CELLS, bytes(30 * 4))
        machine.cpu.mem_write(machine.A5 - 0x4c9e, struct.pack('>I', CUST))
        machine.cpu.mem_write(machine.A5 - 0x4824, struct.pack('>I', CELLS))
        machine.cpu.mem_write(machine.A5 - 0x4f8c, struct.pack('>I', DRAW))
        machine.cpu.mem_write(DRAW + 0x0a, struct.pack('>hH', draw_pass, 0))
        machine.cpu.mem_write(DRAW + 0x14, struct.pack('>H', word))
        for offset, value in ((STATE, word), (-0x5002, paused), (-0x43e6, objects),
                              (-0x43ea, 0), (-0x4fc2, room + 1), (-0x45f6, 0), (-0x45f8, 0)):
            machine.put_word(offset, value)

    def check(label, actual, wanted):
        nonlocal compared
        if actual != wanted:
            raise AssertionError((label, actual, wanted))
        compared += 1

    face_records = records(custom[3])
    for word in (*range(0, 40), 0x7fef, 0x7ff0, 0xffff):
        prepare(3, word)
        machine.call(9, 0x1b3a)
        wanted = face_step(word)
        ended = machine.word(-0x43ea) == -1
        dirty = [('dirty',)] if invalidates(3, word, wanted) else []
        check(('face', word), (None if ended else machine.word(STATE) & 0xffff, machine.calls),
              (wanted, dirty))
        if ended:
            check(('face cleared', word), machine.word(STATE), 0)
        prepare(3, word, draw_pass=11)
        machine.call(9, 0x1ba4)
        check(('face draw', word), machine.calls,
              [('draw', image.record, 11, face_records[image.record][1], face_records[image.record][2], 11)
               for image in face_images(word)])
    spider_words = [frame | timer << 3 | flag
                     for frame, timer, flag in product(range(8), (0, 1, 2, 5, 90), (0, ACTIVE_BIT))]
    for word, paused, roll in product(spider_words, (0, 1), (0, 3, 5)):
        prepare(2, word, paused)
        machine.roll = roll
        machine.call(9, 0x1bf0)
        draws = Draws(roll)
        wanted = spider_step(word, draws, bool(paused))
        rnd = [('rnd', stop - 1) for stop in draws.stops]
        dirty = [('dirty',)] if invalidates(2, word, wanted) else []
        check(('spider', word, paused, roll),
              (machine.word(STATE) & 0xffff, [c for c in machine.calls if c[0] != 'dirty'],
               [c for c in machine.calls if c[0] == 'dirty']),
              (wanted, rnd, dirty))
    spider_records = records(custom[2])
    for word in spider_words:
        if word & ACTIVE_BIT and word & 7 > 5:
            continue  # b index past the table: never reached from the level's word
        prepare(2, word, draw_pass=11)
        machine.call(9, 0x1cba)
        wanted = [('draw', image.record, 11, spider_records[image.record][1],
                   spider_records[image.record][2], 11) for image in spider_images(word, native=True)]
        check(('spider draw', word), machine.calls, wanted)

    glint_words = [index | value << 4 | flag | TROB_BIT
                   for index, value, flag in product((0, 1, 2, 3, 8), (0, 1, 2, 5, 6, 7, 8, 80),
                                                     (0, ACTIVE_BIT))]
    crystal_records = records(custom[5])
    for word, paused, objects, roll in product(glint_words, (0, 1), (0, 1), (0, 40)):
        prepare(5, word, paused, objects)
        machine.roll = roll
        machine.call(9, 0x1e30)
        draws = Draws(roll)
        wanted = crystal_step(word, draws, bool(paused), objects)
        check(('crystal', word, paused, objects, roll),
              (machine.word(STATE) & 0xffff, machine.calls),
              (wanted, [('rnd', stop - 1) for stop in draws.stops]
               + ([('dirty',)] if invalidates(5, word, wanted) else [])))
    def reachable(word, last):
        # AnimFinl* never leave an active count past their last frame.
        return not word & ACTIVE_BIT or (word & 0x7f0) >> 4 <= last

    for word in (word for word in glint_words if reachable(word, 5)):
        prepare(5, word)
        machine.call(9, 0x1f5e)
        image = crystal_image(word)
        wanted = [] if image is None else [(
            'draw', image.record, image.draw_pass, crystal_records[image.record][1] + image.dy,
            crystal_records[image.record][2] + image.dx, image.draw_pass)]
        check(('crystal draw', word), machine.calls, wanted)
    for room, word, paused, objects, roll in product((6, 7), glint_words, (0, 1), (1,), (0, 40)):
        prepare(room, word, paused, objects)
        machine.roll = roll
        machine.call(9, 0x20dc)
        draws = Draws(roll)
        wanted = gargoyle_step(word, room, draws, bool(paused), objects)
        removed = machine.word(-0x43ea) == -1
        check(('gargoyle', room, word, paused, roll),
              (None if removed else machine.word(STATE) & 0xffff, machine.calls),
              (wanted, [('rnd', stop - 1) for stop in draws.stops]
               + ([('dirty',)] if invalidates(room, word, wanted) else [])))
    for room, word in product((6, 7), (word for word in glint_words if reachable(word, 7) and word & 15 < 4)):
        prepare(room, word)
        machine.call(9, 0x2238)
        image = gargoyle_image(word)
        wanted = [] if image is None else [
            ('draw', image.record, image.draw_pass, image.bottom, image.x, image.draw_pass)]
        check(('gargoyle draw', room, word), machine.calls, wanted)
        # 9:2314-231a puts the record back at 0, 0 with pass 11.
        if image is not None:
            check(('gargoyle restore', room, word),
                  struct.unpack('>3h', machine.cpu.mem_read(CUST + 30 + image.record * 32 + 2, 6)),
                  (0, 0, 11))
    for room, routine, counter, kind in ((5, 0x2068, -0x2872, 41), (6, 0x233a, -0x2874, 42)):
        for index, roll, cell in product(range(10), (0, 17, 40), (0, 13, 29)):
            prepare(room, 0)
            machine.put_word(counter, index)
            machine.roll = roll
            machine.call(9, routine, (room + 1, cell))
            draws = Draws(roll)
            if room == 5 and index >= 9:
                wanted = (0, [], index)
            else:
                wanted = (trigger(index, draws), [('rnd', 40), ('add_trob', room + 1, cell, 1, kind)],
                          index + 1)
            native = struct.unpack('>H', machine.cpu.mem_read(CELLS + cell * 4, 2))[0]
            check(('trigger', room, index, roll, cell), (native, machine.calls, machine.word(counter)),
                  wanted)
    return compared


ACTIVE_BIT, TROB_BIT = 0x800, 0x1000


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--recovery', default='../PoP2-Mac-Code-Recovery')
    args = parser.parse_args()
    print(f'{run_probe(args.recovery)} original CODE 9 moving-scenery cases agree')
