"""Execute the native temple world/Prince caller with explicit service boundaries."""

import argparse
from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_gate_actor_bank import NativeGateActorBank, bank_layouts, bank_reference
from tools.probe_temple_gate_actor_clip import clip_reference, put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_plate_release import initial_state
from tools.probe_temple_slide_rock_update import actor_word


EDGE_SOURCES = (101, 103, 107, 109)
EDGE_DESTINATIONS = (-0x356e, -0x3570, -0x3572, -0x3574)


@dataclass(frozen=True)
class CallerInputs:
    live: int = 1
    suppress_animation: int = 0
    control_result: int = -2
    invulnerable: int = 0
    prep_result: int = -2
    time_left: int = 1
    force_mode: int | None = None
    floating: int = 0
    special_actor: int = 0
    initial_countdown: int = -2


CASES = {
    'ordinary': CallerInputs(),
    'not-live': CallerInputs(live=0),
    'suppress-animation': CallerInputs(suppress_animation=1),
    'control-minus-one': CallerInputs(control_result=-1),
    'control-positive': CallerInputs(control_result=7),
    'invulnerable': CallerInputs(invulnerable=1),
    'cut-return': CallerInputs(prep_result=7),
    'time-zero': CallerInputs(time_left=0),
    'forced-mode4': CallerInputs(force_mode=4),
    'forced-mode4-floating': CallerInputs(force_mode=4, floating=1),
    'special-actor10': CallerInputs(special_actor=10),
    'countdown-zero': CallerInputs(initial_countdown=0),
    'countdown-one': CallerInputs(initial_countdown=1),
}


def gravity_reference(actor, floating):
    result = bytearray(actor)
    if actor_word(result, 16) in (4, 9):
        speed = actor_word(result, 20)
        if floating:
            speed = min(8, signed_word(speed + 2))
        elif speed < 63:
            speed = min(63, signed_word(speed + 6))
        put_actor(result, 20, speed)
    events = [('gravity',), ('vertical_move',)]
    if actor_word(result, 6) < 3650:
        put_actor(result, 6, actor_word(result, 6) + actor_word(result, 20))
        if actor_word(result, 16) == 4:
            delta = actor_word(result, 18)
            if floating:
                delta >>= 1
            put_actor(result, 4, actor_word(result, 4) + (delta if actor_word(result, 2) == 0 else -delta))
            events.append(('frame',))
    return bytes(result), events


def prince_reference(state, sequences, inputs):
    result = dict(state)
    events = list(state['events']) + [('prince',), ('load_kid',), ('outside_check',)]
    saved = state['prince']
    actor = bytearray(saved)

    def controls():
        events.append(('controls', inputs.control_result, inputs.force_mode))
        if inputs.force_mode is not None:
            put_actor(actor, 16, inputs.force_mode)
        return inputs.control_result

    if actor_word(saved, 22) == 0:
        control = controls()
        events.extend((('outside_fall',), ('prince_copy',)))
        return dict(result, prince=bytes(actor), working=bytes(actor), events=events, result=control)

    # The fixture's opponent index is -1; nearest returns supplied -1 -> slot0.
    if actor_word(actor, 58) != -1:
        raise ValueError('This caller reference supplies opponent index-1 only')
    events.extend((('nearest', 1), ('load_opponent', 0), ('frame',), ('sword',), ('edges',)))
    control = controls()
    if control != -1 and inputs.live:
        if inputs.suppress_animation:
            control = 1
        else:
            clip = clip_reference(bytes(actor), sequences)
            actor = bytearray(clip['actor'])
            events.extend(clip['events'])
            if actor_word(actor, 10) != 0:
                moved, motion_events = gravity_reference(actor, inputs.floating)
                actor = bytearray(moved)
                events.extend(motion_events)
                events.extend((('frame',), ('sword',), ('edges',), ('fight_distance',),
                               ('barrier',), ('collide',), ('gate_contact',), ('floor',), ('pressure',),
                               ('spikes',), ('temple_hazard',)))
                if not inputs.invulnerable:
                    events.append(('hit_hazard',))
                events.append(('scythe_start',))
                if not inputs.invulnerable:
                    events.append(('scythe_hit',))
                events.append(('row_shake',))
            control = 0
    countdown = result['countdown']
    if countdown >= 0:
        if (countdown == 0 and actor_word(saved, 28) < 0
                and actor_word(saved, 16) not in (3, 4)):
            events.append(('audio', 110))
            countdown = -2
        else:
            countdown = signed_word(countdown - 1)
    if inputs.live:
        result['saved_edges'] = EDGE_SOURCES
    events.append(('prince_copy',))
    return dict(result, prince=bytes(actor), working=bytes(actor), events=events,
                countdown=countdown, result=control)


