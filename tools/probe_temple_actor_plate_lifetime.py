"""Connect native actor pressure admission to real plate/rock activation and release."""

import argparse
from collections import Counter
from dataclasses import replace
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_fresh_plate_setup import plate_reference, source_fixtures
from tools.probe_temple_plate_lifetime import NativePlateLifetime, lifetime_step
from tools.probe_temple_pressure_admission import PressureActor, actor_bytes, admission_reference
from tools.probe_temple_slide_rock_admission import link_chain
from tools.probe_temple_slide_rock_geometry import TempleCellReader
from tools.probe_temple_slide_rock_lifecycle import store_bank


PLANS = {
    'tap-release-repress': ('ordinary',) + ('animate',) * 5 + ('ordinary',) + ('animate',) * 5,
    'held-then-rejected': ('ordinary', 'animate') * 6 + ('aux-off', 'animate') * 5 + ('ordinary',),
    'rejected-then-return': ('ordinary', 'kind10', 'floating', 'mode2', 'below-y', 'selected29')
                            + ('animate',) * 5 + ('ordinary',),
    'above-source': ('above', 'animate') * 3 + ('animate',) * 5,
    'permanent-then-living': ('permanent',) + ('animate',) * 6 + ('ordinary',) + ('animate',) * 6,
    'type4-nonnegative-alive': ('type4',) + ('animate',) * 5 + ('ordinary',),
}


def actor_variant(actor, name):
    if name == 'ordinary':
        return actor
    changes = {
        'aux-off': dict(aux=0), 'kind10': dict(kind=10), 'floating': dict(floating=1),
        'mode2': dict(mode=2), 'below-y': dict(y=actor.row * 120 + 94),
        'selected29': dict(kind=1, selected=29),
        'above': dict(row=actor.row + 1, y=(actor.row + 1) * 120 + 95, pose=87, mode=2, aux=0),
        'permanent': dict(alive=0, pose=185), 'type4': dict(kind=4, alive=0),
    }
    if name not in changes:
        raise ValueError('Unknown supplied actor variant')
    return replace(actor, **changes[name])


def actor_plate_step(state, reader, operation, actor):
    state = dict(state, pressure_requests=[])
    context = (actor.pose, actor.alive, actor.room, 0)
    if operation == 'animate':
        return lifetime_step(state, reader, operation, context, actor.room, actor.row * 10 + actor.column)
    if operation != 'check':
        raise ValueError('Expected a supplied check or animation operation')
    requests, flag = admission_reference(actor, reader, state['press_flag'])
    state = dict(state, press_flag=flag)
    for name, arguments in requests:
        state['pressure_requests'].append((name, arguments))
        if name == 'permanent':
            # Original 5:252e writes timer31, then calls PushPlate(kind,index).
            kind, foreground = reader.cache[:2]
            index = foreground & 255
            level = bytearray(reader.level)
            struct.pack_into('>h', level, 0x1680 + index * 10 + 4, 31)
            reader.level = level
            state['pressure_requests'].append(('push', (kind, index)))
        if name in ('push', 'permanent'):
            state = plate_reference(state, reader, context)
        elif name not in ('loose', 'trapdoor'):
            raise ValueError('Unexpected pressure endpoint')
    return state


class NativeActorPlateLifetime(NativePlateLifetime):
    RANGES = NativePlateLifetime.RANGES | {
        4: NativePlateLifetime.RANGES[4] + ((0x35a6, 0x35b8), (0x3ff8, 0x400e)),
        5: NativePlateLifetime.RANGES[5] + ((0x127e, 0x13dc), (0x252e, 0x2552)),
    }
    SUPPLIED = NativePlateLifetime.SUPPLIED | {(5, 0x2710): 'loose', (7, 0x36a0): 'trapdoor'}

    def reset(self, level):
        super().reset(level)
        self.pressure_requests = []

    def dispatch(self, cpu, address, size, user):
        for segment, offset, count, name in ((5, 0x240c, 2, 'push'), (5, 0x252e, 0, 'permanent'),
                                             (5, 0x2710, 1, 'loose'), (7, 0x36a0, 0, 'trapdoor')):
            if address == self.address(segment, offset):
                stack = cpu.reg_read(self.registers['a7'])
                args = struct.unpack(f'>{count}h', cpu.mem_read(stack + 4, count * 2)) if count else ()
                self.pressure_requests.append((name, args))
        super().dispatch(cpu, address, size, user)


