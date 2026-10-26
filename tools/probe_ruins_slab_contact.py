"""Bound native falling-slab contact, special-actor crush and offscreen cells."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.animation_data import parse_frame_records
from pop2.loose_floors import FallingFloor, crush_sequence, floor_hits_actor
from pop2.mac_resources import parse_resource_fork
from pop2.ruins_actors import frame_index
from pop2.sequence_runtime import SequenceState
from tools.probe_level7_rules import NativeRules
from tools.probe_level7_sequence_selection import supporting_column


class NativeSlab(NativeRules):
    RANGES = {4: ((0x29d8, 0x2a62), (0x2bae, 0x2bcc), (0x31fa, 0x3262), (0x34f2, 0x3596),
                  (0x3a72, 0x3aea)),
              5: ((0x3642, 0x376c), (0x48b0, 0x48dc)),
              6: ((0x28f0, 0x29ea),)}
    SUPPLIED = {}
    ACTOR = 0xc0000

    def dispatch(self, cpu, address, size, user):
        if address in (self.address(4, 0x4ac0), self.address(6, 0x0006)):
            stack = cpu.reg_read(self.registers['a7'])
            destination = struct.unpack('>I', cpu.mem_read(stack, 4))[0]
            if address == self.address(4, 0x4ac0):
                # The serpent-only fallback reloads this prepared actor bank.
                cpu.mem_write(self.A5 - 0x5056, bytes(cpu.mem_read(self.ACTOR, 62)))
                self.put_word(-0x520e, self.record.offset_x)
                self.put_word(-0x520a, self.record.aux)
            else:
                self.selected = struct.unpack('>h', cpu.mem_read(stack + 4, 2))[0]
            cpu.reg_write(self.registers['a7'], stack + 4)
            cpu.reg_write(self.registers['pc'], destination)
            return
        super().dispatch(cpu, address, size, user)

    def actor(self, level, state, row, column, record, alive=True):
        self.reset(level)
        self.cpu.mem_write(self.A5 - 0x5056, bytes(62))
        self.record = record
        for offset, value in ((-0x5056, 1), (-0x5054, 0 if state.facing else -1),
                              (-0x5052, state.target_x + 207),
                              (-0x5050, 106 + row * 120 + state.current_y),
                              (-0x504e, state.actor_type), (-0x504c, state.action),
                              (-0x504a, column), (-0x5048, row), (-0x5046, state.animation_state),
                              (-0x5040, 4), (-0x503a, -1 if alive else 0), (-0x5038, 3)):
            self.put_word(offset, value)
        payload = bytes(self.cpu.mem_read(self.A5 - 0x5056, 62))
        self.cpu.mem_write(self.ACTOR, payload)
        self.selected = None
        return payload


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    head = parse_resource_fork((directory / 'Head.rsrc.bin').read_bytes())
    raw_frames = head['FRAM'][750]['data']
    frames = parse_frame_records(raw_frames)
    level = prince['LEVL'][2005]['data']
    if struct.unpack_from('>H', level, 0x218a)[0] != 6:
        raise ValueError('Expected native level-six fixture')
    machine = NativeSlab(parse_resource_fork(executable))
    counts, positives = Counter(), Counter()
    for kind, facing, x, row, dx, dy, alive, same_room, same_row in product(
            (7, 8, 11), (0, 1), range(220, 241, 2), range(3), (-1, 0, 1),
            (-1, 0, 1), (False, True), (False, True), (False, True)):
        pose = 252 if kind == 11 else 150
        index = frame_index(kind, pose)
        record = frames[index]
        state = SequenceState(131, action=pose, actor_type=kind, facing=facing,
                              target_x=x, current_y=0 if kind == 11 else -33)
        column = supporting_column(x + 207, 0 if facing else -1,
                                   raw_frames[index * 10:(index + 1) * 10])[0]
        before = machine.actor(level, state, row, column, record, alive)
        height = 0 if kind == 11 else -38
        bottom = 106 + row * 120 + state.current_y + height + dy
        block = FallingFloor(3 if same_room else 2, column + dx,
                             row if same_row else row + 1, bottom, mob_type=3)
        for offset, value in ((-0x44a6, block.x), (-0x44a4, block.y),
                              (-0x44a2, block.room + 1), (-0x449a, block.row)):
            machine.put_word(offset, value)
        expected = bool(machine.call(5, 0x3642, arg_bytes=struct.pack('>I', machine.ACTOR)))
        actual = floor_hits_actor(block, SimpleNamespace(room=3, row=row), state, record, alive)
        if actual != expected:
            raise AssertionError(('contact', kind, facing, x, row, dx, dy, alive, same_room, same_row,
                                  actual, expected))
        if (bytes(machine.cpu.mem_read(machine.ACTOR, 62)) != before
                or machine.level_bytes(len(level)) != level):
            raise AssertionError('Contact changed the supplied actor or level')
        counts['contacts'] += 1
        positives['contacts'] += int(actual)
    for kind, row, mode, pose in product((7, 8, 11), range(3), (0, 1, 2, 7, 8), (8, 109, 150, 252)):
        record = frames[frame_index(kind, 252 if kind == 11 else 150)]
        state = SequenceState(131, action=pose, actor_type=kind, facing=0,
                              target_x=230, current_y=-12, animation_state=mode)
        machine.actor(level, state, row, 4, record)
        machine.call(6, 0x28f0)
        actual = crush_sequence(state, fatal=True)
        if actual != machine.selected:
            raise AssertionError(('crush', kind, row, mode, pose, actual, machine.selected))
        if actual is not None:
            target_y = row * 120 + 106 + (0 if kind == 11 else -33)
            if machine.word(-0x5050) != target_y or machine.word(-0x5034) != -3:
                raise AssertionError('Crush did not align the actor and mark fatal damage')
            positives['crush'] += 1
        counts['crush'] += 1
    for column, row in product(range(10), (-1, 0, 1, 2, 3)):
        machine.reset(level)
        actual = machine.call(4, 0x2a38, (column, row))
        expected = 30 if row not in range(3) else row * 10 + column
        if actual != expected:
            raise AssertionError(('IndexCell1', column, row, actual, expected))
        counts['cell_index'] += 1
    if not 0 < positives['contacts'] < counts['contacts'] or not 0 < positives['crush'] < counts['crush']:
        raise AssertionError('Both admitted and rejected cases must execute')
    return dict(comparisons=dict(counts), positive_results=dict(positives), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                level_sha256=hashlib.sha256(level).hexdigest(),
                head_frames_sha256=hashlib.sha256(raw_frames).hexdigest(),
                supplied=['Serpent-only LoadActor4:4ac0 copies the prepared actor and FRAM offset/flags',
                          'JumpSeq6:0006 records selection only; no native sequence decoding',
                          'Working actor, cached foot column, original Head FRAM750 and LEVL2005'],
                scope='Real contact5:3642 including serpent neighbors/GetDist1 and real fatal '
                      'Crushed6:28f0 with SetCharFloor/DecLifePts. IndexCell1 checked separately. '
                      'Crush verifies pending damage, not downstream wound/ALIVE registration. '
                      'Excludes full scheduling, generator banks, nonfatal recovery, rendering, '
                      'full object sorting, audio and complete AI parity.')


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