def world_reference(state, sequences, inputs):
    result = dict(state, events=[('world',)])
    if inputs.live:
        prefix = result['events'] + [('rubble',), ('bank',)]
        result = bank_reference(result)
        result['events'] = prefix + result['events']
        if inputs.special_actor == 10:
            result['events'].append(('opponent_check',))
        result['events'].extend((('generators', state['view']), ('nearest_sides',)))
    result = prince_reference(result, sequences, inputs)
    if not inputs.live or result['result'] == -1:
        return result
    if result['result'] != 0:
        result['events'].extend((('opponents',), ('environment',), ('meters',), ('prepare_cut', 0)))
        result['result'] = -2
        return result
    result['events'].append(('opponents',))
    if not inputs.invulnerable and state['view'] != 0:
        result['events'].extend((('strike',), ('stab',)))
    result['events'].extend((('effects',), ('alert',), ('environment',), ('meters',),
                             ('cut_all',), ('prepare_cut', 0)))
    result['result'] = inputs.prep_result
    if inputs.prep_result == -2:
        result['events'].extend((('cut_opponent',), ('clock',)))
        if not inputs.time_left:
            result['events'].append(('timeout',))
            result['exit_flag'], result['result'] = 0, -1
    return result


class NativeTempleWorldPrince(NativeGateActorBank):
    RANGES = NativeGateActorBank.RANGES | {
        2: ((0x6224, 0x648a),),
        4: NativeGateActorBank.RANGES[4] + ((0x341a, 0x34e0), (0x3788, 0x37c8)),
    }
    ENDPOINTS = {
        (5, 0x29e8): 'rubble', (4, 0x14c6): 'opponent_check', (6, 0x3a0c): 'generators',
        (2, 0x6e7e): 'nearest_sides', (6, 0x36f2): 'nearest', (4, 0x3312): 'load_opponent',
        (4, 0x2a72): 'frame', (3, 0x0ac8): 'sword', (4, 0x5cbc): 'edges',
        (4, 0x3b88): 'controls', (4, 0x3688): 'outside_fall', (2, 0x6c64): 'fight_distance',
        (4, 0x4e34): 'barrier', (4, 0x54da): 'collide', (4, 0x60e4): 'gate_contact',
        (5, 0x1202): 'floor', (5, 0x127e): 'pressure', (5, 0x3c42): 'spikes',
        (10, 0x2540): 'temple_hazard', (5, 0x3af8): 'hit_hazard',
        (5, 0x57bc): 'scythe_start', (5, 0x588a): 'scythe_hit', (2, 0x6c1c): 'row_shake',
        (2, 0x648c): 'opponents', (6, 0x57b2): 'strike', (6, 0x5092): 'stab',
        (5, 0x4cde): 'effects', (2, 0x6b46): 'alert', (2, 0x7124): 'environment',
        (2, 0x54d6): 'meters', (6, 0x4382): 'cut_all', (2, 0x532c): 'prepare_cut',
        (6, 0x424c): 'cut_opponent', (2, 0x51f4): 'clock', (2, 0x7194): 'timeout',
    }

    def reset(self, level):
        super().reset(level)
        self.inputs = CallerInputs()

    def dispatch(self, cpu, address, size, user):
        segment, offset = divmod(address - self.CODE_BASE, 0x10000)
        name = self.ENDPOINTS.get((segment, offset))
        if name is not None:
            stack = cpu.reg_read(self.registers['a7'])
            event, value = (name,), 0
            if name == 'controls':
                event = (name, self.inputs.control_result, self.inputs.force_mode)
                value = self.inputs.control_result
                if self.inputs.force_mode is not None:
                    self.put_word(-0x5046, self.inputs.force_mode)
            elif name in ('generators', 'nearest', 'load_opponent', 'prepare_cut'):
                event = (name, struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0])
                if name == 'nearest':
                    value = -1
                elif name == 'prepare_cut':
                    value = self.inputs.prep_result
            self.events.append(event)
            self.services[name] += 1
            self.return_value(value & 65535)
            return
        native_events = {(2, 0x6224): 'world', (5, 0x0c38): 'bank', (2, 0x62e6): 'prince',
                         (4, 0x3788): 'outside_check', (4, 0x341a): 'gravity',
                         (4, 0x3464): 'vertical_move', (2, 0x6472): 'prince_copy'}
        if (segment, offset) in native_events:
            self.events.append((native_events[segment, offset],))
        super().dispatch(cpu, address, size, user)

    def snapshot(self, size):
        return dict(super().snapshot(size), countdown=self.word(-0x5008),
                    saved_edges=tuple(self.word(offset) for offset in EDGE_DESTINATIONS),
                    exit_flag=self.word(-0x4faa), view=self.word(-0x4fc2))


