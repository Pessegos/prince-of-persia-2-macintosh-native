"""Bound native scythe contact/trigger predicates, with QuickDraw services supplied."""

import argparse
from collections import Counter
import hashlib
from itertools import product
import json
from pathlib import Path
import struct
from types import SimpleNamespace

from pop2.animation_data import parse_frame_records
from pop2.cavern_state import CavernState
from pop2.mac_resources import parse_resource_fork
from pop2.scythes import Scythes
from pop2.sequence_runtime import SequenceState
from pop2.terrain import LevelMap
from tools.probe_level7_rules import NativeRules
from tools.probe_level7_sequence_selection import supporting_column


class NativeScythe(NativeRules):
    RANGES = {4: ((0x26e2, 0x28a8), (0x28b6, 0x29c0), (0x31fa, 0x3262)),
              5: ((0x0004, 0x0066), (0x57bc, 0x5856), (0x588a, 0x5942), (0x59e6, 0x5a0a), (0x5a1c, 0x5aae), (0x5e6c, 0x5e98))}
    SUPPLIED = {}

    def dispatch(self, cpu, address, size, user):
        stack = cpu.reg_read(self.registers['a7'])
        if address in (self.address(5, 0x5942), self.address(5, 0x584e)):
            self.hit = True
            self.reached = True
            cpu.emu_stop()
            return
        if address in (self.address(5, 0x5a44), self.address(5, 0x5928)):
            output, first, second = struct.unpack('>3I', cpu.mem_read(stack, 12))
            a = struct.unpack('>4h', cpu.mem_read(first, 8))
            b = struct.unpack('>4h', cpu.mem_read(second, 8))
            union = address == self.address(5, 0x5a44)
            rect = ((min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3]))
                    if union else
                    (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))
            nonempty = rect[0] < rect[2] and rect[1] < rect[3]
            cpu.mem_write(output, struct.pack('>4h', *(rect if union or nonempty else (0, 0, 0, 0))))
            if not union:
                cpu.mem_write(stack + 12, bytes((int(nonempty), 0)))
            cpu.reg_write(self.registers['a7'], stack + 12)
            cpu.reg_write(self.registers['pc'], address + 2)
            return
        if address == self.address(5, 0x5aa4):
            dy, dx, pointer = struct.unpack('>hhI', cpu.mem_read(stack, 8))
            t, l, b, r = struct.unpack('>4h', cpu.mem_read(pointer, 8))
            cpu.mem_write(pointer, struct.pack('>4h', t + dy, l + dx, b + dy, r + dx))
            cpu.reg_write(self.registers['a7'], stack + 8)
            cpu.reg_write(self.registers['pc'], address + 2)
            return
        super().dispatch(cpu, address, size, user)

    def prepare(self, level, motion, state, bounds, column, foreground):
        self.reset(level)
        for (room, cell), value in foreground.items():
            self.cpu.mem_write(self.LEVEL + 0x780 + room * 120 + cell * 4, struct.pack('>H', value))
        for offset, value in ((-0x504e, state.actor_type), (-0x502e, state.selected_sequence_id or 0),
                              (-0x504c, state.action), (-0x504a, column), (-0x5048, motion.row),
                              (-0x5040, motion.room + 1)):
            self.put_word(offset, value)
        l, t, r, b = bounds
        self.cpu.mem_write(self.A5 - 0x502c, struct.pack('>4h', max(0, t), max(0, l), min(365, b + 1), min(510, r + 1)))
        self.put_word(-0x503a, -1)
        self.put_word(-0x5052, state.target_x + 207)
        self.put_word(-0x5050, motion.row * 120 + 106 + state.current_y)
        self.hit = False
        return bytes(self.cpu.mem_read(self.A5 - 0x5056, 62)), self.level_bytes(len(level))

    def query(self, entry, level, motion, state, bounds, column, foreground):
        actor, prepared = self.prepare(level, motion, state, bounds, column, foreground)
        self.call(5, entry)
        if (bytes(self.cpu.mem_read(self.A5 - 0x5056, 62)) != actor
                or self.level_bytes(len(level)) != prepared):
            raise AssertionError('Contact predicate modified its actor or level fixture')
        return self.hit


