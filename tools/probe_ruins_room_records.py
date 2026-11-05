"""Compare native side-record transfers and unloaded ruins slab contacts.

Actual LEVL records and original CODE execute read-only in the probe CPU.
The room/link globals and debris are supplied; no game/emulator is operated.
Excludes full FrameAdv, drawing, loaded actor contact and native capacity loss.
"""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.loose_floors import FallingFloor, floor_hits_ruins_record
from pop2.animation_data import sequence_words
from pop2.mac_resources import parse_resource_fork
from pop2.ruins_actors import ruins_spawns
from pop2.ruins_ai import RuinsCreatures
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap, floor_y
from tools.probe_level7_rules import NativeRules


class NativeRoomRecords(NativeRules):
    RANGES = {5: ((0x377e, 0x3812),),
              6: ((0x2f4e, 0x3090), (0x3462, 0x3576), (0x358e, 0x3630), (0x3642, 0x36de)),
              19: ((0x4bb0, 0x4c4c),)}
    SUPPLIED = {}


def room_records(level, room):
    start = 0x20e6 + (room + 1) * 0xc0
    count = struct.unpack_from('>H', level, start)[0]
    return [struct.unpack_from('>19h', level, start + 2 + index * 38) for index in range(count)]


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    machine = NativeRoomRecords(parse_resource_fork(executable))
    sequences = {key: sequence_words(value['data']) for key, value in prince['SEQS'].items()}
    counts, positive, digests = Counter(), Counter(), []
    for number in (6, 7, 8, 9):
        level = prince['LEVL'][1999 + number]['data']
        assert struct.unpack_from('>H', level, 0x218a)[0] == number
        assert struct.unpack_from('>h', level, 0x21a4)[0] == 5
        terrain = LevelMap(level)
        for room in range(struct.unpack_from('>H', level, 0x2180)[0]):
            expected = {r: room_records(level, r) for r in range(32)}
            skipped = False
            for side, delta in (('left', -510), ('right', 510)):
                neighbor = terrain.neighbor(room, side)
                if neighbor is None:
                    continue
                for record in list(expected[neighbor]):
                    admitted = record[1] > 585 if side == 'left' else record[1] < 331
                    if not admitted:
                        continue
                    if len(expected[room]) >= 5:
                        # Preserve the port's existing capacity safeguard,
                        # not the original AddOpp failure + source deletion.
                        skipped = True
                        break
                    expected[neighbor].remove(record)
                    moved = list(record)
                    moved[1] += delta
                    moved[7] = len(expected[room])
                    expected[room].append(tuple(moved))
                    expected[neighbor] = [tuple((*r[:7], i, *r[8:]))
                                          for i, r in enumerate(expected[neighbor])]
            if skipped:
                counts['capacity_excluded'] += 1
                continue
            machine.reset(level)
            machine.put_word(-0x4fc2, room + 1)
            for side, global_offset in (('left', -0x4fc0), ('right', -0x4fbe)):
                linked = terrain.neighbor(room, side)
                machine.put_word(global_offset, 0 if linked is None else linked + 1)
            machine.call(6, 0x2f4e)
            actual_level = machine.level_bytes(len(level))
            creatures = RuinsCreatures()
            encounter = SimpleNamespace(level=level, level_kind=4, sequences=sequences, terrain=terrain)
            creatures.load_room(encounter, room)
            for source_room in range(32):
                actual = room_records(actual_level, source_room)
                if actual != expected[source_room]:
                    raise AssertionError(('side records', number, room + 1, source_room + 1,
                                          actual, expected[source_room]))
                runtime = Counter((a.row, a.state.target_x + 207, a.ruins.kind, a.ruins.skill)
                                  for a in creatures.actors(source_room))
                original = Counter((r[0] // 10, r[1], r[12], r[3]) for r in actual)
                # The host loads the current and immediate side rooms only.
                if source_room in creatures.rooms and runtime != original:
                    raise AssertionError(('runtime records', number, room + 1, source_room + 1,
                                          runtime, original))
            counts['side_room_entries'] += 1
            positive['transferred_records'] += len(expected[room]) - len(room_records(level, room))
            digests.append(hashlib.sha256(actual_level).hexdigest())
        for room in range(32):
            for spawn in ruins_spawns(level, room):
                record = struct.pack('>19h', *spawn.words)
                for velocity, displacement, dc in product((0, 8, 16, 32, 64),
                                                         (-1, 0, 1, 31, 64, 128, 256, 257),
                                                         (-1, 0, 1)):
                    threshold = floor_y(spawn.row) - (0 if spawn.kind == 8 else 57)
                    state = SequenceState(130, target_x=spawn.native_x - 207)
                    actor = SimpleNamespace(state=state, room=room, row=spawn.row, alive=True,
                        ruins=SimpleNamespace(kind=spawn.kind, removed=False))
                    block = FallingFloor(room, spawn.column + dc, spawn.row,
                                         threshold + displacement, velocity, 3)
                    machine.reset(level)
                    address = machine.LEVEL + 0x9000
                    machine.cpu.mem_write(address, record)
                    for offset, value in ((-0x44a6, block.x), (-0x44a4, block.y),
                                          (-0x44a0, velocity)):
                        machine.put_word(offset, value)
                    native = bool(machine.call(5, 0x377e, arg_bytes=struct.pack('>I', address)))
                    actual = floor_hits_ruins_record(block, actor)
                    if native != actual:
                        raise AssertionError(('record contact', number, room + 1, spawn.slot,
                                              velocity, displacement, dc, native, actual))
                    counts['record_contacts'] += 1
                    positive['record_contacts'] += native
    assert 0 < positive['record_contacts'] < counts['record_contacts']
    assert positive['transferred_records'] > 0
    return dict(counts=dict(counts), positive=dict(positive), mismatches=0,
        executable_sha256=hashlib.sha256(executable).hexdigest(),
        side_outputs_sha256=hashlib.sha256(''.join(digests).encode()).hexdigest(),
        supplied=['Native current/left/right room globals from actual links',
                  'Actual LEVL opponent records; supplied debris X/Y/velocity'],
        services=[], exclusions=__doc__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result['counts']))


if __name__ == '__main__':
    main()
