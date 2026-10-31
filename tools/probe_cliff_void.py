"""Bounded original undefined-cell and silent non-rooftop void-death probes.

No graphics/audio are played. The death probe records the supplied DecLifePts
and SetMode endpoints, so it certifies their admission/arguments, not their
implementation. Undefined-cell selection executes the complete native helper.
"""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from pop2.mac_resources import parse_resource_fork
from pop2.terrain import LevelMap
from tools.probe_level7_rules import NativeRules


class NativeVoid(NativeRules):
    RANGES = {4: ((0x374a, 0x3786),)}
    SUPPLIED = {}
    ENDPOINTS = {0x34f2: 'DecLifePts', 0x3196: 'SetMode'}

    def reset(self, level):
        super().reset(level)
        self.calls = []

    def dispatch(self, cpu, address, size, user):
        for offset, name in self.ENDPOINTS.items():
            if address == self.address(4, offset):
                stack = cpu.reg_read(self.registers['a7'])
                self.calls.append((name, struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]))
                cpu.reg_write(self.registers['a7'], stack + 4)
                cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])
                return
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    forks = Path(source) / 'resource_forks'
    executable = (forks / 'Prince of Persia 2.bin').read_bytes()
    program = parse_resource_fork(executable)
    levels = parse_resource_fork((forks / 'Prince.rsrc.bin').read_bytes())['LEVL']
    cells = NativeRules(program)
    count = 0
    # Imported geometry; compare only undefined cells reached by real links.
    # The caller's origin remains in a5-4fc2 during GetUndefineCellId.
    # Every level; a5-0x4fbc is the Kid room's real upper link (3:1ab0),
    # so the ruins' top-row air (4:2944-2954) is compared as well.
    for number in range(1, 15):
        data = levels[2000 + number - 1]['data']
        terrain = LevelMap(data)
        for room, column, row in product(range(32), range(-2, 12), range(-2, 6)):
            tile = terrain.tile(room, column, row)
            if tile.room is not None:
                continue
            cells.reset(data)
            cells.put_word(-0x4fc2, room + 1)
            cells.put_word(-0x4fbc, struct.unpack_from('>H', data, 0x2080 + room * 8 + 4)[0])
            original = cells.call(4, 0x28b6, (column, row))
            if original != tile.kind:
                raise AssertionError((number, room + 1, column, row, original, tile.kind))
            count += 1
    death = NativeVoid(program)
    death_cases = 0
    for number, y, velocity in product((3, 4, 5, 6, 7, 8, 9), (731, 760, 900), (0, 59, 63)):
        death.reset(levels[2000 + number - 1]['data'])
        for offset, value in ((-0x504e, 0), (-0x5050, y), (-0x5042, velocity), (-0x5046, 4)):
            death.put_word(offset, value)
        death.call(4, 0x374a)
        actual = tuple(death.word(offset) for offset in (-0x504c, -0x5050, -0x5042, -0x5046))
        if actual != (185, 730, 0, 1) or death.calls != [('DecLifePts', 100), ('SetMode', 3)]:
            raise AssertionError((number, actual, death.calls))
        death_cases += 1
    return dict(executable_sha256=hashlib.sha256(executable).hexdigest(),
                undefined_cells=count, silent_void_deaths=death_cases,
                sources=['4:28b6-29c0', '4:374a-3786'],
                supplied=['Void death: DecLifePts and SetMode recorded, not executed'],
                exclusions=['Not a full FrameAdv/CutChar trace or audio waveform comparison',
                            'Undefined cells: rooms 1-32 of LEVL 2000-2013, the Kid room as the'
                            ' lookup origin',
                            'Void death: Prince only; NPC/redraw endpoints excluded'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('rendered/cliff_void_probe.json'))
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='ascii')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
