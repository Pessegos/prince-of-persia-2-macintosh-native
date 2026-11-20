"""Compare the port's object drawing order with the original SortObjTable.

Runs SortObjTable 3:3b62, CompareObj 3:3bec and GetObjForePriority 3:3e24 in
Unicorn, with no endpoint stubbed, on random object tables of two to eight
objects, against `pop2.object_order.sort_objects`. The table holds X (+0),
bottom Y (+2), pose (+8) and kind (+0xc) and is listed as DrawObjs 3:3a02-3a26
lists it, last added first. Kinds: the Prince (0), opponents 1, 2, 6, 7, 8 and
10, the hit burst/temple flame (5), the shadow's flame (14), attachments 3/9
and MOB types 0-13 (| 0x80); poses include the heads' back poses 166/181.
Coordinates come from a small range so that equal bottoms and X occur.
Excluded: DrawObj itself, attachment links (+0x16) and how objects are added.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import struct

from pop2.mac_resources import parse_resource_fork
from pop2.object_order import DrawObject, MOB, sort_objects
from tools.probe_level7_rules import NativeRules

TABLE = 0xC0000
KINDS = (0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 14) + tuple(MOB | kind for kind in range(14))
POSES = (0, 15, 150, 165, 166, 167, 173, 181, 306)


class NativeSort(NativeRules):
    RANGES = {3: ((0x3b62, 0x3bda), (0x3bec, 0x3e14), (0x3e24, 0x3e64))}
    SUPPLIED = {}

    def order(self, objects):
        self.reset(b'\0' * 16)
        for index, item in enumerate(objects):
            record = bytearray(0x1c)
            struct.pack_into('>hh', record, 0, item.x, item.y)
            struct.pack_into('>h', record, 8, item.frame)
            struct.pack_into('>h', record, 0xc, item.kind)
            self.cpu.mem_write(TABLE + 0x1c * index, bytes(record))
        self.cpu.mem_write(self.A5 - 0x4cb2, struct.pack('>I', TABLE))
        self.put_word(-0x49d0, len(objects))
        for slot, index in enumerate(range(len(objects) - 1, -1, -1)):
            self.put_word(-0x49ce + 2 * slot, index)
        self.call(3, 0x3b62)
        return [self.word(-0x49ce + 2 * slot) for slot in range(len(objects))]


def run_probe(recovery, count=20000, seed=1):
    executable = (Path(recovery) / 'resource_forks' / 'Prince of Persia 2.bin').read_bytes()
    machine = NativeSort(parse_resource_fork(executable))
    rng = random.Random(seed)
    counts, examples, digest = Counter(), [], hashlib.sha256()
    for _case in range(count):
        objects = [DrawObject(rng.randrange(-20, 60, 7), rng.randrange(100, 140, 5),
                              rng.choice(KINDS), rng.choice(POSES), index)
                   for index in range(rng.randrange(2, 9))]
        native = machine.order(objects)
        port = [item.item for item in sort_objects(objects)]
        if machine.services:
            raise AssertionError('The sort called a service')
        counts['match' if native == port else 'mismatch'] += 1
        if native != port and len(examples) < 20:
            examples.append(dict(objects=[vars(item) for item in objects], native=native, port=port))
        digest.update(struct.pack(f'>{len(native)}h', *native))
    return dict(cases=dict(counts), examples=examples, outputs_sha256=digest.hexdigest(),
                executable_sha256=hashlib.sha256(executable).hexdigest(), scope=__doc__)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='The original recovery folder')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--count', type=int, default=20000)
    args = parser.parse_args()
    report = run_probe(args.source, args.count)
    text = json.dumps(report, indent=2) + '\n'
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding='utf-8')
    print(json.dumps(report['cases']))
    if report['cases'].get('mismatch'):
        raise SystemExit(1)
