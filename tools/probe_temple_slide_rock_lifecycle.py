"""Connect native rock activation, bank updates and presentation with persistent state."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_slide_rock_geometry import TempleCellReader
from tools.probe_temple_slide_rock_motion import NativeSlideRockMotion
from tools.probe_temple_slide_rock_presentation import (
    NativeSlideRockPresentation, STORAGE_SIZE, VIEW_FIELDS, presentation_reference, view_for,
)
from tools.probe_temple_slide_rock_trigger import trigger_reference
from tools.probe_temple_slide_rock_update import NativeSlideRockUpdate, make_prince, update_reference


def store_bank(storage, bank):
    if len(storage) != 512 or len(bank) > 30 or any(len(mob) != 8 for mob in bank):
        raise ValueError('Expected guarded storage and at most thirty eight-word records')
    result = bytearray(storage)
    for index, mob in enumerate(bank):
        struct.pack_into('>8h', result, 16 + index * 16, *mob)
    return bytes(result)


def trigger_state_reference(state, reader, room, cell, how):
    result = dict(state, events=[], phases=[], actor_inputs=[])
    trigger = trigger_reference(room, cell, how, state['bank'])
    if trigger['scratch'] is not None:
        reader.read(room, cell % 10, cell // 10)
        result['mob'] = trigger['scratch']
    result['bank'] = trigger['bank']
    result['bank_storage'] = store_bank(state['bank_storage'], result['bank'])
    return result


def update_bank_reference(state, reader):
    if any(mob[5] != 6 for mob in state['bank']):
        raise ValueError('Connected lifecycle covers type-six banks only')
    result = dict(state, events=[], phases=[], actor_inputs=[])
    updated = []
    for mob in state['bank']:
        step = update_reference(mob, reader, result['prince'], result['working'], 22,
                                pending=result['pending'])
        for name in ('mob', 'prince', 'working', 'pending'):
            result[name] = step[name]
        for name in ('events', 'phases', 'actor_inputs'):
            result[name].extend(step[name])
        updated.append(step['mob'])
    # Native compaction overwrites survivor slots but preserves the old tail.
    result['bank'] = tuple(mob for mob in updated if mob[3] != -1)
    result['bank_storage'] = store_bank(store_bank(state['bank_storage'], updated), result['bank'])
    return result


def present_bank_reference(state, reader, view, visible, decorations, clip):
    if any(mob[5] != 6 for mob in state['bank']):
        raise ValueError('Connected lifecycle covers type-six banks only')
    result = dict(state, events=[], phases=[], actor_inputs=[])
    for mob in state['bank']:
        step = presentation_reference(mob, reader, view, visible, result['heights'],
                                      result['widths'], decorations, clip, result['objects'],
                                      count=result['count'], screen_cell=result['screen_cell'])
        for name in ('mob', 'heights', 'widths', 'count', 'screen_cell'):
            result[name] = step[name]
        result['objects'] = step['storage']
        result['events'].extend(step['events'])
    return result


class NativeSlideRockLifecycle(NativeSlideRockPresentation, NativeSlideRockMotion):
    # Presentation/geometry observes ReadCell once; motion supplies only its
    # audio/actor endpoints. Both instruction sets run in the same CPU/memory.
    RANGES = {segment: (NativeSlideRockPresentation.RANGES.get(segment, ())
                        + NativeSlideRockUpdate.RANGES.get(segment, ()))
              for segment in NativeSlideRockPresentation.RANGES.keys() | NativeSlideRockUpdate.RANGES.keys()}
    ENDPOINTS = NativeSlideRockUpdate.ENDPOINTS
    ACTOR_TAGS = NativeSlideRockUpdate.ACTOR_TAGS

    def reset(self, level):
        super().reset(level)
        self.phases = []

    def clear_events(self):
        self.events, self.phases, self.actor_inputs, self.reads = [], [], [], []

    def dispatch(self, cpu, address, size, user):
        if address == self.address(10, 0x1656):
            self.events.append(('filled', self.word(-0x44a6)))
        elif address == self.address(4, 0x27ee):
            stack = cpu.reg_read(self.registers['a7'])
            caller = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            if caller in (self.address(10, 0x1e5c), self.address(10, 0x1edc)):
                self.events.append(('cell', *struct.unpack('>3h', cpu.mem_read(stack + 4, 6))))
        elif address in (self.address(10, 0x1d5c), self.address(10, 0x16f6)):
            self.phases.append(('motion' if address == self.address(10, 0x1d5c) else 'crush', self.mob()))
        super().dispatch(cpu, address, size, user)

    def snapshot(self):
        count = self.word(-0x4490)
        if not 0 <= count <= 30:
            raise AssertionError('Native bank count exceeds the supplied budget')
        return dict(
            mob=self.mob(), bank=tuple(struct.unpack('>8h', self.cpu.mem_read(self.BANK + i * 16, 16))
                                       for i in range(count)),
            bank_storage=bytes(self.cpu.mem_read(self.BANK - 16, 512)),
            prince=bytes(self.cpu.mem_read(self.A5 - 0x50d2, 62)),
            working=bytes(self.cpu.mem_read(self.A5 - 0x5056, 62)), pending=self.word(-0x439e),
            heights=self.dimensions()[0], widths=self.dimensions()[1],
            objects=bytes(self.cpu.mem_read(self.OBJECTS - 16, STORAGE_SIZE)),
            count=self.word(-0x4826), screen_cell=self.word(-0x34c8),
            events=self.events, phases=self.phases, actor_inputs=self.actor_inputs,
        )


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince_fork = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeSlideRockLifecycle(parse_resource_fork(executable))
    canary = bytes((i * 29 + 3) % 256 for i in range(512))
    object_canary = bytes((i * 13 + 3) % 256 for i in range(STORAGE_SIZE))
    counts, event_counts, traces, level_hashes = Counter(), Counter(), [], {}
    digest = hashlib.sha256()
    clip = (0, 0, 365, 510)

    def configure(level, room, row, bank=()):
        machine.reset(level)
        state = dict(mob=(17, 19, 23, 29, 31, 37, 41, 43), bank=tuple(bank),
                     bank_storage=store_bank(canary, bank),
                     prince=make_prince(room=room % 32 + 1, row=row, x=-30000),
                     working=bytes((i * 17 + 7) % 256 for i in range(62)), pending=192,
                     heights=machine.default_heights, widths=machine.default_widths,
                     objects=object_canary, count=0, screen_cell=-1234,
                     events=[], phases=[], actor_inputs=[])
        machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *state['mob']))
        machine.cpu.mem_write(machine.A5 - 0x50d2, state['prince'])
        machine.cpu.mem_write(machine.A5 - 0x5056, state['working'])
        machine.cpu.mem_write(machine.BANK - 16, state['bank_storage'])
        machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
        machine.cpu.mem_write(machine.OBJECTS - 16, object_canary)
        machine.cpu.mem_write(machine.A5 - 0x4fec, struct.pack('>4h', *clip))
        machine.put_word(-0x4490, len(bank))
        machine.put_word(-0x439e, state['pending'])
        machine.put_word(-0x34c8, state['screen_cell'])
        machine.put_word(-0x3570, 22)
        return state, TempleCellReader(level, room)

    def set_view(reader, room, relation):
        view = view_for(room, relation)
        for key, value in view.items():
            machine.put_word(VIEW_FIELDS[key], value)
        reader.view_room = view['current']
        return view

    def begin(reader):
        machine.clear_events()
        reader.requests.clear()

    def check(level, reader, state, label, context):
        actual = machine.snapshot()
        if (actual != state or machine.reads != reader.requests or machine.cache() != reader.cache
                or machine.level_bytes(len(level)) != level or machine.services):
            different = [key for key in state if state[key] != actual[key]]
            raise AssertionError(dict(operation=label, context=context, different=different,
                                      actual={k: v for k, v in actual.items() if k in different and not isinstance(v, bytes)},
                                      expected={k: v for k, v in state.items() if k in different and not isinstance(v, bytes)},
                                      reads=machine.reads, expected_reads=reader.requests,
                                      cache=machine.cache(), expected_cache=reader.cache))
        counts[label] += 1
        event_counts.update(event[0] for event in actual['events'])
        event_counts.update(event[1] for event in actual['events'] if event[0] == 'actor')
        digest.update(actual['bank_storage'] + actual['objects'] + actual['prince'] + actual['working'])
        digest.update(json.dumps([actual['mob'], actual['bank'], actual['heights'], actual['widths'],
                                 actual['pending'], actual['count'], actual['screen_cell'],
                                 actual['events'], actual['phases'], machine.reads, machine.cache()]).encode('ascii'))

    def update(level, reader, state, context):
        begin(reader)
        original_count = len(state['bank'])
        state = update_bank_reference(state, reader)
        machine.call(5, 0x29e8)
        if machine.word(-0x4492) != original_count:
            raise AssertionError('Native update did not visit the original bank count')
        check(level, reader, state, 'updates', context)
        return state

    def present(level, reader, state, view, visible, context):
        begin(reader)
        machine.visible = visible
        state = present_bank_reference(state, reader, view, visible, machine.decorations, clip)
        machine.call(5, 0x307c)
        check(level, reader, state, 'presentations', context)
        return state

    for number in range(10, 14):
        level = prince_fork['LEVL'][1999 + number]['data']
        if (struct.unpack_from('>H', level, 0x2186)[0] != 2
                or struct.unpack_from('>H', level, 0x218a)[0] != number):
            raise ValueError('Unexpected original level header')
        level_hashes[str(number)] = hashlib.sha256(level).hexdigest()
        for room in range(1, 33):
            for cell in range(30):
                if struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0] != 25:
                    continue
                baseline = None
                for mode in ('none', 'visible', 'invisible', 'alternating', 'double'):
                    state, reader = configure(level, room, cell // 10)
                    physics, snapshots = [], []
                    for cycle in range(160):
                        context = (number, room, cell, mode, cycle)
                        relation = ('current', 'left', 'below', 'unrelated')[(cycle // 40) % 4]
                        view = set_view(reader, room, relation)
                        # This queue boundary is supplied explicitly. Persistent
                        # queue bytes, dimensions, cell cache and bank are retained.
                        state['count'] = 0
                        machine.put_word(-0x4826, 0)
                        if cycle in (0, 8, 64, 72):
                            how = 1 if cycle in (0, 64) else 2
                            begin(reader)
                            state = trigger_state_reference(state, reader, room, cell, how)
                            machine.call(10, 0x2152, (room, cell, how))
                            check(level, reader, state, 'triggers', context)
                        state = update(level, reader, state, context)
                        if mode != 'none':
                            visible = mode != 'invisible' and (mode != 'alternating' or cycle % 2 == 0)
                            visible = visible and relation != 'unrelated'
                            for repeat in range(2 if mode == 'double' else 1):
                                state = present(level, reader, state, view, visible, (*context, repeat))
                        physics.append((state['bank_storage'], state['bank'], state['prince'],
                                        state['working'], state['pending']))
                        if cycle in (0, 8, 39, 63, 64, 72, 79, 119, 159):
                            snapshots.append(dict(cycle=cycle, view=relation, bank=state['bank'],
                                                  objects=state['count'], heights=state['heights'][6:8]))
                    if baseline is None:
                        baseline = physics
                    elif physics != baseline:
                        raise AssertionError(('Drawing changed the persistent update trace', number, room, cell, mode))
                    else:
                        counts['draw_frequency_invariance'] += len(physics)
                    counts['traces'] += 1
                    traces.append(dict(level=number, room=room, cell=cell, mode=mode,
                                       final=state['bank'], snapshots=snapshots))

    # Multiple type-six records share dimensions, object queue and bank iteration.
    level = prince_fork['LEVL'][2009]['data']
    for count in (0, 1, 3, 6):
        bank = tuple((0 if i % 3 == 0 else 204, 236, 28, 0, -2, 6, 1, 459)
                     for i in range(count))
        state, reader = configure(level, 28, 1, bank)
        view = set_view(reader, 28, 'current')
        for cycle in range(8):
            state['count'] = 0
            machine.put_word(-0x4826, 0)
            state = update(level, reader, state, ('multiple', count, cycle))
            state = present(level, reader, state, view, True, ('multiple', count, cycle))
        counts['multi_record_traces'] += 1

    return dict(
        cases=dict(counts), event_counts=dict(event_counts), traces=traces, mismatches=0,
        outputs_sha256=digest.hexdigest(), level_hashes=level_hashes,
        executable_sha256=hashlib.sha256(executable).hexdigest(),
        supplied=[
            'Explicit trigger/update/presentation order, 160 cycles per original anchor/mode; not FrameAdv',
            'Object count reset once per cycle; allocated 128 queue slots with guarded raw bytes',
            'View relation, visibility, clipping rectangle and actor fixtures',
            'Audio requests recorded; cue193 false; no playback/queue side effects',
            'Actor reactions 5:3cee,6:1a84,10:1b04 use documented marker endpoints',
            'Presentation visibility/redraw sink, SectRect callback and OffsetRect trap',
        ],
        scope=('Original TriggerSlideRock, MakeRubble/type6 motion/geometry/crush admission, '
               'ATMLoose/ATMSlideRock and native object appends in persistent CPU memory. '
               'Full levels, actors, bank/raw tail, object queue/padding, dimensions, cell cache '
               'and ordered endpoints checked after each operation. Compare identical update '
               'traces with absent, visible, invisible, alternating or repeated presentation. '
               'No full actor reaction/death, real visibility, raster pixels, FrameAdv cadence, '
               'save/checkpoint/restart, arbitrary mixed-type banks or campaign claim.'),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps({key: value for key, value in report.items() if key != 'traces'}, indent=2))


if __name__ == '__main__':
    main()