def snapshot(machine):
    mobs, trobs = machine.word(-0x4490), machine.word(-0x43e6)
    if not 0 <= mobs <= 30 or not 0 <= trobs <= 20:
        raise AssertionError(('Invalid bank count', mobs, trobs))
    return dict(mob=struct.unpack('>8h', machine.cpu.mem_read(machine.A5 - 0x44a6, 16)),
                bank=tuple(struct.unpack('>8h', machine.cpu.mem_read(machine.BANK + i * 16, 16))
                           for i in range(mobs)),
                bank_storage=bytes(machine.cpu.mem_read(machine.BANK - 16, 512)),
                trobs=tuple(struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x448e + i * 8, 8))
                            for i in range(trobs)),
                trob_storage=bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)),
                trob_scratch=struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x43ee, 8)),
                os=bytes(machine.cpu.mem_read(machine.A5 - 0x4818, 6)),
                object_calls=machine.object_calls, rock_calls=machine.rock_calls,
                events=machine.events, press_flag=machine.word(-0x4f9e),
                pressure_requests=machine.pressure_requests)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    fixtures, excluded = source_fixtures(resources)
    fixtures = [f for f in fixtures if f[0].startswith('original') and all(
        target[3] == 25 for target in link_chain(f[1], struct.unpack_from(
            '>H', f[1], 0x780 + (f[2] - 1) * 120 + f[3] * 4)[0] & 255))]
    if len(fixtures) != 5:
        raise ValueError('Expected the five admitted original rock-only source plates')
    machine = NativeActorPlateLifetime(parse_resource_fork(executable))
    counts, services, outcomes, digest = Counter(), Counter(), Counter(), hashlib.sha256()
    saved_actor = bytes((i * 7 + 17) % 256 for i in range(62))
    for label, original, room, cell in fixtures:
        source_offset = 0x780 + (room - 1) * 120 + cell * 4
        foreground = struct.unpack_from('>H', original, source_offset)[0]
        index = foreground & 255
        target_room, target_cell = link_chain(original, index)[0][1:3]
        target_row, target_col = divmod(target_cell, 10)
        rock = (target_col * 51, 116 + target_row * 120, target_room, 0, 2, 6, target_row, target_col * 51)
        filler = (9, room % 32 + 1, 1, 1)
        banks = ((), (rock,), ((0, 116, target_room % 32 + 1, 0, 2, 6, 0, 0),) * 30)
        for (plan_name, plan), timer, bank, trobs in product(
                PLANS.items(), (0, 31), banks, ((), (filler,) * 19, (filler,) * 20)):
            level = bytearray(original)
            struct.pack_into('>h', level, 0x1680 + index * 10 + 4, timer)
            struct.pack_into('>H', level, source_offset, foreground & ~0x2000)
            machine.reset(level)
            machine.operation = 'check'
            storage = bytearray((i * 19 + 7) % 256 for i in range(160))
            for i, record in enumerate(trobs):
                struct.pack_into('>4h', storage, i * 8, *record)
            state = dict(mob=(11, 13, 17, 19, 23, 29, 31, 37), bank=bank,
                         bank_storage=store_bank(bytes((i * 37 + 11) % 256 for i in range(512)), bank),
                         trobs=trobs, trob_storage=bytes(storage), trob_scratch=(41, 43, 47, 53),
                         os=bytes((11, 13, 17, 19, 23, 29)), object_calls=[], rock_calls=[],
                         events=[], press_flag=4321, pressure_requests=[])
            machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *state['mob']))
            machine.cpu.mem_write(machine.BANK - 16, state['bank_storage'])
            machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
            machine.put_word(-0x4490, len(bank))
            machine.cpu.mem_write(machine.A5 - 0x448e, state['trob_storage'])
            machine.cpu.mem_write(machine.A5 - 0x43ee, struct.pack('>4h', *state['trob_scratch']))
            machine.cpu.mem_write(machine.A5 - 0x4818, state['os'])
            machine.put_word(-0x43e6, len(trobs))
            machine.put_word(-0x4fc2, room)
            machine.put_word(-0x4fc4, 0)
            machine.put_word(-0x439e, 1234)
            machine.put_word(-0x4f9e, 4321)
            machine.cpu.mem_write(machine.A5 - 0x50d2, saved_actor)
            reader = TempleCellReader(level, room)
            base_actor = PressureActor(room, cell % 10, cell // 10, (cell // 10) * 120 + 116)
            actor = base_actor
            for step, token in enumerate(plan):
                operation = 'animate' if token == 'animate' else 'check'
                if operation == 'check':
                    actor = actor_variant(base_actor, token)
                current = actor_bytes(actor)
                machine.cpu.mem_write(machine.A5 - 0x5056, current)
                machine.put_word(-0x520a, actor.aux)
                machine.put_word(-0x4fa6, actor.floating)
                machine.operation = operation
                machine.clear_events()
                machine.services.clear()
                machine.pressure_requests = []
                reader.requests.clear()
                state = dict(state, events=[], object_calls=[], rock_calls=[])
                state = actor_plate_step(state, reader, operation, actor)
                machine.call(5, 0x0c38 if operation == 'animate' else 0x127e)
                actual = snapshot(machine)
                expected_services = Counter('audio_request' if event[0] == 'sound' else 'plate_redraw'
                                            for event in state['events']
                                            if event[0] in ('sound', 'redraw', 'release_redraw'))
                expected_services.update(name for name, _ in state['pressure_requests']
                                         if name in ('loose', 'trapdoor'))
                if (actual != state or machine.services != expected_services
                        or machine.level_bytes(len(reader.level)) != reader.level
                        or machine.reads != reader.requests or machine.cache() != reader.cache
                        or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != current
                        or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != saved_actor
                        or machine.word(-0x439e) != 1234):
                    raise AssertionError(dict(source=label, plan=plan_name, step=step, token=token,
                                              differences={k: (actual[k], state[k]) for k in state if actual[k] != state[k]},
                                              cache=(machine.cache(), reader.cache), reads=(machine.reads, reader.requests),
                                              services=(machine.services, expected_services)))
                counts[operation] += 1
                outcomes.update(name for name, _ in state['pressure_requests'])
                outcomes['no_pressure_request'] += operation == 'check' and not state['pressure_requests']
                services.update(machine.services)
                digest.update(bytes(reader.level) + state['bank_storage'] + state['trob_storage'] + state['os'])
                digest.update(json.dumps([state['events'], state['pressure_requests'], state['press_flag'],
                                         state['mob'], state['trob_scratch'], machine.cache(), machine.reads]).encode('ascii'))
            counts['traces'] += 1
    return dict(cases=dict(counts), outcomes=dict(outcomes), mismatches=0, services=dict(services),
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
                source_labels=[entry[0] for entry in fixtures], excluded_raw_sources=excluded,
                level_sha256={str(n): hashlib.sha256(resources['LEVL'][1999 + n]['data']).hexdigest()
                              for n in range(10, 14)},
                plans={name: list(plan) for name, plan in PLANS.items()},
                supplied_services=['5:4d84 audio request sink', '5:0f38 redraw request sink',
                                   '5:2710 loose-floor request sink', '7:36a0 trapdoor request sink'],
                scope='Native CheckPress -> ordinary/permanent PushPlate -> rock-only links and plate release '
                      'over persistent banks/cache/level state. Supporting cell, actor/FRAM inputs and call '
                      'schedule supplied. No full FrameAdv, gate animation, rock motion, pixels/audio, saves '
                      'or temple gameplay integration.')


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
