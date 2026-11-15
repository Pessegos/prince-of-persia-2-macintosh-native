"""Original AddImgObj top-row arithmetic for every falling-slab SHAP family.

Executes CODE3:0302-030c; caller's bottom/height/A6/A3 and allocation endpoint
are supplied. Excludes image loading, clipping, pixel decoder and full draw loop.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn.m68k_const import UC_M68K_REG_A3, UC_M68K_REG_A6

from pop2.mac_resources import parse_resource_fork
from pop2.caverns import room_assets
from tools.probe_level7_rules import NativeRules


class NativeTop(NativeRules):
    RANGES = {3: ((0x0302, 0x0310),)}
    SUPPLIED = {}


def run(source):
    root = source / 'resource_forks'
    raw = (root / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((root / 'Prince.rsrc.bin').read_bytes())
    machine = NativeTop(parse_resource_fork(raw))
    output = []
    for number, name, shapes in ((3, 'Caverns.rsrc.bin', (3557, 3604)),
                                  (6, 'Ruins.rsrc.bin', (3514, 3518)),
                                  (10, 'Temple.rsrc.bin', (3528, 3529))):
        art = parse_resource_fork((root / name).read_bytes())
        level = prince['LEVL'][1999 + number]['data']
        assert struct.unpack_from('>3H', level, 0x2186) == {3: (3, 2, 3), 6: (4, 9, 6), 10: (2, 9, 10)}[number]
        _, imported, _, _ = room_assets(number, 0)
        for shape in shapes:
            assert imported['SHAP'][shape]['data'][:8] == art['SHAP'][shape]['data'][:8]
            width, height = struct.unpack_from('>2H', art['SHAP'][shape]['data'], 4)
            for bottom in (-64, -1, 0, 5, 125, 245, 365, 429):
                machine.reset(level)
                frame, record = 0xe0000, 0xb8000
                machine.cpu.reg_write(UC_M68K_REG_A6, frame)
                machine.cpu.reg_write(UC_M68K_REG_A3, record)
                machine.cpu.mem_write(frame - 8, struct.pack('>h', height))
                machine.cpu.mem_write(frame + 14, struct.pack('>h', bottom))
                machine.call(3, 0x0302, stop=(3, 0x0310))
                top = struct.unpack('>h', machine.cpu.mem_read(record + 2, 2))[0]
                assert top == bottom - height + 1
                assert not machine.services
                output.append([number, shape, width, height, bottom, top])
    return dict(comparisons=len(output), mismatches=0, outputs=output, scope=__doc__,
                original_sha256=hashlib.sha256(raw).hexdigest())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.source)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(result['comparisons'], 'comparisons,0 mismatches')
