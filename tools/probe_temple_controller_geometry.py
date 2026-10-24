"""Execute real temple cell and sliding-rock queries inside the Prince controller."""

import argparse
from collections import Counter
from dataclasses import replace
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_gate_actor_clip import NativeGateActorClip, put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_hanging_control import LATCHES, WALL
from tools.probe_temple_plate_release import initial_state
from tools.probe_temple_player_control import AXES, SAVED_LATCHES, NativeTemplePlayerControl, PlayerInputs, player_reference
from tools.probe_temple_slide_rock_geometry import NativeSlideRockGeometry, TempleCellReader
from tools.probe_temple_slide_rock_motion import trunc_div
from tools.probe_temple_world_prince import EDGE_DESTINATIONS, EDGE_SOURCES, world_reference


MOB_BANK = 0xb0010


def left_edge_reference(level, record, facing, width):
    edge = signed_word(record[0] + 223 - 5)
    argument = signed_word(edge - 51)
    before_divide = signed_word(argument - 22)
    dividend = signed_word(before_divide - 4)
    quotient = trunc_div(dividend)
    remainder = dividend - quotient * 51
    edge_column = signed_word(quotient - 4 - int(before_divide < 0))
    raw_offset = (record[2] - 1) * 60 + (record[6] * 10 + edge_column) * 2
    if not 0 <= raw_offset <= len(level) - 2 or not -2 <= edge_column <= 12:
        raise ValueError('Raw left-edge lookup outside the supplied level/table bounds')
    raw_kind = struct.unpack_from('>h', level, raw_offset)[0]
    clipped = raw_kind in WALL or raw_kind == 4
    if clipped:
        boundary = signed_word(258 + edge_column * 51 + 39)
        if facing == 0:
            boundary = signed_word(boundary + width)
        edge = max(edge, boundary)
    return dict(edge=edge, remainder=remainder, clipped=clipped)


def rock_in_cell_reference(level, cache, bank, facing, width, margin=0):
    """10:2036 with real10:180e/1a9e logic; bounded static bank and raw level reads."""
    if len(bank) > 30 or facing not in (-1, 0) or not 0 <= margin <= 51:
        raise ValueError('Outside the bounded static rock-query domain')
    _kind, _foreground, _index, room, column, row = cache
    record = next((record for record in bank if record[5] == 6 and record[3] != -1
                   and record[2] == room and record[6] == row), None)
    events = [('rock_in_cell', margin), ('rock_edge', 0, room, row)]
    if record is None:
        return dict(result=False, events=events, remainder=None)
    right = signed_word(record[0] + 223 + 56)
    if right == 0:
        return dict(result=False, events=events, remainder=None)
    right = signed_word(right - 223)
    left_cell, right_cell = signed_word(column * 51), signed_word(column * 51 + 51)
    span = 51 - margin
    if left_cell + span <= right <= right_cell + span:
        return dict(result=True, events=events, remainder=None)
    events.append(('rock_edge', -1, room, row))
    left = left_edge_reference(level, record, facing, width)
    if left['clipped']:
        events.append(('clip_left',))
    edge = signed_word(left['edge'] - 223)
    return dict(result=left_cell - margin <= edge <= right_cell - margin,
                events=events, remainder=left['remainder'])


