"""Execute TriggerJinnee 4:1d7e, CheckPress 5:127e and the removal 4:1d64.

Real bodies: 4:1d7e with 4:322a and 4:31fa; CheckPress with ReadCell, 4:35a6 and
4:3ff8; 4:1d64 up to its removal call. Supplied or sunk: 6:3642 returns a
supplied opponent record, JumpSeq 6:0006, the song 5:4d58, SetOppLifePts
6:2ae0, 4:34e2, the set load 3:5278 and the save 4:4a46 record their calls, and
4:4b02 is left to run so the Kid returns to the working actor. The press sinks
5:240c and 5:252e and the removal 4:48f8 record their calls. Frame flags -520a
are supplied from FRAM 750. Compared with `Jinnee.released`, `pressure_tile`
and `Jinnee.gone`. No full FrameAdv, AnimChar or drawing.
"""

import argparse
from collections import Counter
from itertools import product
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.animation_data import parse_frame_records
from pop2.jinnee import RUNNING_FLAGS, Jinnee
from pop2.loose_floors import pressure_tile
from pop2.mac_resources import parse_resource_fork
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap, TerrainMotion, floor_y
from tools.probe_level7_rules import NativeRules

RECORD = 0xb1000
ROOM, ROW = 23, 2
SINKS = {(6, 0x0006): 'jump_seq', (5, 0x4d58): 'song', (6, 0x2ae0): 'life', (4, 0x34e2): 'clear',
         (3, 0x5278): 'load_set', (4, 0x4a46): 'save', (5, 0x240c): 'press', (5, 0x252e): 'press_for_good',
         (5, 0x2710): 'loose', (7, 0x36a0): 'shelf', (4, 0x48f8): 'remove'}


class NativeJinnee(NativeRules):
    RANGES = {
        3: ((0x4eb2, 0x4ee4), (0x4ef2, 0x4f30)),
        4: ((0x1d64, 0x1d7c), (0x1d7e, 0x1f0a), (0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x31fa, 0x3262),
            (0x35a6, 0x35b8), (0x3ff8, 0x400e), (0x4b02, 0x4b14)),
        5: ((0x0004, 0x0066), (0x127e, 0x13dc), (0x48b0, 0x48dc)),
        19: ((0x4bb0, 0x4bb6), (0x4bd0, 0x4bf4), (0x4bfe, 0x4c4c)),
    }
    SUPPLIED = {}

    def dispatch(self, cpu, address, size, user):
        key = divmod(address - self.CODE_BASE, 0x10000)
        name = SINKS.get(key)
        if key == (6, 0x3642) or (name and address != self.stop_at):
            stack = cpu.reg_read(self.registers['a7'])
            if name:
                self.events.append((name, struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]))
            cpu.reg_write(self.registers['d0'], RECORD if key == (6, 0x3642) else 0)
            cpu.reg_write(self.registers['pc'], struct.unpack('>I', cpu.mem_read(stack, 4))[0])
            cpu.reg_write(self.registers['a7'], stack + 4)
            return
        super().dispatch(cpu, address, size, user)