def gravity_controls(machine, level):
    counts, digest = Counter(), hashlib.sha256()
    saved, bank = bytes(range(62)), bytes((i * 19 + 7) % 256 for i in range(160))
    for mode, vx, vy, y, facing, floating in product(
            (0, 2, 4, 5, 9), (-3, 0, 5), (-8, 0, 7, 8, 58, 62, 63, 70),
            (-32760, 100, 3649, 3650, 32767), (-1, 0), (0, 1)):
        actor = bytearray(actor_fixture(3, 1, 2, facing, mode))
        for offset, value in ((4, 400), (6, y), (18, vx), (20, vy)):
            put_actor(actor, offset, value)
        expected, expected_events = gravity_reference(actor, floating)
        machine.reset(level)
        machine.inputs = CallerInputs(floating=floating)
        machine.put_word(-0x4fa6, floating)
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(actor))
        machine.cpu.mem_write(machine.A5 - 0x50d2, saved)
        machine.cpu.mem_write(machine.A5 - 0x448e, bank)
        machine.call(4, 0x341a)
        machine.call(4, 0x3464)
        actual = bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62))
        expected_services = Counter({'frame': expected_events.count(('frame',))})
        if (actual != expected or machine.events != expected_events or machine.services != +expected_services
                or machine.level_bytes(len(level)) != level
                or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != saved
                or bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)) != bank):
            raise AssertionError(dict(gravity_inputs=(mode, vx, vy, y, facing, floating),
                                      native_actor=struct.unpack('>31h', actual),
                                      expected_actor=struct.unpack('>31h', expected),
                                      actual_events=machine.events, expected_events=expected_events))
        machine.verify_sequences()
        counts[f'mode{mode}'] += 1
        digest.update(actual + saved + bank + json.dumps(expected_events).encode('ascii'))
    return dict(cases=dict(counts), mismatches=0, outputs_sha256=digest.hexdigest(),
                scope='Direct native gravity4:341a and vertical movement4:3464, type0 only; '
                      'signed/float/cap/Y-threshold controls. LoadFrame is supplied, not frame geometry/collision.')


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    raw = {n: resources['SEQS'][n]['data'] for n in (2, 9, 47, 210)}
    sequences = {n: struct.unpack('>' + str(len(data) // 2) + 'h', data) for n, data in raw.items()}
    machine = NativeTempleWorldPrince(parse_resource_fork(executable), raw)
    counts, events, services, results, digest = Counter(), Counter(), Counter(), Counter(), hashlib.sha256()
    cache = struct.pack('>6h', 11, 13, 17, 19, 23, 29)
    mob = bytes((i * 7 + 13) % 256 for i in range(22))
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

    for number, original, room, cell in inventory:
        row, column = divmod(cell, 10)
        for (position, phase), (case, inputs), actor_room, layout in product(
                ((3, 1), (12, 1), (120, 4), (80, 2)), CASES.items(), (0, room), ('single', 'full20')):
            level = bytearray(original)
            struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, position)
            state = initial_state(level, bank_layouts(room, cell, phase)[layout])
            actor = bytearray(actor_fixture(actor_room, row + 1, column, -1, 2))
            for field, value in ((4, 207 + column * 51), (6, row * 120 + 110), (10, 91), (18, 3),
                                  (20, 0), (24, -1), (28, -1), (30, 3), (34, 0),
                                  (36, 3), (38, 9), (40, 9), (58, -1)):
                put_actor(actor, field, value)
            state.update(prince=bytes(actor), working=bytes((i * 7 + 19) % 256 for i in range(62)),
                         countdown=inputs.initial_countdown, saved_edges=(211, 223, 227, 229),
                         exit_flag=1234, view=room, result=-2)
            machine.reset(level)
            machine.inputs = inputs
            machine.cpu.mem_write(machine.A5 - 0x5056, state['working'])
            machine.cpu.mem_write(machine.A5 - 0x50d2, state['prince'])
            machine.cpu.mem_write(machine.A5 - 0x448e, state['trob_storage'])
            machine.put_word(-0x43e6, len(state['trobs']))
            machine.cpu.mem_write(machine.A5 - 0x43ee, struct.pack('>4h', *state['scratch']))
            machine.cpu.mem_write(machine.A5 - 0x4818, state['os'])
            machine.cpu.mem_write(machine.A5 - 0x34b0, cache)
            machine.cpu.mem_write(machine.A5 - 0x44a6, mob)
            for source, value in zip((-0x3560, -0x3562, -0x3568, -0x356a), EDGE_SOURCES):
                machine.put_word(source, value)
            for destination, value in zip(EDGE_DESTINATIONS, state['saved_edges']):
                machine.put_word(destination, value)
            for offset, value in ((-0x4fc2, room), (-0x5008, inputs.initial_countdown), (-0x4490, 17), (-0x439e, 192),
                                  (-0x4fee, inputs.live), (-0x4fac, inputs.suppress_animation),
                                  (-0x4f90, inputs.invulnerable), (-0x4fce, inputs.time_left),
                                  (-0x4faa, 1234), (-0x4fa6, inputs.floating), (-0x5200, inputs.special_actor)):
                machine.put_word(offset, value)
            for step in range(4):
                machine.events = []
                machine.services.clear()
                state = world_reference(state, sequences, inputs)
                returned = signed_word(machine.call(2, 0x6224))
                actual = dict(machine.snapshot(len(level)), result=returned)
                names = set(machine.ENDPOINTS.values())
                expected_services = Counter({'sound': 'gate_sound', 'redraw': 'gate_redraw',
                                             'audio': 'audio_request'}.get(event[0], event[0])
                                            for event in state['events'] if event[0] in names | {'sound', 'redraw', 'audio'})
                if (actual != state or machine.services != expected_services
                        or bytes(machine.cpu.mem_read(machine.A5 - 0x34b0, 12)) != cache
                        or bytes(machine.cpu.mem_read(machine.A5 - 0x44a6, 22)) != mob
                        or machine.word(-0x4490) != 17 or machine.word(-0x439e) != 192):
                    raise AssertionError(dict(anchor=(number, room, cell), inputs=(position, phase, case, actor_room, layout),
                                              step=step, differences={k: (actual[k], state[k]) for k in state if actual[k] != state[k]},
                                              actual_services=machine.services, expected_services=expected_services))
                machine.verify_sequences()
                counts[case] += 1
                events.update(event[0] for event in state['events'])
                services.update(machine.services)
                results[f'return{returned}'] += 1
                digest.update(state['level'] + state['prince'] + state['working'] + state['trob_storage'] + state['os'])
                digest.update(json.dumps([state['scratch'], state['saved_edges'], state['countdown'], returned,
                                          state['exit_flag'], state['events']]).encode('ascii'))
    direct_gravity = gravity_controls(machine, inventory[0][1])
    return dict(cases=dict(counts), traces=sum(counts.values()) // 4, mismatches=0,
                gravity_controls=direct_gravity,
                events=dict(events), services=dict(services), results=dict(results), outputs_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(), inputs={k: asdict(v) for k, v in CASES.items()},
                sequence_sha256={str(n): hashlib.sha256(data).hexdigest() for n, data in raw.items()},
                level_sha256={str(n): hashlib.sha256(resources['LEVL'][1999 + n]['data']).hexdigest()
                              for n in range(10, 14)},
                supplied_services={f'{segment}:{offset:04x}': name for (segment, offset), name in machine.ENDPOINTS.items()},
                other_supplied=['5:3828/0fe6/4d84 cue/redraw/audio requests', '17:330e and4:3098 prepared sequence handles',
                                'Memory Manager handle traps state0; PlayerCtrl return/mode controls are supplied'],
                scope='Actual2:6224 world and2:62e6 Prince callers, native temple gate bank/compaction, '
                      'LoadKid/AnimChar/gravity/vertical movement and actual2:6472 actor save. '
                      'Four persistent updates per supplied gate/actor/header/control fixture. '
                      'PlayerCtrl, geometry/collision/pressure/hazards, opponent work, clock/cut services '
                      'and OS/audio/drawing endpoints supplied; NOT complete FrameAdv, real input, physical '
                      'fall/contact/death, reachable placements, saves/reset or playable temple integration.')


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
