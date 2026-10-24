"""Connect mixed temple plate/gate lifetimes to real sliding-rock bank motion."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_actor_plate_lifetime import snapshot
from tools.probe_temple_gate_services import gate_actor_reference
from tools.probe_temple_mixed_lifetime import NativeMixedGateServices, mixed_lifetime_step
from tools.probe_temple_pressure_admission import PressureActor, actor_bytes
from tools.probe_temple_slide_rock_geometry import TempleCellReader
from tools.probe_temple_slide_rock_lifecycle import store_bank, update_bank_reference
from tools.probe_temple_slide_rock_update import NativeSlideRockUpdate, actor_word, make_prince


PLANS = {
    'close-full-motion': ('close',) + ('tick',) * 240,
    'close-open-close': ('close',) + ('tick',) * 8 + ('open',) + ('tick',) * 8
                        + ('close',) + ('tick',) * 224,
    'held-rejected-repress': ('close', 'tick') * 8 + ('reject', 'tick') * 6
                              + ('close', 'tick') + ('tick',) * 200,
    'permanent-open': ('permanent',) + ('tick',) * 160,
}


def mixed_rock_step(state, reader, operation, actor):
    if operation == 'rocks':
        if actor_word(state['prince'], 22) != 0 or actor_word(state['prince'], 10) != 0:
            raise ValueError('This first mixed-motion model supplies a room0/frame0 saved Prince')
        result = update_bank_reference(state, reader)
        if result['actor_inputs']:
            raise AssertionError('Actor reactions are outside this mixed-motion experiment')
        return result
    result = mixed_lifetime_step(state, reader, operation, actor)
    return dict(result, working=gate_actor_reference(state['working'], state['prince'], result['events']))


class NativeMixedRockMotion(NativeMixedGateServices):
    RANGES = {segment: NativeMixedGateServices.RANGES.get(segment, ()) + NativeSlideRockUpdate.RANGES.get(segment, ())
              for segment in NativeMixedGateServices.RANGES.keys() | NativeSlideRockUpdate.RANGES.keys()}
    SUPPLIED = NativeMixedGateServices.SUPPLIED | {(5, 0x5252): 'stop_sound', (5, 0x52c8): 'sound_query'}

    def clear_events(self):
        super().clear_events()
        self.phases, self.actor_inputs = [], []

    def dispatch(self, cpu, address, size, user):
        if address in (self.address(5, 0x3cee), self.address(6, 0x1a84), self.address(10, 0x1b04)):
            raise AssertionError('Unexpected actor-reaction endpoint in room0/frame0 trace')
        if address == self.address(10, 0x1656):
            self.events.append(('filled', self.word(-0x44a6)))
        elif address == self.address(4, 0x27ee):
            stack = cpu.reg_read(self.registers['a7'])
            caller = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            if caller in (self.address(10, 0x1e5c), self.address(10, 0x1edc)):
                self.events.append(('cell', *struct.unpack('>3h', cpu.mem_read(stack + 4, 6))))
        elif address in (self.address(10, 0x1d5c), self.address(10, 0x16f6)):
            mob = struct.unpack('>8h', cpu.mem_read(self.A5 - 0x44a6, 16))
            self.phases.append(('motion' if address == self.address(10, 0x1d5c) else 'crush', mob))
        elif address in (self.address(5, 0x5252), self.address(5, 0x52c8)):
            stack = cpu.reg_read(self.registers['a7'])
            cue = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            name = 'stop' if address == self.address(5, 0x5252) else 'query'
            if name == 'query' and cue != 193:
                raise AssertionError('Unexpected sound-state query')
            self.events.append((name, cue))
        super().dispatch(cpu, address, size, user)


def initial_state(level, position, bank, trobs):
    level = bytearray(level)
    struct.pack_into('>H', level, 0x780 + 2 * 120 + 2 * 4, position)
    for cell in (15, 16):
        offset = 0x780 + 2 * 120 + cell * 4
        foreground = struct.unpack_from('>H', level, offset)[0]
        struct.pack_into('>H', level, offset, foreground & ~0x2000)
        struct.pack_into('>h', level, 0x1680 + (foreground & 255) * 10 + 4, 0)
    storage = bytearray((i * 19 + 7) % 256 for i in range(160))
    for index, record in enumerate(trobs):
        struct.pack_into('>4h', storage, index * 8, *record)
    state = dict(mob=(11, 13, 17, 19, 23, 29, 31, 37), bank=bank,
                 bank_storage=store_bank(bytes((i * 37 + 11) % 256 for i in range(512)), bank),
                 trobs=trobs, trob_storage=bytes(storage), trob_scratch=(41, 43, 47, 53),
                 os=bytes((11, 13, 17, 19, 23, 29)), object_calls=[], rock_calls=[], events=[],
                 press_flag=4321, pressure_requests=[], relief_countdown=1234, pending=192,
                 prince=make_prince(room=0, row=0, frame=0), working=bytes(62), phases=[], actor_inputs=[])
    return state, TempleCellReader(level, 3)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    original = resources['LEVL'][2010]['data']
    if (struct.unpack_from('>3h', original, 0x2186)[::2] != (2, 11)
            or tuple(struct.unpack_from('>h', original, 2 * 60 + cell * 2)[0]
                     for cell in (2, 15, 16, 18)) != (4, 6, 5, 25)):
        raise ValueError('Expected the original level11 room3 gate/close/open/rock layout')
    machine = NativeMixedRockMotion(parse_resource_fork(executable))
    rock = (408, 236, 3, 0, 2, 6, 1, 408)
    banks = ((), (rock,), ((*rock[:4], -2, *rock[5:]),), ((*rock[:4], 100, *rock[5:]),),
             ((0, 116, 4, 0, 100, 6, 0, 0),) * 30,
             ((0, 116, 4, -1, 100, 6, 0, 0),) * 30)
    trob_banks = ((), ((9, 4, 1, 1),) * 20)
    counts, events, outcomes, digest = Counter(), Counter(), Counter(), hashlib.sha256()
    movement, snapshots = [], []
    for (plan_name, plan), position, bank, trobs, order in product(
            PLANS.items(), (0, 80), banks, trob_banks, ('animate-first', 'rocks-first')):
        state, reader = initial_state(original, position, bank, trobs)
        machine.reset(reader.level)
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *state['mob']))
        machine.cpu.mem_write(machine.BANK - 16, state['bank_storage'])
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
        machine.cpu.mem_write(machine.A5 - 0x448e, state['trob_storage'])
        machine.cpu.mem_write(machine.A5 - 0x43ee, struct.pack('>4h', *state['trob_scratch']))
        machine.cpu.mem_write(machine.A5 - 0x4818, state['os'])
        machine.cpu.mem_write(machine.A5 - 0x50d2, state['prince'])
        for offset, value in ((-0x43e6, len(trobs)), (-0x4490, len(bank)), (-0x4fc2, 3),
                              (-0x4fc4, 0), (-0x439e, 192), (-0x4f9e, 4321), (-0x5008, 1234), (-0x3570, 22)):
            machine.put_word(offset, value)
        actor = PressureActor(3, 5, 1, 236)
        trace = (plan_name, position, len(bank), bank[0][4] if bank else None,
                 bank[0][3] if bank else None, len(trobs), order)
        for cycle, token in enumerate(plan):
            operations = (('animate', 'rocks') if order == 'animate-first' else ('rocks', 'animate')) if token == 'tick' else ('check',)
            if token != 'tick':
                actor = PressureActor(3, 5 if token in ('close', 'reject') else 6, 1, 236,
                                      alive=0 if token == 'permanent' else -1,
                                      pose=185 if token == 'permanent' else 15,
                                      aux=0 if token == 'reject' else 0x40)
            for operation in operations:
                state = dict(state, working=actor_bytes(actor), events=[], object_calls=[], rock_calls=[],
                             pressure_requests=[], phases=[], actor_inputs=[])
                machine.cpu.mem_write(machine.A5 - 0x5056, state['working'])
                machine.put_word(-0x520a, actor.aux)
                machine.put_word(-0x4fa6, actor.floating)
                machine.operation = operation
                machine.clear_events()
                machine.pressure_requests = []
                machine.services.clear()
                reader.requests.clear()
                old_bank = state['bank']
                state = mixed_rock_step(state, reader, operation, actor)
                machine.call(5, {'check': 0x127e, 'animate': 0x0c38, 'rocks': 0x29e8}[operation])
                actual = dict(snapshot(machine), relief_countdown=machine.word(-0x5008),
                              pending=machine.word(-0x439e),
                              prince=bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)),
                              working=bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)),
                              phases=machine.phases, actor_inputs=machine.actor_inputs)
                service_names = {'sound': 'audio_request', 'redraw': 'plate_redraw', 'release_redraw': 'plate_redraw',
                                 'gate_sound': 'gate_sound', 'gate_redraw': 'gate_redraw',
                                 'stop': 'stop_sound', 'query': 'sound_query'}
                expected_services = Counter(service_names[event[0]] for event in state['events'] if event[0] in service_names)
                if (actual != state or machine.services != expected_services
                        or machine.level_bytes(len(reader.level)) != reader.level
                        or machine.reads != reader.requests or machine.cache() != reader.cache
                        or (operation == 'rocks' and machine.word(-0x4492) != len(old_bank))):
                    raise AssertionError(dict(trace=trace, cycle=cycle, token=token, operation=operation,
                                              differences={key: (actual[key], state[key]) for key in state if actual[key] != state[key]},
                                              cache=(machine.cache(), reader.cache), reads=(machine.reads, reader.requests),
                                              services=(machine.services, expected_services)))
                counts[operation] += 1
                events.update(event[0] for event in state['events'])
                if operation == 'rocks':
                    moved = any(before[1][0] != after[1][0] or before[1][2] != after[1][2]
                                for before, after in zip(state['phases'][::2], state['phases'][1::2]))
                    counts['moving_updates'] += moved
                    counts['removed_records'] += len(old_bank) - len(state['bank'])
                    if moved and len(movement) < 12:
                        movement.append(dict(trace=trace, cycle=cycle, before=old_bank, after=state['bank']))
                digest.update(bytes(reader.level) + state['bank_storage'] + state['trob_storage'] + state['os']
                              + state['prince'] + state['working'])
                digest.update(json.dumps([state['mob'], state['trob_scratch'], state['events'], state['phases'],
                                         state['pending'], state['relief_countdown'], state['press_flag'],
                                         state['pressure_requests'], machine.cache(), machine.reads]).encode('ascii'))
        counts['traces'] += 1
        outcomes[f'mobs_{len(state["bank"])}'] += 1
        outcomes[f'trobs_{len(state["trobs"])}'] += 1
        outcomes.update(f'control_{record[4]}' for record in state['bank'])
        if len(snapshots) < 12:
            snapshots.append(dict(trace=trace, bank=state['bank'], trobs=state['trobs']))
    if not counts['moving_updates'] or any(events.get(name, 0) for name in ('actor',)):
        raise AssertionError('Expected actual rock motion and no actor reactions')
    return dict(cases=dict(counts), events=dict(events), outcomes=dict(outcomes), movement=movement,
                snapshots=snapshots, mismatches=0, outputs_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                level_sha256=hashlib.sha256(original).hexdigest(),
                supplied_services=['5:4d84 audio request', '5:0f38 plate redraw', '5:3828 gate cue request',
                                   '5:0fe6 gate redraw', '5:5252 stop cue request', '5:52c8 cue193 returns0',
                                   '5:2710 loose-floor sink (not reached)', '7:36a0 trapdoor sink (not reached)'],
                scope='Connected original level11 mixed links, real actor pressure, plate/gate TROBs, '
                      'rock geometry/motion/crush admission and MOB/TROB compaction. Real LoadKid and relief. '
                      'Saved Prince room0/frame0 excludes reactions; working actor inputs resupplied per operation. '
                      'Both bank-update orders are supplied schedules, not FrameAdv. No actor damage, '
                      'presentation/pixels/audio playback, saves/reset or temple runtime integration.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps({key: value for key, value in report.items() if key not in ('movement', 'snapshots')}, indent=2))


if __name__ == '__main__':
    main()
