"""Inventory linked-room sources in imported scenery, without running a game.

Counts cover all 32 stored room slots per exported level, including unused
slots. A reference does not prove visible pixels or campaign reachability.
"""

import argparse
from collections import Counter
import json
from pathlib import Path

from pop2.caverns import cavern_assets, cavern_flask_instances
from pop2.game_session import GameResources
from pop2.terrain import LevelMap


def inventory():
    resources = GameResources.load()
    totals, examples, panels = Counter(), {}, []
    for number in range(3, 15):
        program = cavern_assets(number)[0]
        terrain = LevelMap(resources.level(number).data)
        for view in map(int, program['rooms']):
            totals['views'] += 1
            entries = {}
            for category, records in (
                ('torch', program.get('torches', {}).get(str(view), ())),
                ('pressure', program.get('pressure_plates', {}).get('rooms', {}).get(str(view), ())),
                ('lava', program.get('lava', {}).get('rooms', {}).get(str(view), ())),
            ):
                entries[category] = {(r['room'], r['cell']) for r in records}
            slots = program.get('loose_floors', {}).get('rooms', {}).get(str(view), {})
            for category in ('cells', 'scythes', 'planks'):
                entries[category] = {tuple(key) for key in slots.get(category, ())}
            entries['potion'] = {(tile.room, tile.row * 10 + tile.column)
                                 for _, tile in cavern_flask_instances(program, view, terrain)}
            for category, keys in entries.items():
                external = sorted(key for key in keys if key[0] != view)
                totals[category + '_references'] += len(keys)
                totals[category + '_external'] += len(external)
                if external:
                    examples.setdefault(category, (number, view + 1, external[0][0] + 1, external[0][1]))
            upper = terrain.neighbor(view, 'up')
            if upper is not None:
                for column in range(10):
                    if terrain.tile(upper, column, 2).kind == 26:
                        panels.append((number, view + 1, upper + 1, column))
    return dict(totals=dict(totals), examples=examples, upper_panels=panels)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Optional JSON report path')
    args = parser.parse_args()
    report = json.dumps(inventory(), indent=2) + '\n'
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding='utf-8')
    print(report, end='')


if __name__ == '__main__':
    main()
