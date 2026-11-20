"""Compare native CheckSideRoomsForVisibleOpps with the port's room entry.

Original CODE 6:2f4e-308a (with RemoveOpp 3462, AddOpp 358e and GetOppInfo
3642) runs on LEVL records of every level whose opponent set the ordinary
bank holds (0, 2, 7): first the actual initial records, then one copy of each
of the level's record kinds appended to each side room at native X around
both thresholds. Only the current/left/right room globals are supplied, from
the level's own links; no game or emulator is operated. The port side calls
the production routine `CombatEncounter._take_visible_side_records` after
loading the entered room alone, so it checks that rule, not the full
enter_room carry/Cut scheduler. Skeleton heaps are compared at their LEVL X:
SkelAddOpponent's settle (4:19f0) runs later in InitOpps than 6:2f4e, and
the port settles only on entry (`_settle_entered_heaps`), so building a side
room early leaves its records at the X 2f4e reads.

Excluded and reported separately: records the port does not represent in
the ordinary bank (temple kinds other than the guard and the flaming sword),
palace figures (actor 6, kept by the final-path code) and entries where the
entered room already holds five records (native AddOpp drops the sixth
after RemoveOpp has deleted it; the port keeps it in its room).
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import struct

from pop2.animation_data import sequence_words
from pop2.combat import CombatEncounter, GuardSpawn
from pop2.mac_resources import parse_resource_fork
from pop2.sequence_runtime import SequenceRuntime, SequenceState
from pop2.terrain import LevelMap
from tools.probe_level7_rules import NativeRules


class NativeSideRecords(NativeRules):
    RANGES = {6: ((0x2f4e, 0x3090), (0x3462, 0x3576), (0x358e, 0x3630), (0x3642, 0x36de))}
    SUPPLIED = {}


# Native X around both thresholds (331 right, 585 left) and far inside.
SWEEP_X = (100, 330, 331, 332, 400, 584, 585, 586, 650)
SIDES = (('left', -510), ('right', 510))


def room_records(level, native_room, *, slots=True):
    start = 0x20e6 + native_room * 0xc0
    count = struct.unpack_from('>H', level, start)[0]
    records = [struct.unpack_from('>19h', level, start + 2 + index * 38) for index in range(count)]
    # Word 7 is the record's slot; RemoveOpp renumbers those left behind.
    return records if slots else [(*r[:7], *r[8:]) for r in records]


def with_record(level, native_room, words):
    """A copy of LEVL with one more record appended to a room's bank."""
    data = bytearray(level)
    start = 0x20e6 + native_room * 0xc0
    count = struct.unpack_from('>H', data, start)[0]
    words = list(words)
    words[7] = count
    struct.pack_into('>19h', data, start + 2 + count * 38, *words)
    struct.pack_into('>H', data, start, count + 1)
    return bytes(data)