def run_probe(source):
    directory = Path(source) / 'resource_forks'
    executable = (directory / 'Prince of Persia 2.bin').read_bytes()
    prince = parse_resource_fork((directory / 'Prince.rsrc.bin').read_bytes())
    kid_bytes = (directory / 'Kid.rsrc.bin').read_bytes()
    kid = parse_resource_fork(kid_bytes)
    frames = kid['FRAM'][25001]['data']
    records = parse_frame_records(frames)
    level = prince['LEVL'][2006]['data']
    machine = NativeScythe(parse_resource_fork(executable))
    terrain = LevelMap(level)
    trap = Scythes()
    terrain.caverns = CavernState(scythes=trap)
    motion = SimpleNamespace(room=18, row=2)
    counts, digest = Counter(), hashlib.sha256()
    # The independent column reference uses original FRAM bytes; the host
    # implementation uses its parsed record and floor_contact_x helper.
    for pose, facing, x, kind, phase in product(range(34, 45), (0, 1),
                                               range(260, 451, 5), (0, 2),
                                               (0, 2, 16, 17, 19)):
        state = SequenceState(4, selected_sequence_id=4, action=pose, actor_type=kind,
                              target_x=x, current_y=-20, facing=facing)
        column = supporting_column(x + 207, 0 if facing else -1,
                                   frames[pose * 10:(pose + 1) * 10])[0]
        # Supplied, inclusive body rectangles: their generation and native
        # sprite clipping are deliberately outside this contact-only probe.
        bounds = (x - 50, 270, x - 1, 326) if facing else (x, 270, x + 50, 326)
        foreground = {(18, 25): phase, (18, 26): phase}
        expected = machine.query(0x588a, level, motion, state, bounds, column, foreground)
        trap.foreground = foreground.copy()
        actual = trap.cut(terrain, motion, state, bounds, records[pose])
        if actual != expected:
            raise AssertionError(('contact', pose, facing, x, kind, phase, column, actual, expected))
        counts['contacts'] += 1
        digest.update(struct.pack('>6h?', pose, facing, x, kind, phase, column, actual))
    # Fresh, resting trap: bound the trigger predicate through its call into
    # TriggerScythe; capacity/admission and phase advancement are excluded.
    for pose, facing, x, y in product((15, 34, 39, 44), (0, 1),
                                     range(260, 401, 4), (-31, -30, 0)):
        state = SequenceState(4, selected_sequence_id=4, action=pose, actor_type=0,
                              target_x=x, current_y=y, facing=facing)
        column = supporting_column(x + 207, 0 if facing else -1,
                                   frames[pose * 10:(pose + 1) * 10])[0]
        foreground = {(18, 25): 0, (18, 26): 0}
        expected = machine.query(0x57bc, level, motion, state, (x, 270, x + 10, 346), column, foreground)
        trap.foreground, trap.active = foreground.copy(), set()
        actual = trap.trigger(terrain, motion, state, records[pose])
        if actual != expected:
            raise AssertionError(('trigger', pose, facing, x, y, column, actual, expected))
        counts['triggers'] += 1
    for row, kind in product(range(3), (0, 2)):
        machine.reset(level)
        machine.put_word(-0x5048, row)
        machine.put_word(-0x504e, kind)
        machine.put_word(-0x5050, row * 120 + 86)
        machine.call(4, 0x31fa)
        if machine.word(-0x5050) != row * 120 + 106:
            raise AssertionError('SetCharFloor did not align a cut actor')
        counts['floor_alignment'] += 1
    # Original cut sequences execute SetCharFloor before their first pose.
    for sequence, pose in ((113, 267), (190, 241)):
        words = struct.unpack('>4h', prince['SEQS'][sequence]['data'][:8])
        if words != (-7, 5, -19, pose):
            raise AssertionError(('Unexpected cut sequence prefix', sequence, words))
    return dict(comparisons=dict(counts), mismatches=0,
                executable_sha256=hashlib.sha256(executable).hexdigest(),
                kid_sha256=hashlib.sha256(kid_bytes).hexdigest(),
                contact_outputs_sha256=digest.hexdigest(),
                supplied=['QuickDraw UnionRect, SectRect and OffsetRect with original stack cleanup',
                          'Living actor snapshots, inclusive body rectangles and cached supporting column',
                          'Original LEVL2006 with both scythe foregrounds varied; Kid FRAM25001'],
                scope='CODE5:57bc trigger through5:584e and5:588a contact through5:5942, '
                      'real ReadCell/GetScytheHitType/ComputeBladeHitRect and DATA rectangles. '
                      'No death/audio/blood-write endpoints execute in contact queries. '
                      'SetCharFloor4:31fa is executed separately and original SEQS113/190 prefixes checked. '
                      'Excludes full FrameAdv, animation timing, body-edge generation, rasterization, '
                      'trap capacity/admission, neighbor/vertical crossings and complete native parity.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = run_probe(args.source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='ascii')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()

