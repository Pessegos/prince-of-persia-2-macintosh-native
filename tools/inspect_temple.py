"""Inventory temple levels without importing assets or enabling campaign progression."""

import argparse
from collections import Counter
import json
from pathlib import Path

from tools.inspect_level7 import inspect, inventory_level


LEVELS = (10, 11, 12, 13)


def summarize(report):
    if report['level'] not in LEVELS or report['environment'] != 2 or report['opponent_set'] != 7:
        raise ValueError('Expected a temple level 10..13 with environment 2 and opponent set 7')
    generators = Counter((record[12], record[4]) for room in report['rooms']
                         for record in room['generator_records'])
    return dict(
        level=report['level'], resource_id=report['resource_id'],
        level_sha256=report['level_sha256'], start=report['start'],
        checkpoints=report['checkpoints'], reachable_rooms=report['reachable_rooms'],
        generator_count=sum(generators.values()),
        generator_kinds_and_sequences=[dict(raw_kind=kind, sequence=sequence, count=count)
                                       for (kind, sequence), count in sorted(generators.items())],
        mechanism_cells={str(kind): [dict(room=room['room'], cell=cell['cell'],
                                         foreground=cell['foreground'], reachable=room['reachable'])
                                    for room in report['rooms'] for cell in room['cells']
                                    if cell['kind'] == kind]
                         for kind in (25, 26, 43)},
        custom_candidates=[dict(room=room['room'], resource=room['custom_resource'],
                                reachable=room['reachable'],
                                present_in_scenery=(None if 'missing_custom_resources' not in report else
                                                    room['custom_resource'] not in report['missing_custom_resources']))
                           for room in report['rooms'] if room['custom_resource'] is not None],
    )


def inventory_temple_level(data, number):
    report = inventory_level(data, number)
    return summarize(report)


def run_inventory(recovery):
    reports = [inspect(recovery, number) for number in LEVELS]
    dependencies = [report['dependencies'] for report in reports]
    if any(item != dependencies[0] for item in dependencies):
        raise ValueError('Temple levels no longer share the expected dependencies')
    return dict(
        dependencies=dependencies[0],
        scenery_resources=reports[0]['scenery_resources'],
        opponent_resources=reports[0]['opponents_resources'],
        summaries=[summarize(report) for report in reports], levels=reports,
        scope=('Inventory using existing LevelDefinition/LevelMap decoders, not independent '
               'native verification of those decoders. Raw generators are not working actors. '
               'Room-link reachability is not gameplay solvability. Missing custom candidates '
               'are not fatal import errors; native loading/fallback needs separate evidence. '
               'No drawing, campaign or simulation enabled.'),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_inventory(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(dependencies=report['dependencies'], summaries=report['summaries']), indent=2))


if __name__ == '__main__':
    main()
