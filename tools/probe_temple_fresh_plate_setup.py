"""Recover temple first-press setup with explicit audio/redraw request sinks."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_mixed_plate_links import NativeMixedPlateLinks, add_trob, mixed_chain
from tools.probe_temple_slide_rock_admission import link_chain
from tools.probe_temple_slide_rock_geometry import TempleCellReader
from tools.probe_temple_slide_rock_lifecycle import store_bank


def plate_reference(state, reader, context):
    kind, foreground, cell, room, _, _ = reader.cache
    if kind not in (5, 6):
        raise ValueError('Expected a cached mode5/6 source plate')
    index = foreground & 255
    timer_offset = 0x1680 + index * 10 + 4
    timer = struct.unpack_from('>h', reader.level, timer_offset)[0]
    level = bytearray(reader.level)
    if timer != 31:
        struct.pack_into('>h', level, timer_offset, 5)
    reader.level = level
    if timer < 2:
        state = add_trob(state, room, cell, 1, kind)
        level_number = struct.unpack_from('>h', reader.level, 0x218a)[0]
        if context[0] != 185 and (room != 4 or level_number != 13):
            state = dict(state, events=state['events'] + [('sound', 27)])
        state = dict(state, events=state['events'] + [('redraw', room, cell, foreground & 65535)])
    state = mixed_chain(state, reader, index, kind, context)
    if timer < 2:
        state = dict(state, press_flag=1)
    level = bytearray(reader.level)
    struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + cell * 4, (foreground | 0x2000) & 65535)
    reader.level = level
    return state


class NativeFreshPlateSetup(NativeMixedPlateLinks):
    SUPPLIED = {(5, 0x4d84): 'audio_request', (5, 0x0f38): 'plate_redraw'}

    def dispatch(self, cpu, address, size, user):
        if address == self.address(5, 0x4d84):
            stack = cpu.reg_read(self.registers['a7'])
            cue = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            self.events.append(('sound', cue))
        elif address == self.address(5, 0x0f38):
            cell, room = self.word(-0x34ac), self.word(-0x34aa)
            offset = self.LEVEL + 0x780 + (room - 1) * 120 + cell * 4
            foreground = struct.unpack('>H', cpu.mem_read(offset, 2))[0]
            self.events.append(('redraw', room, cell, foreground))
        super().dispatch(cpu, address, size, user)


def source_fixtures(resources):
    fixtures, excluded = [], []
    for number in range(10, 14):
        level = resources['LEVL'][1999 + number]['data']
        if struct.unpack_from('>3h', level, 0x2186)[::2] != (2, number):
            raise ValueError('Inconsistent temple resource header')
        max_room = struct.unpack_from('>h', level, 0x2180)[0]
        for room in range(1, 33):
            for cell in range(30):
                kind = struct.unpack_from('>h', level, (room - 1) * 60 + cell * 2)[0]
                if kind not in (5, 6):
                    continue
                foreground = struct.unpack_from('>H', level, 0x780 + (room - 1) * 120 + cell * 4)[0]
                chain = link_chain(level, foreground & 255)
                if not any(target[3] == 25 for target in chain):
                    continue
                if room > max_room:
                    excluded.append((number, room, cell))
                    continue
                if any(target[3] not in (4, 25) for target in chain):
                    raise ValueError('Unexpected target mechanism')
                fixtures.append((f'original-{number}-{room}-{cell}', level, room, cell))
    if len(fixtures) != 7 or excluded != [(12, 29, 4)]:
        raise ValueError(('Unexpected source inventory', len(fixtures), excluded))
    # Supplied source placement isolates the level13/room4 sound suppression.
    source = next(entry for entry in fixtures if entry[0] == 'original-13-5-18')
    for number, room in ((12, 4), (13, 4), (13, 3)):
        level = bytearray(source[1])
        struct.pack_into('>h', level, 0x218a, number)
        struct.pack_into('>h', level, (room - 1) * 60 + 18 * 2, 6)
        foreground = struct.unpack_from('>H', level, 0x780 + 4 * 120 + 18 * 4)[0]
        struct.pack_into('>H', level, 0x780 + (room - 1) * 120 + 18 * 4, foreground)
        fixtures.append((f'supplied-sound-control-{number}-{room}', bytes(level), room, 18))
    return fixtures, excluded


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    fixtures, excluded = source_fixtures(resources)
    machine = NativeFreshPlateSetup(parse_resource_fork(executable))
    counts, services, digest = Counter(), Counter(), hashlib.sha256()
    canary = bytes((i * 37 + 11) % 256 for i in range(512))
    scratch = (11, 13, 17, 19, 23, 29, 31, 37)
    for label, original, room, cell in fixtures:
        offset = 0x780 + (room - 1) * 120 + cell * 4
        foreground = struct.unpack_from('>H', original, offset)[0]
        index = foreground & 255
        targets = link_chain(original, index)
        tr, tc = next(target[1:3] for target in targets if target[3] == 25)
        row, col = divmod(tc, 10)
        rock = (col * 51, 116 + row * 120, tr, 0, -2, 6, row, col * 51)
        filler = (9, room % 32 + 1, 1, 6)
        trobs = ((), (filler,) * 19, (filler,) * 20,
                 ((cell, room, -1, 99),) + (filler,) * 19)
        banks = ((), (rock,), ((0, 116, tr % 32 + 1, 0, 2, 6, 0, 0),) * 30)
        for timer, depressed, pose, bank, trob_bank in product(
                (-1, 0, 1, 2, 31), (False, True), (0, 185), banks, trobs):
            level = bytearray(original)
            struct.pack_into('>h', level, 0x1680 + index * 10 + 4, timer)
            struct.pack_into('>H', level, offset, (foreground & ~0x2000) | (0x2000 if depressed else 0))
            machine.reset(level)
            context = (pose, -1, room, 0)
            actor = bytearray((i * 11 + 3) % 256 for i in range(62))
            for location, value in ((8, 0), (10, pose), (22, room), (28, -1)):
                struct.pack_into('>h', actor, location, value)
            machine.cpu.mem_write(machine.A5 - 0x5056, bytes(actor))
            machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(actor))
            machine.put_word(-0x4fc2, room)
            machine.put_word(-0x4fc4, 0)
            machine.put_word(-0x439e, 1234)
            machine.put_word(-0x4f9e, 4321)
            storage = bytearray((i * 19 + 7) % 256 for i in range(160))
            for i, record in enumerate(trob_bank):
                struct.pack_into('>4h', storage, i * 8, *record)
            state = dict(mob=scratch, bank=tuple(bank), bank_storage=store_bank(canary, bank),
                         trobs=tuple(trob_bank), trob_storage=bytes(storage), trob_scratch=(41, 43, 47, 53),
                         object_calls=[], rock_calls=[], events=[], press_flag=4321)
            machine.cpu.mem_write(machine.A5 - 0x44a6, struct.pack('>8h', *scratch))
            machine.cpu.mem_write(machine.BANK - 16, state['bank_storage'])
            machine.cpu.mem_write(machine.A5 - 0x4496, struct.pack('>I', machine.BANK))
            machine.put_word(-0x4490, len(bank))
            machine.cpu.mem_write(machine.A5 - 0x448e, state['trob_storage'])
            machine.cpu.mem_write(machine.A5 - 0x43ee, struct.pack('>4h', *state['trob_scratch']))
            machine.put_word(-0x43e6, len(trob_bank))
            reader = TempleCellReader(level, room)
            for repetition in range(2):
                machine.clear_events()
                machine.services.clear()
                reader.requests.clear()
                state = dict(state, object_calls=[], rock_calls=[], events=[])
                reader.read(room, cell % 10, cell // 10)
                machine.call(4, 0x27ee, (room, cell % 10, cell // 10))
                state = plate_reference(state, reader, context)
                machine.call(5, 0x240c, (0, -1))
                actual = dict(mob=struct.unpack('>8h', machine.cpu.mem_read(machine.A5 - 0x44a6, 16)),
                              bank=tuple(struct.unpack('>8h', machine.cpu.mem_read(machine.BANK + i * 16, 16))
                                         for i in range(machine.word(-0x4490))),
                              bank_storage=bytes(machine.cpu.mem_read(machine.BANK - 16, 512)),
                              trobs=tuple(struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x448e + i * 8, 8))
                                          for i in range(machine.word(-0x43e6))),
                              trob_storage=bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)),
                              trob_scratch=struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x43ee, 8)),
                              object_calls=machine.object_calls, rock_calls=machine.rock_calls,
                              events=machine.events, press_flag=machine.word(-0x4f9e))
                expected_services = Counter('audio_request' if event[0] == 'sound' else 'plate_redraw'
                                            for event in state['events'] if event[0] in ('sound', 'redraw'))
                if (actual != state or machine.services != expected_services
                        or machine.level_bytes(len(reader.level)) != reader.level
                        or machine.reads != reader.requests or machine.cache() != reader.cache
                        or bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)) != actor
                        or bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)) != actor
                        or machine.word(-0x439e) != 1234):
                    raise AssertionError(dict(label=label, timer=timer, repetition=repetition,
                                              pose=pose, banks=(len(bank), len(trob_bank)),
                                              differences={key: (actual[key], state[key]) for key in state
                                                           if actual[key] != state[key]},
                                              cache=(machine.cache(), reader.cache), services=machine.services))
                category = 'original_source_calls' if label.startswith('original') else 'supplied_sound_control_calls'
                counts[category] += 1
                services.update(machine.services)
                digest.update(bytes(reader.level) + actual['bank_storage'] + actual['trob_storage'])
                digest.update(json.dumps([actual['events'], actual['press_flag'], actual['mob'],
                                         actual['trob_scratch'], len(actual['bank']), len(actual['trobs']),
                                         machine.cache(), machine.reads]).encode('ascii'))
    return dict(cases=dict(counts), mismatches=0, services=dict(services),
                source_labels=[entry[0] for entry in fixtures], excluded_raw_sources=excluded,
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
                level_hashes={str(n): hashlib.sha256(resources['LEVL'][1999 + n]['data']).hexdigest()
                              for n in range(10, 14)},
                supplied_services=['5:4d84 AddSound: record request; no queue or priority behavior',
                                   '5:0f38 RedrawPlate: record source foreground; no rectangle/pixels'],
                scope=('Full PushPlate decision flow for seven admitted resource sources and three explicitly '
                       'supplied room/level sound controls, including first press then held repeat, native '
                       'link traversal, gate/rock activation and both banks. Audio/redraw bodies are supplied '
                       'no-op request sinks; no sound playback/priority, redraw effects, actual actor admission, '
                       'TROB animation, timer decay, FrameAdv, saves or gameplay parity claimed.'))


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
