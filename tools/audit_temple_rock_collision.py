"""Compare the port's rock collision with the native-checked references.

Pure Python: two frames of CheckBarr 4:4e34 with a live rock (banks_reference)
and CheckCollide1 4:54da (decision_reference), both checked against the
original code by tools/probe_temple_rock_overlay.py, against
`LevelMap.wall_correction` for the same step. Runs at every tile-25 cell of
levels 10-13. Supplied: the rock's X and control, its 0 or 2 pixel step, the
Kid's fixture words, body height 74, a cold history before the first frame
and no displayed-room slots. Starts already past a face or inside a barrier
are counted apart, as in tools/audit_temple_collision.py.
"""

import argparse
from collections import Counter
from itertools import product
import json
from pathlib import Path
from types import SimpleNamespace

from pop2.cavern_state import CavernState
from pop2.coordinates import NATIVE_X_ORIGIN
from pop2.mac_resources import parse_resource_fork
from pop2.slide_rocks import SlideRocks
from pop2.terrain import LevelMap
from tools.probe_temple_collision_banks import banks_reference
from tools.probe_temple_collision_decision import decision_reference
from tools.probe_temple_collision_history import TABLES
from tools.probe_temple_gate_standing import StandingCellReader
from tools.probe_temple_rock_overlay import HALF, fixture, rock_cells


def native_step(level, room, row, old, new, mobs, facing, armed):
    """The native-reference correction for one step (port scene X), and
    whether the body overlapped a barrier or crossed a face at the start."""
    tables = {name: [65535] * 10 if name.endswith('tags') else [0] * 10 for name in TABLES}
    previous, result, overlapped = row, None, False
    reader = StandingCellReader(level, room)
    for index, (x, mob) in enumerate(zip((old, new), mobs)):
        native = x + NATIVE_X_ORIGIN
        edges = (native - HALF, native + HALF + 1)
        actor = fixture(room, row, native, facing, armed, new - old)
        banks = banks_reference(actor, edges, tables, reader, previous, mobs=(mob,))
        tables, previous = banks['tables'], banks['previous']
        if not index:
            overlapped = any(mask == 0xff for mask in tables['current_masks'])
        else:
            decision = decision_reference(actor, edges, tables['current_tags'], banks['hit_low'],
                                          banks['hit_high'], reader, anchor=banks['anchor'],
                                          mobs=(mob,))
            result = decision['events'][0][1] if decision['events'] else 0
    return result, overlapped


def run_audit(source, x_step=9):
    forks = Path(source) / 'resource_forks'
    levels = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL']
    totals, mismatches, examples = Counter(), Counter(), {}
    for number, level, room, row, column in rock_cells(levels):
        start = column * 51
        terrain = LevelMap(level)
        for x, control, delta, offset, face, facing, armed in product(
                range(start, 11, -x_step), (2, 100), (-9, -4, -1, 0, 1, 4, 9), range(-15, 16, 2),
                (11, 72), (-1, 0), (0, 1)):
            step = 0 if control == 100 else 2
            mobs = ((x + step, 236, room, 0, control, 6, row, start),
                    (x, 236, room, 0, control, 6, row, start))
            terrain.caverns = CavernState(rocks=SlideRocks([mobs[1]]))
            old, new = x + face + offset - delta, x + face + offset
            try:
                native, overlapped = native_step(level, room, row, old, new, mobs, facing, armed)
            except ValueError:
                totals['outside reference domain'] += 1
                continue
            state = SimpleNamespace(actor_type=0, source_sequence_id=2, facing=int(facing == 0),
                                    sequence_mode=0, animation_state=0, action=15)
            bounds = (new - HALF, 0, new + HALF, 73)
            old_bounds = (old - HALF, 0, old + HALF, 73)
            corrected = terrain.wall_correction(room - 1, old, new, bounds, old_bounds,
                                                None if armed else state.facing,
                                                physical_row=row, state=state)
            port = corrected - new
            label = f'level {number}' + (' overlapping start' if overlapped else '')
            totals[label] += 1
            totals['native contact' if native else 'native clear'] += 1
            if port != native:
                key = (label, 'armed' if armed else 'unarmed', 'rock ' + ('moving' if step else 'still'))
                mismatches[key] += 1
                examples.setdefault(key, []).append(dict(
                    room=room, row=row, rock=x, old=old, new=new, facing=facing,
                    native=native, port=port))
    return dict(cases=dict(totals),
                mismatches={' '.join(key): count for key, count in mismatches.items()},
                examples={' '.join(key): items[:6] for key, items in examples.items()},
                supplied=__doc__.split('Supplied: ')[1].strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--x-step', type=int, default=9)
    args = parser.parse_args()
    report = run_audit(args.source, args.x_step)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('cases', 'mismatches')}, indent=2))
    for key, items in report['examples'].items():
        print(key, items[:3])


if __name__ == '__main__':
    main()
