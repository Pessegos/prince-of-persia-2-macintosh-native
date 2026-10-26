"""Recover collision history4:5152 with native byte copy/fill helpers.

Current/previous physical-row globals, actor column/facing/velocity and all
eight ten-word tables are supplied. Copies19:2f72 and fill19:2ff0 execute
natively; no endpoint is replaced. No row-global update from4:4e94, collision
sweep, cells, ShapeBounds, gate response or complete FrameAdv is executed.
"""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_level7_rules import NativeRules
from tools.probe_level7_sequence_selection import signed_word
from tools.probe_temple_gate_actor_clip import put_actor
from tools.probe_temple_gate_hanging import actor_fixture
from tools.probe_temple_slide_rock_update import actor_word


TABLES = dict(upper_tags=-0x35d2, lower_tags=-0x35be, current_tags=-0x35aa,
              history_tags=-0x3596, upper_masks=-0x35fa, lower_masks=-0x35e6,
              history_masks=-0x355e, current_masks=-0x354a)


def history_reference(actor, current_row, previous_row, tables):
    if (len(actor) != 62 or actor_word(actor, 2) not in (-1, 0)
            or set(tables) != set(TABLES) or any(len(bank) != 10 for bank in tables.values())
            or not -32768 <= current_row <= 32767 or not -32768 <= previous_row <= 32767):
        raise ValueError('Outside the bounded collision-history domain')
    result = {name: list(bank) for name, bank in tables.items()}
    if previous_row in (current_row, current_row + 3, current_row - 3):
        selected = 'current'
    elif previous_row in (current_row + 1, current_row - 2):
        selected = 'upper'
    else:
        selected = 'lower'
        col, facing, velocity = (actor_word(actor, o) for o in (12, 2, 18))
        if 0 <= col <= 9 and velocity:
            forwards = velocity < 0 if facing == -1 else velocity > 0
            result['lower_masks'][col] &= 0xf0 if forwards else 0x0f
    result['history_tags'] = list(result[selected + '_tags'])
    result['history_masks'] = list(result[selected + '_masks'])
    for name in ('upper_tags', 'lower_tags', 'current_tags'):
        result[name] = [65535] * 10
    return dict(tables=result, selected=selected)


class NativeCollisionHistory(NativeRules):
    RANGES = {4: ((0x5152, 0x52aa),), 19: ((0x2f72, 0x2f8a), (0x2ff0, 0x3008))}
    SUPPLIED = {}


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    level = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL'][2009]['data']
    machine = NativeCollisionHistory(parse_resource_fork(executable))
    counts, selected, digest = Counter(), Counter(), hashlib.sha256()
    row_pairs = sorted({(current, signed_word(previous))
        for current in (-32768, -3, -1, 0, 1, 2, 3, 5, 32767)
        for previous in (current, current - 3, current - 2, current - 1,
                         current + 1, current + 2, current + 3, 7, -32768, 32767)})
    for (current, previous), column, facing, velocity, pattern in product(
            row_pairs, (-1, 0, 4, 9, 10, 1280), (-1, 0), (-32768, -1, 0, 1, 32767),
            (0x00ff, 0xafff)):
        tables = {name: [((i + 1) * 257 + c * 41) & 65535 for c in range(10)]
                  for i, name in enumerate(TABLES)}
        for name in ('upper_masks', 'lower_masks', 'current_masks'):
            tables[name] = [pattern] * 10
        actor = bytearray(actor_fixture(1, 1, column, facing, 0))
        put_actor(actor, 18, velocity)
        machine.reset(level)
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(actor))
        machine.cpu.mem_write(machine.A5 - 0x50d2, bytes(range(62)))
        machine.cpu.mem_write(machine.A5 - 0x448e, bytes(range(160)))
        for name, offset in TABLES.items():
            machine.cpu.mem_write(machine.A5 + offset, struct.pack('>10H', *tables[name]))
        machine.put_word(-0x357c, current)
        machine.put_word(-0x357e, previous)
        before = bytearray(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        expected = history_reference(bytes(actor), current, previous, tables)
        machine.call(4, 0x5152)
        for name, offset in TABLES.items():
            struct.pack_into('>10H', before, len(machine.data) + offset, *expected['tables'][name])
        after = bytes(machine.cpu.mem_read(machine.A5 - len(machine.data), len(machine.data)))
        if after != before or machine.services or machine.level_bytes(len(level)) != level:
            raise AssertionError(dict(current=current, previous=previous, column=column,
                facing=facing, velocity=velocity, selected=expected['selected'],
                changed=[(hex(i - len(machine.data)), a, b)
                         for i, (a, b) in enumerate(zip(before, after)) if a != b]))
        counts['calls'] += 1
        selected[expected['selected']] += 1
        digest.update(actor + struct.pack('>2h', current, previous))
        for bank in expected['tables'].values():
            digest.update(struct.pack('>10H', *bank))
    return dict(comparisons=dict(counts), selections=dict(selected), mismatches=0,
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
