"""Connect native temple gate bank iteration/compaction to bounded actor clip updates."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_gate_actor_clip import NativeGateActorClip, clip_reference, put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_hanging_animation import hanging_animation_reference
from tools.probe_temple_plate_release import initial_state
from tools.probe_temple_slide_rock_update import actor_word


def bank_reference(state):
    """Native AnimTrobs order and stable compaction, for gate/default records only."""
    if len(state['trobs']) > 20:
        raise ValueError('Native TROB capacity is20')
    result = dict(state, events=[])
    level, storage, updated = bytearray(state['level']), bytearray(state['trob_storage']), []
    for index, (cell, room, phase, kind) in enumerate(state['trobs']):
        if not 1 <= room <= 32 or not 0 <= cell < 30 or kind not in (1, 4):
            raise ValueError('Only in-range gate/default bank records are covered')
        offset = 0x780 + (room - 1) * 120 + cell * 4
        foreground, tail = struct.unpack_from('>2H', level, offset)
        raw_kind = struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0]
        result['events'].append(('visit', index, cell, room, phase, kind))
        if kind == 4:
            gate = hanging_animation_reference(foreground, phase, result['prince'], result['working'], room, cell)
            foreground, phase = gate['foreground'], gate['phase']
            struct.pack_into('>H', level, offset, foreground)
            result.update(prince=gate['prince'], working=gate['working'])
            result['events'].extend(gate['events'])
        else:
            phase = -1
        result['os'] = struct.pack('>3H', foreground, tail, raw_kind)
        result['scratch'] = (cell, room, phase, kind)
        updated.append(result['scratch'])
        struct.pack_into('>h', storage, index * 8 + 4, phase)
    survivors = tuple(record for record in updated if record[2] >= 0)
    if len(survivors) != len(updated):
        for index, record in enumerate(survivors):
            struct.pack_into('>4h', storage, index * 8, *record)
    return dict(result, level=bytes(level), trobs=survivors, trob_storage=bytes(storage))


def bank_layouts(room, cell, phase):
    gate, filler = (cell, room, phase, 4), (cell, room, 1, 1)
    return {'single': (gate,), 'erase-before': (filler, gate), 'erase-after': (gate, filler),
            'full20': (filler,) * 9 + (gate,) + (filler,) * 10,
            'duplicate-gate': (gate, gate), 'slow-and-fast': ((cell, room, 1, 4), (cell, room, 4, 4))}


class NativeGateActorBank(NativeGateActorClip):
    def dispatch(self, cpu, address, size, user):
        if address == self.address(5, 0x0cd6):
            stack = cpu.reg_read(self.registers['a7'])
            index = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            record = struct.unpack('>4h', cpu.mem_read(self.A5 - 0x43ee, 8))
            self.events.append(('visit', index, *record))
        super().dispatch(cpu, address, size, user)

    def snapshot(self, size):
        count = self.word(-0x43e6)
        if not 0 <= count <= 20:
            raise AssertionError('Invalid native TROB count')
        return dict(level=self.level_bytes(size),
                    trobs=tuple(struct.unpack('>4h', self.cpu.mem_read(self.A5 - 0x448e + i * 8, 8))
                                for i in range(count)),
                    trob_storage=bytes(self.cpu.mem_read(self.A5 - 0x448e, 160)),
                    scratch=struct.unpack('>4h', self.cpu.mem_read(self.A5 - 0x43ee, 8)),
                    os=bytes(self.cpu.mem_read(self.A5 - 0x4818, 6)), events=list(self.events),
                    prince=bytes(self.cpu.mem_read(self.A5 - 0x50d2, 62)),
                    working=bytes(self.cpu.mem_read(self.A5 - 0x5056, 62)))


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    raw = {n: resources['SEQS'][n]['data'] for n in (2, 9, 47, 210)}
    sequences = {n: struct.unpack('>' + str(len(data) // 2) + 'h', data) for n, data in raw.items()}
    machine = NativeGateActorBank(parse_resource_fork(executable), raw)
    counts, visits, services, outcomes, digest = Counter(), Counter(), Counter(), Counter(), hashlib.sha256()
    cache = struct.pack('>6h', 11, 13, 17, 19, 23, 29)
    mob = bytes((i * 7 + 13) % 256 for i in range(22))
    inventory = []
    for number in range(10, 14):
        level = resources['LEVL'][1999 + number]['data']
        if struct.unpack_from('>3h', level, 0x2186)[::2] != (2, number):
            raise ValueError('Expected original temple headers')
        for room in range(1, struct.unpack_from('>h', level, 0x2180)[0] + 1):
            for cell in range(30):
                if struct.unpack_from('>h', level, (room - 1) * 60 + cell * 2)[0] == 4:
                    inventory.append((number, level, room, cell))
    if len(inventory) != 41:
        raise ValueError('Expected all41 original temple gates')

    for number, original, room, cell in inventory:
        row, column = divmod(cell, 10)
        for (position, phase), layout, order in product(
                ((3, 1), (12, 1), (120, 4), (180, 3), (80, 2)),
                tuple(bank_layouts(room, cell, 1)), ('actor-first', 'bank-first')):
            level = bytearray(original)
            struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, position)
            state = initial_state(level, bank_layouts(room, cell, phase)[layout])
            actor = bytearray(actor_fixture(room, row + 1, column, -1, 2))
            for field, value in ((4, 207 + column * 51), (6, row * 120 + 110), (10, 91),
                                  (28, -1), (30, 3), (34, 0), (36, 3), (38, 9), (40, 9)):
                put_actor(actor, field, value)
            state.update(prince=bytes(actor), working=bytes((i * 7 + 19) % 256 for i in range(62)))
            machine.reset(level)
            machine.cpu.mem_write(machine.A5 - 0x5056, state['working'])
            machine.cpu.mem_write(machine.A5 - 0x50d2, state['prince'])
            machine.cpu.mem_write(machine.A5 - 0x448e, state['trob_storage'])
            machine.put_word(-0x43e6, len(state['trobs']))
            machine.cpu.mem_write(machine.A5 - 0x43ee, struct.pack('>4h', *state['scratch']))
            machine.cpu.mem_write(machine.A5 - 0x4818, state['os'])
            machine.cpu.mem_write(machine.A5 - 0x34b0, cache)
            machine.cpu.mem_write(machine.A5 - 0x44a6, mob)
            for offset, value in ((-0x4fc2, room), (-0x5008, 4321), (-0x4490, 17), (-0x439e, 192)):
                machine.put_word(offset, value)

            def compare(label, step):
                actual = machine.snapshot(len(state['level']))
                expected_services = Counter({'sound': 'gate_sound', 'redraw': 'gate_redraw',
                                             'audio': 'audio_request'}[event[0]]
                                            for event in state['events'] if event[0] in ('sound', 'redraw', 'audio'))
                if (actual != state or machine.services != expected_services
                        or bytes(machine.cpu.mem_read(machine.A5 - 0x34b0, 12)) != cache
                        or bytes(machine.cpu.mem_read(machine.A5 - 0x44a6, 22)) != mob
                        or machine.word(-0x5008) != 4321 or machine.word(-0x4490) != 17
                        or machine.word(-0x439e) != 192):
                    raise AssertionError(dict(anchor=(number, room, cell), inputs=(position, phase, layout, order),
                                              operation=(label, step),
                                              differences={k: (actual[k], state[k]) for k in state if actual[k] != state[k]},
                                              actual_services=machine.services, expected_services=expected_services))
                machine.verify_sequences()
                counts[label] += 1
                visits.update(event[0] for event in state['events'])
                services.update(machine.services)
                digest.update(state['level'] + state['prince'] + state['working'] + state['trob_storage'] + state['os'])
                digest.update(json.dumps([state['trobs'], state['scratch'], state['events']]).encode('ascii'))

            for step in range(8):
                operations = ('load', 'clip', 'copy', 'bank') if order == 'actor-first' else ('bank', 'load', 'clip', 'copy')
                for operation in operations:
                    machine.events = []
                    machine.services.clear()
                    state = dict(state, events=[])
                    if operation == 'bank':
                        state = bank_reference(state)
                        machine.call(5, 0x0c38)
                    elif operation == 'load':
                        state.update(working=state['prince'], events=[('load_kid',)])
                        machine.call(4, 0x4b02)
                    elif operation == 'clip':
                        animated = clip_reference(state['working'], sequences)
                        state.update(working=animated['actor'], events=animated['events'])
                        machine.call(4, 0x2c0c)
                    else:
                        state.update(prince=state['working'], events=[('save_kid',)])
                        machine.call(5, 0x1516, stop=(5, 0x1528))
                    compare(operation, step)
                if step == 0:
                    outcomes[f'{order}_first_mode{actor_word(state["prince"], 16)}'] += 1
            outcomes[f'final_bank{len(state["trobs"])}'] += 1
            outcomes[f'final_source{actor_word(state["prince"], 40)}'] += 1
    return dict(cases=dict(counts), traces=counts['bank'] // 8, events=dict(visits), services=dict(services),
                outcomes=dict(outcomes), mismatches=0, outputs_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                sequence_sha256={str(n): hashlib.sha256(data).hexdigest() for n, data in raw.items()},
                level_sha256={str(n): hashlib.sha256(resources['LEVL'][1999 + n]['data']).hexdigest()
                              for n in range(10, 14)},
                supplied_services=['5:3828 gate cue request', '5:0fe6 redraw request', '5:4d84 audio request',
                                   '17:330e existence/prepared handle,4:3098 prepared original sequence handles',
                                   'HGetState/HLock/HSetState state0; actor-copy fragment stopped before5:1528'],
                scope='Full native AnimTrobs iteration/stable compaction with temple gates and default-kind '
                      'records, actual actor clip/linked resources and copyback.8 persistent cycles in both '
                      'supplied actor-first/bank-first orders,6 supplied bank topologies including duplicates '
                      'and full20,5 position/phase controls at all41 original anchors. Not FrameAdv cadence '
                      'or reachable duplicate banks, controller/physics/fall/contact/death, pressure activation, '
                      'MOB motion, sound/pixels, saves/reset or playable temple integration.')


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
