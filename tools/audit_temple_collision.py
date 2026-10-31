"""Compare the port's wall correction with Codex's temple collision references.

Pure Python: two frames of CheckBarr 4:4e34 (banks_reference: history,
three row sweeps, incoming contacts) and CheckCollide1 4:54da
(decision_reference), whose Collide 4:5738 argument is added to X
(4:575e), against `LevelMap.wall_correction` for the same step. The
references are native-checked by their own probes; this audit checks the
port against them, not the native program directly. Supplied: an empty
MOB bank (no sliding rocks), a cold history before the first frame, the
Kid's fixture words, body height 74 and no displayed-room slots.
"""

import argparse
from collections import Counter
from itertools import product
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.coordinates import NATIVE_X_ORIGIN
from pop2.mac_resources import parse_resource_fork
from pop2.terrain import LevelMap
from tools.probe_temple_collision_banks import banks_reference, column_reference
from tools.probe_temple_collision_decision import decision_reference
from tools.probe_temple_collision_history import TABLES
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_gate_standing import StandingCellReader


def native_step(level, room, row, old, new, facing, armed, half, height=74):
    """The native-reference correction for one step (port scene X), and
    whether the first position already overlapped a barrier (mask 0xff)."""
    tables = {name: [65535] * 10 if name.endswith('tags') else [0] * 10 for name in TABLES}
    previous = row
    result, overlapped = None, False
    for x in (old, new):
        native = x + NATIVE_X_ORIGIN
        edges = (native - half, native + half + 1)
        actor = bytearray(actor_fixture(room, row, column_reference(native)[0], facing, 0))
        for offset, value in ((4, native), (6, row * 120 + 106), (8, 0), (10, 15),
                              (18, new - old), (26, armed), (28, -1), (30, 3), (40, 2),
                              (42, 20), (46, 20 + height)):
            put_actor(actor, offset, value)
        reader = StandingCellReader(level, room)
        banks = banks_reference(bytes(actor), edges, tables, reader, previous, height=height)
        tables, previous = banks['tables'], banks['previous']
        if x is old:
            overlapped = any(mask == 0xff for mask in tables['current_masks'])
        if x is new:
            decision = decision_reference(bytes(actor), edges, tables['current_tags'],
                                          banks['hit_low'], banks['hit_high'], reader,
                                          height=height, anchor=banks['anchor'])
            result = decision['events'][0][1] if decision['events'] else 0
    return result, overlapped


def run_audit(source):
    forks = Path(source) / 'resource_forks'
    levels = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL']
    totals, mismatches, examples = Counter(), Counter(), {}
    for number in range(10, 14):
        level = levels[1999 + number]['data']
        terrain = LevelMap(level)
        rooms = struct.unpack_from('>H', level, 0x2180)[0]
        for room, row, x, delta, facing, armed in product(
                range(1, rooms + 1), range(3), range(10, 500, 7), (-9, -4, -1, 1, 4, 9),
                (-1, 0), (0, 1)):
            half = 12
            old, new = x, x + delta
            try:
                native, overlapped = native_step(level, room, row, old, new, facing, armed, half)
            except ValueError:
                totals['outside reference domain'] += 1
                continue
            state = SimpleNamespace(actor_type=0, source_sequence_id=2, facing=int(facing == 0))
            bounds = (new - half, 0, new + half, 73)
            old_bounds = (old - half, 0, old + half, 73)
            corrected = terrain.wall_correction(room - 1, old, new, bounds, old_bounds,
                                                None if armed else state.facing,
                                                physical_row=row, state=state)
            port = corrected - new
            # A start already inside a barrier has no native contact to
            # find (the earlier frame would have met it); counted apart.
            label = f'level {number}' + (' overlapping start' if overlapped else '')
            totals[label] += 1
            if port != native:
                key = (label, 'armed' if armed else 'unarmed')
                mismatches[key] += 1
                examples.setdefault(key, []).append(dict(room=room, row=row, old=old, new=new,
                                                         facing=facing, native=native, port=port))
    return dict(cases=dict(totals),
                mismatches={f'{a} {b}': n for (a, b), n in mismatches.items()},
                examples={f'{a} {b}': v[:8] for (a, b), v in examples.items()},
                supplied=__doc__.split('Supplied: ')[1].strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_audit(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: report[key] for key in ('cases', 'mismatches')}, indent=2))
    for key, items in report['examples'].items():
        print(key, items[:3])


if __name__ == '__main__':
    main()
