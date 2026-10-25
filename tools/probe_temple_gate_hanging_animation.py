"""Compose real gate TROB animation with hanging selection/copyback and cue admission."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_gate_animation import gate_animation_reference
from tools.probe_temple_gate_hanging import (
    NativeGateHanging, actor_fixture, hanging_cue_reference, stop_actor_reference,
)


GATE_STATES = ((3, 1), (0, 0), (60, 4), (180, 3), (255, 1), (180, 2))


def hanging_animation_reference(foreground, phase, prince, working, room, cell, available=True):
    if len(working) != 62:
        raise ValueError('Expected a complete working actor')
    gate = gate_animation_reference(foreground, phase, relief_countdown=4321)
    events = []
    slow_terminal = phase in (0, 1) and (foreground & 255) != 255 and (gate['foreground'] & 255) == 0
    for event in gate['events']:
        if event == ('relief_check',):
            events.extend(hanging_cue_reference(prince, room, cell))
        events.append(event)
        if event == ('load_kid',):
            stopped = stop_actor_reference(prince, cell, gate['foreground'] & 255, available)
            prince, working = stopped['prince'], stopped['working']
            events.extend(stopped['events'][2:])
            if slow_terminal:
                events.extend(hanging_cue_reference(prince, room, cell))
    return dict(gate, events=events, prince=prince, working=working)


def run_probe(recovery):
    directory = Path(recovery) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    resources = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    if not resources['SEQS'][47]['data']:
        raise ValueError('Expected original SEQS47')
    machine = NativeGateHanging(parse_resource_fork(executable))
    counts, events, services, digest = Counter(), Counter(), Counter(), hashlib.sha256()
    working = bytes((i * 7 + 19) % 256 for i in range(62))
    cache = struct.pack('>6h', 11, 13, 17, 19, 23, 29)
    bank = bytes((i * 17 + 3) % 256 for i in range(160))
    anchors = 0
    for number in range(10, 14):
        original = resources['LEVL'][1999 + number]['data']
        if struct.unpack_from('>3h', original, 0x2186)[::2] != (2, number):
            raise ValueError('Expected original temple headers')
        for room in range(1, struct.unpack_from('>h', original, 0x2180)[0] + 1):
            for cell in range(30):
                if struct.unpack_from('>h', original, (room - 1) * 60 + cell * 2)[0] != 4:
                    continue
                anchors += 1
                row, column = divmod(cell, 10)
                for (position, phase), facing, action, delta, actor_room, available in product(
                        GATE_STATES, (-1, 0, 1), (0, 2, 6), (-1, 0, 1), (0, room), (False, True)):
                    prince = actor_fixture(actor_room, row + 1, column + delta, facing, action)
                    expected = hanging_animation_reference(position, phase, prince, working, room, cell, available)
                    level = bytearray(original)
                    offset = 0x780 + (room - 1) * 120 + cell * 4
                    struct.pack_into('>H', level, offset, position)
                    expected_level = bytearray(level)
                    struct.pack_into('>H', expected_level, offset, expected['foreground'])
                    machine.reset(level)
                    machine.available = available
                    machine.cpu.mem_write(machine.A5 - 0x5056, working)
                    machine.cpu.mem_write(machine.A5 - 0x50d2, prince)
                    machine.cpu.mem_write(machine.A5 - 0x34b0, cache)
                    machine.cpu.mem_write(machine.A5 - 0x448e, bank)
                    machine.cpu.mem_write(machine.A5 - 0x43ee, struct.pack('>4h', cell, room, phase, 4))
                    machine.put_word(-0x4fc2, room)
                    machine.put_word(-0x5008, 4321)
                    machine.call(5, 0x0cd6, (0,))
                    actual = dict(foreground=machine.word(-0x4818) & 65535, phase=machine.word(-0x43ea),
                                  relief_countdown=machine.word(-0x5008), events=machine.events,
                                  prince=bytes(machine.cpu.mem_read(machine.A5 - 0x50d2, 62)),
                                  working=bytes(machine.cpu.mem_read(machine.A5 - 0x5056, 62)))
                    service_names = {'sound': 'gate_sound', 'redraw': 'gate_redraw',
                                     'audio': 'audio_request', 'resource': 'resource_exists'}
                    expected_services = Counter(service_names[event[0]] for event in expected['events']
                                                if event[0] in service_names)
                    if (actual != expected or machine.services != expected_services
                            or machine.level_bytes(len(level)) != expected_level
                            or bytes(machine.cpu.mem_read(machine.A5 - 0x34b0, 12)) != cache
                            or bytes(machine.cpu.mem_read(machine.A5 - 0x448e, 160)) != bank
                            or struct.unpack('>4h', machine.cpu.mem_read(machine.A5 - 0x43ee, 8)) !=
                                (cell, room, expected['phase'], 4)):
                        raise AssertionError(dict(anchor=(number, room, cell), inputs=(position, phase, facing,
                                                  action, delta, actor_room, available),
                                                  actual=actual, expected=expected, services=machine.services))
                    counts[f'position{position}_phase{phase}'] += 1
                    events.update(event[0] for event in expected['events'])
                    services.update(machine.services)
                    digest.update(bytes(expected_level) + actual['prince'] + actual['working'])
                    digest.update(json.dumps(actual['events']).encode('ascii'))
    if anchors != 41:
        raise ValueError('Expected41 original temple gate anchors')
    return dict(cases=dict(counts), events=dict(events), services=dict(services), mismatches=0,
                outputs_sha256=digest.hexdigest(), executable_sha256=hashlib.sha256(executable).hexdigest(),
                sequence47_sha256=hashlib.sha256(resources['SEQS'][47]['data']).hexdigest(),
                level_sha256={str(n): hashlib.sha256(resources['LEVL'][1999 + n]['data']).hexdigest()
                              for n in range(10, 14)},
                supplied_services=['5:3828 gate cue request', '5:0fe6 redraw request', '5:4d84 audio request',
                                   '17:330e SEQS47 existence; missing-resource controls supplied'],
                scope='Native gate type4 TROB body, StopGate/LoadKid/JumpSeq47/copyback, hanging cue and '
                      'real temple relief rejection; all41 original anchors with supplied type0 actors. '
                      'Six phase/position controls, not every gate state. No AnimChar/clip execution, '
                      'actor controller/collision/death, bank iteration/compaction, complete FrameAdv, '
                      'sound playback/pixels, saves/reset or temple runtime integration.')


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
