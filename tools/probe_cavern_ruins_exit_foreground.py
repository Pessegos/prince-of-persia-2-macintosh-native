"""Check original cavern/ruins exit-frame BF promotion, not rasterization.

Enter after the moving-door image admission. The caller's next BF item,
PIEC pointer, source row clip, Prince pose/row/absolute Y and buffers are
supplied. Native conditionals, ResetNextBFItem and TransferBFItemMidFields
execute. AddNextBFItemToTable is a supplied original-SHAP-header/clip/counter
endpoint. The moving-door prefix, resources, dirty scheduling, actor drawing,
full ClipChar/FrameAdv and hardware rasterization are excluded.
"""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from tools.probe_temple_exit_foreground import NativeExitForeground


class NativeOtherExitForeground(NativeExitForeground):
    RANGES = {3: ((0x29e2, 0x2b92),), 7: ((0x27c0, 0x2802),), 8: ((0x1cfe, 0x1d7c),)}

    def drawing_clip(self):
        return struct.unpack('>4h', self.cpu.mem_read(self.A5 - 0x4600, 8))


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(executable)
    prince = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())
    digest = hashlib.sha256()
    profiles = ((3, 3, 'Caverns', 8, 0x1cfe, 0x1d7c, 3565, 14, -30, 1),
                (6, 4, 'Ruins', 7, 0x27c0, 0x2802, 3545, -11, -25, -10))
    results = []
    for number, environment, name, segment, entry, end, shape, dx, dy, clip_top in profiles:
        artwork_bytes = (forks / f'{name}.rsrc.bin').read_bytes()
        artwork = parse_resource_fork(artwork_bytes)
        level = prince['LEVL'][1999 + number]['data']
        if struct.unpack_from('>H', level, 0x2186)[0] != environment:
            raise AssertionError('Wrong original level/environment fixture')
        pieces = artwork['PIEC'][3500]['data']
        if struct.unpack_from('>2h', pieces, 0x47e) != (dx, dy):
            raise AssertionError('Unexpected exit PIEC offsets')
        if environment == 4 and struct.unpack_from('>h', pieces, 0x47c)[0] != shape - 3500:
            raise AssertionError('Unexpected ruins exit SHAP')
        machine = NativeOtherExitForeground(program, artwork)
        width, height = struct.unpack_from('>hH', artwork['SHAP'][shape]['data'], 4)
        count = promoted = 0
        for row, column, pose, y, foreground in product(
                range(3), range(10), range(216, 228), (0, -24, -25, -42), (0, 79)):
            machine.fixture(level, row, column, pose, 0, foreground)
            source_top = max(0, row * 120 + clip_top)
            machine.cpu.mem_write(machine.A5 - 0x4600, struct.pack('>4h', source_top, 0, 365, 510))
            machine.put_word(-0x5048, row)
            machine.put_word(-0x5050, row * 120 + 106 + y)
            machine.call(segment, entry, stop=(segment, end))
            front = 217 <= pose <= 226 and (environment != 3 or y < -24)
            x, bottom = column * 51 + dx, (row + 1) * 120 + 5 + dy
            expected = [['front' if front else 'back', shape, x, bottom, 16, row,
                         [max(source_top, bottom - height), max(0, x),
                          min(365, bottom), min(510, x + width)], column]]
            if machine.commands != expected:
                raise AssertionError(((number, row, column, pose, y, foreground),
                                      machine.commands, expected))
            digest.update(json.dumps([number, row, column, pose, y, foreground, machine.commands]).encode('ascii'))
            count += 1
            promoted += int(front)
        results.append(dict(environment=environment, level=number, comparisons=count, promoted=promoted,
                            artwork_sha256=hashlib.sha256(artwork_bytes).hexdigest()))
    return dict(comparisons=sum(item['comparisons'] for item in results), mismatches=0,
                profiles=results, executable_sha256=hashlib.sha256(executable).hexdigest(),
                outputs_sha256=digest.hexdigest(), scope=__doc__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
