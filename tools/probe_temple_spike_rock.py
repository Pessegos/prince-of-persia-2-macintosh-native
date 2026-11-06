"""Execute SlideRockNearSpikes 10:1fa8 and CheckSpikeHit 5:3af8 in the temple.

Real bodies: 10:1fa8, 10:2036, 10:180e, 10:1a9e, ReadCell with its room
normalization, 5:3fa4 (MobSpikes), 4:47a0 (IsDeadPos) and the column division.
Supplied: the MOB bank (one type-6 rock), the actor words and edges, and the
spike's foreground word; the impalement 5:3cee and MOB lookup 5:3f42 are sinks
that record the call. Compared with `LevelMap.slide_rock_near_spikes` and
`WallSpikes.contact`. Native X includes the 207-pixel origin.
"""

import argparse
from collections import Counter
from itertools import product
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.cavern_state import CavernState
from pop2.mac_resources import parse_resource_fork
from pop2.slide_rocks import SlideRocks
from pop2.terrain import LevelMap, TerrainMotion, floor_y
from pop2.wall_spikes import WallSpikes
from tools.probe_level7_rules import NativeRules

MOB_BANK = 0xb0010
RECORD = SimpleNamespace(offset_x=0, aux=0)
SINKS = {(5, 0x3cee): 'impale', (5, 0x3f42): 'find_mob'}


class NativeSpikeRock(NativeRules):
    RANGES = {
        3: ((0x4eb2, 0x4ee4), (0x4ef2, 0x4f30)),
        4: ((0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x322a, 0x3262), (0x3ad6, 0x3aea), (0x47a0, 0x48e8)),
        5: ((0x0004, 0x0066), (0x293c, 0x2994), (0x48b0, 0x48dc), (0x3af8, 0x3c40), (0x3fa4, 0x3fd8)),
        10: ((0x180e, 0x18f2), (0x1a9e, 0x1ae8), (0x1fa8, 0x201c), (0x2036, 0x20e8)),
        19: ((0x4bb0, 0x4bb6), (0x4bd0, 0x4bf4), (0x4bfe, 0x4c4c)),
    }
    SUPPLIED = {}

    def dispatch(self, cpu, address, size, user):
        name = SINKS.get(divmod(address - self.CODE_BASE, 0x10000))
        if name and address != self.stop_at:
            self.events.append(name)
            stack = cpu.reg_read(self.registers['a7'])
            cpu.reg_write(self.registers['d0'], 0)
            cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])
            cpu.reg_write(self.registers['a7'], stack + 4)
            return
        super().dispatch(cpu, address, size, user)

    def prepare(self, level, mob, left, width, facing=0):
        self.reset(level)
        self.events = []
        self.cpu.mem_write(MOB_BANK, struct.pack('>8h', *mob))
        self.cpu.mem_write(self.A5 - 0x4496, struct.pack('>I', MOB_BANK))
        self.put_word(-0x4490, 1)
        self.put_word(-0x3564, left)
        self.put_word(-0x3566, left + width)
        self.put_word(-0x5054, facing)


def spike_cells(level):
    rooms = struct.unpack_from('>h', level, 0x2180)[0]
    return [(room, cell) for room in range(1, rooms + 1) for cell in range(30)
            if struct.unpack_from('>H', level, (room - 1) * 60 + cell * 2)[0] == 2]


def neighbors(level, room):
    found = [room]
    for side in (0, 2):
        current = room
        for _ in range(2):
            current = struct.unpack_from('>H', level, 0x2080 + (current - 1) * 8 + side)[0]
            if not current:
                break
            if current not in found:
                found.append(current)
    return found


