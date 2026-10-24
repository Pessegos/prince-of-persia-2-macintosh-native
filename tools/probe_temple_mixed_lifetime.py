"""Connect actor pressure, both original mixed links and gate/plate TROB lifetimes."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_actor_plate_lifetime import NativeActorPlateLifetime, actor_plate_step, snapshot
from tools.probe_temple_gate_animation import NativeGateAnimation, gate_animation_reference
from tools.probe_temple_plate_release import animate_record
from tools.probe_temple_pressure_admission import PressureActor, actor_bytes
from tools.probe_temple_slide_rock_geometry import TempleCellReader
from tools.probe_temple_slide_rock_lifecycle import store_bank


PLANS = {
    'open-full-lifetime': ('open',) + ('animate',) * 160,
    'open-then-fast-close': ('open',) + ('animate',) * 12 + ('close',) + ('animate',) * 8,
    'held-rejected-release': ('open', 'animate') * 12 + ('reject', 'animate') * 6 + ('animate',) * 150,
    'permanent-open': ('permanent',) + ('animate',) * 80,
    'close-then-open': ('close',) + ('animate',) * 4 + ('open',) + ('animate',) * 160,
}


def mixed_animation_step(state, reader):
    storage, updated = bytearray(state['trob_storage']), []
    state = dict(state, pressure_requests=[])
    for index, record in enumerate(state['trobs']):
        cell, room, phase, kind = record
        if kind == 4:
            offset = 0x780 + (room - 1) * 120 + cell * 4
            foreground, tail = struct.unpack_from('>2H', reader.level, offset)
            raw_kind = struct.unpack_from('>H', reader.level, (room - 1) * 60 + cell * 2)[0]
            gate = gate_animation_reference(foreground, phase, relief_countdown=state['relief_countdown'])
            level = bytearray(reader.level)
            struct.pack_into('>H', level, offset, gate['foreground'])
            reader.level = bytes(level)
            events = [('visit', index, *record)]
            events.extend(('gate_' + event[0], *event[1:]) if event[0] in ('sound', 'redraw') else event
                          for event in gate['events'])
            state = dict(state, trob_scratch=(cell, room, gate['phase'], kind), relief_countdown=gate['relief_countdown'],
                         os=struct.pack('>3H', gate['foreground'], tail, raw_kind), events=state['events'] + events)
        else:
            plate = animate_record(reader.level, record, index)
            reader.level = plate['level']
            events = [('release_redraw', *event[1:]) if event[0] == 'redraw' else event for event in plate['events']]
            state = dict(state, trob_scratch=plate['scratch'], os=plate['os'], events=state['events'] + events)
        updated.append(state['trob_scratch'])
        struct.pack_into('>h', storage, index * 8 + 4, state['trob_scratch'][2])
    surviving = tuple(record for record in updated if record[2] >= 0)
    if len(surviving) != len(updated):
        for index, record in enumerate(surviving):
            struct.pack_into('>4h', storage, index * 8, *record)
    return dict(state, trobs=surviving, trob_storage=bytes(storage))


def mixed_lifetime_step(state, reader, operation, actor):
    if actor.kind != 0 or actor.mode != 0:
        raise ValueError('This mixed trace supplies only non-hanging type0 actors')
    if operation == 'animate':
        return mixed_animation_step(state, reader)
    return actor_plate_step(state, reader, operation, actor)


class NativeMixedLifetime(NativeActorPlateLifetime):
    RANGES = {segment: NativeActorPlateLifetime.RANGES.get(segment, ()) + NativeGateAnimation.RANGES.get(segment, ())
              for segment in NativeActorPlateLifetime.RANGES.keys() | NativeGateAnimation.RANGES.keys()}
    SUPPLIED = NativeActorPlateLifetime.SUPPLIED | NativeGateAnimation.SUPPLIED

    def dispatch(self, cpu, address, size, user):
        if address == self.address(5, 0x3828):
            stack = cpu.reg_read(self.registers['a7'])
            self.events.append(('gate_sound', struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]))
        elif address == self.address(5, 0x0fe6):
            self.events.append(('gate_redraw', self.word(-0x4818) & 65535, self.word(-0x43ea)))
        elif address == self.address(4, 0x4b02):
            self.events.append(('load_kid',))
        elif address == self.address(5, 0x4766):
            self.events.append(('relief_check',))
        super().dispatch(cpu, address, size, user)
        # The supplied level4 relief predicate returns0; this is not a
        # collision/death predicate or evidence of crushing consequences.


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    original = resources['LEVL'][2010]['data']
    machine = NativeMixedLifetime(parse_resource_fork(executable))
    if struct.unpack_from('>3h', original, 0x2186)[::2] != (2, 11):
        raise ValueError('Expected original temple level11')
    if tuple(struct.unpack_from('>h', original, 2 * 60 + cell * 2)[0] for cell in (2, 15, 16, 18)) != (4, 6, 5, 25):
        raise ValueError('Unexpected mixed gate/close/open/rock cell layout')
    filler = (9, 4, 1, 1)
    banks = ((), ((0, 116, 4, 0, 2, 6, 0, 0),) * 30)
    trobs = ((), ((2, 3, 2, 4),), (filler,) * 19, (filler,) * 20)
    saved = bytearray((i * 7 + 17) % 256 for i in range(62))
    struct.pack_into('>h', saved, 22, 0)
    counts, outcomes, services, digest = Counter(), Counter(), Counter(), hashlib.sha256()
    for (plan_name, plan), position, bank, initial_trobs in product(PLANS.items(), (0, 80, 255), banks, trobs):
        level = bytearray(original)
        struct.pack_into('>H', level, 0x780 + 2 * 120 + 2 * 4, position)
        for cell in (15, 16):
            foreground = struct.unpack_from('>H', level, 0x780 + 2 * 120 + cell * 4)[0]
            struct.pack_into('>H', level, 0x780 + 2 * 120 + cell * 4, foreground & ~0x2000)
            struct.pack_into('>h', level, 0x1680 + (foreground & 255) * 10 + 4, 0)
        machine.reset(level)
        machine.operation = 'check'
        storage = bytearray((i * 19 + 7) % 256 for i in range(160))
        for i, record in enumerate(initial_trobs):
            struct.pack_into('>4h', storage, i * 8, *record)
        state = dict(mob=(11, 13, 17, 19, 23, 29, 31, 37), bank=bank,
                     bank_storage=store_bank(bytes((i * 37 + 11) % 256 for i in range(512)), bank),
                     trobs=initial_trobs, trob_storage=bytes(storage), trob_scratch=(41, 43, 47, 53),
                     os=bytes((11, 13, 17, 19, 23, 29)), object_calls=[], rock_calls=[], events=[],
                     press_flag=4321, pressure_requests=[], relief_countdown=1234)
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *state['mob']))
        machine.cpu.mem_write(machine.BANK - 16, state['bank_storage'])
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
        machine.put_word(-0x4490, len(bank))
        machine.cpu.mem_write(machine.A5 - 0x448e, state['trob_storage'])
        machine.cpu.mem_write(machine.A5 - 0x43ee, struct.pack('>4h', *state['trob_scratch']))
        machine.cpu.mem_write(machine.A5 - 0x4818, state['os'])
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(saved))
        for offset, value in ((-0x43e6, len(initial_trobs)), (-0x4fc2, 3), (-0x4fc4, 0),
                              (-0x439e, 1234), (-0x4f9e, 4321), (-0x5008, 1234)):
            machine.put_word(offset, value)
        reader = TempleCellReader(level, 3)
        actor = PressureActor(3, 6, 1, 236)
        for step, token in enumerate(plan):
            operation = 'animate' if token == 'animate' else 'check'
            if operation == 'check':
                if token not in ('open', 'close', 'reject', 'permanent'):
                    raise ValueError('Unknown mixed plan token')
                actor = PressureActor(3, 5 if token == 'close' else 6, 1, 236,
                                      alive=0 if token == 'permanent' else -1,
                                      pose=185 if token == 'permanent' else 15,
                                      aux=0 if token == 'reject' else 0x40)
            current = actor_bytes(actor)
            machine.cpu.mem_write(machine.A5 - 0x5056, current)
            machine.put_word(-0x520a, actor.aux)
            machine.put_word(-0x4fa6, actor.floating)
            machine.operation = operation
            machine.clear_events()
            machine.pressure_requests = []
            machine.services.clear()
            reader.requests.clear()
            state = mixed_lifetime_step(dict(state, events=[], object_calls=[], rock_calls=[]), reader, operation, actor)
            machine.call(5, 0x0c38 if operation == 'animate' else 0x127e)
            actual = dict(snapshot(machine), relief_countdown=machine.word(-0x5008))
            service_names = {'sound': 'audio_request', 'redraw': 'plate_redraw', 'release_redraw': 'plate_redraw',
                             'gate_sound': 'gate_sound', 'gate_redraw': 'gate_redraw',
                             'load_kid': 'load_kid', 'relief_check': 'relief_check'}
            expected_services = Counter(service_names[event[0]] for event in state['events'] if event[0] in service_names)
            if (actual != state or machine.services != expected_services
                    or machine.level_bytes(len(reader.level)) != reader.level
                    or machine.reads != reader.requests or machine.cache() != reader.cache
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != current
                    or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != saved
                    or machine.word(-0x439e) != 1234):
                raise AssertionError(dict(plan=plan_name, initial=(position, len(bank), len(initial_trobs)),
                                          step=step, token=token,
                                          differences={k: (actual[k], state[k]) for k in state if actual[k] != state[k]},
                                          cache=(machine.cache(), reader.cache), services=(machine.services, expected_services)))
            counts[operation] += 1
            services.update(machine.services)
            digest.update(bytes(reader.level) + state['bank_storage'] + state['trob_storage'] + state['os'])
            digest.update(json.dumps([state['events'], state['pressure_requests'], state['press_flag'], state['mob'],
                                     state['trob_scratch'], machine.cache(), machine.reads]).encode('ascii'))
        counts['traces'] += 1
        gate_position = struct.unpack_from('>H', reader.level, 0x780 + 2 * 120 + 2 * 4)[0] & 255
        outcomes[f'gate_position_{gate_position}'] += 1
        outcomes[f'trobs_{len(state["trobs"])}'] += 1
    return dict(cases=dict(counts), outcomes=dict(outcomes), services=dict(services), mismatches=0,
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
                level_sha256=hashlib.sha256(original).hexdigest(), plans={k: list(v) for k, v in PLANS.items()},
                supplied_services=['5:4d84 audio request', '5:0f38 plate redraw request', '5:3828 gate sound request',
                                   '5:0fe6 gate redraw request', '4:4b02 LoadKid no-op', '5:4766 level4 relief returns0',
                                   '5:2710 loose-floor sink (not expected)', '7:36a0 trapdoor sink (not expected)'],
                scope='Connected original level11 room3 open/close mixed plate links, actor admission, source/target '
                      'TROBs, gate motion and stable compaction with persistent level/MOB/TROB/cache state. '
                      'Non-hanging actor/FRAM/support inputs and check/animation schedule supplied. No rock motion, '
                      'real contact/crush, sound/pixels, full FrameAdv, saves or temple gameplay integration.')


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