def geometry_player_reference(actor, sequences, inputs, state):
    room, column, row = (struct.unpack_from('>h', actor, field)[0] for field in (22, 12, 14))
    facing = struct.unpack_from('>h', actor, 2)[0]

    def projection(col, r):
        reader = TempleCellReader(state['level'], state['view'])
        reader.cache = struct.unpack('>6h', state['cell_cache'])
        kind = reader.read(room, col, r)
        return kind, reader.cache

    current, _ = projection(column, row)
    front, _ = projection(column + (1 if facing == -1 else -1), row)
    above, above_cache = projection(column, row - 1)
    obstacle = rock_in_cell_reference(state['level'], above_cache, state['mob_records'], facing, state['frame_width'])
    derived = replace(inputs, current=current, front=front, above=above,
                      foreground=above_cache[1] & 65535, bars=int(obstacle['result']))
    result = player_reference(actor, sequences, derived, state)
    reader = TempleCellReader(state['level'], state['view'])
    reader.cache = struct.unpack('>6h', state['cell_cache'])
    events = []
    remainder = state['division_remainder']
    for event in result['events']:
        if event[0] in ('current_cell', 'front_cell', 'above_cell'):
            col, r = column, row
            if event[0] == 'front_cell':
                col += 1 if facing == -1 else -1
            elif event[0] == 'above_cell':
                r -= 1
            events.extend(((event[0],), ('read_cell', room, col, r)))
            expected_kind = reader.read(room, col, r)
            if expected_kind != event[1]:
                raise AssertionError('Projected cell kind differed from ordered native-query model')
        elif event[0] == 'bars':
            query = rock_in_cell_reference(state['level'], reader.cache, state['mob_records'], facing,
                                           state['frame_width'], event[1])
            events.extend(query['events'])
            if query['remainder'] is not None:
                remainder = query['remainder']
        else:
            events.append(event)
    result['events'] = events
    result['updates'].update(cell_cache=struct.pack('>6h', *reader.cache), division_remainder=remainder)
    return result


class NativeTempleControllerGeometry(NativeTemplePlayerControl):
    RANGES = {segment: NativeTemplePlayerControl.RANGES.get(segment, ()) + NativeSlideRockGeometry.RANGES.get(segment, ())
              for segment in NativeTemplePlayerControl.RANGES.keys() | NativeSlideRockGeometry.RANGES.keys()}
    RANGES[4] += ((0x35a6, 0x35b8), (0x3a48, 0x3a70), (0x3ff8, 0x400e), (0x3ad6, 0x3aea))
    RANGES[5] += ((0x293c, 0x2994), (0x48b0, 0x48dc))
    RANGES[10] += ((0x180e, 0x18f2), (0x1a9e, 0x1ae8), (0x2036, 0x20e8))
    CELLS = {}

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        stack = cpu.reg_read(self.registers['a7'])
        cell_entries = {0x35a6: 'current_cell', 0x3a48: 'front_cell', 0x3ff8: 'above_cell'}
        if segment == 4 and offset in cell_entries:
            self.events.append((cell_entries[offset],))
        elif (segment, offset) == (4, 0x27ee):
            self.events.append(('read_cell', *struct.unpack('>3h', cpu.mem_read(stack + 4, 6))))
        elif (segment, offset) == (10, 0x180e):
            self.events.append(('rock_edge', *struct.unpack('>3h', cpu.mem_read(stack + 4, 6))))
        elif (segment, offset) == (10, 0x18a8):
            self.events.append(('clip_left',))
        elif (segment, offset) == (10, 0x2036):
            self.events.append(('rock_in_cell', struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]))
            # Skip the legacy supplied-bool endpoint at this entry only.
            NativeGateActorClip.dispatch(self, cpu, address, size, user)
            return
        super().dispatch(cpu, address, size, user)

    def snapshot(self, size):
        count = self.word(-0x4490)
        return dict(super().snapshot(size), division_remainder=self.word(-0x481c),
                    frame_width=self.word(-0x3566) - self.word(-0x3564),
                    mob_records=tuple(struct.unpack('>8h', self.cpu.mem_read(MOB_BANK + i * 16, 16)) for i in range(count)),
                    mob_storage=bytes(self.cpu.mem_read(MOB_BANK - 16, 512)))


