"""Bound native temple gate -> GenCtrl hanging decisions -> first actor clip."""

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_gate_actor_bank import NativeGateActorBank, bank_reference
from tools.probe_temple_gate_actor_clip import clip_reference, put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_services import NativeGateServices
from tools.probe_temple_plate_release import initial_state
from tools.probe_temple_slide_rock_update import actor_word


SPACE = frozenset((0, 9, 27, 47, 49))
WALL = frozenset((2, 7, 20, 25, 43))
IMPASSABLE = frozenset((11, 12, 13, 15, 23, 24, 26))
LATCHES = (-0x3488, -0x3486, -0x3484, -0x3482, -0x3480)


@dataclass(frozen=True)
class HangingInputs:
    held: int = 1
    up: int = 0
    cooldown: int = 0
    current: int = 1
    front: int = 1
    above: int = 1
    foreground: int = 0
    bars: int = 0
    release_word: int = 0


CASES = {
    'hold': HangingInputs(),
    'hold-space-above': HangingInputs(above=0),
    'hold-wall': HangingInputs(current=20),
    'hold-gate': HangingInputs(current=4),
    'release-word11': HangingInputs(release_word=11),
    'release': HangingInputs(held=0),
    'release-space': HangingInputs(held=0, current=0, front=9),
    'release-current-wall': HangingInputs(held=0, current=20),
    'release-front-wall': HangingInputs(held=0, front=20),
    'release-current-only': HangingInputs(held=0, front=0),
    'release-front-only': HangingInputs(held=0, current=0),
    'release-impassable-wall': HangingInputs(held=0, current=20, front=11),
    'release-wall-impassable': HangingInputs(held=0, current=11, front=20),
    'climb': HangingInputs(up=-1),
    'climb-gate47': HangingInputs(up=1, above=4, foreground=47),
    'climb-gate48': HangingInputs(up=1, above=4, foreground=48),
    'climb-gate-high-byte': HangingInputs(up=1, above=4, foreground=0xff2f),
    'climb-bars': HangingInputs(up=1, bars=1),
    'climb-cooldown': HangingInputs(up=1, cooldown=1),
    'climb-before-release': HangingInputs(held=0, up=1, release_word=11),
}


def hanging_reference(actor, sequences, inputs, latches):
    if (len(actor) != 62 or actor_word(actor, 8) != 0 or actor_word(actor, 26) == 1
            or actor_word(actor, 24) >= 0 or actor_word(actor, 16) not in (2, 6)
            or not 87 <= actor_word(actor, 10) <= 99 or actor_word(actor, 40) in (27, 110)):
        raise ValueError('Only live unarmed type0 hanging GenCtrl routing is bounded')
    if len(latches) != 5 or tuple(latches[2::2]) != (inputs.up, inputs.held):
        raise ValueError('Expected five supplied control latches matching up/held inputs')
    working, flags = bytearray(actor), list(latches)
    events = [('gen_ctrl',), ('hanging',)]
    foreground = None

    def select(number):
        if number not in sequences:
            raise ValueError('All selected original sequences must be prepared')
        events.extend((('jump_seq', number), ('resource', number)))
        for offset, value in ((36, 0), (38, number), (40, number)):
            put_actor(working, offset, value)

    def clear():
        events.append(('clear_controls',))
        flags[:4] = (0, 0, 0, 0)

    def release():
        nonlocal working
        events.append(('release',))
        clear()
        flags[3] = 1
        events.extend((('front_cell', inputs.front), ('current_cell', inputs.current)))
        if inputs.front in SPACE and inputs.current in SPACE:
            events.append(('preview',))
            saved = tuple(actor_word(working, field) for field in (36, 38, 40))
            old_pose = actor_word(working, 10) & 65535
            preview = clip_reference(working, sequences)
            working = bytearray(preview['actor'])
            events.extend(preview['events'])
            use99 = (actor_word(working, 10) & 65535) <= old_pose
            for field, value in zip((36, 38, 40), saved):
                put_actor(working, field, value)
            select(99 if use99 else 23)
            return
        current_floor = inputs.current not in SPACE | WALL | IMPASSABLE | {6, 34}
        front_floor = inputs.front not in SPACE | WALL | IMPASSABLE | {6, 34}
        if not current_floor and not front_floor:
            if inputs.front not in SPACE | WALL and inputs.current in WALL:
                front_floor = True
            elif inputs.current not in SPACE | WALL and inputs.front in WALL:
                current_floor = True
        if inputs.current in WALL:
            delta, sequence = -23, 11 if front_floor else 23
        elif not current_floor and front_floor:
            delta, sequence = -12, 11
        elif current_floor and not front_floor:
            delta, sequence = 10, 11
        else:
            delta, sequence = 0, 11 if current_floor and front_floor else 23
        if delta:
            put_actor(working, 4, actor_word(working, 4) + (delta if actor_word(working, 2) == 0 else -delta))
        select(sequence)

    if inputs.cooldown == 0 and inputs.up != 0:
        events.append(('climb',))
        clear()
        flags[2], flags[4] = 1, 1
        events.append(('above_cell', inputs.above, inputs.foreground))
        foreground = inputs.foreground
        narrow_gate = (inputs.above == 4 and (inputs.foreground & 255) >> 2 < 12
                       and actor_word(working, 2) == -1)
        if not narrow_gate:
            events.append(('bars', 0))
        select(73 if narrow_gate or inputs.bars else 10)
    elif inputs.held == 0 or actor_word(working, 52) == 11:
        put_actor(working, 52, 0)
        release()
    else:
        events.append(('current_cell', inputs.current))
        if ((actor_word(working, 16) != 6 and inputs.current in WALL)
                or (actor_word(working, 2) == -1 and inputs.current == 4)):
            select(25)
        else:
            events.append(('above_cell', inputs.above, inputs.foreground))
            foreground = inputs.foreground
            if inputs.above in SPACE:
                release()
    return dict(actor=bytes(working), latches=tuple(flags), foreground=foreground, events=events)


