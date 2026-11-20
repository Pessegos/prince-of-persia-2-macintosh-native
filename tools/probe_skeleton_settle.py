"""Compare native SkelAddOpponent (CODE 4:198a-1a70) with the port's settle.

InitOpps 6:2ce6 calls SkelAddOpponent for a zero-cursor skeleton record each
time the Kid enters its room. The probe runs the original routine with its
own callees (17fa, 2bae, 39fc, 3a48, 3a72-3ae8, ReadCell 27ee, 3:4eb2,
5:48b0, GetOppInfo 6:3642) on every LEVL skeleton record of the skeleton
levels, with the record's X swept across the room, both facings, and a
range of supplied fields of the frame record already loaded (a5-0x520e
and a5-0x520a, whose low six bits GetFCharX subtracts; the Prince's frame
when the Kid enters). The globals InitOpps sets before the call are supplied
from the record as 6:2c1c-2cb8 does: slot -0x5056, room -0x5040/-0x4fc2,
row -0x5048 (signed /10, minus one if negative), X -0x5052, facing
-0x5054 and GetCharCol(X) -0x504a (computed by native 4:3ad6). No game or
emulator is operated.

The port side loads the same room through `CombatEncounter._load_room`,
with the skeleton FRAM 750 parsed by the port's decoder (the heap's own
pose feeds `_supporting_column`), then calls `Skeleton.settle_heap` with a
one-record Prince frame table carrying the same fields. Compared: the
resulting X and the selected sequence (112/119/63). Excluded: none; active
(marker 1) records are compared too and must stay put.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import struct
from types import SimpleNamespace

from pop2.animation_data import parse_frame_records, sequence_words
from pop2.combat import CombatEncounter
from pop2.mac_resources import parse_resource_fork
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import LevelMap
from tools.probe_level7_rules import NativeRules


class NativeSettle(NativeRules):
    RANGES = {
        3: ((0x4eb2, 0x4ee4),),
        4: ((0x17fa, 0x1836), (0x198a, 0x1a70), (0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x2bae, 0x2bcc), (0x322a, 0x3262),
            (0x39fc, 0x3a32), (0x3a48, 0x3aea)),
        5: ((0x0004, 0x0066), (0x48b0, 0x48dc), (0x4e0c, 0x4e42)),
        6: ((0x3642, 0x36de),),
    }
    SUPPLIED = {}


# Native X 207 is port X 0; the sweep covers the room and both neighbours' edges.
SWEEP_X = tuple(range(190, 735, 5))
# (a5-0x520e, a5-0x520a): FRAM offset_x and flags, whose low six bits
# GetFCharX 4:3a72 subtracts; the upper bits must not count.
FRAMES = tuple((offset, flags) for offset in range(-8, 61, 4) for flags in (0, 0xc5))


def skeleton_records(level):
    for native_room in range(1, 33):
        start = 0x20e6 + native_room * 0xc0
        for slot in range(struct.unpack_from('>H', level, start)[0]):
            address = start + 2 + slot * 38
            yield native_room, slot, address, struct.unpack_from('>19h', level, address)


def native_settle(machine, level, native_room, slot, address, words, frame):
    machine.reset(level)
    machine.cpu.mem_write(machine.LEVEL + address, struct.pack('>19h', *words))
    for offset, value in ((-0x4fc2, native_room), (-0x5040, native_room), (-0x5056, slot)):
        machine.put_word(offset, value)
    cell = words[0]
    row = int(cell / 10) - (cell < 0)
    machine.put_word(-0x5048, row)
    machine.put_word(-0x5052, words[1])
    machine.put_word(-0x5054, words[2])
    machine.put_word(-0x504a, machine.call(4, 0x3ad6, (words[1],)))
    machine.put_word(-0x520e, frame[0])
    machine.put_word(-0x520a, frame[1])
    machine.call(4, 0x198a, arg_bytes=struct.pack('>I', machine.LEVEL + address))
    record = machine.level_bytes(address + 38)[address:]
    return machine.word(-0x5052), struct.unpack_from('>h', record, 8)[0]


def run_probe(source, *, stride=1):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    skeleton = parse_resource_fork((forks / 'Skeleton.rsrc.bin').read_bytes())
    art = SimpleNamespace(frames=parse_frame_records(skeleton['FRAM'][750]['data']))
    machine = NativeSettle(parse_resource_fork(executable))
    sequences = {key: sequence_words(value['data']) for key, value in prince['SEQS'].items()}
    counts, moved, digest = Counter(), Counter(), hashlib.sha256()
    for resource in sorted(prince['LEVL']):
        level = prince['LEVL'][resource]['data']
        if struct.unpack_from('>h', level, 0x21a4)[0] != 2:
            continue
        number = struct.unpack_from('>H', level, 0x218a)[0]
        kind = struct.unpack_from('>h', level, 0x2186)[0]
        player = SequenceRuntime(sequences, SequenceState(
            2, action=0, current_x=150, target_x=150, actor_type=0, level_kind=kind))
        encounter = CombatEncounter(player, sequences, None, 509, level=level, rng=random.Random(1))
        encounter.terrain = LevelMap(level)
        encounter.guard_art = art
        for native_room, slot, address, words in skeleton_records(level):
            encounter.room_encounters = {}
            encounter._load_room(native_room - 1)
            heap = encounter.room_encounters[native_room - 1][0][slot]
            first = heap.state.action, heap.state.source_sequence_id
            for x in SWEEP_X[::stride]:
                for facing in (-1, 0):
                    for frame in FRAMES[::stride]:
                        case = list(words)
                        case[1], case[2] = x, facing
                        native_x, native_sequence = native_settle(
                            machine, level, native_room, slot, address, case, frame)
                        state = heap.state
                        state.target_x = state.current_x = x - 207
                        state.facing = int(facing == 0)
                        encounter.player_frames = [SimpleNamespace(offset_x=frame[0], aux=frame[1])]
                        encounter.player.state.action = 0
                        heap.skeleton.settle_heap(encounter, heap)
                        actual = state.target_x + 207, first[1]
                        if actual != (native_x, native_sequence):
                            raise AssertionError(('settle', number, native_room, slot, x, facing,
                                                  frame, first, actual, (native_x, native_sequence)))
                        counts[f'level_{number}'] += 1
                        moved[f'level_{number}'] += native_x != x
                        digest.update(struct.pack('>3h', native_room, x, native_x))
    return dict(counts=dict(counts), moved=dict(moved), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                outputs_sha256=digest.hexdigest(),
                supplied=['InitOpps globals from each record (6:2c1c-2cb8)',
                          'Loaded frame record: a5-0x520e offset_x -8..60 step 4, '
                          'a5-0x520a flags 0 or 0xc5',
                          f'Record X {SWEEP_X[0]}-{SWEEP_X[-1]} step {5 * stride}, facings -1/0'],
                services=[], exclusions=__doc__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(counts=result['counts'], moved=result['moved'])))


if __name__ == '__main__':
    main()
