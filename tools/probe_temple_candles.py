"""Check candle frame selection and old-export metadata against Macintosh CODE.

TempGetTorchFrame 10:12b6 and CaveGetTorchFrame 8:3b4e run with only Rnd supplied.
TriggerTorch 5:1ffa additionally supplies visibility and records AddTrob. The
existing scenery exporter runs the original room drawers, with its documented
drawing/rectangle/resource services; this is not an independent raster decoder.
No full FrameAdv, native random stream or native desktop is exercised.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import struct
from unittest.mock import patch

from pop2.cavern_state import CavernState
from pop2.caverns import temple_torch_records
from pop2.level_data import LevelDefinition
from pop2.mac_resources import parse_resource_fork
from pop2.terrain import LevelMap
from tools.extract_caverns import CavernRecovery, recover_room
from tools.probe_level7_rules import NativeRules


class NativeCandles(NativeRules):
    RANGES = {5: ((0x1ffa, 0x208e),), 8: ((0x3b4e, 0x3b78),),
              10: ((0x12b6, 0x12e2),)}
    SUPPLIED = {}
    draw = 0

    def dispatch(self, cpu, address, size, user):
        key = divmod(address - self.CODE_BASE, 0x10000)
        service = {(17, 0x6e06): 'random', (10, 0x12fa): 'visible', (5, 0x20a0): 'add_trob'}.get(key)
        if service is not None:
            stack = cpu.reg_read(self.registers['a7'])
            args = struct.unpack('>4h', cpu.mem_read(stack + 4, 8))
            self.events.append((service, args if service == 'add_trob' else args[:1]))
            result = self.draw if service == 'random' else int(service == 'visible')
            cpu.reg_write(self.registers['d0'], result)
            cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])
            cpu.reg_write(self.registers['a7'], stack + 4)
            return
        super().dispatch(cpu, address, size, user)


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    program_bytes = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince_bytes = (directory / 'Prince.rsrc.bin').read_bytes()
    temple = (directory / 'Temple.rsrc.bin').read_bytes()
    kid = (directory / 'Kid.rsrc.bin').read_bytes()
    program, prince = parse_resource_fork(program_bytes), parse_resource_fork(prince_bytes)
    machine = NativeCandles(program)
    totals = Counter()
    for number, segment, offset, count in ((10, 10, 0x12b6, 6), (3, 8, 0x3b4e, 9)):
        level = LevelDefinition.read(prince, number).data
        record = {'room': 0, 'cell': 20, 'frame_count': count}
        for previous in range(count):
            for draw in range(count):
                machine.reset(level)
                machine.events, machine.draw = [], draw
                actual = machine.call(segment, offset, (previous,))
                state = CavernState(torches={(0, 20): 0x1200 | previous})
                with patch('pop2.cavern_state.random.randint', return_value=draw) as random:
                    state.advance_torches([record, record])
                expected = state.torches[0, 20]
                assert expected == 0x1200 | actual, (number, previous, draw, actual, expected)
                assert machine.events == [('random', (count - 1,))], machine.events
                random.assert_called_once_with(0, count - 1)
                totals[f'level_{number}_frame_pairs'] += 1

    level = LevelDefinition.read(prince, 10).data
    for flags in (0, 0x10, 0x70, 0xf0):
        for draw in range(6):
            machine.reset(level)
            machine.events, machine.draw = [], draw
            bank, cell = 0x94000, 20
            machine.cpu.mem_write(machine.A5 - 0x4824, struct.pack('>I', bank))
            machine.cpu.mem_write(bank + cell * 4, struct.pack('>H', flags | 5))
            machine.call(5, 0x1ffa, (1, cell))
            actual = struct.unpack('>H', machine.cpu.mem_read(bank + cell * 4, 2))[0]
            state = CavernState()
            record = {'room': 0, 'cell': cell, 'foreground': flags | 5, 'frame_count': 6}
            with patch('pop2.cavern_state.random.randint', return_value=draw):
                state.configure_torches({'0': [record, record]})
            assert actual == state.torches[0, cell], (flags, draw, actual, state.torches)
            assert machine.events == [('visible', (1,)), ('random', (5,)),
                                      ('add_trob', (1, cell, 1, 19))], machine.events
            totals['temple_initializations'] += 1

    artwork = parse_resource_fork(temple)
    levels = {}
    # Actual source columns come directly from the native shape-info record
    # in recover_room. The fallback independently reconstructs them from X/PIEC.
    with CavernRecovery(program_bytes, (temple, kid), prince_bytes) as recovery:
        for number in (10, 11, 12, 13):
            level = LevelDefinition.read(prince, number).data
            terrain = LevelMap(level)
            sources, fragments = set(), 0
            for room in range(32):
                scene = recover_room(program_bytes, (temple, kid), level, room, prince_bytes,
                                     _machine=recovery)
                fallback = temple_torch_records(scene['commands'], terrain, room, artwork)
                key = lambda r: (r['room'], r['cell'], repr(r['command']))
                assert sorted(scene['torches'], key=key) == sorted(fallback, key=key), (number, room)
                for record in fallback:
                    sources.add((record['room'], record['cell']))
                fragments += len(fallback)
                totals['native_rooms'] += 1
            levels[number] = {'candles': len(sources), 'visible_fragments': fragments}
    return {'checks': dict(totals), 'levels': levels, 'mismatches': 0,
            'supplied': ['Rnd returns each bounded choice', 'TriggerTorch visibility true and AddTrob sink',
                         'recover_room drawing/resource/rectangle endpoints'],
            'excluded': ['full FrameAdv', 'native random stream', 'independent raster decoding',
                         'TempVisibleTorch body', 'native desktop']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
