"""Original temple gate face/back distances with real admission and room adjustment.

Working actor, collision edges and visible/neighbor-room slots are supplied.
The two distance helpers, admission, classification and AdjustRoom execute
without supplied endpoints. This is not the general 4:5eae selector, collision
bank construction, frame loading, InitRoom or a reachable gameplay trace.
"""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_admission import admission_reference
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import NativeTempleGateStanding
from tools.probe_temple_slide_rock_update import actor_word


NEIGHBOR_SLOTS = (-0x4fc0, -0x4fb4, -0x4fb8, -0x4fbe, -0x4fb2, -0x4fb6)


def adjusted_anchor_reference(anchor, room, view, neighbors):
    """4:56e6 reads two left/two right slots; the third on each side is not read."""
    if len(neighbors) != 6:
        raise ValueError('Expected the six supplied room slots')
    if room != view:
        if room in neighbors[:2]:
            anchor = signed_word(anchor - 510)
        elif room in neighbors[3:5]:
            anchor = signed_word(anchor + 510)
    return anchor


def distance_reference(actor, foreground, gate_room, gate_column, edges,
                       view_room, neighbors, *, back=False, anchor=73):
    """Gate type1's two geometric distances; all arithmetic stores signed words."""
    if (len(actor) != 62 or actor_word(actor, 2) not in (-1, 0)
            or not 0 <= foreground <= 65535 or not 1 <= gate_room <= 32
            or not 0 <= gate_column <= 9 or len(neighbors) != 6 or len(edges) != 2):
        raise ValueError('Outside the bounded temple gate geometry domain')
    if not back and not admission_reference(actor, foreground, 2):
        return dict(distance=-1, anchor=anchor)
    anchor = adjusted_anchor_reference(signed_word(229 + gate_column * 51),
                                       gate_room, view_room, neighbors)
    # DATA type1: face offset40, back offset0, cell span50.
    left, right = edges
    left_distance = signed_word(left - signed_word(anchor + 50))
    right_distance = signed_word(signed_word(anchor + 40) - right)
    left_facing = actor_word(actor, 2) == -1
    distance = left_distance if left_facing != back else right_distance
    return dict(distance=distance, anchor=anchor)


class NativeTempleGateDistance(NativeTempleGateStanding):
    RANGES = dict(NativeTempleGateStanding.RANGES)
    RANGES[4] += ((0x52bc, 0x5358), (0x56e6, 0x5728), (0x5b0e, 0x5ba8),
                  (0x6562, 0x65f8), (0x6610, 0x6696))


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(executable)
    levels = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL']
    machine = NativeTempleGateDistance(program)
    counts, outcomes, digest = Counter(), Counter(), hashlib.sha256()
    machine.reset(levels[2009]['data'])
    if (machine.word(-0x3620 + 2), machine.word(-0x360e + 2)) != (40, 0):
        raise AssertionError('Original type1 barrier offsets differ from the model')

    def check(level, actor, room, column, foreground, edges, view, neighbors, back, label):
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, actor)
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(range(62)))
        machine.cpu.mem_write(machine.A5 - 0x448e, bytes(range(160)))
        machine.put_word(-0x4fc2, view)
        machine.put_word(-0x34ae, foreground)
        machine.put_word(-0x35fc, 73)
        for offset, value in zip(NEIGHBOR_SLOTS, neighbors):
            machine.put_word(offset, value)
        for offset, value in zip((-0x3564, -0x3566), edges):
            machine.put_word(offset, value)
        expected = distance_reference(actor, foreground, room, column, edges, view, neighbors,
                                      back=back)
        before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        actual = signed_word(machine.call(4, 0x6610 if back else 0x6562, (4, room, column)))
        struct.pack_into('>h', before, len(machine.data) - 0x35fc, expected['anchor'])
        after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        if (actual != expected['distance'] or after != before or machine.services or machine.reads
                or machine.level_bytes(len(level)) != level):
            raise AssertionError(dict(label=label, actor=actor.hex(), room=room, column=column,
                                      foreground=foreground, edges=edges, view=view,
                                      neighbors=neighbors, back=back, actual=actual, expected=expected,
                                      changed=[(hex(i - len(machine.data)), a, b)
                                               for i, (a, b) in enumerate(zip(before, after)) if a != b]))
        counts[label] += 1
        outcomes['negative' if actual < 0 else 'nonnegative'] += 1
        digest.update(actor + struct.pack('>7h', room, column, *edges, view,
                                        actual, expected['anchor']))

    gates = 0
    for number in range(10, 14):
        level = levels[1999 + number]['data']
        for room, cell in product(range(1, 33), range(30)):
            if struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0] != 4:
                continue
            gates += 1
            row, column = divmod(cell, 10)
            for facing, kind, source, height, foreground, delta, back in product(
                    (-1, 0), (0, 1, 4), (9, 68), (34, 74), (0, 1, 96, 100, 183, 184, 255, 0x8100),
                    (-25, -1, 0, 25, 51), (False, True)):
                actor = bytearray(actor_fixture(room, row, column, facing, 0))
                for offset, value in ((8, kind), (40, source), (42, 20), (46, 20 + height)):
                    put_actor(actor, offset, value)
                anchor = 229 + column * 51
                check(level, bytes(actor), room, column, foreground,
                      (anchor + delta, anchor + delta + 30), room, (0,) * 6, back,
                      'original_gate_anchors')
    level = levels[2009]['data']
    # Neighbor slot priority, same-room precedence, an unrelated room and
    # signed-word edge/absolute-distance controls. No InitRoom is executed.
    neighbors_cases = ((2, 3, 4, 5, 6, 7), (5, 6, 7, 2, 3, 4),
                       (2, 0, 0, 2, 0, 0), (0,) * 6) + tuple(
                       tuple(2 if i == slot else 0 for i in range(6)) for slot in range(6))
    for facing, kind, edges, view, neighbors, back in product(
            (-1, 0), (0, 1, 4),
            ((-32768, 32767), (32767, -32768), (-1, 0), (400, 430)),
            (1, 2), neighbors_cases,
            (False, True)):
        actor = bytearray(actor_fixture(1, 1, 4, facing, 0))
        for offset, value in ((8, kind), (42, 20), (46, 94)):
            put_actor(actor, offset, value)
        check(level, bytes(actor), 2, 4, 1, edges, view, neighbors, back, 'room_and_signed_controls')
    return dict(gates=gates, comparisons=dict(counts), outcomes=dict(outcomes), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                outputs_sha256=digest.hexdigest(), supplied=[], scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
