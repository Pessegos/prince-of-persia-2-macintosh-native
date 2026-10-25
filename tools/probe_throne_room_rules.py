"""Check the native throne barrier and special music without external services."""

import argparse
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules


class ThroneRules(NativeRules):
    RANGES = {4: ((0x52bc, 0x5358),), 5: ((0x5388, 0x5466),)}
    SUPPLIED = {}


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    program = parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes())
    level = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2007]['data']
    machine = ThroneRules(program)
    songs = barriers = 0
    for number, room, sword, fighting in product((6, 7, 8, 9), (1, 9, 10, 32), (-1, 0, 1, 2), (0, 1)):
        data = bytearray(level)
        struct.pack_into('>H', data, 0x218a, number)
        machine.reset(data)
        for offset, value in ((-0x4fc2, room), (-0x500a, sword), (-0x5200, 0), (-0x50ca, 0)):
            machine.put_word(offset, value)
        song = machine.call(5, 0x5388, (fighting,))
        expected = 180 if number == 8 and room == 9 and sword != 1 else 65535
        if song != expected or machine.services:
            raise AssertionError((number, room, sword, fighting, song, expected))
        songs += 1
        barrier = machine.call(4, 0x52bc, (4,))
        expected = 8 if number == 8 and room == 9 else 1
        if barrier != expected or machine.services:
            raise AssertionError((number, room, barrier, expected))
        barriers += 1
    offsets = [machine.word(-0x3620 + 8 * 2), machine.word(-0x360e + 8 * 2)]
    if offsets != [16, 24]:
        raise AssertionError(offsets)
    return {'music_cases': songs, 'barrier_cases': barriers, 'barrier_offsets': offsets,
            'mismatches': 0, 'supplied': ['Level eight LEVL with controlled level/room/sword/combat fields'],
            'external_services': [],
            'scope': 'Actual 5:5388 SpecialMusic and 4:52bc GetBarrCode, original DATA offsets; '
                     'not complete audio playback, collision scheduling or NIS rendering.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