class NativeTempleHangingControl(NativeGateActorBank):
    RANGES = NativeGateActorBank.RANGES | {
        3: ((0x4da6, 0x4f24),),
        4: NativeGateActorBank.RANGES[4] + ((0x3e3a, 0x3e4e),),
        6: NativeGateActorBank.RANGES[6] + ((0x0560, 0x07e0), (0x18e0, 0x1bbc)),
    }
    CELLS = {(4, 0x35a6): ('current_cell', 'current'), (4, 0x3a48): ('front_cell', 'front'),
             (4, 0x3ff8): ('above_cell', 'above')}

    def reset(self, level):
        super().reset(level)
        self.inputs = HangingInputs()

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        stack = cpu.reg_read(self.registers['a7'])
        if (segment, offset) in self.CELLS:
            name, field = self.CELLS[segment, offset]
            value = getattr(self.inputs, field)
            event = (name, value)
            if name == 'above_cell':
                self.put_word(-0x34ae, self.inputs.foreground)
                event += (self.inputs.foreground,)
            self.events.append(event)
            self.services[name] += 1
            self.return_value(value)
            return
        if (segment, offset) == (10, 0x2036):
            argument = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            if argument != 0:
                raise AssertionError('Only the climb bars query0 is bounded')
            self.events.append(('bars', argument))
            self.services['bars'] += 1
            self.return_value(self.inputs.bars)
            return
        if (segment, offset) == (17, 0x330e):
            kind, number = struct.unpack('>4sh', cpu.mem_read(stack + 4, 6))
            if kind != b'SEQS' or number not in self.sequence_bytes:
                raise AssertionError('Unexpected original sequence resource request')
            self.events.append(('resource', number))
            self.return_value(self.sequence_bytes[number][0])
            return
        if (segment, offset) == (6, 0x0006):
            number = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            self.events.append(('jump_seq', number))
            # Bypass the older StopGate-only logger, not the native JumpSeq body.
            NativeGateServices.dispatch(self, cpu, address, size, user)
            return
        native = {(6, 0x0560): 'gen_ctrl', (6, 0x18e0): 'hanging', (6, 0x1998): 'climb',
                  (6, 0x1a84): 'release', (6, 0x1b7e): 'preview', (4, 0x3e3a): 'clear_controls'}
        if (segment, offset) in native:
            self.events.append((native[segment, offset],))
        super().dispatch(cpu, address, size, user)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    raw = {n: resources['SEQS'][n]['data'] for n in (2, 9, 10, 11, 23, 25, 47, 73, 99, 210)}
    sequences = {n: struct.unpack('>' + str(len(data) // 2) + 'h', data) for n, data in raw.items()}
    machine = NativeTempleHangingControl(parse_resource_fork(executable), raw)
    counts, outcomes, services, digest = Counter(), Counter(), Counter(), hashlib.sha256()
    inventory = []
    for number in range(10, 14):
        level = resources['LEVL'][1999 + number]['data']
        if (struct.unpack_from('>3h', level, 0x2186)[::2] != (2, number)
                or struct.unpack_from('>h', level, 0x21a4)[0] != 7):
            raise ValueError('Expected original temple/opponent headers')
        for room in range(1, struct.unpack_from('>h', level, 0x2180)[0] + 1):
            for cell in range(30):
                if struct.unpack_from('>h', level, (room - 1) * 60 + cell * 2)[0] == 4:
                    inventory.append((number, level, room, cell))
    if len(inventory) != 41:
        raise ValueError('Expected all41 original temple gate anchors')
    cache = struct.pack('>6H', 11, 13, 17, 19, 23, 29)
    mob = bytes((i * 7 + 13) % 256 for i in range(22))

    def compare_case(anchor, position, phase, facing, inputs, pose, cursor, sequence, label, mode=2):
        number, original, room, cell = anchor
        row, column = divmod(cell, 10)
        level = bytearray(original)
        struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, position)
        actor = bytearray(actor_fixture(room, row + 1, column, facing, mode))
        for field, value in ((4, 207 + column * 51), (6, row * 120 + 110), (10, pose), (18, 0), (20, 0),
                              (24, -1), (26, 0), (28, -1), (30, 3), (34, 0),
                              (36, cursor), (38, sequence), (40, sequence), (52, inputs.release_word)):
            put_actor(actor, field, value)
        state = dict(initial_state(level, ((cell, room, phase, 4),)),
                     prince=bytes(actor), working=bytes(range(62)))
        flags, expected_cache = (2, -3, inputs.up, 4, inputs.held), cache
        machine.reset(level)
        machine.inputs = inputs
        for offset, data in ((-0x5056, state['working']), (-0x50d2, state['prince']),
                             (-0x448e, state['trob_storage']), (-0x4818, state['os']),
                             (-0x43ee, struct.pack('>4h', *state['scratch'])), (-0x34b0, cache), (-0x44a6, mob)):
            machine.cpu.mem_write(machine.A5 + offset, data)
        for offset, value in tuple(zip(LATCHES, flags)) + ((-0x43e6, 1), (-0x4fc2, room),
                (-0x5008, -2), (-0x4490, 17), (-0x439e, 192), (-0x4f96, inputs.cooldown)):
            machine.put_word(offset, value)
        for operation in ('bank', 'load', 'control', 'animate'):
            machine.events, state['events'] = [], []
            machine.services.clear()
            if operation == 'bank':
                state = bank_reference(state)
                machine.call(5, 0x0c38)
                outcomes['gate-selected47' if actor_word(state['prince'], 38) == 47 else 'gate-kept-hang'] += 1
            elif operation == 'load':
                state.update(working=state['prince'], events=[('load_kid',)])
                machine.call(4, 0x4b02)
            elif operation == 'control':
                expected = hanging_reference(state['working'], sequences, inputs, flags)
                state.update(working=expected['actor'], events=expected['events'])
                flags = expected['latches']
                if expected['foreground'] is not None:
                    expected_cache = cache[:2] + struct.pack('>H', expected['foreground']) + cache[4:]
                machine.call(6, 0x0560)
                outcomes[f'control-source{actor_word(state["working"], 40)}'] += 1
                outcomes['preview'] += ('preview',) in state['events']
            else:
                expected = clip_reference(state['working'], sequences)
                state.update(working=expected['actor'], events=expected['events'])
                machine.call(4, 0x2c0c)
                outcomes[f'after-mode{actor_word(state["working"], 16)}'] += 1
            expected_services = Counter({'sound': 'gate_sound', 'redraw': 'gate_redraw', 'audio': 'audio_request'}
                                        .get(e[0], e[0]) for e in state['events']
                                        if e[0] in {'sound', 'redraw', 'audio', 'current_cell', 'front_cell', 'above_cell', 'bars'})
            actual = machine.snapshot(len(level))
            if (actual != state or machine.services != expected_services
                    or tuple(machine.word(offset) for offset in LATCHES) != flags
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x34b0, 12)) != expected_cache
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x44a6, 22)) != mob
                    or machine.word(-0x5008) != -2 or machine.word(-0x4490) != 17
                    or machine.word(-0x439e) != 192 or machine.word(-0x4f96) != inputs.cooldown):
                raise AssertionError(dict(anchor=(number, room, cell), inputs=asdict(inputs),
                                          fixture=(label, position, phase, facing, pose, cursor, sequence, mode), operation=operation,
                                          differences={k: (actual[k], state[k]) for k in state if actual[k] != state[k]},
                                          flags=(tuple(machine.word(o) for o in LATCHES), flags),
                                          services=(machine.services, expected_services)))
            machine.verify_sequences()
            counts[f'{label}:{operation}'] += 1
            services.update(machine.services)
            digest.update(state['level'] + state['prince'] + state['working'] + state['trob_storage'] + state['os'])
            digest.update(json.dumps([state['scratch'], state['events'], flags, expected_cache.hex()]).encode('ascii'))

    for anchor, (position, phase), facing, inputs in product(
            inventory, ((3, 1), (12, 1), (120, 4), (80, 2)), (-1, 0), CASES.values()):
        compare_case(anchor, position, phase, facing, inputs, 91, 3, 9, 'connected-gates')
    # Supplied tile pairs/poses are branch controls, not reachable level placements.
    for current, front, facing, (pose, cursor, sequence) in product(
            range(52), range(52), (-1, 0), ((91, 3, 9), (87, 1, 210))):
        compare_case(inventory[0], 12, 1, facing, HangingInputs(held=0, current=current, front=front),
                     pose, cursor, sequence, 'release-tile-pairs')
    for current, above, facing, mode in product(range(52), range(52), (-1, 0), (2, 6)):
        compare_case(inventory[0], 12, 1, facing, HangingInputs(current=current, above=above),
                     91, 3, 9, 'hold-tile-pairs', mode)
    for foreground, bars, facing in product((0, 1, 47, 48, 255, 0xff2f, 0xff30), (0, 1), (-1, 0)):
        compare_case(inventory[0], 12, 1, facing, HangingInputs(up=1, above=4, foreground=foreground, bars=bars),
                     91, 3, 9, 'climb-thresholds')
    return dict(cases=dict(counts), traces=sum(counts.values()) // 4, mismatches=0,
                outcomes=dict(outcomes), services=dict(services), outputs_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(), inputs={k: asdict(v) for k, v in CASES.items()},
                sequence_sha256={str(n): hashlib.sha256(data).hexdigest() for n, data in raw.items()},
                level_sha256={str(n): hashlib.sha256(resources['LEVL'][1999 + n]['data']).hexdigest() for n in range(10, 14)},
                supplied_services=['4:35a6 current cell kind', '4:3a48 front cell kind',
                                   '4:3ff8 above kind/foreground', '10:2036 bars query0 bool',
                                   '5:3828/0fe6/4d84 cue/redraw/audio requests',
                                   '17:330e and4:3098 prepared original sequence handles; state0 handle traps'],
                scope='Native AnimTrobs -> LoadKid -> GenCtrl unarmed living type0 hanging route '
                      '-> real6:18e0/1998/1a84/1b7e/JumpSeq -> first AnimChar. Four separately checked '
                      'calls per trace; no original coordinator/PlayerCtrl wrapper, input sampling, '
                      'physical geometry/support/fall/contact/death, save/reset, audio/pixels or runtime integration. '
                      'Cell/bars responses, placements, initial gate states and latches are supplied.')


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
