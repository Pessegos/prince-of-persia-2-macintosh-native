"""Bounded original sliding-rock motion with explicit geometry/actor endpoints."""

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


def trunc_div(value, divisor=51):
    return (abs(value) // divisor) * (-1 if value < 0 else 1)


def motion_reference(mob, left_room, *, filled=(False, False), tiles=(1, 1),
                     cue193_on=False, pending=-1, prince=(0, 0, 0)):
    """Model 10:1d5c; endpoint tuples or independent geometry callbacks."""
    if (len(mob) != 8 or any(not -32768 <= word <= 32767 for word in mob)
            or mob[5] != 6 or not 1 <= mob[2] <= 32 or not 0 <= mob[6] <= 2
            or not 0 <= mob[0] <= 561 or not 0 <= left_room <= 32
            or (not callable(filled) and len(filled) != 2)
            or (not callable(tiles) and len(tiles) != 2) or len(prince) != 3
            or any(not -32768 <= word <= 32767 for word in
                   (*(() if callable(tiles) else tiles), *prince, pending))):
        raise ValueError('Outside the bounded type-6 motion fixture domain')
    result = list(mob)
    events = []
    if result[4] in (0, 100):
        return dict(mob=tuple(result), events=events, pending=pending)
    x = result[0]
    candidate = x
    if result[4] == -2:
        candidate -= 2
    else:
        events.append(('filled', x))
        first_filled = filled(x) if callable(filled) else filled[0]
        if first_filled and result[4] >= 8:
            result[4] = 0
            events.append(('stop', 192))
            if pending == 192:
                pending = -1
        else:
            events.append(('filled', signed_word(x - 16)))
            second_filled = filled(signed_word(x - 16)) if callable(filled) else filled[1]
            if second_filled:
                events.append(('sound', 191))
            candidate -= 2
            if result[4] <= 8:
                result[4] = signed_word(result[4] + 1)
    if candidate < 0:
        result[2] = left_room
        candidate += 510
    if result[2] == 0:
        result[3] = -1
        events.append(('stop', 192))
        return dict(mob=tuple(result), events=events, pending=pending)
    if result[4] == 0 or result[4] == 100:
        return dict(mob=tuple(result), events=events, pending=pending)
    front = signed_word(candidate - 31)
    column = trunc_div(front) - int(front <= 0)
    events.append(('cell', result[2], column, result[6]))
    front_tile = tiles(result[2], column, result[6]) if callable(tiles) else tiles[0]
    if result[3] == 1:
        result[3] = 0
        result[4] = 100
        result[1] = signed_word(result[1] + 1)
        result[0] = signed_word(candidate + 3)
        if front_tile == 2:
            events.append(('actor', '5:3cee'))
    else:
        old_column = trunc_div(x - 6)
        new_column = trunc_div(candidate - 6)
        if new_column != old_column or column != old_column:
            events.append(('cell', result[2], new_column, result[6]))
            edge_tile = tiles(result[2], new_column, result[6]) if callable(tiles) else tiles[1]
            if (edge_tile in (20, 2, 7, 25, 43, 4) or front_tile == 2) and result[3] == 0:
                result[3] = 1
                result[1] = signed_word(result[1] - 1)
                events.append(('query', 193))
                if not cue193_on and front_tile != 2:
                    events.append(('sound', 18))
        frame, prince_column, prince_row = prince
        if (87 <= frame <= 99 and result[6] + 1 == prince_row
                and prince_column == trunc_div(candidate - 12)):
            events.append(('actor', '6:1a84'))
    if result[4] == 100:
        events.append(('stop', 192))
    else:
        result[0] = signed_word(candidate)
        if result[4] != 0:
            events.append(('sound', 192))
    return dict(mob=tuple(result), events=events, pending=pending)


class NativeSlideRockMotion(NativeRules):
    RANGES = {
        3: ((0x4ef2, 0x4f24),),
        4: ((0x4b02, 0x4b14),),
        10: ((0x1d5c, 0x1fa6),),
        19: ((0x4bb0, 0x4bb6), (0x4bd0, 0x4bf4), (0x4bfe, 0x4c4c)),
    }
    SUPPLIED = {}
    ENDPOINTS = {
        (10, 0x1656): 'filled', (4, 0x27ee): 'cell',
        (5, 0x5252): 'stop', (5, 0x4d84): 'sound', (5, 0x52c8): 'query',
        (5, 0x3cee): '5:3cee', (6, 0x1a84): '6:1a84',
    }
    ACTOR_TAGS = {'5:3cee': 30001, '6:1a84': 30003}
    BRANCHES = {
        0x1d80: 'minus_two', 0x1d94: 'filled_stop', 0x1db4: 'second_filled_test',
        0x1dae: 'clear_matching_pending_cue', 0x1de6: 'left_room_crossing',
        0x1e0e: 'missing_left_removal', 0x1e6a: 'finalize_marker',
        0x1e8e: 'actor_5_3cee', 0x1efe: 'begin_marker',
        0x1f64: 'actor_6_1a84', 0x1f98: 'terminal_sound_stop',
    }

    def __init__(self, program):
        super().__init__(program)
        self.branches = Counter()

    def reset(self, level):
        super().reset(level)
        self.events, self.actor_inputs = [], []
        self.filled = (False, False)
        self.tiles = (1, 1)
        self.cue193_on = False
        self.predicate_index = self.cell_index = 0

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        if segment == 10 and offset in self.BRANCHES:
            self.branches[self.BRANCHES[offset]] += 1
        endpoint = self.ENDPOINTS.get((segment, offset))
        if endpoint is None:
            return super().dispatch(cpu, address, size, user)
        stack = cpu.reg_read(self.registers['a7'])
        value = 0
        if endpoint == 'filled':
            if self.predicate_index >= 2:
                raise AssertionError('Unexpected extra filled-band predicate')
            self.events.append(('filled', self.word(-0x44a6)))
            value = int(self.filled[self.predicate_index])
            self.predicate_index += 1
        elif endpoint == 'cell':
            if self.cell_index >= 2:
                raise AssertionError('Unexpected extra tile read')
            self.events.append(('cell', *struct.unpack('>3h', cpu.mem_read(stack + 4, 6))))
            value = self.tiles[self.cell_index]
            self.cell_index += 1
        elif endpoint in ('stop', 'sound', 'query'):
            cue = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            self.events.append((endpoint, cue))
            if endpoint == 'query':
                if cue != 193:
                    raise AssertionError('Unexpected sound-state query')
                value = int(self.cue193_on)
        else:
            self.events.append(('actor', endpoint))
            self.actor_inputs.append(bytes(cpu.mem_read(self.A5 - 0x5056, 62)))
            tag = self.ACTOR_TAGS[endpoint]
            self.put_word(-0x5056, tag)
            self.put_word(-0x5056 + 60, tag + 1)
        cpu.reg_write(self.registers['d0'], value & 65535)
        destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
        cpu.reg_write(self.registers['a7'], stack + 4)
        cpu.reg_write(self.registers['pc'], destination)

    def mob(self):
        return struct.unpack('>8h', self.cpu.mem_read(self.A5 - 0x44a6, 16))


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince_fork = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeSlideRockMotion(parse_resource_fork(executable))
    counts, event_counts = Counter(), Counter()
    digest = hashlib.sha256()
    level_hashes = {}
    working = bytes((index * 11 + 7) % 256 for index in range(62))
    bank = bytes((index * 17 + 3) % 256 for index in range(512))

    def check(level, mob, label, **options):
        room = mob[2]
        left = struct.unpack_from('>H', level, 0x2080 + (room - 1) * 8)[0]
        expected = motion_reference(mob, left, **options)
        actor = bytearray((index * 7 + 13) % 256 for index in range(62))
        for index, value in zip((10, 12, 14), options.get('prince', (0, 0, 0))):
            struct.pack_into('>h', actor, index, value)
        machine.reset(level)
        machine.filled = options.get('filled', (False, False))
        machine.tiles = options.get('tiles', (1, 1))
        machine.cue193_on = options.get('cue193_on', False)
        machine.put_word(-0x439e, options.get('pending', -1))
        machine.cpu.mem_write(machine.A5 - 0x5056, working)
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(actor))
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *mob))
        machine.cpu.mem_write(0xb0000, bank)
        machine.call(10, 0x1d5c)
        expected_actor, expected_working = bytes(actor), working
        effects = [event[1] for event in expected['events'] if event[0] == 'actor']
        if effects:
            if len(effects) != 1 or machine.actor_inputs != [bytes(actor)]:
                raise AssertionError('Native working-actor copy differs')
            tag = 30001 if effects[0] == '5:3cee' else 30003
            struct.pack_into('>h', actor, 0, tag)
            struct.pack_into('>h', actor, 60, tag + 1)
            expected_actor = expected_working = bytes(actor)
        elif machine.actor_inputs:
            raise AssertionError('Unexpected actor endpoint')
        if (machine.mob() != expected['mob'] or machine.events != expected['events']
                or machine.word(-0x439e) != expected['pending']
                or machine.level_bytes(len(level)) != level
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != expected_actor
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != expected_working
                or bytes(machine.cpu.mem_read(0xb0000, 512)) != bank
                or machine.services):
            raise AssertionError(dict(label=label, mob=mob, options=options,
                                      expected=expected, actual=machine.mob(), events=machine.events))
        counts[label] += 1
        event_counts.update(event[0] for event in machine.events)
        event_counts.update(event[1] for event in machine.events if event[0] == 'actor')
        digest.update(struct.pack('>8hh', *machine.mob(), machine.word(-0x439e)))
        digest.update(json.dumps(machine.events).encode('ascii'))
        digest.update(expected_actor + expected_working)

    level = prince_fork['LEVL'][2009]['data']
    states = (-32768, -3, -2, -1, 0, 1, 2, 7, 8, 9, 99, 100, 101, 32767)
    for state, x, mark, filled in product(
            states, (0, 1, 2, 6, 7, 30, 31, 32, 51, 57, 58, 561),
            (-1, 0, 1), ((False, False), (False, True), (True, False), (True, True))):
        check(level, (x, 236, 28, mark, state, 6, 1, 459), 'control_thresholds', filled=filled)
    for front, edge, mark, on193, x in product(
            (0, 1, 2, 25), (0, 1, 2, 4, 7, 20, 25, 43, 49),
            (-1, 0, 1, 2), (False, True), (31, 57, 58)):
        check(level, (x, 236, 28, mark, -2, 6, 1, 459), 'tile_controls',
              tiles=(front, edge), cue193_on=on193)
    for pending, state, filled in product((-1, 191, 192, 193), (7, 8, 9, 100),
                                          ((False, False), (True, False))):
        check(level, (204, 236, 28, 0, state, 6, 1, 459), 'pending_sound',
              filled=filled, pending=pending)
    for frame, column, row in product((-1, 0, 86, 87, 88, 98, 99, 100, 32767),
                                       (0, 1, 2), (0, 1, 2, 3)):
        check(level, (65, 236, 28, 0, -2, 6, 1, 459), 'actor_admission',
              prince=(frame, column, row))
    for y, mark in product((-32768, -32767, 32766, 32767), (0, 1)):
        check(level, (58, y, 28, mark, -2, 6, 1, 459), 'y_word_limits', tiles=(1, 4))
    for number in range(10, 14):
        original = prince_fork['LEVL'][1999 + number]['data']
        if (struct.unpack_from('>H', original, 0x2186)[0],
                struct.unpack_from('>H', original, 0x218a)[0]) != (2, number):
            raise ValueError('Inconsistent original temple fixture')
        level_hashes[str(number)] = hashlib.sha256(original).hexdigest()
        for room in range(1, 33):
            for cell in range(30):
                if struct.unpack_from('>H', original, (room - 1) * 60 + cell * 2)[0] != 25:
                    continue
                row, col = divmod(cell, 10)
                for state in (-2, 2, 8, 100):
                    for x in (0, 1, col * 51):
                        check(original, (x, 116 + row * 120, room, 0, state, 6, row, col * 51),
                              'original_anchor_controls')
    # Explicit no-left-neighbor and linked-room controls without changing originals.
    for left in (0, 2):
        supplied = bytearray(level)
        struct.pack_into('>H', supplied, 0x2080, left)
        for x, mark in product((0, 1, 2), (-1, 0, 1)):
            check(bytes(supplied), (x, 32767, 1, mark, -2, 6, 1, 459), 'room_crossing')
    if set(machine.branches) != set(machine.BRANCHES.values()):
        raise AssertionError('A declared native branch control was not exercised')
    return dict(
        cases=dict(counts), events=dict(event_counts), mismatches=0,
        native_branches=dict(machine.branches),
        outputs_sha256=digest.hexdigest(), level_hashes=level_hashes,
        executable_sha256=hashlib.sha256(executable).hexdigest(),
        supplied=[
            '10:1656 filled-band predicate: up to two supplied independent booleans; X logged',
            '4:27ee ReadCell: supplied front/edge tile words; room/column/row logged; no cache writes',
            '5:5252 StopSound and 5:4d84 AddSound: record requests, no audio side effects',
            '5:52c8 PrinceSndOn: supplied cue193 boolean',
            '5:3cee and 6:1a84: record actor admission and replace working-actor end words with markers',
        ],
        scope=('Complete motion helper 10:1d5c-1fa6 with native IsWall3:4ef2, '
               'signed division19:4bb0 and actor copy4:4b02. Supplied records, geometry, '
               'audio state and actor outcomes; real level bytes used only for left links '
               'and anchor fixtures. Compare record, endpoint order/arguments, pending cue, '
               'entire level, 62-byte Prince/working actors and unrelated bank guards. '
               'NOT the full type6 driver: its subsequent CheckSlideRockCrush10:16f6 '
               'does not execute. No actual geometry predicate/cell cache, actor reaction, '
               'rendering, reachable state, FrameAdv cadence, save/load or gameplay claim.'),
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