def release_cases(machine, level):
    totals, bad = Counter(), []
    for x, facing, row in product(range(140, 400, 3), (-1, 0), (0, 1, 2)):
        machine.reset(level)
        machine.events = []
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(62))
        for offset, value in ((-0x5054, facing), (-0x5052, x + 207), (-0x5048, row), (-0x5040, ROOM),
                              (-0x504e, 0)):
            machine.put_word(offset, value)
        machine.call(4, 0x1d7e)
        record = struct.unpack('>8h', machine.cpu.mem_read(RECORD, 16))
        kid = SequenceState(91, action=109, target_x=x, facing=int(facing == 0), actor_type=0)
        port = Jinnee.released(kid, TerrainMotion(ROOM - 1, row))
        # The Kid is back in the working actor (4:4b02), the record holds the genie.
        native = (record[1] - 207, record[2], record[4], record[0] % 10, record[0] // 10)
        wanted = (port.state.target_x, -1, 180, native[3], row)
        events = [event[0] for event in machine.events]
        if native != wanted or ('jump_seq', 180) not in machine.events or ('song', 244) not in machine.events:
            bad.append(dict(x=x, facing=facing, row=row, native=native, port=wanted, events=events))
        totals['released'] += 1
    return totals, bad


def press_cases(machine, level, frames):
    totals, bad = Counter(), []
    for pose, x, y_shift, kind, state in product(
            range(150, 167), range(240, 600, 11), (0, -30), (5, 6, 34, 1, 11, 15), (8, 1)):
        supplied = bytearray(level)
        struct.pack_into('>H', supplied, (ROOM - 1) * 60 + 29 * 2, kind)
        for cell in (27, 26, 25):
            struct.pack_into('>H', supplied, (ROOM - 1) * 60 + cell * 2, kind)
        record = frames[pose - 149]
        jinnee = Jinnee(SequenceState(180, action=pose, target_x=x, facing=0, actor_type=12,
                                      animation_state=state),
                        TerrainMotion(ROOM - 1, ROW))
        contact = jinnee.column
        y = ROW * 120 + 118 + y_shift
        machine.reset(supplied)
        machine.events = []
        machine.cpu.mem_write(machine.A5 - 0x5056, bytes(62))
        for offset, value in ((-0x5054, -1), (-0x5052, x + 207), (-0x5050, y), (-0x504e, 12),
                              (-0x504c, pose), (-0x504a, contact), (-0x5048, ROW), (-0x5040, ROOM),
                              (-0x503a, -1), (-0x5046, state), (-0x520a, record.aux)):
            machine.put_word(offset, value)
        machine.call(5, 0x127e)
        native = sorted({event[0] for event in machine.events})
        terrain = LevelMap(bytes(supplied))
        view = SimpleNamespace(actor_type=12, action=pose, target_x=x, facing=0, animation_state=state,
                               current_y=y - floor_y(ROW))
        tile = pressure_tile(terrain, jinnee.motion, view, jinnee.record)
        port = ('press' if tile is not None and tile.kind in (5, 6, 34) else
                'loose' if tile is not None and tile.kind == 11 else
                'shelf' if tile is not None and tile.kind == 15 else None)
        totals[port or 'nothing'] += 1
        if native != ([port] if port else []):
            bad.append(dict(pose=pose, x=x, y=y, kind=kind, state=state, native=native, port=port))
    return totals, bad


def removal_cases(machine, level):
    totals, bad = Counter(), []
    for column in range(-4, 14):
        machine.reset(level)
        machine.events = []
        machine.put_word(-0x504a, column)
        machine.call(4, 0x1d64)
        native = any(event[0] == 'remove' for event in machine.events)
        jinnee = Jinnee(SequenceState(180, action=150, target_x=column * 51 + 60, facing=0, actor_type=12),
                        TerrainMotion(ROOM - 1, ROW))
        totals['removed' if native else 'kept'] += 1
        if jinnee.column != column or jinnee.gone != native:
            bad.append(dict(column=column, port_column=jinnee.column, native=native, port=jinnee.gone))
    return totals, bad


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    machine = NativeJinnee(parse_resource_fork((directory / 'Prince of Persia 2.bin').read_bytes()))
    level = bytes(parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())['LEVL'][2011]['data'])
    genie = parse_resource_fork((directory / 'Jinnee.rsrc.bin').read_bytes())
    frames = parse_frame_records(genie['FRAM'][750]['data'])
    if {pose: frames[pose - 149].aux for pose in RUNNING_FLAGS} != RUNNING_FLAGS:
        raise AssertionError('RUNNING_FLAGS differ from FRAM 750')
    report = {}
    for name, (totals, bad) in (('release', release_cases(machine, level)),
                                ('press', press_cases(machine, level, frames)),
                                ('removal', removal_cases(machine, level))):
        report[name] = dict(cases=dict(totals), mismatches=len(bad), examples=bad[:8])
    report['supplied'] = __doc__
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'supplied'}, indent=1)[:3000])


if __name__ == '__main__':
    main()