def direct_rock_controls(machine, original):
    counts, events, digest = Counter(), Counter(), hashlib.sha256()
    for x, column, margin, facing, width, kind in product(
            (102, 148, 153, 199, 200, 204, 255, 306), range(7), (0, 5, 51), (-1, 0), (0, 18, 40), (0, 1, 4, 20)):
        level = bytearray(original)
        for cell in range(10):
            struct.pack_into('>h', level, cell * 2, kind)
        cache = (1, 0, column, 1, column, 0)
        bank = ((x, 116, 1, 0, -2, 6, 0, 459),)
        expected = rock_in_cell_reference(level, cache, bank, facing, width, margin)
        actor = actor_fixture(1, 1, column, facing, 2)
        saved, trobs = bytes(range(62)), bytes((i * 13 + 7) % 256 for i in range(160))
        storage = bytearray((i * 19 + 7) % 256 for i in range(512))
        struct.pack_into('>8h', storage, 16, *bank[0])
        machine.reset(level)
        machine.cpu.mem_write(MOB_BANK - 16, bytes(storage))
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', MOB_BANK))
        machine.cpu.mem_write(machine.A5 - 0x5056, actor)
        machine.cpu.mem_write(machine.A5 - 0x50d2, saved)
        machine.cpu.mem_write(machine.A5 - 0x448e, trobs)
        machine.cpu.mem_write(machine.A5 - 0x34b0, struct.pack('>6h', *cache))
        for offset, value in ((-0x4490, 1), (-0x481c, 61), (-0x3564, 400), (-0x3566, 400 + width)):
            machine.put_word(offset, value)
        returned = machine.call(10, 0x2036, (margin,))
        remainder = 61 if expected['remainder'] is None else expected['remainder']
        if (returned != int(expected['result']) or machine.events != expected['events'] or machine.services
                or machine.word(-0x481c) != remainder or machine.word(-0x4490) != 1
                or machine.level_bytes(len(level)) != level
                or bytes(machine.cpu.mem_read(MOB_BANK - 16, 512)) != storage
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != actor
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != saved
                or bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)) != trobs
                or struct.unpack('>6h', machine.cpu.mem_read(machine.A5 - 0x34b0, 12)) != cache):
            raise AssertionError(dict(direct_inputs=(x, column, margin, facing, width, kind), returned=returned,
                                      actual_events=machine.events, expected=expected, remainder=machine.word(-0x481c)))
        machine.verify_sequences()
        counts[f'cell-margin{margin}'] += 1
        events.update(event[0] for event in machine.events)
        digest.update(bytes(level) + actor + bytes(storage) + struct.pack('>2h', returned, remainder))
        digest.update(json.dumps(machine.events).encode('ascii'))
        # Compare the edge itself too: a correct cell bool can conceal bad clipping.
        machine.events = []
        machine.put_word(-0x481c, 61)
        left = left_edge_reference(level, bank[0], facing, width)
        returned = signed_word(machine.call(10, 0x180e, (-1, 1, 0)))
        expected_events = [('rock_edge', -1, 1, 0)] + ([('clip_left',)] if left['clipped'] else [])
        if (returned != left['edge'] or machine.events != expected_events or machine.services
                or machine.word(-0x481c) != left['remainder'] or machine.level_bytes(len(level)) != level
                or bytes(machine.cpu.mem_read(MOB_BANK - 16, 512)) != storage
                or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != actor
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != saved
                or bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)) != trobs
                or struct.unpack('>6h', machine.cpu.mem_read(machine.A5 - 0x34b0, 12)) != cache):
            raise AssertionError(dict(left_inputs=(x, column, margin, facing, width, kind),
                                      returned=returned, expected=left, events=machine.events))
        counts['left-edge'] += 1
        events.update(event[0] for event in machine.events)
        digest.update(struct.pack('>2h', returned, left['remainder']) + json.dumps(machine.events).encode('ascii'))
    return dict(cases=dict(counts), comparisons=sum(counts.values()), mismatches=0, events=dict(events),
                outputs_sha256=digest.hexdigest(),
                scope='Direct native SlideRockInCell/GetSlideRockX with supplied static type6 bank, raw tile '
                      'controls, cached cell, frame width and margins0/5/51. Not extra world frames or physical contact.')


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    raw = {n: resources['SEQS'][n]['data'] for n in (2, 9, 10, 11, 23, 25, 47, 73, 99, 210)}
    sequences = {n: struct.unpack('>' + str(len(data) // 2) + 'h', data) for n, data in raw.items()}
    machine = NativeTempleControllerGeometry(parse_resource_fork(executable), raw)
    levels = {n: resources['LEVL'][1999 + n]['data'] for n in range(10, 14)}
    counts, events, outcomes, digest = Counter(), Counter(), Counter(), hashlib.sha256()
    scratch = bytearray((i * 7 + 13) % 256 for i in range(22))
    struct.pack_into('>I', scratch, 16, MOB_BANK)
    scratch = bytes(scratch)
    samples = ((0, 0, -1), (0, -1, -1), (0, 0, 0))
    for n, level in levels.items():
        if (struct.unpack_from('>3h', level, 0x2186)[::2] != (2, n)
                or struct.unpack_from('>h', level, 0x21a4)[0] != 7):
            raise ValueError('Expected original temple/opponent headers')
    machine.reset(levels[10])
    if ((machine.word(-0x4b96), machine.word(-0x4b94)) != (1, -1)
            or tuple(machine.word(-0x4b86 + i * 2) for i in range(-2, 13)) != tuple(258 + i * 51 for i in range(-2, 13))):
        raise ValueError('Unexpected native front-offset or column boundary table')

    def compare(number, room, column, row, facing, sample, label, *, gate=None, bank=(), width=18, view=None, level=None):
        level = bytearray(levels[number] if level is None else level)
        records = ()
        if gate is not None:
            cell, position, phase = gate
            struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, position)
            records = ((cell, room, phase, 4),)
        inputs = PlayerInputs(raw_axes=sample)
        actor = bytearray(actor_fixture(room, row, column, facing, 2))
        for field, value in ((4, 207 + column * 51), (6, row * 120 - 10), (10, 91), (18, 0), (20, 0),
                (24, -1), (26, 0), (28, -1), (30, 3), (34, 0), (36, 3), (38, 9), (40, 9), (52, 0), (58, -1)):
            put_actor(actor, field, value)
        storage = bytearray((i * 19 + 7) % 256 for i in range(512))
        for index, record in enumerate(bank):
            struct.pack_into('>8h', storage, 16 + index * 16, *record)
        state = dict(initial_state(level, records), prince=bytes(actor), working=bytes(range(62)), countdown=-2,
                     saved_edges=(211, 223, 227, 229), exit_flag=1234, view=room if view is None else view, result=-2,
                     cooldown=0, input_latches=(0, 0, 0, 0, 0), working_latches=(31, 37, 41, 43, 47),
                     raw_axes=(53, 59, 61), cell_cache=struct.pack('>6h', 0, 0, 0, 0, -32768, -32768),
                     division_remainder=61, frame_width=width, mob_records=tuple(bank), mob_storage=bytes(storage))
        machine.reset(level)
        machine.inputs = inputs
        for destination, data in ((-0x5056, state['working']), (-0x50d2, state['prince']),
                (-0x448e, state['trob_storage']), (-0x4818, state['os']), (-0x43ee, struct.pack('>4h', *state['scratch'])),
                (-0x34b0, state['cell_cache']), (-0x44a6, scratch)):
            machine.cpu.mem_write(machine.A5 + destination, data)
        machine.cpu.mem_write(MOB_BANK - 16, bytes(storage))
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', MOB_BANK))
        machine.cpu.mem_write(machine.A5 - 0x43a4, b'\0' * 4)
        for destinations, values in ((SAVED_LATCHES, state['input_latches']), (LATCHES, state['working_latches']),
                (AXES, state['raw_axes']), (EDGE_DESTINATIONS, state['saved_edges']),
                ((-0x3560, -0x3562, -0x3568, -0x356a), EDGE_SOURCES)):
            for destination, value in zip(destinations, values):
                machine.put_word(destination, value)
        for destination, value in ((-0x43e6, len(records)), (-0x4fc2, state['view']), (-0x5008, -2),
                (-0x4490, len(bank)), (-0x439e, 192), (-0x4f96, 0), (-0x4fee, 1), (-0x4fac, 0),
                (-0x4f90, 0), (-0x4fce, 1), (-0x4faa, 1234), (-0x4fa6, 0), (-0x5200, 0),
                (-0x4fa8, 0), (-0x4ffe, 0), (-0x4f92, number), (-0x4fd2, number), (-0x43b6, 0),
                (-0x481c, 61), (-0x3564, 400), (-0x3566, 400 + width)):
            machine.put_word(destination, value)
        expected = world_reference(state, sequences, inputs, geometry_player_reference)
        returned = signed_word(machine.call(2, 0x6224))
        actual = dict(machine.snapshot(len(level)), result=returned)
        names = set(machine.ENDPOINTS.values()) | {'sample_input'}
        expected_services = Counter({'sound': 'gate_sound', 'redraw': 'gate_redraw', 'audio': 'audio_request'}
                                    .get(e[0], e[0]) for e in expected['events']
                                    if e[0] in names | {'sound', 'redraw', 'audio'})
        if (actual != expected or machine.services != expected_services
                or bytes(machine.cpu.mem_read(machine.A5 - 0x44a6, 22)) != scratch
                or machine.word(-0x439e) != 192):
            raise AssertionError(dict(fixture=(number, room, column, row, facing, sample, label, gate, bank, width, view),
                                      differences={k: (actual[k], expected[k]) for k in expected if actual[k] != expected[k]},
                                      services=(machine.services, expected_services)))
        machine.verify_sequences()
        counts[label] += 1
        events.update(e[0] for e in expected['events'])
        outcomes[f'source{struct.unpack_from(">h", expected["prince"], 40)[0]}'] += 1
        digest.update(expected['level'] + expected['prince'] + expected['working'] + expected['trob_storage']
                      + expected['cell_cache'] + expected['mob_storage'])
        digest.update(json.dumps([expected['events'], expected['division_remainder'], expected['input_latches']]).encode('ascii'))

    for number, level in levels.items():
        maximum = struct.unpack_from('>H', level, 0x2180)[0]
        for room, cell in product(range(1, maximum + 1), range(30)):
            row, column = divmod(cell, 10)
            compare(number, room, column, row, -1, samples[1], 'all-admitted-cell-climbs')
            if column in (0, 9):
                for facing, sample in product((-1, 0), samples):
                    compare(number, room, column, row, facing, sample, 'room-edge-controls')
            if struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0] == 4:
                for (position, phase), facing, sample in product(((3, 1), (12, 1), (120, 4)), (-1, 0), samples):
                    compare(number, room, column, row + 1, facing, sample, 'gate-controller-geometry', gate=(cell, position, phase))
    for number, room, column, row, facing, sample in product((10, 12, 13), (0, 29), (-1, 10), (0, 3), (-1, 0), samples):
        compare(number, room, column, row, facing, sample, 'normalized-border-controls', view=4 if number == 13 else 1)
    # Static rock-bank controls deliberately supplied near a valid level10 cell.
    for x, facing, width, topology in product((102, 153, 204, 255, 306), (-1, 0), (0, 18, 40), ('one', 'removed', 'wrong-row', 'first-match')):
        rock = (x, 116, 1, 0, -2, 6, 0, 459)
        bank = (rock,)
        if topology == 'removed':
            bank = (rock[:3] + (-1,) + rock[4:],)
        elif topology == 'wrong-row':
            bank = (rock[:6] + (1, 459),)
        elif topology == 'first-match':
            bank = (rock, (306, 116, 1, 0, 100, 6, 0, 459))
        for column in (1, 2, 3, 4, 5):
            compare(10, 1, column, 1, facing, samples[1], 'static-rock-climb-controls', bank=bank, width=width)
    controls = direct_rock_controls(machine, levels[10])
    return dict(cases=dict(counts), comparisons=sum(counts.values()), mismatches=0, events=dict(events), outcomes=dict(outcomes),
                direct_rock_controls=controls,
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
                level_sha256={str(n): hashlib.sha256(data).hexdigest() for n, data in levels.items()},
                sequence_sha256={str(n): hashlib.sha256(data).hexdigest() for n, data in raw.items()},
                supplied_services={f'{s}:{o:04x}': name for (s, o), name in machine.ENDPOINTS.items()},
                other_supplied=['2:55d2 sampled axes', '5:3828/0fe6/4d84 cue/redraw/audio',
                                '17:330e/4:3098 prepared sequence handles; state0 handle traps'],
                scope='Actual world/Prince/PlayerCtrl/GenCtrl plus current/front/above ReadCell and SlideRockInCell '
                      'with native bank lookup, raw left-edge clipping and signed column division. One update per supplied '
                      'actor/static-bank fixture; empty or supplied TROB gates. Input polling, other frame/contact/hazards, '
                      'MOB motion/generation, opponents and presentation/time services supplied. No physical reachability, '
                      'outer FrameAdv, full collision/death, persistent gameplay, saves or temple runtime integration.')


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
