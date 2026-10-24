"""Check per-slot loose-floor drawing against whole-room original renders.

Runs the original renderer for every loose-floor variant the previous export
enumerated (`extract_loose_floor_scenery`) and compares the slot composition
(`pop2.slot_drawing`) for the room, floor and climbing redraws and the
entrance frames. Needs the original program and imported resources:

    python -m tools.check_slot_scenery --source PATH_TO_RECOVERY [--level 6]
"""

import argparse
from collections import Counter
from functools import partial
import json
from pathlib import Path
import time

from pop2.caverns import scenery_name, scenery_resource, slot_variant
from pop2.crevices import hide_crevices
from pop2.level_data import LevelDefinition
from pop2.mac_resources import parse_resource_fork
from pop2.paths import ASSET_DIR


def check_level(program, resources, prince, number, base, progress=lambda _text: None):
    from pop2.caverns import delta_commands
    from tools.extract_caverns import CavernRecovery, extract_loose_floor_scenery, recover_room
    from tools.extract_slots import loose_floor_slot_scenery

    definition = LevelDefinition.read(parse_resource_fork(prince), number)
    level = hide_crevices(definition.data) if definition.kind == 4 else definition.data
    with CavernRecovery(program, resources, prince, track_reads=True) as machine:
        recover = partial(recover_room, _machine=machine)
        started = time.perf_counter()
        slots = loose_floor_slot_scenery(program, resources, prince, level, base, progress, recover=recover)
        slot_seconds = time.perf_counter() - started
    # The whole-room oracle renders every combination; one harness machine
    # fails after several thousand rooms, so it is renewed periodically.
    machines = {'count': 0, 'machine': None}

    def recover(*args, **options):
        if machines['machine'] is None or machines['count'] >= 400:
            if machines['machine'] is not None:
                machines['machine'].__exit__(None, None, None)
            machines['machine'] = CavernRecovery(program, resources, prince).__enter__()
            machines['count'] = 0
        machines['count'] += 1
        return recover_room(*args, _machine=machines['machine'], **options)

    started = time.perf_counter()
    try:
        whole = extract_loose_floor_scenery(program, resources, prince, level, base, progress, recover=recover)
    finally:
        if machines['machine'] is not None:
            machines['machine'].__exit__(None, None, None)
    whole_seconds = time.perf_counter() - started
    results = Counter()
    for room, info in whole['rooms'].items():
        climb = base.get('climb_redraw', {}).get(room, {})
        for key, variant in info['variants'].items():
            if info.get('delta'):
                variant = {'commands': delta_commands(base['rooms'][room], variant['commands']),
                           'floor_redraw': delta_commands(base['floor_redraw'][room], variant['floor_redraw']),
                           'climb_redraw': {action: delta_commands(climb.get(action, []), items)
                                            for action, items in variant['climb_redraw'].items()},
                           **({'entry_frames': [delta_commands(frame['commands'], items) for frame, items
                                                in zip(base['entry_exit']['frames'], variant['entry_frames'])]}
                              if 'entry_frames' in variant else {})}
            composed = slot_variant(slots, slots['rooms'][room], key)
            for part, value in variant.items():
                results['match' if composed.get(part) == value else 'differ'] += 1
    return {'level': number, 'variants': sum(len(info['variants']) for info in whole['rooms'].values()),
            'checks': dict(results), 'slot_seconds': round(slot_seconds, 1),
            'whole_room_seconds': round(whole_seconds, 1), 'slot_bytes': len(json.dumps(slots)),
            'whole_room_bytes': len(json.dumps(whole))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='Original recovery directory')
    parser.add_argument('--level', type=int, action='append', help='Level number (default: 3-7)')
    options = parser.parse_args()
    program = (options.source / 'resource_forks' / 'Prince of Persia 2.bin').read_bytes()
    prince = (ASSET_DIR / 'Prince.rsrc').read_bytes()
    failed = False
    for number in options.level or (3, 4, 5, 6, 7):
        resources = (ASSET_DIR / scenery_resource(number)).read_bytes()
        base = json.loads((ASSET_DIR / scenery_name(number)).read_text(encoding='ascii'))
        report = check_level(program, resources, prince, number, base)
        print(json.dumps(report))
        failed |= bool(report['checks'].get('differ'))
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