def near_cases(machine, levels, x_step):
    """10:1fa8 against the port, for every wall-spike cell of every level."""
    totals, mismatches = Counter(), []
    for number, level in levels.items():
        for room, cell in spike_cells(level):
            row, column = divmod(cell, 10)
            terrain = LevelMap(level)
            for rock_room, x, facing, width in product(
                    neighbors(level, room), range(-20, 520, x_step), (-1, 0), (20, 41)):
                mob = (x, 116 + row * 120, rock_room, 0, 2, 6, row, 459)
                terrain.caverns = CavernState(rocks=SlideRocks([mob]))
                machine.prepare(level, mob, 400, width, facing)
                machine.call(4, 0x27ee, (room, column, row))
                native = machine.call(10, 0x1fa8) != 0
                port = terrain.slide_rock_near_spikes(terrain.tile(room - 1, column, row),
                                                      int(facing == 0), width)
                totals[f'level {number} near' if native else f'level {number} clear'] += 1
                if port != native:
                    mismatches.append(dict(level=number, room=room, cell=cell, rock_room=rock_room,
                                           x=x, facing=facing, width=width, native=native, port=port))
    return totals, mismatches


def hit_cases(machine, level, room, cell):
    """5:3af8 against `WallSpikes.contact` with and without a rock."""
    row, spike = divmod(cell, 10)
    foreground = 0x780 + (room - 1) * 120 + cell * 4
    totals, mismatches = Counter(), []
    rocks = {'none': None, 'near': (spike + 1) * 51 - 30, 'far': (spike + 5) * 51}
    for (label, rock), pose, y, armed, facing, left, phase, kind in product(
            rocks.items(), (2, 15, 125, 121, 132, 133, 185), (row * 120 + 118, row * 120 + 40),
            (0, 1), (-1, 0), (spike * 51 + 80, spike * 51 + 92, spike * 51 + 110), (0, 1, 2, 3, 240),
            (0, 1, 4)):
        supplied = bytearray(level)
        struct.pack_into('>H', supplied, foreground, phase)
        native_x = (spike + 1) * 51 + 73 + 207
        mob = (rock if rock is not None else 0, 116 + row * 120,
               room if rock is not None else 99, 0, 2, 6, row, 459)
        machine.prepare(supplied, mob, left + 207, 30, facing)
        words = ((-0x5052, native_x), (-0x5050, y), (-0x504e, kind), (-0x504c, pose),
                 (-0x504a, spike + 1), (-0x5048, row), (-0x5040, room), (-0x503c, armed),
                 (-0x502e, 2))
        for offset, value in words:
            machine.put_word(offset, value)
        machine.call(5, 0x3af8)
        native = 'impale' in machine.events
        terrain = LevelMap(bytes(supplied))
        terrain.caverns = CavernState(rocks=SlideRocks([mob] if rock is not None else []))
        state = SimpleNamespace(actor_type=kind, source_sequence_id=2, action=pose,
                                target_x=(spike + 1) * 51 + 73, facing=int(facing == 0),
                                current_y=y - floor_y(row))
        bounds = (left + state.facing, 0, left + state.facing + 29, 0)
        hit = WallSpikes().contact(
            terrain, TerrainMotion(room - 1, row), state, RECORD, bounds, True, bool(armed),
            rock_near=lambda tile: terrain.slide_rock_near_spikes(tile, state.facing, 30))
        totals[f'{label} hit' if native else f'{label} clear'] += 1
        if (hit is not None) != native:
            mismatches.append(dict(rock=label, pose=pose, y=y, armed=armed, facing=facing, left=left,
                                   phase=phase, kind=kind, native=native, port=hit))
    return totals, mismatches


def run_probe(source, x_step=7):
    directory = Path(source) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    machine = NativeSpikeRock(parse_resource_fork(executable))
    levels = {number: bytes(prince['LEVL'][1999 + number]['data']) for number in range(10, 14)}
    near, near_bad = near_cases(machine, levels, x_step)
    room, cell = next(found for number in levels for found in spike_cells(levels[number]))
    level = next(levels[number] for number in levels if spike_cells(levels[number]))
    hit, hit_bad = hit_cases(machine, level, room, cell)
    return dict(near=dict(near), near_mismatches=len(near_bad), near_examples=near_bad[:12],
                hit=dict(hit), hit_mismatches=len(hit_bad), hit_examples=hit_bad[:12],
                spike_cells={number: len(spike_cells(level)) for number, level in levels.items()},
                supplied=__doc__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--x-step', type=int, default=7)
    args = parser.parse_args()
    report = run_probe(args.source, args.x_step)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'supplied'}, indent=1)[:3500])


if __name__ == '__main__':
    main()