def compare_entry(machine, sequences, level, room):
    """Run 6:2f4e and the port rule for one entry; return its outcome."""
    terrain = LevelMap(level)
    kind = struct.unpack_from('>h', level, 0x2186)[0]
    sides = {side: terrain.neighbor(room, side) for side, _delta in SIDES}
    machine.reset(level)
    machine.put_word(-0x4fc2, room + 1)
    for side, offset in (('left', -0x4fc0), ('right', -0x4fbe)):
        machine.put_word(offset, 0 if sides[side] is None else sides[side] + 1)
    before = {r: room_records(level, r + 1, slots=False) for r in range(32)}
    machine.call(6, 0x2f4e)
    native_level = machine.level_bytes(len(level))
    after = {r: room_records(native_level, r + 1, slots=False) for r in range(32)}
    digest = hashlib.sha256(native_level).hexdigest()
    moved = len(after[room]) - len(before[room])
    if sum(len(before[r]) - len(after[r]) for r in range(32)):
        return 'capacity_excluded', moved, [], digest
    port_types = {r: {(s.row, s.x + 207): s.actor_type
                      for s in GuardSpawn.all_from_level(level, r)} for r in range(32)}
    skip = []
    for side, _delta in SIDES:
        source_room = sides[side]
        if source_room is None or source_room == room:
            continue
        for words in before[source_room]:
            if words not in after[source_room]:
                actor = port_types[source_room].get((words[0] // 10, words[1]))
                if actor not in (2, 4, 10):
                    skip.append((room + 1, source_room + 1, words[1], words[11], actor))
    if skip:
        return 'unrepresented_moves_excluded', moved, skip, digest
    player = SequenceRuntime(sequences, SequenceState(
        2, action=15, current_x=150, target_x=150, actor_type=0, level_kind=kind))
    encounter = CombatEncounter(player, sequences, None, 509, level=level, rng=random.Random(1))
    encounter.terrain = terrain
    encounter.room_encounters = {}
    encounter.player.room = room
    encounter._load_room(room)
    encounter.guards = encounter.room_encounters[room][0]
    encounter._take_visible_side_records(room)
    for check in {room, *(r for r in sides.values() if r is not None)}:
        encounter._load_room(check)
        actual = Counter((a.row, a.state.target_x + 207,
                          a.state.actor_type)
                         for a in encounter.room_encounters[check][0])
        expected = Counter()
        for words in after[check]:
            key = (words[0] // 10, words[1])
            if words in before[check]:
                actor = port_types[check].get(key)
            else:
                actor = next((port_types[sides[side]][(key[0], key[1] - delta)]
                              for side, delta in SIDES
                              if sides[side] is not None
                              and (key[0], key[1] - delta) in port_types[sides[side]]), None)
            if actor is not None:
                expected[(*key, actor)] += 1
        if actual != expected:
            raise AssertionError(('side records', struct.unpack_from('>H', level, 0x218a)[0],
                                  room + 1, check + 1, sorted(actual.items()),
                                  sorted(expected.items()),
                                  [a.state.target_x for r in sides.values() if r is not None
                                   for a in encounter.room_encounters.get(r, ((),))[0]]))
    return 'room_entries', moved, [], digest


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    machine = NativeSideRecords(parse_resource_fork(executable))
    sequences = {key: sequence_words(value['data']) for key, value in prince['SEQS'].items()}
    counts, positive, excluded, digests = Counter(), Counter(), Counter(), []

    def tally(phase, number, result):
        status, moved, skip, digest = result
        counts[f'{phase}_{status}'] += 1
        digests.append(digest)
        for _room, _source, _x, raw_kind, actor in skip:
            excluded[f'level {number} {phase} raw kind {raw_kind} port actor {actor}'] += 1
        if status == 'room_entries':
            positive[f'{phase}_transferred_records'] += moved
            positive[f'{phase}_entries_with_transfer'] += bool(moved)

    for resource in sorted(prince['LEVL']):
        level = prince['LEVL'][resource]['data']
        number = struct.unpack_from('>H', level, 0x218a)[0]
        if struct.unpack_from('>h', level, 0x21a4)[0] not in (0, 2, 7):
            continue
        terrain = LevelMap(level)
        rooms = range(struct.unpack_from('>H', level, 0x2180)[0])
        for room in rooms:
            tally('initial', number, compare_entry(machine, sequences, level, room))
        templates = {}
        for room in rooms:
            for words in room_records(level, room + 1):
                templates.setdefault(words[12], words)
        for room in rooms:
            for side, _delta in SIDES:
                source_room = terrain.neighbor(room, side)
                if (source_room is None or source_room == room
                        or len(room_records(level, source_room + 1)) >= 5):
                    continue
                for template in templates.values():
                    for x in SWEEP_X:
                        words = list(template)
                        words[1] = x
                        placed = with_record(level, source_room + 1, words)
                        tally('sweep', number, compare_entry(machine, sequences, placed, room))
    assert positive['initial_transferred_records'] > 0
    assert 0 < positive['sweep_entries_with_transfer'] < counts['sweep_room_entries']
    return dict(counts=dict(counts), positive=dict(positive), mismatches=0,
                excluded_moves=dict(excluded),
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                side_outputs_sha256=hashlib.sha256(''.join(digests).encode()).hexdigest(),
                supplied=['Native current/left/right room globals from actual LEVL links',
                          'Actual initial LEVL opponent records of sets 0, 2 and 7',
                          'Sweep: one copy of each level record kind appended to a side '
                          'room at native X ' + ', '.join(map(str, SWEEP_X))],
                services=[], exclusions=__doc__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(counts=result['counts'], positive=result['positive'],
                          excluded=result['excluded_moves'])))


if __name__ == '__main__':
    main()
